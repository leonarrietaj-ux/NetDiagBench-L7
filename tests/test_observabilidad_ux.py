import urllib.parse
import urllib.request

import pytest


def _is_server_online() -> bool:
    try:
        req = urllib.request.Request("http://127.0.0.1:8000/observabilidad", headers={"User-Agent": "pytest"})
        with urllib.request.urlopen(req, timeout=0.8) as resp:
            return resp.status == 200
    except Exception:
        return False


@pytest.mark.skipif(not _is_server_online(), reason="Requiere servidor Uvicorn en vivo en http://127.0.0.1:8000")
def test_observabilidad_ux():
    # 1. Check HTML
    resp = urllib.request.urlopen("http://127.0.0.1:8000/observabilidad")
    html = resp.read().decode("utf-8")

    assert "Suite Completa L7 (18 Escenarios)" in html, "Missing static 18 scenarios card"
    assert 'id="selScenario"' in html and 'value="ALL"' in html, "Missing ALL hidden input"
    assert '<select id="selScenario"' not in html, "Individual scenario dropdown still exists"
    assert "selSeed" in html, "Missing selSeed dropdown"
    assert '<option value="42"' in html, "Missing seed 42"
    assert '<option value="1337"' in html, "Missing seed 1337"
    assert '<option value="2026"' in html, "Missing seed 2026"
    assert '<option value="custom"' in html, "Missing custom seed option in selSeed"
    assert 'id="txtCustomSeed"' in html, "Missing txtCustomSeed input"
    assert "syncCustomSeed" in html, "Missing syncCustomSeed JS function"
    assert "resetToStandardSeed" in html, "Missing resetToStandardSeed JS function"
    assert "max-h-[520px] overflow-y-auto" in html, "Missing internal scroll container"
    assert "lastCompletedScenarioIndex" in html, "Missing resume tracking in JS"
    assert '>Iniciar<' in html, "Missing Iniciar button text"
    assert "'Reanudar'" in html or '"Reanudar"' in html, "Missing Reanudar button text in JS"
    print("[PASS] /observabilidad HTML validation passed 100%!")

    # 2. Check Resume SSE from start_index=17
    req = urllib.request.Request("http://127.0.0.1:8000/stream-diagnostico?scenario_id=ALL&start_index=17&seed=42")
    with urllib.request.urlopen(req, timeout=60) as sse:
        chunks = []
        while True:
            line = sse.readline().decode("utf-8")
            if not line:
                break
            chunks.append(line)
            if "stream-complete" in line:
                break
        content = "".join(chunks)
        assert "Escenario 18 de 18" in content, "Scenario 18 not emitted"
        assert 'data-suite-finished="true"' in content, "Suite finished banner missing"
        assert "Escenario 1 de 18" not in content, "Should not start from 0 when start_index=17"
    print("[PASS] Resume from index 17 SSE validation passed 100%!")

    # 3. Check start_index >= 18 does not loop
    req2 = urllib.request.Request("http://127.0.0.1:8000/stream-diagnostico?scenario_id=ALL&start_index=18&seed=42")
    with urllib.request.urlopen(req2, timeout=20) as sse2:
        chunks2 = []
        while True:
            line2 = sse2.readline().decode("utf-8")
            if not line2:
                break
            chunks2.append(line2)
            if "stream-complete" in line2:
                break
        content2 = "".join(chunks2)
        assert "Suite de 18 escenarios ya finalizada" in content2, "Did not halt immediately"
        assert "Escenario 1 de 18" not in content2, "Looped when it should halt"
    # 4. Check Scenario 7 synchronization between statusBadge and faultProblemCard
    req3 = urllib.request.Request("http://127.0.0.1:8000/stream-diagnostico?scenario_id=ALL&start_index=6&seed=42")
    with urllib.request.urlopen(req3, timeout=60) as sse3:
        chunks = []
        while True:
            line = sse3.readline().decode("utf-8")
            if not line:
                break
            chunks.append(line)
            if "Escenario 7 de 18 resuelto" in line:
                break
    content3 = "".join(chunks)
    assert "Resolviendo Escenario 7 de 18" in content3, "Missing synchronized statusBadge for Scenario 7"
    assert "RESOLVIENDO: CASO 7 DE 18" in content3, "Missing synchronized faultProblemCard for Scenario 7"
    print("[PASS] Synchronized statusBadge and faultProblemCard validation passed 100%!")

    # 5. Check Custom Seed in /api/execute-suite
    data = urllib.parse.urlencode({"scenario_id": "ALL", "model_id": "qwen3-8b", "seed": "777", "start_index": "0"}).encode("utf-8")
    req_custom = urllib.request.Request("http://127.0.0.1:8000/api/execute-suite", data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req_custom, timeout=10) as resp_c:
        c_html = resp_c.read().decode("utf-8")
        assert "seed=777" in c_html, "Custom seed 777 was not passed to SSE connection URL"
    print("[PASS] Custom Seed 777 passed to SSE stream successfully!")

if __name__ == "__main__":
    test_observabilidad_ux()
