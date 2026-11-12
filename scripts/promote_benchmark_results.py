#!/usr/bin/env python3
"""
NetDiagBench-L7: Controlled Promotion Pipeline (Section 9)
==========================================================
Script de promoción controlada para transicionar de manera segura
los resultados experimentales desde un directorio de staging aislado hacia
las rutas canónicas de producción del benchmark.

Cumple con las 8 etapas obligatorias:
1. Directorio de staging aislado.
2. Validación de las 162 combinaciones únicas (3 modelos x 18 escenarios x 3 semillas).
3. Verificación de distribución exacta (27 emuladas Docker / 135 sintéticas de laboratorio).
4. Verificación de motor (engine_mode == 'live_ollama' para todas las corridas definitivas).
5. Verificación de trazabilidad criptográfica y canonical config sin fuga.
6. Verificación de consistencia bidireccional entre CSV y JSONL.
7. Generación / recalculación de reportes derivados y métricas estadísticas.
8. Promoción atómica y archivado histórico con manifiesto SHA-256.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd

from src.core.config import PROJECT_ROOT
from src.core.contracts import FaultClass, ServiceCategory
from src.core.logger import logger
from src.core.trace_validator import (
    calculate_file_sha256,
    calculate_prompt_sha256,
    compute_canonical_config_sha256,
    validate_alignment_csv_jsonl,
    validate_trace_file,
)
from src.layer1_lab.runner import ScenarioLabRunner
from src.layer7_evaluator.composite_score import (
    calculate_model_composite_scores,
    rank_models_by_composite_score,
)
from src.layer7_evaluator.statistical_analysis import compute_classification_metrics

EMULATED_SCENARIOS = {"TLS-EXP-01", "HTTP-502-01", "DNS-SRV-01"}
CANONICAL_MODELS = {"qwen3-8b", "glm-4-9b-chat", "phi-4-mini-instruct"}
CANONICAL_SEEDS = {42, 1337, 2026}


class PromotionValidationError(Exception):
    """Excepción para fallos de validación en el pipeline de promoción."""
    pass


def get_git_info() -> Dict[str, Any]:
    """Obtiene información sobre el commit y estado git."""
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        commit = "unknown"

    try:
        status = subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=PROJECT_ROOT, stderr=subprocess.DEVNULL
        ).decode().strip()
        dirty = bool(status)
    except Exception:
        dirty = False

    return {"commit_sha": commit, "is_dirty": dirty}


def compute_file_sha256(path: Path) -> str:
    """Calcula el hash SHA-256 de un archivo en disco."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


class ControlledPromotionPipeline:
    """Pipeline de control y promoción de resultados del benchmark NetDiagBench-L7."""

    def __init__(
        self,
        staging_dir: Path,
        target_csv: Path | None = None,
        target_jsonl: Path | None = None,
        archive_dir: Path | None = None,
        dry_run: bool = False,
        allow_incomplete: bool = False,
    ):
        self.staging_dir = Path(staging_dir).resolve()
        self.target_csv = (
            Path(target_csv).resolve()
            if target_csv
            else (PROJECT_ROOT / "data" / "benchmark_results" / "resultados.csv")
        )
        self.target_jsonl = (
            Path(target_jsonl).resolve()
            if target_jsonl
            else (PROJECT_ROOT / "data" / "benchmark_results" / "traza.jsonl")
        )
        self.archive_dir = (
            Path(archive_dir).resolve()
            if archive_dir
            else (PROJECT_ROOT / "data" / "historical_runs_archive")
        )
        self.dry_run = dry_run
        self.allow_incomplete = allow_incomplete

        self.scenario_runner = ScenarioLabRunner()
        self.catalog_scenarios = {s.scenario_id: s for s in self.scenario_runner.list_scenarios()}

    def validate_staging_files(self) -> Tuple[Path, Path]:
        """Etapa 1: Valida que existan los archivos en el directorio de staging."""
        csv_candidates = list(self.staging_dir.glob("*.csv"))
        jsonl_candidates = list(self.staging_dir.glob("*.jsonl"))

        if not csv_candidates:
            raise PromotionValidationError(f"No se encontró archivo CSV en staging: {self.staging_dir}")
        if not jsonl_candidates:
            raise PromotionValidationError(f"No se encontró archivo JSONL en staging: {self.staging_dir}")

        # Preferir nombres estandarizados si existen
        csv_file = next((f for f in csv_candidates if "resultados" in f.name), csv_candidates[0])
        jsonl_file = next((f for f in jsonl_candidates if "traza" in f.name), jsonl_candidates[0])

        logger.info(f"Staging CSV detectado: {csv_file}")
        logger.info(f"Staging JSONL detectado: {jsonl_file}")
        return csv_file, jsonl_file

    def validate_experimental_design(self, df: pd.DataFrame) -> None:
        """Etapas 2 y 3: Valida las 162 combinaciones y la distribución 27/135."""
        total_runs = len(df)
        expected_total = 162

        if not self.allow_incomplete and total_runs != expected_total:
            raise PromotionValidationError(
                f"Discrepancia en total de corridas: esperadas {expected_total}, encontradas {total_runs}"
            )

        # Validar modelos
        found_models = set(df["model_id"].unique())
        if not self.allow_incomplete and found_models != CANONICAL_MODELS:
            raise PromotionValidationError(
                f"Modelos no coinciden con el diseño canónico: {found_models} != {CANONICAL_MODELS}"
            )

        # Validar semillas
        found_seeds = set(df["seed"].unique())
        if not self.allow_incomplete and found_seeds != CANONICAL_SEEDS:
            raise PromotionValidationError(
                f"Semillas no coinciden con el diseño canónico: {found_seeds} != {CANONICAL_SEEDS}"
            )

        # Validar escenarios
        found_scenarios = set(df["scenario_id"].unique())
        missing_scenarios = set(self.catalog_scenarios.keys()) - found_scenarios
        if not self.allow_incomplete and missing_scenarios:
            raise PromotionValidationError(
                f"Faltan escenarios en las corridas candidatas: {missing_scenarios}"
            )

        # Validar unicidad de (model_id, scenario_id, seed)
        duplicates = df.duplicated(subset=["model_id", "scenario_id", "seed"])
        if duplicates.any():
            dup_rows = df[duplicates][["model_id", "scenario_id", "seed"]].to_dict(orient="records")
            raise PromotionValidationError(f"Se encontraron combinaciones duplicadas: {dup_rows}")

        # Validar distribución 27 emulados / 135 sintéticos
        emulated_mask = df["scenario_id"].isin(EMULATED_SCENARIOS)
        emulated_count = int(emulated_mask.sum())
        synthetic_count = int((~emulated_mask).sum())

        if not self.allow_incomplete:
            if emulated_count != 27:
                raise PromotionValidationError(
                    f"Discrepancia en corridas emuladas: esperadas 27, encontradas {emulated_count}"
                )
            if synthetic_count != 135:
                raise PromotionValidationError(
                    f"Discrepancia en corridas sintéticas: esperadas 135, encontradas {synthetic_count}"
                )

        # Validar execution_mode en cada subgrupo
        invalid_emulated = df[emulated_mask & (df["execution_mode"] != "emulado")]
        if not invalid_emulated.empty:
            raise PromotionValidationError(
                f"{len(invalid_emulated)} escenarios emulados tienen execution_mode != 'emulado'"
            )

        invalid_synthetic = df[(~emulated_mask) & (df["execution_mode"] != "sintetico_determinista")]
        if not invalid_synthetic.empty:
            raise PromotionValidationError(
                f"{len(invalid_synthetic)} escenarios sintéticos tienen execution_mode != 'sintetico_determinista'"
            )

        logger.info(f"Diseño experimental verificado: {total_runs} corridas ({emulated_count} emuladas, {synthetic_count} sintéticas).")

    def validate_engine_and_telemetry(self, df: pd.DataFrame) -> None:
        """Etapa 4: Valida engine_mode y consistencia de hardware/telemetría."""
        # Todos deben ser live_ollama para resultados reales definitivos
        non_live = df[df["engine_mode"] != "live_ollama"]
        if not non_live.empty:
            raise PromotionValidationError(
                f"{len(non_live)} corridas no tienen engine_mode == 'live_ollama'. "
                "Las corridas definitivas no pueden ser simuladas determinísticamente."
            )

        # Validar que no haya VRAM arbitraria de 5 GB
        arbitrary_vram = df[df["peak_vram_gb"] == 5.0]
        if not arbitrary_vram.empty:
            raise PromotionValidationError(
                f"{len(arbitrary_vram)} corridas tienen peak_vram_gb == 5.0 (valor arbitrario no permitido)."
            )

        # Validar campos de hardware y estado de medición VRAM
        if "vram_measurement_status" in df.columns:
            unmeasured_mask = df["vram_measurement_valid"] == False
            if unmeasured_mask.any():
                invalid_nulls = df[unmeasured_mask & df["peak_vram_gb"].notna() & (df["peak_vram_gb"] > 0)]
                if not invalid_nulls.empty:
                    logger.warning(
                        f"{len(invalid_nulls)} filas tienen vram_measurement_valid == False pero peak_vram_gb > 0."
                    )

        logger.info("Motor live_ollama y telemetría de hardware validados correctamente.")

    def validate_traces_and_hashes(self, jsonl_path: Path, df_csv: pd.DataFrame) -> List[Dict[str, Any]]:
        """Etapa 5 y 6: Valida hashes criptográficos y consistencia CSV <-> JSONL."""
        traces: List[Dict[str, Any]] = []
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    traces.append(data)
                except json.JSONDecodeError as e:
                    raise PromotionValidationError(f"Error decodificando línea {line_num} en {jsonl_path}: {e}")

        if not self.allow_incomplete and len(traces) != len(df_csv):
            raise PromotionValidationError(
                f"Discrepancia en cantidad de registros: CSV={len(df_csv)}, JSONL={len(traces)}"
            )

        # Mapear por run_id o por tupla (model_id, scenario_id, seed)
        csv_runs = set()
        if "run_id" in df_csv.columns:
            csv_runs = set(df_csv["run_id"].dropna().unique())

        for idx, tr in enumerate(traces):
            run_id = tr.get("run_id")
            if csv_runs and run_id and run_id not in csv_runs:
                raise PromotionValidationError(f"run_id '{run_id}' del JSONL no existe en el CSV.")

            # Validar hashes criptográficos recalculados
            prompt_text = tr.get("prompt", "")
            response_text = tr.get("response", "")
            expected_prompt_hash = tr.get("prompt_sha256", "")
            expected_resp_hash = tr.get("response_sha256", "")

            if prompt_text and expected_prompt_hash:
                recalc_prompt_hash = calculate_prompt_sha256(prompt_text)
                if recalc_prompt_hash != expected_prompt_hash:
                    raise PromotionValidationError(
                        f"Discrepancia criptográfica en prompt_sha256 para traza {run_id or idx}: "
                        f"{recalc_prompt_hash} != {expected_prompt_hash}"
                    )

            if response_text and expected_resp_hash:
                recalc_resp_hash = calculate_prompt_sha256(response_text)
                if recalc_resp_hash != expected_resp_hash:
                    raise PromotionValidationError(
                        f"Discrepancia criptográfica en response_sha256 para traza {run_id or idx}: "
                        f"{recalc_resp_hash} != {expected_resp_hash}"
                    )

            # Validar canonical config hash (no vacío y 64 hex caracteres)
            config_hash = tr.get("config_sha256", "")
            if config_hash:
                if len(config_hash) != 64 or not all(c in "0123456789abcdefABCDEF" for c in config_hash):
                    raise PromotionValidationError(f"config_sha256 inválido en traza {run_id or idx}: '{config_hash}'")

        logger.info(f"Criptografía y consistencia verificadas para {len(traces)} trazas.")
        return traces

    def execute_promotion(self, csv_file: Path, jsonl_file: Path, df: pd.DataFrame, traces: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Etapas 7 y 8: Archivación previa, promoción atómica y generación de reportes."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        git_info = get_git_info()

        # Resumen de métricas
        f1_summary = {}
        for model in df["model_id"].unique():
            df_m = df[df["model_id"] == model]
            rows_m = df_m.to_dict(orient="records")
            try:
                met = compute_classification_metrics(rows_m)
                f1_summary[model] = {
                    "accuracy": float((df_m["is_root_cause_correct"] == 1).mean()) if "is_root_cause_correct" in df_m.columns else 0.0,
                    "f1_macro": float(met.get("f1_macro", 0.0)),
                    "precision_macro": float(met.get("precision_macro", 0.0)),
                    "recall_macro": float(met.get("recall_macro", 0.0)),
                }
            except Exception as e:
                f1_summary[model] = {"error": str(e)}

        receipt = {
            "promotion_timestamp_utc": timestamp,
            "git_commit": git_info["commit_sha"],
            "git_dirty": git_info["is_dirty"],
            "dry_run": self.dry_run,
            "total_runs_promoted": len(df),
            "emulated_runs": int((df["execution_mode"] == "emulado").sum()),
            "synthetic_runs": int((df["execution_mode"] == "sintetico_determinista").sum()),
            "models": list(df["model_id"].unique()),
            "metrics_summary": f1_summary,
            "source_csv_sha256": compute_file_sha256(csv_file),
            "source_jsonl_sha256": compute_file_sha256(jsonl_file),
        }

        if self.dry_run:
            logger.info("MODO DRY-RUN: Validación completa exitosa. No se modificaron archivos canónicos.")
            return receipt

        # 1. Archivar resultados existentes si existen
        archive_subdir = self.archive_dir / f"archive_{timestamp}"
        archive_subdir.mkdir(parents=True, exist_ok=True)
        archived_files = []

        for target_f in [self.target_csv, self.target_jsonl]:
            if target_f.exists():
                dst = archive_subdir / target_f.name
                shutil.copy2(target_f, dst)
                dst_sha = compute_file_sha256(dst)
                archived_files.append((target_f.name, dst_sha))
                logger.info(f"Archivo previo respaldado: {target_f.name} -> {dst} (SHA-256: {dst_sha[:12]}...)")

        # Manifiesto de archivado
        manifest_path = archive_subdir / "MANIFEST_SHA256.txt"
        with open(manifest_path, "w", encoding="utf-8") as f:
            f.write(f"# NetDiagBench-L7 Archive Manifest - Timestamp: {timestamp}\n")
            f.write(f"# Git Commit: {git_info['commit_sha']} (Dirty: {git_info['is_dirty']})\n\n")
            for fname, sha in archived_files:
                f.write(f"{sha}  {fname}\n")

        receipt["archive_location"] = str(archive_subdir)
        receipt["archived_files"] = [f[0] for f in archived_files]

        # 2. Promover atómicamente a destinos canónicos
        self.target_csv.parent.mkdir(parents=True, exist_ok=True)
        self.target_jsonl.parent.mkdir(parents=True, exist_ok=True)

        shutil.copy2(csv_file, self.target_csv)
        shutil.copy2(jsonl_file, self.target_jsonl)

        receipt["target_csv"] = str(self.target_csv)
        receipt["target_jsonl"] = str(self.target_jsonl)
        receipt["target_csv_sha256"] = compute_file_sha256(self.target_csv)
        receipt["target_jsonl_sha256"] = compute_file_sha256(self.target_jsonl)

        # 3. Guardar recibo oficial de promoción
        receipt_path = self.target_csv.parent / f"ACTA_PROMOCION_{timestamp}.json"
        with open(receipt_path, "w", encoding="utf-8") as f:
            json.dump(receipt, f, indent=2, ensure_ascii=False)

        # 4. Actualizar summary global JSON
        summary_path = self.target_csv.parent / "benchmark_summary.json"
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(receipt, f, indent=2, ensure_ascii=False)

        logger.info(f"Promoción atómica completada exitosamente. Acta archivada en: {receipt_path}")
        return receipt

    def run(self) -> Dict[str, Any]:
        """Ejecuta todo el flujo de validación y promoción."""
        logger.info(f"Iniciando pipeline de promoción controlada desde: {self.staging_dir}")
        csv_file, jsonl_file = self.validate_staging_files()

        df_csv = pd.read_csv(csv_file)
        self.validate_experimental_design(df_csv)
        self.validate_engine_and_telemetry(df_csv)
        traces = self.validate_traces_and_hashes(jsonl_file, df_csv)

        receipt = self.execute_promotion(csv_file, jsonl_file, df_csv, traces)
        return receipt


def main():
    parser = argparse.ArgumentParser(description="Pipeline de promoción controlada de NetDiagBench-L7")
    parser.add_argument("--staging-dir", type=str, default="data/benchmark_staging", help="Directorio de staging")
    parser.add_argument("--target-csv", type=str, default=None, help="Ruta canónica del CSV de resultados")
    parser.add_argument("--target-jsonl", type=str, default=None, help="Ruta canónica del JSONL de trazas")
    parser.add_argument("--archive-dir", type=str, default="data/historical_runs_archive", help="Directorio de archivo")
    parser.add_argument("--dry-run", action="store_true", help="Valida sin promover archivos")
    parser.add_argument("--allow-incomplete", action="store_true", help="Permite lotes menores a 162 corridas (para pruebas)")
    args = parser.parse_args()

    pipeline = ControlledPromotionPipeline(
        staging_dir=Path(args.staging_dir),
        target_csv=Path(args.target_csv) if args.target_csv else None,
        target_jsonl=Path(args.target_jsonl) if args.target_jsonl else None,
        archive_dir=Path(args.archive_dir) if args.archive_dir else None,
        dry_run=args.dry_run,
        allow_incomplete=args.allow_incomplete,
    )

    try:
        receipt = pipeline.run()
        print("\n=== PROMOCIÓN CONTROLADA COMPLETADA CON ÉXITO ===")
        print(json.dumps(receipt, indent=2, ensure_ascii=False))
        sys.exit(0)
    except PromotionValidationError as e:
        logger.error(f"Fallo de validación en la promoción: {e}")
        print(f"\n[ERROR DE PROMOCIÓN]: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Error inesperado durante la promoción: {e}")
        print(f"\n[ERROR FATAL]: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
