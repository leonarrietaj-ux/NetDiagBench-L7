import urllib.request

import pytest


def _is_server_online() -> bool:
    try:
        req = urllib.request.Request("http://127.0.0.1:8000/", headers={"User-Agent": "pytest"})
        with urllib.request.urlopen(req, timeout=0.8) as resp:
            return resp.status == 200
    except Exception:
        return False


@pytest.mark.skipif(not _is_server_online(), reason="Requiere servidor Uvicorn en vivo en http://127.0.0.1:8000")
def test_integration():
    # 1. Test Index HTML
    resp = urllib.request.urlopen("http://127.0.0.1:8000/")
    html = resp.read().decode("utf-8")
    assert "Visor de Diagnóstico L7" in html
    assert "diagnostico-workspace" in html
    assert "visor-resultados" in html

    # 1.1 Test Ejecutar Endpoint (Inyección HTMX en #visor-resultados)
    req_exec = urllib.request.Request(
        "http://127.0.0.1:8000/api/ejecutar",
        data=b"scenario_id=DNS-NXD-01&model_id=phi-4-mini-instruct&seed=42",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req_exec) as resp_exec:
        html_exec = resp_exec.read().decode("utf-8")
    assert "timelineEventsContainer" in html_exec
    assert 'hx-ext="sse"' in html_exec
    print("[PASS] Index HTML and execution endpoint contain Observability container and HTMX SSE directives.")

    # 2. Test Stream Diagnostico SSE
    req = urllib.request.Request("http://127.0.0.1:8000/stream-diagnostico?scenario_id=DNS-NXD-01&model_id=phi-4-mini-instruct&seed=42")
    with urllib.request.urlopen(req, timeout=60) as sse_stream:
        chunks = []
        while True:
            line = sse_stream.readline()
            if not line:
                break
            chunks.append(line.decode("utf-8"))
            if "stream-complete" in line.decode("utf-8"):
                break

    full_stream = "".join(chunks)
    print(f"[PASS] SSE Stream received {len(full_stream)} characters.")

    assert "ingest_telemetry" in full_stream, "Missing ingest_telemetry"
    assert "retrieve_rfc_standards" in full_stream, "Missing retrieve_rfc_standards"
    assert "formulate_hypothesis" in full_stream, "Missing formulate_hypothesis"
    assert "execute_read_only_tool" in full_stream, "Missing execute_read_only_tool"
    assert "dig @127.0.0.1 -p 5353" in full_stream, "Missing tool command"
    assert "evaluate_evidence" in full_stream, "Missing evaluate_evidence"
    assert "DIAGNÓSTICO FINAL" in full_stream, "Missing final diagnosis"
    assert "Telemetría de Inferencia Computada" in full_stream, "Missing telemetry line in final verdict"
    assert "stream-complete" in full_stream, "Missing stream-complete signal"

    print("[PASS] All LangGraph nodes, terminal evidence, CoT, and OOB metrics verified successfully!")

if __name__ == "__main__":
    test_integration()
