"""
Unit Tests for NetDiagBench-L7 Contracts and Configurations
"""

from pathlib import Path

import yaml

from src.core.config import SystemConfig
from src.core.contracts import (
    DiagnosticoFinalContract,
    EscenarioLabContract,
    FaultClass,
    GroundTruth,
    ServiceCategory,
)


def test_escenario_contract_serialization():
    gt = GroundTruth(
        root_cause="Missing DNS A record",
        affected_component="bind9",
        suggested_action="Add A record in zone file",
        minimum_required_evidence=["dig @127.0.0.1 app.internal -> NXDOMAIN"]
    )
    escenario = EscenarioLabContract(
        scenario_id="DNS-TEST-01",
        category=ServiceCategory.DNS,
        fault_class=FaultClass.NXDOMAIN,
        description="Test DNS failure",
        topology_file="scenarios/topologies/dns_bind9/clab-dns.clab.yml",
        ground_truth=gt
    )
    data = escenario.model_dump()
    assert data["scenario_id"] == "DNS-TEST-01"
    assert data["category"] == "DNS"
    assert data["ground_truth"]["affected_component"] == "bind9"


def test_parsed_catalog_files():
    catalog_dir = Path("scenarios/catalog")
    yaml_files = list(catalog_dir.glob("**/*.yaml"))
    assert len(yaml_files) >= 2, "Debe haber al menos 2 escenarios definidos en el catálogo"
    for yf in yaml_files:
        with open(yf, "r", encoding="utf-8") as f:
            content = yaml.safe_load(f)
        esc = EscenarioLabContract(**content)
        assert esc.scenario_id is not None
        assert esc.ground_truth.root_cause != ""


def test_config_loader():
    sys_config = SystemConfig()
    assert sys_config.hardware.vram_gb == 8.0
    assert len(sys_config.models) == 3
    model_ids = [m.id for m in sys_config.models]
    assert "qwen3-8b" in model_ids
    assert "glm-4-9b-chat" in model_ids
    assert "phi-4-mini-instruct" in model_ids
    assert sys_config.benchmark.temperature == 0.0
    assert sys_config.benchmark.repetitions_per_scenario == 3
    assert sys_config.benchmark.rag_max_memory_gb == 0.45


def test_diagnostico_contract():
    diag = DiagnosticoFinalContract(
        scenario_id="HTTP-502-01",
        model_id="qwen3-8b",
        root_cause="Upstream connection refused",
        affected_component="backend-fastapi",
        suggested_action="Restart backend service",
        natural_language_explanation="The gateway received TCP RST from upstream port 8080.",
        supporting_evidence=["curl -I http://localhost:80 -> 502 Bad Gateway"],
        is_evidence_backed=True
    )
    assert diag.is_evidence_backed is True
    assert len(diag.supporting_evidence) == 1


def test_telemetria_inferencia_contract_validation():
    from src.core.contracts import TelemetriaInferencia
    t = TelemetriaInferencia(
        time_to_first_token_ms=142.5,
        decode_tokens_per_second=39.8,
        total_latency_ms=4200.0,
        prompt_tokens=512,
        completion_tokens=180,
        vram_peak_gb=2.8,
        gpu_utilization_percent=85.0
    )
    assert t.time_to_first_token_ms == 142.5
    assert t.decode_tokens_per_second == 39.8
    assert t.prompt_tokens + t.completion_tokens == 692
    assert t.vram_peak_gb == 2.8


def test_resultado_evaluacion_contract_json_roundtrip():
    from src.core.contracts import ResultadoEvaluacionContract
    r = ResultadoEvaluacionContract(
        scenario_id="DNS-NXD-01",
        model_id="phi-4-mini-instruct",
        seed=42,
        repetition_index=1,
        category="DNS",
        fault_class="NXDOMAIN",
        is_root_cause_correct=True,
        is_component_correct=True,
        partial_match_score=1.0,
        evidence_backed=True,
        ttft_ms=138.5,
        tokens_per_sec=42.1,
        total_time_ms=3950.0,
        tool_steps_count=1,
        cpu_percent_avg=35.5,
        peak_ram_mb=68.2,
        peak_vram_gb=2.8,
        energy_kwh=0.00015,
        co2_emissions_kg=0.000042,
        rubric_score=5.0,
        host_hardware_fingerprint="TEST_HOST_AMD64"
    )
    json_str = r.model_dump_json()
    assert "DNS-NXD-01" in json_str
    reconstructed = ResultadoEvaluacionContract.model_validate_json(json_str)
    assert reconstructed.scenario_id == r.scenario_id
    assert reconstructed.ttft_ms == r.ttft_ms
    assert reconstructed.is_root_cause_correct is True
    assert hasattr(reconstructed, "is_full_diagnosis_correct")


def test_service_categories_and_fault_classes_completeness():
    expected_faults = [
        "NXDOMAIN", "SERVFAIL", "DELEGATION_ERROR",
        "DNS_REFUSED", "DNS_TRUNCATED_EDNS",
        "HTTP_502_BAD_GATEWAY", "HTTP_504_GATEWAY_TIMEOUT", "HTTP_500_INTERNAL",
        "HTTP_403_FORBIDDEN", "HTTP_429_RATE_LIMITED", "HTTP_503_SERVICE_UNAVAILABLE",
        "TLS_EXPIRED_CERT", "TLS_CHAIN_INVALID",
        "TLS_SNI_MISMATCH", "TLS_CIPHER_MISMATCH",
        "ORIGIN_DOWN", "CONNECTION_POOL_EXHAUSTED", "NETWORK_LATENCY_TC"
    ]
    all_fault_values = [fc.value for fc in FaultClass]
    for ef in expected_faults:
        assert ef in all_fault_values

    expected_categories = ["DNS", "HTTP_WEB", "API_GATEWAY", "TLS"]
    all_cat_values = [sc.value for sc in ServiceCategory]
    for ec in expected_categories:
        assert ec in all_cat_values


def test_traza_orquestacion_step_contract():
    from src.core.contracts import ToolExecutionStep, TrazaOrquestacionContract
    step = ToolExecutionStep(
        step_number=1,
        tool_name="dig",
        command_executed="dig @127.0.0.1 -p 5353 app.internal.corp A",
        output_received="status: NXDOMAIN",
        reasoning="Verificar si el registro existe en el servidor autoritativo",
        hypothesis_tested="Registro A ausente en zona BIND9"
    )
    traza = TrazaOrquestacionContract(
        session_id="test-session-01",
        scenario_id="DNS-NXD-01",
        model_id="qwen3-8b",
        seed=42,
        steps=[step],
        final_decision_reached=True,
        iterations_count=1
    )
    assert len(traza.steps) == 1
    assert traza.steps[0].tool_name == "dig"
    assert traza.final_decision_reached is True


def test_contexto_rag_contract_footprint():
    from src.core.contracts import ContextoRAGContract, RAGDocumentChunk
    chunk = RAGDocumentChunk(
        source_document="RFC_1035.md",
        section="Section 4.1.1 RCODE",
        content="RCODE 3 represents Name Error (NXDOMAIN)",
        similarity_score=0.95
    )
    ctx = ContextoRAGContract(
        query="error NXDOMAIN dns",
        chunks=[chunk],
        formatted_markdown="### RFC 1035\nRCODE 3 represents Name Error",
        memory_footprint_mb=0.02
    )
    assert len(ctx.chunks) == 1
    assert ctx.memory_footprint_mb < 450.0  # Must be strictly under 0.45 GB

