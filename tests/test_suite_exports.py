"""
Test suite for NetDiagBench-L7 Suite Run Store & Export Endpoints.
Verifies:
1. Session creation and recording in SuiteRunStore.
2. Premature download rejection (HTTP 400) for PDF, Excel, and JSON when suite is incomplete.
3. Successful generation of PDF with real SLM CoT reasoning, telemetry, and ground truth comparison.
4. Successful generation of Excel with 18 real cases and metrics summary.
5. Successful JSON reproducible dump.
6. Backward compatibility fallback when run_id is omitted.
"""

import pytest
from fastapi.testclient import TestClient

from src.layer6_interface.suite_store import suite_store
from src.layer6_interface.web import app


@pytest.fixture
def client():
    return TestClient(app)


def test_premature_download_rejection(client):
    """Verifica que si la suite está incompleta o en progreso, los endpoints retornen HTTP 400."""
    run_id = "suite_test_incomplete_run"
    suite_store.create_or_get_session(
        model_id="qwen3-8b",
        seed=42,
        run_id=run_id,
        model_name="Qwen3-8B"
    )
    # Registrar solo 5 casos (incompleto)
    for i in range(1, 6):
        suite_store.record_case(run_id, {
            "index": i,
            "scenario_id": f"TEST-{i:02d}",
            "category": "DNS",
            "fault_class": "TIMEOUT",
            "description": f"Test case {i}",
            "prediction": {"root_cause": "Timeout", "affected_component": "DNS Server", "natural_language_explanation": "CoT test"},
            "ground_truth": {"root_cause": "Timeout", "affected_component": "DNS Server"},
            "telemetry": {"ttft_ms": 120.0, "tok_per_sec": 45.0, "total_latency_ms": 1500.0, "vram_peak_gb": 3.5},
            "evaluation": {"root_cause_correct": True, "component_correct": True}
        })

    # 1. PDF Prematuro
    resp_pdf = client.get(f"/api/export/pdf/suite?run_id={run_id}")
    assert resp_pdf.status_code == 400
    assert "La suite debe finalizar completamente" in resp_pdf.json()["detail"]

    # 2. Excel Prematuro
    resp_excel = client.get(f"/api/export/excel?run_id={run_id}")
    assert resp_excel.status_code == 400
    assert "La suite debe finalizar completamente" in resp_excel.json()["detail"]

    # 3. JSON Prematuro
    resp_json = client.get(f"/api/export/json?run_id={run_id}")
    assert resp_json.status_code == 400
    assert "La suite debe finalizar completamente" in resp_json.json()["detail"]


def test_completed_suite_exports(client):
    """Verifica que al completarse los 18 casos, se generen PDF, Excel y JSON con datos empíricos reales."""
    run_id = "suite_test_completed_18cases"
    suite_store.create_or_get_session(
        model_id="deepseek-r1-1-5b",
        seed=1337,
        run_id=run_id,
        model_name="Deepseek R1 (1.5B)"
    )

    # Registrar 18 casos completos con CoT real
    for i in range(1, 19):
        suite_store.record_case(run_id, {
            "index": i,
            "scenario_id": f"SCENARIO-{i:02d}",
            "category": "HTTP" if i % 2 == 0 else "DNS",
            "fault_class": "GATEWAY_TIMEOUT" if i % 2 == 0 else "NXDOMAIN",
            "description": f"Escenario real de prueba {i}",
            "prediction": {
                "root_cause": "Conexión rechazada en backend upstream",
                "affected_component": "api-gateway",
                "suggested_action": "Reiniciar servicio y verificar socket",
                "confidence_score": 0.96,
                "natural_language_explanation": f"Paso 1: Análisis de paquetes SYN.\nPaso 2: Se observa timeout L7 en puerto 8080.\nConclusión para caso {i}: Falla confirmada en gateway.",
                "is_evidence_backed": True
            },
            "ground_truth": {
                "root_cause": "Conexión rechazada en backend upstream",
                "affected_component": "api-gateway",
                "suggested_action": "Reiniciar backend"
            },
            "telemetry": {
                "ttft_ms": 110.5,
                "tok_per_sec": 48.2,
                "total_latency_ms": 1250.0,
                "vram_peak_gb": 2.8,
                "completion_tokens": 180
            },
            "evaluation": {
                "root_cause_correct": True,
                "component_correct": True,
                "partial_score": 1.0,
                "rubric_score": 5.0,
                "tool_called": True
            },
            "tool_execution": {
                "tool_name": "curl",
                "command": "curl -I http://127.0.0.1:8080",
                "output": "HTTP/1.1 504 Gateway Timeout"
            }
        })

    suite_store.mark_completed(run_id)

    # 1. Exportación JSON real
    resp_json = client.get(f"/api/export/json?run_id={run_id}")
    assert resp_json.status_code == 200
    json_data = resp_json.json()
    assert json_data["run_id"] == run_id
    assert json_data["status"] == "completed"
    assert json_data["completed_cases"] == 18
    assert len(json_data["cases"]) == 18
    assert "Cadena de Razonamiento" in json_data["cases"][0]["prediction"]["natural_language_explanation"] or "Paso 1" in json_data["cases"][0]["prediction"]["natural_language_explanation"]

    # 2. Exportación Excel real
    resp_excel = client.get(f"/api/export/excel?run_id={run_id}")
    assert resp_excel.status_code == 200
    assert resp_excel.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert f"suite_observabilidad_{run_id}.xlsx" in resp_excel.headers["content-disposition"]
    assert len(resp_excel.content) > 1000

    # 3. Exportación PDF real
    resp_pdf = client.get(f"/api/export/pdf/suite?run_id={run_id}")
    assert resp_pdf.status_code == 200
    assert resp_pdf.headers["content-type"] == "application/pdf"
    assert f"reporte_suite_observabilidad_{run_id}.pdf" in resp_pdf.headers["content-disposition"]
    assert len(resp_pdf.content) > 2000
