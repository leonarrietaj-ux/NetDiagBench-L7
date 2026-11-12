"""
Pruebas Unitarias para Traducción al Español y Extracción Exclusiva del Mismo Modelo (Cero Fuga de Ground Truth).
Verifica que:
1. Cualquier respuesta o campo en inglés sea traducido de forma fiel y fluida al español.
2. Causa raíz, componente, mitigación y fundamentación provengan obligatoriamente del mismo modelo evaluado.
"""

import pytest
from src.core.translator import translate_english_to_spanish, is_predominantly_english
from src.layer1_lab.runner import ScenarioLabRunner
from src.layer4_inference.engine import LocalInferenceEngine
from src.layer5_orchestrator.agent import DiagnosticOrchestratorAgent
from src.layer6_interface.observability import _render_final_verdict


def test_is_predominantly_english():
    tinyllama_english = (
        "The following instructions provide a taxonomy of components that must be included in the solution "
        "for the Vista Logic Technical Support team to perform their verification and final diagnosis: "
        "1. Components Verified (DNs): The DNs are the technical support team's primary means of verifying "
        "the system's functionality, including its software components, hardware components, and network connectivity."
    )
    assert is_predominantly_english(tinyllama_english) is True

    spanish_diag = (
        "La telemetría observada y la herramienta dig confirman código RCODE 3 NXDOMAIN conforme a RFC 1035. "
        "El servidor autoritativo BIND9 no contiene la zona o registro solicitado en app.internal.corp."
    )
    assert is_predominantly_english(spanish_diag) is False


def test_translate_english_to_spanish_on_technical_text():
    raw_en = (
        "The DNS server returned NXDOMAIN because the domain app.internal.corp is not found in the authoritative database. "
        "The intermediate CA certificate is missing from the nginx configuration. "
        "Reload the BIND service using rndc reload to apply the new DNS zone records."
    )
    trans = translate_english_to_spanish(raw_en)
    assert "servidor DNS retornó NXDOMAIN" in trans
    assert "no se encuentra en la base de datos autoritativa" in trans
    assert "falta el certificado de la ca intermedia" in trans.lower()
    assert "rndc reload" in trans  # Preservar comandos de red


def test_reasoning_cot_integrated_in_natural_language_explanation():
    lab = ScenarioLabRunner()
    sc = lab.get_scenario("DNS-NXD-01")
    agent = DiagnosticOrchestratorAgent(inference_engine=LocalInferenceEngine(force_simulation=True))

    cot_chain = (
        "Analizando el incidente DNS-NXD-01. Observo que se realizaron consultas a 127.0.0.1 en puerto 5353. "
        "La respuesta de dig devolvió status: NXDOMAIN (Name Error). "
        "Esto indica que el resolver pudo contactar al servidor autoritativo, pero el FQDN solicitado no está "
        "presente en el archivo de zonas db.corp.internal. Por lo tanto, el componente afectado es bind9-authoritative."
    )
    model_raw_response = (
        f"<think>\n{cot_chain}\n</think>\n\n"
        "```json\n"
        "{\n"
        '  "causa_raiz": "Registro ausente en base de datos BIND9.",\n'
        '  "componente": "bind9-authoritative",\n'
        '  "mitigacion": "Publicar registro y recargar con rndc reload.",\n'
        '  "fundamentacion_tecnica": "Conclusión breve: NXDOMAIN verificado."\n'
        "}\n"
        "```"
    )

    diag = agent._parse_final_diagnosis(
        scenario=sc,
        model_id="deepseek-r1:1.5b",
        response_text=model_raw_response,
        evidence_list=["dig app.internal.corp -> NXDOMAIN"]
    )

    assert diag.root_cause == "Registro ausente en base de datos BIND9."
    assert diag.affected_component == "bind9-authoritative"
    assert "rndc reload" in diag.suggested_action
    assert "Cadena de Razonamiento CoT:" in diag.natural_language_explanation
    assert "Analizando el incidente DNS-NXD-01" in diag.natural_language_explanation
    assert "NXDOMAIN verificado" in diag.natural_language_explanation


def test_model_fields_extracted_from_same_model_and_translated():
    """Verifica que causa raíz, componente, mitigación y fundamentación provengan del modelo y se traduzcan al español."""
    lab = ScenarioLabRunner()
    sc = lab.get_scenario("DNS-NXD-01")
    agent = DiagnosticOrchestratorAgent(inference_engine=LocalInferenceEngine(force_simulation=True))

    # Modelo emite JSON puramente en inglés con sus propias deducciones
    model_english_response = (
        "```json\n"
        "{\n"
        '  "root_cause": "The authoritative DNS server returned NXDOMAIN for the requested hostname.",\n'
        '  "component": "bind9-authoritative",\n'
        '  "mitigation": "Add the DNS record to the zone file and reload BIND with rndc reload.",\n'
        '  "fundamentacion_tecnica": "Telemetry shows that queries for app.internal.corp failed with status NXDOMAIN. The dig command confirmed that no such record exists in the authoritative zone."\n'
        "}\n"
        "```"
    )

    diag = agent._parse_final_diagnosis(
        scenario=sc,
        model_id="english-model:1b",
        response_text=model_english_response,
        evidence_list=["dig app.internal.corp -> NXDOMAIN"]
    )

    # 1. Causa raíz proviene del modelo y está traducida al español
    assert "servidor DNS autoritativo retornó NXDOMAIN" in diag.root_cause
    assert not is_predominantly_english(diag.root_cause)

    # 2. Componente proviene del modelo
    assert diag.affected_component == "bind9-authoritative"

    # 3. Mitigación proviene del modelo y está traducida al español
    assert "archivo de zona" in diag.suggested_action.lower()
    assert "rndc reload" in diag.suggested_action

    # 4. Fundamentación proviene del modelo y está traducida al español
    assert "la telemetría muestra que las consultas" in diag.natural_language_explanation.lower()
    assert not is_predominantly_english(diag.natural_language_explanation)


def test_render_final_verdict_displays_translated_model_outputs_without_ground_truth_leak():
    """Verifica que el renderizador de la UI muestre exclusivamente las salidas del modelo traducidas al español."""
    model_rc = "The upstream backend server is unreachable due to high network latency"
    model_comp = "network-infrastructure"
    model_act = "Verify network routing and reduce traffic control latency"
    model_exp = "Based on the observed telemetry, packet delay caused HTTP 504 gateway timeout."

    html_verdict = _render_final_verdict(
        scenario_id="DNS-NXD-01",  # Un escenario completamente distinto (para probar cero fuga)
        root_cause=model_rc,
        affected_component=model_comp,
        suggested_action=model_act,
        explanation=model_exp,
        confidence_score=0.75,
    )

    # Debe contener lo que el MODELO dijo (traducido), NO lo del escenario DNS-NXD-01
    assert "servidor upstream" in html_verdict.lower() or "latencia" in html_verdict.lower()
    assert "network-infrastructure" in html_verdict
    assert "tráfico" in html_verdict.lower() or "latencia" in html_verdict.lower()
    assert "con base en la telemetría observada" in html_verdict.lower()
    # NO debe tener texto del ground truth de DNS-NXD-01 (cero fuga)
    assert "Registro de zona faltante o nombre de dominio inexistente en la base de datos de BIND9" not in html_verdict
