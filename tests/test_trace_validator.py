"""
Tests for Phase 3: Trazabilidad y Validación de traza.jsonl (NetDiagBench-L7).
"""

import json
from pathlib import Path

import pytest
from src.core.trace_validator import (
    MANDATORY_TRACE_FIELDS,
    TraceEntryContract,
    calculate_prompt_sha256,
    validate_trace_entry,
    validate_trace_file,
)


@pytest.fixture
def sample_valid_trace_entry():
    prompt = "INCIDENTE DNS-NXD-01\n\nTelemetría de red observada..."
    p_hash = calculate_prompt_sha256(prompt)
    return {
        "run_id": "DNS-NXD-01_s42_r1_qwen3-8b",
        "scenario_id": "DNS-NXD-01",
        "model_id": "qwen3-8b",
        "engine_mode": "deterministic_simulator",
        "execution_mode": "sintetico_determinista",
        "timestamp": "2026-11-05T12:00:00Z",
        "prompt": prompt,
        "template_sha256": p_hash,
        "evaluator_version": "a1b2c3d4e5f6",
        "response": '{"causa_raiz": "Registro inexistente NXDOMAIN", "componente": "bind9-authoritative"}',
        "tools_called": ["dig"],
        "outputs": ["; <<>> DiG 9.18.18 <<>> status: NXDOMAIN"],
        "return_codes": [0],
        "ttft_s": 0.125,
        "tokens": 450,
        "speed": 28.5,
        "energy_kwh": 0.00012,
        "vram_peak_gb": 4.5,
        "ram_gb": 1.2,
        "root_cause_expected": "Registro DNS no existe (NXDOMAIN)",
        "root_cause_predicted": "Registro inexistente NXDOMAIN",
        "factual_accuracy_c6": 2,
        "is_evidence_backed": True,
    }


def test_mandatory_fields_list():
    """Verifica que los 23 campos obligatorios estén contemplados."""
    assert len(MANDATORY_TRACE_FIELDS) == 23
    assert "factual_accuracy_c6" in MANDATORY_TRACE_FIELDS
    assert "template_sha256" in MANDATORY_TRACE_FIELDS
    assert "engine_mode" in MANDATORY_TRACE_FIELDS
    assert "execution_mode" in MANDATORY_TRACE_FIELDS


def test_validate_valid_trace_entry(sample_valid_trace_entry):
    """Verifica que un registro conforme sea aceptado."""
    ok, err = validate_trace_entry(sample_valid_trace_entry)
    assert ok is True
    assert err == ""


def test_validate_missing_field(sample_valid_trace_entry):
    """Verifica el rechazo si falta algún campo obligatorio."""
    del sample_valid_trace_entry["engine_mode"]
    ok, err = validate_trace_entry(sample_valid_trace_entry)
    assert ok is False
    assert "Faltan campos obligatorios" in err


def test_validate_hash_mismatch(sample_valid_trace_entry):
    """Verifica el rechazo si el template_sha256 no coincide con el prompt."""
    sample_valid_trace_entry["template_sha256"] = "invalid_hash_value"
    ok, err = validate_trace_entry(sample_valid_trace_entry, verify_prompt_hash=True)
    assert ok is False
    assert "Discrepancia criptográfica" in err


def test_validate_tools_alignment_mismatch(sample_valid_trace_entry):
    """Verifica que herramientas, salidas y return_codes deban coincidir en número."""
    sample_valid_trace_entry["outputs"].append("segunda salida huérfana")
    ok, err = validate_trace_entry(sample_valid_trace_entry)
    assert ok is False
    assert "Desalineación en longitud de pasos de herramientas" in err


def test_validate_trace_file_lifecycle(tmp_path, sample_valid_trace_entry):
    """Verifica la validación integral de un archivo traza.jsonl."""
    trace_path = tmp_path / "traza.jsonl"
    with open(trace_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(sample_valid_trace_entry) + "\n")

    report = validate_trace_file(trace_path)
    assert report["file_exists"] is True
    assert report["total_lines"] == 1
    assert report["valid_lines"] == 1
    assert report["invalid_lines"] == 0
    assert report["is_valid"] is True
    assert len(report["sha256"]) == 64
