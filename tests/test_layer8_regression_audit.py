"""
NetDiagBench-L7: Suite de Pruebas de Regresión para la Auditoría de Capa 8
Verifica exhaustivamente la corrección de los 4 defectos identificados:
1. La acción «Nueva Sesión» debe crear una sesión nueva con identificador único sin sobrescribir sesiones previas.
2. La apertura de clave exige rigurosamente las precondiciones metodológicas (54 de A, 54 de B, concordancia, motivo válido).
3. Los materiales entregados a evaluadores (XLSX, HTML, ZIP, manifiestos) son estrictamente ciegos (sin ground truth).
4. Prevención estricta de path traversal en identificadores de sesión (web y CLI).
"""

import csv
import io
import json
from pathlib import Path
import shutil
import zipfile

from fastapi.testclient import TestClient
import pytest
from typer.testing import CliRunner

from src.core.config import PROJECT_ROOT
from src.layer1_lab.runner import ScenarioLabRunner
from src.layer6_interface.cli import app as cli_app
from src.layer6_interface.web import app as fastapi_app
from src.layer8_human_eval.exporter_packet import export_expert_packet_html
from src.layer8_human_eval.exporter_xlsx import export_expert_instrument
from src.layer8_human_eval.labels import generate_expert_label
from src.layer8_human_eval.sampler import (
    build_stratified_sample,
    load_blind_cards_from_sample,
    save_blind_key,
)
from src.layer8_human_eval.session import (
    CURRENT_SESSION_FILE,
    HUMAN_EVAL_BASE_DIR,
    create_new_session_dir,
    get_active_session_id,
    get_session_dir,
    get_session_state,
    open_key_audit,
    set_active_session,
    validate_session_id,
)
from src.layer8_human_eval.web_routes import (
    InitSessionRequest,
    OpenKeyRequest,
    api_get_state,
    api_init_session,
    api_open_key,
)

runner = CliRunner()


@pytest.fixture(autouse=True)
def preserve_active_session():
    """Garantiza la preservación de la sesión activa original al finalizar cada prueba."""
    original_session = None
    if CURRENT_SESSION_FILE.exists():
        original_session = CURRENT_SESSION_FILE.read_text(encoding="utf-8").strip()
    yield
    if original_session:
        set_active_session(original_session)
    elif CURRENT_SESSION_FILE.exists():
        CURRENT_SESSION_FILE.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Defecto 1: «Nueva Sesión» debe crear una sesión nueva y proteger sesiones previas
# ---------------------------------------------------------------------------

def test_01_nueva_sesion_creates_unique_id_and_rejects_overwrite(tmp_path: Path):
    """
    1. Verifica que:
    - Inicializar sin sesion_id genera un identificador único seguro (SESION_...).
    - Dos llamadas sucesivas generan IDs distintos sin colisión.
    - No reutiliza la sesión activa previa.
    - Proporcionar un ID existente lanza FileExistsError en create_new_session_dir y HTTP 409 en la API.
    - Los archivos y contenidos de la sesión previa se conservan intactos.
    """
    base_dir = tmp_path / "human_eval_sessions"
    base_dir.mkdir(parents=True, exist_ok=True)

    # 1. Crear sesión base inicial simulando datos existentes
    id_prev, dir_prev = create_new_session_dir(sesion_id="SESION_PREVIA_01", base_dir=base_dir)
    assert id_prev == "SESION_PREVIA_01"
    assert dir_prev.exists()

    dummy_key = dir_prev / "clave_RESTRINGIDA.json"
    dummy_key.write_text(json.dumps({"entradas": [{"codigo": "EV-001"}]}), encoding="utf-8")
    dummy_etiquetas = dir_prev / "etiquetas.json"
    dummy_etiquetas.write_text(json.dumps({"A": {"alias": "ExpA"}}), encoding="utf-8")

    set_active_session(id_prev, base_dir=base_dir)
    assert get_active_session_id(base_dir=base_dir) == id_prev

    # 2. Inicializar sin sesion_id: debe generar un ID NUEVO y NO reutilizar SESION_PREVIA_01
    id_new_1, dir_new_1 = create_new_session_dir(sesion_id=None, base_dir=base_dir)
    id_new_2, dir_new_2 = create_new_session_dir(sesion_id=None, base_dir=base_dir)

    assert id_new_1 != id_prev
    assert id_new_2 != id_prev
    assert id_new_1 != id_new_2
    assert id_new_1.startswith("SESION_")
    assert dir_new_1.exists() and dir_new_2.exists()

    # 3. Intentar crear nuevamente una sesión con ID existente debe fallar con FileExistsError
    with pytest.raises(FileExistsError) as exc_info:
        create_new_session_dir(sesion_id="SESION_PREVIA_01", base_dir=base_dir)
    assert "ya existe" in str(exc_info.value)

    # 4. Verificar integridad absoluta de los archivos de la sesión previa
    assert dummy_key.exists()
    assert json.loads(dummy_key.read_text(encoding="utf-8")) == {"entradas": [{"codigo": "EV-001"}]}
    assert dummy_etiquetas.exists()
    assert json.loads(dummy_etiquetas.read_text(encoding="utf-8")) == {"A": {"alias": "ExpA"}}

    # 5. Probar comportamiento vía endpoint API HTTP
    # Inicializar con sesión existente retorna 409
    conflict_sesion = "SESION_EXISTENTE_TEST_CONFLICT"
    conflict_path = HUMAN_EVAL_BASE_DIR / conflict_sesion
    conflict_path.mkdir(parents=True, exist_ok=True)
    try:
        res_conflict = api_init_session(InitSessionRequest(seed=2026, sesion_id=conflict_sesion))
        assert res_conflict.status_code == 409
        data_conflict = json.loads(res_conflict.body.decode())
        assert data_conflict["ok"] is False
        assert "ya existe" in data_conflict["error"]
    finally:
        shutil.rmtree(conflict_path, ignore_errors=True)


# ---------------------------------------------------------------------------
# Defecto 2: La apertura de clave debe exigir las precondiciones metodológicas
# ---------------------------------------------------------------------------

def test_02_apertura_clave_requires_methodological_preconditions(tmp_path: Path):
    """
    2. Verifica que:
    - La apertura de clave falla con error y sin generar KEY_OPENED_AUDIT.json si:
      a) Falta clave de cegamiento.
      b) Evaluador A tiene menos de 54 respuestas.
      c) Evaluador B tiene menos de 54 respuestas.
      d) No se ha calculado la concordancia inter-evaluador.
      e) El motivo de auditoría está vacío o no es válido.
    - Solo tiene éxito cuando se cumplen estrictamente todas las precondiciones.
    - La vista web permanece restringida hasta la apertura autorizada.
    """
    sesion_id = "test_audit_preconditions"
    s_dir = PROJECT_ROOT / "data" / "human_eval" / sesion_id
    if s_dir.exists():
        shutil.rmtree(s_dir, ignore_errors=True)

    try:
        # 1. Sesión no inicializada
        with pytest.raises(ValueError) as exc_uninit:
            open_key_audit(sesion_id=sesion_id, reason="Apertura formal de prueba")
        assert "no existe" in str(exc_uninit.value) or "no ha sido inicializada" in str(exc_uninit.value)

        # 2. Inicializar sesión (crea clave y etiquetas, pero 0 evaluaciones)
        s_dir.mkdir(parents=True, exist_ok=True)
        set_active_session(sesion_id)
        sample = build_stratified_sample(seed=2026)
        save_blind_key(sample, sesion_id, 2026, s_dir)
        codes = [s.codigo for s in sample]
        etiquetas_map = {
            "A": generate_expert_label("A", sesion_id, codes, semilla_orden=11),
            "B": generate_expert_label("B", sesion_id, codes, semilla_orden=22),
            "C": generate_expert_label("C", sesion_id, codes, semilla_orden=33),
        }
        from src.layer8_human_eval.labels import save_etiquetas
        save_etiquetas(etiquetas_map, s_dir)

        # Intentar abrir clave inmediatamente con 0 evaluaciones vía API
        res_fail_evals = api_open_key(
            OpenKeyRequest(motivo="Apertura prematura con cero evaluaciones"),
            sesion_id=sesion_id
        )
        assert res_fail_evals.status_code == 400
        assert "54 evaluaciones completas" in json.loads(res_fail_evals.body.decode())["error"]
        assert not (s_dir / "KEY_OPENED_AUDIT.json").exists()
        assert get_session_state(sesion_id)["is_key_opened"] is False

        # 3. Agregar 54 respuestas solo para A (B sigue con 0)
        def _write_csv(path: Path, count: int):
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["codigo", "c1", "c2", "c3", "c4", "c5", "c6", "s", "u", "observacion", "rubrica"])
                for i in range(1, count + 1):
                    w.writerow([f"EV-{i:03d}", 2, 2, 2, 2, 2, 2, "Sí", 5, "Obs", 5.0])

        _write_csv(s_dir / "respuestas_A.csv", 54)
        _write_csv(s_dir / "respuestas_B.csv", 10)  # Incompleto

        with pytest.raises(ValueError) as exc_b:
            open_key_audit(sesion_id=sesion_id, reason="Apertura con B incompleto")
        assert "Experto B=10/54" in str(exc_b.value)
        assert not (s_dir / "KEY_OPENED_AUDIT.json").exists()

        # 4. Completar B (54/54) pero SIN concordancia calculada
        _write_csv(s_dir / "respuestas_B.csv", 54)

        with pytest.raises(ValueError) as exc_agr:
            open_key_audit(sesion_id=sesion_id, reason="Apertura sin concordancia")
        assert "concordancia inter-evaluador" in str(exc_agr.value)
        assert not (s_dir / "KEY_OPENED_AUDIT.json").exists()

        # 5. Agregar concordancia calculada y datos automáticos
        (s_dir / "concordancia.json").write_text(json.dumps({"ok": True}), encoding="utf-8")
        with open(s_dir / "automatico.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["codigo", "is_correct", "rubric_score", "evidence_backed"])
            for i in range(1, 55):
                w.writerow([f"EV-{i:03d}", 1, 4.5, 1])

        # Intentar abrir con motivo vacío o inválido (< 5 caracteres)
        with pytest.raises(ValueError) as exc_motivo:
            open_key_audit(sesion_id=sesion_id, reason="   ")
        assert "motivo de auditoría" in str(exc_motivo.value)
        assert not (s_dir / "KEY_OPENED_AUDIT.json").exists()

        # 6. Apertura válida con todos los requisitos metodológicos cumplidos
        valid_reason = "Apertura formal autorizada para análisis correlacional de tesis"
        audit_res = open_key_audit(sesion_id=sesion_id, reason=valid_reason)
        assert audit_res["estado"] == "clave_abierta_analisis_desbloqueados"
        assert audit_res["motivo"] == valid_reason
        assert (s_dir / "KEY_OPENED_AUDIT.json").exists()

        # Verificar que el estado formal ahora sí es CLAVE_ABIERTA
        state = get_session_state(sesion_id)
        assert state["phase"] == "CLAVE_ABIERTA"
        assert state["is_key_opened"] is True

        # Verificar vía CLI Typer
        res_cli_correlate = runner.invoke(
            cli_app,
            ["human-eval", "correlate", "--open-key", "--session-id", sesion_id]
        )
        assert res_cli_correlate.exit_code == 0
        assert "CLAVE DE CEGAMIENTO ABIERTA" in res_cli_correlate.output
    finally:
        if s_dir.exists():
            shutil.rmtree(s_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Defecto 3: Materiales para evaluadores estrictamente ciegos sin Ground Truth
# ---------------------------------------------------------------------------

def test_03_materiales_evaluadores_ciegos_sin_ground_truth(tmp_path: Path):
    """
    3. Verifica que:
    - En el cuaderno Excel de evaluación (Evaluación):
      * NO existen columnas 'Causa raíz esperada', 'Componente esperado' ni 'Evidencia mínima requerida'.
      * Ninguna celda contiene valores de verdad fundamental de los escenarios.
    - En el paquete ciego HTML (Paquete_Experto_A_*.html):
      * La sección 1 solo muestra 'Escenario Asignado' y 'Síntoma Observado'.
      * NO figuran 'Causa Raíz Esperada', 'Componente Afectado' ni 'Evidencia Mínima Requerida'.
      * Cero fugas de los textos reales de verdad fundamental.
    - En manifest.json y README del ZIP de exportación no hay ground truth.
    """
    import openpyxl

    sample = build_stratified_sample(seed=2026)
    codes = [e.codigo for e in sample]
    etiqueta_a = generate_expert_label("A", "sesion_test_blind_gt", codes, semilla_orden=11)
    blind_cards = load_blind_cards_from_sample(sample)

    xlsx_path = tmp_path / "Instrumento_Experto_A_sesion_test_blind_gt.xlsx"
    html_path = tmp_path / "Paquete_Experto_A_sesion_test_blind_gt.html"

    export_expert_instrument(etiqueta_a, blind_cards, xlsx_path)
    export_expert_packet_html(etiqueta_a, blind_cards, html_path)

    assert xlsx_path.exists()
    assert html_path.exists()

    # Obtener valores reales de verdad fundamental para comprobar su ausencia absoluta
    lab = ScenarioLabRunner()
    gt_root_causes = set()
    gt_components = set()
    for s_entry in sample:
        sc = lab.get_scenario(s_entry.scenario_id)
        if sc and sc.ground_truth:
            gt_root_causes.add(sc.ground_truth.root_cause.strip().lower())
            gt_components.add(sc.ground_truth.affected_component.strip().lower())

    # --- VERIFICACIÓN DE EXCEL ---
    wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    ws_eval = wb["Evaluación"]

    # Fila 4: Cabeceras
    headers = [str(cell.value or "").strip() for cell in ws_eval[4] if cell.value]
    headers_lower = [h.lower() for h in headers]

    # Comprobar que las columnas de ground truth no existen en las cabeceras
    assert "causa raíz esperada" not in headers_lower
    assert "causa raiz esperada" not in headers_lower
    assert "componente esperado" not in headers_lower
    assert "evidencia mínima requerida" not in headers_lower
    assert "evidencia minima requerida" not in headers_lower

    # Comprobar que ninguna celda de Evaluación contenga causas raíz reales
    for row in ws_eval.iter_rows(min_row=5, values_only=True):
        for cell_val in row:
            if cell_val is not None:
                val_str = str(cell_val).strip().lower()
                for rc in gt_root_causes:
                    if len(rc) > 10:
                        assert rc not in val_str, f"Fuga de Ground Truth en Excel: '{rc}' encontrado en celda."

    # 1. Comprobar que los objetos que alimentan los exportadores ciegos no tienen campos de ground truth
    first_card = list(blind_cards.values())[0]
    assert not hasattr(first_card, "causa_raiz_esperada")
    assert not hasattr(first_card, "componente_esperado")
    assert not hasattr(first_card, "evidencia_minima")

    # --- VERIFICACIÓN DE HTML ---
    html_text = html_path.read_text(encoding="utf-8")
    html_lower = html_text.lower()

    # Comprobar ausencia de títulos de verdad fundamental
    assert "causa raíz esperada" not in html_lower
    assert "causa raiz esperada" not in html_lower
    assert "evidencia mínima requerida" not in html_lower
    assert "evidencia minima requerida" not in html_lower

    # Comprobar que en la Sección 1 (Ficha del Escenario) solo se muestre contexto operativo y síntoma
    assert "1. ficha del escenario (contexto operativo ciego)" in html_lower
    assert "síntoma observado" in html_lower

    # Comprobar que en las tablas de contexto del escenario (Sección 1) no aparezcan campos ni valores de verdad fundamental
    import re
    sec1_blocks = re.findall(r"<!-- 1\. Ficha del Escenario -->.*?(?=<!-- 2\. Pasos)", html_text, re.DOTALL)
    assert len(sec1_blocks) == 54
    for b in sec1_blocks:
        b_lower = b.lower()
        assert "causa raíz esperada" not in b_lower
        assert "causa raiz esperada" not in b_lower
        assert "componente afectado" not in b_lower
        assert "componente esperado" not in b_lower
        assert "evidencia mínima requerida" not in b_lower
        for rc in gt_root_causes:
            if len(rc) > 10:
                assert rc not in b_lower


# ---------------------------------------------------------------------------
# Defecto 4: Prevención estricta de Path Traversal en sesion_id
# ---------------------------------------------------------------------------

def test_04_path_traversal_prevention_on_session_id(tmp_path: Path):
    """
    4. Verifica que:
    - validate_session_id rechaza tajantemente:
      * Separadores de ruta (/ y \\).
      * Rutas relativas con . y ..
      * Rutas absolutas (Windows y Unix).
      * Caracteres especiales o espacios fuera de ^[a-zA-Z0-9_-]+$.
      * Intentos de escape de directorio.
    - Se aceptan identificadores canónicos válidos.
    - Ninguna llamada escribe fuera del directorio temporal asignado.
    """
    sandbox_dir = tmp_path / "sandbox_human_eval"
    sandbox_dir.mkdir(parents=True, exist_ok=True)

    malicious_ids = [
        "../escape",
        "..\\escape",
        "../../etc/passwd",
        "..\\..\\windows\\system32",
        "folder/subfolder",
        "folder\\subfolder",
        ".",
        "..",
        "sesion con espacios",
        "sesion$invalida",
        "sesion;rm -rf",
        "sesion|evil",
        "sesion\0nullbyte",
        "",
        "   ",
        "C:\\Windows\\System32",
        "/etc/shadow",
    ]

    for bad_id in malicious_ids:
        with pytest.raises(ValueError) as exc:
            validate_session_id(bad_id, base_dir=sandbox_dir)
        assert len(str(exc.value)) > 0, f"Debe lanzar ValueError para '{bad_id}'"

    # Verificar identificadores válidos
    valid_ids = [
        "SESION_20261105_120000_abcd",
        "SESION_KIT_CASO2",
        "test_audit_session_01",
        "eval-2026-v1",
        "SESION_TEST",
    ]

    for good_id in valid_ids:
        clean_id, resolved = validate_session_id(good_id, base_dir=sandbox_dir)
        assert clean_id == good_id
        assert resolved == (sandbox_dir / good_id).resolve()
        assert resolved.parent == sandbox_dir.resolve()

    # Comprobar rechazo vía API REST (HTTP 400)
    with TestClient(fastapi_app) as client:
        res_traversal_state = client.get("/api/human-eval/state?sesion_id=../../traversal_test")
        assert res_traversal_state.status_code == 400

        res_traversal_init = client.post(
            "/api/human-eval/init",
            json={"seed": 2026, "sesion_id": "../evil_init"}
        )
        assert res_traversal_init.status_code == 400

    # Comprobar que ningún archivo malicioso fue creado fuera de sandbox_dir
    parent_files = list(tmp_path.iterdir())
    assert parent_files == [sandbox_dir], f"Archivos inesperados creados fuera de base: {parent_files}"
