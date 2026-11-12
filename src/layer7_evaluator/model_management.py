"""
NetDiagBench-L7: Layer 7 - Gestión de Modelos para Informes y Ciclo de Vida
Provee:
  1. Selección persistente de modelos para los informes (Comparativo OE4,
     Análisis Correlacional 4.1.2 e Informe Consolidado) y sus entregables
     (Excel, PDF, HTML, JSON).
  2. Eliminación en cascada de un modelo: configuración, registro del motor de
     inferencia, filas del dataset ``resultados.csv`` (con respaldo previo),
     artefactos por modelo (CSV/MD/PDF/JSON de corridas), pesos en Ollama
     (opcional) y regeneración de los informes derivados y del dataset bundle.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.core.config import CONFIGS_DIR, PROJECT_ROOT, SystemConfig
from src.core.logger import logger

RESULTS_DIR = PROJECT_ROOT / "data" / "benchmark_results"
RUNS_DIR = PROJECT_ROOT / "data" / "runs"
CSV_PATH = RESULTS_DIR / "resultados.csv"
BUNDLE_PATH = RESULTS_DIR / "dataset_bundle.json"
BACKUP_DIR = RESULTS_DIR / "backups"
SELECTION_PATH = CONFIGS_DIR / "report_selection.json"

# Archivos maestros que nunca deben eliminarse al borrar un modelo
_PROTECTED_FILES = {"resultados.csv", "dataset_bundle.json"}


# ── Utilidades de lectura del dataset ────────────────────────────────────

def result_counts_by_model(csv_path: Path = CSV_PATH) -> dict[str, int]:
    """Devuelve el número de corridas registradas en el dataset por cada model_id."""
    counts: dict[str, int] = {}
    if not csv_path.exists():
        return counts
    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            mid = (row.get("model_id") or "").strip()
            if mid:
                counts[mid] = counts.get(mid, 0) + 1
    return counts


def list_report_models() -> list[dict[str, Any]]:
    """
    Lista la unión de modelos registrados en el sistema y modelos con resultados
    en el dataset, indicando si son de la terna base y cuántas corridas tienen.
    """
    cfg = SystemConfig()
    counts = result_counts_by_model()
    base_ids = {m.id for m in cfg.models}
    registered = {m.id: m for m in cfg.get_all_models()}

    items: dict[str, dict[str, Any]] = {}
    for mid, m in registered.items():
        n_runs = counts.get(mid, 0) + (counts.get(m.ollama_tag, 0) if m.ollama_tag != mid else 0)
        items[mid] = {
            "id": mid,
            "name": m.name,
            "ollama_tag": m.ollama_tag,
            "parameters": m.parameters_raw,
            "is_base": mid in base_ids,
            "registered": True,
            "n_runs": n_runs,
        }
    tags = {m.ollama_tag for m in registered.values()}
    for mid, n in counts.items():
        if mid in items or mid in tags:
            continue
        items[mid] = {
            "id": mid,
            "name": mid,
            "ollama_tag": mid,
            "parameters": "",
            "is_base": False,
            "registered": False,
            "n_runs": n,
        }
    return sorted(items.values(), key=lambda x: (not x["is_base"], x["id"]))


# ── Selección de modelos para los informes ───────────────────────────────

def get_report_selection() -> list[str]:
    """Devuelve la selección persistida ([] = todos los modelos con resultados)."""
    if not SELECTION_PATH.exists():
        return []
    try:
        data = json.loads(SELECTION_PATH.read_text(encoding="utf-8"))
        return [str(x) for x in (data.get("models") or [])]
    except Exception:
        return []


def set_report_selection(model_ids: list[str]) -> list[str]:
    """
    Persiste la selección de modelos para los informes. Solo se conservan
    modelos con resultados en el dataset.
    """
    available = set(result_counts_by_model().keys())
    clean = sorted({m for m in model_ids if m in available})
    SELECTION_PATH.parent.mkdir(parents=True, exist_ok=True)
    SELECTION_PATH.write_text(
        json.dumps(
            {"models": clean, "updated_at": datetime.now(timezone.utc).isoformat()},
            indent=2, ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return clean if clean else sorted(available)


def resolve_models(models_param: str | list[str] | None = None) -> list[str] | None:
    """
    Resuelve el filtro de modelos efectivo:
      - ``models_param`` explícito ("a,b", ["a", "b"] o "all") tiene prioridad.
      - En su defecto se usa la selección persistida.
    Devuelve lista de modelos o None si no hay selección y se usa la terna base oficial.
    """
    available = set(result_counts_by_model().keys())
    if models_param is not None:
        if isinstance(models_param, str):
            clean_str = models_param.strip().lower()
            if clean_str in ("all", "*", "todos"):
                return sorted(available)
            if clean_str in ("none", ""):
                return None
            requested = [m.strip() for m in models_param.split(",") if m.strip()]
        elif isinstance(models_param, (list, tuple, set)):
            requested = [str(m).strip() for m in models_param if str(m).strip()]
        else:
            requested = get_report_selection()
    else:
        requested = get_report_selection()

    chosen = [m for m in requested if m in available]
    if not chosen:
        return None
    return sorted(set(chosen))


OFFICIAL_TERNA_MODELS = ["qwen3-8b", "glm-4-9b-chat", "phi-4-mini-instruct"]

def load_selected_rows(models_param: str | list[str] | None = None) -> tuple[list[dict[str, Any]], list[str]]:
    """Carga las filas del dataset filtradas por la selección efectiva de modelos."""
    from src.layer7_evaluator.statistical_analysis import load_benchmark_csv

    rows = load_benchmark_csv(CSV_PATH) if CSV_PATH.exists() else []
    models = resolve_models(models_param)
    if models is not None:
        allowed = set(models)
        rows = [r for r in rows if r["model_id"] in allowed]
    else:
        # Por defecto consolidar los 162 registros de la terna oficial si están presentes
        allowed = set(OFFICIAL_TERNA_MODELS)
        official_rows = [r for r in rows if r.get("model_id") in allowed]
        rows = official_rows if official_rows else rows
    included = sorted({r["model_id"] for r in rows})
    return rows, included


def selection_signature(models_param: str | list[str] | None = None) -> str:
    """Firma estable de la selección efectiva (para claves de caché)."""
    models = resolve_models(models_param)
    return "ALL" if models is None else ",".join(models)


# ── Dataset bundle (FAIR / Zenodo) ───────────────────────────────────────

def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest().upper()


def refresh_dataset_bundle(full: bool = True) -> None:
    """
    Sincroniza ``dataset_bundle.json`` con el estado actual del dataset:
    huellas SHA-256 y (si ``full``) los resultados agregados de todos los modelos.
    """
    if not BUNDLE_PATH.exists() or not CSV_PATH.exists():
        return
    try:
        bundle = json.loads(BUNDLE_PATH.read_text(encoding="utf-8"))
        fingerprints = bundle.get("file_integrity_fingerprints_sha256", {}) or {}
        for rel in list(fingerprints.keys()) or ["data/benchmark_results/resultados.csv"]:
            p = PROJECT_ROOT / rel
            if p.exists():
                fingerprints[rel] = _sha256(p)
        fingerprints["data/benchmark_results/resultados.csv"] = _sha256(CSV_PATH)
        bundle["file_integrity_fingerprints_sha256"] = fingerprints

        if full:
            from src.layer7_evaluator.statistical_analysis import (
                build_aggregated_results,
                load_benchmark_csv,
            )
            import csv
            all_rows = load_benchmark_csv(CSV_PATH)
            # Sincronizar esquema de columnas del dataset exactamente con CSV_PATH
            with open(CSV_PATH, "r", encoding="utf-8") as f_csv:
                csv_cols = next(csv.reader(f_csv))
            old_schema = bundle.get("dataset_schema", {}).get("columns", {})
            new_schema = {}
            for c in csv_cols:
                new_schema[c] = old_schema.get(c, f"Métrica / atributo {c} del benchmark experimental")
            bundle.setdefault("dataset_schema", {})["columns"] = new_schema
            # Filtrar y consolidar exclusivamente los 162 registros de la terna oficial
            official_set = {"qwen3-8b", "glm-4-9b-chat", "phi-4-mini-instruct"}
            official_rows = [r for r in all_rows if r.get("model_id") in official_set]
            bundle["aggregated_results"] = build_aggregated_results(official_rows)
            if "benchmark_protocol" in bundle:
                bundle["benchmark_protocol"]["total_runs"] = len(official_rows)

        BUNDLE_PATH.write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as ex:
        logger.warning(f"No se pudo sincronizar dataset_bundle.json: {ex}")


# ── Entregables según la selección ───────────────────────────────────────

def regenerate_report_markdowns(models_param: str | None = None) -> dict[str, str]:
    """
    Regenera los informes Markdown fuente (comparativo y correlacional) para la
    selección efectiva de modelos. Devuelve el texto de ambos informes.
    """
    from src.layer7_evaluator.statistical_analysis import (
        build_comparative_summary,
        generate_comparative_markdown,
        generate_correlation_report,
        run_correlation_analysis,
    )

    rows, _ = load_selected_rows(models_param)
    comp_md = generate_comparative_markdown(
        build_comparative_summary(rows=rows),
        output_path=RESULTS_DIR / "resultados_resumen.md",
    )
    corr_md = generate_correlation_report(
        analysis=run_correlation_analysis(rows=rows),
        output_path=RESULTS_DIR / "analisis_correlacional.md",
    )
    return {"comparative": comp_md, "correlation": corr_md}


def export_selection_json(models_param: str | None = None, output_path: Path | None = None) -> Path:
    """
    Exporta en JSON los informes de la selección: metadatos, resumen comparativo
    (OE4), análisis correlacional (4.1.2), resultados agregados y dataset granular.
    """
    from src.layer7_evaluator.statistical_analysis import (
        build_aggregated_results,
        build_comparative_summary,
        run_correlation_analysis,
    )

    if output_path is None:
        output_path = RESULTS_DIR / "informe_modelos_seleccionados.json"

    rows, included = load_selected_rows(models_param)
    corr = run_correlation_analysis(rows=rows) if rows else {}
    if corr:
        corr = dict(corr)
        corr["bootstrap_ci_95"] = {
            mid: {mk: list(v) for mk, v in metrics.items()}
            for mid, metrics in corr.get("bootstrap_ci_95", {}).items()
        }

    payload = {
        "name": "NetDiagBench-L7 - Informe de Modelos Seleccionados",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "models_included": included,
        "n_runs": len(rows),
        "comparative_report_oe4": build_comparative_summary(rows=rows) if rows else {},
        "correlation_analysis_4_1_2": corr,
        "aggregated_results": build_aggregated_results(rows),
        "dataset": [{k: v for k, v in r.items()} for r in rows],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return output_path


# ── Eliminación en cascada de un modelo ──────────────────────────────────

def _model_file_pattern(model_id: str) -> re.Pattern[str]:
    """Coincide con nombres de archivo que contienen el id delimitado por '_' o '.'."""
    return re.compile(rf"(^|_){re.escape(model_id)}(_|\.)")


def _purge_ollama_model(tag: str, base_url: str) -> str:
    """Elimina los pesos del modelo en Ollama (CLI con respaldo HTTP)."""
    try:
        proc = subprocess.run(
            ["ollama", "rm", tag], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=120,
        )
        if proc.returncode == 0:
            return f"Pesos de '{tag}' eliminados de Ollama."
        detail = proc.stderr.strip() or proc.stdout.strip()
        return f"Ollama no eliminó '{tag}': {detail}"
    except FileNotFoundError:
        try:
            import httpx
            resp = httpx.request("DELETE", f"{base_url}/api/delete", json={"model": tag}, timeout=60.0)
            if resp.status_code == 200:
                return f"Pesos de '{tag}' eliminados de Ollama (API HTTP)."
            return f"Ollama API respondió {resp.status_code}: {resp.text[:200]}"
        except Exception as ex:
            return f"No se pudo contactar Ollama para eliminar '{tag}': {ex}"
    except Exception as ex:
        return f"Error al eliminar '{tag}' de Ollama: {ex}"


def delete_model(
    model_id: str,
    purge_ollama: bool = False,
    system_config: SystemConfig | None = None,
    inference_engine: Any = None,
) -> dict[str, Any]:
    """
    Elimina un modelo y todo lo relacionado con él:
      1. Respaldo de ``resultados.csv`` y eliminación de sus corridas del dataset.
      2. Artefactos por modelo en ``data/benchmark_results`` y ``data/runs``.
      3. Registro en la configuración (dynamic_models.json / removed_models.json).
      4. Registro en memoria del motor de inferencia.
      5. Selección de informes.
      6. Pesos en Ollama (opcional).
      7. Regeneración de informes Markdown y del dataset bundle.
    """
    cfg = system_config or SystemConfig()
    model_def = next(
        (m for m in cfg.get_all_models() if m.id == model_id or m.ollama_tag == model_id),
        None,
    )
    match_ids = {model_id}
    if model_def is not None:
        match_ids.update({model_def.id, model_def.ollama_tag})

    counts = result_counts_by_model()
    if model_def is None and not any(mid in counts for mid in match_ids):
        raise ValueError(f"El modelo '{model_id}' no existe en el sistema ni en el dataset.")

    report: dict[str, Any] = {
        "model_id": model_def.id if model_def else model_id,
        "ollama_tag": model_def.ollama_tag if model_def else model_id,
        "was_base_model": bool(model_def and model_def.id in {m.id for m in cfg.models}),
        "csv_rows_removed": 0,
        "backup_file": None,
        "files_removed": [],
        "dirs_removed": [],
        "config_removed": False,
        "ollama": "No solicitado",
    }

    # 1. Dataset maestro (con respaldo previo)
    if CSV_PATH.exists():
        with open(CSV_PATH, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or []
            all_rows = list(reader)
        keep = [r for r in all_rows if (r.get("model_id") or "").strip() not in match_ids]
        removed = len(all_rows) - len(keep)
        if removed:
            BACKUP_DIR.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_id = re.sub(r"[^a-zA-Z0-9_.-]", "-", report["model_id"])
            backup = BACKUP_DIR / f"resultados_{stamp}_antes_de_eliminar_{safe_id}.csv"
            shutil.copy2(CSV_PATH, backup)
            with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(keep)
            report["csv_rows_removed"] = removed
            report["backup_file"] = str(backup.relative_to(PROJECT_ROOT))

    # 2. Artefactos por modelo
    file_ids = {re.sub(r"[^a-zA-Z0-9_.-]", "-", i) for i in match_ids} | match_ids
    patterns = [_model_file_pattern(i) for i in file_ids]
    for folder in (RESULTS_DIR, RUNS_DIR):
        if not folder.exists():
            continue
        for p in folder.iterdir():
            if p.is_dir():
                if folder == RUNS_DIR and p.name in file_ids:
                    shutil.rmtree(p, ignore_errors=True)
                    report["dirs_removed"].append(str(p.relative_to(PROJECT_ROOT)))
                continue
            if p.name in _PROTECTED_FILES:
                continue
            if any(pt.search(p.name) for pt in patterns):
                try:
                    p.unlink()
                    report["files_removed"].append(str(p.relative_to(PROJECT_ROOT)))
                except Exception as ex:
                    logger.warning(f"No se pudo eliminar {p}: {ex}")

    # 3. Configuración
    if model_def is not None:
        report["config_removed"] = cfg.remove_model(model_def.id) is not None

    # 4. Motor de inferencia en memoria
    if inference_engine is not None:
        for i in match_ids:
            try:
                inference_engine.unregister_model(i)
            except Exception:
                pass

    # 5. Selección de informes
    current = get_report_selection()
    if current and any(i in current for i in match_ids):
        remaining = [m for m in current if m not in match_ids]
        if remaining:
            set_report_selection(remaining)
        elif SELECTION_PATH.exists():
            SELECTION_PATH.unlink()

    # 6. Pesos en Ollama (opcional)
    if purge_ollama:
        base_url = getattr(inference_engine, "ollama_base_url", "http://127.0.0.1:11434")
        report["ollama"] = _purge_ollama_model(report["ollama_tag"], base_url)

    # 7. Informes derivados
    try:
        from src.layer7_evaluator import statistical_analysis as sa
        sa.get_model_parameter_count.cache_clear()
        sa.get_model_size_label.cache_clear()
        if CSV_PATH.exists() and result_counts_by_model():
            regenerate_report_markdowns()
        refresh_dataset_bundle(full=True)
    except Exception as ex:
        logger.warning(f"Regeneración de informes tras eliminar el modelo falló: {ex}")

    logger.info(f"Modelo eliminado: {report}")
    return report
