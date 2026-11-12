"""
Pruebas Unitarias para la Capa 6: Interfaz Web y API FastAPI (NetDiagBench-L7)
"""

import pytest
from fastapi.testclient import TestClient

from src.layer6_interface.web import app


@pytest.fixture
def client():
    from src.core.config import PROJECT_ROOT
    from src.layer6_interface.web import system_config
    dynamic_file = PROJECT_ROOT / "configs" / "dynamic_models.json"
    dynamic_file.write_text("[]\n", encoding="utf-8")
    sel_file = PROJECT_ROOT / "configs" / "report_selection.json"
    if sel_file.exists():
        sel_file.write_text('{"models": []}\n', encoding="utf-8")
    system_config.dynamic_models = []
    yield TestClient(app)
    dynamic_file.write_text("[]\n", encoding="utf-8")
    if sel_file.exists():
        sel_file.write_text('{"models": []}\n', encoding="utf-8")
    system_config.dynamic_models = []


def test_web_index_page(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "NetDiagBench-L7" in response.text
    assert "Ejecutar Diagnóstico" in response.text


def test_api_scenarios_endpoint(client):
    response = client.get("/api/scenarios")
    assert response.status_code == 200
    scenarios = response.json()
    assert len(scenarios) == 18


def test_api_models_endpoint(client):
    response = client.get("/api/models")
    assert response.status_code == 200
    models = response.json()
    assert len(models) >= 3


def test_api_diagnose_endpoint(client, monkeypatch):
    from src.layer6_interface.web import orchestrator
    monkeypatch.setattr(orchestrator.engine, "force_simulation", True)
    payload = {
        "scenario_id": "DNS-NXD-01",
        "model_id": "phi-4-mini-instruct",
        "seed": 42
    }
    response = client.post("/api/diagnose", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "diagnostico" in data
    assert "telemetria" in data
    assert data["diagnostico"]["scenario_id"] == "DNS-NXD-01"


def test_api_benchmark_summary_endpoint(client):
    response = client.get("/api/benchmark-summary")
    assert response.status_code == 200
    data = response.json()
    assert "report_markdown" in data
    assert "NetDiagBench-L7" in data["report_markdown"]


def test_api_correlation_analysis_endpoint(client):
    response = client.get("/api/correlation-analysis")
    assert response.status_code == 200
    data = response.json()
    assert "report_markdown" in data or "error" in data
    if "report_markdown" in data:
        assert "Correlacional" in data["report_markdown"]
        assert "correlations" in data
        assert "kruskal_wallis" in data


def test_cli_doctor_command():
    from typer.testing import CliRunner

    from src.layer6_interface.cli import app as cli_app
    runner = CliRunner()
    result = runner.invoke(cli_app, ["doctor"])
    assert result.exit_code == 0
    assert "Hardware Sistema" in result.stdout
    assert "Base RAG Normativa" in result.stdout
    assert "Catálogo Escenarios" in result.stdout


def test_cli_validate_catalog_command():
    from typer.testing import CliRunner

    from src.layer6_interface.cli import app as cli_app
    runner = CliRunner()
    result = runner.invoke(cli_app, ["validate-catalog"])
    assert result.exit_code == 0
    assert "Catálogo 100% íntegro" in result.stdout


def test_api_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert "ollama_online" in data
    assert "simulator_ready" in data
    assert data["simulator_ready"] is True


def test_api_report_html_endpoint(client):
    response = client.get("/api/report-html")
    assert response.status_code == 200
    assert "<!DOCTYPE html>" in response.text
    assert "NetDiagBench-L7" in response.text


def test_cli_export_report_command(tmp_path):
    from typer.testing import CliRunner

    from src.layer6_interface.cli import app as cli_app
    out_file = tmp_path / "test_report.html"
    runner = CliRunner()
    result = runner.invoke(cli_app, ["export-report", "--output", str(out_file)])
    assert result.exit_code == 0
    assert out_file.exists()
    assert "<!DOCTYPE html>" in out_file.read_text(encoding="utf-8")


def test_api_comparative_report_endpoint(client):
    response = client.get("/api/comparative-report")
    assert response.status_code == 200
    data = response.json()
    if "error" in data:
        pytest.skip("Dataset de benchmark no disponible")
    assert data["n_models"] >= 3
    assert data["n_scenarios"] == 18
    assert data["n_total"] == 162
    assert set(data["ranking"]) == set(data["model_ids"])
    for mid in data["model_ids"]:
        m = data["models"][mid]
        assert 0.0 <= m["efficiency_score"] <= 1.0
        assert abs(sum(m["score_components"].values()) - m["efficiency_score"]) < 0.002
        assert m["vram_gb"] > 0 and m["tokens_per_sec"] > 0
    assert len(data["scenario_matrix"]) == data["n_scenarios"]
    assert len(data["conclusions"]) in (2, 3)


def test_api_correlation_analysis_extended_payload(client):
    data = client.get("/api/correlation-analysis").json()
    if "error" in data:
        pytest.skip("Dataset de benchmark no disponible")
    for key in ("descriptives", "bootstrap_ci_95", "effect_sizes", "model_ids", "n_models"):
        assert key in data
    for mid in data["model_ids"]:
        for lo, hi in data["bootstrap_ci_95"][mid].values():
            assert lo <= hi


def test_analytics_dashboard_page(client):
    response = client.get("/analitica")
    assert response.status_code == 200
    html = response.text
    assert "Informe Técnico Comparativo (OE4)" in html
    assert "Análisis Correlacional (Tarea 4.1.2)" in html
    assert "/api/comparative-report" in html
    assert "/api/correlation-analysis" in html
    assert "/api/report-html" in html
    # Autonomo: sin dependencias externas (CDN)
    assert "<script src=" not in html


def test_index_links_to_analytics_dashboard(client):
    html = client.get("/").text
    assert "/analitica" in html


def test_observability_page(client):
    response = client.get("/observabilidad")
    assert response.status_code == 200
    html = response.text
    assert "Visor de Observabilidad" in html
    assert '<header id="visorStandaloneHeader"' in html
    assert "&larr; Panel Principal" not in html
    assert "Descargar Excel" in html
    assert "htmx.org" in html
    assert "hx-ext-sse" in html or "sse.js" in html
    assert "/stream-diagnostico" in html


def test_observability_page_embedded_header_isolated(client):
    """Verifica que en modo embed (Suite de Observabilidad) se aisle y elimine la cabecera individual del Visor."""
    response = client.get("/observabilidad?embed=true")
    assert response.status_code == 200
    html = response.text
    assert "is-embedded" in html
    assert '<header id="visorStandaloneHeader"' not in html
    assert "&larr; Panel Principal" not in html
    assert "Dashboard Analítico" not in html
    assert "Línea de Tiempo de Ejecución (LangGraph Timeline)" in html
    assert "FALLA L7 EN DIAGNÓSTICO" in html
    # Validar que los IDs y enlaces HTMX apunten a la Suite de Observabilidad
    assert 'id="suite-timeline-container"' in html
    assert 'hx-post="/api/execute-suite"' in html
    assert 'hx-target="#suite-timeline-container"' in html


def test_execute_suite_endpoint(client):
    """Verifica que el endpoint HTMX /api/execute-suite responda con el stream SSE conectado a ALL."""
    response = client.post("/api/execute-suite", data={"model_id": "qwen3-8b", "seed": "1337", "start_index": "0"})
    assert response.status_code == 200
    html = response.text
    assert 'id="timelineEventsStream"' in html
    assert 'hx-ext="sse"' in html
    assert 'sse-connect="/stream-diagnostico?scenario_id=ALL&model_id=qwen3-8b&seed=1337&start_index=0"' in html
    assert 'sse-swap="message,stream-complete"' in html
    assert 'hx-swap="beforeend"' in html


def test_stream_diagnostico_endpoint(client, monkeypatch):
    import src.layer6_interface.observability as obs
    async def mock_events(*args, **kwargs):
        yield {"event": "stream-complete", "data": ""}
    monkeypatch.setattr(obs, "generate_langgraph_sse_events", mock_events)
    with client.stream("GET", "/stream-diagnostico?scenario_id=DNS-NXD-01&model_id=phi-4-mini-instruct&seed=42") as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")


def test_index_page_contains_add_model_and_indicator(client):
    """Verifica que el panel izquierdo contenga el botón, formulario e indicador de descarga HTMX."""
    response = client.get("/")
    assert response.status_code == 200
    html = response.text
    assert "Añadir nuevo modelo" in html
    assert "btnToggleAddModel" in html
    assert "addModelBox" in html
    assert 'hx-post="/api/models/pull"' in html
    assert 'hx-indicator="#pullIndicator"' in html
    assert "Descargando pesos del modelo, por favor espere..." in html
    assert "Descargar" in html


def test_api_models_pull_empty_name(client):
    """Verifica validación de nombre de modelo vacío."""
    response = client.post("/api/models/pull", json={"model_name": ""})
    assert response.status_code == 400
    assert "no puede estar vacío" in response.text


def test_api_models_pull_success(client, monkeypatch):
    """Verifica descarga simulada exitosa e integración con HTMX y SystemConfig."""
    import subprocess

    from src.core.config import SystemConfig
    from src.layer6_interface.web import inference_engine

    # Mock subprocess.run para simular descarga rápida
    class MockCompletedProcess:
        returncode = 0
        stdout = "success"
        stderr = ""

    def mock_subprocess_run(*args, **kwargs):
        return MockCompletedProcess()

    monkeypatch.setattr(subprocess, "run", mock_subprocess_run)

    # Simular petición HTMX
    headers = {"HX-Request": "true", "Content-Type": "application/x-www-form-urlencoded"}
    data = "model_name=llama3.2:1b"
    response = client.post("/api/models/pull", content=data, headers=headers)
    assert response.status_code == 200
    html = response.text
    assert "selModelWrapper" in html
    assert "llama3-2-1b" in html
    assert 'selected="selected"' in html
    assert "descargado e integrado con éxito" in html

    # Verificar que el modelo quedó registrado en SystemConfig e InferenceEngine
    sys_cfg = SystemConfig()
    all_models = [m.id for m in sys_cfg.get_all_models()]
    assert "llama3-2-1b" in all_models
    assert "llama3-2-1b" in inference_engine.models_by_id

    # Limpiar modelo dinámico de prueba
    from src.core.config import PROJECT_ROOT
    dynamic_file = PROJECT_ROOT / "configs" / "dynamic_models.json"
    dynamic_file.write_text("[]\n", encoding="utf-8")


def test_ejecutar_alias_endpoint(client, monkeypatch):
    """Verifica que el alias /ejecutar acepte el modelo dinámico y retorne diagnóstico completo."""
    from src.layer6_interface.web import orchestrator
    monkeypatch.setattr(orchestrator.engine, "force_simulation", True)

    payload = {
        "scenario_id": "DNS-NXD-01",
        "model_id": "qwen3-8b",
        "seed": 42
    }
    response = client.post("/ejecutar", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "diagnostico" in data
    assert "telemetria" in data
    assert data["diagnostico"]["scenario_id"] == "DNS-NXD-01"


def test_index_page_ux_features(client):
    """Verifica que la página principal incorpore todas las recomendaciones UX/UI implementadas."""
    response = client.get("/")
    assert response.status_code == 200
    html = response.text

    # 1. Quick Chips de modelos
    assert "llama3.2:1b" in html
    assert "qwen2.5:1.5b" in html
    assert "deepseek-r1:1.5b" in html
    assert "phi4-mini:instruct" in html
    assert "mistral:7b" in html
    assert "selectQuickModelTag" in html

    # 2. Atajo de teclado en botón de ejecución
    assert "Ctrl+↵" in html
    assert "keydown" in html

    # 3. Historial de ejecuciones recientes
    assert "recentRunsCard" in html
    assert "recentRunsList" in html
    assert "recordRecentRun" in html
    assert "loadRecentRun" in html

    # 4. Helpers para portapapeles y exportación JSON
    assert "copyTextToClipboard" in html
    assert "copyDiagnosisMarkdown" in html
    assert "downloadDiagnosisJson" in html

    # 5. Agrupación semántica de opciones
    assert "── TERNA BASE DE INVESTIGACIÓN ──" in html or "optgroup" in html

    # 6. Botones extraídos del Dashboard Analítico en el panel
    assert "btnNavObservability" in html
    assert "btnAnalytics" in html
    assert "btnCorrAnalysis" in html
    assert "btnHtmlReport" in html
    assert "btnSuiteObservabilidad" in html
    assert "EXPORTACIÓN DE ARTEFACTOS" not in html

    # 7. Conmutador de vistas en columna derecha permanente (sin modal que tape el panel)
    assert "switchMainView" in html
    assert "mainViewIframe" in html
    assert "viewContainerObservability" in html
    assert "viewContainerIframe" in html
    assert "embeddedModal" not in html

    # 8. Paneles tipo acordeón desplegable y aprovechamiento total de pantalla
    assert "accordion-card" in html
    assert "cardConfigTest" in html
    assert "cardAnalyticsViews" in html
    assert "cardGroundTruth" in html
    assert "toggleAccordion" in html
    assert "btnToggleSidebar" in html
    assert "toggleSidebar" in html
    assert "sidebar-collapsed" in html

    # 9. Botones de descarga directa en cabecera de pestañas (Excel y PDF)
    assert "btnDownloadExcel" in html
    assert "btnDownloadPdf" in html
    assert "/api/export/excel" in html
    assert "/api/export/pdf/consolidated" in html
    assert "btnPrintView" in html
    assert "printCurrentView" in html


def test_observability_copy_and_export_buttons():
    """Verifica que los bloques renderizados de terminal y veredicto incluyan los botones interactivos."""
    from src.layer6_interface.observability import _render_final_verdict, _render_terminal_block

    rendered_term = _render_terminal_block(
        tool_name="dig",
        command="dig @127.0.0.1 -p 1053 example.com",
        output=";; ->>HEADER<<- opcode: QUERY, status: NXDOMAIN",
        exit_code=0,
    )
    assert "copyTextToClipboard" in rendered_term
    assert "Copiar comando" in rendered_term

    rendered_verdict = _render_final_verdict(
        scenario_id="DNS-NXD-01",
        root_cause="Registro inexistente NXDOMAIN",
        affected_component="Servidor CoreDNS autoritativo",
        suggested_action="Verificar zona de reenvío en named.conf",
        explanation="Consulta recursiva falló con código 3.",
        confidence_score=0.95,
        ttft_ms=120.5,
        tok_per_sec=42.1,
        vram_peak_gb=4.2,
        latency_ms=1800.0,
    )
    # Pie limpio sin saturación: telemetría y certificado presentes, botones redundantes eliminados
    assert "Telemetría de Inferencia Computada:" in rendered_verdict
    assert "NetDiagBench-L7" in rendered_verdict
    assert "Certificado Reproducible" in rendered_verdict
    assert "Copiar Markdown" not in rendered_verdict
    assert "Exportar JSON" not in rendered_verdict
    assert "Imprimir / PDF" not in rendered_verdict


def test_single_page_flow_unification(client):
    """Verifica que el menú lateral esté unificado con 'Visor de Diagnóstico' y el workspace dinámico."""
    response = client.get("/")
    assert response.status_code == 200
    html = response.text

    # 1. Unificación en el sidebar: único botón 'Visor de Diagnóstico'
    assert "btnNavObservability" in html
    assert "Visor de Diagnóstico" in html
    assert "btnNavSetup" not in html

    # 2. Workspace dinámico en contenedor principal con Doble Panel Vertical y Scroll Independiente
    assert "diagnostico-workspace" in html
    assert "flex flex-col h-full overflow-hidden" in html
    assert "viewContainerObservability" in html
    assert "viewContainerSetup" not in html
    assert "visor-resultados" in html
    assert "overflow-y-auto pb-10" in html

    # 3. Estado 1 inicial renderizado dentro de #diagnostico-workspace (Toolbar Compacta Sticky)
    assert "cardConfigTest" in html
    assert "flex flex-wrap items-end gap-4" in html
    assert "sticky top-0" in html
    assert "selScenario" in html
    assert "selModel" in html
    assert "txtSeed" in html
    assert "btnRun" in html
    assert 'hx-post="/api/ejecutar"' in html
    assert 'hx-target="#visor-resultados"' in html
    assert 'hx-indicator="#diagnostico-indicator"' in html


def test_api_configuracion_form_and_ejecutar_endpoints(client):
    """Verifica el Doble Panel Vertical y transición continua entre Configuración y Visor de Observabilidad."""
    # 1. GET /api/configuracion-form (Doble Panel: Toolbar Compacta + Visor de Resultados con Scroll)
    resp_cfg = client.get("/api/configuracion-form?scenario_id=DNS-NXD-01&model_id=phi-4-mini-instruct&seed=42")
    assert resp_cfg.status_code == 200
    html_cfg = resp_cfg.text
    assert "cardConfigTest" in html_cfg
    assert "flex flex-wrap items-end gap-4" in html_cfg
    assert "sticky top-0" in html_cfg
    assert "selScenario" in html_cfg
    assert "selModel" in html_cfg
    assert "visor-resultados" in html_cfg
    assert "overflow-y-auto pb-10" in html_cfg
    assert 'hx-post="/api/ejecutar"' in html_cfg
    assert 'hx-target="#visor-resultados"' in html_cfg

    # 2. POST /api/ejecutar (Inyección en #visor-resultados manteniendo la configuración arriba)
    form_data = {
        "scenario_id": "DNS-NXD-01",
        "model_id": "phi-4-mini-instruct",
        "seed": "42"
    }
    resp_exec = client.post("/api/ejecutar", data=form_data)
    assert resp_exec.status_code == 200
    html_exec = resp_exec.text

    # El botón "Volver a Configurar" debe haber sido eliminado porque la configuración coexiste
    assert "Volver a Configurar" not in html_exec

    # Tarjeta Problem Statement y Contenedor SSE
    assert "problem-statement-card" in html_exec
    assert "FALLA L7 A RESOLVER POR EL MODELO" in html_exec
    assert 'hx-ext="sse"' in html_exec
    assert "/stream-diagnostico" in html_exec
    assert "timelineEventsContainer" in html_exec


def test_vistas_partial_endpoints_and_navigation(client):
    """Verifica los endpoints parciales /vistas/... y los atributos data-route en la barra lateral."""
    # 1. Comprobar que el HTML principal contiene los botones con sus rutas y llamadas a switchMainView
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text
    assert 'onclick="switchMainView(\'diagnostico\')"' in html
    assert 'onclick="switchMainView(\'comparativo\')"' in html
    assert 'onclick="switchMainView(\'correlacion\')"' in html
    assert 'onclick="switchMainView(\'consolidado\')"' in html
    assert 'onclick="switchMainView(\'suite_observabilidad\')"' in html
    assert 'data-route="/vistas/diagnostico"' in html
    assert 'data-route="/analitica?view=comparativo"' in html
    assert 'data-route="/analitica?view=correlacion"' in html
    assert 'data-route="/api/report-html"' in html
    assert 'data-route="/observabilidad?embed=true"' in html
    assert "switchMainView(" in html

    # 2. Endpoint /vistas/diagnostico
    resp_diag = client.get("/vistas/diagnostico")
    assert resp_diag.status_code == 200
    assert "cardConfigTest" in resp_diag.text
    assert "selScenario" in resp_diag.text

    # 3. Endpoint /vistas/comparativo
    resp_comp = client.get("/vistas/comparativo")
    assert resp_comp.status_code == 200
    assert "/analitica?view=comparativo" in resp_comp.text

    # 4. Endpoint /vistas/correlacion
    resp_corr = client.get("/vistas/correlacion")
    assert resp_corr.status_code == 200
    assert "/analitica?view=correlacion" in resp_corr.text

    # 5. Endpoint /vistas/consolidado
    resp_cons = client.get("/vistas/consolidado")
    assert resp_cons.status_code == 200
    assert "/api/report-html" in resp_cons.text

    # 6. Endpoint /vistas/suite_observabilidad
    resp_obs = client.get("/vistas/suite_observabilidad")
    assert resp_obs.status_code == 200
    assert "/observabilidad?embed=true" in resp_obs.text


def test_contextual_header_buttons_and_exports(client):
    """Verifica la existencia y funcionamiento de los nuevos endpoints contextuales de exportación."""
    # 1. Verificar presencia de botones específicos en la cabecera principal de index
    resp_index = client.get("/")
    assert resp_index.status_code == 200
    html = resp_index.text
    assert 'id="btnDownloadDiagLog"' in html
    assert 'id="btnExportDiagPdf"' in html
    assert "Descargar Log (JSON/MD)" in html
    assert "Exportar Diagnóstico (PDF)" in html
    assert "Reporte de la Suite (PDF)" in html
    assert 'id="btnDownloadCsv"' in html
    assert "/api/export/csv" in html

    # 1.1 Endpoint /api/export/csv
    resp_csv = client.get("/api/export/csv")
    assert resp_csv.status_code == 200
    assert "text/csv" in resp_csv.headers["content-type"]

    # 2. Endpoint /api/export/pdf/suite
    resp_suite = client.get("/api/export/pdf/suite")
    assert resp_suite.status_code == 200
    assert resp_suite.headers["content-type"] == "application/pdf"
    assert "reporte_suite_observabilidad" in resp_suite.headers.get("content-disposition", "")
    assert ".pdf" in resp_suite.headers.get("content-disposition", "")

    # 3. Endpoint /api/export/pdf/diagnosis
    resp_diag_pdf = client.get("/api/export/pdf/diagnosis?scenario_id=DNS-NXD-01&model_id=phi-4-mini-instruct&seed=42")
    assert resp_diag_pdf.status_code == 200
    assert resp_diag_pdf.headers["content-type"] == "application/pdf"
    assert "diagnostico_DNS-NXD-01_phi-4-mini-instruct.pdf" in resp_diag_pdf.headers.get("content-disposition", "")

    # 4. Endpoint /api/export/diagnostic-log (JSON y MD)
    resp_log_json = client.get("/api/export/diagnostic-log?scenario_id=DNS-NXD-01&model_id=phi-4-mini-instruct&seed=42&format=json")
    assert resp_log_json.status_code == 200
    assert "application/json" in resp_log_json.headers["content-type"]
    log_data = resp_log_json.json()
    assert log_data["scenario"]["scenario_id"] == "DNS-NXD-01"
    assert log_data["model"]["model_id"] == "phi-4-mini-instruct"

    resp_log_md = client.get("/api/export/diagnostic-log?scenario_id=DNS-NXD-01&model_id=phi-4-mini-instruct&seed=42&format=md")
    assert resp_log_md.status_code == 200
    assert "text/markdown" in resp_log_md.headers["content-type"]
    assert "Log de Diagnóstico L7: DNS-NXD-01" in resp_log_md.text


def test_expandable_system_lines_in_observability():
    """Verifica que las líneas de telemetría y RFC sean tarjetas de nodo completas en el timeline con Dashboard de Pestañas."""
    from src.layer6_interface.observability import _render_subtle_system_line

    rendered = _render_subtle_system_line(
        node_name="ingest_telemetry",
        text="Minería Drain3 finalizada",
        payload='{"status": "ok", "logs": 6}'
    )

    # 1. Contenedor de nodo y eje vertical con ícono circular
    assert "relative pl-[3.25rem] pb-6" in rendered
    assert "w-8 h-8 rounded-full bg-slate-800 border-2 border-slate-600" in rendered
    assert "translate-x-[5px]" in rendered

    # 2. Tarjeta principal Dashboard de Pestañas con Acordeón Semántico (details/summary)
    assert "<details class=\"group bg-[#101624] border border-slate-800/80 rounded-xl overflow-hidden shadow-sm\"" in rendered
    assert "<details open" not in rendered  # Inicia colapsado por defecto
    assert "<summary class=\"flex flex-wrap gap-4 items-center justify-between p-4 cursor-pointer list-none hover:bg-slate-800/40 transition-colors select-none\"" in rendered
    assert "group-open:rotate-180" in rendered
    assert "<div class=\"border-t border-slate-800/80 p-4\">" in rendered
    assert 'role="tablist"' in rendered
    assert "Vista" in rendered
    assert "JSON crudo" in rendered

    # 3. Componentes de Ingesta (KPIs, timeline, templates, tabla, crudo)
    assert "Ingesta de telemetría L7" in rendered
    assert "Drain3 Log Parser v0.9.11" in rendered
    assert "Eventos ingeridos" in rendered
    assert "Patrones distintos" in rendered
    assert "Tasa NXDOMAIN" in rendered
    assert "Línea de tiempo de consultas" in rendered
    assert "Patrones extraídos por Drain3" in rendered
    assert "Eventos crudos (orden cronológico)" in rendered
    assert "payload_drain3.json" in rendered
    assert "bg-[#090b10]" in rendered
    assert "rounded-t-none" in rendered
    assert "rounded-b-lg" in rendered
    assert "overflow-auto" in rendered

    # 4. Resaltado de sintaxis JSON
    assert "text-blue-300" in rendered
    assert "text-emerald-300" in rendered
    assert "text-orange-300" in rendered
    assert "status" in rendered
    assert "ok" in rendered
    assert "logs" in rendered

    # 5. Verificación de nodo RAG (Dashboard RAG, hits, checklist, rcodes, crudo)
    rendered_rfc = _render_subtle_system_line(
        node_name="retrieve_rfc_standards",
        text="RFC 1035",
        payload="=== BASE NORMATIVA ===\n--- [NORMA 1]: sop_dns.md ---\n- **Def:** `dig test`"
    )
    assert "relative pl-[3.25rem] pb-6" in rendered_rfc
    assert "w-8 h-8 rounded-full bg-slate-800 border-2 border-slate-600" in rendered_rfc
    assert "<details class=\"group bg-[#101624] border border-slate-800/80 rounded-xl overflow-hidden shadow-sm\"" in rendered_rfc
    assert "<details open" not in rendered_rfc  # Inicia colapsado por defecto
    assert "<summary class=\"flex flex-wrap gap-4 items-center justify-between p-4 cursor-pointer list-none hover:bg-slate-800/40 transition-colors select-none\"" in rendered_rfc
    assert "group-open:rotate-180" in rendered_rfc
    assert "<div class=\"border-t border-slate-800/80 p-4\">" in rendered_rfc
    assert "Recuperación normativa IETF (RAG)" in rendered_rfc
    assert "Markdown crudo" in rendered_rfc
    assert "rag_context_output.md" in rendered_rfc
    assert "Verificación técnica obligatoria" in rendered_rfc
    assert "RFC 1035 §4.1.1 · Códigos de respuesta" in rendered_rfc
    assert "NXDOMAIN" in rendered_rfc
    assert "text-blue-300" in rendered_rfc
    assert "text-amber-300" in rendered_rfc
    assert "text-emerald-400" in rendered_rfc
    assert "text-white font-bold" in rendered_rfc


def test_dynamic_coherence_tls_and_http_in_observability():
    """Verifica que Ingesta y RAG sean dinámicos y coherentes para TLS y HTTP."""
    import json

    from src.layer6_interface.observability import _render_subtle_system_line

    # 1. Caso TLS (TLS-CIPH-01)
    tls_payload = json.dumps({
        "scenario_id": "TLS-CIPH-01",
        "category": "TLS",
        "fault_class": "TLS_CIPHER_MISMATCH",
        "target_component": "nginx-ssl",
        "raw_telemetry_logs": [
            {"timestamp": "2026-09-25 10:00:00", "source_service": "nginx-ssl", "log_level": "INFO", "raw_message": "127.0.0.1 TLS client hello offered suites: [TLS_RSA_WITH_AES_128_CBC_SHA]", "code": "TLS"},
            {"timestamp": "2026-09-25 10:00:04", "source_service": "nginx-ssl", "log_level": "ERROR", "raw_message": "SSL_do_handshake() failed (SSL: error:0A000410:SSL routines::sslv3 alert handshake failure) while SSL handshaking", "code": "CIPHER_ERR"}
        ]
    })
    rendered_tls_ingest = _render_subtle_system_line(
        node_name="ingest_telemetry",
        text="Minería TLS finalizada",
        payload=tls_payload,
        scenario_id="TLS-CIPH-01",
        category="TLS",
        fault_class="TLS_CIPHER_MISMATCH"
    )
    assert "Nginx SSL / TLS Handshake Engine" in rendered_tls_ingest
    assert "Tasa TLS_CIPHER_MISMATCH" in rendered_tls_ingest
    assert "CIPHER_ERR" in rendered_tls_ingest
    assert "Estado TLS" in rendered_tls_ingest
    assert "Servidor SNI" in rendered_tls_ingest
    assert "Línea de tiempo de eventos" in rendered_tls_ingest

    tls_rag_payload = (
        "=== BASE NORMATIVA IETF & ESTÁNDARES RFC (RFC 8446 (TLS 1.3)) ===\n"
        "Escenario: [TLS] TLS-CIPH-01 - Falla L7: TLS_CIPHER_MISMATCH\n"
        "Consulta RAG: 'RFC 8446 (TLS 1.3) TLS_CIPHER_MISMATCH TLS TLS-CIPH-01' (Presupuesto RAM: 0.02 MB)\n"
        "--- [NORMA / PROCEDIMIENTO 1]: sop_nginx_gateway_troubleshooting.md -> 2.3. Síntoma: Fallo en Negociación TLS / SSL Handshake Failed (Score: 4.2150) ---\n"
        "Fallo en negociación TLS\n"
        "--- [NORMA / PROCEDIMIENTO 2]: rfc8446_tls_excerpts.md -> 6.2. Error Alerts (Score: 3.8400) ---\n"
        "Alert Protocol"
    )
    rendered_tls_rag = _render_subtle_system_line(
        node_name="retrieve_rfc_standards",
        text="RFC 8446",
        payload=tls_rag_payload,
        scenario_id="TLS-CIPH-01",
        category="TLS",
        fault_class="TLS_CIPHER_MISMATCH"
    )
    assert "RFC 8446 (TLS 1.3)" in rendered_tls_rag
    assert "openssl s_client" in rendered_tls_rag
    assert "HANDSHAKE_FAIL" in rendered_tls_rag
    assert "nginx -s reload" in rendered_tls_rag
    assert "RFC 8446 §6.2 · Alertas y Errores TLS" in rendered_tls_rag

    # 2. Caso HTTP 502 (HTTP-502-01)
    http_payload = json.dumps({
        "scenario_id": "HTTP-502-01",
        "category": "HTTP_WEB",
        "fault_class": "HTTP_502_BAD_GATEWAY",
        "target_component": "nginx",
        "raw_telemetry_logs": [
            {"timestamp": "2026-09-25 10:00:00", "source_service": "nginx", "log_level": "INFO", "raw_message": '127.0.0.1 - - [GET /static/style.css HTTP/1.1] 200 4521 "-" "curl/8.4.0"', "code": "200"},
            {"timestamp": "2026-09-25 10:00:04", "source_service": "nginx", "log_level": "ERROR", "raw_message": '[error] connect() failed (111: Connection refused) while connecting to upstream: "http://127.0.0.1:8080/api/v1/users"', "code": "502"}
        ]
    })
    rendered_http_ingest = _render_subtle_system_line(
        node_name="ingest_telemetry",
        text="Minería HTTP finalizada",
        payload=http_payload,
        scenario_id="HTTP-502-01",
        category="HTTP_WEB",
        fault_class="HTTP_502_BAD_GATEWAY"
    )
    assert "Nginx Reverse Proxy / Upstream Gateway" in rendered_http_ingest
    assert "Tasa HTTP_502_BAD_GATEWAY" in rendered_http_ingest
    assert "502" in rendered_http_ingest
    assert "Status HTTP" in rendered_http_ingest
    assert "Upstream Socket" in rendered_http_ingest

    http_rag_payload = (
        "=== BASE NORMATIVA IETF & ESTÁNDARES RFC (RFC 9110 (HTTP Semantics)) ===\n"
        "Escenario: [HTTP_WEB] HTTP-502-01 - Falla L7: HTTP_502_BAD_GATEWAY\n"
        "Consulta RAG: 'RFC 9110 (HTTP Semantics) HTTP_502_BAD_GATEWAY HTTP_WEB HTTP-502-01' (Presupuesto RAM: 0.02 MB)\n"
    )
    rendered_http_rag = _render_subtle_system_line(
        node_name="retrieve_rfc_standards",
        text="RFC 9110",
        payload=http_rag_payload,
        scenario_id="HTTP-502-01",
        category="HTTP_WEB",
        fault_class="HTTP_502_BAD_GATEWAY"
    )
    assert "RFC 9110 (HTTP Semantics)" in rendered_http_rag
    assert "curl -I" in rendered_http_rag
    assert "BAD_GATEWAY" in rendered_http_rag
    assert "systemctl restart backend-app" in rendered_http_rag
    assert "RFC 9110 §15 · Códigos de estado HTTP" in rendered_http_rag


def test_stop_suite_endpoint():
    """Verifica que el endpoint /api/stop-suite suspenda la bandera global limpiamente."""
    from fastapi.testclient import TestClient

    import src.layer6_interface.observability as obs
    from src.layer6_interface.web import app

    client = TestClient(app)
    resp = client.post("/api/stop-suite")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "paused"
    assert obs._suite_active_flag is False


def test_execute_suite_pause_and_resume():
    """Verifica que /api/execute-suite reciba start_index y genere la URL SSE correspondiente."""
    from fastapi.testclient import TestClient

    import src.layer6_interface.observability as obs
    from src.layer6_interface.web import app

    client = TestClient(app)

    # 1. Enviar con start_index=5
    resp = client.post(
        "/api/execute-suite",
        data={"scenario_id": "ALL", "model_id": "qwen3-8b", "seed": "42", "start_index": "5"}
    )
    assert resp.status_code == 200
    html = resp.text
    assert "start_index=5" in html
    assert "timelineEventsStream" in html
    assert obs._suite_active_flag is True

    # 2. Enviar con start_index >= 18 debe reiniciar a 0
    resp_reset = client.post(
        "/api/execute-suite",
        data={"scenario_id": "ALL", "model_id": "qwen3-8b", "seed": "42", "start_index": "18"}
    )
    assert resp_reset.status_code == 200
    assert "start_index=0" in resp_reset.text

    # 3. Enviar con start_index=19 también debe reiniciar a 0
    resp_reset19 = client.post(
        "/api/execute-suite",
        data={"scenario_id": "ALL", "model_id": "glm-4-9b", "seed": "1337", "start_index": "19"}
    )
    assert resp_reset19.status_code == 200
    assert "start_index=0" in resp_reset19.text


def test_observabilidad_alpine_pause_resume_markup():
    """Verifica que la vista /observabilidad contenga los componentes Alpine.js para Pausa y Reanudación."""
    from fastapi.testclient import TestClient

    from src.layer6_interface.web import app

    client = TestClient(app)
    resp = client.get("/observabilidad")
    assert resp.status_code == 200
    html = resp.text

    # Reactividad Alpine.js en el panel de control
    assert 'x-data="{ isRunning: false, currentIndex: 0, totalCases: 18 }"' in html
    assert '@suite-progress.window=' in html
    assert '@suite-finished.window=' in html
    assert '@suite-paused.window=' in html
    assert 'x-text="currentIndex"' in html

    # Lógica visual de los botones Iniciar y Reanudar
    assert "REANUDAR" in html
    assert "INICIAR" in html
    assert 'x-text="currentIndex > 0 && currentIndex < totalCases ? \'REANUDAR\' : \'INICIAR\'"' in html
    assert '@click="if(currentIndex >= totalCases) currentIndex = 0; isRunning = true;"' in html
    assert '@change="currentIndex = 0; isRunning = false;' in html
    assert 'x-show="currentIndex > 0 && currentIndex < totalCases && !isRunning"' in html
    assert ':disabled="isRunning"' in html
    assert ':disabled="!isRunning"' in html
    assert 'stopStreaming()' in html
    assert 'clearTimeline()' in html


def test_htmx_anti_flicker_and_fragment_rendering(client):
    """Verifica la erradicación del bloque heredado de cabecera, control de caché y renderizado de fragmentos."""
    # 1. Verificar que 'Dashboard Analítico · NetDiagBench-L7' no existe en ninguna vista ni en la analítica
    resp_index = client.get("/")
    assert "Dashboard Analítico · NetDiagBench-L7" not in resp_index.text

    resp_analitica = client.get("/analitica")
    assert resp_analitica.status_code == 200
    assert "Dashboard Analítico · NetDiagBench-L7" not in resp_analitica.text
    assert "<header>" not in resp_analitica.text
    assert '<body class="is-embedded">' in resp_analitica.text
    assert "header, .tabs, .hdr-actions { display: none !important; }" in resp_analitica.text

    # 2. Control de caché e historial en fragmentos de vistas
    for path in ["/vistas/comparativo", "/vistas/correlacion", "/vistas/diagnostico", "/vistas/consolidado", "/vistas/suite_observabilidad"]:
        resp_v = client.get(path)
        assert resp_v.status_code == 200
        assert resp_v.headers.get("hx-push-url") == "false" or resp_v.headers.get("HX-Push-Url") == "false"
        assert "no-store" in resp_v.headers.get("cache-control", "")
        assert 'hx-history="false"' in resp_v.text

    # 3. Endpoints directos /comparativo y /correlacional con HX-Request
    resp_comp_htmx = client.get("/comparativo", headers={"HX-Request": "true"})
    assert resp_comp_htmx.status_code == 200
    assert 'hx-history="false"' in resp_comp_htmx.text
    assert "/analitica?view=comparativo" in resp_comp_htmx.text

    resp_corr_htmx = client.get("/correlacional", headers={"HX-Request": "true"})
    assert resp_corr_htmx.status_code == 200
    assert 'hx-history="false"' in resp_corr_htmx.text
    assert "/analitica?view=correlacion" in resp_corr_htmx.text

    # 4. Redirección si no es HX-Request
    resp_comp_direct = client.get("/comparativo", follow_redirects=False)
    assert resp_comp_direct.status_code == 303
    assert resp_comp_direct.headers["location"] == "/?view=comparativo"

    resp_corr_direct = client.get("/correlacional", follow_redirects=False)
    assert resp_corr_direct.status_code == 303
    assert resp_corr_direct.headers["location"] == "/?view=correlacion"

    # 5. Desactivación de caché de historial HTMX en la página principal
    assert "hx-history=\"false\"" in resp_index.text
    assert "historyCacheSize = 0" in resp_index.text


def test_ux_enhancements_phase1_and_phase2(client):
    """Verifica las optimizaciones de experiencia de usuario de Fase 1 y Fase 2."""
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

    # 1. Deep linking y sincronización de parámetros
    assert "syncUrlParams" in html
    assert "window.location.search" in html

    # 2. Paleta de comandos (Ctrl + K)
    assert 'id="btnCommandPalette"' in html
    assert 'id="commandPaletteInput"' in html
    assert 'id="commandPaletteList"' in html
    assert "showCommandPalette" in html
    assert "openCommandPalette" in html
    assert "closeCommandPalette" in html
    assert "Ctrl+K" in html

    # 3. Banner proactivo de Ollama
    assert 'id="ollamaOfflineBanner"' in html
    assert "checkHealthAndSync" in html
    assert "ollama serve" in html

    # 4. Atajos numéricos 1-5 en keydown
    assert "evt.key === '1'" in html
    assert "evt.key === '5'" in html

    # 5. Ficha técnica para ticket
    assert "copyTicketToClipboard" in html
    assert "Copiar Ficha para Ticket" in html

    # 6. Tooltips explicativos en analítica
    resp_an = client.get("/analitica")
    assert resp_an.status_code == 200
    an_html = resp_an.text
    assert "Spearman rho" in an_html or "Spearman" in an_html
    assert "Kruskal-Wallis" in an_html
    assert "Bootstrap" in an_html
    assert "title=" in an_html


def test_security_headers_middleware_and_cors(client):
    """Verifica que el middleware inyecte cabeceras de seguridad HTTP OWASP en todas las respuestas."""
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.headers.get("x-frame-options") == "SAMEORIGIN"
    assert response.headers.get("x-content-type-options") == "nosniff"
    assert response.headers.get("referrer-policy") == "strict-origin-when-cross-origin"
    assert response.headers.get("x-xss-protection") == "1; mode=block"


def test_path_traversal_prevention_in_exports(client):
    """Verifica que los endpoints de exportación rechacen con HTTP 400 secuencias maliciosas de Path Traversal."""
    malicious_inputs = ["../../etc/passwd", "..\\..\\windows\\win.ini", "%2e%2e/secret"]
    for evil in malicious_inputs:
        resp_diag = client.get(f"/api/export/pdf/diagnosis?scenario_id={evil}&model_id=phi-4-mini-instruct")
        assert resp_diag.status_code == 400
        assert "no permitidos" in resp_diag.text

        resp_log = client.get(f"/api/export/diagnostic-log?scenario_id={evil}&model_id=phi-4-mini-instruct")
        assert resp_log.status_code == 400
        assert "no permitidos" in resp_log.text

        resp_excel = client.get(f"/api/export/excel?run_id={evil}")
        assert resp_excel.status_code == 400
        assert "no permitidos" in resp_excel.text


def test_anti_formula_injection_sanitization():
    """Verifica que el sanitizador de hojas de cálculo neutralice caracteres de inyección de fórmulas."""
    from src.layer7_evaluator.excel_exporter import sanitize_cell_value

    assert sanitize_cell_value("=cmd|' /C calc'!A0") == "'=cmd|' /C calc'!A0"
    assert sanitize_cell_value("@SUM(A1:A10)") == "'@SUM(A1:A10)"
    assert sanitize_cell_value("+malicious_cmd()") == "'+malicious_cmd()"
    assert sanitize_cell_value("\t=1+1") == "'\t=1+1"
    # Número legítimo negativo no se altera
    assert sanitize_cell_value("-12.5") == "-12.5"
    assert sanitize_cell_value(-5.0) == -5.0
    # Texto regular no se altera
    assert sanitize_cell_value("Diagnóstico normal de DNS") == "Diagnóstico normal de DNS"


def test_custom_tooltip_component_in_all_views(client):
    """Verifica que todas las vistas incorporen el componente moderno de Tooltips NOC (#netdiag-custom-tooltip)."""
    # 1. Página Principal (Index)
    resp_index = client.get("/")
    assert resp_index.status_code == 200
    assert "netdiag-custom-tooltip" in resp_index.text
    assert "ensureTooltip" in resp_index.text
    assert "formatTooltipContent" in resp_index.text

    # 2. Dashboard Analítico (/analitica)
    resp_analitica = client.get("/analitica")
    assert resp_analitica.status_code == 200
    assert "netdiag-custom-tooltip" in resp_analitica.text
    assert "ensureTooltip" in resp_analitica.text
    assert "<script src=" not in resp_analitica.text  # Autonomía intacta

    # 3. Suite de Observabilidad (/observabilidad)
    resp_obs = client.get("/observabilidad")
    assert resp_obs.status_code == 200
    assert "netdiag-custom-tooltip" in resp_obs.text
    assert "ensureTooltip" in resp_obs.text


def test_tooltip_elimination_on_explicit_buttons_and_preserved_technical_icons(client):
    """
    Verifica las reglas estrictas de UX/UI para eliminar ruido visual:
    1. PROHIBIDO: Botones con texto explícito (Ocultar Panel, Descargar Excel/PDF/JSON, Imprimir)
       y controles universales (Buscador, Modo Día/Noche) no deben poseer atributo 'title'.
    2. PERMITIDO: Íconos técnicos de información (ℹ️) en métricas complejas (Spearman, Kruskal-Wallis, Cohen's d).
    3. ENGINE: isEligibleForTooltip está presente en el helper global.
    """
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

    # 1. Botones principales del visor limpios de tooltips redundantes
    assert 'id="togglePanelBtn" data-testid="btnToggleSidebar" class="view-header-btn btn-toggle-panel"' in html
    assert 'title="Colapsar o expandir' not in html
    assert 'id="btnDownloadDiagLog" class="view-header-btn" onclick="downloadCurrentDiagnosticLog()"' in html
    assert 'id="btnPrintView" class="view-header-btn" onclick="printCurrentView()"' in html
    assert 'id="btnDownloadExcel" href="/api/export/excel"' in html

    # 2. Controles universales sin tooltip
    assert 'id="btnCommandPalette"' in html
    assert 'title="Abrir paleta de comandos' not in html
    assert 'id="themeToggleBtnHeader"' in html
    assert 'title="Alternar Modo Nocturno' not in html

    # 3. Motor JS con reglas estrictas de elegibilidad
    assert "isEligibleForTooltip" in html
    assert "CANDIDATE_SELECTOR" in html

    # 4. En analítica, los íconos técnicos informativos (ℹ️) se conservan para métricas complejas
    resp_an = client.get("/analitica")
    assert resp_an.status_code == 200
    an_html = resp_an.text
    assert "ℹ️" in an_html
    assert 'title="d de Cohen:' in an_html
    assert 'title="Spearman rho:' in an_html
    assert 'title="Prueba estadística no paramétrica H de Kruskal-Wallis' in an_html


def test_navbar_institutional_logos_and_typographic_brand(client):
    """
    Verifica que el navbar superior incorpore los logos institucionales y la tipografía Tailwind de marca:
    - Logo Unipamplona (image_1077e9.png) con h-10 w-auto object-contain
    - Logo Telecomunicaciones (image_1074a1.png) con h-10 w-auto object-contain
    - Contenedor de logos con flex items-center gap-2
    - Tipografía continua NetDiagBench-L7 con text-white, text-cyan-400 y sin bordes en el sufijo
    - Badge de versión v1.0.0 con estilo bg-rose-950/50 text-rose-400 border border-rose-800/50
    """
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

    # Logos institucionales
    assert "image_1077e9.png" in html
    assert "image_1074a1.png" in html
    assert "h-10 w-auto object-contain" in html
    assert "flex items-center gap-2" in html

    # Tipografía de Marca
    assert "text-2xl font-extrabold tracking-tight flex items-center" in html
    assert "text-white" in html
    assert "NetDiag" in html
    assert "text-cyan-400" in html
    assert "Bench" in html
    assert '<span class="text-white">NetDiag</span><span class="text-cyan-400">Bench</span><span class="text-white">-L7</span>' in html
    assert "-L7" in html
    assert "Universidad de Pamplona" in html
    assert "Diagnóstico Reproducible L7 con SLMs" in html

    # Badge de versión
    assert "bg-rose-950/50 text-rose-400 border border-rose-800/50 rounded-md" in html
    assert "v1.0.0" in html

    # Probar que las imágenes se sirven estáticamente vía HTTP con 200 OK y mimetype image/png
    resp_uni = client.get("/static/img/image_1077e9.png")
    assert resp_uni.status_code == 200
    assert "image/png" in resp_uni.headers.get("content-type", "")

    resp_tele = client.get("/static/img/image_1074a1.png")
    assert resp_tele.status_code == 200
    assert "image/png" in resp_tele.headers.get("content-type", "")

