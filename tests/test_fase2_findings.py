"""
Tests for Phase 2 Subsanación findings in NetDiagBench-L7:
- Hallazgo 4.1: Puntaje compuesto 40/20/20/20 y umbral previo del 70% de exactitud.
- Hallazgos 4.2 & 4.3: Detección y persistencia de hardware físico real (AMD Radeon 610M, RAM, CPU).
- Hallazgo 4.4: Separación ortogonal de execution_mode y engine_mode.
- Hallazgo 4.5: Normalización de unidades (TTFT en s, tokens/kWh, RAM en GB).
- Hallazgo 4.6: Expansión de conceptos TLS/HTTP en configs/evaluator_concepts.yaml y aislamiento de HTTP 503.
- Hallazgo 4.7: Exactitud factual C6 y sustento empírico.
"""

import pytest
from src.core.contracts import (
    DiagnosticoFinalContract,
    EscenarioLabContract,
    FaultClass,
    GroundTruth,
    ResultadoEvaluacionContract,
    ServiceCategory,
)
from src.core.hardware_detector import detect_system_hardware
from src.layer7_evaluator.composite_score import (
    ACCURACY_THRESHOLD_PCT,
    WEIGHTS,
    calculate_model_composite_scores,
    rank_models_by_composite_score,
)
from src.layer7_evaluator.metrics import (
    check_root_cause_correct,
    load_evaluator_concepts,
)
from src.layer5_orchestrator.agent import DiagnosticOrchestratorAgent


def test_composite_score_weights():
    """Verifica que los pesos sean exactamente 40% precisión, 20% rúbrica, 20% velocidad, 20% VRAM."""
    assert WEIGHTS["accuracy"] == 0.40
    assert WEIGHTS["rubric"] == 0.20
    assert WEIGHTS["speed"] == 0.20
    assert WEIGHTS["vram_efficiency"] == 0.20
    assert sum(WEIGHTS.values()) == pytest.approx(1.0)


def test_composite_score_threshold_70_pct():
    """Verifica que el umbral del 70% excluya modelos con exactitud < 70%."""
    sample_models = {
        "model_high": {
            "accuracy_pct": 72.2,
            "rubric": 4.1,
            "tokens_per_sec": 30.0,
            "vram_gb": 4.0,
        },
        "model_border": {
            "accuracy_pct": 70.0,
            "rubric": 3.8,
            "tokens_per_sec": 25.0,
            "vram_gb": 5.0,
        },
        "model_low": {
            "accuracy_pct": 66.7,
            "rubric": 4.5,
            "tokens_per_sec": 40.0,
            "vram_gb": 3.0,
        },
    }

    scored = calculate_model_composite_scores(sample_models, threshold_pct=70.0)
    assert scored["model_high"]["elegibilidad"] is True
    assert scored["model_high"]["motivo_exclusion"] == ""

    assert scored["model_border"]["elegibilidad"] is True
    assert scored["model_border"]["motivo_exclusion"] == ""

    assert scored["model_low"]["elegibilidad"] is False
    assert "inferior al umbral mínimo" in scored["model_low"]["motivo_exclusion"]

    ranked_eligible, ranked_excluded = rank_models_by_composite_score(scored)
    assert "model_high" in ranked_eligible
    assert "model_border" in ranked_eligible
    assert "model_low" in ranked_excluded


def test_physical_hardware_detector():
    """Verifica la detección no inventada del hardware físico real del host."""
    hw = detect_system_hardware()
    assert hw.gpu_model == "AMD Radeon(TM) 610M" or "AMD" in hw.gpu_model or "NVIDIA" in hw.gpu_model
    assert hw.ram_total_gb > 0.0
    assert hw.vram_total_gb > 0.0
    assert hw.cpu_cores_logical >= 4
    assert len(hw.fingerprint) > 20


def test_normalized_units_in_evaluation_contract():
    """Verifica los campos normalizados en ResultadoEvaluacionContract."""
    hw = detect_system_hardware()
    res = ResultadoEvaluacionContract(
        scenario_id="DNS-NXD-01",
        model_id="qwen3-8b",
        seed=42,
        repetition_index=1,
        category="DNS",
        fault_class="NXDOMAIN",
        is_root_cause_correct=True,
        is_component_correct=True,
        partial_match_score=1.0,
        evidence_backed=True,
        ttft_ms=125.0,
        tokens_per_sec=28.5,
        total_time_ms=500.0,
        tool_steps_count=2,
        cpu_percent_avg=45.0,
        peak_ram_mb=1024.0,
        peak_vram_gb=4.5,
        energy_kwh=0.00012,
        co2_emissions_kg=0.00003,
        rubric_score=4.2,
        host_hardware_fingerprint=hw.fingerprint,
        execution_mode="sintetico_determinista",
        engine_mode="deterministic_simulator",
        factual_accuracy_c6=2,
        ttft_s=0.125,
        tokens_per_kwh=237500.0,
        energy_measurement_type="estimada",
        ram_gb=1.0,
        gpu_model_detected=hw.gpu_model,
        vram_total_gb=hw.vram_total_gb,
        vram_measurement_method=hw.vram_measurement_method,
        vram_measurement_valid=False,
        vram_declared_gb=8.0,
        ram_total_gb=hw.ram_total_gb,
        ram_available_gb=hw.ram_available_gb,
        process_max_ram_gb=1.0,
        cpu_model=hw.cpu_model,
        os_version=hw.os_version,
        driver_version=hw.driver_version,
        cuda_version=hw.cuda_version,
        puntaje_precision=0.40,
        puntaje_rubrica=0.168,
        puntaje_velocidad=0.114,
        puntaje_vram=0.044,
        puntaje_compuesto=0.726,
        elegibilidad=True,
        motivo_exclusion="",
    )

    assert res.ttft_s == 0.125
    assert res.ram_gb == 1.0
    assert res.energy_measurement_type == "estimada"
    assert res.execution_mode == "sintetico_determinista"
    assert res.engine_mode == "deterministic_simulator"
    assert res.factual_accuracy_c6 == 2


def test_tls_expired_cert_concept_expansion():
    """Verifica que TLS_EXPIRED_CERT reconozca los términos ampliados en inglés y español."""
    concepts = load_evaluator_concepts().get("classes", {})
    tls_class = concepts.get("TLS_EXPIRED_CERT", {})
    cause_groups = tls_class.get("cause_groups", [])

    # Verificar que las palabras clave expandidas están presentes
    group_texts = []
    for g in cause_groups:
        group_texts.extend(g.get("nucleus", []))
        group_texts.extend(g.get("modifiers", []))

    for required_term in ["expired", "notafter", "not after", "vencido", "certificate has expired", "certificado expirado"]:
        assert any(required_term in t.lower() for t in group_texts), f"Term {required_term} missing from TLS_EXPIRED_CERT"

    # Verificar evaluación con texto en inglés y español
    corr_es, _ = check_root_cause_correct(
        predicted_root_cause="El certificado digital ha vencido y superó la fecha notAfter.",
        ground_truth_root_cause="Certificado X.509 expirado",
        fault_class="TLS_EXPIRED_CERT",
    )
    assert corr_es is True

    corr_en, _ = check_root_cause_correct(
        predicted_root_cause="The server certificate is expired according to notAfter date.",
        ground_truth_root_cause="Expired certificate",
        fault_class="TLS_EXPIRED_CERT",
    )
    assert corr_en is True


def test_http_503_isolation_from_certificates():
    """Verifica que HTTP_503_SERVICE_UNAVAILABLE tenga aislados los conceptos de certificados para evitar falsos positivos."""
    concepts = load_evaluator_concepts().get("classes", {})
    http503 = concepts.get("HTTP_503_SERVICE_UNAVAILABLE", {})
    neighbors = [n.lower() for n in http503.get("neighbor_concepts", [])]

    assert "certificate" in neighbors or "certificado" in neighbors
    assert "expired" in neighbors or "vencido" in neighbors

    # Un diagnóstico que erróneamente concluye certificado expirado en HTTP 503 debe ser marcado is_correct = False
    corr, _ = check_root_cause_correct(
        predicted_root_cause="El error es debido a que el certificado ssl está expirado y vencido.",
        ground_truth_root_cause="Saturación de workers",
        fault_class="HTTP_503_SERVICE_UNAVAILABLE",
    )
    assert corr is False


def test_factual_accuracy_c6_and_evidence_backing():
    """Verifica que C6 distinga evidencia plena, parcial y nula/bloqueada."""
    agent = DiagnosticOrchestratorAgent()
    sc = EscenarioLabContract(
        scenario_id="TLS-EXP-01",
        category=ServiceCategory.TLS,
        fault_class=FaultClass.TLS_EXPIRED_CERT,
        description="Certificado caducado",
        ground_truth=GroundTruth(
            root_cause="Certificado expirado",
            affected_component="nginx-tls-termination",
            suggested_action="Renovar certificado",
            minimum_required_evidence=["openssl s_client", "verify error:num=10:certificate has expired"],
        ),
    )

    # 1. Evidencia plena con salida correspondiente
    diag_full = agent._parse_final_diagnosis(
        scenario=sc,
        model_id="qwen3-8b",
        response_text='{"causa_raiz": "Certificado expirado", "componente": "nginx-tls-termination", "mitigacion": "Renovar", "fundamentacion_tecnica": "Fundamentación técnica válida."}',
        evidence_list=["openssl s_client -> verify error:num=10:certificate has expired"],
        execution_mode="sintetico_determinista",
        engine_mode="deterministic_simulator",
        tool_blocked_penalty=False,
    )
    assert diag_full.factual_accuracy_c6 == 2
    assert diag_full.is_evidence_backed is True
    assert diag_full.engine_mode == "deterministic_simulator"

    # 2. Sin evidencia ejecutada
    diag_none = agent._parse_final_diagnosis(
        scenario=sc,
        model_id="qwen3-8b",
        response_text='{"causa_raiz": "Certificado expirado", "componente": "nginx-tls-termination", "mitigacion": "Renovar", "fundamentacion_tecnica": "Fundamentación técnica válida."}',
        evidence_list=[],
        execution_mode="sintetico_determinista",
        engine_mode="deterministic_simulator",
        tool_blocked_penalty=False,
    )
    assert diag_none.factual_accuracy_c6 == 0
    assert diag_none.is_evidence_backed is False

    # 3. Penalización por comando bloqueado
    diag_blocked = agent._parse_final_diagnosis(
        scenario=sc,
        model_id="qwen3-8b",
        response_text='{"causa_raiz": "Certificado expirado", "componente": "nginx-tls-termination", "mitigacion": "Renovar", "fundamentacion_tecnica": "Fundamentación técnica válida."}',
        evidence_list=["openssl s_client -> Bloqueado: comando no permitido"],
        execution_mode="sintetico_determinista",
        engine_mode="deterministic_simulator",
        tool_blocked_penalty=True,
    )
    assert diag_blocked.factual_accuracy_c6 == 0
    assert diag_blocked.is_evidence_backed is False
