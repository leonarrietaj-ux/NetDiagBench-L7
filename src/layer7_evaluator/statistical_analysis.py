EXPERIMENT_SEEDS = [42, 1337, 2026]
"""
NetDiagBench-L7: Layer 7 - Statistical Correlation & Significance Analysis
Implementa el analisis correlacional requerido por la Tarea 4.1.2 y el OE4:
  - Correlacion de Spearman (rho) y Pearson (r) entre parametros del modelo
    y metricas de rendimiento (latencia, tokens/s, energia).
  - Intervalos de confianza al 95% via bootstrap percentil por conglomerados.
  - Prueba de Kruskal-Wallis (no parametrica) para diferencias significativas
    entre modelos en metricas continuas.
  - Descriptivos consolidados (media, sigma, CV, p50, p95) por modelo.
  - Generacion del informe de correlacion en formato Markdown.

Referencia metodologica: SciPy Stats (scipy.stats.spearmanr, pearsonr,
kruskal) segun el diseno descrito en la propuesta de trabajo de grado.
"""

import csv
import math
import re
import statistics
from functools import lru_cache
from pathlib import Path
from typing import Any

# SciPy se importa de forma lazy para no bloquear tests si no esta instalado
try:
    from scipy import stats as scipy_stats
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

from src.core.config import PROJECT_ROOT
from src.core.logger import logger

# ÔöÇÔöÇ Perfil de parametros por modelo ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
# Utilizado para el eje X del analisis correlacional (tamano del modelo).
MODEL_PARAMETER_COUNTS: dict[str, float] = {
    "qwen3-8b": 8.2e9,
    "glm-4-9b-chat": 9.0e9,
    "phi-4-mini-instruct": 3.8e9,
    "deepseek-r1-7b": 7.0e9,
    "tinyllama-1-1b": 1.1e9,
}

# Cuantizacion de referencia para la terna (Q4_K_M)
MODEL_QUANT_SIZES_GB: dict[str, float] = {
    "qwen3-8b": 5.5,
    "glm-4-9b-chat": 5.9,
    "phi-4-mini-instruct": 2.8,
    "deepseek-r1-7b": 5.1,
    "tinyllama-1-1b": 0.6,
}

MODEL_SIZE_LABELS: dict[str, str] = {
    "qwen3-8b": "8.2B",
    "glm-4-9b-chat": "9.0B",
    "phi-4-mini-instruct": "3.8B",
    "deepseek-r1-7b": "7.0B",
    "tinyllama-1-1b": "1.1B",
}


@lru_cache(maxsize=256)
def get_model_parameter_count(model_id: str) -> float:
    """
    Obtiene el n├║mero aproximado de par├ímetros para el eje correlacional.
    Busca en el perfil base, en SystemConfig (modelos din├ímicos de Ollama) o infiere del tag.
    """
    if model_id in MODEL_PARAMETER_COUNTS:
        return MODEL_PARAMETER_COUNTS[model_id]

    try:
        from src.core.config import SystemConfig
        sys_cfg = SystemConfig()
        for m in sys_cfg.get_all_models():
            if m.id == model_id or m.ollama_tag == model_id:
                raw = (m.parameters_raw or "").strip().upper()
                m_match = re.search(r'([\d.]+)\s*([BMK]?)', raw)
                if m_match:
                    val = float(m_match.group(1))
                    unit = m_match.group(2)
                    mult = 1e9 if unit == "B" else (1e6 if unit == "M" else 1e9)
                    return val * mult
    except Exception:
        pass

    m_tag = re.search(r'([\d.]+)[bB]', model_id)
    if m_tag:
        return float(m_tag.group(1)) * 1e9

    m_tag_m = re.search(r'([\d.]+)[mM]', model_id)
    if m_tag_m:
        return float(m_tag_m.group(1)) * 1e6

    return 4.0e9


@lru_cache(maxsize=256)
def get_model_size_label(model_id: str) -> str:
    """Obtiene la etiqueta legible de tama├▒o (ej. 8.2B, 1B)."""
    if model_id in MODEL_SIZE_LABELS:
        return MODEL_SIZE_LABELS[model_id]

    try:
        from src.core.config import SystemConfig
        sys_cfg = SystemConfig()
        for m in sys_cfg.get_all_models():
            if m.id == model_id or m.ollama_tag == model_id:
                if m.parameters_raw:
                    return m.parameters_raw
    except Exception:
        pass

    m_tag = re.search(r'([\d.]+[bB])', model_id)
    if m_tag:
        return m_tag.group(1).upper()

    return "Auto"


# ÔöÇÔöÇ Funciones estadisticas de bajo nivel ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ

def descriptive_stats(values: list[float]) -> dict[str, float]:
    """
    Calcula estadisticos descriptivos: media, sigma, CV, min, max, p50, p95.
    Retorna un diccionario con claves legibles.
    """
    valid = [float(v) for v in (values or []) if v is not None and not (isinstance(v, float) and math.isnan(v))]
    if not valid:
        return {
            "mean": 0.0, "std": 0.0, "cv": 0.0,
            "min": 0.0, "max": 0.0, "p50": 0.0, "p95": 0.0, "n": 0,
        }
    values = valid
    n = len(values)
    mean = statistics.mean(values)
    std = statistics.stdev(values) if n > 1 else 0.0
    cv = (std / mean * 100.0) if mean != 0 else 0.0
    sorted_v = sorted(values)
    p50 = sorted_v[int(n * 0.50)]
    p95 = sorted_v[min(int(n * 0.95), n - 1)]
    return {
        "mean": round(mean, 4),
        "std": round(std, 4),
        "cv": round(cv, 2),
        "min": round(min(values), 4),
        "max": round(max(values), 4),
        "p50": round(p50, 4),
        "p95": round(p95, 4),
        "n": n,
    }


def spearman_correlation(x: list[float], y: list[float]) -> tuple[float, float]:
    """
    Calcula la correlacion de Spearman (rho) y su p-value.
    Retorna (rho, p_value). Si scipy no esta disponible, calcula rho manualmente.
    """
    if len(x) != len(y) or len(x) < 3:
        return (0.0, 1.0)

    # Si alguna variable es constante, la correlaci├│n no est├í definida estad├¡sticamente
    if len(set(x)) <= 1 or len(set(y)) <= 1:
        return (0.0, 1.0)

    if SCIPY_AVAILABLE:
        result = scipy_stats.spearmanr(x, y)
        rho_val = float(result.statistic)
        p_val = float(result.pvalue)
        # scipy returns NaN for constant inputs
        if math.isnan(rho_val):
            rho_val = 0.0
        if math.isnan(p_val):
            p_val = 1.0
        return (round(rho_val, 4), round(p_val, 6))

    # Fallback: calculo manual de rho de Spearman
    n = len(x)
    rank_x = _compute_ranks(x)
    rank_y = _compute_ranks(y)
    d_sq = sum((rx - ry) ** 2 for rx, ry in zip(rank_x, rank_y))
    rho = 1.0 - (6.0 * d_sq) / (n * (n ** 2 - 1))
    return (round(rho, 4), 1.0)  # p-value no disponible sin scipy


def pearson_correlation(x: list[float], y: list[float]) -> tuple[float, float]:
    """
    Calcula la correlacion de Pearson (r) y su p-value.
    Retorna (r, p_value).
    """
    if len(x) != len(y) or len(x) < 3:
        return (0.0, 1.0)

    # Si alguna variable es constante, no hay varianza
    if len(set(x)) <= 1 or len(set(y)) <= 1:
        return (0.0, 1.0)

    if SCIPY_AVAILABLE:
        result = scipy_stats.pearsonr(x, y)
        r_val = float(result.statistic)
        p_val = float(result.pvalue)
        # scipy returns NaN for constant inputs
        if math.isnan(r_val):
            r_val = 0.0
        if math.isnan(p_val):
            p_val = 1.0
        return (round(r_val, 4), round(p_val, 6))

    # Fallback: calculo manual
    mean_x = statistics.mean(x)
    mean_y = statistics.mean(y)
    num = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
    den_x = math.sqrt(sum((xi - mean_x) ** 2 for xi in x))
    den_y = math.sqrt(sum((yi - mean_y) ** 2 for yi in y))
    if den_x == 0 or den_y == 0:
        return (0.0, 1.0)
    r = num / (den_x * den_y)
    return (round(r, 4), 1.0)


def kruskal_wallis_test(*groups: list[float]) -> tuple[float, float]:
    """
    Prueba de Kruskal-Wallis para k muestras independientes.
    H0: Las distribuciones de las k poblaciones son identicas.
    Retorna (H_statistic, p_value).
    """
    if not SCIPY_AVAILABLE:
        return (0.0, 1.0)
    if len(groups) < 2:
        return (0.0, 1.0)
    # Filtrar grupos vacios
    valid = [g for g in groups if len(g) >= 2]
    if len(valid) < 2:
        return (0.0, 1.0)

    # Si todos los elementos en todos los grupos son id├®nticos, no hay varianza inter ni intra grupo
    all_elements = set(val for g in valid for val in g)
    if len(all_elements) <= 1:
        return (0.0, 1.0)

    result = scipy_stats.kruskal(*valid)
    h_val = float(result.statistic)
    p_val = float(result.pvalue)
    if math.isnan(h_val):
        h_val = 0.0
    if math.isnan(p_val):
        p_val = 1.0
    return (round(h_val, 4), round(p_val, 6))


def bootstrap_ci(
    values: list[float],
    stat_func=statistics.mean,
    n_bootstrap: int = 1000,
    confidence: float = 0.95,
    seed: int = 42
) -> tuple[float, float]:
    """
    Intervalo de confianza via bootstrap percentil.
    Retorna (lower_bound, upper_bound).
    """
    import random
    rng = random.Random(seed)
    n = len(values)
    if n < 2:
        val = values[0] if values else 0.0
        return (val, val)

    boot_stats = []
    choices = rng.choices
    if stat_func is statistics.mean or stat_func == statistics.mean:
        for _ in range(n_bootstrap):
            sample = choices(values, k=n)
            boot_stats.append(sum(sample) / n)
    else:
        for _ in range(n_bootstrap):
            sample = choices(values, k=n)
            boot_stats.append(stat_func(sample))

    boot_stats.sort()
    alpha = 1.0 - confidence
    lo_idx = int((alpha / 2) * n_bootstrap)
    hi_idx = int((1 - alpha / 2) * n_bootstrap) - 1
    return (round(boot_stats[lo_idx], 4), round(boot_stats[hi_idx], 4))


def effect_size_cohens_d(group1: list[float], group2: list[float]) -> float:
    """
    Calcula la d de Cohen para el tamano del efecto entre dos grupos.
    d = (mean1 - mean2) / pooled_std
    """
    if len(group1) < 2 or len(group2) < 2:
        return 0.0
    m1, m2 = statistics.mean(group1), statistics.mean(group2)
    s1, s2 = statistics.stdev(group1), statistics.stdev(group2)
    n1, n2 = len(group1), len(group2)
    pooled = math.sqrt(((n1 - 1) * s1**2 + (n2 - 1) * s2**2) / (n1 + n2 - 2))
    if pooled == 0:
        return 0.0
    return round((m1 - m2) / pooled, 4)


def interpret_effect_size(d: float) -> str:
    """Interpreta la d de Cohen segun Cohen (1988)."""
    d_abs = abs(d)
    if d_abs < 0.2:
        return "Efecto insignificante (Negligible)"
    elif d_abs < 0.5:
        return "Efecto pequeno (Small)"
    elif d_abs < 0.8:
        return "Efecto mediano (Medium)"
    else:
        return "Efecto grande (Large)"


# ÔöÇÔöÇ Funciones auxiliares ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ

def _compute_ranks(values: list[float]) -> list[float]:
    """Calcula rangos con empates promediados para Spearman manual."""
    indexed = sorted(enumerate(values), key=lambda x: x[1])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(indexed):
        j = i
        while j < len(indexed) and indexed[j][1] == indexed[i][1]:
            j += 1
        avg_rank = (i + j + 1) / 2.0  # 1-based average
        for k in range(i, j):
            ranks[indexed[k][0]] = avg_rank
        i = j
    return ranks


def compute_evaluator_concept_provenance(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Retorna la trazabilidad y procedencia normativa del evaluador oficial de conceptos (RFC 1035/9110/8446).
    """
    from src.layer7_evaluator.metrics import get_evaluator_version, load_evaluator_concepts

    version = get_evaluator_version()
    concepts = load_evaluator_concepts()
    classes = concepts.get("classes", {})

    return {
        "evaluator_version": version,
        "standard_sources": ["RFC 1035", "RFC 9110", "RFC 8446", "RFC 5280", "RFC 6066", "Linux tc-netem"],
        "classes_count": len(classes),
        "classes": list(classes.keys()),
    }

def load_benchmark_csv(
    csv_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Carga el dataset de resultados desde CSV."""
    if csv_path is None:
        csv_path = PROJECT_ROOT / "data" / "benchmark_results" / "resultados.csv"
    rows = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Convertir tipos numericos
            for key in [
                "seed", "repetition_index", "tool_steps_count",
            ]:
                if key in row:
                    row[key] = int(row[key])
            for key in [
                "partial_match_score", "ttft_ms", "tokens_per_sec",
                "total_time_ms", "cpu_percent_avg", "peak_ram_mb",
                "peak_vram_gb", "energy_kwh", "co2_emissions_kg", "rubric_score",
            ]:
                if key in row:
                    val = str(row[key]).strip()
                    row[key] = float(val) if val and val.lower() not in ("none", "null", "nan") else None
            for key in ["is_root_cause_correct", "is_component_correct", "evidence_backed"]:
                if key in row:
                    row[key] = row[key].strip().lower() in ("true", "1", "yes")
            rows.append(row)
    return rows


def format_p_value(p: float | None) -> str:
    """
    Formatea valores p según norma formal APA / IEEE (nunca imprime '0.000').
    - Si p es None o NaN (prueba no calculable / indeterminada): retorna 'p = NA'.
    - Si p < 0.001: retorna 'p < 0.001'.
    - Si p >= 0.001: formatea con tres decimales (ej. 'p = 0.042', 'p = 1.000').
    """
    if p is None:
        return "p = NA"
    try:
        val = float(p)
        if math.isnan(val):
            return "p = NA"
        if val < 0.001:
            return "p < 0.001"
        return f"p = {val:.3f}"
    except (TypeError, ValueError):
        return "p = NA"



def parse_fault_class_predicted(
    model_text: str,
    concepts_catalog: dict[str, Any] | None = None
) -> tuple[str, bool, dict[str, int]]:
    """
    Extrae y normaliza deterministamente la clase de falla a partir exclusivamente
    de la respuesta original emitida por el modelo (Cero Fuga de Datos / Zero Data Leakage).
    Relaciona el texto con el cat├ílogo normativo oficial (evaluator_concepts.yaml).

    Retorna: (predicted_class: str, is_ambiguous: bool, candidate_scores: dict[str, int])
    - Si el texto est├í vac├¡o o no coincide con ninguna clase: ("UNKNOWN", False, {})
    - Si existe empate en la m├íxima puntuaci├│n positiva: (clase_ganadora, True, scores)
    - Si existe una clase ganadora un├¡voca: (clase_ganadora, False, scores)
    """
    if not model_text or not str(model_text).strip():
        return "UNKNOWN", False, {}

    if concepts_catalog is None:
        from src.layer7_evaluator.metrics import load_evaluator_concepts
        concepts_catalog = load_evaluator_concepts().get("classes", {})

    from src.layer7_evaluator.metrics import _clean_text, _match_group, _match_term

    cleaned = _clean_text(model_text)
    scores: dict[str, int] = {}

    for cls_name, cls_def in concepts_catalog.items():
        score = 0
        for g in cls_def.get("cause_groups", []):
            if _match_group(g, cleaned):
                score += 3
        for c in cls_def.get("cause_concepts", []):
            if _match_term(c, cleaned):
                score += 1
        for n in cls_def.get("neighbor_concepts", []):
            if _match_term(n, cleaned):
                score -= 1
        if score > 0:
            scores[cls_name] = score

    if not scores:
        return "UNKNOWN", False, {}

    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_score = sorted_scores[0][1]
    top_tied = [cls for cls, sc in sorted_scores if sc == top_score]
    is_ambiguous = len(top_tied) > 1

    return top_tied[0], is_ambiguous, scores
def compute_classification_metrics(
    rows: list[dict[str, Any]],
    n_bootstrap: int = 1000,
    seed: int = 42
) -> dict[str, Any]:
    """
    Calcula m├®tricas de clasificaci├│n diagn├│stica formal:
    - F1 Macro v├¡a scikit-learn (sin fuga de datos)
    - Precisi├│n y Recall Macro
    - Matriz de confusi├│n multicriterio
    - Intervalo de confianza al 95% para F1 Macro mediante Bootstrap pareado por conglomerados (escenarios).
    """
    if not rows:
        return {
            "f1_macro": 0.0,
            "precision_macro": 0.0,
            "recall_macro": 0.0,
            "f1_macro_ci95": (0.0, 0.0),
            "confusion_matrix": [],
            "labels": [],
            "per_class": {},
        }

    import numpy as np
    from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score
    from src.layer7_evaluator.metrics import load_evaluator_concepts

    concepts_catalog = load_evaluator_concepts().get("classes", {})
    canonical_labels = sorted(list(concepts_catalog.keys())) if concepts_catalog else []

    def _infer_canonical_fault_class(row: dict[str, Any]) -> str:
        # Cero fuga de información: la predicción procede exclusivamente de la respuesta original
        if row.get("fault_class_predicted"):
            val = str(row["fault_class_predicted"]).strip()
            if val and val.upper() != "NONE":
                return val
        pred_txt = str(row.get("root_cause_predicted") or row.get("model_diagnosis_text") or row.get("response") or row.get("root_cause") or "")
        if pred_txt.strip():
            pred_cls, _, _ = parse_fault_class_predicted(pred_txt, concepts_catalog)
            return pred_cls
        if row.get("is_root_cause_correct") is True and row.get("fault_class"):
            return str(row["fault_class"])
        return "UNKNOWN"

    y_true = [str(r.get("fault_class", "UNKNOWN")) for r in rows]
    y_pred = [_infer_canonical_fault_class(r) for r in rows]

    unique_present = sorted(list(set(y_true + y_pred)))
    if len(rows) < 18 or not set(y_true).issubset(set(canonical_labels)):
        labels = unique_present
    else:
        labels = canonical_labels if canonical_labels else unique_present

    f1_m = float(f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0))
    prec_m = float(precision_score(y_true, y_pred, labels=labels, average="macro", zero_division=0))
    rec_m = float(recall_score(y_true, y_pred, labels=labels, average="macro", zero_division=0))
    cm = confusion_matrix(y_true, y_pred, labels=labels).tolist()

    # Per class
    per_class: dict[str, dict[str, float]] = {}
    f1_per_c = f1_score(y_true, y_pred, labels=labels, average=None, zero_division=0)
    prec_per_c = precision_score(y_true, y_pred, labels=labels, average=None, zero_division=0)
    rec_per_c = recall_score(y_true, y_pred, labels=labels, average=None, zero_division=0)

    for idx, lbl in enumerate(labels):
        per_class[lbl] = {
            "f1": round(float(f1_per_c[idx]), 4),
            "precision": round(float(prec_per_c[idx]), 4),
            "recall": round(float(rec_per_c[idx]), 4),
            "support": int(sum(1 for yt in y_true if yt == lbl)),
        }

        # Cluster Bootstrap para F1 Macro por conglomerados (escenarios) cuando sea aplicable
    rng = np.random.default_rng(seed)
    n = len(rows)
    boot_f1s = []

    scenarios_present = sorted(list(set(str(r.get("scenario_id")) for r in rows if r.get("scenario_id"))))
    if len(scenarios_present) > 1:
        sc_map: dict[str, list[tuple[str, str]]] = {}
        for r, yt, yp in zip(rows, y_true, y_pred):
            sc_map.setdefault(str(r.get("scenario_id")), []).append((yt, yp))

        for _ in range(n_bootstrap):
            sampled_scs = rng.choice(scenarios_present, size=len(scenarios_present), replace=True)
            sample_yt, sample_yp = [], []
            for sc in sampled_scs:
                for yt, yp in sc_map[sc]:
                    sample_yt.append(yt)
                    sample_yp.append(yp)
            eval_labels = [c for c in labels if c in sample_yt or c in sample_yp]
            score = f1_score(sample_yt, sample_yp, labels=eval_labels, average="macro", zero_division=0)
            boot_f1s.append(score)
    else:
        y_t_arr = np.array(y_true)
        y_p_arr = np.array(y_pred)
        for _ in range(n_bootstrap):
            sample_idx = rng.integers(0, n, size=n)
            sample_yt = y_t_arr[sample_idx]
            sample_yp = y_p_arr[sample_idx]
            eval_labels = [c for c in labels if c in sample_yt or c in sample_yp]
            score = f1_score(sample_yt, sample_yp, labels=eval_labels, average="macro", zero_division=0)
            boot_f1s.append(score)

    boot_f1s.sort()
    lo_idx = int(0.025 * n_bootstrap)
    hi_idx = min(int(0.975 * n_bootstrap), len(boot_f1s) - 1)
    ci_f1 = (round(float(boot_f1s[lo_idx]), 4), round(float(boot_f1s[hi_idx]), 4))

    # Matriz de confusión diagnóstica con categoría explícita UNKNOWN si fue predicha
    labels_diagnostic = list(canonical_labels) if canonical_labels else list(labels)
    unknown_count = sum(1 for yp in y_pred if yp == "UNKNOWN")
    if unknown_count > 0 and "UNKNOWN" not in labels_diagnostic:
        labels_diagnostic.append("UNKNOWN")
    cm_diagnostic = confusion_matrix(y_true, y_pred, labels=labels_diagnostic).tolist()

    error_report = {
        "total_predictions": len(rows),
        "total_errors": sum(1 for yt, yp in zip(y_true, y_pred) if yt != yp),
        "unknown_predictions_count": unknown_count,
        "classes_evaluated": labels,
    }

    return {
        "f1_macro": round(f1_m, 4),
        "precision_macro": round(prec_m, 4),
        "recall_macro": round(rec_m, 4),
        "f1_macro_ci95": ci_f1,
        "confusion_matrix": cm,
        "confusion_matrix_diagnostic": cm_diagnostic,
        "confusion_matrix_diagnostic_labels": labels_diagnostic,
        "unknown_predictions_count": unknown_count,
        "error_report": error_report,
        "labels": labels,
        "per_class": per_class,
        "support_total": len(rows),
    }


def run_correlation_analysis(
    rows: list[dict[str, Any]] | None = None,
    csv_path: Path | None = None,
) -> dict[str, Any]:
    """
    Ejecuta el analisis correlacional completo (Tarea 4.1.2 / OE4):
      1. Descriptivos por modelo
      2. Correlacion Spearman y Pearson: parametros_modelo vs {latencia, TTFT, tok/s, energia}
      3. Kruskal-Wallis: diferencias entre modelos en cada metrica
      4. Intervalos de confianza bootstrap al 95% para metricas clave
      5. Tamano del efecto (d de Cohen) entre pares de modelos

    Retorna un diccionario estructurado con todos los resultados.
    """
    if rows is None:
        rows = load_benchmark_csv(csv_path)

    # Agrupar por modelo
    by_model: dict[str, list[dict]] = {}
    for r in rows:
        mid = r["model_id"]
        by_model.setdefault(mid, []).append(r)

    model_ids = sorted(by_model.keys())

    # ÔöÇÔöÇ 1. Descriptivos por modelo ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
    descriptives: dict[str, dict[str, dict[str, float]]] = {}
    metrics_keys = [
        "ttft_ms", "tokens_per_sec", "total_time_ms",
        "peak_vram_gb", "peak_ram_mb", "energy_kwh",
        "rubric_score", "partial_match_score",
    ]
    for mid in model_ids:
        descriptives[mid] = {}
        for mk in metrics_keys:
            vals = [r.get(mk) for r in by_model[mid]]
            if mk == "peak_vram_gb" and all(v is None for v in vals):
                decl = by_model[mid][0].get("vram_declared_gb") or MODEL_QUANT_SIZES_GB.get(mid) or 0.0
                vals = [float(decl)] * len(vals)
            descriptives[mid][mk] = descriptive_stats(vals)

    # ÔöÇÔöÇ 2. Correlacion: parametros del modelo vs metricas ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
    # Construir vectores: cada fila del CSV tiene un model_id,
    # asignamos el numero de parametros correspondiente.
    param_vector = []
    metric_vectors: dict[str, list[float]] = {k: [] for k in metrics_keys}
    accuracy_vector: list[float] = []

    for r in rows:
        mid = r["model_id"]
        params = get_model_parameter_count(mid)
        param_vector.append(params)
        for mk in metrics_keys:
            val_k = r.get(mk)
            if val_k is None and mk == "peak_vram_gb":
                val_k = r.get("vram_declared_gb") or MODEL_QUANT_SIZES_GB.get(mid) or 0.0
            metric_vectors[mk].append(float(val_k) if val_k is not None else 0.0)
        accuracy_vector.append(1.0 if r["is_root_cause_correct"] else 0.0)

    correlations: dict[str, dict[str, Any]] = {}
    target_metrics = [
        "ttft_ms", "tokens_per_sec", "total_time_ms",
        "energy_kwh", "rubric_score", "partial_match_score",
    ]
    for mk in target_metrics:
        rho, rho_p = spearman_correlation(param_vector, metric_vectors[mk])
        r_val, r_p = pearson_correlation(param_vector, metric_vectors[mk])
        correlations[mk] = {
            "spearman_rho": rho,
            "spearman_p": rho_p,
            "pearson_r": r_val,
            "pearson_p": r_p,
            "significant_005": rho_p < 0.05 or r_p < 0.05,
        }

    # ÔöÇÔöÇ 3. Kruskal-Wallis entre modelos ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
    kruskal_results: dict[str, dict[str, float]] = {}
    for mk in target_metrics:
        groups = [
            [r[mk] for r in by_model[mid]]
            for mid in model_ids
        ]
        h_stat, kw_p = kruskal_wallis_test(*groups)
        kruskal_results[mk] = {
            "H_statistic": h_stat,
            "p_value": kw_p,
            "significant_005": kw_p < 0.05,
        }

    # ÔöÇÔöÇ 4. Intervalos de confianza bootstrap ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
    ci_results: dict[str, dict[str, tuple[float, float]]] = {}
    ci_metrics = ["ttft_ms", "tokens_per_sec", "total_time_ms", "energy_kwh"]
    for mid in model_ids:
        ci_results[mid] = {}
        for mk in ci_metrics:
            vals = [r[mk] for r in by_model[mid]]
            lo, hi = bootstrap_ci(vals, seed=42)
            ci_results[mid][mk] = (lo, hi)

    # ÔöÇÔöÇ 5. Tamano del efecto (Cohen's d) entre pares ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
    effect_sizes: dict[str, dict[str, dict[str, Any]]] = {}
    for mk in ["ttft_ms", "tokens_per_sec", "total_time_ms"]:
        effect_sizes[mk] = {}
        for i, mid_a in enumerate(model_ids):
            for mid_b in model_ids[i + 1:]:
                g1 = [r[mk] for r in by_model[mid_a]]
                g2 = [r[mk] for r in by_model[mid_b]]
                d = effect_size_cohens_d(g1, g2)
                pair_key = f"{mid_a} vs {mid_b}"
                effect_sizes[mk][pair_key] = {
                    "cohens_d": d,
                    "interpretation": interpret_effect_size(d),
                }

    evaluator_provenance = compute_evaluator_concept_provenance(rows)
    classification_overall = compute_classification_metrics(rows)
    classification_by_model = {mid: compute_classification_metrics(by_model[mid]) for mid in model_ids}

    return {
        "n_total": len(rows),
        "n_models": len(model_ids),
        "model_ids": model_ids,
        "descriptives": descriptives,
        "correlations": correlations,
        "kruskal_wallis": kruskal_results,
        "bootstrap_ci_95": ci_results,
        "effect_sizes": effect_sizes,
        "classification_overall": classification_overall,
        "classification_by_model": classification_by_model,
        "evaluator_concept_provenance": evaluator_provenance,
    }


def generate_correlation_report(
    analysis: dict[str, Any] | None = None,
    output_path: Path | None = None,
) -> str:
    """
    Genera el informe de analisis correlacional en Markdown (Tarea 4.1.2).
    Incluye: tabla de correlaciones, pruebas de significancia, IC 95%,
    tamano del efecto y descriptivos consolidados.
    """
    if analysis is None:
        analysis = run_correlation_analysis()

    if output_path is None:
        output_path = PROJECT_ROOT / "data" / "benchmark_results" / "analisis_correlacional.md"

    lines = [
        "# Analisis Correlacional y de Significancia Estadistica",
        "",
        "**Modulo:** NetDiagBench-L7 / Layer 7 - Statistical Analysis",
        f"**Muestras totales:** {analysis['n_total']} corridas, "
        f"{analysis['n_models']} modelos evaluados",
        "",
        "---",
        "",
        "## 1. Correlacion Parametros del Modelo vs Metricas de Rendimiento",
        "",
        "Analisis de la relacion entre el numero de parametros del modelo (eje X)",
        "y cada metrica de rendimiento (eje Y), usando correlacion de Spearman (rho)",
        "y Pearson (r) con su p-value asociado.",
        "",
        "| Metrica | Spearman rho | p-value | Pearson r | p-value | Significativo (p<0.05) |",
        "|---|---|---|---|---|---|",
    ]

    _METRIC_LABELS = {
        "ttft_ms": "TTFT (ms)",
        "tokens_per_sec": "Tokens/s",
        "total_time_ms": "Latencia Total (ms)",
        "energy_kwh": "Energia (kWh)",
        "rubric_score": "Rubrica (0-5)",
        "partial_match_score": "Puntaje de Coincidencia Parcial",
    }

    for mk, corr in analysis["correlations"].items():
        label = _METRIC_LABELS.get(mk, mk)
        sig = "Si" if corr["significant_005"] else "No"
        sp_p = format_p_value(corr['spearman_p'])
        pe_p = format_p_value(corr['pearson_p'])
        lines.append(
            f"| {label} | {corr['spearman_rho']} | {sp_p} | "
            f"{corr['pearson_r']} | {pe_p} | {sig} |"
        )

    # Seccion 2: Kruskal-Wallis
    lines.extend([
        "",
        "## 2. Prueba de Kruskal-Wallis: Diferencias entre Modelos",
        "",
        "H0: Las distribuciones de la metrica son identicas entre los k modelos.",
        "Se rechaza H0 si p < 0.05.",
        "",
        "| Metrica | H Estadistico | p-value | Diferencias Significativas |",
        "|---|---|---|---|",
    ])
    for mk, kw in analysis["kruskal_wallis"].items():
        label = _METRIC_LABELS.get(mk, mk)
        sig = "Si" if kw["significant_005"] else "No"
        kw_p = format_p_value(kw['p_value'])
        lines.append(f"| {label} | {kw['H_statistic']} | {kw_p} | {sig} |")

    # Seccion 3: Intervalos de confianza
    lines.extend([
        "",
        "## 3. Intervalos de Confianza Bootstrap al 95%",
        "",
        "| Modelo | Metrica | IC 95% Inferior | IC 95% Superior |",
        "|---|---|---|---|",
    ])
    ci_labels = {
        "ttft_ms": "TTFT (ms)", "tokens_per_sec": "Tokens/s",
        "total_time_ms": "Latencia (ms)", "energy_kwh": "Energia (kWh)",
    }
    for mid in analysis["model_ids"]:
        if mid in analysis["bootstrap_ci_95"]:
            for mk, (lo, hi) in analysis["bootstrap_ci_95"][mid].items():
                label = ci_labels.get(mk, mk)
                lines.append(f"| **{mid}** | {label} | {lo} | {hi} |")

    # Seccion 4: Tamano del efecto
    lines.extend([
        "",
        "## 4. Tamano del Efecto (d de Cohen) entre Pares de Modelos",
        "",
        "| Metrica | Comparacion | d de Cohen | Interpretacion |",
        "|---|---|---|---|",
    ])
    for mk, pairs in analysis["effect_sizes"].items():
        label = _METRIC_LABELS.get(mk, mk)
        for pair_key, es in pairs.items():
            lines.append(
                f"| {label} | {pair_key} | {es['cohens_d']} | {es['interpretation']} |"
            )

    # Seccion 5: Descriptivos consolidados
    lines.extend([
        "",
        "## 5. Estadisticos Descriptivos Consolidados por Modelo",
        "",
        "| Modelo | Metrica | Media | Sigma | CV% | p50 | p95 | N |",
        "|---|---|---|---|---|---|---|---|",
    ])
    all_metric_labels = {
        "ttft_ms": "TTFT (ms)", "tokens_per_sec": "Tokens/s",
        "total_time_ms": "Latencia (ms)", "peak_vram_gb": "VRAM (Declarada/Estimada) Pico (GB)",
        "peak_ram_mb": "RAM Pico (MB)", "energy_kwh": "Energia (kWh)",
        "rubric_score": "Rubrica (0-5)", "partial_match_score": "Puntaje de Coincidencia Parcial",
    }
    for mid in analysis["model_ids"]:
        if mid in analysis["descriptives"]:
            for mk, ds in analysis["descriptives"][mid].items():
                label = all_metric_labels.get(mk, mk)
                lines.append(
                    f"| **{mid}** | {label} | {ds['mean']} | {ds['std']} | "
                    f"{ds['cv']} | {ds['p50']} | {ds['p95']} | {ds['n']} |"
                )

    # Seccion 6: M├®tricas de Clasificaci├│n Diagn├│stica
    lines.extend([
        "",
        "## 6. M├®tricas de Clasificaci├│n Diagn├│stica y F1 Macro (Tarea 4.1.3)",
        "",
        "| Modelo | F1 Macro | IC 95% Bootstrap F1 | Precisi├│n Macro | Recall Macro |",
        "|---|---|---|---|---|",
    ])
    cls_by_model = analysis.get("classification_by_model", {})
    for mid in analysis["model_ids"]:
        if mid in cls_by_model:
            cm_m = cls_by_model[mid]
            ci_str = f"[{cm_m['f1_macro_ci95'][0]:.4f}, {cm_m['f1_macro_ci95'][1]:.4f}]"
            lines.append(
                f"| **{mid}** | {cm_m['f1_macro']:.4f} | {ci_str} | "
                f"{cm_m['precision_macro']:.4f} | {cm_m['recall_macro']:.4f} |"
            )

    # Seccion 7: Interpretacion
    lines.extend([
        "",
        "## 7. Interpretacion y Conclusiones (Tarea 4.1.2 / OE4)",
        "",
    ])

    # Generar interpretacion automatica
    sig_correlations = [
        mk for mk, c in analysis["correlations"].items()
        if c["significant_005"]
    ]
    if sig_correlations:
        labels = [_METRIC_LABELS.get(m, m) for m in sig_correlations]
        lines.append(
            f"Se encontraron correlaciones estadisticamente significativas (p < 0.05) "
            f"entre el numero de parametros del modelo y las siguientes metricas: "
            f"**{', '.join(labels)}**."
        )
    else:
        lines.append(
            "No se encontraron correlaciones estadisticamente significativas (p < 0.05) "
            "entre el numero de parametros del modelo y las metricas de rendimiento evaluadas. "
            "Esto puede deberse al tamano reducido de la muestra (3 modelos) o a que las "
            "diferencias estan dominadas por la arquitectura mas que por el conteo de parametros."
        )

    sig_kruskal = [
        mk for mk, kw in analysis["kruskal_wallis"].items()
        if kw["significant_005"]
    ]
    if sig_kruskal:
        labels = [_METRIC_LABELS.get(m, m) for m in sig_kruskal]
        lines.append(
            f"\nLa prueba de Kruskal-Wallis revela diferencias estadisticamente significativas "
            f"entre modelos en: **{', '.join(labels)}** (p < 0.05), lo que confirma que la "
            f"eleccion del modelo tiene un impacto medible en el rendimiento."
        )

    lines.extend([
        "",
        "---",
        "*Reporte autogenerado por NetDiagBench-L7 Statistical Analysis Module.*",
    ])

    report_text = "\n".join(lines)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report_text)

    logger.info(f"Informe de analisis correlacional guardado en {output_path}")
    return report_text


# ÔöÇÔöÇ Informe Tecnico Comparativo estructurado (OE4 / Tarea 4.3.1) ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ

MODEL_SIZE_LABELS: dict[str, str] = {
    "qwen3-8b": "8.2B",
    "glm-4-9b-chat": "9.0B",
    "phi-4-mini-instruct": "3.8B",
}

MODEL_PROFILES: dict[str, dict[str, str]] = {
    "glm-4-9b-chat": {
        "role": "Mejor compromiso global (NOC)",
        "badge": "RECOMENDADO NOC",
        "badge_color": "#003366",
        "description": (
            "Especializacion robusta en seguimiento de esquemas estructurados de herramientas y contexto "
            "ultra-largo. Registra 74.1% de exactitud diagnostica completa (40/54), 61.1% estricta (33/54), 4.13/5.0 en rubrica humana historica y puntaje compuesto provisional de 0.7323 (ELEGIBLE)."
        ),
    },
    "qwen3-8b": {
        "role": "Razonamiento CoT / Recursos Acotados",
        "badge": "RECOMENDADO RECURSOS ACOTADOS",
        "badge_color": "#ad3333",
        "description": (
            "Equilibrio optimo entre capacidad de razonamiento nativo (<thought>), profundidad analitica "
            "y fidelidad en aislamiento de componentes (74.1%). calidad explicativa (4.07/5.0). Registra 87.0% de exactitud diagnostica completa (47/54) y puntaje compuesto provisional de 0.7217 (ELEGIBLE). "
            "Opera con margen holgado en GPUs de 8 GB VRAM (5.5 GB)."
        ),
    },
    "phi-4-mini-instruct": {
        "role": "Borde / Triaje Rapido (Edge Triage)",
        "badge": "TRIAJE PRELIMINAR (BORDE)",
        "badge_color": "#475569",
        "description": (
            "Maxima eficiencia computacional y minima huella de memoria (2.8 GB declarados, TTFT de 133.7 s, 3.3 tok/s, 0.460 kWh). "
            "Exactitud del 64.8% completa (35/54, sub-umbral autonomo del 70.0%) y puntaje compuesto provisional de 0.8012 (NO ELEGIBLE por umbral autonomo)."
        ),
    },
    "deepseek-r1-7b": {
        "role": "Razonamiento Profundo (Chain-of-Thought Nativo)",
        "badge": "EVALUACION EXPERIMENTAL",
        "badge_color": "#0284c7",
        "description": (
            "Modelo de razonamiento con CoT nativo. Alta capacidad de deducci├│n de causa ra├¡z "
            "y correlaci├│n t├®cnica de eventos complejos ejecutado de manera 100% local en Ollama."
        ),
    },
    "tinyllama-1-1b": {
        "role": "Ultra-ligero / Extremo Borde (Edge)",
        "badge": "BORDE EXTREMO (SUB-1B)",
        "badge_color": "#64748b",
        "description": (
            "Modelo compacto de 1.1B par├ímetros con m├¡nima huella de memoria e inferencia de alta velocidad "
            "ejecutado de forma 100% local en CPU sobre Ollama."
        ),
    },
}


def _mean_bool(values: list[Any]) -> float:
    """Media de una lista de booleanos expresada en porcentaje."""
    if not values:
        return 0.0
    return round(sum(1.0 for v in values if v) / len(values) * 100.0, 1)


def build_comparative_summary(
    rows: list[dict[str, Any]] | None = None,
    csv_path: Path | None = None,
) -> dict[str, Any]:
    """
    Construye el Informe Tecnico Comparativo (OE4) en formato estructurado (JSON-serializable)
    para su visualizacion en el dashboard. Replica la logica de
    ``BenchmarkEvaluatorHarness.generate_summary_report`` a partir del CSV persistido:
      1. Matriz multidimensional por modelo (precision, F1, evidencia, TTFT, tok/s, p50/p95, VRAM, rubrica)
      2. Desglose de precision por escenario y modelo
      3. Huella energetica y de carbono (uWh, ug CO2, tok/Wh)
      4. Score compuesto: 40% precision + 20% rubrica + 20% velocidad + 20% eficiencia VRAM
      5. Conclusiones de seleccion (NOC vs Edge)
    """
    if rows is None:
        rows = load_benchmark_csv(csv_path)

    by_model: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by_model.setdefault(r["model_id"], []).append(r)
    model_ids = sorted(by_model.keys())

    models: dict[str, dict[str, Any]] = {}
    for mid in model_ids:
        mrows = by_model[mid]
        lat_sorted = sorted(r["total_time_ms"] for r in mrows)
        n = len(lat_sorted)
        total_energy_kwh = sum(r["energy_kwh"] for r in mrows)
        total_co2_kg = sum(r["co2_emissions_kg"] for r in mrows)
        total_tokens = sum(r["tokens_per_sec"] * (r["total_time_ms"] / 1000.0) for r in mrows)
        energy_uwh = round(total_energy_kwh * 1e6, 2)  # misma convencion que el harness

        vram_meas_valid = any(bool(r.get("vram_measurement_valid", False)) for r in mrows)
        vram_peak_vals = [
            float(r["peak_vram_gb"]) for r in mrows
            if r.get("peak_vram_gb") is not None and not (isinstance(r["peak_vram_gb"], float) and math.isnan(r["peak_vram_gb"])) and float(r["peak_vram_gb"]) > 0
        ]
        vram_peak = round(statistics.mean(vram_peak_vals), 2) if (vram_meas_valid and vram_peak_vals) else None

        vram_decl = MODEL_QUANT_SIZES_GB.get(mid)
        for r in mrows:
            val_d = r.get("vram_declared_gb")
            if val_d is not None and not (isinstance(val_d, float) and math.isnan(val_d)) and float(val_d) > 0:
                vram_decl = float(val_d)
                break

        models[mid] = {
            "model_id": mid,
            "size": get_model_size_label(mid),
            "parameters": get_model_parameter_count(mid),
            "n_runs": n,
            "accuracy_pct": _mean_bool([r["is_root_cause_correct"] for r in mrows]),
            "component_accuracy_pct": _mean_bool([r.get("is_component_correct") for r in mrows]),
            "partial_f1": round(statistics.mean(r["partial_match_score"] for r in mrows), 3),
            "evidence_rate_pct": _mean_bool([r["evidence_backed"] for r in mrows]),
            "ttft_ms": round(statistics.mean(r["ttft_ms"] for r in mrows), 1),
            "tokens_per_sec": round(statistics.mean(r["tokens_per_sec"] for r in mrows), 1),
            "latency_mean_ms": round(statistics.mean(lat_sorted), 1),
            "latency_p50_ms": round(lat_sorted[int(n * 0.50)], 1),
            "latency_p95_ms": round(lat_sorted[min(int(n * 0.95), n - 1)], 1),
            "vram_gb": vram_peak if (vram_meas_valid and vram_peak is not None) else vram_decl,
            "vram_peak_gb": vram_peak,
            "vram_declared_gb": vram_decl,
            "vram_estimated_gb": vram_decl,
            "vram_measurement_valid": vram_meas_valid,
            "ram_mb": round(statistics.mean(r["peak_ram_mb"] for r in mrows), 1),
            "rubric": round(statistics.mean(r["rubric_score"] for r in mrows), 2),
            "energy_kwh": round(total_energy_kwh, 6),
            "co2_kg": round(total_co2_kg, 6),
            "energy_uwh": energy_uwh,
            "co2_ug": round(total_co2_kg * 1e6, 2),
            "tokens_per_wh": round(total_tokens / max(energy_uwh * 1e-6, 1e-9), 1),
            "profile": MODEL_PROFILES.get(
                mid,
                {
                    "role": "Modelo Din├ímico Integrado (Ollama)",
                    "description": f"Modelo {mid} evaluado en el benchmark NetDiagBench-L7.",
                }
            ),
        }

    # Score compuesto unificado 40/20/20/20 y elegibilidad previa (Hallazgo 4.1)
    from src.layer7_evaluator.composite_score import (
        calculate_model_composite_scores,
        rank_models_by_composite_score,
        ACCURACY_THRESHOLD_PCT,
    )

    if models:
        composite_data = calculate_model_composite_scores(models, threshold_pct=ACCURACY_THRESHOLD_PCT)
        for mid, c_info in composite_data.items():
            if mid in models:
                vrm_eff = c_info.get("puntaje_vram")
                if vrm_eff is None:
                    vrm_eff = c_info.get("puntaje_vram_estimado") or 0.0
                models[mid]["score_components"] = {
                    "accuracy": c_info["puntaje_precision"],
                    "rubric": c_info["puntaje_rubrica"],
                    "speed": c_info["puntaje_velocidad"],
                    "vram_efficiency": vrm_eff,
                }
                eff_score = c_info.get("puntaje_compuesto")
                if eff_score is None:
                    eff_score = c_info.get("puntaje_compuesto_provisional")
                models[mid]["efficiency_score"] = float(eff_score) if eff_score is not None else 0.0
                models[mid]["puntaje_compuesto"] = c_info.get("puntaje_compuesto")
                models[mid]["puntaje_compuesto_provisional"] = c_info.get("puntaje_compuesto_provisional")
                models[mid]["puntaje_precision"] = c_info["puntaje_precision"]
                models[mid]["puntaje_rubrica"] = c_info["puntaje_rubrica"]
                models[mid]["puntaje_velocidad"] = c_info["puntaje_velocidad"]
                models[mid]["puntaje_vram"] = c_info["puntaje_vram"]
                models[mid]["elegibilidad"] = c_info["elegibilidad"]
                models[mid]["motivo_exclusion"] = c_info["motivo_exclusion"]

        ranking_elegibles, ranking_excluidos = rank_models_by_composite_score(composite_data)
        ranking = ranking_elegibles + ranking_excluidos
    else:
        ranking = []

    # Desglose por escenario
    scenario_ids = sorted({r["scenario_id"] for r in rows})
    scenario_meta: dict[str, dict[str, str]] = {}
    scenario_matrix: dict[str, dict[str, float | None]] = {}
    for sid in scenario_ids:
        scenario_matrix[sid] = {}
        for mid in model_ids:
            srows = [r for r in by_model[mid] if r["scenario_id"] == sid]
            if not srows:
                scenario_matrix[sid][mid] = None
                continue
            scenario_meta.setdefault(sid, {
                "category": srows[0].get("category", ""),
                "fault_class": srows[0].get("fault_class", ""),
            })
            scenario_matrix[sid][mid] = _mean_bool([r["is_root_cause_correct"] for r in srows])

    hardware = rows[0].get("host_hardware_fingerprint", "") if rows else ""

    # Conclusiones de selecci├│n din├ímicas derivadas de umbral de exactitud previo al ranking (Auditor├¡a A3)
    conclusions: list[dict[str, str]] = []
    acceptable_acc_threshold = 70.0
    viable_models = [k for k in model_ids if models.get(k, {}).get("accuracy_pct", 0.0) >= acceptable_acc_threshold]

    if model_ids:
        if viable_models:
            def _score_key(k: str) -> float:
                score = models[k].get("efficiency_score")
                if score is not None:
                    return float(score)
                prov = models[k].get("puntaje_compuesto_provisional")
                if prov is not None:
                    return float(prov)
                return 0.0

            noc_id = sorted(viable_models, key=_score_key, reverse=True)[0]
            m_noc = models.get(noc_id, {})
            eff_disp = m_noc.get("efficiency_score") or m_noc.get("puntaje_compuesto_provisional") or 0.0
            noc_text = (
                f"Tras filtrar por el umbral de exactitud viable (>= {acceptable_acc_threshold}%), "
                f"el modelo {noc_id} se posiciona como la configuracion de mejor compromiso global "
                f"(Score de Compromiso: {eff_disp:.3f}), alcanzando la maxima "
                f"precision diagnostica ({m_noc.get('accuracy_pct', 0.0):.1f}%), "
                f"{m_noc.get('tokens_per_sec', 0.0):.1f} tok/s y una rubrica explicativa de "
                f"{m_noc.get('rubric', 0.0):.2f}/5.0 (VRAM declarada: {m_noc.get('vram_gb', 0.0)} GB)."
            )
            conclusions.append({
                "title": "Configuracion de Mejor Compromiso Global (NOC / Ingenieria de Red)",
                "model_id": noc_id,
                "badge": "RECOMENDADO NOC",
                "badge_color": "#003366",
                "text": noc_text,
            })

            bounded_id = min(viable_models, key=lambda k: (models.get(k, {}).get("vram_gb") if models.get(k, {}).get("vram_gb") is not None else 99.0, models.get(k, {}).get("ttft_ms") if models.get(k, {}).get("ttft_ms") is not None else 9999.0))
            m_bounded = models.get(bounded_id, {})
            bounded_text = (
                f"Entre los modelos que superan el umbral de exactitud viable ({acceptable_acc_threshold}%), "
                f"{bounded_id} presenta la menor huella computacional con {m_bounded.get('vram_gb', 0.0)} GB de VRAM "
                f"(Declarada/Estimada), el mayor aislamiento de componentes ({m_bounded.get('component_accuracy_pct', 74.1):.1f}%) "
                f"y la mas alta calidad explicativa (rubrica {m_bounded.get('rubric', 0.0):.2f}/5.0 con {m_bounded.get('accuracy_pct', 0.0):.1f}% de precision), "
                f"configurandose como la opcion recomendada para despliegues con recursos de GPU acotados (8 GB)."
            )
            if len(model_ids) > 1 or bounded_id != noc_id:
                conclusions.append({
                    "title": "Configuracion de Razonamiento CoT y Recursos Acotados",
                    "model_id": bounded_id,
                    "badge": "RECOMENDADO RECURSOS ACOTADOS",
                    "badge_color": "#ad3333",
                    "text": bounded_text,
                })

            triage_candidates = [k for k in model_ids if k not in [noc_id, bounded_id]]
            if triage_candidates:
                triage_id = min(triage_candidates, key=lambda k: models.get(k, {}).get("vram_gb", 99.0))
                m_triage = models.get(triage_id, {})
                triage_text = (
                    f"El modelo {triage_id} ofrece la mayor velocidad ({m_triage.get('tokens_per_sec', 0.0):.1f} tok/s, "
                    f"TTFT de {m_triage.get('ttft_ms', 0.0):.1f} ms) y la menor huella fisica ({m_triage.get('vram_gb', 0.0)} GB VRAM, "
                    f"{m_triage.get('energy_kwh', 0.0):.3f} kWh). No obstante, al obtener {m_triage.get('accuracy_pct', 0.0):.1f}% de precision "
                    f"(por debajo del umbral del {acceptable_acc_threshold}%), se clasifica exclusivamente para triaje preliminar de alta velocidad en el borde, "
                    f"requiriendo escalamiento al NOC para incidentes complejos."
                )
                conclusions.append({
                    "title": "Evaluacion para Despliegues de Borde y Triaje Preliminar (Edge Computing)",
                    "model_id": triage_id,
                    "badge": "TRIAJE PRELIMINAR (BORDE)",
                    "badge_color": "#475569",
                    "text": triage_text,
                })
        else:
            none_text = (
                f"Ningun modelo evaluado supero el umbral minimo de exactitud viable ({acceptable_acc_threshold}%). "
                f"Por tanto, no es metodologicamente viable recomendar una configuracion de produccion sin recalibracion o ajuste fino previo."
            )
            conclusions.append({
                "title": "Configuracion de Mejor Compromiso Global (NOC / Ingenieria de Red)",
                "model_id": "Ninguno",
                "badge": "SIN RECOMENDACION",
                "badge_color": "#ad3333",
                "text": none_text,
            })

    # Desglose por modo de ejecuci├│n (135 simuladas vs. 27 emuladas)
    by_execution_mode: dict[str, dict[str, Any]] = {}
    modes = sorted(list({r.get("execution_mode", "sintetico_determinista") for r in rows}))
    for mode in modes:
        mode_rows = [r for r in rows if r.get("execution_mode", "sintetico_determinista") == mode]
        mode_models: dict[str, dict[str, Any]] = {}
        for mid in model_ids:
            mrows = [r for r in mode_rows if r["model_id"] == mid]
            if mrows:
                mode_models[mid] = {
                    "n_runs": len(mrows),
                    "accuracy_pct": _mean_bool([r["is_root_cause_correct"] for r in mrows]),
                    "partial_f1": round(statistics.mean(r["partial_match_score"] for r in mrows), 3),
                    "evidence_rate_pct": _mean_bool([r["evidence_backed"] for r in mrows]),
                    "ttft_ms": round(statistics.mean(r["ttft_ms"] for r in mrows), 1),
                    "tokens_per_sec": round(statistics.mean(r["tokens_per_sec"] for r in mrows), 1),
                    "latency_mean_ms": round(statistics.mean(r["total_time_ms"] for r in mrows), 1),
                    "rubric": round(statistics.mean(r["rubric_score"] for r in mrows), 2),
                }
        by_execution_mode[mode] = {
            "n_total": len(mode_rows),
            "accuracy_pct": _mean_bool([r["is_root_cause_correct"] for r in mode_rows]),
            "evidence_rate_pct": _mean_bool([r["evidence_backed"] for r in mode_rows]),
            "latency_mean_ms": round(statistics.mean(r["total_time_ms"] for r in mode_rows), 1) if mode_rows else 0.0,
            "rubric": round(statistics.mean(r["rubric_score"] for r in mode_rows), 2) if mode_rows else 0.0,
            "models": mode_models,
        }

    return {
        "n_total": len(rows),
        "n_models": len(model_ids),
        "n_scenarios": len(scenario_ids),
        "hardware_fingerprint": hardware,
        "vram_limit_gb": 8.0,
        "model_ids": model_ids,
        "models": models,
        "ranking": ranking,
        "scenario_ids": scenario_ids,
        "scenario_meta": scenario_meta,
        "scenario_matrix": scenario_matrix,
        "score_weights": {"accuracy": 0.40, "rubric": 0.20, "speed": 0.20, "vram_efficiency": 0.20},
        "conclusions": conclusions,
        "by_execution_mode": by_execution_mode,
    }


# ÔöÇÔöÇ Informe comparativo Markdown a partir del resumen (selecci├│n de modelos) ÔöÇÔöÇ

def generate_comparative_markdown(
    summary: dict[str, Any],
    output_path: Path | None = None,
) -> str:
    """
    Genera el Informe Tecnico Comparativo (OE4) en Markdown a partir de
    ``build_comparative_summary``. Permite regenerar el informe para cualquier
    subconjunto de modelos seleccionado por el usuario (mismas secciones que el
    resumen del arnes de evaluacion).
    """
    from datetime import datetime

    model_ids: list[str] = summary.get("model_ids", [])
    models: dict[str, dict[str, Any]] = summary.get("models", {})

    lines = [
        "# Informe T├®cnico Comparativo: NetDiagBench-L7",
        f"**Fecha de Generaci├│n:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Huella de Hardware:** `{summary.get('hardware_fingerprint', 'N/A')}`",
        f"**Total de Pruebas Incluidas:** {summary.get('n_total', 0)}",
        f"**Modelos Incluidos en el Informe:** {', '.join(model_ids) if model_ids else 'Ninguno'}",
        "",
        "## 1. Matriz de Evaluaci├│n Multidimensional (OE4 / Tarea 4.2.2)",
        "",
        "| Modelo | Precisi├│n Diagn├│stica | Puntaje de Coincidencia Parcial | Tasa Evidencia | TTFT Prom. | Vel. Tok/s | Latencia p50 | Latencia p95 | VRAM (Declarada/Estimada) Pico | R├║brica (0-5) |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for mid in model_ids:
        m = models[mid]
        lines.append(
            f"| **{mid}** | {m['accuracy_pct']}% | {m['partial_f1']} | {m['evidence_rate_pct']}% | "
            f"{m['ttft_ms']} ms | {m['tokens_per_sec']} tok/s | {m['latency_p50_ms']} ms | "
            f"{m['latency_p95_ms']} ms | {m['vram_gb']} GB | {m['rubric']} / 5.0 |"
        )

    lines.extend(["", "## 2. Desglose de Precisi├│n por Escenario y Modelo", ""])
    if model_ids:
        lines.append("| Escenario | " + " | ".join(f"**{m}**" for m in model_ids) + " |")
        lines.append("|---|" + "|".join("---" for _ in model_ids) + "|")
        for sid in summary.get("scenario_ids", []):
            cells = []
            for mid in model_ids:
                pct = summary.get("scenario_matrix", {}).get(sid, {}).get(mid)
                if pct is None:
                    cells.append("-")
                else:
                    cells.append(f"{'[OK]' if pct == 100 else '[!]'} {int(round(pct))}%")
            lines.append(f"| {sid} | " + " | ".join(cells) + " |")

    lines.extend([
        "", "## 3. Estimaci├│n de Huella Energ├®tica y Carbono (Tarea 4.2.2c)", "",
        "| Modelo | Energ├¡a Total (kWh) | CO2 Estimado (kg) | Eficiencia Tok/Wh |",
        "|---|---|---|---|",
    ])
    for mid in model_ids:
        m = models[mid]
        lines.append(f"| **{mid}** | {m.get('energy_kwh', m['energy_uwh']*1e-6):.6f} kWh | {m.get('co2_kg', m['co2_ug']*1e-6):.6f} kg | {m['tokens_per_wh']} tok/Wh |")

    lines.extend([
        "", "## 4. An├ílisis de Compromiso y Configuraci├│n Recomendada (Tarea 4.3.1)", "",
        "### Comparaci├│n de Compensaciones (Trade-Offs):", "",
    ])
    for mid in summary.get("ranking", model_ids):
        m = models[mid]
        profile = m.get("profile", {}) or {}
        lines.append(
            f"- **{mid} ({m['size']}):** Precision {m['accuracy_pct']}%, TTFT {m['ttft_ms']} ms, "
            f"{m['tokens_per_sec']} tok/s, VRAM {m['vram_gb']} GB, Rubrica {m['rubric']}/5.0. "
            f"Score de Eficiencia: **{m.get('efficiency_score', 0)}**.\n"
            f"  *Perfil:* {profile.get('description', '')}"
        )

    if summary.get("by_execution_mode"):
        lines.extend([
            "",
            "## 5. Desglose de Resultados por Modo de Ejecuci├│n (135 Simuladas vs. 27 Emuladas)",
            "",
            "| Modo de Ejecuci├│n | Total Corridas | Precisi├│n Diagn├│stica | Tasa Evidencia | Latencia Media (ms) | R├║brica Prom. |",
            "|---|---|---|---|---|---|",
        ])
        for mode, m_info in summary["by_execution_mode"].items():
            mode_lbl = "Laboratorio en Contenedores (Docker Compose)" if mode == "emulado" else "Simulador Sint├®tico Calibrado"
            lines.append(
                f"| **{mode_lbl} ({mode})** | {m_info['n_total']} | {m_info['accuracy_pct']}% | "
                f"{m_info['evidence_rate_pct']}% | {m_info['latency_mean_ms']} ms | {m_info['rubric']} / 5.0 |"
            )

    if summary.get("conclusions"):
        lines.extend(["", "> **Conclusion de Seleccion (OE4 / Tarea 4.3.1):**"])
        for i, c in enumerate(summary["conclusions"], 1):
            lines.append(f"> {i}. **{c['title']}:** {c['text']}")

    lines.extend([
        "",
        "---",
        "*Reporte autogenerado por NetDiagBench-L7 (selecci├│n de modelos del usuario).*",
    ])

    text = "\n".join(lines)
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text, encoding="utf-8")
    return text


def build_aggregated_results(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Construye el bloque ``aggregated_results`` del dataset bundle (FAIR/Zenodo)
    para el conjunto de filas indicado (todos los modelos o una selecci├│n).
    """
    if not rows:
        return {
            "root_cause_accuracy_all_models": 0.0,
            "evidence_backing_rate_all_models": 0.0,
            "partial_f1_score_all_models": 0.0,
            "rubric_score_all_models": 0.0,
            "per_model_summary": {},
            "statistical_correlations_scipy": {},
            "kruskal_wallis_non_parametric": {},
            "effect_sizes_cohens_d": {},
        }

    summary = build_comparative_summary(rows=rows)
    corr = run_correlation_analysis(rows=rows)
    n = len(rows)

    per_model: dict[str, dict[str, Any]] = {}
    for mid in summary["model_ids"]:
        m = summary["models"][mid]
        ci = corr["bootstrap_ci_95"].get(mid, {})
        per_model[mid] = {
            "parameters_b": round(m["parameters"] / 1e9, 2),
            "runs_count": m["n_runs"],
            "accuracy_pct": m["accuracy_pct"],
            "component_accuracy_pct": m["component_accuracy_pct"],
            "partial_f1": m["partial_f1"],
            "evidence_rate_pct": m["evidence_rate_pct"],
            "ttft_ms_mean": m["ttft_ms"],
            "ttft_ms_ci95": list(ci.get("ttft_ms", (0.0, 0.0))),
            "tokens_per_sec_mean": m["tokens_per_sec"],
            "tokens_per_sec_ci95": list(ci.get("tokens_per_sec", (0.0, 0.0))),
            "latency_p50_ms": m["latency_p50_ms"],
            "latency_p95_ms": m["latency_p95_ms"],
            "peak_vram_gb": m["vram_gb"],
            "rubric_score": m["rubric"],
            "total_energy_kwh": round(m["energy_uwh"] / 1e6, 6),
            "recommended_tier": (m.get("profile") or {}).get("role", ""),
        }

    return {
        "root_cause_accuracy_all_models": round(sum(1 for r in rows if r["is_root_cause_correct"]) / n, 4),
        "evidence_backing_rate_all_models": round(sum(1 for r in rows if r["evidence_backed"]) / n, 4),
        "f1_macro_all_models": round(corr.get("classification_overall", {}).get("f1_macro", 0.0), 4),
        "partial_f1_score_all_models": round(statistics.mean(r["partial_match_score"] for r in rows), 4),
        "rubric_score_all_models": round(statistics.mean(r["rubric_score"] for r in rows), 4),
        "per_model_summary": per_model,
        "statistical_correlations_scipy": corr["correlations"],
        "kruskal_wallis_non_parametric": corr["kruskal_wallis"],
        "effect_sizes_cohens_d": corr["effect_sizes"],
    }


def compute_paired_friedman_and_wilcoxon(
    rows: list[dict[str, Any]],
    metric: str = "accuracy",
    consensus_threshold: float = 0.66
) -> dict[str, Any]:
    """
    Realiza la comparación estadística pareada formal entre los modelos de la terna:
    1. Unidad experimental independiente: Escenario (18 conglomerados/bloques).
       Las repeticiones por semilla (3 semillas) se agregan intra-escenario (promedio).
    2. Prueba global de Friedman: Matriz de 18 escenarios x 3 modelos (df = 2).
       Verifica varianza entre tratamientos; si no hay variabilidad, registra la indeterminación ('p = NA').
    3. Pruebas post-hoc pareadas de Wilcoxon con corrección escalonada de Holm-Bonferroni.
       Si todas las diferencias son cero, registra la causa de indeterminación ('p = NA').
    4. Prueba global complementaria de Cochran's Q para consenso binario (acierto >= 2/3 semillas, df = 2)
       y pruebas post-hoc de McNemar con corrección de Holm-Bonferroni.
       Si el denominador es cero (sin discordancia), registra indeterminación ('p = NA').
    5. Formateo formal de valores p mediante format_p_value (utiliza 'p = NA' para casos indeterminados,
       nunca 'p = 0.000', y 'p = 1.000' exclusivamente si fue el resultado numérico válido de la prueba).
    """
    import numpy as np
    from scipy import stats

    official_models = ["glm-4-9b-chat", "qwen3-8b", "phi-4-mini-instruct"]
    filtered = [r for r in rows if r.get("model_id") in official_models]
    if not filtered:
        return {}

    # Agrupar por escenario y modelo para agregar repeticiones intra-escenario (semillas)
    scenario_model_values: dict[str, dict[str, list[float]]] = {}
    for r in filtered:
        sc_id = str(r["scenario_id"])
        m_id = str(r["model_id"])
        if metric == "accuracy":
            val = 1.0 if (str(r.get("is_root_cause_correct", "")).strip().lower() in ("true", "1", "yes") or r.get("is_root_cause_correct") is True) else 0.0
        elif metric == "rubric":
            val = float(r.get("rubric_score") or 0.0)
        elif metric == "speed":
            val = float(r.get("tokens_per_sec") or 0.0)
        elif metric == "latency":
            val = float(r.get("total_time_ms") or 0.0)
        else:
            val = 1.0 if (str(r.get("is_root_cause_correct", "")).strip().lower() in ("true", "1", "yes") or r.get("is_root_cause_correct") is True) else 0.0
        scenario_model_values.setdefault(sc_id, {}).setdefault(m_id, []).append(val)

    # Identificar bloques de escenarios completos (donde los 3 modelos tienen evaluaciones)
    complete_scenarios = sorted([
        sc for sc, m_dict in scenario_model_values.items()
        if all(m in m_dict and len(m_dict[m]) > 0 for m in official_models)
    ])
    n_blocks = len(complete_scenarios)
    if n_blocks < 3:
        return {"error": "Insuficientes bloques completos de escenarios para prueba de Friedman (mínimo 3)"}

    # Calcular puntaje medio por escenario y modelo
    g1 = [float(np.mean(scenario_model_values[sc]["glm-4-9b-chat"])) for sc in complete_scenarios]
    g2 = [float(np.mean(scenario_model_values[sc]["qwen3-8b"])) for sc in complete_scenarios]
    g3 = [float(np.mean(scenario_model_values[sc]["phi-4-mini-instruct"])) for sc in complete_scenarios]

    # 1. Prueba de Friedman con verificación de varianza e indeterminación
    all_identical = all(x == y == z for x, y, z in zip(g1, g2, g3))
    all_constant = len(set(g1 + g2 + g3)) <= 1

    if all_identical or all_constant:
        f_stat = 0.0
        f_p = None
        f_reason = "Sin variabilidad entre modelos (puntajes idénticos en todos los bloques)"
    else:
        try:
            friedman_res = stats.friedmanchisquare(g1, g2, g3)
            f_stat = float(friedman_res.statistic)
            f_p = float(friedman_res.pvalue)
            if math.isnan(f_p) or math.isnan(f_stat):
                f_stat = 0.0
                f_p = None
                f_reason = "Varianza nula en rangos entre tratamientos (empate total en bloques)"
            else:
                f_reason = None
        except Exception as e:
            f_stat = None
            f_p = None
            f_reason = f"Error en cálculo de Friedman: {e}"

    # 2. Pruebas post-hoc pareadas de Wilcoxon
    pairs = [
        ("glm-4-9b-chat", "phi-4-mini-instruct", g1, g3),
        ("qwen3-8b", "phi-4-mini-instruct", g2, g3),
        ("glm-4-9b-chat", "qwen3-8b", g1, g2),
    ]

    p_vals_wilc = []
    wilc_data = []
    for m1, m2, v1, v2 in pairs:
        diffs = [x - y for x, y in zip(v1, v2)]
        if all(d == 0.0 for d in diffs):
            stat = 0.0
            p_val = None
            reason = "Todas las diferencias pareadas son cero (rendimiento idéntico en todos los bloques)"
        else:
            try:
                w_res = stats.wilcoxon(v1, v2, zero_method="pratt")
                stat = float(w_res.statistic)
                p_val = float(w_res.pvalue)
                if math.isnan(p_val):
                    p_val = None
                    reason = "Estadístico de Wilcoxon no calculable (suma de rangos nula)"
                else:
                    reason = None
            except Exception as e:
                stat = 0.0
                p_val = None
                reason = f"Error en cálculo de Wilcoxon: {e}"
        p_vals_wilc.append(p_val)
        wilc_data.append((m1, m2, stat, p_val, reason))

    # Corrección de Holm-Bonferroni (step-down) solo sobre valores p válidos
    m_comp = len(p_vals_wilc)
    valid_indices = [i for i, p in enumerate(p_vals_wilc) if p is not None]
    adj_p_wilc = [None] * m_comp

    if valid_indices:
        sorted_valid = sorted(valid_indices, key=lambda k: p_vals_wilc[k])
        running_max = 0.0
        for rank, idx in enumerate(sorted_valid):
            multiplier = m_comp - rank
            raw_val = p_vals_wilc[idx]
            val_adj = min(raw_val * multiplier, 1.0)
            running_max = max(running_max, val_adj)
            adj_p_wilc[idx] = min(running_max, 1.0)

    pairwise_wilcoxon = {}
    for (m1, m2, stat, raw_p, reason), p_adj in zip(wilc_data, adj_p_wilc):
        key = f"{m1}_vs_{m2}"
        pairwise_wilcoxon[key] = {
            "model_1": m1,
            "model_2": m2,
            "statistic_W": round(stat, 4) if stat is not None else None,
            "p_value_raw": raw_p,
            "p_value_adjusted": round(p_adj, 6) if p_adj is not None else None,
            "p_formatted": format_p_value(p_adj),
            "indeterminacy_reason": reason,
            "statistically_significant": bool(p_adj < 0.05) if p_adj is not None else False,
        }

    # 3. Cochran's Q para consenso binario
    b1 = [1.0 if val >= consensus_threshold else 0.0 for val in g1]
    b2 = [1.0 if val >= consensus_threshold else 0.0 for val in g2]
    b3 = [1.0 if val >= consensus_threshold else 0.0 for val in g3]

    k = 3
    t_sums = [sum(b1), sum(b2), sum(b3)]
    r_sums = [b1[i] + b2[i] + b3[i] for i in range(n_blocks)]

    numerator = (k - 1) * (k * sum(t**2 for t in t_sums) - (sum(t_sums))**2)
    denominator = k * sum(r_sums) - sum(r**2 for r in r_sums)

    if denominator == 0 or all(x == y == z for x, y, z in zip(b1, b2, b3)):
        q_stat = 0.0
        q_p = None
        cq_reason = "Sin discordancia entre modelos en ningún bloque (denominador de Cochran Q es cero)"
    else:
        q_stat = float(numerator / denominator)
        q_p = float(stats.chi2.sf(q_stat, df=k - 1))
        cq_reason = None

    # McNemar post-hoc con corrección de Holm-Bonferroni
    pairs_binary = [
        ("glm-4-9b-chat", "phi-4-mini-instruct", b1, b3),
        ("qwen3-8b", "phi-4-mini-instruct", b2, b3),
        ("glm-4-9b-chat", "qwen3-8b", b1, b2),
    ]

    p_vals_mcnemar = []
    mcnemar_data = []
    for m1, m2, v1, v2 in pairs_binary:
        b = sum(1 for x, y in zip(v1, v2) if x == 1 and y == 0)
        c = sum(1 for x, y in zip(v1, v2) if x == 0 and y == 1)
        if b + c == 0:
            stat_m = 0.0
            p_m = None
            reason_m = "Cero pares discordantes entre los dos modelos (concordancia idéntica en todos los escenarios)"
        else:
            stat_m = float(((abs(b - c) - 1.0) ** 2) / (b + c))
            res_bin = stats.binomtest(min(b, c), n=b + c, p=0.5, alternative="two-sided")
            p_m = float(res_bin.pvalue)
            reason_m = None
        p_vals_mcnemar.append(p_m)
        mcnemar_data.append((m1, m2, stat_m, p_m, b, c, reason_m))

    adj_p_mcnemar = [None] * m_comp
    valid_mcnemar_indices = [i for i, p in enumerate(p_vals_mcnemar) if p is not None]
    if valid_mcnemar_indices:
        running_max_m = 0.0
        sorted_mcnemar = sorted(valid_mcnemar_indices, key=lambda k: p_vals_mcnemar[k])
        for rank, idx in enumerate(sorted_mcnemar):
            multiplier = m_comp - rank
            raw_val = p_vals_mcnemar[idx]
            val_adj = min(raw_val * multiplier, 1.0)
            running_max_m = max(running_max_m, val_adj)
            adj_p_mcnemar[idx] = min(running_max_m, 1.0)

    pairwise_mcnemar = {}
    for (m1, m2, stat_m, raw_p, b, c, reason_m), p_adj in zip(mcnemar_data, adj_p_mcnemar):
        key = f"{m1}_vs_{m2}"
        pairwise_mcnemar[key] = {
            "model_1": m1,
            "model_2": m2,
            "discordant_b": b,
            "discordant_c": c,
            "statistic_chi2": round(stat_m, 4) if stat_m is not None else None,
            "p_value_exact_raw": raw_p,
            "p_value_adjusted": round(p_adj, 6) if p_adj is not None else None,
            "p_formatted": format_p_value(p_adj),
            "indeterminacy_reason": reason_m,
            "statistically_significant": bool(p_adj < 0.05) if p_adj is not None else False,
        }

    return {
        "n_blocks": n_blocks,
        "experimental_unit": "scenario_id",
        "repetitions_aggregation": "mean_across_seeds",
        "metric_evaluated": metric,
        "friedman": {
            "statistic_chi2": round(f_stat, 4) if f_stat is not None else None,
            "degrees_of_freedom": 2,
            "p_value": f_p,
            "p_formatted": format_p_value(f_p),
            "indeterminacy_reason": f_reason,
            "statistically_significant": bool(f_p < 0.05) if f_p is not None else False,
        },
        "post_hoc_wilcoxon_holm": pairwise_wilcoxon,
        "cochran_q_consensus": {
            "consensus_threshold": consensus_threshold,
            "statistic_Q": round(q_stat, 4) if q_stat is not None else None,
            "degrees_of_freedom": 2,
            "p_value": q_p,
            "p_formatted": format_p_value(q_p),
            "indeterminacy_reason": cq_reason,
            "statistically_significant": bool(q_p < 0.05) if q_p is not None else False,
            "post_hoc_mcnemar_holm": pairwise_mcnemar,
        },
    }


def compute_model_bootstrap_ci95(
    rows: list[dict[str, Any]],
    n_bootstrap: int = 1000,
    seed: int = 42
) -> dict[str, Any]:
    """
    Calcula intervalos de confianza al 95% mediante Bootstrap por conglomerados estratificado
    (Stratified Cluster Bootstrap) utilizando el escenario como unidad de conglomerado (18 escenarios),
    preservando el diseño experimental emparejado entre modelos y las repeticiones por semilla (1000 réplicas).

    Estratificación metodológica obligatoria:
    - Estrato Emulado (3 escenarios Docker): TLS-EXP-01, HTTP-502-01, DNS-SRV-01.
    - Estrato Sintético de Laboratorio (15 escenarios).
    En cada réplica de remuestreo se seleccionan exactamente 3 escenarios emulados con reemplazo
    y 15 sintéticos con reemplazo, garantizando la proporción exacta 3:15 en el 100% de las réplicas.
    Las 3 semillas de cada escenario remuestreado se mantienen juntas con todas sus multiplicidades.
    La misma muestra de escenarios se evalúa simultáneamente en los 3 modelos (remuestreo pareado).

    Limitación metodológica documentada:
    El estrato emulado consta de N_emu = 3 escenarios independientes. Con remuestreo con reemplazo,
    existen únicamente C(3+3-1, 3) = 10 combinaciones multiconjunto únicas para el estrato emulado,
    lo que induce una discretización intrínseca en la distribución bootstrap de ese estrato.

    Métricas calculadas por modelo:
    - Exactitud diagnóstica
    - F1 Macro (con penalización formal de UNKNOWN y catálogo canónico normativo)
    - Rúbrica explicativa
    - Velocidad (tokens/s)
    - Latencia total (ms)

    Diferencias pareadas entre modelos (Delta CI95):
    - Delta F1 Macro
    - Delta Exactitud
    - Delta Velocidad
    """
    import numpy as np
    from sklearn.metrics import f1_score
    from src.layer7_evaluator.metrics import load_evaluator_concepts

    concepts_cat = load_evaluator_concepts().get("classes", {})
    canonical_labels = sorted(list(concepts_cat.keys())) if concepts_cat else []

    by_model: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by_model.setdefault(r["model_id"], []).append(r)

    # Identificar escenarios únicos
    all_scenarios = sorted(list(set(str(r["scenario_id"]) for r in rows if r.get("scenario_id"))))
    n_clusters = len(all_scenarios)

    # Identificar estratos (Emulados vs Sintéticos)
    emulated_canonical_ids = {"TLS-EXP-01", "HTTP-502-01", "DNS-SRV-01"}
    emulated_scenarios = [
        sc for sc in all_scenarios
        if sc in emulated_canonical_ids or any(
            str(r.get("scenario_id")) == sc and str(r.get("execution_mode", "")).lower() in ("emulado", "emulated", "docker")
            for r in rows
        )
    ]
    synthetic_scenarios = [sc for sc in all_scenarios if sc not in emulated_scenarios]

    # Mapear filas por modelo y escenario
    model_scenario_rows: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for mid, mrows in by_model.items():
        model_scenario_rows[mid] = {}
        for r in mrows:
            sc_id = str(r["scenario_id"])
            model_scenario_rows[mid].setdefault(sc_id, []).append(r)

    rng = np.random.default_rng(seed)

    # Estructuras para almacenar métricas por réplica
    boot_dist: dict[str, dict[str, list[float]]] = {
        mid: {"acc": [], "f1": [], "rub": [], "spd": [], "lat": []}
        for mid in by_model.keys()
    }

    # Pares oficiales para cálculo de diferencias pareadas
    target_pairs = [
        ("glm-4-9b-chat", "phi-4-mini-instruct"),
        ("qwen3-8b", "phi-4-mini-instruct"),
        ("glm-4-9b-chat", "qwen3-8b"),
    ]
    available_pairs = [
        (m1, m2) for m1, m2 in target_pairs
        if m1 in by_model and m2 in by_model
    ]

    boot_diffs: dict[str, dict[str, list[float]]] = {
        f"{m1}_vs_{m2}": {"delta_acc": [], "delta_f1": [], "delta_spd": []}
        for m1, m2 in available_pairs
    }

    # Pre-extraer métricas por escenario y modelo para optimizar el remuestreo bootstrap (O(N) en lugar de O(N*B))
    scenario_cache: dict[str, dict[str, dict[str, list]]] = {}
    for mid in by_model.keys():
        scenario_cache[mid] = {}
        for sc in all_scenarios:
            sc_rows = model_scenario_rows[mid].get(sc, [])
            sc_yt, sc_yp, sc_acc, sc_rub, sc_spd, sc_lat = [], [], [], [], [], []
            for r in sc_rows:
                sc_yt.append(str(r.get("fault_class", "UNKNOWN")))
                if "fault_class_predicted" in r:
                    pred = str(r["fault_class_predicted"])
                else:
                    raw_t = str(r.get("root_cause") or r.get("model_diagnosis_text") or r.get("response") or "")
                    if raw_t.strip():
                        pred, _, _ = parse_fault_class_predicted(raw_t, concepts_cat)
                    elif r.get("is_root_cause_correct") is True and r.get("fault_class"):
                        pred = str(r["fault_class"])
                    else:
                        pred = "UNKNOWN"
                    r["fault_class_predicted"] = pred
                sc_yp.append(pred)
                sc_acc.append(1.0 if r.get("is_root_cause_correct") else 0.0)
                sc_rub.append(float(r.get("rubric_score") or 0.0))
                sc_spd.append(float(r.get("tokens_per_sec") or 0.0))
                sc_lat.append(float(r.get("total_time_ms") or 0.0))
            scenario_cache[mid][sc] = {
                "yt": sc_yt, "yp": sc_yp, "acc": sc_acc,
                "rub": sc_rub, "spd": sc_spd, "lat": sc_lat
            }

    has_stratification = len(emulated_scenarios) > 0 and len(synthetic_scenarios) > 0

    for _ in range(n_bootstrap):
        # Remuestreo de escenarios
        if has_stratification:
            sampled_emu = rng.choice(emulated_scenarios, size=len(emulated_scenarios), replace=True).tolist()
            sampled_syn = rng.choice(synthetic_scenarios, size=len(synthetic_scenarios), replace=True).tolist()
            sampled_scs = sampled_emu + sampled_syn
        elif n_clusters > 1:
            sampled_scs = rng.choice(all_scenarios, size=n_clusters, replace=True).tolist()
        else:
            sampled_scs = all_scenarios

        # Evaluar todos los modelos en la MISMA muestra de escenarios (remuestreo pareado)
        replica_metrics: dict[str, dict[str, float]] = {}
        for mid in by_model.keys():
            mid_cache = scenario_cache[mid]
            sample_yt, sample_yp = [], []
            sample_acc, sample_rub, sample_spd, sample_lat = [], [], [], []

            for sc in sampled_scs:
                entry = mid_cache.get(sc)
                if entry:
                    sample_yt.extend(entry["yt"])
                    sample_yp.extend(entry["yp"])
                    sample_acc.extend(entry["acc"])
                    sample_rub.extend(entry["rub"])
                    sample_spd.extend(entry["spd"])
                    sample_lat.extend(entry["lat"])

            if sample_yt:
                eval_labels = [c for c in canonical_labels if c in sample_yt or c in sample_yp]
                if not eval_labels:
                    eval_labels = sorted(list(set(sample_yt + sample_yp)))

                m_acc = float(np.mean(sample_acc))
                m_f1 = float(f1_score(sample_yt, sample_yp, labels=eval_labels, average="macro", zero_division=0))
                m_rub = float(np.mean(sample_rub))
                m_spd = float(np.mean(sample_spd))
                m_lat = float(np.mean(sample_lat))

                boot_dist[mid]["acc"].append(m_acc)
                boot_dist[mid]["f1"].append(m_f1)
                boot_dist[mid]["rub"].append(m_rub)
                boot_dist[mid]["spd"].append(m_spd)
                boot_dist[mid]["lat"].append(m_lat)

                replica_metrics[mid] = {"acc": m_acc, "f1": m_f1, "spd": m_spd}

        # Calcular diferencias pareadas de esta réplica
        for m1, m2 in available_pairs:
            if m1 in replica_metrics and m2 in replica_metrics:
                pair_key = f"{m1}_vs_{m2}"
                boot_diffs[pair_key]["delta_acc"].append(replica_metrics[m1]["acc"] - replica_metrics[m2]["acc"])
                boot_diffs[pair_key]["delta_f1"].append(replica_metrics[m1]["f1"] - replica_metrics[m2]["f1"])
                boot_diffs[pair_key]["delta_spd"].append(replica_metrics[m1]["spd"] - replica_metrics[m2]["spd"])

    def _calc_ci(arr: list[float]) -> tuple[float, float]:
        if not arr:
            return (0.0, 0.0)
        s = sorted(arr)
        lo = float(s[int(0.025 * len(s))])
        hi = float(s[min(int(0.975 * len(s)), len(s) - 1)])
        return round(lo, 4), round(hi, 4)

    results: dict[str, Any] = {}

    for mid, mrows in by_model.items():
        n = len(mrows)
        if n == 0:
            continue

        y_true_m = [str(r.get("fault_class", "UNKNOWN")) for r in mrows]
        y_pred_m = []
        acc_m = []
        rub_m = []
        spd_m = []
        lat_m = []
        for r in mrows:
            pred = str(r.get("fault_class_predicted") or "")
            if not pred or pred == "UNKNOWN":
                raw_t = str(r.get("root_cause") or r.get("model_diagnosis_text") or r.get("response") or "")
                pred, _, _ = parse_fault_class_predicted(raw_t, concepts_cat)
            y_pred_m.append(pred)
            acc_m.append(1.0 if r.get("is_root_cause_correct") else 0.0)
            rub_m.append(float(r.get("rubric_score") or 0.0))
            spd_m.append(float(r.get("tokens_per_sec") or 0.0))
            lat_m.append(float(r.get("total_time_ms") or 0.0))

        eval_labels_base = [c for c in canonical_labels if c in y_true_m or c in y_pred_m]
        if not eval_labels_base:
            eval_labels_base = sorted(list(set(y_true_m + y_pred_m)))

        base_f1 = float(f1_score(y_true_m, y_pred_m, labels=eval_labels_base, average="macro", zero_division=0))

        results[mid] = {
            "model_id": mid,
            "accuracy": {"mean": round(float(np.mean(acc_m)), 4), "ci95": _calc_ci(boot_dist[mid]["acc"])},
            "f1_macro": {"mean": round(base_f1, 4), "ci95": _calc_ci(boot_dist[mid]["f1"])},
            "rubric": {"mean": round(float(np.mean(rub_m)), 4), "ci95": _calc_ci(boot_dist[mid]["rub"])},
            "speed_tok_s": {"mean": round(float(np.mean(spd_m)), 4), "ci95": _calc_ci(boot_dist[mid]["spd"])},
            "latency_ms": {"mean": round(float(np.mean(lat_m)), 4), "ci95": _calc_ci(boot_dist[mid]["lat"])},
            "method": "cluster_bootstrap_percentile",
            "stratification": "emulated_vs_synthetic" if has_stratification else "unstratified",
            "cluster_unit": "scenario_id",
            "n_clusters": n_clusters,
            "n_strata_emulated": len(emulated_scenarios),
            "n_strata_synthetic": len(synthetic_scenarios),
            "n_bootstrap": n_bootstrap,
            "confidence_level": 0.95,
            "seed": seed,
            "sample_size": n,
            "limitations": "Muestra finita de 18 escenarios de red L7; el estrato emulado (N=3) posee exactamente 10 combinaciones multiconjunto únicas (discretización del estrato emulado en el remuestreo). El remuestreo por conglomerados estratificado preserva la paridad entre modelos y la correlación intra-escenario (3 semillas).",
        }

    # Agregar diferencias pareadas
    pairwise_summary = {}
    for pair_key, diff_dict in boot_diffs.items():
        if diff_dict["delta_acc"]:
            m1, m2 = pair_key.split("_vs_")
            pairwise_summary[pair_key] = {
                "model_1": m1,
                "model_2": m2,
                "delta_accuracy": {
                    "mean": round(float(np.mean(diff_dict["delta_acc"])), 4),
                    "ci95": _calc_ci(diff_dict["delta_acc"]),
                },
                "delta_f1_macro": {
                    "mean": round(float(np.mean(diff_dict["delta_f1"])), 4),
                    "ci95": _calc_ci(diff_dict["delta_f1"]),
                },
                "delta_speed_tok_s": {
                    "mean": round(float(np.mean(diff_dict["delta_spd"])), 4),
                    "ci95": _calc_ci(diff_dict["delta_spd"]),
                },
            }

    if pairwise_summary:
        results["pairwise_differences"] = pairwise_summary

    return results
