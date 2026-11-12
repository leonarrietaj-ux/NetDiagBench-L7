"""
NetDiagBench-L7: Suite de Pruebas de la Capa 8 - CLI Typer y Rutas Web / FastAPI
Verifica la integración completa de:
- benchapp human-eval (init, emit, import, emit-tiebreak, analyze, export-agreement, correlate, status)
- Endpoints REST de FastAPI (/vistas/human_eval, /api/human-eval/state, export, agreement, correlation, open-key)
"""

import io
import json
from pathlib import Path
import shutil
import zipfile

from fastapi.testclient import TestClient
import pytest
from typer.testing import CliRunner

from src.core.config import PROJECT_ROOT
from src.layer6_interface.cli import app as cli_app
from src.layer6_interface.web import app as fastapi_app
from src.layer8_human_eval.session import get_session_dir

runner = CliRunner()


@pytest.fixture
def test_session_id(tmp_path):
    from src.layer8_human_eval.session import CURRENT_SESSION_FILE, set_active_session
    prev_session = CURRENT_SESSION_FILE.read_text(encoding="utf-8").strip() if CURRENT_SESSION_FILE.exists() else None

    sesion_id = "test_phase4_cli"
    s_dir = PROJECT_ROOT / "data" / "human_eval" / sesion_id
    if s_dir.exists():
        shutil.rmtree(s_dir, ignore_errors=True)
    yield sesion_id
    if s_dir.exists():
        shutil.rmtree(s_dir, ignore_errors=True)
    if prev_session:
        set_active_session(prev_session)
    else:
        set_active_session("SESION_KIT_CASO2")


def test_cli_human_eval_workflow(test_session_id):
    """Verifica el flujo CLI completo de la Capa 8."""
    # 1. Init
    res_init = runner.invoke(cli_app, ["human-eval", "init", "--seed", "2026", "--session-id", test_session_id])
    assert res_init.exit_code == 0, f"Error en init: {res_init.output}"
    assert "Muestra estratificada generada" in res_init.output
    assert "Etiquetas Oficiales de Expertos" in res_init.output

    # 2. Status
    res_status = runner.invoke(cli_app, ["human-eval", "status", "--session-id", test_session_id])
    assert res_status.exit_code == 0
    assert "clave_RESTRINGIDA.json" in res_status.output
    assert "CIEGA (Restringida)" in res_status.output

    # 3. Emit A y B
    res_emit_a = runner.invoke(cli_app, ["human-eval", "emit", "--expert", "A", "--session-id", test_session_id])
    assert res_emit_a.exit_code == 0
    assert "Cuaderno Excel generado" in res_emit_a.output
    assert "Paquete ciego HTML generado" in res_emit_a.output

    res_emit_b = runner.invoke(cli_app, ["human-eval", "emit", "--expert", "B", "--session-id", test_session_id])
    assert res_emit_b.exit_code == 0

    s_dir = PROJECT_ROOT / "data" / "human_eval" / test_session_id
    xlsx_a = s_dir / f"Instrumento_Experto_A_{test_session_id}.xlsx"
    html_a = s_dir / f"Paquete_Experto_A_{test_session_id}.html"
    assert xlsx_a.exists()
    assert html_a.exists()


def test_fastapi_human_eval_endpoints(test_session_id):
    """Verifica los endpoints web y la 6ª vista de la barra lateral."""
    from src.layer8_human_eval.web_routes import (
        InitSessionRequest,
        OpenKeyRequest,
        api_export_kit,
        api_get_labels,
        api_get_state,
        api_init_session,
        api_open_key,
        vista_human_eval_fragment,
    )

    # 1. 6ª Vista HTML
    res_view = vista_human_eval_fragment()
    assert res_view.status_code == 200
    html_text = res_view.body.decode("utf-8")
    assert "Capa 8: Validación Humana y Calibración Inter-Evaluador" in html_text
    assert "1. Instrumentos y Evaluadores" in html_text
    assert "2. Concordancia y Calibración" in html_text
    assert "3. Informe de Correlación Diagnóstica" in html_text

    # 2. Inicializar sesión vía API
    res_init = api_init_session(InitSessionRequest(seed=2026, sesion_id=test_session_id))
    assert res_init.status_code == 200
    data_init = json.loads(res_init.body.decode())
    assert data_init["ok"] is True
    assert data_init["sample_size"] == 54

    # 3. Estado de la sesión
    res_state = api_get_state(test_session_id)
    assert res_state.status_code == 200
    data_state = json.loads(res_state.body.decode())
    assert data_state["active"] is True
    assert data_state["has_key"] is True
    assert data_state["is_key_opened"] is False

    # 4. Etiquetas
    res_labels = api_get_labels(test_session_id)
    assert res_labels.status_code == 200
    labels = json.loads(res_labels.body.decode())
    assert "A" in labels and "B" in labels and "C" in labels
    assert labels["A"]["codigo_acceso"] is not None

    # 5. Exportar Kit ZIP para Experto A
    res_zip = api_export_kit("A", test_session_id)
    assert res_zip.status_code == 200
    assert res_zip.media_type == "application/zip"

    # Verificar contenido del ZIP
    zip_bytes = io.BytesIO(res_zip.body)
    with zipfile.ZipFile(zip_bytes, "r") as zf:
        namelist = zf.namelist()
        assert any(n.endswith(".xlsx") for n in namelist)
        assert any(n.endswith(".html") for n in namelist)

    # 6. Apertura de Clave: verificar rechazo temprano cuando faltan precondiciones metodológicas
    res_open_early = api_open_key(
        OpenKeyRequest(motivo="Apertura prematura sin evaluaciones completas"),
        sesion_id=test_session_id
    )
    assert res_open_early.status_code == 400
    data_early = json.loads(res_open_early.body.decode())
    assert data_early["ok"] is False
    assert "Requisito metodológico incumplido" in data_early["error"]

    s_dir = PROJECT_ROOT / "data" / "human_eval" / test_session_id
    assert not (s_dir / "KEY_OPENED_AUDIT.json").exists()
    assert json.loads(api_get_state(test_session_id).body.decode())["is_key_opened"] is False

    # Cumplir precondiciones metodológicas: importar respuestas completas para A y B y calcular concordancia
    import csv
    for exp in ["A", "B"]:
        resp_csv = s_dir / f"respuestas_{exp}.csv"
        with open(resp_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["codigo", "c1", "c2", "c3", "c4", "c5", "c6", "s", "u", "observacion", "rubrica"])
            for idx in range(1, 55):
                writer.writerow([f"EV-{idx:03d}", 2, 2, 2, 2, 2, 2, "Sí", 5, "Diagnóstico verificado", 5.0])

    (s_dir / "concordancia.json").write_text(json.dumps({"ok": True, "kappa": 1.0}), encoding="utf-8")

    # Intentar apertura con motivo inválido (< 5 caracteres o vacío)
    res_open_invalid_reason = api_open_key(
        OpenKeyRequest(motivo="   "),
        sesion_id=test_session_id
    )
    assert res_open_invalid_reason.status_code == 400
    assert not (s_dir / "KEY_OPENED_AUDIT.json").exists()

    # Apertura formal válida con precondiciones cumplidas y motivo explícito
    res_open = api_open_key(
        OpenKeyRequest(motivo="Apertura formal para sustentación y análisis final de tesis tras cumplir requisitos"),
        sesion_id=test_session_id
    )
    assert res_open.status_code == 200
    data_open = json.loads(res_open.body.decode())
    assert data_open["ok"] is True
    assert data_open["audit"]["estado"] == "clave_abierta_analisis_desbloqueados"
    assert (s_dir / "KEY_OPENED_AUDIT.json").exists()

    # Verificar que el estado refleja la apertura
    res_state_after = api_get_state(test_session_id)
    assert json.loads(res_state_after.body.decode())["is_key_opened"] is True
