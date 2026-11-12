"""
Pruebas Unitarias para la Capa 1: Laboratorio de Escenarios (NetDiagBench-L7)
"""

from src.core.contracts import FaultClass, ServiceCategory
from src.layer1_lab.runner import ScenarioLabRunner


def test_scenario_lab_runner_loading():
    runner = ScenarioLabRunner()
    scenarios = runner.list_scenarios()
    assert len(scenarios) >= 8, "Debe cargar al menos los 8 escenarios del catálogo"

    ids = [s.scenario_id for s in scenarios]
    assert "DNS-NXD-01" in ids
    assert "DNS-SRV-01" in ids
    assert "DNS-DEL-01" in ids
    assert "HTTP-502-01" in ids
    assert "HTTP-504-01" in ids
    assert "HTTP-500-01" in ids
    assert "TLS-EXP-01" in ids
    assert "HTTP-ORIGIN-01" in ids


def test_scenario_synthetic_logs_generation():
    runner = ScenarioLabRunner()
    sc = runner.get_scenario("DNS-NXD-01")
    assert sc is not None

    logs = runner.generate_synthetic_logs(sc, seed=42, count=10)
    assert len(logs) == 10
    for log in logs:
        assert "timestamp" in log
        assert "source_service" in log
        assert "log_level" in log
        assert "raw_message" in log
        assert log["source_service"] == "bind9"


def test_scenario_execution():
    runner = ScenarioLabRunner()
    sc, logs, telemetry = runner.execute_scenario("HTTP-502-01", seed=1337)
    assert sc.scenario_id == "HTTP-502-01"
    assert sc.category == ServiceCategory.API_GATEWAY
    assert sc.fault_class == FaultClass.HTTP_502_BAD_GATEWAY
    assert len(logs) > 0
    assert "error_rate_pct" in telemetry
    assert telemetry["error_rate_pct"] > 50.0


def test_all_18_scenarios_exist_and_ground_truth_valid():
    runner = ScenarioLabRunner()
    expected_18 = [
        "DNS-NXD-01", "DNS-SRV-01", "DNS-DEL-01", "DNS-REF-01", "DNS-TRUNC-01",
        "HTTP-502-01", "HTTP-504-01", "HTTP-500-01", "HTTP-403-01", "HTTP-429-01", "HTTP-503-01",
        "HTTP-ORIGIN-01", "HTTP-POOL-01", "NET-LAT-01",
        "TLS-EXP-01", "TLS-CHN-01", "TLS-SNI-01", "TLS-CIPH-01"
    ]
    assert len(runner.list_scenarios()) == 18
    for sc_id in expected_18:
        sc = runner.get_scenario(sc_id)
        assert sc is not None, f"Escenario {sc_id} debe existir en el catálogo"
        assert len(sc.ground_truth.root_cause) > 5
        assert len(sc.ground_truth.affected_component) > 2
        assert len(sc.ground_truth.suggested_action) > 5
        assert len(sc.ground_truth.minimum_required_evidence) >= 1


def test_log_generation_determinism_across_seeds():
    runner = ScenarioLabRunner()
    sc = runner.get_scenario("DNS-NXD-01")
    logs_seed_a = runner.generate_synthetic_logs(sc, seed=42, count=12)
    logs_seed_b = runner.generate_synthetic_logs(sc, seed=42, count=12)
    logs_seed_diff = runner.generate_synthetic_logs(sc, seed=2026, count=12)

    # Identical seed must yield identical logs
    assert logs_seed_a == logs_seed_b

    # Different seeds must yield different log selections
    msgs_a = [log_item["raw_message"] for log_item in logs_seed_a]
    msgs_diff = [log_item["raw_message"] for log_item in logs_seed_diff]
    assert msgs_a != msgs_diff


def test_tls_scenario_log_patterns():
    runner = ScenarioLabRunner()
    sc_exp = runner.get_scenario("TLS-EXP-01")
    sc_chn = runner.get_scenario("TLS-CHN-01")

    logs_exp = runner.generate_synthetic_logs(sc_exp, seed=42, count=10)
    logs_chn = runner.generate_synthetic_logs(sc_chn, seed=42, count=10)

    # Must contain TLS/SSL failure indicators
    exp_text = " ".join(log_item["raw_message"] for log_item in logs_exp)
    chn_text = " ".join(log_item["raw_message"] for log_item in logs_chn)
    assert "TLS" in exp_text or "certificate" in exp_text.lower() or "SSL" in exp_text
    assert "TLS" in chn_text or "intermediate" in chn_text.lower() or "ca" in chn_text.lower()


def test_network_latency_scenario_telemetry():
    runner = ScenarioLabRunner()
    sc, logs, tel = runner.execute_scenario("NET-LAT-01", seed=42)
    assert sc.scenario_id == "NET-LAT-01"
    assert "p95_latency_ms" in tel
    assert tel["p95_latency_ms"] >= 100.0  # Simulated high latency degradation


def test_expanded_scenarios_logs_and_telemetry():
    runner = ScenarioLabRunner()
    expanded_ids = [
        "DNS-REF-01", "DNS-TRUNC-01",
        "HTTP-403-01", "HTTP-429-01", "HTTP-503-01",
        "TLS-SNI-01", "TLS-CIPH-01"
    ]
    for sc_id in expanded_ids:
        sc, logs, tel = runner.execute_scenario(sc_id, seed=42)
        assert sc.scenario_id == sc_id
        assert len(logs) >= 5
        assert "error_rate_pct" in tel
        assert "p50_latency_ms" in tel
        assert "p95_latency_ms" in tel
        assert tel["error_rate_pct"] > 0


def test_dns_refused_and_truncation_patterns():
    runner = ScenarioLabRunner()
    sc_ref = runner.get_scenario("DNS-REF-01")
    sc_tru = runner.get_scenario("DNS-TRUNC-01")

    logs_ref = runner.generate_synthetic_logs(sc_ref, seed=42, count=10)
    logs_tru = runner.generate_synthetic_logs(sc_tru, seed=42, count=10)

    text_ref = " ".join(item["raw_message"] for item in logs_ref)
    text_tru = " ".join(item["raw_message"] for item in logs_tru)

    assert "REFUSED" in text_ref or "denied" in text_ref
    assert "TC flag" in text_tru or "TCP" in text_tru or "truncated" in text_tru


def test_http_403_and_429_patterns():
    runner = ScenarioLabRunner()
    sc_403 = runner.get_scenario("HTTP-403-01")
    sc_429 = runner.get_scenario("HTTP-429-01")

    logs_403 = runner.generate_synthetic_logs(sc_403, seed=42, count=10)
    logs_429 = runner.generate_synthetic_logs(sc_429, seed=42, count=10)

    text_403 = " ".join(item["raw_message"] for item in logs_403)
    text_429 = " ".join(item["raw_message"] for item in logs_429)

    assert "403" in text_403 or "forbidden" in text_403.lower()
    assert "429" in text_429 or "rate" in text_429.lower() or "limit" in text_429.lower()


def test_http_503_worker_exhaustion_patterns():
    runner = ScenarioLabRunner()
    sc_503 = runner.get_scenario("HTTP-503-01")
    logs_503 = runner.generate_synthetic_logs(sc_503, seed=42, count=10)
    text_503 = " ".join(item["raw_message"] for item in logs_503)

    assert "503" in text_503 or "unavailable" in text_503.lower() or "worker" in text_503.lower()


def test_tls_sni_and_cipher_mismatch_patterns():
    runner = ScenarioLabRunner()
    sc_sni = runner.get_scenario("TLS-SNI-01")
    sc_ciph = runner.get_scenario("TLS-CIPH-01")

    logs_sni = runner.generate_synthetic_logs(sc_sni, seed=42, count=10)
    logs_ciph = runner.generate_synthetic_logs(sc_ciph, seed=42, count=10)

    text_sni = " ".join(item["raw_message"] for item in logs_sni)
    text_ciph = " ".join(item["raw_message"] for item in logs_ciph)

    assert "SNI" in text_sni or "mismatch" in text_sni.lower() or "certificate" in text_sni.lower()
    assert "handshake" in text_ciph.lower() or "cipher" in text_ciph.lower() or "SSL" in text_ciph




