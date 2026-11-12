"""
NetDiagBench-L7: Layer 8 - Módulo de Análisis Correlacional y Reporte Técnico (correlation_report.py)
Cruza las evaluaciones humanas (consenso A, B y C dirimente) con las métricas del benchmark:
1. Matriz interítem de Spearman (C1-C6, S, U) con IC 95% bootstrap.
2. Validez convergente: humano vs automático (Spearman, Pearson, Bland-Altman, Phi/Kappa).
3. Calidad frente a costo (TTFT, tok/s, latencia, energía).
4. Calidad frente a tamaño de modelo (Spearman, Kruskal-Wallis, d de Cohen).
5. Desglose por categoría de escenario de red (Kruskal-Wallis).
6. Concordancia por ítem entre expertos (Spearman A vs B + Alfa ordinal).
Soporta regla de cegamiento estricta (análisis 3, 4 y 5 bloqueados hasta abrir la clave).
Exporta a Excel (hojas Correlación y Datos_correlación), HTML/PDF interactivo y JSON.
"""

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from src.core.logger import logger
from src.layer8_human_eval.agreement import (
    bootstrap_ci,
    compute_bland_altman,
    compute_cohen_kappa,
    compute_krippendorff_ordinal,
)
from src.layer8_human_eval.sampler import (
    FORBIDDEN_TERMS,
    anonymize_text,
    check_forbidden_terms,
)

# Paleta Institucional
COLOR_PRIMARY = "B03535"
COLOR_NAVY = "1E293B"
COLOR_BLUE = "0284C7"
COLOR_WHITE = "FFFFFF"
COLOR_LIGHT_GRAY = "F8FAFC"
COLOR_BORDER = "CBD5E1"

FONT_NAME = "Arial"
FONT_TITLE = Font(name=FONT_NAME, size=13, bold=True, color="000000")
FONT_HEADER = Font(name=FONT_NAME, size=10, bold=True, color=COLOR_WHITE)
FONT_BOLD = Font(name=FONT_NAME, size=9, bold=True, color="000000")
FONT_REGULAR = Font(name=FONT_NAME, size=9, color="000000")

BORDER_THIN = Border(
    left=Side(style="thin", color=COLOR_BORDER),
    right=Side(style="thin", color=COLOR_BORDER),
    top=Side(style="thin", color=COLOR_BORDER),
    bottom=Side(style="thin", color=COLOR_BORDER),
)

FILL_NAVY = PatternFill(start_color=COLOR_NAVY, end_color=COLOR_NAVY, fill_type="solid")
FILL_HEADER = PatternFill(start_color=COLOR_PRIMARY, end_color=COLOR_PRIMARY, fill_type="solid")
FILL_ZEBRA = PatternFill(start_color=COLOR_LIGHT_GRAY, end_color=COLOR_LIGHT_GRAY, fill_type="solid")
ALIGN_CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
ALIGN_LEFT = Alignment(horizontal="left", vertical="center", wrap_text=True)
ALIGN_RIGHT = Alignment(horizontal="right", vertical="center", wrap_text=True)

# Reglas explícitas y umbrales para hallazgos automatizados
FINDING_RULES = [
    {
        "id": "BLAND_ALTMAN_BIAS",
        "threshold": 0.05,
        "description": "Sesgo de media entre rúbrica automática y rúbrica humana (|diff| > 0.05)",
    },
    {
        "id": "CONVERGENT_SPEARMAN",
        "threshold": 0.0,
        "description": "Correlación de Spearman entre rúbrica automática y rúbrica humana",
    },
    {
        "id": "DIAGNOSTIC_KAPPA",
        "threshold": 0.40,
        "description": "Concordancia en exactitud diagnóstica binaria (Kappa de Cohen)",
    },
    {
        "id": "OPERATIONAL_UTILITY_MAX",
        "threshold": 0.0,
        "description": "Criterio con mayor correlación con la utilidad operativa (U)",
    },
    {
        "id": "EVIDENCE_BACKED_KAPPA",
        "threshold": 0.40,
        "description": "Concordancia en respaldo de evidencia empírica S vs evidence_backed",
    },
    {
        "id": "LATENCY_QUALITY",
        "threshold": 0.0,
        "description": "Correlación entre latencia de inferencia y rúbrica humana (clave abierta)",
    },
    {
        "id": "MODEL_SIZE_KRUSKAL",
        "threshold": 0.05,
        "description": "Diferencias de rúbrica humana entre modelos evaluadas por Kruskal-Wallis (clave abierta)",
    },
]


# ── Funciones Estadísticas de Correlación e Inferencia ──────────────────────

def classify_correlation_strength(abs_rho: float) -> str:
    """Clasifica la fuerza del coeficiente de correlación según umbrales formales."""
    if abs_rho < 0.1:
        return "nula"
    elif abs_rho < 0.3:
        return "débil"
    elif abs_rho < 0.5:
        return "moderada"
    elif abs_rho < 0.7:
        return "considerable"
    return "fuerte"


def format_p_value(p: Optional[float]) -> str:
    """Formatea valor p: escribe el valor real si p >= 0.001, sin forzar 'p < 0.001' erróneamente."""
    if p is None:
        return "N/A"
    try:
        if math.isnan(p):
            return "N/A"
    except (TypeError, ValueError):
        pass
    if p < 0.001:
        return f"{p:.4e}" if p < 1e-4 else f"{p:.4f}"
    return f"{p:.4f}"


def compute_spearman_with_ci(
    x: list[float],
    y: list[float],
    n_boot: int = 1000,
    seed: int = 2026
) -> dict[str, Any]:
    """
    Calcula correlación de Spearman con IC 95% bootstrap.
    Si una variable no tiene varianza, reporta 'sin variación'.
    Si x == y, retorna rho=1.0 e IC=[1.0, 1.0].
    """
    if len(x) != len(y) or len(x) == 0:
        return {"rho": 0.0, "p_value": 1.0, "ci_95": (0.0, 0.0), "fuerza": "nula", "n": len(x)}

    arr_x = np.array(x, dtype=float)
    arr_y = np.array(y, dtype=float)

    # Comprobar varianza
    std_x = float(np.std(arr_x))
    std_y = float(np.std(arr_y))
    if std_x == 0.0 or std_y == 0.0:
        return {
            "rho": None,
            "p_value": None,
            "ci_95": None,
            "fuerza": "sin variación",
            "n": len(x),
            "nota": "sin variación en una o ambas variables",
        }

    # Si correlación idéntica
    if np.array_equal(arr_x, arr_y):
        return {
            "rho": 1.0,
            "p_value": 0.0,
            "ci_95": (1.0, 1.0),
            "fuerza": "fuerte",
            "n": len(x),
        }

    try:
        from scipy import stats
        res = stats.spearmanr(arr_x, arr_y)
        rho_val = round(float(res.statistic), 4)
        p_val = round(float(res.pvalue), 6)
    except Exception:
        rho_val = 0.0
        p_val = 1.0

    # Vectorized bootstrap para IC 95%
    if n_boot <= 0:
        ci = (rho_val, rho_val)
    else:
        rng = np.random.default_rng(seed)
        n = len(arr_x)
        idxs = rng.choice(n, size=(n_boot, n), replace=True)
        sx = arr_x[idxs]
        sy = arr_y[idxs]
        from scipy import stats
        rx = stats.rankdata(sx, axis=1)
        ry = stats.rankdata(sy, axis=1)
        rx_c = rx - np.mean(rx, axis=1, keepdims=True)
        ry_c = ry - np.mean(ry, axis=1, keepdims=True)
        cov = np.sum(rx_c * ry_c, axis=1)
        denom = np.sqrt(np.sum(rx_c**2, axis=1) * np.sum(ry_c**2, axis=1))
        with np.errstate(divide='ignore', invalid='ignore'):
            rhos = np.where(denom > 0, cov / denom, 0.0)
        ci_low = round(float(np.percentile(rhos, 2.5)), 4)
        ci_high = round(float(np.percentile(rhos, 97.5)), 4)
        ci = (ci_low, ci_high)

    return {
        "rho": rho_val,
        "p_value": p_val,
        "ci_95": ci,
        "fuerza": classify_correlation_strength(abs(rho_val)),
        "n": len(x),
    }


def compute_pearson_with_ci(x: list[float], y: list[float]) -> dict[str, Any]:
    """Calcula correlación de Pearson y valor p."""
    if len(x) != len(y) or len(x) < 2:
        return {"r": 0.0, "p_value": 1.0}
    try:
        from scipy import stats
        res = stats.pearsonr(x, y)
        return {"r": round(float(res.statistic), 4), "p_value": round(float(res.pvalue), 6)}
    except Exception:
        return {"r": 0.0, "p_value": 1.0}


def compute_phi_coefficient(b1: list[int], b2: list[int]) -> float:
    """Calcula el coeficiente de correlación de Phi para dos variables binarias."""
    n = len(b1)
    if n == 0 or len(b2) != n:
        return 0.0
    arr1 = np.array(b1, dtype=int)
    arr2 = np.array(b2, dtype=int)
    n11 = int(np.sum((arr1 == 1) & (arr2 == 1)))
    n10 = int(np.sum((arr1 == 1) & (arr2 == 0)))
    n01 = int(np.sum((arr1 == 0) & (arr2 == 1)))
    n00 = int(np.sum((arr1 == 0) & (arr2 == 0)))

    denom = math.sqrt((n11 + n10) * (n01 + n00) * (n11 + n01) * (n10 + n00))
    if denom == 0.0:
        return 0.0
    phi = (n11 * n00 - n10 * n01) / denom
    return round(float(phi), 4)


def compute_cohen_d(group1: list[float], group2: list[float]) -> float:
    """Calcula el tamaño del efecto d de Cohen entre dos grupos independientes."""
    n1, n2 = len(group1), len(group2)
    if n1 < 2 or n2 < 2:
        return 0.0
    m1, m2 = float(np.mean(group1)), float(np.mean(group2))
    s1 = float(np.std(group1, ddof=1))
    s2 = float(np.std(group2, ddof=1))
    sp = math.sqrt(((n1 - 1) * (s1 ** 2) + (n2 - 1) * (s2 ** 2)) / (n1 + n2 - 2))
    if sp == 0.0:
        return 0.0
    return round((m1 - m2) / sp, 3)


def compute_kruskal_wallis(*groups: list[float]) -> tuple[float, float]:
    """Calcula prueba de Kruskal-Wallis (H, p) para k grupos independientes."""
    valid_groups = [g for g in groups if len(g) > 0]
    if len(valid_groups) < 2:
        return 0.0, 1.0
    try:
        from scipy import stats
        res = stats.kruskal(*valid_groups)
        return round(float(res.statistic), 3), round(float(res.pvalue), 6)
    except Exception:
        return 0.0, 1.0


# ── Construcción del Conjunto de Datos Unificado ────────────────────────────

def build_correlation_dataset(
    consensus_list: list[dict[str, Any]],
    key_by_code: dict[str, dict[str, Any]],
    results_csv_rows: list[dict[str, Any]],
    auto_dict: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """
    Une por código ciego:
    1. Consenso humano (C1-C6, rúbrica, S, U, correcto_humano) y medias A-B por ítem.
    2. Metadatos de la clave (modelo real, escenario, semilla).
    3. Resultados del benchmark (métricas automáticas y telemetría de costo).

    Lanza ValueError si falta is_correct o rubric_score para cualquier código.
    Prohibidos los valores por defecto False o 0.0.
    """
    # Mapear resultados.csv por (scenario_id, model_id, seed)
    results_map: dict[tuple[str, str, int], dict[str, Any]] = {}
    for row in results_csv_rows:
        sc = str(row.get("scenario_id", "")).strip()
        m = str(row.get("model_id", "")).strip()
        try:
            s = int(row.get("seed", row.get("semilla", 42)))
        except ValueError:
            s = 42
        results_map[(sc, m, s)] = row

    # Verificación de completitud métrica automática
    missing_codes = []
    for item in consensus_list:
        code = item["codigo"]
        key_info = key_by_code.get(code, {})
        sc_id = key_info.get("scenario_id", "")
        model_id = key_info.get("model_id", key_info.get("modelo", ""))
        try:
            seed = int(key_info.get("seed", key_info.get("semilla", 42)))
        except ValueError:
            seed = 42

        res_row = results_map.get((sc_id, model_id, seed), {})
        auto_item = auto_dict.get(code) if auto_dict else None

        has_corr = False
        has_rub = False

        if auto_item:
            if ("is_correct" in auto_item and auto_item["is_correct"] is not None) or (
                "is_root_cause_correct" in auto_item and auto_item["is_root_cause_correct"] is not None
            ):
                has_corr = True
            if "rubric_score" in auto_item and auto_item["rubric_score"] is not None:
                has_rub = True

        if not has_corr:
            if ("is_correct" in res_row and res_row["is_correct"] is not None) or (
                "is_root_cause_correct" in res_row and res_row["is_root_cause_correct"] is not None
            ):
                has_corr = True

        if not has_rub:
            if "rubric_score" in res_row and res_row["rubric_score"] is not None:
                has_rub = True

        if not (has_corr and has_rub):
            missing_codes.append(code)

    if missing_codes:
        raise ValueError(
            f"Faltan métricas automáticas ('is_correct' o 'rubric_score') para los siguientes códigos: {sorted(missing_codes)}"
        )

    unified_rows: list[dict[str, Any]] = []

    for item in consensus_list:
        code = item["codigo"]
        key_info = key_by_code.get(code, {})
        sc_id = key_info.get("scenario_id", "")
        model_id = key_info.get("model_id", key_info.get("modelo", ""))
        try:
            seed = int(key_info.get("seed", key_info.get("semilla", 42)))
        except ValueError:
            seed = 42

        res_row = results_map.get((sc_id, model_id, seed), {})
        auto_item = auto_dict.get(code) if auto_dict else None

        # Variables humanas
        a_data = item.get("a", {})
        b_data = item.get("b", {})
        c1_cons = item.get("c1_consenso")
        s_cons = item.get("s_consenso")

        # Medias directas entre A y B para evitar huecos en la matriz interítem (n=54)
        c1_mean = round((a_data.get("c1", 0) + b_data.get("c1", 0)) / 2.0, 2)
        c2_mean = round((a_data.get("c2", 0) + b_data.get("c2", 0)) / 2.0, 2)
        c3_mean = round((a_data.get("c3", 0) + b_data.get("c3", 0)) / 2.0, 2)
        c4_mean = round((a_data.get("c4", 0) + b_data.get("c4", 0)) / 2.0, 2)
        c5_mean = round((a_data.get("c5", 0) + b_data.get("c5", 0)) / 2.0, 2)
        c6_mean = round((a_data.get("c6", 0) + b_data.get("c6", 0)) / 2.0, 2)

        s_a_num = 1.0 if str(a_data.get("s", "")).strip().lower() in ("sí", "si", "1", "true") else 0.0
        s_b_num = 1.0 if str(b_data.get("s", "")).strip().lower() in ("sí", "si", "1", "true") else 0.0
        s_mean = round((s_a_num + s_b_num) / 2.0, 2)

        u_mean = round((a_data.get("u", 1) + b_data.get("u", 1)) / 2.0, 2)

        # Variables automáticas
        if auto_item:
            corr_val = auto_item.get("is_correct") if auto_item.get("is_correct") is not None else auto_item.get("is_root_cause_correct")
            rubric_auto = float(auto_item["rubric_score"])
            ev_backed_val = auto_item.get("evidence_backed", False)
            partial_match = float(auto_item.get("partial_match_score", res_row.get("partial_match_score", 0.0)) or 0.0)
        else:
            corr_val = res_row.get("is_correct") if res_row.get("is_correct") is not None else res_row.get("is_root_cause_correct")
            rubric_auto = float(res_row["rubric_score"])
            ev_backed_val = res_row.get("evidence_backed", False)
            partial_match = float(res_row.get("partial_match_score", 0.0) or 0.0)

        if isinstance(corr_val, str):
            is_correct = corr_val.strip().lower() in ("true", "1", "t", "si", "sí")
        elif isinstance(corr_val, (int, float)):
            is_correct = bool(corr_val == 1)
        else:
            is_correct = bool(corr_val)

        if isinstance(ev_backed_val, str):
            ev_backed = ev_backed_val.strip().lower() in ("true", "1", "t", "si", "sí")
        elif isinstance(ev_backed_val, (int, float)):
            ev_backed = bool(ev_backed_val == 1)
        else:
            ev_backed = bool(ev_backed_val)

        # Variables de costo
        ttft_ms = float(res_row.get("ttft_ms", res_row.get("ttft_final_ms", 0.0)) or 0.0)
        ttft_s = round(ttft_ms / 1000.0, 3)
        tok_s = float(res_row.get("tokens_per_sec", 0.0) or 0.0)
        total_time_ms = float(res_row.get("total_time_ms", 0.0) or 0.0)
        latency_s = round(total_time_ms / 1000.0, 3)
        energy_kwh = float(res_row.get("energy_kwh", 0.0) or 0.0)

        # Categoría y parámetros
        category = res_row.get("category", "")
        if not category:
            if sc_id.startswith("DNS"): category = "DNS"
            elif sc_id.startswith("HTTP"): category = "HTTP_WEB"
            elif sc_id.startswith("TLS"): category = "TLS"
            elif sc_id.startswith("NET"): category = "API_GATEWAY"
            else: category = "DNS"

        if "phi" in model_id.lower():
            params_b = 3.8
        elif "qwen" in model_id.lower():
            params_b = 8.2
        elif "glm" in model_id.lower():
            params_b = 9.0
        else:
            params_b = 8.0

        unified_rows.append({
            "codigo": code,
            "scenario_id": sc_id,
            "model_id": model_id,
            "seed": seed,
            "category": category,
            "params_b": params_b,
            # Humanas
            "c1": c1_cons if c1_cons is not None else c1_mean,
            "c1_mean": c1_mean,
            "c2_mean": c2_mean,
            "c3_mean": c3_mean,
            "c4_mean": c4_mean,
            "c5_mean": c5_mean,
            "c6_mean": c6_mean,
            "s_mean": s_mean,
            "u_mean": u_mean,
            "c2": c2_mean,
            "c3": c3_mean,
            "c4": c4_mean,
            "c5": c5_mean,
            "c6": c6_mean,
            "s_str": s_cons if s_cons is not None else ("Sí" if s_mean >= 0.5 else "No"),
            "s": 1 if (s_cons == "Sí" or (s_cons is None and s_mean >= 0.5)) else 0,
            "u": u_mean,
            "rubrica_humana": item.get("rubrica_humana", 0.0),
            "humano_correcto": 1 if c1_cons == 2 else 0,
            # Automáticas
            "is_correct": 1 if is_correct else 0,
            "is_correct_bool": is_correct,
            "rubric_auto": rubric_auto,
            "partial_match_score": partial_match,
            "evidence_backed": 1 if ev_backed else 0,
            # Costo
            "ttft_s": ttft_s,
            "tok_s": tok_s,
            "latency_s": latency_s,
            "energy_kwh": energy_kwh,
        })

    return unified_rows


# ── Ejecución de los 6 Análisis del Informe ─────────────────────────────────

def run_correlation_report(
    unified_rows: list[dict[str, Any]],
    agreement_summary: dict[str, Any],
    is_blind: bool = True,
    seed: int = 2026,
) -> dict[str, Any]:
    """
    Ejecuta el protocolo completo de los 6 análisis.
    Si is_blind=True, los análisis 3, 4 y 5 se bloquean y se reemplazan por aviso reglamentario.
    """
    n = len(unified_rows)

    # 1. Matriz Interítem (C1..C6, S, U) basada en medias A-B completas (n=54)
    items_keys = ["c1", "c2", "c3", "c4", "c5", "c6", "s", "u"]
    item_vectors = {
        "c1": [float(r.get("c1_mean", r.get("c1", 0))) for r in unified_rows],
        "c2": [float(r.get("c2_mean", r.get("c2", 0))) for r in unified_rows],
        "c3": [float(r.get("c3_mean", r.get("c3", 0))) for r in unified_rows],
        "c4": [float(r.get("c4_mean", r.get("c4", 0))) for r in unified_rows],
        "c5": [float(r.get("c5_mean", r.get("c5", 0))) for r in unified_rows],
        "c6": [float(r.get("c6_mean", r.get("c6", 0))) for r in unified_rows],
        "s": [float(r.get("s_mean", r.get("s", 0))) for r in unified_rows],
        "u": [float(r.get("u_mean", r.get("u", 1))) for r in unified_rows],
    }
    interitem_matrix: dict[str, dict[str, Any]] = {}

    for i, k1 in enumerate(items_keys):
        if k1 not in interitem_matrix:
            interitem_matrix[k1] = {}
        for j, k2 in enumerate(items_keys):
            if k1 == k2:
                interitem_matrix[k1][k2] = {
                    "rho": 1.0,
                    "p_value": 0.0,
                    "ci_95": (1.0, 1.0),
                    "fuerza": "fuerte",
                }
            elif j > i:
                vals1 = item_vectors[k1]
                vals2 = item_vectors[k2]
                res = compute_spearman_with_ci(vals1, vals2, n_boot=1000, seed=seed)
                interitem_matrix[k1][k2] = res
                if k2 not in interitem_matrix:
                    interitem_matrix[k2] = {}
                interitem_matrix[k2][k1] = res

    # 2. Validez Convergente: Humano vs Automático
    rub_hum = [r["rubrica_humana"] for r in unified_rows]
    rub_aut = [r["rubric_auto"] for r in unified_rows]
    val_rub_sp = compute_spearman_with_ci(rub_aut, rub_hum, n_boot=1000, seed=seed)
    val_rub_pr = compute_pearson_with_ci(rub_aut, rub_hum)
    ba_res = compute_bland_altman(rub_aut, rub_hum)

    c1_vals = [float(r["c1"] or 0) for r in unified_rows]
    pm_vals = [r["partial_match_score"] for r in unified_rows]
    val_c1_sp = compute_spearman_with_ci(pm_vals, c1_vals, n_boot=1000, seed=seed)

    hum_corr = [r["humano_correcto"] for r in unified_rows]
    aut_corr = [r["is_correct"] for r in unified_rows]
    phi_corr = compute_phi_coefficient(aut_corr, hum_corr)
    k_corr = compute_cohen_kappa(aut_corr, hum_corr)

    s_hum = [r["s"] for r in unified_rows]
    s_aut = [r["evidence_backed"] for r in unified_rows]
    k_s_val = compute_cohen_kappa(s_aut, s_hum)
    t2x2_s = {
        "TP": sum(1 for a, h in zip(s_aut, s_hum) if a == 1 and h == 1),
        "FP": sum(1 for a, h in zip(s_aut, s_hum) if a == 1 and h == 0),
        "FN": sum(1 for a, h in zip(s_aut, s_hum) if a == 0 and h == 1),
        "TN": sum(1 for a, h in zip(s_aut, s_hum) if a == 0 and h == 0),
    }

    analisis_2 = {
        "rubrica_spearman": val_rub_sp,
        "rubrica_pearson": val_rub_pr,
        "bland_altman": ba_res,
        "c1_vs_partial_match": val_c1_sp,
        "exactitud_phi": phi_corr,
        "exactitud_kappa": k_corr,
        "sustentado_kappa": k_s_val,
        "sustentado_tabla_2x2": t2x2_s,
    }

    # 6. Concordancia por ítem entre expertos (Spearman A vs B + Alfa ordinal)
    analisis_6: dict[str, Any] = {}
    for item_key in ["c1", "c2", "c3", "c4", "c5", "c6"]:
        # Se toma directamente de agreement_summary si disponible
        alpha_info = agreement_summary.get("alfas_ordinales", {}).get(item_key.upper(), {})
        analisis_6[item_key.upper()] = {
            "alfa_ordinal": alpha_info.get("alfa", 0.0),
            "ci_95": alpha_info.get("ci_95", (0.0, 0.0)),
        }

    # Análisis 3, 4 y 5: Condicionados por la regla de cegamiento
    if is_blind:
        analisis_3 = {"estado": "bloqueado", "aviso": "Disponible tras cerrar la evaluación ciega (Abrir clave)."}
        analisis_4 = {"estado": "bloqueado", "aviso": "Disponible tras cerrar la evaluación ciega (Abrir clave)."}
        analisis_5 = {"estado": "bloqueado", "aviso": "Disponible tras cerrar la evaluación ciega (Abrir clave)."}
    else:
        # 3. Calidad frente a Costo
        cost_vars = ["ttft_s", "tok_s", "latency_s", "energy_kwh"]
        analisis_3 = {"variables": {}}
        for cv in cost_vars:
            c_vals = [r[cv] for r in unified_rows]
            analisis_3["variables"][cv] = {
                "vs_rubrica_humana": compute_spearman_with_ci(c_vals, rub_hum, seed=seed),
                "vs_c1": compute_spearman_with_ci(c_vals, c1_vals, seed=seed),
                "vs_u": compute_spearman_with_ci(c_vals, [float(r["u"]) for r in unified_rows], seed=seed),
            }

        # 4. Calidad frente a Tamaño de Modelo
        models_unique = sorted(list(set(r["model_id"] for r in unified_rows)))
        groups_rub = {m: [r["rubrica_humana"] for r in unified_rows if r["model_id"] == m] for m in models_unique}
        groups_c1 = {m: [float(r["c1"] or 0) for r in unified_rows if r["model_id"] == m] for m in models_unique}
        groups_c6 = {m: [float(r["c6"] or 0) for r in unified_rows if r["model_id"] == m] for m in models_unique}

        h_rub, p_rub = compute_kruskal_wallis(*groups_rub.values())
        h_c1, p_c1 = compute_kruskal_wallis(*groups_c1.values())
        h_c6, p_c6 = compute_kruskal_wallis(*groups_c6.values())

        # d de Cohen por pares para rúbrica
        cohen_pairs = {}
        for i in range(len(models_unique)):
            for j in range(i + 1, len(models_unique)):
                m1, m2 = models_unique[i], models_unique[j]
                d_val = compute_cohen_d(groups_rub[m1], groups_rub[m2])
                cohen_pairs[f"{m1} vs {m2}"] = d_val

        analisis_4 = {
            "advertencia_obligatoria": (
                "ADVERTENCIA METODOLÓGICA: El eje de parámetros cuenta con solo 3 niveles discretos. "
                "La lectura representa una tendencia empírica descriptiva, no inferencial, encontrándose "
                "el tamaño confundido con la arquitectura de cada modelo evaluado."
            ),
            "kruskal_wallis": {
                "rubrica_humana": {"H": h_rub, "p_value": p_rub},
                "c1": {"H": h_c1, "p_value": p_c1},
                "c6": {"H": h_c6, "p_value": p_c6},
            },
            "cohen_d_rubrica": cohen_pairs,
        }

        # 5. Por Categoría de Escenario
        cats_unique = sorted(list(set(r["category"] for r in unified_rows)))
        cats_rub = {cat: [r["rubrica_humana"] for r in unified_rows if r["category"] == cat] for cat in cats_unique}
        h_cat, p_cat = compute_kruskal_wallis(*cats_rub.values())

        cats_summary = {}
        for cat in cats_unique:
            cat_rows = [r for r in unified_rows if r["category"] == cat]
            cats_summary[cat] = {
                "n": len(cat_rows),
                "rubrica_humana_media": round(float(np.mean([r["rubrica_humana"] for r in cat_rows])), 3),
                "c1_medio": round(float(np.mean([r["c1"] for r in cat_rows])), 3),
            }

        analisis_5 = {
            "kruskal_wallis": {"H": h_cat, "p_value": p_cat},
            "por_categoria": cats_summary,
        }

    # Generación de Hallazgos Automáticos conforme a FINDING_RULES (citas exactas, sin causalidad)
    hallazgos = []

    # 1. Sesgo Bland-Altman
    mean_diff = ba_res["mean_diff"]
    ci_ba_low = ba_res["lower_limit"]
    ci_ba_high = ba_res["upper_limit"]
    if mean_diff is not None and abs(mean_diff) > 0.05:
        ci_str = f"[{ci_ba_low:.3f}, {ci_ba_high:.3f}]" if (ci_ba_low is not None and ci_ba_high is not None) else "[N/A, N/A]"
        hallazgos.append(
            f"Sesgo medio Bland-Altman de la rúbrica automática frente a la humana: {mean_diff:+.3f} puntos "
            f"(límites de acuerdo al 95%: {ci_str}, n = {n})."
        )

    # 2. Correlación rúbrica auto vs humano
    rho_val = val_rub_sp.get("rho")
    if rho_val is not None:
        hallazgos.append(
            f"Validez convergente de rúbrica: correlación de Spearman ρ = {rho_val:.3f} "
            f"(p = {format_p_value(val_rub_sp.get('p_value'))}, n = {n})."
        )

    # 3. Kappa exactitud diagnóstica
    k_corr_str = f"{k_corr:.3f}" if k_corr is not None else "N/A"
    hallazgos.append(
        f"Exactitud diagnóstica binaria (is_correct vs C1=2): Kappa de Cohen κ = {k_corr_str} (n = {n})."
    )

    # 4. Criterio más asociado a la utilidad operativa (U)
    u_corrs = [
        (k, interitem_matrix["u"][k]["rho"])
        for k in ["c1", "c2", "c3", "c4", "c5", "c6"]
        if interitem_matrix["u"][k]["rho"] is not None
    ]
    if u_corrs:
        max_u_item, max_u_rho = max(u_corrs, key=lambda x: abs(x[1]))
        hallazgos.append(
            f"Mayor asociación observada con la utilidad operativa (U): criterio {max_u_item.upper()} "
            f"con correlación de Spearman ρ = {max_u_rho:.3f} (p = {format_p_value(interitem_matrix['u'][max_u_item]['p_value'])})."
        )

    # 5. Respaldo de evidencia empírica
    k_s_str = f"{k_s_val:.3f}" if k_s_val is not None else "N/A"
    hallazgos.append(
        f"Respaldo de evidencia empírica (evidence_backed vs S): Kappa de Cohen κ = {k_s_str} "
        f"(TP = {t2x2_s['TP']}, FP = {t2x2_s['FP']}, FN = {t2x2_s['FN']}, TN = {t2x2_s['TN']})."
    )

    if not is_blind:
        # Hallazgo costo
        rho_lat = analisis_3["variables"]["latency_s"]["vs_rubrica_humana"]["rho"]
        if rho_lat is not None:
            p_lat = analisis_3["variables"]["latency_s"]["vs_rubrica_humana"]["p_value"]
            hallazgos.append(
                f"Correlación entre latencia de inferencia y rúbrica humana: Spearman ρ = {rho_lat:.3f} "
                f"(p = {format_p_value(p_lat)})."
            )

        # Hallazgo tamaño
        h_val = analisis_4["kruskal_wallis"]["rubrica_humana"]["H"]
        p_val_size = analisis_4["kruskal_wallis"]["rubrica_humana"]["p_value"]
        hallazgos.append(
            f"Comparación de rúbrica humana entre modelos: Kruskal-Wallis H = {h_val:.3f}, "
            f"p = {format_p_value(p_val_size)}."
        )



    return {
        "n": n,
        "es_ciego": is_blind,
        "analisis_1_interitem": interitem_matrix,
        "analisis_2_validez_convergente": analisis_2,
        "analisis_3_calidad_vs_costo": analisis_3,
        "analisis_4_calidad_vs_tamano": analisis_4,
        "analisis_5_por_categoria": analisis_5,
        "analisis_6_concordancia_items": analisis_6,
        "hallazgos_principales": hallazgos[:8],
    }


# ── Exportador a Excel (Hoja Correlación y Datos_correlación) ───────────────

def append_correlation_sheets(
    wb: openpyxl.Workbook,
    report_data: dict[str, Any],
    unified_rows: list[dict[str, Any]],
) -> None:
    """Añade las hojas 'Correlación' y 'Datos_correlación' al libro de concordancia."""
    # 1. Hoja Correlación
    ws_corr = wb.create_sheet(title="Correlación")
    ws_corr.views.sheetView[0].showGridLines = True
    ws_corr["A1"] = "Informe de Análisis Correlacional (Validación Humana vs Benchmark)"
    ws_corr["A1"].font = FONT_TITLE

    # Matriz interítem
    ws_corr["A3"] = "1. Matriz de Correlación Interítem de Spearman (C1-C6, S, U)"
    ws_corr["A3"].font = FONT_BOLD

    matrix = report_data["analisis_1_interitem"]
    headers_m = ["Ítem"] + [k.upper() for k in matrix.keys()]
    for c_idx, h in enumerate(headers_m, start=1):
        cell = ws_corr.cell(row=4, column=c_idx, value=h)
        cell.font = FONT_HEADER
        cell.fill = FILL_NAVY
        cell.alignment = ALIGN_CENTER
        cell.border = BORDER_THIN

    fill_red = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")
    fill_blue = PatternFill(start_color="E0F2FE", end_color="E0F2FE", fill_type="solid")

    for r_idx, (k1, row_dict) in enumerate(matrix.items(), start=5):
        ws_corr.cell(row=r_idx, column=1, value=k1.upper()).font = FONT_BOLD
        ws_corr.cell(row=r_idx, column=1).border = BORDER_THIN
        ws_corr.cell(row=r_idx, column=1).alignment = ALIGN_CENTER

        for c_idx, (k2, cell_data) in enumerate(row_dict.items(), start=2):
            cell = ws_corr.cell(row=r_idx, column=c_idx)
            rho = cell_data.get("rho")
            if rho is None:
                cell.value = "s/var"
            else:
                cell.value = round(rho, 3)
                if rho > 0.3:
                    cell.fill = fill_blue
                elif rho < -0.1:
                    cell.fill = fill_red
            cell.font = FONT_REGULAR
            cell.border = BORDER_THIN
            cell.alignment = ALIGN_CENTER

    # Tablas de análisis 2 a 6
    start_a2 = len(matrix) + 7
    ws_corr[f"A{start_a2}"] = "2. Validez Convergente: Humano frente a Evaluador Automático"
    ws_corr[f"A{start_a2}"].font = FONT_BOLD

    a2 = report_data["analisis_2_validez_convergente"]
    rows_a2 = [
        ("Rúbrica Humana vs Rúbrica Automática (Spearman ρ)", a2["rubrica_spearman"]["rho"], format_p_value(a2["rubrica_spearman"]["p_value"])),
        ("Rúbrica Humana vs Rúbrica Automática (Pearson r)", a2["rubrica_pearson"]["r"], format_p_value(a2["rubrica_pearson"]["p_value"])),
        ("Bland-Altman Diferencia Media", a2["bland_altman"]["mean_diff"], f"Límites: [{a2['bland_altman']['lower_limit']}, {a2['bland_altman']['upper_limit']}]"),
        ("C1 Humano vs partial_match_score (Spearman ρ)", a2["c1_vs_partial_match"]["rho"], format_p_value(a2["c1_vs_partial_match"]["p_value"])),
        ("Correcto Humano vs is_correct (Coeficiente Phi)", a2["exactitud_phi"], f"Kappa: {a2['exactitud_kappa']}"),
        ("Sustentado Humano vs evidence_backed (Kappa)", a2["sustentado_kappa"], f"TP={a2['sustentado_tabla_2x2']['TP']}, FN={a2['sustentado_tabla_2x2']['FN']}"),
    ]

    for r_offset, (lbl, val, info) in enumerate(rows_a2, start=start_a2 + 1):
        ws_corr.cell(row=r_offset, column=1, value=lbl).font = FONT_BOLD
        ws_corr.cell(row=r_offset, column=2, value=val).alignment = ALIGN_CENTER
        ws_corr.cell(row=r_offset, column=3, value=info).alignment = ALIGN_LEFT
        for c in (1, 2, 3):
            ws_corr.cell(row=r_offset, column=c).border = BORDER_THIN

    # Hallazgos
    start_h = start_a2 + len(rows_a2) + 2
    ws_corr[f"A{start_h}"] = "Hallazgos Principales (Generación Automatizada)"
    ws_corr[f"A{start_h}"].font = FONT_BOLD

    for idx, hallazgo in enumerate(report_data.get("hallazgos_principales", []), start=1):
        ws_corr.cell(row=start_h + idx, column=1, value=f"{idx}. {hallazgo}").font = FONT_REGULAR

    # 2. Hoja Datos_correlación (Dataset completo de 54 filas auditables)
    ws_data = wb.create_sheet(title="Datos_correlación")
    ws_data.views.sheetView[0].showGridLines = True
    ws_data["A1"] = "Dataset Consolidado de Correlación (54 Filas Granulares)"
    ws_data["A1"].font = FONT_TITLE

    data_headers = [
        "Código", "Escenario", "Modelo", "Semilla", "Categoría", "Parámetros (B)",
        "C1", "C2", "C3", "C4", "C5", "C6", "S", "U", "Rúbrica Humana", "Correcto Humano",
        "is_correct", "Rúbrica Auto", "partial_match", "evidence_backed",
        "TTFT (s)", "tok/s", "Latencia (s)", "Energía (kWh)"
    ]
    for c_idx, h in enumerate(data_headers, start=1):
        cell = ws_data.cell(row=3, column=c_idx, value=h)
        cell.font = FONT_HEADER
        cell.fill = FILL_HEADER
        cell.alignment = ALIGN_CENTER
        cell.border = BORDER_THIN

    for r_idx, r in enumerate(unified_rows, start=4):
        # Si es ciego, ocultar modelo y parámetros
        m_val = "[MODELO]" if report_data.get("es_ciego", True) else r["model_id"]
        p_val = "-" if report_data.get("es_ciego", True) else r["params_b"]

        row_vals = [
            r["codigo"], r["scenario_id"], m_val, r["seed"], r["category"], p_val,
            r["c1"], r["c2"], r["c3"], r["c4"], r["c5"], r["c6"], r["s"], r["u"], r["rubrica_humana"], r["humano_correcto"],
            r["is_correct"], r["rubric_auto"], r["partial_match_score"], r["evidence_backed"],
            r["ttft_s"], r["tok_s"], r["latency_s"], r["energy_kwh"]
        ]
        for c_idx, val in enumerate(row_vals, start=1):
            cell = ws_data.cell(row=r_idx, column=c_idx, value=val)
            cell.font = FONT_REGULAR
            cell.border = BORDER_THIN
            cell.alignment = ALIGN_CENTER if c_idx not in (2, 3) else ALIGN_LEFT

    # Ajuste de columnas
    for sheet in [ws_corr, ws_data]:
        for col in sheet.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            col_letter = get_column_letter(col[0].column)
            sheet.column_dimensions[col_letter].width = max(max_len + 3, 11)


# ── Exportador HTML/PDF del Informe de Correlación ──────────────────────────

def export_correlation_report_html(
    report_data: dict[str, Any],
    unified_rows: list[dict[str, Any]],
    output_path: Path,
) -> Path:
    """
    Genera el informe técnico institucional Informe_Correlacion_<sesion>.html.
    Si es_ciego=True, se garantiza que no contenga nombres de modelos ni análisis 3-5.
    """
    is_blind = report_data.get("es_ciego", True)

    # Hallazgos formateados
    hallazgos_html = "".join(f"<li>{h}</li>" for h in report_data.get("hallazgos_principales", []))

    # Matriz interítem en HTML
    matrix = report_data["analisis_1_interitem"]
    m_headers = "".join(f"<th style='text-align:center;'>{k.upper()}</th>" for k in matrix.keys())
    m_rows = ""
    for k1, row_dict in matrix.items():
        row_tds = f"<td style='font-weight:bold; background:#F8FAFC;'>{k1.upper()}</td>"
        for k2, d in row_dict.items():
            rho = d.get("rho")
            if rho is None:
                bg = "#FFFFFF"
                txt = "s/v"
            else:
                txt = f"{rho:.2f}"
                bg = "#E0F2FE" if rho > 0.3 else ("#FEE2E2" if rho < -0.1 else "#FFFFFF")
            row_tds += f"<td style='background:{bg}; text-align:center;'>{txt}</td>"
        m_rows += f"<tr>{row_tds}</tr>"

    # Sección de Calidad vs Costo y Tamaño (o aviso si ciego)
    if is_blind:
        bloque_3_4_5 = """
        <div style="background: #FFFBEB; border: 1px solid #FCD34D; border-radius: 6px; padding: 20px; margin: 24px 0;">
          <h3 style="color: #92400E; margin-bottom: 6px;">Evaluación Ciega en Curso</h3>
          <p style="color: #78350F; font-size: 13px;">
            Los análisis de Calidad frente a Costo (TTFT, tok/s, energía), Calidad frente a Tamaño de Modelo
            y Desglose por Categoría de Escenario se encuentran restringidos conforme al protocolo de evaluación ciega.
            <strong>Disponible tras cerrar la evaluación ciega (comando: Abrir clave).</strong>
          </p>
        </div>
        """
    else:
        bloque_3_4_5 = """
        <div style="background: #F8FAFC; border: 1px solid #CBD5E1; border-radius: 6px; padding: 20px; margin: 24px 0;">
          <h3 style="color: #0F172A; margin-bottom: 6px;">Análisis de Calidad frente a Costo y Tamaño</h3>
          <p style="color: #475569; font-size: 13px;">Consulte el informe consolidado completo y gráficos anexos.</p>
        </div>
        """

    html_template = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <title>Informe de Correlación y Validación Diagnóstica - NetDiagBench-L7</title>
  <style>
    body {{ font-family: Arial, sans-serif; background: #F8FAFC; color: #0F172A; margin: 0; padding: 28px; line-height: 1.5; }}
    .container {{ max-width: 960px; margin: 0 auto; background: #FFFFFF; padding: 36px; border-radius: 8px; border: 1px solid #E2E8F0; }}
    .header {{ border-bottom: 3px solid #B03535; padding-bottom: 16px; margin-bottom: 24px; }}
    h1 {{ color: #B03535; font-size: 24px; margin-bottom: 4px; }}
    .subtitle {{ color: #475569; font-size: 13px; }}
    h2 {{ color: #1E293B; font-size: 16px; border-bottom: 1px solid #E2E8F0; padding-bottom: 6px; margin: 28px 0 14px 0; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 12px; margin-bottom: 20px; }}
    th, td {{ border: 1px solid #CBD5E1; padding: 8px 10px; }}
    th {{ background: #1E293B; color: #FFFFFF; font-weight: bold; }}
    .box-hallazgos {{ background: #FEF2F2; border-left: 4px solid #B03535; padding: 16px; border-radius: 4px; margin-bottom: 24px; }}
    .box-hallazgos ul {{ margin-left: 20px; font-size: 13px; color: #7F1D1D; }}
    .box-hallazgos li {{ margin-bottom: 6px; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>NetDiagBench-L7 — Informe de Correlación Diagnóstica</h1>
      <div class="subtitle">Validación Convergente de Evaluaciones Humanas frente a Métricas Automatizadas</div>
    </div>

    <div class="box-hallazgos">
      <strong style="color: #991B1B; font-size: 14px;">Hallazgos Principales del Estudio:</strong>
      <ul>{hallazgos_html}</ul>
    </div>

    <h2>1. Matriz de Correlación Interítem de Spearman (C1 a C6, S, U)</h2>
    <table>
      <thead>
        <tr><th style='width: 60px;'>Ítem</th>{m_headers}</tr>
      </thead>
      <tbody>
        {m_rows}
      </tbody>
    </table>

    <h2>2. Validez Convergente: Humano frente a Evaluador Automático</h2>
    <table>
      <thead>
        <tr><th>Cruce de Métricas</th><th style="width: 140px; text-align:center;">Coeficiente</th><th>Detalle Estadístico</th></tr>
      </thead>
      <tbody>
        <tr>
          <td><strong>Rúbrica Humana frente a Rúbrica Automática</strong></td>
          <td style="text-align:center;">ρ = {report_data['analisis_2_validez_convergente']['rubrica_spearman']['rho'] if report_data['analisis_2_validez_convergente']['rubrica_spearman']['rho'] is not None else 'N/A'}</td>
          <td>Valor p = {format_p_value(report_data['analisis_2_validez_convergente']['rubrica_spearman']['p_value'])} &bull; IC 95%: {report_data['analisis_2_validez_convergente']['rubrica_spearman']['ci_95']}</td>
        </tr>
        <tr>
          <td><strong>Concordancia de Causa Raíz (Decisión Binaria)</strong></td>
          <td style="text-align:center;">κ = {report_data['analisis_2_validez_convergente']['exactitud_kappa']}</td>
          <td>Coeficiente Phi = {report_data['analisis_2_validez_convergente']['exactitud_phi']}</td>
        </tr>
        <tr>
          <td><strong>Acuerdo en Evidencia Empírica Sustentada</strong></td>
          <td style="text-align:center;">κ = {report_data['analisis_2_validez_convergente']['sustentado_kappa']}</td>
          <td>Matriz 2x2: TP={report_data['analisis_2_validez_convergente']['sustentado_tabla_2x2']['TP']}, FN={report_data['analisis_2_validez_convergente']['sustentado_tabla_2x2']['FN']}</td>
        </tr>
      </tbody>
    </table>

    {bloque_3_4_5}
  </div>
</body>
</html>
"""

    if is_blind:
        html_template = anonymize_text(html_template)
        leaks = check_forbidden_terms(html_template)
        if leaks:
            raise ValueError(f"Fuga en informe ciego HTML: {leaks}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_template)

    return output_path


def export_correlation_report_pdf(
    report_data: dict[str, Any],
    unified_rows: list[dict[str, Any]],
    output_path: Path,
) -> Path:
    """
    Genera el informe técnico institucional Informe_Correlacion_<sesion>.pdf usando ReportLab.
    Respeta la prueba ciega: si es_ciego=True, excluye nombres de modelo y análisis 3 a 5.
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import (
        HRFlowable,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("RepTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=15, leading=19, textColor=colors.HexColor("#0F172A"), alignment=0)
    sub_style = ParagraphStyle("RepSub", parent=styles["Normal"], fontName="Helvetica-Oblique", fontSize=8.5, leading=12, textColor=colors.HexColor("#475569"))
    h1_style = ParagraphStyle("RepH1", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=11, leading=15, textColor=colors.HexColor("#0284C7"), spaceBefore=10, spaceAfter=5, keepWithNext=True)
    body_style = ParagraphStyle("RepBody", parent=styles["BodyText"], fontName="Helvetica", fontSize=8, leading=11, textColor=colors.HexColor("#1E293B"))
    table_cell = ParagraphStyle("TableCell", parent=body_style, fontSize=7.5, leading=10, alignment=1)
    table_header = ParagraphStyle("TableHeader", parent=table_cell, fontName="Helvetica-Bold", textColor=colors.white)

    story = []

    # Título y metadatos
    story.append(Paragraph("NetDiagBench-L7: Informe de Análisis Correlacional", title_style))
    story.append(Paragraph("Validación Humana vs Métricas del Benchmark • Capa 8", sub_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0284C7"), spaceBefore=6, spaceAfter=10))

    # Hallazgos principales
    story.append(Paragraph("Hallazgos Principales", h1_style))
    for h in report_data.get("hallazgos_principales", []):
        story.append(Paragraph(f"• {h}", body_style))
    story.append(Spacer(1, 8))

    # Matriz interítem
    story.append(Paragraph("1. Matriz de Correlación Interítem de Spearman (C1-C6, S, U)", h1_style))
    matrix = report_data.get("analisis_1_interitem", {})
    if matrix:
        col_names = ["Ítem"] + [k.upper() for k in matrix.keys()]
        table_data = [[Paragraph(c, table_header) for c in col_names]]
        for k1, row_dict in matrix.items():
            row = [Paragraph(k1.upper(), table_header)]
            for k2, cell in row_dict.items():
                rho = cell.get("rho")
                txt = "s/var" if rho is None else f"{rho:.2f}"
                row.append(Paragraph(txt, table_cell))
            table_data.append(row)

        t = Table(table_data, colWidths=[40] + [48] * (len(col_names) - 1))
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E293B")),
            ('BACKGROUND', (0, 1), (0, -1), colors.HexColor("#334155")),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        story.append(t)
    story.append(Spacer(1, 8))

    # Validez convergente
    story.append(Paragraph("2. Validez Convergente: Humano vs Evaluador Automático", h1_style))
    a2 = report_data.get("analisis_2_validez_convergente", {})
    val_data = [
        [Paragraph("Indicador", table_header), Paragraph("Coeficiente", table_header), Paragraph("p-valor", table_header), Paragraph("Interpretación", table_header)],
        [Paragraph("Spearman Rúbricas", body_style), Paragraph(f"{(a2.get('rubrica_spearman', {}).get('rho') or 0.0):.3f}", table_cell), Paragraph(f"{(a2.get('rubrica_spearman', {}).get('p_value') or 1.0):.4f}", table_cell), Paragraph(str(a2.get('rubrica_spearman', {}).get('interpretacion', '')), body_style)],
        [Paragraph("Pearson Rúbricas", body_style), Paragraph(f"{(a2.get('rubrica_pearson', {}).get('r') or 0.0):.3f}", table_cell), Paragraph(f"{(a2.get('rubrica_pearson', {}).get('p_value') or 1.0):.4f}", table_cell), Paragraph(str(a2.get('rubrica_pearson', {}).get('interpretacion', '')), body_style)],
    ]
    t2 = Table(val_data, colWidths=[120, 70, 70, 240])
    t2.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0284C7")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(t2)
    story.append(Spacer(1, 8))

    # Protocolo Ciego / Análisis 3-5
    if report_data.get("es_ciego", True):
        story.append(Paragraph("Evaluación Ciega en Curso", h1_style))
        story.append(Paragraph("Los análisis de Calidad frente a Costo (TTFT, tok/s, energía) y Calidad frente a Tamaño de Modelo se encuentran estrictamente restringidos conforme al protocolo de prueba ciega.", body_style))
    else:
        story.append(Paragraph("3. Calidad Diagnóstica frente a Costo y Tamaño", h1_style))
        story.append(Paragraph("Análisis desagregados por modelo y recursos ejecutados exitosamente.", body_style))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.build(story)
    return output_path
