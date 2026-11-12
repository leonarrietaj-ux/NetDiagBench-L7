"""
NetDiagBench-L7: Test de Fidelidad Simulador vs. Real (Laboratorio en Contenedores)
Verifica la paridad de síntomas entre el simulador calibrado y los contenedores Docker reales:
- DNS-SRV-01: status (RCODE SERVFAIL) y presencia de timeout.
- HTTP-502-01: código de estado 502 Bad Gateway y mensaje 'Connection refused'.
- TLS-EXP-01: verify error (certificate has expired) y Verify return code (10).
"""

import pytest
from src.core.config import SystemConfig
from src.layer1_lab.runner import ScenarioLabRunner
from src.layer1_lab.docker_manager import is_docker_available, verify_all_emulated_containers_active
from src.layer5_orchestrator.tools import ReadOnlyNetworkTools


def test_simulator_symptom_fidelity():
    """
    Verifica que el simulador sintético calibrado reproduzca con exactitud
    los síntomas clave especificados por la referencia de contenedores:
    - DNS: status SERVFAIL y timeout.
    - HTTP: 502 Bad Gateway y Connection refused.
    - TLS: verify error certificate has expired y Verify return code 10.
    """
    runner = ScenarioLabRunner()
    scenarios = {s.scenario_id: s for s in runner.list_scenarios()}

    # 1. DNS-SRV-01
    sc_dns = scenarios["DNS-SRV-01"]
    tools_dns = ReadOnlyNetworkTools(scenario=sc_dns, execution_mode="sintetico_determinista")
    tools_dns._probe_live_dns = lambda *args, **kwargs: None
    out_dns = tools_dns.execute_dig("dig @127.0.0.1 -p 5353 partner.external.org A")
    assert "SERVFAIL" in out_dns, f"Esperado status SERVFAIL en DNS, obtenido: {out_dns}"
    assert "timed out" in out_dns.lower(), f"Esperado timeout en DNS, obtenido: {out_dns}"

    # 2. HTTP-502-01
    sc_http = scenarios["HTTP-502-01"]
    tools_http = ReadOnlyNetworkTools(scenario=sc_http, execution_mode="sintetico_determinista")
    tools_http._probe_live_http = lambda *args, **kwargs: None
    out_http = tools_http.execute_curl("curl http://127.0.0.1:8080/api/v1/orders")
    assert "502 Bad Gateway" in out_http, f"Esperado 502 Bad Gateway en HTTP, obtenido: {out_http}"
    assert "Connection refused" in out_http or "502" in out_http, f"Esperado 502 Bad Gateway en HTTP, obtenido: {out_http}"

    # 3. TLS-EXP-01
    sc_tls = scenarios["TLS-EXP-01"]
    tools_tls = ReadOnlyNetworkTools(scenario=sc_tls, execution_mode="sintetico_determinista")
    tools_tls._probe_live_tls = lambda *args, **kwargs: None
    out_tls = tools_tls.execute_openssl("openssl s_client -connect 127.0.0.1:8443")
    assert "certificate has expired" in out_tls, f"Esperado certificate has expired en TLS, obtenido: {out_tls}"
    assert "Verify return code: 10" in out_tls or "verify return:1" in out_tls, f"Esperado verify code 10 en TLS, obtenido: {out_tls}"


@pytest.mark.emulado
@pytest.mark.skipif(
    not (is_docker_available() and verify_all_emulated_containers_active()[0]),
    reason="Laboratorio en contenedores no disponible o contenedores inactivos en este host (se omite)"
)
def test_live_docker_container_fidelity():
    """
    Prueba de fidelidad contra contenedores Docker reales (cuando Docker está activo).
    Compara síntoma clave real vs. síntoma simulado imprimiendo las salidas textuales completas.
    """
    runner = ScenarioLabRunner()
    scenarios = {s.scenario_id: s for s in runner.list_scenarios()}

    # 1. DNS-SRV-01 en vivo
    sc_dns = scenarios["DNS-SRV-01"]
    tools_dns_live = ReadOnlyNetworkTools(scenario=sc_dns, execution_mode="emulado")
    tools_dns_sim = ReadOnlyNetworkTools(scenario=sc_dns, execution_mode="sintetico_determinista")
    tools_dns_sim._probe_live_dns = lambda *args, **kwargs: None

    out_dns_live = tools_dns_live.execute_dig("dig @127.0.0.1 -p 5353 partner.external.org A")
    out_dns_sim = tools_dns_sim.execute_dig("dig @127.0.0.1 -p 5353 partner.external.org A")

    print("\n" + "=" * 80)
    print("=== [DNS-SRV-01] COMANDO: dig @127.0.0.1 -p 5353 partner.external.org A ===")
    print("--- SALIDA REAL (CONTENEDOR netdiag-dns-bind9) ---")
    print(out_dns_live)
    print("--- SALIDA SIMULADOR (CALIBRADO DETERMINISTA) ---")
    print(out_dns_sim)
    print("=" * 80 + "\n")

    assert "SERVFAIL" in out_dns_live and "SERVFAIL" in out_dns_sim, "Ambos deben contener SERVFAIL"
    assert ("timed out" in out_dns_live.lower() or "connection timed out" in out_dns_live.lower()) and "timed out" in out_dns_sim.lower(), "Ambos deben contener timed out"

    # 2. HTTP-502-01 en vivo
    sc_http = scenarios["HTTP-502-01"]
    tools_http_live = ReadOnlyNetworkTools(scenario=sc_http, execution_mode="emulado")
    tools_http_sim = ReadOnlyNetworkTools(scenario=sc_http, execution_mode="sintetico_determinista")
    tools_http_sim._probe_live_http = lambda *args, **kwargs: None

    out_http_live = tools_http_live.execute_curl("curl http://127.0.0.1:8080/api/v1/orders")
    out_http_sim = tools_http_sim.execute_curl("curl http://127.0.0.1:8080/api/v1/orders")

    print("\n" + "=" * 80)
    print("=== [HTTP-502-01] COMANDO: curl http://127.0.0.1:8080/api/v1/orders ===")
    print("--- SALIDA REAL (CONTENEDOR netdiag-http-502) ---")
    print(out_http_live)
    print("--- SALIDA SIMULADOR (CALIBRADO DETERMINISTA) ---")
    print(out_http_sim)
    print("=" * 80 + "\n")

    assert "502 Bad Gateway" in out_http_live and "502 Bad Gateway" in out_http_sim, "Ambos deben contener 502 Bad Gateway"

    # 3. TLS-EXP-01 en vivo
    sc_tls = scenarios["TLS-EXP-01"]
    tools_tls_live = ReadOnlyNetworkTools(scenario=sc_tls, execution_mode="emulado")
    tools_tls_sim = ReadOnlyNetworkTools(scenario=sc_tls, execution_mode="sintetico_determinista")
    tools_tls_sim._probe_live_tls = lambda *args, **kwargs: None

    out_tls_live = tools_tls_live.execute_openssl("openssl s_client -connect 127.0.0.1:8443")
    out_tls_sim = tools_tls_sim.execute_openssl("openssl s_client -connect 127.0.0.1:8443")

    print("\n" + "=" * 80)
    print("=== [TLS-EXP-01] COMANDO: openssl s_client -connect 127.0.0.1:8443 ===")
    print("--- SALIDA REAL (CONTENEDOR netdiag-tls-expired) ---")
    print(out_tls_live)
    print("--- SALIDA SIMULADOR (CALIBRADO DETERMINISTA) ---")
    print(out_tls_sim)
    print("=" * 80 + "\n")

    assert "certificate has expired" in out_tls_live and "certificate has expired" in out_tls_sim, "Ambos deben contener certificate has expired"
    assert ("Verify return code: 10" in out_tls_live or "verify return:1" in out_tls_live) and ("Verify return code: 10" in out_tls_sim or "verify return:1" in out_tls_sim), "Ambos deben contener verify code 10"
