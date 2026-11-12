"""
Pruebas Unitarias y de Integración: Historial de Ejecuciones (Execution History)
Almacenamiento 100% en memoria RAM (LangGraph MemorySaver) sin bases de datos externas.
"""

from fastapi.testclient import TestClient

from src.layer6_interface.execution_history import (
    ExecutionHistoryManager,
    execution_history_manager,
    render_execution_detail_partial,
    render_executions_partial,
)
from src.layer6_interface.web import app

client = TestClient(app)


def test_in_memory_manager_langgraph_memory_saver():
    """Valida que ExecutionHistoryManager almacene y recupere estados usando MemorySaver nativo de LangGraph."""
    mgr = ExecutionHistoryManager(max_records=10)
    rec = mgr.add_execution(
        scenario_id="DNS-NXD-01",
        model_id="qwen3-8b",
        seed=42,
        status="RESUELTO",
        is_correct=True,
        category="DNS",
        fault_class="Configuración Errónea",
        cot_explanation="Paso 1: Analizar registros DNS. Paso 2: Ejecutar dig. Causa raíz: NXDOMAIN intencional.",
        root_cause_predicted="Registro no existente",
        root_cause_expected="Registro no existente",
        component_predicted="named.conf",
        component_expected="named.conf",
        suggested_action="Verificar zona DNS",
        tool_called=True,
        tool_name="dig",
        tool_command="dig @127.0.0.1 -p 5353 app.internal.corp A",
        tool_output="status: NXDOMAIN\nANSWER: 0",
        ttft_ms=120.5,
        tok_per_sec=42.0,
        latency_ms=1500.0,
        completion_tokens=210,
    )

    assert rec["id"].startswith("exec-")
    assert len(mgr.records) == 1

    # Recuperar desde LangGraph MemorySaver
    saved_state = mgr.get_execution(rec["id"])
    assert saved_state is not None
    assert "record" in saved_state
    saved_rec = saved_state["record"]
    assert saved_rec["escenario_id"] == "DNS-NXD-01"
    assert saved_rec["tool_called"] is True
    assert "NXDOMAIN" in saved_rec["tool_output"]
    assert "Analizar registros DNS" in saved_rec["cot_explanation"]


def test_render_functions_noc_design():
    """Verifica que las funciones de renderizado produzcan tarjetas compactas NOC con atributos HTMX correctos."""
    records = [
        {
            "id": "exec-test-1",
            "timestamp": "23:15:00",
            "modelo": "Qwen 2.5 7B",
            "escenario_id": "TLS-SNI-01",
            "categoria": "TLS",
            "seed": 1337,
            "status": "RESUELTO",
            "is_correct": True,
            "tool_called": True,
            "tool_command": "openssl s_client ...",
            "latency_ms": 1420.0,
            "completion_tokens": 180,
            "cot_explanation": "Inspección de handshake TLS...",
            "root_cause_predicted": "SNI mismatch",
            "component_predicted": "nginx-ssl",
        }
    ]

    html_cards = render_executions_partial(records)
    assert "exec-test-1" in html_cards
    assert 'hx-get="/api/history/execution/exec-test-1"' in html_cards
    assert 'hx-target="#modal-visor-historial"' in html_cards
    assert 'hx-delete="/api/history/execution/exec-test-1"' in html_cards
    assert 'hx-target="#executionHistoryContainer"' in html_cards
    assert 'hx-confirm="¿Eliminar esta sesión de la RAM?"' in html_cards
    assert 'event.stopPropagation()' in html_cards
    assert "TLS-SNI-01" in html_cards
    assert "23:15" in html_cards

    html_detail = render_execution_detail_partial("exec-test-1", {"record": records[0], "rendered_html": ""})
    assert "modal-visor-backdrop" in html_detail
    assert "modal-visor-historial" in html_detail
    assert "✕ Cerrar" in html_detail
    assert "REPRODUCCIÓN HISTÓRICA EN RAM" in html_detail
    assert "LangGraph MemorySaver" in html_detail
    assert "Cadena de Razonamiento CoT" in html_detail
    assert "Inspección de handshake TLS..." in html_detail
    assert "SNI mismatch" in html_detail


def test_api_history_executions_and_detail_endpoints():
    """Verifica los endpoints HTMX /api/history/executions y /api/history/execution/{id}."""
    # 1. Asegurar registro en el manager global
    rec = execution_history_manager.add_execution(
        scenario_id="HTTP-502-01",
        model_id="phi-4-mini-instruct",
        seed=2026,
        status="RESUELTO",
        is_correct=True,
        category="HTTP",
        fault_class="Servicio Caído",
        cot_explanation="Diagnóstico de backend HTTP caído detrás del gateway.",
        root_cause_predicted="Bad Gateway por backend inalcanzable",
        root_cause_expected="Bad Gateway por backend inalcanzable",
        component_predicted="gunicorn",
        component_expected="gunicorn",
        suggested_action="Reiniciar proceso gunicorn",
        tool_called=True,
        tool_command="curl -I http://127.0.0.1:8080",
        tool_output="HTTP/1.1 502 Bad Gateway",
        ttft_ms=95.0,
        tok_per_sec=48.0,
        latency_ms=1100.0,
        completion_tokens=150,
    )
    exec_id = rec["id"]

    # 2. GET /api/history/executions
    resp_list = client.get("/api/history/executions")
    assert resp_list.status_code == 200
    assert "text/html" in resp_list.headers.get("content-type", "")
    assert exec_id in resp_list.text
    assert "HTTP-502-01" in resp_list.text
    assert f'hx-get="/api/history/execution/{exec_id}"' in resp_list.text
    assert 'hx-target="#modal-visor-historial"' in resp_list.text

    # 3. GET /api/history/execution/{id}
    resp_detail = client.get(f"/api/history/execution/{exec_id}")
    assert resp_detail.status_code == 200
    assert "text/html" in resp_detail.headers.get("content-type", "")
    assert "REPRODUCCIÓN HISTÓRICA EN RAM" in resp_detail.text
    assert "Bad Gateway" in resp_detail.text
    assert "curl -I http://127.0.0.1:8080" in resp_detail.text


def test_sidebar_history_and_f5_survival_markup():
    """Verifica que el menú lateral (Sidebar) incluya la Bitácora de Sesión con hx-get y hx-trigger=load para sobrevivir a F5."""
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

    # Contenedor en el sidebar para F5 survival
    assert 'id="sidebarHistorySection"' in html
    assert 'id="executionHistoryContainer"' in html
    assert 'hx-get="/api/history/executions"' in html
    assert 'hx-trigger="load' in html
    assert "Bitácora de Sesión" in html

    # Contenedor central del visor
    assert 'id="visor-content"' in html

    # Visor fragment
    resp_fragment = client.get("/vistas/diagnostico")
    assert resp_fragment.status_code == 200
    assert 'id="visor-content"' in resp_fragment.text

    # Limpieza en observabilidad: ya no debe contener la tabla inferior de bitácora
    resp_obs = client.get("/observabilidad")
    assert resp_obs.status_code == 200
    assert "isHistoryOpen" not in resp_obs.text


def test_app_state_in_memory_bindings():
    """Verifica que app.state exponga execution_history y memory_saver."""
    assert hasattr(app.state, "execution_history")
    assert isinstance(app.state.execution_history, list)
    assert hasattr(app.state, "memory_saver")
    # Verificar que el memory_saver sea el de LangGraph
    assert app.state.memory_saver.__class__.__name__ in ("MemorySaver", "InMemorySaver")


def test_single_scenario_stream_saves_to_memory_saver():
    """Valida que una ejecución individual desde el Visor de Diagnóstico se registre en la bitácora en RAM."""
    from unittest.mock import MagicMock, patch

    execution_history_manager.clear()
    assert len(execution_history_manager.records) == 0

    mock_diag = MagicMock()
    mock_diag.root_cause = "NXDOMAIN intencional"
    mock_diag.affected_component = "named.conf"
    mock_diag.suggested_action = "Verificar zona DNS"
    mock_diag.natural_language_explanation = "Resolución DNS fallida por NXDOMAIN"
    mock_diag.confidence_score = 0.95

    mock_resp = MagicMock()
    mock_resp.latency_ms = 120.0
    mock_resp.ttft_ms = 50.0
    mock_resp.tokens_per_second = 40.0
    mock_resp.completion_tokens = 150
    mock_resp.telemetry = MagicMock()
    mock_resp.telemetry.completion_tokens = 150

    mock_step = MagicMock()
    mock_step.tool_name = "dig"
    mock_step.tool_command = "dig @127.0.0.1 -p 5353 app.internal.corp A"
    mock_step.evidence_text = "status: NXDOMAIN"
    mock_step.hypothesis = "Posible registro inexistente"

    mock_trace = MagicMock()
    mock_trace.pasos = [mock_step]

    with patch("src.layer6_interface.observability.suite_harness.execute_trial_inference", return_value=(mock_trace, mock_diag, mock_resp)):
        with patch("scripts.regenerate_reports.regenerate_all_reports", return_value=None):
            with client.stream("GET", "/stream-diagnostico?scenario_id=DNS-NXD-01&model_id=phi-4-mini-instruct&seed=42") as resp:
                assert resp.status_code == 200
                full_text = "".join([chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk for chunk in resp.iter_text()])

    # 1. Comprobar que se guardó en la lista en memoria RAM y en MemorySaver
    assert len(execution_history_manager.records) >= 1
    latest = execution_history_manager.records[0]
    assert latest["escenario_id"] == "DNS-NXD-01"
    assert latest["seed"] == 42
    assert latest["model_id"] == "phi-4-mini-instruct"
    assert latest["modelo"] != ""  # model_name asignado correctamente

    # 2. Comprobar que en el stream SSE se emitió el OOB Swap instantáneo
    assert 'id="executionHistoryContainer" hx-swap-oob="innerHTML"' in full_text
    assert "DNS-NXD-01" in full_text

    # 3. Comprobar que el checkpoint de LangGraph MemorySaver es recuperable
    chk = execution_history_manager.get_execution(latest["id"])
    assert chk is not None
    assert chk["record"]["escenario_id"] == "DNS-NXD-01"


def test_bitacora_design_color_and_typography_compliance():
    """Valida que la bitácora utilice la paleta de colores (#003366, #0d1e33, #070e18, #38bdf8) y tipografía del Visor."""
    rec = execution_history_manager.add_execution(
        scenario_id="DNS-NXD-01",
        model_id="phi-4-mini-instruct",
        seed=42,
        status="RESUELTO",
        is_correct=True,
        category="DNS",
        fault_class="Configuración Errónea",
        cot_explanation="Análisis de resolución DNS",
        root_cause_predicted="NXDOMAIN",
        root_cause_expected="NXDOMAIN",
        component_predicted="named.conf",
        component_expected="named.conf",
        suggested_action="Verificar zona",
        tool_called=True,
        tool_name="dig",
        tool_command="dig @127.0.0.1 -p 5353 app.internal.corp A",
        tool_output="status: NXDOMAIN"
    )

    # 1. Tarjetas laterales (render_executions_partial)
    cards_html = render_executions_partial(execution_history_manager.records)
    # Colores corporativos del Visor de Diagnóstico
    assert "#0d1e33" in cards_html
    assert "#081424" in cards_html
    assert "#38bdf8" in cards_html  # Sky hover accent
    assert "rgba(0, 82, 163, 0.4)" in cards_html  # Subtle border
    assert "#10b981" in cards_html  # Green indicator dot
    # Tipografía
    assert "font-mono" in cards_html
    assert "font-sans" in cards_html

    # 2. Vista de Replay Histórico (render_execution_detail_partial)
    detail_html = render_execution_detail_partial(rec["id"], {"record": rec, "rendered_html": ""})
    assert "#0e1b2e" in detail_html or "#070e18" in detail_html
    assert "#003366" in detail_html
    assert "REPRODUCCIÓN HISTÓRICA EN RAM" in detail_html
    assert "font-mono" in detail_html
    assert "Volver a Diagnóstico" not in detail_html
    assert "modal-visor-historial" in detail_html

    # Verificaciones de las Mejoras UX
    assert "RAM:" in cards_html
    assert "/150" in cards_html
    assert "hist-filter-chip" in cards_html
    assert "Todos (" in cards_html
    assert "Resueltos (" in cards_html
    assert "Fallos (" in cards_html
    assert "data-status=" in cards_html
    assert "markActiveHistoryCard" in cards_html

    assert "Re-ejecutar" in detail_html
    assert "rerunExecution" in detail_html
    assert "Copiar Ficha" in detail_html
    assert "copyExecutionTicketMarkdown" in detail_html
    assert "ticket-raw-" in detail_html


def test_delete_execution_manager_and_endpoint():
    """Valida la eliminación individual de ejecuciones tanto en ExecutionHistoryManager como vía DELETE /api/history/execution/{id}."""
    execution_history_manager.clear()
    rec1 = execution_history_manager.add_execution(
        scenario_id="HTTP-404-01",
        model_id="qwen3-8b",
        seed=1,
        status="RESUELTO",
        is_correct=True,
    )
    rec2 = execution_history_manager.add_execution(
        scenario_id="HTTP-500-01",
        model_id="qwen3-8b",
        seed=2,
        status="FALLO",
        is_correct=False,
    )
    assert len(execution_history_manager.records) == 2

    # Eliminar rec1 vía DELETE endpoint
    resp = client.delete(f"/api/history/execution/{rec1['id']}")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")
    assert rec1["id"] not in resp.text
    assert rec2["id"] in resp.text
    assert len(execution_history_manager.records) == 1

    # Eliminar rec2 vía manager
    success = execution_history_manager.delete_execution(rec2["id"])
    assert success is True
    assert len(execution_history_manager.records) == 0


def test_full_stack_modals_and_interceptor_markup():
    """Valida que el layout principal contenga el contenedor de modal de visor, el modal de confirmación y el interceptor htmx:confirm."""
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

    # 1. Contenedor del Visor en Modal
    assert 'id="modal-visor-historial"' in html

    # 2. Contenedor y elementos del Modal de Confirmación
    assert 'id="custom-confirm-modal"' in html
    assert 'id="confirm-msg"' in html
    assert 'id="confirm-no"' in html
    assert 'id="confirm-yes"' in html
    assert "Confirmar Acción" in html
    assert "Cancelar" in html
    assert "Confirmar" in html

    # 3. Interceptor Script
    assert "htmx:confirm" in html
    assert "if (!e.detail.question)" in html
    assert "e.preventDefault()" in html
    assert "e.detail.issueRequest(true)" in html

    # 4. Atributos en los botones de acción
    assert 'hx-post="/api/history/clear"' in html
    assert 'hx-confirm="¿Está seguro de que desea limpiar la bitácora en memoria de esta sesión?"' in html


def test_undo_clear_manager_and_endpoint():
    """Valida la capacidad de Deshacer (Undo) al vaciar la bitácora en RAM sin diálogos invasivos."""
    execution_history_manager.clear()
    rec = execution_history_manager.add_execution(
        scenario_id="HTTP-403-01",
        model_id="phi-4-mini-instruct",
        seed=101,
        status="RESUELTO",
        is_correct=True,
    )
    assert len(execution_history_manager.records) == 1

    # Limpiar
    execution_history_manager.clear()
    assert len(execution_history_manager.records) == 0

    # Deshacer en manager
    recovered = execution_history_manager.undo_clear()
    assert recovered is True
    assert len(execution_history_manager.records) == 1
    assert execution_history_manager.records[0]["id"] == rec["id"]

    # Probar endpoint POST /api/history/undo-clear
    resp_clear = client.post("/api/history/clear")
    assert resp_clear.status_code == 200
    assert "Bitácora en RAM Vacía" in resp_clear.text

    resp_undo = client.post("/api/history/undo-clear")
    assert resp_undo.status_code == 200
    assert "text/html" in resp_undo.headers.get("content-type", "")
    assert rec["id"] in resp_undo.text
    assert "HTTP-403-01" in resp_undo.text
    assert len(execution_history_manager.records) == 1


def test_ux_keyboard_hints_and_scroll_memory_markup():
    """Valida la presencia de etiquetas <kbd> (Ctrl+Enter, Esc, 1-5) y funciones de scroll memory."""
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

    # 1. Botón Ejecutar con atajo Ctrl+↵
    assert "Ctrl+↵" in html
    assert "<kbd" in html

    # 2. Botones de Navegación 1 a 5 con clase nav-kbd-hint
    assert "nav-kbd-hint" in html
    assert ">1</kbd>" in html
    assert ">2</kbd>" in html
    assert ">3</kbd>" in html
    assert ">4</kbd>" in html
    assert ">5</kbd>" in html

    # 3. Tecla Esc en modal de confirmación
    assert ">Esc</kbd>" in html

    # 4. Funciones de UX: Deshacer y Scroll Memory
    assert "clearHistoryWithUndo" in html
    assert "undoClearHistory" in html
    assert "closeVisorModal" in html
    assert "savedVisorScrollTop" in html


def test_f5_reload_preserves_clear_and_deletions():
    """Valida que tras limpiar la bitácora o eliminar sesiones, recargar la página (F5) no resucite los datos."""
    # 1. Agregar ejecuciones
    execution_history_manager.clear()
    rec1 = execution_history_manager.add_execution(
        scenario_id="HTTP-503-TEST",
        model_id="qwen-7b",
        seed=1,
        status="RESUELTO",
        is_correct=True,
    )
    rec2 = execution_history_manager.add_execution(
        scenario_id="DNS-SERVFAIL-TEST",
        model_id="qwen-7b",
        seed=2,
        status="FALLO",
        is_correct=False,
    )
    assert len(execution_history_manager.records) == 2

    # 2. Eliminar rec1
    resp_del = client.delete(f"/api/history/execution/{rec1['id']}")
    assert resp_del.status_code == 200
    assert rec1["id"] not in resp_del.text
    assert rec2["id"] in resp_del.text

    # 3. Simular F5 (GET /api/history/executions)
    resp_f5 = client.get("/api/history/executions")
    assert resp_f5.status_code == 200
    assert rec1["id"] not in resp_f5.text
    assert "HTTP-503-TEST" not in resp_f5.text
    assert rec2["id"] in resp_f5.text
    assert "DNS-SERVFAIL-TEST" in resp_f5.text

    # 4. Limpiar por completo la bitácora
    resp_clr = client.post("/api/history/clear")
    assert resp_clr.status_code == 200
    assert "Bitácora en RAM Vacía" in resp_clr.text

    # 5. Simular F5 tras limpiar: la bitácora debe seguir vacía y no repoblarse
    resp_f5_after_clear = client.get("/api/history/executions")
    assert resp_f5_after_clear.status_code == 200
    assert "Bitácora en RAM Vacía" in resp_f5_after_clear.text
    assert rec1["id"] not in resp_f5_after_clear.text
    assert rec2["id"] not in resp_f5_after_clear.text
    assert len(execution_history_manager.records) == 0




