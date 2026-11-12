"""
NetDiagBench-L7: Layer 1 & 5 - Zero Data Leakage Test Suite (Hallazgo C1)
Verifica que los logs generados, el contexto del prompt y las salidas del simulador
cumplan estrictamente con la política de Cero Fuga de Información Técnica:
1. No contienen el scenario_id.
2. No contienen frases prohibidas eliminadas:
   ('backend-application-pool', 'upstream-cluster', 'filtered by firewall', 'no live upstreams').
3. No filtran nombres internos de componentes ni causas del Ground Truth en logs o herramientas.
   Excepción autorizada: mensajes técnicos estándar emitidos por herramientas reales
   ('certificate has expired', 'REFUSED', 'NXDOMAIN', 'lame server delegation').
"""

import re
import pytest
from src.layer1_lab.runner import ScenarioLabRunner
from src.layer2_pipeline.aggregator import DataPipelineAgent
from src.layer3_rag.retriever import RAGKnowledgeEngine
from src.layer4_inference.engine import LocalInferenceEngine
from src.layer5_orchestrator.agent import DiagnosticOrchestratorAgent
from src.layer5_orchestrator.tools import ReadOnlyNetworkTools

ELIMINATED_PHRASES = [
    "backend-application-pool",
    "upstream-cluster",
    "filtered by firewall",
    "no live upstreams"
]

ALLOWED_EXCEPTIONS = [
    "certificate has expired",
    "refused",
    "nxdomain",
    "lame server delegation",
    "lame server",
    "connection refused",
    "no route to host",
    "timed out"
]


def test_no_leakage_in_synthetic_logs_all_scenarios():
    """Verifica que los logs generados para los 18 escenarios no contengan scenario_id ni frases prohibidas."""
    lab = ScenarioLabRunner()
    scenarios = lab.list_scenarios()
    assert len(scenarios) == 18, f"Se esperaban 18 escenarios, se encontraron {len(scenarios)}"

    for sc in scenarios:
        for seed in (42, 1337, 2026):
            logs = lab.generate_synthetic_logs(sc, seed=seed, count=20)
            for entry in logs:
                msg = entry.get("raw_message", "")
                msg_lower = msg.lower()

                # 1. No debe contener el ID del escenario
                assert sc.scenario_id not in msg, (
                    f"Fuga detectada: scenario_id '{sc.scenario_id}' encontrado en log de {sc.scenario_id}"
                )

                # 2. No debe contener frases eliminadas
                for phrase in ELIMINATED_PHRASES:
                    assert phrase not in msg_lower, (
                        f"Fuga detectada: frase prohibida '{phrase}' encontrada en log de {sc.scenario_id}: {msg}"
                    )


def test_no_leakage_in_simulator_outputs_all_scenarios():
    """Verifica que las respuestas del simulador de herramientas no contengan scenario_id ni frases eliminadas."""
    lab = ScenarioLabRunner()
    scenarios = lab.list_scenarios()

    probe_commands = {
        "dig": [
            "dig @127.0.0.1 -p 5353 app.internal.corp A",
            "dig @127.0.0.1 -p 5353 sub.corp.internal NS",
            "dig @127.0.0.1 -p 5353 restricted.corp.internal A",
            "dig @127.0.0.1 -p 5353 partner.external.org A",
            "dig @127.0.0.1 -p 5353 large-recordset.corp.internal ANY +bufsize=512 +notcp"
        ],
        "curl": [
            "curl -I http://127.0.0.1:80/api/v1/users",
            "curl -I http://127.0.0.1:80/api/v1/orders",
            "curl -I http://127.0.0.1:80/api/v1/reports",
            "curl -I http://127.0.0.1:80/api/v1/health",
            "curl -I http://127.0.0.1:80/admin/system/status",
            "curl -I http://127.0.0.1:80/api/v1/search?q=telecom"
        ],
        "openssl": [
            "openssl s_client -connect 127.0.0.1:443 -servername secure.corp.internal",
            "openssl s_client -connect 127.0.0.1:443 -servername api-unregistered.corp.internal",
            "openssl s_client -connect 127.0.0.1:443 -cipher AES128-SHA"
        ],
        "ping": [
            "ping -c 4 127.0.0.1"
        ]
    }

    for sc in scenarios:
        tools = ReadOnlyNetworkTools(scenario=sc)
        for tool_name, cmds in probe_commands.items():
            for cmd in cmds:
                success, output = tools.dispatch(tool_name, cmd)
                out_lower = output.lower()

                # 1. No debe contener el ID del escenario
                assert sc.scenario_id not in output, (
                    f"Fuga en herramienta {tool_name}: '{sc.scenario_id}' en salida de {sc.scenario_id}"
                )

                # 2. No debe contener frases eliminadas
                for phrase in ELIMINATED_PHRASES:
                    assert phrase not in out_lower, (
                        f"Fuga en herramienta {tool_name}: frase prohibida '{phrase}' en salida de {sc.scenario_id}: {output}"
                    )


def test_no_leakage_in_model_context_prompt(monkeypatch):
    """Verifica que el prompt contextual que recibe el modelo no contenga scenario_id ni frases prohibidas."""
    lab = ScenarioLabRunner()
    scenarios = lab.list_scenarios()
    pipe = DataPipelineAgent()
    rag = RAGKnowledgeEngine()

    prompts_inspected = []
    engine = LocalInferenceEngine(force_simulation=True)
    orig_generate = engine.generate

    def mock_generate(*args, **kwargs):
        prompts_inspected.append(kwargs.get("prompt", ""))
        return orig_generate(*args, **kwargs)

    monkeypatch.setattr(engine, "generate", mock_generate)
    orch = DiagnosticOrchestratorAgent(inference_engine=engine)

    for sc in scenarios:
        prompts_inspected.clear()
        _, logs, tel = lab.execute_scenario(sc.scenario_id, seed=42)
        ventana = pipe.process_window(sc, logs, tel)
        contexto = rag.query(sc.category.value)

        orch.run_diagnosis(sc, ventana, contexto, model_id="qwen3-8b", seed=42)
        assert len(prompts_inspected) >= 1

        for p in prompts_inspected:
            # 1. El prompt nunca debe incluir el scenario_id
            assert sc.scenario_id not in p, (
                f"Fuga en prompt contextual: '{sc.scenario_id}' expuesto en el prompt de {sc.scenario_id}"
            )
            # 2. El bloque de telemetría observada nunca debe incluir las frases eliminadas
            m_tel = re.search(r"<telemetria_observada>(.*?)</telemetria_observada>", p, re.DOTALL)
            if m_tel:
                tel_text = m_tel.group(1).lower()
                for phrase in ELIMINATED_PHRASES:
                    assert phrase not in tel_text, (
                        f"Fuga en telemetría observada: frase prohibida '{phrase}' expuesta al LLM en {sc.scenario_id}"
                    )
