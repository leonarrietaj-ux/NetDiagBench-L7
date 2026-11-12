"""
Pruebas de Seguridad y Guardrails Defensivos (NetDiagBench-L7)
Valida mitigaciones contra SSRF, Inyección de Argumentos, Path Traversal y Cabeceras de Seguridad.
"""

import pytest
from src.layer5_orchestrator.tools import ReadOnlyNetworkTools, SecurityPolicyViolation
from src.layer1_lab.docker_manager import _validate_safe_container_name
from src.layer6_interface.web import _validate_safe_identifier, DiagnoseRequest
from pydantic import ValidationError


def test_ssrf_mitigation_cloud_metadata():
    """Verifica que el orquestador bloquee intentos de SSRF contra metadatos de nube y servicios internos."""
    tools = ReadOnlyNetworkTools()
    
    blocked_commands = [
        "curl http://169.254.169.254/latest/meta-data/",
        "curl http://100.100.100.200/latest/meta-data/",
        "curl http://[fd00:ec2::254]/latest/meta-data/",
        "curl http://metadata.google.internal/computeMetadata/v1/",
        "curl http://metadata.tencentyun.com/meta-data/",
        "curl http://kubernetes.default.svc/api",
        "dig @169.254.169.254 instance-data",
    ]
    
    for cmd in blocked_commands:
        tool_name = cmd.split()[0]
        with pytest.raises(SecurityPolicyViolation, match=r"anti-SSRF"):
            tools._assert_read_only(tool_name, cmd)


def test_container_name_validation():
    """Verifica que identificadores maliciosos o con inyección de argumentos sean rechazados en docker_manager."""
    # Válidos
    assert _validate_safe_container_name("netdiag-dns-bind9") == "netdiag-dns-bind9"
    assert _validate_safe_container_name("netdiag_http_502") == "netdiag_http_502"
    
    # Inválidos / vectores de ataque
    invalid_names = [
        "--filter=name=other",
        "container; rm -rf /",
        "container && id",
        "container|whoami",
        "container name",
        "container\nstop",
        "../container",
    ]
    for inv in invalid_names:
        with pytest.raises(ValueError, match=r"inválido o no seguro"):
            _validate_safe_container_name(inv)


def test_path_traversal_validation():
    """Verifica el bloqueo estricto de secuencias de escape de directorio."""
    assert _validate_safe_identifier("DNS-NXD-01") == "DNS-NXD-01"
    assert _validate_safe_identifier("qwen3-8b") == "qwen3-8b"
    assert _validate_safe_identifier("suite_qwen3-8b_s42_12345") == "suite_qwen3-8b_s42_12345"

    malicious = [
        "../../etc/passwd",
        "..\\..\\windows\\system32",
        "scenario%2e%2e/test",
        "/absolute/path",
        "\\windows\\path",
    ]
    for m in malicious:
        with pytest.raises(Exception):
            _validate_safe_identifier(m)


def test_diagnose_request_schema_validation():
    """Verifica que el schema Pydantic DiagnoseRequest rechace entradas maliciosas o fuera de rango."""
    # Válido
    req = DiagnoseRequest(scenario_id="DNS-NXD-01", model_id="qwen3-8b", seed=42)
    assert req.scenario_id == "DNS-NXD-01"
    
    # Inválidos
    with pytest.raises(ValidationError):
        DiagnoseRequest(scenario_id="bad;cmd", model_id="qwen3-8b", seed=42)
        
    with pytest.raises(ValidationError):
        DiagnoseRequest(scenario_id="DNS-NXD-01", model_id="bad model name", seed=42)
        
    with pytest.raises(ValidationError):
        DiagnoseRequest(scenario_id="DNS-NXD-01", model_id="qwen3-8b", seed=-1)
