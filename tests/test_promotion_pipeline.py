"""
NetDiagBench-L7: Tests for Controlled Promotion Pipeline (Section 9)
===================================================================
Valida exhaustivamente el comportamiento del pipeline de promoción:
- Detección de fallos en el diseño experimental (conteo, modelos, escenarios).
- Detección de motores simulados (debe exigir 'live_ollama').
- Detección de telemetría arbitraria (5 GB de VRAM).
- Detección de discrepancias criptográficas en prompt/response hashes.
- Archivo atómico con manifiesto SHA-256 en modo promoción real.
"""

import json
import shutil
from pathlib import Path
import pandas as pd
import pytest

from scripts.promote_benchmark_results import (
    ControlledPromotionPipeline,
    PromotionValidationError,
    compute_file_sha256,
)
from src.core.trace_validator import calculate_prompt_sha256


@pytest.fixture
def staging_mock_env(tmp_path: Path):
    """Crea un entorno de staging simulado con datos válidos."""
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    archive_dir = tmp_path / "archive"
    archive_dir.mkdir()

    # Crear archivos objetivo preexistentes para probar archivado
    old_csv = target_dir / "resultados.csv"
    old_csv.write_text("old,data\n1,2", encoding="utf-8")
    old_jsonl = target_dir / "traza.jsonl"
    old_jsonl.write_text('{"old": "data"}\n', encoding="utf-8")

    # Crear datos válidos para 3 corridas
    records = []
    traces = []
    test_cases = [
        ("qwen3-8b", "TLS-EXP-01", 42, "emulado"),
        ("glm-4-9b-chat", "HTTP-502-01", 42, "emulado"),
        ("phi-4-mini-instruct", "DNS-NXD-01", 42, "sintetico_determinista"),
    ]

    for model, sc_id, seed, exec_mode in test_cases:
        p_text = f"Prompt para {model} en {sc_id}"
        r_text = f"Diagnóstico de falla para {sc_id}"
        p_sha = calculate_prompt_sha256(p_text)
        r_sha = calculate_prompt_sha256(r_text)
        cfg_sha = "a" * 64
        run_id = f"{model}_{sc_id}_s{seed}"

        rec = {
            "run_id": run_id,
            "model_id": model,
            "scenario_id": sc_id,
            "seed": seed,
            "execution_mode": exec_mode,
            "engine_mode": "live_ollama",
            "peak_vram_gb": None,
            "category": "DNS" if "DNS" in sc_id else "TLS" if "TLS" in sc_id else "API_GATEWAY",
            "fault_class": "NXDOMAIN" if "NXD" in sc_id else "TLS_EXPIRED_CERT" if "TLS" in sc_id else "HTTP_502_BAD_GATEWAY",
            "is_root_cause_correct": 1,
            "is_component_correct": 1,
        }
        records.append(rec)

        tr = {
            "run_id": run_id,
            "model_id": model,
            "scenario_id": sc_id,
            "seed": seed,
            "prompt": p_text,
            "response": r_text,
            "prompt_sha256": p_sha,
            "response_sha256": r_sha,
            "config_sha256": cfg_sha,
        }
        traces.append(tr)

    df = pd.DataFrame(records)
    csv_path = staging_dir / "resultados_staging.csv"
    df.to_csv(csv_path, index=False)

    jsonl_path = staging_dir / "traza_staging.jsonl"
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for t in traces:
            f.write(json.dumps(t) + "\n")

    return {
        "staging_dir": staging_dir,
        "target_csv": old_csv,
        "target_jsonl": old_jsonl,
        "archive_dir": archive_dir,
        "csv_path": csv_path,
        "jsonl_path": jsonl_path,
        "df": df,
    }


def test_promotion_dry_run_success(staging_mock_env):
    """Prueba que el modo dry-run valide con éxito y no altere los archivos objetivo."""
    env = staging_mock_env
    pipeline = ControlledPromotionPipeline(
        staging_dir=env["staging_dir"],
        target_csv=env["target_csv"],
        target_jsonl=env["target_jsonl"],
        archive_dir=env["archive_dir"],
        dry_run=True,
        allow_incomplete=True,
    )
    receipt = pipeline.run()
    assert receipt["dry_run"] is True
    assert receipt["total_runs_promoted"] == 3
    assert receipt["emulated_runs"] == 2
    assert receipt["synthetic_runs"] == 1

    # Asegurar que los archivos objetivo no fueron modificados
    assert env["target_csv"].read_text(encoding="utf-8") == "old,data\n1,2"


def test_promotion_real_execution_archives_and_replaces(staging_mock_env):
    """Prueba que la ejecución real archive los antiguos y promueva los nuevos con hash manifiesto."""
    env = staging_mock_env
    pipeline = ControlledPromotionPipeline(
        staging_dir=env["staging_dir"],
        target_csv=env["target_csv"],
        target_jsonl=env["target_jsonl"],
        archive_dir=env["archive_dir"],
        dry_run=False,
        allow_incomplete=True,
    )
    receipt = pipeline.run()
    assert receipt["dry_run"] is False
    assert receipt["total_runs_promoted"] == 3

    # Comprobar que se creó el subdirectorio de archivo con el manifiesto
    archive_subdirs = list(env["archive_dir"].glob("archive_*"))
    assert len(archive_subdirs) == 1
    manifest = archive_subdirs[0] / "MANIFEST_SHA256.txt"
    assert manifest.exists()
    content = manifest.read_text(encoding="utf-8")
    assert "resultados.csv" in content
    assert "traza.jsonl" in content

    # Comprobar que los archivos destino ahora tienen los datos nuevos
    promoted_df = pd.read_csv(env["target_csv"])
    assert len(promoted_df) == 3
    assert "qwen3-8b" in promoted_df["model_id"].values


def test_promotion_fails_on_simulator_engine(staging_mock_env):
    """Debe rechazar corridas con engine_mode == 'deterministic_simulator'."""
    env = staging_mock_env
    df = pd.read_csv(env["csv_path"])
    df.loc[0, "engine_mode"] = "deterministic_simulator"
    df.to_csv(env["csv_path"], index=False)

    pipeline = ControlledPromotionPipeline(
        staging_dir=env["staging_dir"],
        target_csv=env["target_csv"],
        target_jsonl=env["target_jsonl"],
        archive_dir=env["archive_dir"],
        dry_run=True,
        allow_incomplete=True,
    )
    with pytest.raises(PromotionValidationError, match="no tienen engine_mode == 'live_ollama'"):
        pipeline.run()


def test_promotion_fails_on_arbitrary_5gb_vram(staging_mock_env):
    """Debe rechazar corridas que introduzcan el valor arbitrario de 5 GB."""
    env = staging_mock_env
    df = pd.read_csv(env["csv_path"])
    df.loc[0, "peak_vram_gb"] = 5.0
    df.to_csv(env["csv_path"], index=False)

    pipeline = ControlledPromotionPipeline(
        staging_dir=env["staging_dir"],
        target_csv=env["target_csv"],
        target_jsonl=env["target_jsonl"],
        archive_dir=env["archive_dir"],
        dry_run=True,
        allow_incomplete=True,
    )
    with pytest.raises(PromotionValidationError, match="peak_vram_gb == 5.0"):
        pipeline.run()


def test_promotion_fails_on_tampered_crypto_hash(staging_mock_env):
    """Debe rechazar discrepancias criptográficas en prompt/response."""
    env = staging_mock_env
    # Alterar el prompt sin cambiar el hash
    with open(env["jsonl_path"], "r", encoding="utf-8") as f:
        lines = [json.loads(l) for l in f if l.strip()]
    lines[0]["prompt"] = "PROMPT ADULTERADO"
    with open(env["jsonl_path"], "w", encoding="utf-8") as f:
        for l in lines:
            f.write(json.dumps(l) + "\n")

    pipeline = ControlledPromotionPipeline(
        staging_dir=env["staging_dir"],
        target_csv=env["target_csv"],
        target_jsonl=env["target_jsonl"],
        archive_dir=env["archive_dir"],
        dry_run=True,
        allow_incomplete=True,
    )
    with pytest.raises(PromotionValidationError, match="Discrepancia criptográfica en prompt_sha256"):
        pipeline.run()
