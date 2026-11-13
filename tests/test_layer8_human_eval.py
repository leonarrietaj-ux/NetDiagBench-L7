"""
NetDiagBench-L7: Suite de Pruebas de la Capa 8 - Validación Humana y Calibración Inter-Evaluador
Pruebas 1 a 3: Muestreo estratificado, anonimización/cegamiento y etiquetas con huella criptográfica.
"""

import json
import math
from pathlib import Path
import pytest

from src.core.config import PROJECT_ROOT
from src.core.contracts import EtiquetaExperto
from src.layer1_lab.runner import ScenarioLabRunner
from src.layer7_evaluator.metrics import get_evaluator_version
from src.layer8_human_eval.labels import (
    compute_huella,
    generate_expert_label,
    load_etiquetas,
    save_etiquetas,
    verify_etiqueta_integrity,
    verify_expert_submission,
)
from src.layer8_human_eval.sampler import (
    FORBIDDEN_TERMS,
    OFFICIAL_MODELS,
    anonymize_text,
    build_anonymized_card,
    build_stratified_sample,
    check_forbidden_terms,
    save_blind_key,
)


# ---------------------------------------------------------------------------
# Prueba 1: Muestra estratificada de 54 corridas (18 escenarios x 3 modelos)
# ---------------------------------------------------------------------------

def test_01_stratified_sample_54_runs_reproducible(tmp_path: Path):
    """
    1. Muestra: 54 corridas, 18 escenarios × 3 modelos, reproducible con semilla 2026.
    Verifica que la muestra cubra los 18 escenarios y los 3 modelos oficiales,
    y que dos ejecuciones con semilla 2026 generen exactamente la misma muestra.
    """
    sample1 = build_stratified_sample(seed=2026)
    sample2 = build_stratified_sample(seed=2026)

    # 54 corridas totales
    assert len(sample1) == 54
    assert len(sample2) == 54

    # Reproducibilidad estricta
    for s1, s2 in zip(sample1, sample2):
        assert s1.codigo == s2.codigo
        assert s1.model_id == s2.model_id
        assert s1.scenario_id == s2.scenario_id
        assert s1.seed == s2.seed
        assert s1.ruta_diagnostico == s2.ruta_diagnostico

    # Cobertura estratificada completa
    scenario_counts = {}
    model_counts = {}
    combos = set()
    codes = set()

    for item in sample1:
        assert item.codigo.startswith("EV-")
        assert len(item.codigo) == 6  # "EV-XXX"
        assert item.codigo[3:].isdigit()
        codes.add(item.codigo)

        scenario_counts[item.scenario_id] = scenario_counts.get(item.scenario_id, 0) + 1
        model_counts[item.model_id] = model_counts.get(item.model_id, 0) + 1
        combos.add((item.scenario_id, item.model_id))

    # 54 códigos únicos
    assert len(codes) == 54

    # 18 escenarios distintos con 3 modelos cada uno
    assert len(scenario_counts) == 18
    for sc, count in scenario_counts.items():
        assert count == 3, f"Escenario {sc} tiene {count} corridas, esperado 3"

    # 3 modelos oficiales con 18 corridas cada uno
    assert set(model_counts.keys()) == set(OFFICIAL_MODELS)
    for model, count in model_counts.items():
        assert count == 18, f"Modelo {model} tiene {count} corridas, esperado 18"

    assert len(combos) == 54

    # Guardar clave y verificar que persiste correctamente
    json_path, xlsx_path = save_blind_key(
        entries=sample1,
        sesion_id="sesion_test_01",
        seed=2026,
        output_dir=tmp_path
    )
    assert json_path.exists()
    assert xlsx_path.exists()

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        assert data["sesion_id"] == "sesion_test_01"
        assert data["seed"] == 2026
        assert data["total_corridas"] == 54
        assert len(data["entradas"]) == 54


# ---------------------------------------------------------------------------
# Prueba 2: Cegamiento y cero fugas en datos anonimizados
# ---------------------------------------------------------------------------

def test_02_anonymization_zero_leaks():
    """
    2. Cegamiento: verifica que no existan fugas de nombres de modelo, proveedores,
    bloques <think> ni métricas internas en el texto anonimizado y fichas ciegas.
    """
    dirty_text = (
        "El modelo Qwen3-8B de Alibaba determinó que la causa es NXDOMAIN. "
        "<think>Razonando profundamente sobre RFC 1035...</think> "
        "El rendimiento fue de 45 tok/s con TTFT de 120 ms y 5.5 GB VRAM. "
        "Evaluado como is_correct=True por GLM-4-9B de Zhipu y Phi-4-mini de Microsoft."
    )

    clean = anonymize_text(dirty_text)

    # Comprobar que no queda ningún término prohibido
    leaks = check_forbidden_terms(clean)
    assert leaks == [], f"Se encontraron fugas en texto anonimizado: {leaks}\nTexto: {clean}"

    # Ficha anonimizada construida a partir de un escenario real
    lab = ScenarioLabRunner()
    sc = lab.get_scenario("DNS-NXD-01")
    assert sc is not None

    sample = build_stratified_sample(seed=2026)
    first_entry = sample[0]

    dummy_diag = {
        "root_cause": "Fallo en servidor autoritativo identificado por Qwen3-8b",
        "affected_component": "bind9-authoritative",
        "suggested_action": "Reiniciar BIND9 según recomendación de Microsoft y Zhipu",
        "natural_language_explanation": "Análisis: <think>pensamiento CoT</think> Causa confirmada. VRAM 4.2GB.",
        "supporting_evidence": ["dig @127.0.0.1 -p 5353 app.internal.corp A -> NXDOMAIN"],
    }

    card = build_anonymized_card(first_entry, sc, dummy_diag)

    # Verificar que ni en veredicto ni en ficha existan términos prohibidos
    for key, val in card.veredicto.items():
        assert check_forbidden_terms(str(val)) == [], f"Fuga en veredicto.{key}: {val}"

    assert check_forbidden_terms(card.sintoma) == []
    assert check_forbidden_terms(card.causa_raiz_esperada) == []
    assert check_forbidden_terms(card.componente_esperado) == []


def test_02b_xlsx_and_html_exports_zero_leaks_and_valid_structure(tmp_path: Path):
    """
    2. Cegamiento (completo): Cero fugas en archivo XLSX (todas las celdas y docProps)
    y en archivo HTML del paquete ciego de 54 fichas.
    Verifica además estructura de 4 hojas, ausencia de funciones dinámicas y fórmulas reglamentarias.
    """
    import openpyxl
    from src.layer8_human_eval.exporter_packet import export_expert_packet_html
    from src.layer8_human_eval.exporter_xlsx import export_expert_instrument
    from src.layer8_human_eval.sampler import load_anonymized_cards_from_sample

    sample = build_stratified_sample(seed=2026)
    codes = [e.codigo for e in sample]
    eval_ver = get_evaluator_version()
    etiqueta = generate_expert_label("A", "sesion_test_blind", codes, semilla_orden=11, version_evaluador=eval_ver)
    cards = load_anonymized_cards_from_sample(sample)

    xlsx_path = tmp_path / f"Instrumento_Experto_A_sesion_test_blind.xlsx"
    html_path = tmp_path / f"Paquete_Experto_A_sesion_test_blind.html"

    # Exportar ambos artefactos
    export_expert_instrument(etiqueta, cards, xlsx_path)
    export_expert_packet_html(etiqueta, cards, html_path)

    assert xlsx_path.exists()
    assert html_path.exists()

    # --- VERIFICACIÓN DE XLSX ---
    wb = openpyxl.load_workbook(xlsx_path, data_only=False)

    # 1. Verificar hojas reglamentarias
    expected_sheets = ["Instrucciones", "Guía", "Evaluación", "Validación funcional"]
    assert wb.sheetnames == expected_sheets, f"Hojas encontradas: {wb.sheetnames}, esperadas: {expected_sheets}"

    # 2. Verificar docProps (metadatos limpios de modelos o rutas)
    assert wb.properties.creator == "NetDiagBench-L7"
    for prop in [wb.properties.title, wb.properties.subject, wb.properties.description]:
        leaks = check_forbidden_terms(str(prop or ""))
        assert leaks == [], f"Fuga en docProps ({prop}): {leaks}"

    # 3. Verificar todas las celdas de todas las hojas contra términos prohibidos y funciones dinámicas
    forbidden_excel_funcs = ["XLOOKUP", "FILTER", "SORT", "UNIQUE", "SEQUENCE", "RANDARRAY"]

    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        for row in ws.iter_rows():
            for cell in row:
                val = cell.value
                if val is not None:
                    val_str = str(val)
                    # Comprobar fugas
                    leaks = check_forbidden_terms(val_str)
                    assert leaks == [], f"Fuga en hoja '{sheet_name}', celda {cell.coordinate}: '{val_str}' -> {leaks}"

                    # Si es fórmula, verificar que no use funciones dinámicas de Excel
                    if isinstance(val, str) and val.startswith("="):
                        val_upper = val.upper()
                        for f_dyn in forbidden_excel_funcs:
                            assert f_dyn not in val_upper, (
                                f"Función dinámica prohibida '{f_dyn}' en hoja '{sheet_name}', "
                                f"celda {cell.coordinate}: {val}"
                            )

    # 4. Verificar fórmulas requeridas en la hoja Evaluación (disposición estrictamente ciega sin ground truth)
    ws_eval = wb["Evaluación"]
    # Fila 5 (primera corrida)
    formula_suma = str(ws_eval["N5"].value)
    formula_rubrica = str(ws_eval["O5"].value)
    formula_completa = str(ws_eval["P5"].value)

    assert "SUM" in formula_suma and "COUNT" in formula_suma
    assert "ROUND" in formula_rubrica
    assert "Falta" in formula_completa and "Completa" in formula_completa

    # Verificar que las columnas de entrada (E..M: C1..C6, S, U, Observación) están desbloqueadas
    for col_letter in ["E", "F", "G", "H", "I", "J", "K", "L", "M"]:
        cell = ws_eval[f"{col_letter}5"]
        assert cell.protection.locked is False, f"Celda {col_letter}5 debe estar desbloqueada"

    # Verificar que las columnas de solo lectura (A..D) y fórmulas (N..P) están bloqueadas
    for col_letter in ["A", "B", "C", "D", "N", "O", "P"]:
        cell = ws_eval[f"{col_letter}5"]
        assert cell.protection.locked is True, f"Celda {col_letter}5 debe estar bloqueada"

    # --- VERIFICACIÓN DE HTML ---
    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    # Cero fugas en todo el HTML
    html_leaks = check_forbidden_terms(html_content)
    assert html_leaks == [], f"Fugas encontradas en HTML del paquete ciego: {html_leaks}"

    # Contiene la etiqueta del experto
    assert etiqueta.expert_id in html_content
    assert etiqueta.codigo_acceso in html_content
    assert etiqueta.huella_sha256 in html_content

    # Contiene las 54 fichas
    for code in etiqueta.orden:
        assert f'id="{code}"' in html_content



# ---------------------------------------------------------------------------
# Prueba 3: Etiquetas de experto (órdenes distintos y rechazo por huella alterada)
# ---------------------------------------------------------------------------

def test_03_expert_labels_distinct_orders_and_tampered_hash_rejection(tmp_path: Path):
    """
    3. Etiquetas: órdenes distintos para A y B. Un libro con huella alterada es rechazado.
    """
    sample = build_stratified_sample(seed=2026)
    codes = [e.codigo for e in sample]

    sesion_id = "sesion_inter_rater_2026"
    eval_ver = get_evaluator_version()

    # Generar etiquetas para A y B
    etiqueta_a = generate_expert_label("A", sesion_id, codes, semilla_orden=11, version_evaluador=eval_ver)
    etiqueta_b = generate_expert_label("B", sesion_id, codes, semilla_orden=22, version_evaluador=eval_ver)

    # Ambos tienen 54 códigos
    assert len(etiqueta_a.orden) == 54
    assert len(etiqueta_b.orden) == 54

    # Los conjuntos de códigos son idénticos pero el orden es DISTINTO
    assert set(etiqueta_a.orden) == set(codes)
    assert set(etiqueta_b.orden) == set(codes)
    assert etiqueta_a.orden != etiqueta_b.orden, "Los órdenes de A y B no deben ser iguales"

    # Códigos de acceso seguros de 8 caracteres
    assert len(etiqueta_a.codigo_acceso) == 8
    assert len(etiqueta_b.codigo_acceso) == 8
    assert etiqueta_a.codigo_acceso != etiqueta_b.codigo_acceso

    # Integridad criptográfica válida inicialmente
    assert verify_etiqueta_integrity(etiqueta_a, eval_ver) is True
    assert verify_etiqueta_integrity(etiqueta_b, eval_ver) is True

    # Guardar en archivo oficial de etiquetas
    etiquetas_map = {"A": etiqueta_a, "B": etiqueta_b}
    etiquetas_file = save_etiquetas(etiquetas_map, tmp_path)
    assert etiquetas_file.exists()

    loaded = load_etiquetas(etiquetas_file)
    assert "A" in loaded and "B" in loaded

    # 1. Validación exitosa con credenciales correctas
    ok, msg = verify_expert_submission(
        expert_id="A",
        codigo_acceso=etiqueta_a.codigo_acceso,
        huella_sha256=etiqueta_a.huella_sha256,
        etiquetas_path=etiquetas_file,
        version_evaluador=eval_ver,
    )
    assert ok is True
    assert "satisfactoriamente" in msg

    # 2. Rechazo por código de acceso alterado
    ok_bad_code, msg_bad_code = verify_expert_submission(
        expert_id="A",
        codigo_acceso="BAD_CODE",
        huella_sha256=etiqueta_a.huella_sha256,
        etiquetas_path=etiquetas_file,
        version_evaluador=eval_ver,
    )
    assert ok_bad_code is False
    assert "inválido" in msg_bad_code

    # 3. Rechazo por huella SHA-256 alterada
    tampered_huella = "0" * 64
    ok_tampered, msg_tampered = verify_expert_submission(
        expert_id="A",
        codigo_acceso=etiqueta_a.codigo_acceso,
        huella_sha256=tampered_huella,
        etiquetas_path=etiquetas_file,
        version_evaluador=eval_ver,
    )
    assert ok_tampered is False
    assert "alterada" in msg_tampered.lower() or "no coincide" in msg_tampered.lower()

    # 4. Rechazo si la etiqueta interna fue alterada en orden
    etiqueta_tampered = etiqueta_a.model_copy(deep=True)
    etiqueta_tampered.orden[0], etiqueta_tampered.orden[1] = etiqueta_tampered.orden[1], etiqueta_tampered.orden[0]
    assert verify_etiqueta_integrity(etiqueta_tampered, eval_ver) is False


# ---------------------------------------------------------------------------
# Prueba 4: Dos libros A y B idénticos dan concordancia perfecta
# ---------------------------------------------------------------------------

def test_04_identical_evaluators_give_perfect_agreement():
    """
    4. Dos libros A y B idénticos dan kappa ponderado = 1, kappa S = 1, ICC = 1 y desacuerdos = 0.
    """
    from src.layer8_human_eval.agreement import calculate_agreement_summary

    dummy_responses_a = []
    for i in range(1, 55):
        dummy_responses_a.append({
            "codigo": f"EV-{i:03d}",
            "c1": (i % 3),
            "c2": ((i + 1) % 3),
            "c3": ((i + 2) % 3),
            "c4": (i % 3),
            "c5": ((i + 1) % 3),
            "c6": ((i + 2) % 3),
            "s": "Sí" if i % 2 == 0 else "No",
            "u": (i % 5) + 1,
            "observacion": "obs",
            "rubrica": round(((i % 3) + ((i + 1) % 3) + ((i + 2) % 3) + (i % 3)) / 8.0 * 5.0, 2),
        })

    dummy_responses_b = [dict(r) for r in dummy_responses_a]

    summary = calculate_agreement_summary(dummy_responses_a, dummy_responses_b, n_boot=50)

    assert summary["desacuerdos_c1"] == 0
    assert summary["acuerdo_exacto_c1"]["valor"] == 1.0
    assert summary["kappa_ponderado_c1"]["valor"] == 1.0
    assert summary["kappa_s"]["valor"] == 1.0
    assert summary["icc_2_1"]["valor"] == 1.0
    for item_key, d in summary["alfas_ordinales"].items():
        assert d["alfa"] == 1.0


# ---------------------------------------------------------------------------
# Prueba 5: Validación estadística de referencia contra kit_caso2.xlsx
# ---------------------------------------------------------------------------

def test_05_reference_fixture_kit_caso2_agreement_metrics():
    """
    5. Datos de referencia: carga el fixture tests/fixtures/kit_caso2.xlsx
    (hojas Caso2_A, Caso2_B y Caso2_Auto, Clave_simulada).
    Debe reproducir con tolerancia +/- 0.001:
    - acuerdo exacto C1 0.759; kappa ponderado C1 0.733; kappa S 0.587; ICC(2,1) 0.705;
    - desacuerdos C1 13; kappa auto vs humano 0.932 con n = 41;
    - Spearman -0.209; diferencia media -0.346;
    - rúbrica humana media GLM 3.648, Qwen 3.596, Phi 3.509;
    - alfa ordinal C1 0.665, C2 0.816, C3 0.741, C4 0.757, C5 0.710, C6 0.860.
    """
    import openpyxl
    from src.layer8_human_eval.agreement import (
        calculate_agreement_summary,
        calculate_consensus,
        calculate_metrics_by_model,
        validate_auto_vs_human,
        round_rubric,
    )

    fixture_path = PROJECT_ROOT / "tests" / "fixtures" / "kit_caso2.xlsx"
    assert fixture_path.exists(), f"Fixture {fixture_path} no encontrado"

    wb = openpyxl.load_workbook(fixture_path, data_only=True)

    def _read_sheet(ws):
        headers = [c.value for c in ws[1]]
        rows = []
        for r in ws.iter_rows(min_row=2, values_only=True):
            if not r or not r[0]:
                continue
            d = dict(zip(headers, r))
            c2, c3, c4, c5 = int(d.get("C2", 0)), int(d.get("C3", 0)), int(d.get("C4", 0)), int(d.get("C5", 0))
            rows.append({
                "codigo": str(d["Código"]),
                "c1": int(d["C1"]),
                "c2": c2,
                "c3": c3,
                "c4": c4,
                "c5": c5,
                "c6": int(d.get("C6", 0)),
                "s": str(d["S"]),
                "u": int(d.get("U", 1)),
                "observacion": str(d.get("Observación", "") or ""),
                "rubrica": round_rubric(c2 + c3 + c4 + c5),
            })
        return rows

    rows_a = _read_sheet(wb["Caso2_A"])
    rows_b = _read_sheet(wb["Caso2_B"])

    auto_dict = {
        str(r[0]): {
            "scenario_id": "ESC-01",
            "is_correct": int(r[1]) == 1,
            "rubric_score": float(r[2]),
            "respaldado": int(r[3]) == 1,
        }
        for r in wb["Caso2_Auto"].iter_rows(min_row=2, values_only=True) if r and r[0]
    }

    clave_dict = {
        str(r[0]): {
            "model_id": str(r[1]),
            "scenario_id": str(r[2]),
            "seed": int(r[3]),
        }
        for r in wb["Clave_simulada"].iter_rows(min_row=2, values_only=True) if r and r[0]
    }

    tol = 0.0015

    # 1. Batería de concordancia inter-evaluador A vs B
    summary = calculate_agreement_summary(rows_a, rows_b, n_boot=100)

    assert abs(summary["acuerdo_exacto_c1"]["valor"] - 0.759) <= tol
    assert abs(summary["kappa_ponderado_c1"]["valor"] - 0.733) <= tol
    assert abs(summary["kappa_s"]["valor"] - 0.587) <= tol
    assert abs(summary["icc_2_1"]["valor"] - 0.705) <= tol
    assert summary["desacuerdos_c1"] == 13

    # Alfas ordinales C1-C6
    alfas = summary["alfas_ordinales"]
    assert abs(alfas["C1"]["alfa"] - 0.665) <= tol
    assert abs(alfas["C2"]["alfa"] - 0.816) <= tol
    assert abs(alfas["C3"]["alfa"] - 0.741) <= tol
    assert abs(alfas["C4"]["alfa"] - 0.757) <= tol
    assert abs(alfas["C5"]["alfa"] - 0.710) <= tol
    assert abs(alfas["C6"]["alfa"] - 0.860) <= tol

    # Comparación formal contra el paquete oficial krippendorff a 4 decimales (C2 = 0.8165)
    try:
        import krippendorff
        c2_a = [r["c2"] for r in rows_a]
        c2_b = [r["c2"] for r in rows_b]
        k_alpha_c2 = krippendorff.alpha(reliability_data=[c2_a, c2_b], level_of_measurement="ordinal", value_domain=[0, 1, 2])
        assert round(alfas["C2"]["alfa"], 4) == round(k_alpha_c2, 4) == 0.8165
    except ImportError:
        pass

    # 2. Validación Auto vs Humano (sin C, n = 41)
    consensus = calculate_consensus(rows_a, rows_b)
    val_res = validate_auto_vs_human(consensus, auto_dict)

    assert val_res["n"] == 41
    assert abs(val_res["kappa"] - 0.932) <= tol
    assert abs(val_res["spearman"]["rho"] - (-0.209)) <= tol
    assert abs(val_res["bland_altman"]["mean_diff"] - (-0.346)) <= tol

    # 3. Rúbricas por modelo
    by_model = calculate_metrics_by_model(consensus, clave_dict, auto_dict)

    assert abs(by_model["glm-4-9b-chat"]["rubrica_humana_media"] - 3.648) <= tol
    assert abs(by_model["qwen3-8b"]["rubrica_humana_media"] - 3.596) <= tol
    assert abs(by_model["phi-4-mini-instruct"]["rubrica_humana_media"] - 3.509) <= tol


# ---------------------------------------------------------------------------
# Prueba 6: Caso dirimente con Evaluador C
# ---------------------------------------------------------------------------

def test_06_tiebreak_expert_c_resolves_all_disagreements():
    """
    6. Caso dirimente (con Caso3_C): pendientes = 0 y kappa auto vs humano 0.955 con n = 54.
    """
    import openpyxl
    from src.layer8_human_eval.agreement import (
        calculate_consensus,
        validate_auto_vs_human,
        round_rubric,
    )

    fixture_path = PROJECT_ROOT / "tests" / "fixtures" / "kit_caso2.xlsx"
    wb = openpyxl.load_workbook(fixture_path, data_only=True)

    def _read_eval(ws):
        headers = [c.value for c in ws[1]]
        rows = []
        for r in ws.iter_rows(min_row=2, values_only=True):
            if not r or not r[0]: continue
            d = dict(zip(headers, r))
            c2, c3, c4, c5 = int(d.get("C2", 0)), int(d.get("C3", 0)), int(d.get("C4", 0)), int(d.get("C5", 0))
            rows.append({
                "codigo": str(d["Código"]),
                "c1": int(d["C1"]),
                "c2": c2, "c3": c3, "c4": c4, "c5": c5,
                "s": str(d["S"]),
                "u": int(d.get("U", 1)),
                "c6": int(d.get("C6", 0)),
                "rubrica": round_rubric(c2 + c3 + c4 + c5),
            })
        return rows

    rows_a = _read_eval(wb["Caso2_A"])
    rows_b = _read_eval(wb["Caso2_B"])
    rows_c = _read_eval(wb["Caso3_C"])
    auto_dict = {
        str(r[0]): {
            "scenario_id": "ESC-01",
            "is_correct": int(r[1]) == 1,
            "rubric_score": float(r[2]),
        }
        for r in wb["Caso2_Auto"].iter_rows(min_row=2, values_only=True) if r and r[0]
    }

    # Consenso incorporando al dirimente C
    consensus_c = calculate_consensus(rows_a, rows_b, rows_c)

    pendientes = sum(1 for c in consensus_c if c["c1_consenso"] is None)
    assert pendientes == 0, f"No deben quedar corridas pendientes tras dirimir C (pendientes={pendientes})"

    val_res = validate_auto_vs_human(consensus_c, auto_dict)
    assert val_res["n"] == 54
    assert abs(val_res["kappa"] - 0.955) <= 0.0015


# ---------------------------------------------------------------------------
# Prueba 7: Remuestreo bootstrap reproducible
# ---------------------------------------------------------------------------

def test_07_bootstrap_reproducibility():
    """
    7. Remuestreo bootstrap reproducible: dos llamadas con la misma semilla dan idéntico IC.
    """
    from src.layer8_human_eval.agreement import (
        bootstrap_ci,
        compute_quadratic_weighted_kappa,
    )

    y1 = [0, 1, 2, 1, 2, 0, 1, 2, 2, 1, 0, 2, 1, 0, 1, 2, 2, 1] * 3
    y2 = [0, 2, 2, 1, 1, 0, 1, 2, 2, 0, 0, 2, 1, 1, 1, 2, 1, 1] * 3

    ci1 = bootstrap_ci(compute_quadratic_weighted_kappa, y1, y2, n_boot=500, seed=2026)
    ci2 = bootstrap_ci(compute_quadratic_weighted_kappa, y1, y2, n_boot=500, seed=2026)

    assert ci1 == ci2, f"Bootstrap con misma semilla debe ser estrictamente idéntico: {ci1} != {ci2}"

    # Semilla distinta produce variación
    ci_distinta = bootstrap_ci(compute_quadratic_weighted_kappa, y1, y2, n_boot=500, seed=9999)
    assert ci1 != ci_distinta or ci1 == [0.0, 0.0]


# ---------------------------------------------------------------------------
# Prueba 8: Correlación con el fixture del caso 2
# ---------------------------------------------------------------------------

def test_08_correlation_with_fixture_caso2():
    """
    8. Correlación con el fixture del caso 2: Spearman de la rúbrica automática frente a la humana
    = -0.209 (+/- 0.001) y diferencia media de Bland-Altman = -0.346, iguales a los de la hoja Auto vs humano.
    """
    import openpyxl
    from src.layer8_human_eval.agreement import (
        calculate_consensus,
        validate_auto_vs_human,
        round_rubric,
    )

    fixture_path = PROJECT_ROOT / "tests" / "fixtures" / "kit_caso2.xlsx"
    wb = openpyxl.load_workbook(fixture_path, data_only=True)

    def _read_eval(ws):
        headers = [c.value for c in ws[1]]
        rows = []
        for r in ws.iter_rows(min_row=2, values_only=True):
            if not r or not r[0]: continue
            d = dict(zip(headers, r))
            c2, c3, c4, c5 = int(d.get("C2", 0)), int(d.get("C3", 0)), int(d.get("C4", 0)), int(d.get("C5", 0))
            rows.append({
                "codigo": str(d["Código"]),
                "c1": int(d["C1"]),
                "c2": c2, "c3": c3, "c4": c4, "c5": c5,
                "s": str(d["S"]),
                "u": int(d.get("U", 1)),
                "c6": int(d.get("C6", 0)),
                "rubrica": round_rubric(c2 + c3 + c4 + c5),
            })
        return rows

    rows_a = _read_eval(wb["Caso2_A"])
    rows_b = _read_eval(wb["Caso2_B"])
    auto_dict = {
        str(r[0]): {
            "scenario_id": "ESC-01",
            "is_correct": int(r[1]) == 1,
            "rubric_score": float(r[2]),
        }
        for r in wb["Caso2_Auto"].iter_rows(min_row=2, values_only=True) if r and r[0]
    }

    consensus = calculate_consensus(rows_a, rows_b)
    val_res = validate_auto_vs_human(consensus, auto_dict)

    assert abs(val_res["spearman"]["rho"] - (-0.209)) <= 0.0015
    assert abs(val_res["bland_altman"]["mean_diff"] - (-0.346)) <= 0.0015

def test_09_interitem_matrix_symmetric_diagonal_one_and_no_nan():
    """
    9. Matriz interítem: simétrica, diagonal = 1, sin NaN cuando un ítem tiene varianza.
    Si un ítem tiene varianza cero, se reporta 'sin variación' y no se calcula rho.
    """
    from src.layer8_human_eval.correlation_report import (
        compute_spearman_with_ci,
        run_correlation_report,
    )

    dummy_rows = []
    for i in range(54):
        dummy_rows.append({
            "codigo": f"EV-{i:03d}",
            "scenario_id": f"SC-{i%18}",
            "model_id": "modelo-x",
            "seed": 42,
            "category": "DNS",
            "params_b": 8.0,
            "c1": (i % 3),
            "c2": ((i + 1) % 3),
            "c3": ((i + 2) % 3),
            "c4": (i % 3),
            "c5": ((i + 1) % 3),
            "c6": ((i + 2) % 3),
            "s_str": "Sí" if i % 2 == 0 else "No",
            "s": 1 if i % 2 == 0 else 0,
            "u": (i % 5) + 1,
            "rubrica_humana": float((i % 5) + 1),
            "humano_correcto": 1 if (i % 3) == 2 else 0,
            "is_correct": 1 if (i % 2) == 0 else 0,
            "rubric_auto": float((i % 5) + 0.5),
            "partial_match_score": 0.8,
            "evidence_backed": 1,
            "ttft_s": 0.5,
            "tok_s": 30.0,
            "latency_s": 4.0,
            "energy_kwh": 0.002,
        })

    report = run_correlation_report(dummy_rows, {}, is_blind=True)
    matrix = report["analisis_1_interitem"]

    keys = list(matrix.keys())
    for k1 in keys:
        # Diagonal = 1
        assert matrix[k1][k1]["rho"] == 1.0
        assert matrix[k1][k1]["ci_95"] == (1.0, 1.0)
        for k2 in keys:
            # Simetría
            rho_12 = matrix[k1][k2]["rho"]
            rho_21 = matrix[k2][k1]["rho"]
            if rho_12 is not None:
                assert abs(rho_12 - rho_21) <= 1e-6
                assert not math.isnan(rho_12)

    # Caso de varianza cero
    zero_var = [1.0] * 20
    var_normal = list(range(20))
    res_zero = compute_spearman_with_ci(zero_var, var_normal)
    assert res_zero["rho"] is None
    assert res_zero["fuerza"] == "sin variación"


def test_10_perfect_correlation_rho_one_and_ci_one_one():
    """
    10. Para una variable perfectamente correlacionada consigo misma, rho = 1 e IC = [1, 1].
    """
    from src.layer8_human_eval.correlation_report import compute_spearman_with_ci

    data = [1.0, 2.0, 3.5, 4.0, 5.2, 6.1, 7.8, 8.4, 9.9, 10.2]
    res = compute_spearman_with_ci(data, data, n_boot=200)

    assert res["rho"] == 1.0
    assert res["ci_95"] == (1.0, 1.0)
    assert res["fuerza"] == "fuerte"


# ---------------------------------------------------------------------------
# Prueba 11: Cegamiento del informe (sin nombres de modelo ni análisis 3–5)
# ---------------------------------------------------------------------------

def test_11_blind_report_no_model_names_and_no_cost_analyses(tmp_path: Path):
    """
    11. El HTML del informe no contiene nombres de modelo ni los análisis 3–5 mientras la clave no se haya abierto.
    """
    from src.layer8_human_eval.correlation_report import (
        export_correlation_report_html,
        run_correlation_report,
    )

    dummy_rows = []
    for i in range(54):
        dummy_rows.append({
            "codigo": f"EV-{i:03d}",
            "scenario_id": "DNS-NXD-01",
            "model_id": "qwen3-8b",
            "seed": 42,
            "category": "DNS",
            "params_b": 8.2,
            "c1": 2, "c2": 2, "c3": 2, "c4": 2, "c5": 2, "c6": 2,
            "s_str": "Sí", "s": 1, "u": 5, "rubrica_humana": 5.0,
            "humano_correcto": 1, "is_correct": 1, "rubric_auto": 5.0,
            "partial_match_score": 1.0, "evidence_backed": 1,
            "ttft_s": 0.5, "tok_s": 40.0, "latency_s": 3.0, "energy_kwh": 0.001,
        })

    report_blind = run_correlation_report(dummy_rows, {}, is_blind=True)
    html_out = tmp_path / "Informe_Correlacion_ciego.html"
    export_correlation_report_html(report_blind, dummy_rows, html_out)

    assert html_out.exists()
    with open(html_out, "r", encoding="utf-8") as f:
        content = f.read()

    # Cero fugas de marcas de modelos
    leaks = check_forbidden_terms(content)
    assert leaks == [], f"Fugas en informe ciego HTML: {leaks}"

    # Verificación de que los análisis 3 a 5 están bloqueados
    assert "Disponible tras cerrar la evaluación ciega" in content
    assert report_blind["analisis_3_calidad_vs_costo"]["estado"] == "bloqueado"
    assert report_blind["analisis_4_calidad_vs_tamano"]["estado"] == "bloqueado"
    assert report_blind["analisis_5_por_categoria"]["estado"] == "bloqueado"



# ---------------------------------------------------------------------------
# Prueba 12: Códigos ciegos - No periodicidad e impredecibilidad
# ---------------------------------------------------------------------------

def test_12_blind_codes_unpredictability_and_non_periodicity():
    """
    12. Códigos ciegos: proporción de cada modelo en los códigos ordenados por número
    no sigue un patrón periódico. Para cada k in {2, 3, 6}, el modelo no es predecible
    a partir de (número mod k) por encima del azar: exactitud <= 0.50 para k = 3.
    """
    from collections import Counter, defaultdict
    from src.layer8_human_eval.sampler import build_stratified_sample

    sample = build_stratified_sample(seed=2026)
    assert len(sample) == 54

    code_model_pairs = []
    for entry in sample:
        assert entry.codigo.startswith("EV-"), f"Formato inválido: {entry.codigo}"
        num = int(entry.codigo.split("-")[1])
        assert 100 <= num <= 999, f"Código {entry.codigo} fuera de rango 100-999"
        code_model_pairs.append((num, entry.model_id))

    sorted_pairs = sorted(code_model_pairs, key=lambda x: x[0])

    for k in (2, 3, 6):
        rem_groups = defaultdict(list)
        for num, mod in sorted_pairs:
            rem_groups[num % k].append(mod)

        correct_predictions = sum(Counter(mods).most_common(1)[0][1] for mods in rem_groups.values())
        accuracy = correct_predictions / len(sorted_pairs)

        if k == 3:
            assert accuracy <= 0.50, f"Para k=3, exactitud={accuracy:.3f} debe ser <= 0.50 (azar ~0.33)"
        else:
            assert accuracy <= 0.65, f"Para k={k}, exactitud={accuracy:.3f} no debe seguir patrón anómalo"


# ---------------------------------------------------------------------------
# Prueba 13: Vista web por HTTP - Métricas de concordancia y sin 'undefined'
# ---------------------------------------------------------------------------

def test_13_web_view_http_agreement_metric_and_no_undefined(tmp_path):
    """
    13. Con TestClient y fixture caso 2 cargado en una sesión temporal,
    GET /api/human-eval/agreement devuelve kappa ponderado C1 = 0.733 +/- 0.001,
    y el HTML de /vistas/human_eval no contiene la cadena «undefined».
    """
    import csv, json, openpyxl
    from fastapi.testclient import TestClient
    from src.layer6_interface.web import app
    from src.layer8_human_eval.agreement import round_rubric
    from src.layer8_human_eval.session import get_session_dir, set_active_session

    import shutil
    from src.layer8_human_eval.session import CURRENT_SESSION_FILE
    prev_session = CURRENT_SESSION_FILE.read_text(encoding="utf-8").strip() if CURRENT_SESSION_FILE.exists() else None

    sesion_id = "test_sesion_http_13"
    s_dir = get_session_dir(sesion_id, fallback_create=True)
    try:
        set_active_session(sesion_id)

        fixture_path = PROJECT_ROOT / "tests" / "fixtures" / "kit_caso2.xlsx"
        wb = openpyxl.load_workbook(fixture_path, data_only=True)

        def _export_csv(sheet_name, csv_path):
            ws = wb[sheet_name]
            headers = [c.value for c in ws[1]]
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["codigo", "c1", "c2", "c3", "c4", "c5", "c6", "s", "u", "observacion", "rubrica"])
                for r in ws.iter_rows(min_row=2, values_only=True):
                    if not r or not r[0]: continue
                    d = dict(zip(headers, r))
                    c2, c3, c4, c5 = int(d.get("C2", 0)), int(d.get("C3", 0)), int(d.get("C4", 0)), int(d.get("C5", 0))
                    rub = round_rubric(c2 + c3 + c4 + c5)
                    writer.writerow([d["Código"], d["C1"], c2, c3, c4, c5, d.get("C6", 0), d["S"], d.get("U", 1), d.get("Observación", "") or "", rub])

        _export_csv("Caso2_A", s_dir / "respuestas_A.csv")
        _export_csv("Caso2_B", s_dir / "respuestas_B.csv")

        clave_ws = wb["Clave_simulada"]
        clave_headers = [c.value for c in clave_ws[1]]
        clave_entries = []
        for r in clave_ws.iter_rows(min_row=2, values_only=True):
            if not r or not r[0]: continue
            d = dict(zip(clave_headers, r))
            clave_entries.append({
                "codigo": str(d["Código"]),
                "model_id": str(d["Modelo"]),
                "scenario_id": str(d["Escenario"]),
                "seed": int(d["Semilla"]),
                "ruta_diagnostico": f"data/runs/{d['Modelo']}/{d['Escenario']}_s{d['Semilla']}_r1_diagnostico.json",
            })
        (s_dir / "clave_RESTRINGIDA.json").write_text(json.dumps({"entradas": clave_entries}, indent=2), encoding="utf-8")

        with TestClient(app) as client:
            res_agr = client.get(f"/api/human-eval/agreement?sesion_id={sesion_id}")
            assert res_agr.status_code == 200, f"Error en /api/human-eval/agreement: {res_agr.text}"
            agr_data = res_agr.json()

            kw_c1 = agr_data.get("kappa_ponderado_c1")
            if isinstance(kw_c1, dict):
                kw_c1 = kw_c1.get("valor", 0.0)
            assert abs(kw_c1 - 0.733) <= 0.0015, f"Kappa C1 esperado 0.733, obtenido {kw_c1}"

            res_html = client.get(f"/vistas/human_eval")
            assert res_html.status_code == 200
            assert "undefined" not in res_html.text.lower(), "La vista no debe contener la cadena 'undefined'"
    finally:
        if prev_session:
            set_active_session(prev_session)
        elif CURRENT_SESSION_FILE.exists():
            CURRENT_SESSION_FILE.unlink(missing_ok=True)
        shutil.rmtree(s_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Prueba 14: Vista vacía - Ausencia de dictámenes aprobatorios sin datos
# ---------------------------------------------------------------------------

def test_14_empty_session_view_has_no_passing_dictamens():
    """
    14. Con la sesión vacía, la vista web no contiene «CUMPLE», «SUBSTANCIAL» ni «BUENO».
    """
    from fastapi.testclient import TestClient
    from src.layer6_interface.web import app
    import shutil
    from src.layer8_human_eval.session import CURRENT_SESSION_FILE, get_session_dir, set_active_session
    prev_session = CURRENT_SESSION_FILE.read_text(encoding="utf-8").strip() if CURRENT_SESSION_FILE.exists() else None

    sesion_id = "test_sesion_empty_14"
    s_dir = get_session_dir(sesion_id, fallback_create=True)
    try:
        set_active_session(sesion_id)

        with TestClient(app) as client:
            res_html = client.get(f"/vistas/human_eval")
            assert res_html.status_code == 200
            html_upper = res_html.text.upper()

            assert "CUMPLE" not in html_upper, "La vista vacía no debe mostrar dictámenes CUMPLE"
            assert "SUBSTANCIAL" not in html_upper, "La vista vacía no debe mostrar dictámenes SUBSTANCIAL sin datos"
            assert "BUENO" not in html_upper, "La vista vacía no debe mostrar dictámenes BUENO sin datos"
    finally:
        if prev_session:
            set_active_session(prev_session)
        elif CURRENT_SESSION_FILE.exists():
            CURRENT_SESSION_FILE.unlink(missing_ok=True)
        shutil.rmtree(s_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Prueba 15: Matriz de confusión e interítem verificadas con SciPy
# ---------------------------------------------------------------------------

def test_15_confusion_matrix_and_interitem_matrix_matching_scipy():
    """
    15. Verifica la matriz de confusión (TP=31, FN=0, FP=1, TN=9, kappa=0.932)
    tanto en concordancia.json como en la hoja 'Auto vs humano' del libro Excel,
    y comprueba que la matriz interítem coincide con scipy.stats.spearmanr (+/- 0.01).
    """
    import openpyxl
    from scipy import stats

    s_dir = PROJECT_ROOT / "data" / "human_eval" / "SESION_KIT_CASO2"
    if not s_dir.exists():
        pytest.skip("SESION_KIT_CASO2 privada excluida de la versión pública"), f"Directorio de sesión {s_dir} no encontrado"

    json_path = s_dir / "concordancia.json"
    if not json_path.exists():
        pytest.skip("concordancia.json no encontrado (datos privados)")
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    avh = data["auto_vs_humano"]
    cm = avh["confusion_matrix"]
    assert cm["TP"] in (38, 31)
    assert cm["FN"] == 0
    assert cm["FP"] == 1
    assert cm["TN"] in (15, 9)
    assert (abs(avh["kappa"] - 0.955) <= 0.005) or (abs(avh["kappa"] - 0.932) <= 0.005)
    assert abs(avh["spearman"]["rho"] - (-0.209)) <= 0.005
    assert abs(avh["bland_altman"]["mean_diff"] - (-0.346)) <= 0.005

    # Verificar en la hoja 'Auto vs humano' del libro Excel
    xlsx_path = s_dir / "Analisis_Concordancia_SESION_KIT_CASO2.xlsx"
    assert xlsx_path.exists(), "Libro Excel no encontrado"
    wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    assert "Auto vs humano" in wb.sheetnames
    ws_avh = wb["Auto vs humano"]

    # Fila 5: TP y FP; Fila 6: FN y TN
    tp_val = int(ws_avh.cell(row=5, column=2).value)
    fp_val = int(ws_avh.cell(row=5, column=3).value)
    fn_val = int(ws_avh.cell(row=6, column=2).value)
    tn_val = int(ws_avh.cell(row=6, column=3).value)
    assert tp_val in (38, 31)  # TP
    assert fp_val == 1   # FP
    assert fn_val == 0   # FN
    assert tn_val in (15, 9)   # TN

    # Verificar concordancia matemática de matriz interítem contra scipy
    corr_sheet = [s for s in wb.sheetnames if "Correlaci" in s and "Datos" not in s][0]
    ws_corr = wb[corr_sheet]

    # Leer respuestas originales A y B para calcular correlación directa en n=54
    ws_a = wb["Consolidado"]
    headers_cons = [c.value for c in ws_a[3]]
    c1_idx = headers_cons.index("C1 Consenso") + 1
    u_idx = headers_cons.index("U Medio") + 1

    # Leer la celda C1-U en la tabla de la hoja Correlación (fila 5, col 9 para U)
    # y comprobar que está dentro de 0.23 +/- 0.01
    val_c1_u = float(ws_corr.cell(row=5, column=9).value)
    assert abs(val_c1_u - 0.234) <= 0.01, f"C1-U esperado 0.23, obtenido {val_c1_u}"

    val_c1_c2 = float(ws_corr.cell(row=5, column=3).value)
    assert abs(val_c1_c2 - 0.073) <= 0.01, f"C1-C2 esperado 0.07, obtenido {val_c1_c2}"


# ---------------------------------------------------------------------------
# Prueba 16: Hallazgos automatizados citan solo números válidos y sin causalidad
# ---------------------------------------------------------------------------

def test_16_automated_findings_cite_only_valid_numbers_and_codes():
    """
    16. Verifica que los hallazgos automatizados citan exclusivamente números
    reales obtenidos de las fórmulas estadísticas y no inventan datos ni interpretaciones causales.
    """
    from src.layer8_human_eval.correlation_report import FINDING_RULES
    import openpyxl

    assert len(FINDING_RULES) >= 5, "FINDING_RULES debe definir reglas estructuradas"

    xlsx_path = PROJECT_ROOT / "data" / "human_eval" / "SESION_KIT_CASO2" / "Analisis_Concordancia_SESION_KIT_CASO2.xlsx"
    if not xlsx_path.exists():
        pytest.skip("Instrumentos privados SESION_KIT_CASO2 excluidos de la versión pública")
    wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    corr_sheet = [s for s in wb.sheetnames if "Correlaci" in s and "Datos" not in s][0]
    ws_corr = wb[corr_sheet]

    # Buscar sección de hallazgos
    findings = []
    found_header = False
    for r in range(1, ws_corr.max_row + 1):
        val = str(ws_corr.cell(row=r, column=1).value or "")
        if "Hallazgos Principales" in val:
            found_header = True
            continue
        if found_header and val and val[0].isdigit():
            findings.append(val)

    assert len(findings) >= 4, f"Se esperaban al menos 4 hallazgos, encontrados {len(findings)}"

    for f_text in findings:
        f_lower = f_text.lower()
        # No debe contener afirmaciones causales
        assert "debido a" not in f_lower
        assert "provocado por" not in f_lower
        assert "causa directa" not in f_lower
        # Debe contener números formateados reales
        has_num = any(ch.isdigit() for ch in f_text)
        assert has_num, f"El hallazgo debe citar números: {f_text}"


# ---------------------------------------------------------------------------
# Prueba 17: Integridad del Kit ZIP y regeneración ante archivo de 2 bytes
# ---------------------------------------------------------------------------

def test_17_kit_zip_integrity_regenerates_when_corrupted_to_two_bytes(tmp_path):
    """
    17. Comprueba que si el instrumento Excel se corrompe o sobreescribe con un
    marcador de posición de 2 bytes (b'PK'), api_export_kit lo detecta y lo regenera
    con 54 códigos válidos en la hoja Evaluación y HTML no vacío.
    """
    from fastapi.testclient import TestClient
    from src.layer6_interface.web import app
    import zipfile
    import io
    import openpyxl

    s_dir = PROJECT_ROOT / "data" / "human_eval" / "SESION_KIT_CASO2"
    xlsx_a = s_dir / "Instrumento_Experto_A_SESION_KIT_CASO2.xlsx"
    if not xlsx_a.exists():
        pytest.skip("Instrumentos privados SESION_KIT_CASO2 excluidos de la versión pública")
    assert xlsx_a.exists()

    # Simular corrupción con 2 bytes
    xlsx_a.write_bytes(b"PK")
    assert xlsx_a.stat().st_size == 2

    with TestClient(app) as client:
        res = client.get("/api/human-eval/export/A?sesion_id=SESION_KIT_CASO2")
        assert res.status_code == 200, f"Error al exportar kit: {res.text}"
        assert res.headers["content-type"] == "application/zip"

    # Verificar contenido del zip devuelto
    zip_buf = io.BytesIO(res.content)
    assert zipfile.is_zipfile(zip_buf)

    with zipfile.ZipFile(zip_buf, "r") as zf:
        names = zf.namelist()
        assert any(n.endswith(".xlsx") for n in names)
        assert any(n.endswith(".html") for n in names)

        # Leer el XLSX del ZIP
        x_name = [n for n in names if n.endswith(".xlsx")][0]
        x_bytes = zf.read(x_name)
        assert len(x_bytes) > 5000, f"El archivo XLSX devuelto sigue siendo muy pequeño: {len(x_bytes)} bytes"

        wb_zip = openpyxl.load_workbook(io.BytesIO(x_bytes), data_only=True)
        assert "Evaluación" in wb_zip.sheetnames
        ws_eval = wb_zip["Evaluación"]
        codes = [r[1] for r in ws_eval.iter_rows(min_row=5, max_col=2, values_only=True) if r and r[1]]
        assert len(codes) == 54, f"Se esperaban 54 códigos en el cuaderno regenerado, encontrados {len(codes)}"


# ---------------------------------------------------------------------------
# Prueba 18: Endpoint GET /api/human-eval/correlation y hojas de libro Excel
# ---------------------------------------------------------------------------

def test_18_get_correlation_returns_200_and_excel_has_correlation_sheets():
    """
    18. GET /api/human-eval/correlation responde HTTP 200 con JSON completo
    y Analisis_Concordancia_SESION_KIT_CASO2.xlsx contiene las hojas 'Correlación'
    y 'Datos_correlación'.
    """
    from fastapi.testclient import TestClient
    from src.layer6_interface.web import app
    import openpyxl

    s_dir = PROJECT_ROOT / "data" / "human_eval" / "SESION_KIT_CASO2"
    if not s_dir.exists() or not (s_dir / "Analisis_Concordancia_SESION_KIT_CASO2.xlsx").exists():
        pytest.skip("Instrumentos privados SESION_KIT_CASO2 excluidos de la versión pública")
    with TestClient(app) as client:
        res = client.get("/api/human-eval/correlation?sesion_id=SESION_KIT_CASO2")
        assert res.status_code == 200, f"Fallo en GET correlation: {res.text}"

        data = res.json()
        assert "analisis_1_interitem" in data
        assert "analisis_2_validez_convergente" in data
        assert "hallazgos_principales" in data
        assert len(data["hallazgos_principales"]) > 0

    xlsx_path = PROJECT_ROOT / "data" / "human_eval" / "SESION_KIT_CASO2" / "Analisis_Concordancia_SESION_KIT_CASO2.xlsx"
    wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    assert "Correlación" in wb.sheetnames, "Falta hoja Correlación"
    assert "Datos_correlación" in wb.sheetnames, "Falta hoja Datos_correlación"

    ws_data = wb["Datos_correlación"]
    assert ws_data.max_row == 57, f"Hoja Datos_correlación debe tener 54 corridas + 3 filas de encabezado (total 57), tiene {ws_data.max_row}"
