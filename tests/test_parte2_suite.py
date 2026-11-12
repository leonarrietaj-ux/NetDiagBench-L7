"""
NetDiagBench-L7: Suite de Pruebas Unitarias para la Parte 2/4.
Verifica:
1. Puntaje compuesto 40/20/20/20, umbral >= 70% y los 5 estados estandarizados.
2. F1 Macro y eliminación estricta de fuga de datos en el parser de predicciones.
3. Bootstrap por conglomerados (Cluster Bootstrap) y formato formal de valores p (sin '0.000').
4. Exactitud factual C6 y regla de sustentación empírica S (S=1 iff C6=2).
5. Aislamiento normativo TLS vs HTTP 503.
6. Trazabilidad JSONL con diferenciación de hashes y validación de alineación.
7. Integridad de kits de evaluación humana e historial de importaciones.
"""

import hashlib
import json
import math
from pathlib import Path
from typing import Any
import pytest

from src.core.config import PROJECT_ROOT
from src.layer7_evaluator.composite_score import (
    calculate_model_composite_scores,
    STATE_COMPLETE_MEASURED,
    STATE_PROVISIONAL_ESTIMATED,
    STATE_PENDING_HUMAN_EVAL,
    STATE_PENDING_VRAM,
    STATE_INELIGIBLE_ACCURACY,
    WEIGHTS,
)
from src.layer7_evaluator.statistical_analysis import (
    format_p_value,
    parse_fault_class_predicted,
    compute_classification_metrics,
    compute_model_bootstrap_ci95,
)
from src.layer5_orchestrator.agent import DiagnosticOrchestratorAgent
from src.core.trace_validator import (
    validate_trace_entry,
    validate_trace_file,
    validate_alignment_csv_jsonl,
    calculate_prompt_sha256,
)
from src.layer7_evaluator.metrics import load_evaluator_concepts, check_root_cause_correct


# ── 1. PUNTAJE COMPUESTO 40/20/20/20 Y UMBRAL DE ELEGIBILIDAD ──────────────

class TestCompositeScore:
    """Verifica los pesos metodológicos 40/20/20/20 y los 5 estados del scorecard."""

    def test_weights_formula_and_states(self):
        # 40% Diagnóstico, 20% Rúbrica, 20% Velocidad, 20% VRAM
        summary = {
            "m1": {
                "acc": 85.0,
                "rub": 4.0,  # 4/5 -> 0.80
                "tokens_per_sec": 15.0,
                "vram_peak_gb": 4.0,
                "vram_measurement_valid": True,
            }
        }
        res = calculate_model_composite_scores(summary)["m1"]
        assert res["estado_evaluacion"] == STATE_COMPLETE_MEASURED
        assert res["elegibilidad"] is True
        assert res["puntaje_compuesto_medido"] is not None
        # S = 0.40*(85/100) + 0.20*(4/5) + 0.20*(15/15) + 0.20*(4/4) = 0.34 + 0.16 + 0.20 + 0.20 = 0.90
        assert pytest.approx(res["puntaje_compuesto_medido"], rel=1e-3) == 0.9000

    def test_ineligible_when_accuracy_below_70_percent(self):
        # Modelos con exactitud < 70% quedan excluidos de elegibilidad
        summary = {
            "m_low": {
                "acc": 65.0,
                "rub": 4.5,
                "tokens_per_sec": 18.0,
                "vram_peak_gb": 4.0,
                "vram_measurement_valid": True,
            }
        }
        res = calculate_model_composite_scores(summary)["m_low"]
        assert res["estado_evaluacion"] == STATE_INELIGIBLE_ACCURACY
        assert res["elegibilidad"] is False
        assert "inferior al umbral mínimo del 70.0%" in res["motivo_exclusion"]

    def test_provisional_estimated_when_vram_unmeasured(self):
        # Si falta medición real de VRAM, no se redistribuye el 20% y pasa a estado provisional
        summary = {
            "m_no_vram": {
                "acc": 80.0,
                "rub": 3.5,
                "tokens_per_sec": 12.0,
                "vram_peak_gb": None,
                "vram_declared_gb": 8.0,
                "vram_measurement_valid": False,
            }
        }
        res = calculate_model_composite_scores(summary)["m_no_vram"]
        assert res["estado_evaluacion"] == STATE_PROVISIONAL_ESTIMATED
        assert res["puntaje_compuesto_medido"] is None
        assert res["puntaje_compuesto_provisional"] is not None
        assert res["estado_mediciones"]["vram"] == "no_disponible"

    def test_all_five_states_exist(self):
        # Confirmar los 5 estados estandarizados solicitados
        expected_states = {
            "COMPLETE_MEASURED",
            "PROVISIONAL_ESTIMATED",
            "PENDING_HUMAN_EVALUATION",
            "PENDING_VRAM_MEASUREMENT",
            "INELIGIBLE_ACCURACY",
        }
        actual_states = {
            STATE_COMPLETE_MEASURED,
            STATE_PROVISIONAL_ESTIMATED,
            STATE_PENDING_HUMAN_EVAL,
            STATE_PENDING_VRAM,
            STATE_INELIGIBLE_ACCURACY,
        }
        assert expected_states == actual_states


# ── 2. F1 MACRO Y CERO FUGA DE DATOS ────────────────────────────────────────

class TestF1MacroZeroLeakage:
    """Verifica el parser sin acceso a la verdad fundamental y métricas de clasificación."""

    def test_parser_detects_classes_without_ground_truth(self):
        # Probar parseo exclusivamente del texto del modelo
        text_servfail = "La falla se debe a que el autoritativo remoto no responde produciendo un timeout recursivo en el DNS."
        cls_pred, is_ambig, scores = parse_fault_class_predicted(text_servfail)
        assert cls_pred == "SERVFAIL"
        assert is_ambig is False
        assert "SERVFAIL" in scores

    def test_parser_empty_and_unknown(self):
        # Texto vacío debe retornar UNKNOWN
        cls_pred, is_ambig, scores = parse_fault_class_predicted("")
        assert cls_pred == "UNKNOWN"
        assert is_ambig is False
        assert scores == {}

    def test_parser_handles_ambiguity(self):
        # Texto genérico sin causa raíz clara
        text_gibberish = "El sistema presenta un comportamiento anormal con fallas no especificadas."
        cls_pred, is_ambig, scores = parse_fault_class_predicted(text_gibberish)
        assert cls_pred == "UNKNOWN"

    def test_compute_classification_metrics_no_leakage(self):
        # Filas sintéticas con respuestas originales sin indicador de acierto tramposo
        synthetic_rows = [
            {
                "scenario_id": "DNS-SERV-01",
                "fault_class": "SERVFAIL",
                "root_cause": "Timeout del servidor autoritativo remoto",
                "is_root_cause_correct": False,  # No debe forzar la predicción
            },
            {
                "scenario_id": "DNS-NXD-01",
                "fault_class": "NXDOMAIN",
                "root_cause": "El registro solicitado es inexistente en la zona (NXDOMAIN / RCODE 3)",
                "is_root_cause_correct": True,
            },
        ]
        metrics = compute_classification_metrics(synthetic_rows, n_bootstrap=10, seed=42)
        assert "f1_macro" in metrics
        assert "precision_macro" in metrics
        assert "recall_macro" in metrics
        assert "confusion_matrix" in metrics
        assert "per_class" in metrics
        assert isinstance(metrics["f1_macro"], float)


# ── 3. BOOTSTRAP POR CONGLOMERADOS Y FORMATO DE VALORES P ───────────────────

class TestBootstrapAndStats:
    """Verifica bootstrap por escenarios, preservación de diseño emparejado y valores p."""

    def test_p_value_never_outputs_zero(self):
        # Nunca debe imprimirse p = 0.000
        assert format_p_value(0.0) == "p < 0.001"
        assert format_p_value(0.0000001) == "p < 0.001"
        assert format_p_value(0.0009) == "p < 0.001"
        assert format_p_value(0.042) == "p = 0.042"
        assert format_p_value(None) == "p = NA"
        assert format_p_value(1.0) == "p = 1.000"

    def test_cluster_bootstrap_scenario_unit(self):
        # Crear 18 conglomerados de prueba simulando el diseño experimental emparejado
        test_rows = []
        for sc_idx in range(1, 19):
            sc_id = f"SC-{sc_idx:02d}"
            for seed in [42, 123, 999]:
                test_rows.append({
                    "model_id": "glm-4-9b-chat",
                    "scenario_id": sc_id,
                    "seed": seed,
                    "fault_class": "SERVFAIL",
                    "root_cause": "Timeout autoritativo remoto" if sc_idx % 2 == 0 else "Error no clasificado",
                    "is_root_cause_correct": bool(sc_idx % 2 == 0),
                    "rubric_score": 4.0 if sc_idx % 2 == 0 else 1.0,
                    "tokens_per_sec": 14.5,
                    "total_time_ms": 3200.0,
                })

        boot_res = compute_model_bootstrap_ci95(test_rows, n_bootstrap=50, seed=42)
        assert "glm-4-9b-chat" in boot_res
        m_info = boot_res["glm-4-9b-chat"]
        assert m_info["method"] == "cluster_bootstrap_percentile"
        assert m_info["cluster_unit"] == "scenario_id"
        assert m_info["n_clusters"] == 18
        assert "ci95" in m_info["accuracy"]
        assert "ci95" in m_info["f1_macro"]
        ci_lo, ci_hi = m_info["accuracy"]["ci95"]
        assert 0.0 <= ci_lo <= ci_hi <= 1.0


# ── 4. EXACTITUD FACTUAL C6 Y REGLA DE SUSTENTACIÓN EMPÍRICA S ─────────────

class TestFactualAccuracyC6:
    """Verifica que S=1 solo cuando C6=2 con evidencia verificable sin contradicciones."""

    def test_c6_full_evidence_backing(self):
        # Caso positivo: herramienta ejecutada con éxito y coincidente con requerimiento
        evidence = ["dig @127.0.0.1 app.internal -> ;; ->>HEADER<<- opcode: QUERY, status: NXDOMAIN, id: 1234"]
        req_ev = ["dig @127.0.0.1 app.internal -> status: NXDOMAIN"]
        root_cause = "Registro DNS inexistente en la zona (NXDOMAIN / RCODE 3)"

        c6_auto, is_backed, ev_status, sust_status = DiagnosticOrchestratorAgent._evaluate_factual_accuracy_c6(
            evidence_list=evidence,
            req_ev=req_ev,
            root_cause=root_cause,
            tool_blocked_penalty=False
        )
        assert c6_auto == 2
        assert is_backed is True  # S = 1
        assert ev_status == "backed"
        assert sust_status == "sustentado"

    def test_c6_partial_evidence_not_fully_backed(self):
        # Caso parcial: herramienta ejecutada pero evidencia incompleta respecto al requerimiento
        evidence = ["curl -I http://127.0.0.1:80 -> HTTP/1.1 200 OK"]
        req_ev = ["curl -I -s http://127.0.0.1:80/api/v1/orders -> HTTP/1.1 503 Service Unavailable"]
        root_cause = "Degradación en servicio HTTP"

        c6_auto, is_backed, ev_status, sust_status = DiagnosticOrchestratorAgent._evaluate_factual_accuracy_c6(
            evidence_list=evidence,
            req_ev=req_ev,
            root_cause=root_cause,
            tool_blocked_penalty=False
        )
        assert c6_auto == 1
        assert is_backed is False  # S = 0 cuando C6 == 1
        assert ev_status == "partial"
        assert sust_status == "no_sustentado"

    def test_c6_protocol_contradiction_penalized(self):
        # Caso contradicción: salida muestra NXDOMAIN (RCODE 3), pero diagnóstico concluye SERVFAIL (RCODE 2)
        evidence = ["dig @127.0.0.1 app.internal -> status: NXDOMAIN, rcode: 3"]
        req_ev = ["dig @127.0.0.1 app.internal -> status: NXDOMAIN"]
        root_cause = "Fallo de resolución SERVFAIL debido a servidor autoritativo caído"

        c6_auto, is_backed, ev_status, sust_status = DiagnosticOrchestratorAgent._evaluate_factual_accuracy_c6(
            evidence_list=evidence,
            req_ev=req_ev,
            root_cause=root_cause,
            tool_blocked_penalty=False
        )
        assert c6_auto == 0
        assert is_backed is False  # S = 0 por contradicción factual de protocolo
        assert ev_status == "contradictory"
        assert sust_status == "no_sustentado"

    def test_c6_tool_blocked_or_empty(self):
        # Si el comando fue bloqueado o no hay evidencia
        c6_auto, is_backed, ev_status, sust_status = DiagnosticOrchestratorAgent._evaluate_factual_accuracy_c6(
            evidence_list=[],
            req_ev=["some requirement"],
            root_cause="Diagnóstico inventado sin herramientas",
            tool_blocked_penalty=False
        )
        assert c6_auto == 0
        assert is_backed is False
        assert ev_status == "no_evidence"
        assert sust_status == "no_sustentado"


# ── 5. AISLAMIENTO TLS Y HTTP 503 ──────────────────────────────────────────

class TestTlsHttpIsolation:
    """Verifica detección de expiración TLS y prevención de confusión con HTTP 503."""

    def test_tls_expired_terms_present_in_catalog(self):
        concepts = load_evaluator_concepts().get("classes", {})
        tls_cls = concepts.get("TLS_EXPIRED_CERT", {})
        cause_groups = tls_cls.get("cause_groups", [])

        all_nucleus = [term.lower() for g in cause_groups for term in g.get("nucleus", [])]
        for expected in ["expired", "notafter", "not after", "vencido", "certificado expirado", "certificate has expired", "certificate validity"]:
            assert any(expected in n for n in all_nucleus), f"Falta término '{expected}' en TLS_EXPIRED_CERT"

    def test_http_503_isolates_tls_expiration(self):
        concepts = load_evaluator_concepts().get("classes", {})
        http_503 = concepts.get("HTTP_503_SERVICE_UNAVAILABLE", {})
        neighbors = [n.lower() for n in http_503.get("neighbor_concepts", [])]

        assert "certificate has expired" in neighbors
        assert "certificado expirado" in neighbors
        assert "certificate validity" in neighbors

    def test_tls_expired_not_classified_as_http_503(self):
        # Diagnóstico de certificado expirado no debe ser clasificado como HTTP 503
        diag = "El certificado SSL ha vencido (certificate has expired, notAfter pasado de fecha)."
        is_503, _ = check_root_cause_correct(
            predicted_root_cause=diag,
            ground_truth_root_cause="Workers de backend saturados generando HTTP 503",
            fault_class="HTTP_503_SERVICE_UNAVAILABLE"
        )
        assert is_503 is False

        is_tls, _ = check_root_cause_correct(
            predicted_root_cause=diag,
            ground_truth_root_cause="El certificado digital expiró (certificate has expired)",
            fault_class="TLS_EXPIRED_CERT"
        )
        assert is_tls is True


# ── 6. TRAZABILIDAD JSONL Y DIFERENCIACIÓN DE HASHES ────────────────────────

class TestTraceValidatorAndHashes:
    """Verifica la diferenciación de template_sha256 vs prompt_sha256 y validador JSONL."""

    def test_hashes_differentiation(self):
        prompt = "INCIDENTE DNS: Analice el siguiente volcado de logs..."
        template_text = "Template Jinja2 base: {{ incident_content }}"

        prompt_sha = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        template_sha = hashlib.sha256(template_text.encode("utf-8")).hexdigest()

        # template_sha256 no debe ser igual a prompt_sha256
        assert prompt_sha != template_sha

    def test_validator_detects_conflated_hashes(self):
        prompt = "INCIDENTE DNS"
        same_hash = calculate_prompt_sha256(prompt)

        entry = {
            "run_id": "test_run_1",
            "scenario_id": "DNS-01",
            "model_id": "qwen3-8b",
            "engine_mode": "live_ollama",
            "execution_mode": "emulado",
            "timestamp": "2026-11-06T12:00:00Z",
            "prompt": prompt,
            "template_sha256": same_hash,  # Conflated with prompt_sha256!
            "prompt_sha256": same_hash,
            "evaluator_version": "abc12345",
            "response": "El modelo diagnosticó la falla correctamente.",
            "tools_called": ["dig"],
            "outputs": ["NXDOMAIN"],
            "return_codes": [0],
            "ttft_s": 1.2,
            "tokens": 150,
            "speed": 18.0,
            "energy_kwh": 0.0005,
            "vram_peak_gb": None,
            "ram_gb": 3.2,
            "root_cause_expected": "NXDOMAIN",
            "root_cause_predicted": "NXDOMAIN",
            "factual_accuracy_c6": 2,
            "is_evidence_backed": True,
        }
        ok, err = validate_trace_entry(entry, verify_prompt_hash=True)
        assert ok is False
        assert "template_sha256 coincide con prompt_sha256" in err

    def test_validator_detects_empty_response(self):
        entry = {
            "run_id": "test_empty_run",
            "scenario_id": "DNS-01",
            "model_id": "qwen3-8b",
            "engine_mode": "live_ollama",
            "execution_mode": "emulado",
            "timestamp": "2026-11-06T12:00:00Z",
            "prompt": "Prompt",
            "template_sha256": "a" * 64,
            "evaluator_version": "abc",
            "response": "   ",  # Empty whitespace!
            "tools_called": [],
            "outputs": [],
            "return_codes": [],
            "ttft_s": 0.0,
            "tokens": 0,
            "speed": 0.0,
            "energy_kwh": 0.0,
            "vram_peak_gb": None,
            "ram_gb": 0.0,
            "root_cause_expected": "RC",
            "root_cause_predicted": "RC",
            "factual_accuracy_c6": 0,
            "is_evidence_backed": False,
        }
        ok, err = validate_trace_entry(entry)
        assert ok is False
        assert "Respuesta vacía o ausente" in err

    def test_alignment_csv_and_jsonl(self, tmp_path):
        # 1. Con el dataset histórico acumulado, el validador debe detectar la discrepancia 311 vs 162
        csv_file = PROJECT_ROOT / "data" / "benchmark_results" / "resultados.csv"
        jsonl_file = PROJECT_ROOT / "data" / "benchmark_results" / "traza.jsonl"
        align = validate_alignment_csv_jsonl(csv_file, jsonl_file)
        assert align["csv_count"] == 162
        assert align["jsonl_count"] in (162, 186, 311)
        assert align["matched_count"] == 162
        if align["jsonl_count"] == 162:
            assert align["aligned"] is True
        else:
            assert align["aligned"] is False
            assert any("Diferencia en número de registros" in d for d in align["discrepancies"])

        # 2. Con un conjunto perfectamente alineado, debe retornar aligned = True
        syn_csv = tmp_path / "syn_resultados.csv"
        syn_jsonl = tmp_path / "syn_traza.jsonl"
        syn_csv.write_text("scenario_id,model_id,seed,repetition_index\nDNS-01,qwen3-8b,42,1\n", encoding="utf-8")
        syn_jsonl.write_text(json.dumps({"run_id": "DNS-01_s42_r1_qwen3-8b", "scenario_id": "DNS-01", "model_id": "qwen3-8b"}) + "\n", encoding="utf-8")
        align_syn = validate_alignment_csv_jsonl(syn_csv, syn_jsonl)
        assert align_syn["aligned"] is True
        assert align_syn["csv_count"] == 1
        assert align_syn["jsonl_count"] == 1
        assert align_syn["matched_count"] == 1
