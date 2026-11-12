"""
Pruebas Unitarias para la Capa 2: Pipeline de Ingesta y Drain3 (NetDiagBench-L7)
"""

from src.core.contracts import VentanaLogContract
from src.layer1_lab.runner import ScenarioLabRunner
from src.layer2_pipeline.aggregator import DataPipelineAgent
from src.layer2_pipeline.parser import Drain3LogParser


def test_drain3_log_parser_clustering():
    parser = Drain3LogParser()
    raw_logs = [
        {"raw_message": "client 127.0.0.1#49152: query: foo.corp IN A + (127.0.0.1)", "timestamp": "2026-09-25 10:00:00", "source_service": "bind9"},
        {"raw_message": "client 127.0.0.1#49153: query: bar.corp IN A + (127.0.0.1)", "timestamp": "2026-09-25 10:00:01", "source_service": "bind9"},
    ]
    parsed = parser.parse_batch(raw_logs)
    assert len(parsed) == 2
    assert parsed[0].template_id is not None
    # Drain3 debería agrupar estos mensajes bajo la misma plantilla
    assert parsed[0].template_id == parsed[1].template_id


def test_data_pipeline_agent_process_window():
    lab = ScenarioLabRunner()
    sc, logs, tel = lab.execute_scenario("HTTP-502-01", seed=42)

    pipeline = DataPipelineAgent()
    ventana = pipeline.process_window(sc, logs, tel)

    assert isinstance(ventana, VentanaLogContract)
    assert ventana.scenario_id == "HTTP-502-01"
    assert len(ventana.parsed_logs) == len(logs)
    assert "REGISTRO DE EVENTOS" in ventana.rendered_context_prompt
    assert "Tasa de error observada:" in ventana.rendered_context_prompt


def test_drain3_empty_and_single_log():
    parser = Drain3LogParser()
    assert parser.parse_batch([]) == []

    single = [{"raw_message": "Single error line", "timestamp": "2026-09-25 10:00:00", "source_service": "test"}]
    res = parser.parse_batch(single)
    assert len(res) == 1
    assert res[0].template_id is not None


def test_pipeline_agent_different_categories_prompts():
    lab = ScenarioLabRunner()
    pipeline = DataPipelineAgent()

    # DNS Scenario
    sc_dns, logs_dns, tel_dns = lab.execute_scenario("DNS-NXD-01", seed=42)
    v_dns = pipeline.process_window(sc_dns, logs_dns, tel_dns)
    assert "DNS" in v_dns.rendered_context_prompt or "bind9" in v_dns.rendered_context_prompt

    # TLS Scenario
    sc_tls, logs_tls, tel_tls = lab.execute_scenario("TLS-EXP-01", seed=42)
    v_tls = pipeline.process_window(sc_tls, logs_tls, tel_tls)
    assert "TLS" in v_tls.rendered_context_prompt or "SSL" in v_tls.rendered_context_prompt or "nginx" in v_tls.rendered_context_prompt


def test_pipeline_telemetry_integration():
    lab = ScenarioLabRunner()
    pipeline = DataPipelineAgent()
    sc, logs, tel = lab.execute_scenario("HTTP-504-01", seed=1337)
    ventana = pipeline.process_window(sc, logs, tel)

    assert "TELEMETRÍA" in ventana.rendered_context_prompt
    assert ventana.scenario_id == "HTTP-504-01"
    assert "INCIDENTE-L7" in ventana.rendered_context_prompt

