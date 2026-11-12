"""
Pruebas de resiliencia para generadores de reportes y agregación estadística.
Valida el comportamiento ante listas vacías, registros incompletos, valores nulos y casos de borde.
"""

import math
import pytest
from pathlib import Path
from typing import Any

from src.layer7_evaluator.statistical_analysis import (
    build_aggregated_results,
    build_comparative_summary,
    load_benchmark_csv,
)
from src.layer7_evaluator.report_generator import generate_html_benchmark_report


def test_build_aggregated_results_empty_list():
    """Valida que una lista vacía retorne el esquema esperado sin división por cero."""
    res = build_aggregated_results([])
    assert isinstance(res, dict)
    assert res["full_diagnosis_accuracy_all_models"] == 0.0
    assert res["strict_root_cause_accuracy_all_models"] == 0.0
    assert res["fault_class_accuracy_all_models"] == 0.0
    assert res["evidence_backed_accuracy_all_models"] == 0.0
    assert res["root_cause_accuracy_all_models"] == 0.0
    assert res["evidence_backing_rate_all_models"] == 0.0
    assert res["f1_macro_all_models"] == 0.0
    assert res["partial_f1_score_all_models"] == 0.0
    assert res["rubric_score_all_models"] == 0.0
    assert res["per_model_summary"] == {}


def test_build_aggregated_results_nan_and_missing_values(tmp_path: Path):
    """Valida la resiliencia ante valores NaN, None o campos faltantes."""
    sample_rows = [
        {
            "model_id": "qwen3-8b",
            "scenario_id": "esc_dns_01",
            "category": "DNS",
            "fault_class": "dns_nxdomain_flood",
            "fault_class_predicted": "dns_nxdomain_flood",
            "fault_class_match": True,
            "is_full_diagnosis_correct": True,
            "is_root_cause_correct": True,
            "is_root_cause_correct_strict": True,
            "is_root_cause_correct_full_text": True,
            "is_component_correct": True,
            "evidence_backed": True,
            "partial_match_score": 1.0,
            "ttft_ms": 120.0,
            "tokens_per_sec": 35.0,
            "total_time_ms": 850.0,
            "peak_vram_gb": None,  # VRAM no disponible
            "energy_kwh": 0.0001,
            "co2_emissions_kg": 0.00005,
            "rubric_score": 4.5,
        },
        {
            "model_id": "qwen3-8b",
            "scenario_id": "esc_tls_01",
            "category": "TLS",
            "fault_class": "tls_cert_expired",
            "fault_class_predicted": "UNKNOWN",
            "fault_class_match": False,
            "is_full_diagnosis_correct": False,
            "is_root_cause_correct": False,
            "is_root_cause_correct_strict": False,
            "is_root_cause_correct_full_text": False,
            "is_component_correct": False,
            "evidence_backed": False,
            "partial_match_score": 0.0,
            "ttft_ms": 250.0,
            "tokens_per_sec": 22.0,
            "total_time_ms": 1200.0,
            "peak_vram_gb": float("nan"),
            "energy_kwh": 0.00015,
            "co2_emissions_kg": 0.00007,
            "rubric_score": 2.0,
        },
    ]

    agg = build_aggregated_results(sample_rows)
    assert agg["full_diagnosis_accuracy_all_models"] == 0.5
    assert agg["strict_root_cause_accuracy_all_models"] == 0.5
    assert agg["fault_class_accuracy_all_models"] == 0.5
    assert agg["evidence_backed_accuracy_all_models"] == 0.5
    assert "qwen3-8b" in agg["per_model_summary"]
    qwen_summary = agg["per_model_summary"]["qwen3-8b"]
    assert qwen_summary["runs_count"] == 2
    assert qwen_summary["accuracy_pct"] == 50.0


def test_html_report_generator_with_custom_rows(tmp_path: Path):
    """Valida la generación del reporte HTML consolidado con un conjunto controlado de filas."""
    sample_rows = [
        {
            "model_id": "glm-4-9b-chat",
            "scenario_id": "esc_dns_01",
            "category": "DNS",
            "fault_class": "dns_nxdomain_flood",
            "fault_class_predicted": "dns_nxdomain_flood",
            "fault_class_match": True,
            "is_full_diagnosis_correct": True,
            "is_root_cause_correct": True,
            "is_root_cause_correct_strict": True,
            "is_root_cause_correct_full_text": True,
            "is_component_correct": True,
            "evidence_backed": True,
            "partial_match_score": 1.0,
            "ttft_ms": 150.0,
            "tokens_per_sec": 30.0,
            "total_time_ms": 900.0,
            "peak_vram_gb": 5.4,
            "energy_kwh": 0.00012,
            "co2_emissions_kg": 0.00006,
            "rubric_score": 4.5,
            "host_hardware_fingerprint": "TEST-HW-FP",
        }
    ]
    out_file = tmp_path / "test_report.html"
    res_path = generate_html_benchmark_report(
        output_path=out_file,
        rows=sample_rows,
        models=["glm-4-9b-chat"],
    )
    assert res_path.exists()
    content = res_path.read_text(encoding="utf-8")
    assert "Exactitud Diagnóstica Completa" in content
    assert "Causa Raíz Estricta" in content
    assert "glm-4-9b-chat" in content
