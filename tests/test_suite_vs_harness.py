"""
Pruebas de equivalencia exacta entre la suite de la interfaz web y el arnés evaluador (Harness).
Verifica:
1. Columnas y valores de evaluación idénticos entre filas generadas por la suite web y el harness.
2. Invariante de no duplicación: reemplazo en resultados.csv para la misma tupla (model, scenario, seed, rep).
3. Aborto explícito al iniciar la suite si Docker o los contenedores emulados no están activos.
4. Resolución correcta del container_name en el harness para el digest emulado.
"""

import asyncio
import csv
from unittest.mock import patch
from src.core.contracts import ResultadoEvaluacionContract
from src.layer1_lab.runner import ScenarioLabRunner
from src.layer7_evaluator.harness import (
    BenchmarkEvaluatorHarness,
    save_or_replace_benchmark_result,
)
from src.layer6_interface.observability import generate_langgraph_sse_events


def test_suite_vs_harness_exact_row_and_evaluation_match():
    """
    Requisito 5: Una fila generada por la suite web y una generada por el harness,
    para el mismo (modelo, escenario, semilla), tienen las mismas columnas y los mismos
    valores de evaluación.
    """
    runner = ScenarioLabRunner()
    scenario = runner.get_scenario("DNS-NXD-01")
    assert scenario is not None

    harness = BenchmarkEvaluatorHarness()
    harness.inference_engine.force_simulation = True

    # Ejecución vía harness
    res_harness = harness._execute_single_trial(
        model_id="phi-4-mini-instruct",
        scenario=scenario,
        seed=42,
        rep_index=1
    )

    # Ejecución vía suite web (compartida a través de _execute_single_trial con return_details=True)
    res_web, details = harness._execute_single_trial(
        model_id="phi-4-mini-instruct",
        scenario=scenario,
        seed=42,
        rep_index=1,
        return_details=True
    )

    row_harness = res_harness.model_dump()
    row_web = res_web.model_dump()

    # 1. Exactamente las mismas columnas
    expected_columns = set(ResultadoEvaluacionContract.model_fields.keys())
    assert set(row_harness.keys()) == expected_columns
    assert set(row_web.keys()) == expected_columns
    assert set(row_harness.keys()) == set(row_web.keys())

    # 2. Columnas obligatorias de MLOps y emulación presentes
    for col in [
        "git_commit_hash",
        "git_dirty",
        "model_diagnosis_text",
        "root_cause",
        "execution_mode",
        "container_image_digest",
        "docker_version",
    ]:
        assert col in row_harness
        assert col in row_web

    # 3. Mismos valores de evaluación diagnóstica
    assert row_harness["is_root_cause_correct"] == row_web["is_root_cause_correct"]
    assert row_harness["is_component_correct"] == row_web["is_component_correct"]
    assert row_harness["partial_match_score"] == row_web["partial_match_score"]
    assert row_harness["rubric_score"] == row_web["rubric_score"]
    assert row_harness["evidence_backed"] == row_web["evidence_backed"]
    assert row_harness["category"] == row_web["category"]
    assert row_harness["fault_class"] == row_web["fault_class"]
    assert row_harness["execution_mode"] == row_web["execution_mode"]
    assert row_harness["root_cause"] == row_web["root_cause"]
    assert row_harness["model_diagnosis_text"] == row_web["model_diagnosis_text"]
    assert row_harness["git_commit_hash"] == row_web["git_commit_hash"]
    assert row_harness["git_dirty"] == row_web["git_dirty"]

    # 4. Details contiene los artefactos necesarios para renderizar SSE
    assert "traza" in details
    assert "diag" in details
    assert "inf_resp" in details
    assert "ventana" in details
    assert "contexto_rag" in details


def test_suite_web_csv_replace_no_duplicate(tmp_path):
    """
    Requisito 6: Al escribir en resultados.csv desde la suite web, si ya existe una fila con el
    mismo (model_id, scenario_id, seed, repetition_index), se reemplaza en lugar de agregar otra.
    """
    csv_file = tmp_path / "resultados.csv"

    runner = ScenarioLabRunner()
    sc = runner.get_scenario("HTTP-500-01")
    assert sc is not None

    harness = BenchmarkEvaluatorHarness()
    harness.inference_engine.force_simulation = True

    initial_res = harness._execute_single_trial(
        model_id="glm-4-9b-chat",
        scenario=sc,
        seed=1337,
        rep_index=1
    )

    # 1. Primera escritura
    save_or_replace_benchmark_result(initial_res, csv_path=csv_file)

    with open(csv_file, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["model_id"] == "glm-4-9b-chat"
    assert rows[0]["scenario_id"] == "HTTP-500-01"
    assert int(rows[0]["seed"]) == 1337
    assert int(rows[0]["repetition_index"]) == 1

    # 2. Modificar el resultado y guardar nuevamente con la misma clave (simulando reejecución)
    updated_dict = initial_res.model_dump()
    updated_dict["partial_match_score"] = 0.9999
    updated_dict["model_diagnosis_text"] = "Diagnostico re-ejecutado actualizado"
    updated_res = ResultadoEvaluacionContract(**updated_dict)

    save_or_replace_benchmark_result(updated_res, csv_path=csv_file)

    with open(csv_file, "r", encoding="utf-8") as f:
        rows_after = list(csv.DictReader(f))

    # Invariante: NO se duplicó la fila, sigue habiendo 1 sola fila con el valor actualizado
    assert len(rows_after) == 1
    assert float(rows_after[0]["partial_match_score"]) == 0.9999
    assert rows_after[0]["model_diagnosis_text"] == "Diagnostico re-ejecutado actualizado"

    # 3. Guardar un resultado con clave distinta (otro escenario) debe agregar la segunda fila
    sc2 = runner.get_scenario("DNS-NXD-01")
    res_other = harness._execute_single_trial(
        model_id="glm-4-9b-chat",
        scenario=sc2,
        seed=1337,
        rep_index=1
    )
    save_or_replace_benchmark_result(res_other, csv_path=csv_file)

    with open(csv_file, "r", encoding="utf-8") as f:
        rows_multi = list(csv.DictReader(f))
    assert len(rows_multi) == 2


def test_suite_web_aborts_when_docker_inactive():
    """
    Requisito 3: Al iniciar la suite, verifica que Docker y los 3 contenedores emulados
    estén activos; si alguno no lo está, la suite no inicia y comunica el error por SSE.
    """
    async def _run_sse_check():
        events = []
        with patch("src.layer1_lab.docker_manager.is_docker_available", return_value=False), \
             patch("src.layer1_lab.docker_manager.verify_all_emulated_containers_active", return_value=(False, "Docker no está disponible o el daemon no responde.")):
            async for ev in generate_langgraph_sse_events(scenario_id="ALL", model_id="qwen3-8b", seed=42):
                events.append(ev)
        return events

    events = asyncio.run(_run_sse_check())

    # Debe emitir mensaje de error y terminar el stream inmediatamente
    event_types = [e.get("event") for e in events]
    assert "message" in event_types
    assert "stream-complete" in event_types

    all_data = "".join(e.get("data", "") for e in events)
    assert "Error: Laboratorio Docker Inactivo" in all_data
    assert "Fallo en Inicialización del Laboratorio Docker" in all_data
    assert "netdiag-tls-expired" in all_data or "Docker no está disponible" in all_data
    # No debe haber ejecutado ningún escenario ni emitido tarjetas de nodos
    assert "execute_read_only_tool" not in all_data
    assert "formulate_hypothesis" not in all_data


def test_harness_digest_container_name_lookup():
    """
    Requisito 4: Corrige la obtención del digest:
    c_name = EMULATED_SCENARIOS.get(scenario.scenario_id, {}).get("container_name", "")
    """
    from src.layer1_lab.docker_manager import EMULATED_SCENARIOS

    for sc_id, expected_cname in [
        ("TLS-EXP-01", "netdiag-tls-expired"),
        ("HTTP-502-01", "netdiag-http-502"),
        ("DNS-SRV-01", "netdiag-dns-bind9"),
    ]:
        c_name = EMULATED_SCENARIOS.get(sc_id, {}).get("container_name", "")
        assert isinstance(c_name, str)
        assert c_name == expected_cname

    # Para escenario sintetico no emulado devuelve cadena vacía
    c_synthetic = EMULATED_SCENARIOS.get("DNS-NXD-01", {}).get("container_name", "")
    assert c_synthetic == ""


def test_harness_run_benchmark_replace_preserves_other_rows(tmp_path):
    """
    Verifica que al ejecutar run_benchmark con replace_existing=True,
    se reemplacen las filas objetivo y se preserven intactas las demás filas preexistentes.
    """
    csv_file = tmp_path / "test_replace.csv"
    runner = ScenarioLabRunner()
    sc1 = runner.get_scenario("HTTP-500-01")
    sc2 = runner.get_scenario("DNS-NXD-01")

    harness = BenchmarkEvaluatorHarness(output_dir=tmp_path)
    harness.inference_engine.force_simulation = True

    # 1. Guardar corrida previa de sc1 y sc2
    r1 = harness._execute_single_trial("glm-4-9b-chat", sc1, seed=42, rep_index=1)
    r2 = harness._execute_single_trial("glm-4-9b-chat", sc2, seed=42, rep_index=1)
    save_or_replace_benchmark_result(r1, csv_path=csv_file)
    save_or_replace_benchmark_result(r2, csv_path=csv_file)

    with open(csv_file, "r", encoding="utf-8") as f:
        rows_initial = list(csv.DictReader(f))
    assert len(rows_initial) == 2

    # 2. Ejecutar run_benchmark solo para sc2 con replace_existing=True
    harness.run_benchmark(
        model_ids=["glm-4-9b-chat"],
        scenario_ids=["DNS-NXD-01"],
        seeds=[42],
        repetitions=1,
        output_csv_filename="test_replace.csv",
        generate_report=False,
        replace_existing=True
    )

    with open(csv_file, "r", encoding="utf-8") as f:
        rows_final = list(csv.DictReader(f))

    # Debe mantener exactamente las 2 filas (no duplicar ni eliminar sc1)
    assert len(rows_final) == 2
    scenarios_present = {r["scenario_id"] for r in rows_final}
    assert scenarios_present == {"HTTP-500-01", "DNS-NXD-01"}

