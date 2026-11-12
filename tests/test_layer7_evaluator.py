"""
Pruebas Unitarias para la Capa 7: Evaluación y Arnés de Benchmark (NetDiagBench-L7)
Verifica métricas multi-criterio, rúbrica, estimación energética y el harness completo.
"""

from src.core.contracts import ResultadoEvaluacionContract
from src.layer7_evaluator.harness import BenchmarkEvaluatorHarness
from src.layer7_evaluator.metrics import (
    calculate_token_similarity,
    check_component_correct,
    check_root_cause_correct,
    classify_model,
    estimate_energy_and_carbon,
    evaluate_explanation_rubric,
    get_evaluator_version,
    load_evaluator_concepts,
)

# ── Similitud Jaccard ────────────────────────────────────────────────────────

def test_token_similarity_metric():
    text_a = "Registro DNS A ausente en zona BIND9"
    text_b = "Registro de zona faltante o nombre de dominio inexistente en BIND9"
    sim = calculate_token_similarity(text_a, text_b)
    assert 0.0 <= sim <= 1.0
    assert sim > 0.15


def test_token_similarity_identical():
    text = "NXDOMAIN en BIND9"
    assert calculate_token_similarity(text, text) == 1.0


def test_token_similarity_empty():
    assert calculate_token_similarity("", "algo") == 0.0
    assert calculate_token_similarity("", "") == 0.0


# ── Cotejo multi-criterio de causa raíz ──────────────────────────────────────

def test_root_cause_key_term_hit():
    """El diagnóstico contiene 'NXDOMAIN' → acierto por término clave."""
    is_correct, partial = check_root_cause_correct(
        predicted_root_cause="Registro DNS A ausente (NXDOMAIN) en la zona BIND9",
        ground_truth_root_cause="Registro DNS tipo A ausente en la zona de BIND9, dominio devuelve RCODE 3",
        fault_class="NXDOMAIN",
        predicted_component="bind9-authoritative",
        ground_truth_component="bind9-authoritative",
    )
    assert is_correct is True
    assert partial >= 0.5


def test_root_cause_key_term_502():
    """El diagnóstico contiene '502' → acierto por término clave."""
    is_correct, partial = check_root_cause_correct(
        predicted_root_cause="Backend upstream inaccesible, error 502 Bad Gateway",
        ground_truth_root_cause="Servicio upstream no responde, Connection refused → HTTP 502",
        fault_class="HTTP_502_BAD_GATEWAY",
    )
    assert is_correct is True


def test_root_cause_key_term_tls_expired():
    """El diagnóstico contiene 'expired' y 'certificate' → acierto."""
    is_correct, _ = check_root_cause_correct(
        predicted_root_cause="Certificado TLS expirado en el terminador SSL de Nginx",
        ground_truth_root_cause="Certificado digital X.509 expired en Nginx",
        fault_class="TLS_EXPIRED_CERT",
    )
    assert is_correct is True


def test_root_cause_lax_substring_rejected():
    """Términos genéricos como 'tls' o 'certificado' no deben validar un certificado expirado (Hallazgo A1)."""
    is_correct, _ = check_root_cause_correct(
        predicted_root_cause="Fallo en la conexión TLS segura del servidor web",
        ground_truth_root_cause="Certificado digital X.509 expired en Nginx",
        fault_class="TLS_EXPIRED_CERT",
    )
    assert is_correct is False


def test_root_cause_key_term_servfail():
    """El diagnóstico contiene 'timeout' → acierto para SERVFAIL."""
    is_correct, _ = check_root_cause_correct(
        predicted_root_cause="Timeout en resolución recursiva hacia servidor remoto",
        ground_truth_root_cause="Tiempo de espera agotado al consultar servidor autoritativo",
        fault_class="SERVFAIL",
    )
    assert is_correct is True


def test_root_cause_no_match():
    """Texto completamente irrelevante → no es acierto."""
    is_correct, partial = check_root_cause_correct(
        predicted_root_cause="La aplicación funciona correctamente sin problemas",
        ground_truth_root_cause="Registro DNS tipo A ausente en la zona BIND9",
        fault_class="NXDOMAIN",
    )
    assert is_correct is False
    assert partial < 0.5


def test_root_cause_omitted_is_strictly_penalized():
    """Omisión de causa raíz por el modelo debe penalizarse con 0.0 y False."""
    is_correct, partial = check_root_cause_correct(
        predicted_root_cause="",
        ground_truth_root_cause="Registro DNS tipo A ausente en la zona BIND9",
        fault_class="NXDOMAIN",
    )
    assert is_correct is False
    assert partial == 0.0


def test_component_omitted_is_strictly_penalized():
    """Omisión de componente afectado debe retornar False."""
    assert check_component_correct("", "bind9-authoritative") is False
    assert check_component_correct("   ", "bind9-authoritative") is False


def test_explanation_omitted_is_strictly_penalized():
    """Omisión de explicación debe recibir 0.0 puntos en la rúbrica."""
    score = evaluate_explanation_rubric(
        explanation="",
        root_cause_correct=False,
        component_correct=False,
        evidence_backed=False
    )
    assert score == 0.0


# ── Verificación de componente ───────────────────────────────────────────────

def test_component_exact_match():
    assert check_component_correct("bind9-authoritative", "bind9-authoritative") is True


def test_component_partial_match():
    # Auditoría A4: 'bind9' es compartido por múltiples componentes y no debe coincidir solo
    assert check_component_correct("bind9", "bind9-authoritative") is False
    # Término distintivo sí coincide
    assert check_component_correct("autoritativo", "bind9-authoritative") is True


def test_component_alias_match():
    assert check_component_correct("servidor autoritativo", "bind9-authoritative") is True


def test_component_no_match():
    assert check_component_correct("nginx-proxy", "bind9-authoritative") is False


def test_component_empty():
    assert check_component_correct("", "bind9-authoritative") is False


# ── Estimación energética ────────────────────────────────────────────────────

def test_energy_estimation_model():
    kwh, co2 = estimate_energy_and_carbon(total_time_ms=5000.0, vram_peak_gb=5.5)
    assert kwh > 0.0
    assert co2 > 0.0


def test_energy_estimation_zero_time():
    kwh, co2 = estimate_energy_and_carbon(total_time_ms=0.0, vram_peak_gb=0.0)
    assert kwh == 0.0
    assert co2 == 0.0


# ── Rúbrica de explicabilidad ────────────────────────────────────────────────

def test_explanation_rubric_perfect():
    score = evaluate_explanation_rubric(
        explanation="Explicación técnica detallada del problema con evidencia de dig y logs de BIND9 "
                    "que fundamentan la causa raíz identificada con los pasos de verificación apropiados "
                    "para confirmar el diagnóstico y proponer la mitigación correspondiente.",
        root_cause_correct=True,
        component_correct=True,
        evidence_backed=True
    )
    assert score >= 4.5
    assert score <= 5.0


def test_explanation_rubric_partial():
    score = evaluate_explanation_rubric(
        explanation="Se observan errores en el servicio pero no se identifica la causa exacta.",
        root_cause_correct=False,
        component_correct=True,
        evidence_backed=False
    )
    assert 1.5 <= score <= 3.0


def test_explanation_rubric_poor():
    score = evaluate_explanation_rubric(
        explanation="No sé.",
        root_cause_correct=False,
        component_correct=False,
        evidence_backed=False
    )
    assert score <= 1.5


# ── Arnés de benchmark completo ──────────────────────────────────────────────

def test_benchmark_harness_single_trial(tmp_path):
    harness = BenchmarkEvaluatorHarness(output_dir=tmp_path)
    harness.inference_engine.force_simulation = True
    results = harness.run_benchmark(
        model_ids=["phi-4-mini-instruct"],
        scenario_ids=["DNS-NXD-01"],
        seeds=[42],
        repetitions=1,
        output_csv_filename="test_resultados.csv",
        generate_report=False,
        resume=False
    )
    assert len(results) == 1
    res = results[0]
    assert isinstance(res, ResultadoEvaluacionContract)
    assert res.model_id == "phi-4-mini-instruct"
    assert res.scenario_id == "DNS-NXD-01"
    assert res.evidence_backed is True


def test_benchmark_harness_root_cause_correct(tmp_path):
    """Tras las mejoras, el simulador debe acertar en NXDOMAIN con el matcher multi-criterio."""
    harness = BenchmarkEvaluatorHarness(output_dir=tmp_path)
    harness.inference_engine.force_simulation = True
    results = harness.run_benchmark(
        model_ids=["qwen3-8b"],
        scenario_ids=["DNS-NXD-01"],
        seeds=[42],
        repetitions=1,
        output_csv_filename="test_resultados.csv",
        generate_report=False,
        resume=False
    )
    res = results[0]
    assert res.is_root_cause_correct is True, (
        f"La causa raíz debería ser correcta para DNS-NXD-01 (partial_score={res.partial_match_score})"
    )
    assert res.partial_match_score >= 0.5


def test_benchmark_harness_all_scenarios_correct(tmp_path):
    """Verifica que TODAS las clases de escenario del catálogo son diagnosticadas correctamente."""
    harness = BenchmarkEvaluatorHarness(output_dir=tmp_path)
    harness.inference_engine.force_simulation = True
    results = harness.run_benchmark(
        model_ids=["phi-4-mini-instruct"],
        seeds=[42],
        repetitions=1,
        output_csv_filename="test_resultados.csv",
        generate_report=False,
        resume=False
    )
    failed = [(r.scenario_id, r.fault_class, r.is_root_cause_correct, r.partial_match_score)
              for r in results if not r.is_root_cause_correct]
    assert len(failed) == 0, f"Escenarios con diagnóstico fallido: {failed}"


# ── Verificación del Evaluador Oficial y Clasificación de Modelos ───────────

def test_evaluator_version_and_catalog():
    ver = get_evaluator_version()
    assert len(ver) == 12
    concepts = load_evaluator_concepts()
    classes = concepts.get("classes", {})
    assert len(classes) == 18
    for c_name, c_data in classes.items():
        assert len(c_data.get("cause_groups", c_data.get("cause_concepts", []))) > 0
        assert len(c_data.get("neighbor_concepts", [])) > 0
        assert "source" in c_data


def test_classify_model_triad_and_additionals():
    # Terna oficial: con razonamiento activo vs base
    grp_qwen_cot, fam_qwen_cot = classify_model("qwen3-8b", reasoning_tokens=250)
    assert grp_qwen_cot == "oficial"
    assert fam_qwen_cot == "razonamiento"

    grp_qwen_base, fam_qwen_base = classify_model("qwen3-8b", reasoning_tokens=0)
    assert grp_qwen_base == "oficial"
    assert fam_qwen_base == "completo"

    grp_phi, fam_phi = classify_model("phi-4-mini-instruct", parameters_raw="3.8B")
    assert grp_phi == "oficial"
    assert fam_phi == "intermedio"

    grp_glm, fam_glm = classify_model("glm-4-9b-chat", parameters_raw="9B")
    assert grp_glm == "oficial"
    assert fam_glm == "completo"

    # Modelos adicionales
    grp_coder, fam_coder = classify_model("qwen2.5-coder:7b")
    assert grp_coder == "adicional"
    assert fam_coder == "codigo"

    grp_smol, fam_smol = classify_model("smollm:135m", parameters_raw="135M")
    assert grp_smol == "adicional"
    assert fam_smol == "ultraligero"

    grp_r1, fam_r1 = classify_model("deepseek-r1:8b")
    assert grp_r1 == "adicional"
    assert fam_r1 == "razonamiento"

