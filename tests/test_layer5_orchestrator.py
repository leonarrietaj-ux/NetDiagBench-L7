import pytest
"""
Pruebas Unitarias para la Capa 5: Orquestación y Herramientas Read-Only (NetDiagBench-L7)
"""

from src.core.contracts import DiagnosticoFinalContract, TrazaOrquestacionContract
from src.layer1_lab.runner import ScenarioLabRunner
from src.layer2_pipeline.aggregator import DataPipelineAgent
from src.layer3_rag.retriever import RAGKnowledgeEngine
from src.layer4_inference.engine import LocalInferenceEngine
from src.layer5_orchestrator.agent import DiagnosticOrchestratorAgent
from src.layer5_orchestrator.tools import ReadOnlyNetworkTools


def test_readonly_tools_dispatch():
    lab = ScenarioLabRunner()
    sc = lab.get_scenario("DNS-NXD-01")
    tools = ReadOnlyNetworkTools(scenario=sc)

    # dig de solo lectura
    success, out = tools.dispatch("dig", "dig @127.0.0.1 -p 5353 app.internal.corp A")
    assert success is True
    assert "NXDOMAIN" in out

    # curl de solo lectura
    sc_http = lab.get_scenario("HTTP-502-01")
    tools_http = ReadOnlyNetworkTools(scenario=sc_http)
    success, out = tools_http.dispatch("curl", "curl -I -s http://127.0.0.1:80/api/v1/users")
    assert success is True
    assert "502 Bad Gateway" in out


def test_readonly_tools_security_guardrails():
    tools = ReadOnlyNetworkTools()
    # Intento de mutación o comando no permitido
    success, out = tools.dispatch("curl", "curl http://test.com; rm -rf /")
    assert success is False
    assert "SECURITY_ERROR" in out


def test_diagnostic_orchestrator_execution():
    lab = ScenarioLabRunner()
    sc, logs, tel = lab.execute_scenario("HTTP-502-01", seed=42)
    pipe = DataPipelineAgent()
    ventana = pipe.process_window(sc, logs, tel)
    rag = RAGKnowledgeEngine()
    contexto = rag.query(sc.description)

    engine = LocalInferenceEngine(force_simulation=True)
    orch = DiagnosticOrchestratorAgent(inference_engine=engine)

    traza, diag, inf = orch.run_diagnosis(sc, ventana, contexto, model_id="qwen3-8b", seed=42)
    assert isinstance(traza, TrazaOrquestacionContract)
    assert isinstance(diag, DiagnosticoFinalContract)
    assert diag.scenario_id == "HTTP-502-01"
    assert diag.is_evidence_backed is True
    assert len(traza.steps) > 0


def test_readonly_tools_openssl_dispatch():
    lab = ScenarioLabRunner()
    sc = lab.get_scenario("TLS-EXP-01")
    tools = ReadOnlyNetworkTools(scenario=sc)
    success, out = tools.dispatch("openssl", "openssl s_client -connect 127.0.0.1:443 -servername secure.corp.internal")
    assert success is True
    assert "certificate has expired" in out or "verify error" in out


def test_readonly_tools_blocked_mutating_commands():
    tools = ReadOnlyNetworkTools()
    dangerous = [
        "curl http://127.0.0.1 && systemctl restart nginx",
        "dig @127.0.0.1 test.com | iptables -F",
        "openssl s_client -connect 127.0.0.1:443 & reboot",
        "curl http://127.0.0.1 `kill -9 1`",
        "curl http://test.com > /etc/resolv.conf",
    ]
    for cmd in dangerous:
        success, out = tools.dispatch("curl" if "curl" in cmd else ("dig" if "dig" in cmd else "openssl"), cmd)
        assert success is False
        assert "SECURITY_ERROR" in out


def test_readonly_tools_unregistered_tool():
    tools = ReadOnlyNetworkTools()
    success, out = tools.dispatch("nmap", "nmap -sS 127.0.0.1")
    assert success is False
    assert "TOOL_NOT_SUPPORTED" in out or "no soportada" in out.lower()


def test_orchestrator_all_models_produce_valid_diagnosis():
    lab = ScenarioLabRunner()
    sc, logs, tel = lab.execute_scenario("DNS-NXD-01", seed=42)
    pipe = DataPipelineAgent()
    ventana = pipe.process_window(sc, logs, tel)
    rag = RAGKnowledgeEngine()
    contexto = rag.query(sc.description)

    engine = LocalInferenceEngine(force_simulation=True)
    orch = DiagnosticOrchestratorAgent(inference_engine=engine)

    for m in ["qwen3-8b", "glm-4-9b-chat", "phi-4-mini-instruct"]:
        traza, diag, inf = orch.run_diagnosis(sc, ventana, contexto, model_id=m, seed=42)
        assert diag.scenario_id == "DNS-NXD-01"
        assert diag.model_id == m
        assert diag.is_evidence_backed is True
        assert len(diag.root_cause) > 5


def test_orchestrator_step_count_bounded():
    lab = ScenarioLabRunner()
    sc, logs, tel = lab.execute_scenario("HTTP-502-01", seed=42)
    pipe = DataPipelineAgent()
    ventana = pipe.process_window(sc, logs, tel)
    rag = RAGKnowledgeEngine()
    contexto = rag.query(sc.description)

    engine = LocalInferenceEngine(force_simulation=True)
    orch = DiagnosticOrchestratorAgent(inference_engine=engine, max_steps=3)
    traza, diag, inf = orch.run_diagnosis(sc, ventana, contexto, model_id="phi-4-mini-instruct", seed=42)

    assert len(traza.steps) <= 3
    assert traza.final_decision_reached is True


def test_readonly_tools_expanded_scenarios_dispatch():
    lab = ScenarioLabRunner()

    # DNS Refused
    sc = lab.get_scenario("DNS-REF-01")
    tools = ReadOnlyNetworkTools(scenario=sc)
    ok, out = tools.dispatch("dig", "dig @127.0.0.1 -p 5353 restricted.corp.internal A")
    assert ok and "REFUSED" in out

    # DNS Truncation
    sc = lab.get_scenario("DNS-TRUNC-01")
    tools = ReadOnlyNetworkTools(scenario=sc)
    ok, out = tools.dispatch("dig", "dig @127.0.0.1 -p 5353 large.corp.internal ANY +bufsize=512 +notcp")
    assert ok and ("tc" in out or "Truncation" in out)

    # HTTP 403
    sc = lab.get_scenario("HTTP-403-01")
    tools = ReadOnlyNetworkTools(scenario=sc)
    ok, out = tools.dispatch("curl", "curl -I -s http://127.0.0.1:80/admin/system/status")
    assert ok and "403 Forbidden" in out

    # HTTP 429
    sc = lab.get_scenario("HTTP-429-01")
    tools = ReadOnlyNetworkTools(scenario=sc)
    ok, out = tools.dispatch("curl", "curl -I -s http://127.0.0.1:80/api/v1/search?q=telecom")
    assert ok and "429 Too Many Requests" in out

    # HTTP 503
    sc = lab.get_scenario("HTTP-503-01")
    tools = ReadOnlyNetworkTools(scenario=sc)
    ok, out = tools.dispatch("curl", "curl -I -s http://127.0.0.1:80/api/v1/orders")
    assert ok and "503 Service Unavailable" in out

    # TLS SNI
    sc = lab.get_scenario("TLS-SNI-01")
    tools = ReadOnlyNetworkTools(scenario=sc)
    ok, out = tools.dispatch("openssl", "openssl s_client -connect 127.0.0.1:443 -servername api-unregistered.corp.internal")
    assert ok and "Hostname mismatch" in out

    # TLS Cipher
    sc = lab.get_scenario("TLS-CIPH-01")
    tools = ReadOnlyNetworkTools(scenario=sc)
    ok, out = tools.dispatch("openssl", "openssl s_client -connect 127.0.0.1:443 -cipher AES128-SHA")
    assert ok and ("handshake failure" in out or "SSL alert number 40" in out)


def test_readonly_tools_advanced_security_whitelisting():
    """Verifica que el nuevo guardrail con lista blanca POSIX bloquee flags de exfiltración, escritura y SSRF."""
    tools = ReadOnlyNetworkTools()

    # 1. Banderas de escritura/exfiltración en curl (-o, -d, -F)
    blocked_curls = [
        "curl -o /tmp/payload.sh http://127.0.0.1:80/malicious",
        "curl --output exploit.bin http://127.0.0.1:80",
        "curl -d @/etc/passwd http://127.0.0.1:80",
        "curl -F file=@secret.txt http://127.0.0.1:80",
        "curl -X POST http://127.0.0.1:80/api/v1/users",
    ]
    for cmd in blocked_curls:
        ok, out = tools.dispatch("curl", cmd)
        assert ok is False
        assert "SECURITY_ERROR" in out

    # 2. Banderas de lectura de archivos arbitrarios en dig (-f)
    ok_dig, out_dig = tools.dispatch("dig", "dig -f /etc/shadow")
    assert ok_dig is False
    assert "SECURITY_ERROR" in out

    # 3. Subcomandos generadores/mutadores en openssl (genrsa, req, enc)
    blocked_openssl = [
        "openssl genrsa -out key.pem 2048",
        "openssl req -new -key key.pem -out csr.pem",
        "openssl enc -aes-256-cbc -in data.txt -out data.enc",
    ]
    for cmd in blocked_openssl:
        ok_ssl, out_ssl = tools.dispatch("openssl", cmd)
        assert ok_ssl is False
        assert "SECURITY_ERROR" in out_ssl

    # 4. Destinos prohibidos por política anti-SSRF (metadatos de nube)
    ok_ssrf, out_ssrf = tools.dispatch("curl", "curl -I -s http://169.254.169.254/latest/meta-data/")
    assert ok_ssrf is False
    assert "SECURITY_ERROR" in out_ssrf
    assert "anti-SSRF" in out_ssrf


def test_parse_final_diagnosis_no_data_leak_on_empty():
    """Verifica que el parser NUNCA autocomplete campos vacíos con el ground truth (Resolución Hallazgo 2.2)."""
    lab = ScenarioLabRunner()
    sc = lab.get_scenario("DNS-NXD-01")
    engine = LocalInferenceEngine(force_simulation=True)
    orch = DiagnosticOrchestratorAgent(inference_engine=engine)

    diag = orch._parse_final_diagnosis(
        scenario=sc,
        model_id="test-model",
        response_text="Respuesta sin diagnóstico estructurado.",
        evidence_list=[]
    )
    # Ningún campo debe haber sido contaminado con el ground truth
    assert diag.root_cause == ""
    assert diag.affected_component == ""
    assert diag.suggested_action == ""
    assert diag.is_evidence_backed is False
    assert diag.confidence_score == 0.0


def test_parse_final_diagnosis_extracts_model_output_strictly():
    """Verifica que el parser extraiga estrictamente lo dicho por el modelo sin reemplazar por ground truth."""
    lab = ScenarioLabRunner()
    sc = lab.get_scenario("HTTP-502-01")
    engine = LocalInferenceEngine(force_simulation=True)
    orch = DiagnosticOrchestratorAgent(inference_engine=engine)

    model_resp = (
        "DIAGNÓSTICO:\n"
        "- Causa Raíz: Servidor de backend apagado o caído por falta de memoria\n"
        "- Componente Afectado: nginx-api-gateway\n"
        "- Acción Sugerida: Reiniciar el servicio de contenedor upstream\n"
    )
    diag = orch._parse_final_diagnosis(
        scenario=sc,
        model_id="qwen3-8b",
        response_text=model_resp,
        evidence_list=["curl -I http://127.0.0.1:80 -> 502 Bad Gateway"]
    )
    assert "Servidor de backend apagado" in diag.root_cause
    assert diag.affected_component == "nginx-api-gateway"
    assert "Reiniciar el servicio" in diag.suggested_action
    assert diag.is_evidence_backed is True


def test_tool_calling_traceability_evidence_backed_only_on_success():
    """Verifica que evidence_backed sea True SOLO si dispatch retorna success=True."""
    lab = ScenarioLabRunner()
    sc = lab.get_scenario("HTTP-502-01")
    tools = ReadOnlyNetworkTools(scenario=sc)

    # Intento inválido / violación de seguridad -> dispatch retorna success=False
    success, out = tools.dispatch("curl", "curl http://test.com; rm -rf /")
    assert success is False

    engine = LocalInferenceEngine(force_simulation=True)
    orch = DiagnosticOrchestratorAgent(inference_engine=engine)
    # Si la lista de evidencias está vacía porque la herramienta falló:
    diag = orch._parse_final_diagnosis(
        scenario=sc,
        model_id="qwen3-8b",
        response_text="Diagnóstico: Error 502",
        evidence_list=[]  # No se añade evidencia si success=False
    )
    assert diag.is_evidence_backed is False


def test_tool_calling_execution_mode_emulated_only_on_real_probe(monkeypatch):
    """Verifica que execution_mode sea 'emulado' solo si el sondeo en vivo responde con éxito."""
    lab = ScenarioLabRunner()
    sc = lab.get_scenario("DNS-NXD-01")
    tools = ReadOnlyNetworkTools(scenario=sc)

    # Caso 1: Sondeo en vivo fallido (servicio caído / timeout) -> fallback sintético
    monkeypatch.setattr(tools, "_probe_live_dns", lambda *args, **kwargs: None)
    success, out = tools.dispatch("dig", "dig @127.0.0.1 -p 5353 missing.lab.corp.internal A")
    assert success is True
    assert tools.live_probe_succeeded is False
    assert tools.execution_mode == "sintetico_determinista"

    # Caso 2: Sondeo en vivo exitoso -> emulado
    monkeypatch.setattr(tools, "_probe_live_dns", lambda *args, **kwargs: ";; status: NXDOMAIN (live)")
    tools_live = ReadOnlyNetworkTools(scenario=sc)
    monkeypatch.setattr(tools_live, "_probe_live_dns", lambda *args, **kwargs: ";; status: NXDOMAIN (live)")
    success_live, out_live = tools_live.dispatch("dig", "dig @127.0.0.1 -p 5353 missing.lab.corp.internal A")
    assert success_live is True
    assert tools_live.live_probe_succeeded is True
    assert tools_live.execution_mode == "emulado"


def test_master_prompt_zero_data_leakage(monkeypatch):
    """Verifica que el prompt NO contenga scenario_id ni scenario.description (Hallazgo C1)."""
    lab = ScenarioLabRunner()
    sc, logs, tel = lab.execute_scenario("HTTP-502-01", seed=42)
    pipe = DataPipelineAgent()
    ventana = pipe.process_window(sc, logs, tel)
    rag = RAGKnowledgeEngine()
    contexto = rag.query("HTTP_WEB error")

    prompts_captured = []
    engine = LocalInferenceEngine(force_simulation=True)
    orig_generate = engine.generate

    def mock_generate(*args, **kwargs):
        prompts_captured.append(kwargs.get("prompt", ""))
        return orig_generate(*args, **kwargs)

    monkeypatch.setattr(engine, "generate", mock_generate)
    orch = DiagnosticOrchestratorAgent(inference_engine=engine)
    orch.run_diagnosis(sc, ventana, contexto, model_id="qwen3-8b", seed=42)

    assert len(prompts_captured) >= 1
    initial_prompt = prompts_captured[0]
    # C1: Ni el ID ni la descripción de ground truth deben estar presentes
    assert sc.scenario_id not in initial_prompt
    assert sc.description not in initial_prompt
    assert "<telemetria_observada>" in initial_prompt


def test_agentic_loop_feedback_to_model(monkeypatch):
    """Verifica que el resultado de la herramienta sea devuelto al modelo para reformulación (Hallazgo A3)."""
    lab = ScenarioLabRunner()
    sc, logs, tel = lab.execute_scenario("HTTP-502-01", seed=42)
    pipe = DataPipelineAgent()
    ventana = pipe.process_window(sc, logs, tel)
    rag = RAGKnowledgeEngine()
    contexto = rag.query("HTTP_WEB error")

    prompts_captured = []
    engine = LocalInferenceEngine(force_simulation=True)
    orig_generate = engine.generate

    def mock_generate(*args, **kwargs):
        prompts_captured.append(kwargs.get("prompt", ""))
        return orig_generate(*args, **kwargs)

    monkeypatch.setattr(engine, "generate", mock_generate)
    orch = DiagnosticOrchestratorAgent(inference_engine=engine)
    traza, diag, inf = orch.run_diagnosis(sc, ventana, contexto, model_id="qwen3-8b", seed=42)

    # Si se ejecutó herramienta, deben haber 2 llamadas de inferencia (Hipótesis -> Verificación -> Síntesis)
    if len(traza.steps) > 0:
        assert len(prompts_captured) == 2
        second_prompt = prompts_captured[1]
        assert "RESULTADO DE VERIFICACIÓN EMPÍRICA" in second_prompt
        assert "INSTRUCCIÓN DE SÍNTESIS FINAL TRAS VERIFICACIÓN" in second_prompt

def test_emulated_mode_aborts_explicitly_when_container_unresponsive(monkeypatch):
    """
    Verifica que en execution_mode='emulado', si el contenedor no responde,
    las herramientas NUNCA caigan silenciosamente al simulador y en su lugar
    aborten con un error explícito (RuntimeError) (Requisito 2).
    """
    runner = ScenarioLabRunner()

    # 1. Probar HTTP-502-01
    sc_http = runner.get_scenario("HTTP-502-01")
    tools_http = ReadOnlyNetworkTools(scenario=sc_http, execution_mode="emulado")
    monkeypatch.setattr(tools_http, "_probe_live_http", lambda url, timeout=3.0: None)
    with pytest.raises(RuntimeError) as exc_http:
        tools_http.dispatch("curl", "curl http://127.0.0.1:8080/api/v1/orders")
    assert "no responde" in str(exc_http.value)
    assert "no se permite fallback" in str(exc_http.value)

    # 2. Probar DNS-SRV-01
    sc_dns = runner.get_scenario("DNS-SRV-01")
    tools_dns = ReadOnlyNetworkTools(scenario=sc_dns, execution_mode="emulado")
    monkeypatch.setattr(tools_dns, "_probe_live_dns", lambda qname, port=5353, timeout=12.0: None)
    with pytest.raises(RuntimeError) as exc_dns:
        tools_dns.dispatch("dig", "dig @127.0.0.1 -p 5353 partner.external.org A")
    assert "no responde" in str(exc_dns.value)
    assert "no se permite fallback" in str(exc_dns.value)

    # 3. Probar TLS-EXP-01
    sc_tls = runner.get_scenario("TLS-EXP-01")
    tools_tls = ReadOnlyNetworkTools(scenario=sc_tls, execution_mode="emulado")
    monkeypatch.setattr(tools_tls, "_probe_live_tls", lambda host="127.0.0.1", port=8443, timeout=3.0: None)
    with pytest.raises(RuntimeError) as exc_tls:
        tools_tls.dispatch("openssl", "openssl s_client -connect 127.0.0.1:8443")
    assert "no responde" in str(exc_tls.value)
    assert "no se permite fallback" in str(exc_tls.value)

