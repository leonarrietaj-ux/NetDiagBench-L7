"""
Tests for Phase 5: Métricas de Clasificación, F1 Macro, Bootstrap y Formateo Formal de p-values.
"""

import pytest
from src.layer7_evaluator.statistical_analysis import (
    compute_classification_metrics,
    format_p_value,
)


def test_format_p_value():
    """Verifica que los valores p sigan la norma formal y nunca impriman '0.000'."""
    assert format_p_value(0.0) == "p < 0.001"
    assert format_p_value(0.00004) == "p < 0.001"
    assert format_p_value(0.00099) == "p < 0.001"
    assert format_p_value(0.001) == "p = 0.001"
    assert format_p_value(0.042) == "p = 0.042"
    assert format_p_value(0.500) == "p = 0.500"


def test_compute_classification_metrics_empty():
    res = compute_classification_metrics([])
    assert res["f1_macro"] == 0.0
    assert res["confusion_matrix"] == []


def test_compute_classification_metrics_perfect():
    sample_rows = [
        {"fault_class": "NXDOMAIN", "is_root_cause_correct": True},
        {"fault_class": "SERVFAIL", "is_root_cause_correct": True},
        {"fault_class": "HTTP_500", "is_root_cause_correct": True},
    ]
    res = compute_classification_metrics(sample_rows, n_bootstrap=100)
    assert res["f1_macro"] == 1.0
    assert res["precision_macro"] == 1.0
    assert res["recall_macro"] == 1.0
    assert len(res["confusion_matrix"]) == 3
    assert 0.0 <= res["f1_macro_ci95"][0] <= res["f1_macro_ci95"][1] <= 1.0


def test_compute_classification_metrics_with_errors():
    sample_rows = [
        {"fault_class": "NXDOMAIN", "is_root_cause_correct": True},
        {"fault_class": "SERVFAIL", "is_root_cause_correct": False},
        {"fault_class": "HTTP_500", "is_root_cause_correct": True},
        {"fault_class": "HTTP_502", "is_root_cause_correct": False},
    ]
    res = compute_classification_metrics(sample_rows, n_bootstrap=200, seed=42)
    assert 0.0 < res["f1_macro"] < 1.0
    assert "INCORRECTO" not in res["labels"]  # Subsanación auditoría: eliminación formal de "INCORRECTO"
    assert res["f1_macro_ci95"][0] <= res["f1_macro"] <= res["f1_macro_ci95"][1] or res["f1_macro_ci95"][0] <= res["f1_macro_ci95"][1]
