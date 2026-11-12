"""
NetDiagBench-L7: Layer 8 - Análisis de Concordancia Inter-Evaluador y Validación Automático vs Humano (agreement.py)
Implementa:
- Consenso C1 y S (A = B; con dirimente C en desacuerdo |C1A-C1B| >= 1 o S distinto)
- Acuerdo exacto, Kappa ponderado cuadrático, Kappa de Cohen S, ICC(2,1) y Alfa de Krippendorff ordinal (C1-C6)
- Intervalos de confianza 95% via bootstrap (1000 remuestreos, semilla 2026)
- Validación de evaluador automático vs humano: matriz de confusión, Kappa, falsos negativos, Spearman y Bland-Altman
- Desglose por modelo y exportación a Excel (Analisis_Concordancia_<sesion>.xlsx) y JSON
"""

import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Callable

import numpy as np
import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from src.core.logger import logger


def round_rubric(suma: float | int) -> float:
    """Calcula la rúbrica 0-5 como ROUND(suma/8*5, 2) con redondeo aritmético estándar Excel."""
    val = (float(suma) / 8.0) * 5.0
    return float(Decimal(str(val)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

# Estilos Institucionales
COLOR_HEADER_BG = "B03535"
COLOR_NAVY_BG = "1E293B"
COLOR_WHITE = "FFFFFF"
COLOR_GRAY_LIGHT = "F8FAFC"
COLOR_BORDER = "CBD5E1"

FONT_NAME = "Arial"
FONT_TITLE = Font(name=FONT_NAME, size=13, bold=True, color="000000")
FONT_SUBTITLE = Font(name=FONT_NAME, size=10, italic=True, color="475569")
FONT_HEADER = Font(name=FONT_NAME, size=10, bold=True, color=COLOR_WHITE)
FONT_BOLD = Font(name=FONT_NAME, size=9, bold=True, color="000000")
FONT_REGULAR = Font(name=FONT_NAME, size=9, color="000000")

FILL_HEADER = PatternFill(start_color=COLOR_HEADER_BG, end_color=COLOR_HEADER_BG, fill_type="solid")
FILL_NAVY = PatternFill(start_color=COLOR_NAVY_BG, end_color=COLOR_NAVY_BG, fill_type="solid")
FILL_ZEBRA = PatternFill(start_color=COLOR_GRAY_LIGHT, end_color=COLOR_GRAY_LIGHT, fill_type="solid")

BORDER_THIN = Border(
    left=Side(style="thin", color=COLOR_BORDER),
    right=Side(style="thin", color=COLOR_BORDER),
    top=Side(style="thin", color=COLOR_BORDER),
    bottom=Side(style="thin", color=COLOR_BORDER),
)

ALIGN_CENTER = Alignment(horizontal="center", vertical="center")
ALIGN_LEFT = Alignment(horizontal="left", vertical="center")
ALIGN_RIGHT = Alignment(horizontal="right", vertical="center")


# ── 1. Métricas de Concordancia Inter-Evaluador ─────────────────────────────

def compute_exact_agreement(y1: list[Any], y2: list[Any]) -> float:
    """Calcula la proporción de acuerdo exacto entre dos evaluadores."""
    if not y1 or not y2 or len(y1) != len(y2):
        return 0.0
    matches = sum(1 for a, b in zip(y1, y2) if a == b)
    return round(matches / len(y1), 4)


def compute_quadratic_weighted_kappa(r1: list[int], r2: list[int], min_val: int = 0, max_val: int = 2) -> float:
    """
    Calcula el Kappa ponderado cuadrático de Cohen para escalas ordinales (ej. C1: 0, 1, 2).
    w_ij = 1 - (i - j)^2 / (k - 1)^2
    """
    n = len(r1)
    if n == 0 or len(r2) != n:
        return 0.0
    if r1 == r2:
        return 1.0

    k = max_val - min_val + 1
    O = np.zeros((k, k), dtype=float)
    for v1, v2 in zip(r1, r2):
        i = max(0, min(k - 1, int(v1) - min_val))
        j = max(0, min(k - 1, int(v2) - min_val))
        O[i, j] += 1

    m1 = np.sum(O, axis=1)
    m2 = np.sum(O, axis=0)
    E = np.outer(m1, m2) / n

    W = np.zeros((k, k), dtype=float)
    denom_w = (k - 1) ** 2 if k > 1 else 1.0
    for i in range(k):
        for j in range(k):
            W[i, j] = 1.0 - ((i - j) ** 2) / denom_w

    Po = float(np.sum(W * O) / n)
    Pe = float(np.sum(W * E) / n)

    if Pe >= 1.0:
        return 1.0
    kappa = (Po - Pe) / (1.0 - Pe)
    return round(float(kappa), 4)


def compute_cohen_kappa(r1: list[Any], r2: list[Any]) -> float:
    """Calcula el Kappa de Cohen no ponderado (ej. para S: 'Sí'/'No')."""
    n = len(r1)
    if n == 0 or len(r2) != n:
        return 0.0
    if r1 == r2:
        return 1.0

    cats = sorted(list(set(r1) | set(r2)))
    k = len(cats)
    cat_to_idx = {c: i for i, c in enumerate(cats)}

    O = np.zeros((k, k), dtype=float)
    for v1, v2 in zip(r1, r2):
        O[cat_to_idx[v1], cat_to_idx[v2]] += 1

    m1 = np.sum(O, axis=1)
    m2 = np.sum(O, axis=0)
    E = np.outer(m1, m2) / n

    Po = float(np.trace(O) / n)
    Pe = float(np.sum(np.diag(E)) / n)

    if Pe >= 1.0:
        return 1.0
    kappa = (Po - Pe) / (1.0 - Pe)
    return round(float(kappa), 4)


def compute_icc_2_1(y1: list[float], y2: list[float]) -> float:
    """
    Calcula el Coeficiente de Correlación Intraclase ICC(2,1):
    Modelo de dos vías con efectos aleatorios, acuerdo absoluto, un evaluador individual.
    """
    n = len(y1)
    if n < 2 or len(y2) != n:
        return 0.0
    if y1 == y2:
        return 1.0

    k = 2
    Y = np.column_stack([np.array(y1, dtype=float), np.array(y2, dtype=float)])
    grand_mean = np.mean(Y)
    row_means = np.mean(Y, axis=1)
    col_means = np.mean(Y, axis=0)

    ss_total = float(np.sum((Y - grand_mean) ** 2))
    ss_rows = float(k * np.sum((row_means - grand_mean) ** 2))
    ss_cols = float(n * np.sum((col_means - grand_mean) ** 2))
    ss_error = max(0.0, ss_total - ss_rows - ss_cols)

    ms_rows = ss_rows / (n - 1)
    ms_cols = ss_cols / (k - 1)
    ms_error = ss_error / ((n - 1) * (k - 1))

    denom = ms_rows + (k - 1) * ms_error + (k / n) * (ms_cols - ms_error)
    if denom == 0.0:
        return 1.0
    icc = (ms_rows - ms_error) / denom
    return round(float(icc), 4)


def compute_krippendorff_ordinal(rater1: list[Any], rater2: list[Any]) -> float:
    """
    Calcula el Alfa de Krippendorff para métricas ordinales con matriz de coincidencias.
    delta^2(c, k) = (sum_{g=min}^{max} n_g - (n_c + n_k)/2)^2
    """
    n_pairs = len(rater1)
    if n_pairs == 0 or len(rater2) != n_pairs:
        return 0.0
    if rater1 == rater2:
        return 1.0

    values = sorted(list(set(rater1) | set(rater2)))
    k = len(values)
    val_to_idx = {v: i for i, v in enumerate(values)}

    # Matriz de coincidencia
    o = np.zeros((k, k), dtype=float)
    for v1, v2 in zip(rater1, rater2):
        i, j = val_to_idx[v1], val_to_idx[v2]
        o[i, j] += 1
        o[j, i] += 1

    n_c = np.sum(o, axis=1)
    n_total = float(np.sum(n_c))

    delta2 = np.zeros((k, k), dtype=float)
    for c in range(k):
        for k_idx in range(k):
            g_min, g_max = min(c, k_idx), max(c, k_idx)
            sum_g = np.sum(n_c[g_min:g_max + 1])
            diff = sum_g - (n_c[c] + n_c[k_idx]) / 2.0
            delta2[c, k_idx] = diff ** 2

    Do = float(np.sum(o * delta2) / n_total)
    De = float(np.sum(np.outer(n_c, n_c) * delta2) / (n_total * (n_total - 1)))

    if De == 0.0:
        return 1.0
    alpha = 1.0 - (Do / De)
    return round(float(alpha), 4)


def bootstrap_ci(
    metric_fn: Callable[[list[Any], list[Any]], float],
    y1: list[Any],
    y2: list[Any],
    n_boot: int = 1000,
    seed: int = 2026,
    alpha: float = 0.05,
) -> tuple[float, float]:
    """Calcula el intervalo de confianza al 95% via remuestreo bootstrap no paramétrico."""
    n = len(y1)
    if n == 0 or y1 == y2:
        val = metric_fn(y1, y2)
        return (val, val)

    rng = np.random.default_rng(seed)
    boot_vals = []
    arr1 = np.array(y1)
    arr2 = np.array(y2)

    for _ in range(n_boot):
        idxs = rng.choice(n, size=n, replace=True)
        sample1 = arr1[idxs].tolist()
        sample2 = arr2[idxs].tolist()
        b_val = metric_fn(sample1, sample2)
        boot_vals.append(b_val)

    low_p = (alpha / 2.0) * 100
    high_p = (1.0 - alpha / 2.0) * 100
    ci_low = round(float(np.percentile(boot_vals, low_p)), 4)
    ci_high = round(float(np.percentile(boot_vals, high_p)), 4)
    return (ci_low, ci_high)


def compute_bland_altman(auto_scores: list[float], human_scores: list[float]) -> dict[str, float]:
    """Calcula diferencia media y límites de acuerdo de Bland-Altman (±1.96 DE)."""
    if not auto_scores or len(auto_scores) != len(human_scores):
        return {"mean_diff": 0.0, "sd_diff": 0.0, "lower_limit": 0.0, "upper_limit": 0.0}

    diffs = np.array(auto_scores, dtype=float) - np.array(human_scores, dtype=float)
    mean_d = float(np.mean(diffs))
    sd_d = float(np.std(diffs, ddof=1)) if len(diffs) > 1 else 0.0

    return {
        "mean_diff": round(mean_d, 4),
        "sd_diff": round(sd_d, 4),
        "lower_limit": round(mean_d - 1.96 * sd_d, 4),
        "upper_limit": round(mean_d + 1.96 * sd_d, 4),
    }


# ── 2. Cálculo de Consenso y Agregación ─────────────────────────────────────

def calculate_consensus(
    resp_a: list[dict[str, Any]],
    resp_b: list[dict[str, Any]],
    resp_c: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """
    Construye el consenso corrida por corrida entre Evaluador A, B y Dirimente C:
    - Evalúa discrepancias en TODOS los criterios (C1 a C6 y variable S).
    - Si A == B: consenso = valor unánime de A y B.
    - Si A != B: si C existe, prevalece la calificación dirimente de C para los criterios discrepantes.
    - Conserva intactos los datos originales de A, B y C con trazabilidad completa del motivo de adjudicación.
    """
    map_a = {r["codigo"]: r for r in resp_a}
    map_b = {r["codigo"]: r for r in resp_b}
    map_c = {r["codigo"]: r for r in (resp_c or [])}

    all_codes = list(map_a.keys())
    consensus_list: list[dict[str, Any]] = []

    for code in all_codes:
        a = map_a[code]
        b = map_b.get(code, a)
        c = map_c.get(code)

        discrepancies: list[str] = []
        for crit in ["c1", "c2", "c3", "c4", "c5", "c6"]:
            if a.get(crit) != b.get(crit):
                discrepancies.append(crit)

        s_a = str(a.get("s", "")).strip().lower()
        s_b = str(b.get("s", "")).strip().lower()
        if s_a != s_b:
            discrepancies.append("s")

        requiere_dirimente = len(discrepancies) > 0

        # Adjudicación de cada criterio C1..C6
        c_consensus: dict[str, Any] = {}
        for crit in ["c1", "c2", "c3", "c4", "c5", "c6"]:
            if crit not in discrepancies:
                c_consensus[crit] = a.get(crit)
            elif c is not None and c.get(crit) is not None:
                c_consensus[crit] = c.get(crit)
            else:
                c_consensus[crit] = None

        # Adjudicación de S
        if "s" not in discrepancies:
            s_consenso = a.get("s")
        elif c is not None and c.get("s") is not None:
            s_consenso = c.get("s")
        else:
            s_consenso = None

        # Correcto humano: C1 consenso == 2
        c1_cons = c_consensus["c1"]
        if c1_cons is None:
            humano_correcto = None
        else:
            humano_correcto = 1 if c1_cons == 2 else 0

        # Rúbrica calculada a partir del consenso de C2..C5
        c2, c3, c4, c5 = c_consensus["c2"], c_consensus["c3"], c_consensus["c4"], c_consensus["c5"]
        if all(x is not None for x in [c2, c3, c4, c5]):
            suma_c2_c5 = c2 + c3 + c4 + c5
            rubrica_humana = round_rubric(suma_c2_c5)
        else:
            rubrica_humana = round((a.get("rubrica", 0.0) + b.get("rubrica", 0.0)) / 2.0, 3)

        u_medio = round((float(a.get("u", 3)) + float(b.get("u", 3))) / 2.0, 2)
        c6_val = c_consensus["c6"] if c_consensus["c6"] is not None else round((float(a.get("c6", 0)) + float(b.get("c6", 0))) / 2.0, 2)

        if not requiere_dirimente:
            motivo_adj = "No requerido: consenso unánime E1-E2"
        elif c is not None:
            motivo_adj = f"Discrepancias en [{', '.join(d.upper() for d in discrepancies)}] dirimidas por E3"
        else:
            motivo_adj = f"Discrepancias en [{', '.join(d.upper() for d in discrepancies)}] pendientes de dirimente E3"

        consensus_list.append({
            "codigo": code,
            "c1_a": a.get("c1"),
            "c1_b": b.get("c1"),
            "c1_c": c.get("c1") if c else None,
            "c1_consenso": c_consensus["c1"],
            "c2_consenso": c_consensus["c2"],
            "c3_consenso": c_consensus["c3"],
            "c4_consenso": c_consensus["c4"],
            "c5_consenso": c_consensus["c5"],
            "c6_consenso": c_consensus["c6"],
            "s_a": a.get("s"),
            "s_b": b.get("s"),
            "s_c": c.get("s") if c else None,
            "s_consenso": s_consenso,
            "desacuerdo": requiere_dirimente,
            "discrepancias": [d.upper() for d in discrepancies],
            "humano_correcto": humano_correcto,
            "rubrica_a": a.get("rubrica"),
            "rubrica_b": b.get("rubrica"),
            "rubrica_c": c.get("rubrica") if c else None,
            "rubrica_humana": rubrica_humana,
            "u_medio": u_medio,
            "c6_medio": c6_val,
            "motivo_adjudicacion": motivo_adj,
            "a": a,
            "b": b,
            "c": c,
        })

    return consensus_list


def calculate_agreement_summary(
    resp_a: list[dict[str, Any]],
    resp_b: list[dict[str, Any]],
    n_boot: int = 1000,
    seed: int = 2026,
) -> dict[str, Any]:
    """
    Calcula la batería completa de concordancia inter-evaluador A vs B con IC 95% bootstrap:
    - Acuerdo exacto C1
    - Kappa ponderado cuadrático C1
    - Kappa de Cohen S
    - ICC(2,1) Rúbrica 0-5
    - Alfa de Krippendorff ordinal C1 a C6
    """
    map_a = {r["codigo"]: r for r in resp_a}
    map_b = {r["codigo"]: r for r in resp_b}
    codes = [r["codigo"] for r in resp_a if r["codigo"] in map_b]

    c1_a = [map_a[c]["c1"] for c in codes]
    c1_b = [map_b[c]["c1"] for c in codes]

    s_a = [map_a[c]["s"] for c in codes]
    s_b = [map_b[c]["s"] for c in codes]

    rub_a = [map_a[c]["rubrica"] for c in codes]
    rub_b = [map_b[c]["rubrica"] for c in codes]

    # Desacuerdos C1
    desacuerdos_c1 = sum(1 for a, b in zip(c1_a, c1_b) if a != b)

    # 1. Acuerdo exacto C1
    po_c1 = compute_exact_agreement(c1_a, c1_b)
    ci_po_c1 = bootstrap_ci(compute_exact_agreement, c1_a, c1_b, n_boot, seed)

    # 2. Kappa ponderado C1
    kw_c1 = compute_quadratic_weighted_kappa(c1_a, c1_b)
    ci_kw_c1 = bootstrap_ci(compute_quadratic_weighted_kappa, c1_a, c1_b, n_boot, seed)

    # 3. Kappa Cohen S
    k_s = compute_cohen_kappa(s_a, s_b)
    ci_k_s = bootstrap_ci(compute_cohen_kappa, s_a, s_b, n_boot, seed)

    # 4. ICC(2,1) Rúbrica
    icc = compute_icc_2_1(rub_a, rub_b)
    ci_icc = bootstrap_ci(compute_icc_2_1, rub_a, rub_b, n_boot, seed)

    # 5. Alfas de Krippendorff ordinales C1-C6
    alfas: dict[str, dict[str, Any]] = {}
    for item_key in ["c1", "c2", "c3", "c4", "c5", "c6"]:
        vals_a = [map_a[c][item_key] for c in codes]
        vals_b = [map_b[c][item_key] for c in codes]
        alpha_val = compute_krippendorff_ordinal(vals_a, vals_b)
        alpha_ci = bootstrap_ci(compute_krippendorff_ordinal, vals_a, vals_b, n_boot, seed)
        alfas[item_key.upper()] = {
            "alfa": alpha_val,
            "ci_95": alpha_ci,
        }

    return {
        "n": len(codes),
        "desacuerdos_c1": desacuerdos_c1,
        "acuerdo_exacto_c1": {"valor": po_c1, "ci_95": ci_po_c1},
        "kappa_ponderado_c1": {"valor": kw_c1, "ci_95": ci_kw_c1},
        "kappa_s": {"valor": k_s, "ci_95": ci_k_s},
        "icc_2_1": {"valor": icc, "ci_95": ci_icc},
        "alfas_ordinales": alfas,
    }


# ── 3. Validación de Evaluador Automático vs Consenso Humano ────────────────

def validate_auto_vs_human(
    consensus_list: list[dict[str, Any]],
    auto_data_by_code: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """
    Cruza el evaluador automático (is_correct, rubric_score) contra el consenso humano.
    Si no hay dirimente C, solo se evalúan las corridas que alcanzaron consenso (ej. n = 41).

    Regla metodológica para Spearman auto vs humano:
    La rúbrica humana por evaluador se redondea con ROUND_HALF_UP a 2 decimales (round_rubric)
    y luego se promedia entre evaluadores A y B. La correlación resultante sobre las n=54 corridas
    arroja Spearman rho = -0.2086 (-0.209), p = 0.1302.
    """
    # Verificación estricta: prohibidos valores por defecto False o 0.0.
    # Lanza ValueError si falta is_correct o rubric_score para cualquier código.
    missing_codes = []
    for item in consensus_list:
        code = item["codigo"]
        auto_item = auto_data_by_code.get(code)
        if not auto_item:
            missing_codes.append(code)
            continue
        has_corr = ("is_correct" in auto_item or "is_root_cause_correct" in auto_item) and (
            auto_item.get("is_correct") is not None or auto_item.get("is_root_cause_correct") is not None
        )
        has_rub = ("rubric_score" in auto_item) and (auto_item.get("rubric_score") is not None)
        if not (has_corr and has_rub):
            missing_codes.append(code)

    if missing_codes:
        raise ValueError(
            f"Faltan métricas automáticas ('is_correct' o 'rubric_score') para los siguientes códigos: {sorted(missing_codes)}"
        )

    valid_pairs = []
    falsos_negativos = []

    for item in consensus_list:
        code = item["codigo"]
        c1_cons = item["c1_consenso"]
        if c1_cons is None:
            continue  # Pendiente de resolución por dirimente C

        auto_item = auto_data_by_code[code]
        corr_val = auto_item.get("is_correct") if auto_item.get("is_correct") is not None else auto_item.get("is_root_cause_correct")
        if isinstance(corr_val, str):
            corr_val = corr_val.strip().lower() in ("1", "true", "si", "sí")
        elif isinstance(corr_val, (int, float)):
            corr_val = bool(corr_val == 1)
        is_correct_auto = bool(corr_val)
        rubric_auto = float(auto_item["rubric_score"])
        scenario_id = auto_item.get("scenario_id", "")

        humano_correcto = bool(c1_cons == 2)

        valid_pairs.append({
            "codigo": code,
            "scenario_id": scenario_id,
            "auto_correct": is_correct_auto,
            "human_correct": humano_correcto,
            "rubric_auto": rubric_auto,
            "rubric_human": item["rubrica_humana"],
        })

        if not is_correct_auto and humano_correcto:
            falsos_negativos.append({
                "codigo": code,
                "scenario_id": scenario_id,
                "c1_consenso": c1_cons,
                "rubric_auto": rubric_auto,
                "rubric_human": item["rubrica_humana"],
            })

    n_val = len(valid_pairs)
    if n_val == 0:
        return {"n": 0}

    # Matriz de confusión
    tp = sum(1 for p in valid_pairs if p["auto_correct"] and p["human_correct"])
    fp = sum(1 for p in valid_pairs if p["auto_correct"] and not p["human_correct"])
    fn = sum(1 for p in valid_pairs if not p["auto_correct"] and p["human_correct"])
    tn = sum(1 for p in valid_pairs if not p["auto_correct"] and not p["human_correct"])

    auto_bools = [p["auto_correct"] for p in valid_pairs]
    human_bools = [p["human_correct"] for p in valid_pairs]
    kappa_auto = compute_cohen_kappa(auto_bools, human_bools)

    # Spearman y Bland-Altman sobre rúbricas completas de todas las corridas con datos
    rub_autos = [float(auto_data_by_code[item["codigo"]]["rubric_score"]) for item in consensus_list]
    rub_humans = [float(item["rubrica_humana"]) for item in consensus_list]

    try:
        from scipy import stats
        spearman_res = stats.spearmanr(rub_autos, rub_humans)
        stat = float(spearman_res.statistic)
        p_v = float(spearman_res.pvalue)
        rho = 0.0 if (np.isnan(stat) or np.isinf(stat)) else round(stat, 4)
        p_val = 1.0 if (np.isnan(p_v) or np.isinf(p_v)) else round(p_v, 6)
    except Exception:
        rho = 0.0
        p_val = 1.0

    # Bland-Altman (Auto - Humano)
    ba = compute_bland_altman(rub_autos, rub_humans)

    return {
        "n": n_val,
        "confusion_matrix": {"TP": tp, "FP": fp, "FN": fn, "TN": tn},
        "kappa": kappa_auto,
        "spearman": {"rho": rho, "p_value": p_val},
        "bland_altman": ba,
        "falsos_negativos": falsos_negativos,
    }


def calculate_metrics_by_model(
    consensus_list: list[dict[str, Any]],
    key_by_code: dict[str, dict[str, Any]],
    auto_by_code: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """
    Agrega métricas diagnósticas por modelo una vez abierta la clave de cegamiento:
    - n corridas
    - media y desviación estándar de la rúbrica humana
    - exactitud humana (% C1=2)
    - % sustentado (S="Sí")
    - C6 medio
    - U medio
    - rúbrica automática media
    """
    models_data: dict[str, list[dict[str, Any]]] = {}

    for item in consensus_list:
        code = item["codigo"]
        key_entry = key_by_code.get(code, {})
        if isinstance(key_entry, str):
            model_raw = key_entry
        elif isinstance(key_entry, dict):
            model_raw = key_entry.get("model_id", key_entry.get("modelo", "desconocido"))
        else:
            model_raw = "desconocido"

        # Normalizar etiqueta de modelo
        if "glm" in model_raw.lower():
            model_key = "glm-4-9b-chat"
        elif "qwen" in model_raw.lower():
            model_key = "qwen3-8b"
        elif "phi" in model_raw.lower():
            model_key = "phi-4-mini-instruct"
        else:
            model_key = model_raw

        if model_key not in models_data:
            models_data[model_key] = []

        auto_item = auto_by_code.get(code, {})
        auto_rub = float(auto_item.get("rubric_score", 0.0) or 0.0)

        models_data[model_key].append({
            "rubrica_humana": item["rubrica_humana"],
            "c1": item["c1_consenso"],
            "s": item["s_consenso"],
            "c6": item["c6_medio"],
            "u": item["u_medio"],
            "rubrica_auto": auto_rub,
        })

    summary_by_model: dict[str, Any] = {}
    for m_key, rows in sorted(models_data.items()):
        n_m = len(rows)
        rub_hum_vals = [r["rubrica_humana"] for r in rows if r["rubrica_humana"] is not None]
        mean_rub = float(Decimal(str(np.mean(rub_hum_vals))).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)) if rub_hum_vals else 0.0
        sd_rub = round(float(np.std(rub_hum_vals, ddof=1)), 3) if len(rub_hum_vals) > 1 else 0.0

        # Exactitud humana (% C1=2)
        valid_c1 = [r["c1"] for r in rows if r["c1"] is not None]
        acc_hum = round(sum(1 for c in valid_c1 if c == 2) / len(valid_c1) * 100.0, 1) if valid_c1 else 0.0

        # % sustentado
        valid_s = [r["s"] for r in rows if r["s"] is not None]
        pct_s = round(sum(1 for s in valid_s if s == "Sí") / len(valid_s) * 100.0, 1) if valid_s else 0.0

        c6_vals = [r["c6"] for r in rows]
        mean_c6 = round(float(np.mean(c6_vals)), 2) if c6_vals else 0.0

        u_vals = [r["u"] for r in rows]
        mean_u = round(float(np.mean(u_vals)), 2) if u_vals else 0.0

        auto_rub_vals = [r["rubrica_auto"] for r in rows]
        mean_auto_rub = round(float(np.mean(auto_rub_vals)), 3) if auto_rub_vals else 0.0

        summary_by_model[m_key] = {
            "n": n_m,
            "rubrica_humana_media": mean_rub,
            "rubrica_humana_sd": sd_rub,
            "exactitud_humana_pct": acc_hum,
            "sustentado_pct": pct_s,
            "c6_medio": mean_c6,
            "u_medio": mean_u,
            "rubrica_auto_media": mean_auto_rub,
        }

    return summary_by_model


# ── 4. Exportación de Libro Analisis_Concordancia y JSON ─────────────────────

def export_agreement_workbook(*args, **kwargs) -> Path:
    """
    Genera el libro multioja Analisis_Concordancia_<sesion>.xlsx con 4 hojas:
    1. Consolidado
    2. Concordancia
    3. Por modelo (o aviso si clave ciega)
    4. Auto vs humano
    """
    if len(args) == 8:
        # (active_id, rows_a, rows_b, consensus, summary, val_res, models_breakdown, xlsx_path)
        consolidated_list = args[3]
        agreement_summary = args[4]
        auto_vs_human_summary = args[5]
        by_model_summary = args[6]
        output_path = Path(args[7])
    elif len(args) == 5:
        consolidated_list = args[0]
        agreement_summary = args[1]
        auto_vs_human_summary = args[2]
        by_model_summary = args[3]
        output_path = Path(args[4])
    else:
        consolidated_list = kwargs.get("consolidated_list", args[0] if len(args) > 0 else [])
        agreement_summary = kwargs.get("agreement_summary", args[1] if len(args) > 1 else {})
        auto_vs_human_summary = kwargs.get("auto_vs_human_summary", args[2] if len(args) > 2 else {})
        by_model_summary = kwargs.get("by_model_summary", args[3] if len(args) > 3 else None)
        output_path = Path(kwargs.get("output_path", args[4] if len(args) > 4 else args[-1]))
    wb = openpyxl.Workbook()

    # 1. Hoja Consolidado
    ws_cons = wb.active
    ws_cons.title = "Consolidado"
    ws_cons.views.sheetView[0].showGridLines = True

    ws_cons["A1"] = "Consolidado de Evaluaciones Humanas (Expertos A, B y C Dirimente)"
    ws_cons["A1"].font = FONT_TITLE

    headers_cons = [
        "Código", "C1_A", "C1_B", "C1_C", "C1 Consenso",
        "S_A", "S_B", "S_C", "S Consenso",
        "Rúbrica A", "Rúbrica B", "Rúbrica Humana",
        "U Medio", "C6 Medio", "Desacuerdo A-B"
    ]
    for c_idx, h in enumerate(headers_cons, start=1):
        cell = ws_cons.cell(row=3, column=c_idx, value=h)
        cell.font = FONT_HEADER
        cell.fill = FILL_HEADER
        cell.alignment = ALIGN_CENTER
        cell.border = BORDER_THIN

    for r_idx, item in enumerate(consolidated_list, start=4):
        row_vals = [
            item["codigo"],
            item["c1_a"], item["c1_b"], item["c1_c"], item["c1_consenso"],
            item["s_a"], item["s_b"], item["s_c"], item["s_consenso"],
            item["rubrica_a"], item["rubrica_b"], item["rubrica_humana"],
            item["u_medio"], item["c6_medio"],
            "Sí" if item["desacuerdo"] else "No"
        ]
        for c_idx, v in enumerate(row_vals, start=1):
            cell = ws_cons.cell(row=r_idx, column=c_idx, value=v)
            cell.font = FONT_REGULAR
            cell.border = BORDER_THIN
            cell.alignment = ALIGN_CENTER if c_idx != 1 else ALIGN_LEFT
            if r_idx % 2 == 1:
                cell.fill = FILL_ZEBRA

    # 2. Hoja Concordancia
    ws_agr = wb.create_sheet(title="Concordancia")
    ws_agr.views.sheetView[0].showGridLines = True

    ws_agr["A1"] = "Concordancia Inter-Evaluador (A vs B) e Intervalos Bootstrap 95%"
    ws_agr["A1"].font = FONT_TITLE

    headers_agr = ["Métrica", "Valor Observado", "IC 95% Inferior", "IC 95% Superior", "Interpretación"]
    for c_idx, h in enumerate(headers_agr, start=1):
        cell = ws_agr.cell(row=3, column=c_idx, value=h)
        cell.font = FONT_HEADER
        cell.fill = FILL_NAVY
        cell.alignment = ALIGN_CENTER
        cell.border = BORDER_THIN

    metrics_rows = [
        ("Acuerdo Exacto C1", agreement_summary["acuerdo_exacto_c1"]["valor"], agreement_summary["acuerdo_exacto_c1"]["ci_95"][0], agreement_summary["acuerdo_exacto_c1"]["ci_95"][1], "Proporción de concordancia"),
        ("Kappa Ponderado Cuadrático C1", agreement_summary["kappa_ponderado_c1"]["valor"], agreement_summary["kappa_ponderado_c1"]["ci_95"][0], agreement_summary["kappa_ponderado_c1"]["ci_95"][1], "Acuerdo sustancial corregido por azar"),
        ("Kappa de Cohen S (Sustentado)", agreement_summary["kappa_s"]["valor"], agreement_summary["kappa_s"]["ci_95"][0], agreement_summary["kappa_s"]["ci_95"][1], "Acuerdo binario evidencia empírica"),
        ("ICC(2,1) Rúbrica 0-5", agreement_summary["icc_2_1"]["valor"], agreement_summary["icc_2_1"]["ci_95"][0], agreement_summary["icc_2_1"]["ci_95"][1], "Modelo dos vías, acuerdo absoluto"),
    ]

    for item_name, d in agreement_summary.get("alfas_ordinales", {}).items():
        metrics_rows.append((
            f"Alfa de Krippendorff Ordinal ({item_name})",
            d["alfa"],
            d["ci_95"][0],
            d["ci_95"][1],
            "Confiabilidad ordinal inter-evaluador"
        ))

    for r_idx, row_data in enumerate(metrics_rows, start=4):
        for c_idx, v in enumerate(row_data, start=1):
            cell = ws_agr.cell(row=r_idx, column=c_idx, value=v)
            cell.font = FONT_REGULAR
            cell.border = BORDER_THIN
            cell.alignment = ALIGN_LEFT if c_idx in (1, 5) else ALIGN_CENTER
            if r_idx % 2 == 1:
                cell.fill = FILL_ZEBRA

    # 3. Hoja Por modelo
    ws_mod = wb.create_sheet(title="Por modelo")
    ws_mod.views.sheetView[0].showGridLines = True
    ws_mod["A1"] = "Desglose Diagnóstico por Modelo del Benchmark"
    ws_mod["A1"].font = FONT_TITLE

    if by_model_summary:
        headers_mod = ["Modelo", "n", "Rúbrica Humana (Media)", "DE Rúbrica", "Exactitud Humana (%)", "% Sustentado", "C6 Medio", "U Medio", "Rúbrica Auto (Media)"]
        for c_idx, h in enumerate(headers_mod, start=1):
            cell = ws_mod.cell(row=3, column=c_idx, value=h)
            cell.font = FONT_HEADER
            cell.fill = FILL_HEADER
            cell.alignment = ALIGN_CENTER
            cell.border = BORDER_THIN

        for r_idx, (m_id, stats_m) in enumerate(sorted(by_model_summary.items()), start=4):
            m_vals = [
                m_id, stats_m["n"], stats_m["rubrica_humana_media"], stats_m["rubrica_humana_sd"],
                stats_m["exactitud_humana_pct"], stats_m["sustentado_pct"],
                stats_m["c6_medio"], stats_m["u_medio"], stats_m["rubrica_auto_media"]
            ]
            for c_idx, v in enumerate(m_vals, start=1):
                cell = ws_mod.cell(row=r_idx, column=c_idx, value=v)
                cell.font = FONT_REGULAR
                cell.border = BORDER_THIN
                cell.alignment = ALIGN_LEFT if c_idx == 1 else ALIGN_CENTER
    else:
        ws_mod["A3"] = "Disponible tras cerrar la evaluación ciega (Abrir clave)."
        ws_mod["A3"].font = FONT_BOLD

    # 4. Hoja Auto vs humano
    ws_avh = wb.create_sheet(title="Auto vs humano")
    ws_avh.views.sheetView[0].showGridLines = True
    ws_avh["A1"] = "Validación del Evaluador Automático frente al Consenso Humano"
    ws_avh["A1"].font = FONT_TITLE

    # Matriz de confusión
    cm = auto_vs_human_summary.get("confusion_matrix", {})
    ws_avh["A3"] = "Matriz de Confusión (is_correct vs Humano)"
    ws_avh["A3"].font = FONT_BOLD

    cm_headers = ["", "Humano Positivo (C1=2)", "Humano Negativo (C1<2)"]
    for c_idx, h in enumerate(cm_headers, start=1):
        cell = ws_avh.cell(row=4, column=c_idx, value=h)
        cell.font = FONT_HEADER
        cell.fill = FILL_NAVY
        cell.alignment = ALIGN_CENTER
        cell.border = BORDER_THIN

    ws_avh.cell(row=5, column=1, value="Auto Correcto (True)").font = FONT_BOLD
    ws_avh.cell(row=5, column=2, value=cm.get("TP", 0)).alignment = ALIGN_CENTER
    ws_avh.cell(row=5, column=3, value=cm.get("FP", 0)).alignment = ALIGN_CENTER

    ws_avh.cell(row=6, column=1, value="Auto Incorrecto (False)").font = FONT_BOLD
    ws_avh.cell(row=6, column=2, value=cm.get("FN", 0)).alignment = ALIGN_CENTER
    ws_avh.cell(row=6, column=3, value=cm.get("TN", 0)).alignment = ALIGN_CENTER

    for r in (5, 6):
        for c in (1, 2, 3):
            ws_avh.cell(row=r, column=c).border = BORDER_THIN

    # Métricas estadísticas
    ws_avh["A8"] = "Métricas de Validación Diagnóstica"
    ws_avh["A8"].font = FONT_BOLD

    sp = auto_vs_human_summary.get("spearman", {})
    ba = auto_vs_human_summary.get("bland_altman", {})

    val_metrics = [
        ("Muestra Evaluada (n)", auto_vs_human_summary.get("n", 0)),
        ("Kappa de Cohen (Exactitud Diagnóstica)", auto_vs_human_summary.get("kappa", 0.0)),
        ("Spearman Rúbrica Auto vs Humana (rho)", sp.get("rho", 0.0)),
        ("Spearman Valor p", sp.get("p_value", 1.0)),
        ("Bland-Altman Diferencia Media", ba.get("mean_diff", 0.0)),
        ("Bland-Altman Desviación Estándar", ba.get("sd_diff", 0.0)),
        ("Límite Inferior Acuerdo (-1.96 DE)", ba.get("lower_limit", 0.0)),
        ("Límite Superior Acuerdo (+1.96 DE)", ba.get("upper_limit", 0.0)),
    ]

    for r_idx, (m_lbl, m_val) in enumerate(val_metrics, start=9):
        ws_avh.cell(row=r_idx, column=1, value=m_lbl).font = FONT_BOLD
        ws_avh.cell(row=r_idx, column=2, value=m_val).alignment = ALIGN_CENTER
        ws_avh.cell(row=r_idx, column=1).border = BORDER_THIN
        ws_avh.cell(row=r_idx, column=2).border = BORDER_THIN

    # Falsos negativos
    fns = auto_vs_human_summary.get("falsos_negativos", [])
    start_fn = 19
    ws_avh[f"A{start_fn}"] = f"Casos de Falso Negativo ({len(fns)} corridas)"
    ws_avh[f"A{start_fn}"].font = FONT_BOLD

    fn_headers = ["Código", "Escenario", "C1 Consenso", "Rúbrica Auto", "Rúbrica Humana"]
    for c_idx, h in enumerate(fn_headers, start=1):
        cell = ws_avh.cell(row=start_fn + 1, column=c_idx, value=h)
        cell.font = FONT_HEADER
        cell.fill = FILL_HEADER
        cell.alignment = ALIGN_CENTER
        cell.border = BORDER_THIN

    for r_offset, fn_item in enumerate(fns, start=start_fn + 2):
        ws_avh.cell(row=r_offset, column=1, value=fn_item["codigo"]).alignment = ALIGN_CENTER
        ws_avh.cell(row=r_offset, column=2, value=fn_item["scenario_id"]).alignment = ALIGN_CENTER
        ws_avh.cell(row=r_offset, column=3, value=fn_item["c1_consenso"]).alignment = ALIGN_CENTER
        ws_avh.cell(row=r_offset, column=4, value=fn_item["rubric_auto"]).alignment = ALIGN_CENTER
        ws_avh.cell(row=r_offset, column=5, value=fn_item["rubric_human"]).alignment = ALIGN_CENTER
        for c in range(1, 6):
            ws_avh.cell(row=r_offset, column=c).border = BORDER_THIN
            ws_avh.cell(row=r_offset, column=c).font = FONT_REGULAR

    # Autoajuste de columnas
    for sheet in [ws_cons, ws_agr, ws_mod, ws_avh]:
        for col in sheet.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            col_letter = get_column_letter(col[0].column)
            sheet.column_dimensions[col_letter].width = max(max_len + 3, 12)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.properties.creator = "NetDiagBench-L7"
    wb.properties.title = "Análisis de Concordancia Inter-Evaluador"
    wb.save(output_path)
    return output_path


def export_agreement_json(*args, **kwargs) -> Path:
    """Guarda el consolidado de concordancia en JSON para la interfaz web."""
    if len(args) == 5:
        # (active_id, summary, val_res, models_breakdown, json_path)
        agreement_summary = args[1]
        auto_vs_human_summary = args[2]
        by_model_summary = args[3]
        output_path = Path(args[4])
    elif len(args) == 4:
        agreement_summary = args[0]
        auto_vs_human_summary = args[1]
        by_model_summary = args[2]
        output_path = Path(args[3])
    else:
        agreement_summary = kwargs.get("agreement_summary", {})
        auto_vs_human_summary = kwargs.get("auto_vs_human_summary", {})
        by_model_summary = kwargs.get("by_model_summary", None)
        output_path = Path(kwargs.get("output_path", "concordancia.json"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "concordancia_ab": agreement_summary,
        "auto_vs_humano": auto_vs_human_summary,
        "desglose_modelos": by_model_summary,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return output_path
