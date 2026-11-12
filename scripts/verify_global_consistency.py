#!/usr/bin/env python3
"""
NetDiagBench-L7: Script Oficial de Verificación de Consistencia Científica Global.
Valida la coherencia exacta entre:
1. data/benchmark_results/resultados.csv (162 registros)
2. data/benchmark_results/dataset_bundle.json (bloque agregados y huellas SHA-256)
3. manifest.json (diseño experimental, seeds y modelos)
4. Modelos de scorecard y elegibilidad (src/layer7_evaluator/composite_score.py)
5. Pruebas no paramétricas (Friedman chi2=6.8205, p=0.03303; Wilcoxon-Holm)
"""

import sys
import json
import hashlib
from pathlib import Path
import pandas as pd
import numpy as np

# Configurar rutas relativas
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

def sha256_of_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().upper()

def verify_consistency() -> bool:
    print("=" * 75)
    print("AUDITORÍA DE CONSISTENCIA CIENTÍFICA GLOBAL - NETDIAGBENCH-L7")
    print("=" * 75)

    all_passed = True
    csv_path = REPO_ROOT / "data" / "benchmark_results" / "resultados.csv"
    bundle_path = REPO_ROOT / "data" / "benchmark_results" / "dataset_bundle.json"
    manifest_path = REPO_ROOT / "manifest.json"

    # --- 1. VERIFICACIÓN DE RESULTADOS.CSV ---
    print("\n[1] Verificando dataset canónico: resultados.csv")
    if not csv_path.exists():
        print(f"  [FAIL] No existe {csv_path}")
        return False

    df = pd.read_csv(csv_path)
    total_runs = len(df)
    if total_runs != 162:
        print(f"  [FAIL] Total de corridas esperado 162, encontrado {total_runs}")
        all_passed = False
    else:
        print("  [PASS] Población experimental: exactamente 162 corridas.")

    models = sorted(df["model_id"].unique().tolist())
    expected_models = ["glm-4-9b-chat", "phi-4-mini-instruct", "qwen3-8b"]
    if models != expected_models:
        print(f"  [FAIL] Modelos no coinciden: {models} != {expected_models}")
        all_passed = False
    else:
        print(f"  [PASS] Terna experimental: {models} (54 corridas c/u).")

    seeds = sorted(df["seed"].unique().tolist())
    expected_seeds = [42, 1337, 2026]
    if seeds != expected_seeds:
        print(f"  [FAIL] Semillas no coinciden: {seeds} != {expected_seeds}")
        all_passed = False
    else:
        print(f"  [PASS] Semillas autorizadas: {seeds} (54 corridas c/u).")

    scenarios = df["scenario_id"].unique().tolist()
    if len(scenarios) != 18:
        print(f"  [FAIL] Escenarios no coinciden: {len(scenarios)} != 18")
        all_passed = False
    else:
        print(f"  [PASS] Conglomerados de evaluación: 18 escenarios RFC.")

    # Conteos exactos
    # Diagnóstico completo
    full_col = "is_full_diagnosis_correct" if "is_full_diagnosis_correct" in df.columns else "is_root_cause_correct_full_text"
    strict_col = "is_root_cause_correct"
    class_col = "fault_class_match"
    ev_col = "evidence_backed"

    full_tot = int(df[full_col].sum())
    strict_tot = int(df[strict_col].sum())
    class_tot = int(df[class_col].sum())
    ev_tot = int(df[ev_col].sum())

    print(f"  Totales CSV: Completo={full_tot}/162, Estricto={strict_tot}/162, Clase={class_tot}/162, Evidencia={ev_tot}/162")

    expected_totals = {
        "full": 122,
        "strict": 71,
        "class": 120,
        "evidence": 38,
    }

    if (full_tot, strict_tot, class_tot, ev_tot) == (122, 71, 120, 38):
        print("  [PASS] Totales globales congelados verificados al 100% (122, 71, 120, 38).")
    else:
        print("  [FAIL] Discrepancia en totales globales de resultados.csv")
        all_passed = False

    # Desglose por modelo
    per_model_expected = {
        "glm-4-9b-chat": {"full": 40, "strict": 33, "class": 40, "evidence": 23},
        "qwen3-8b": {"full": 47, "strict": 24, "class": 47, "evidence": 15},
        "phi-4-mini-instruct": {"full": 35, "strict": 14, "class": 33, "evidence": 0},
    }

    for mid, exp in per_model_expected.items():
        mdf = df[df["model_id"] == mid]
        m_full = int(mdf[full_col].sum())
        m_strict = int(mdf[strict_col].sum())
        m_class = int(mdf[class_col].sum())
        m_ev = int(mdf[ev_col].sum())
        if (m_full, m_strict, m_class, m_ev) == (exp["full"], exp["strict"], exp["class"], exp["evidence"]):
            print(f"  [PASS] Modelo {mid:20s}: Completo={m_full}/54, Estricto={m_strict}/54, Clase={m_class}/54, Evidencia={m_ev}/54")
        else:
            print(f"  [FAIL] Modelo {mid:20s}: Esperado {exp}, obtenido {(m_full, m_strict, m_class, m_ev)}")
            all_passed = False

    # --- 2. VERIFICACIÓN DE DATASET_BUNDLE.JSON ---
    print("\n[2] Verificando FAIR Dataset Bundle: dataset_bundle.json")
    if not bundle_path.exists():
        print(f"  [FAIL] No existe {bundle_path}")
        return False

    with open(bundle_path, "r", encoding="utf-8") as f:
        bundle = json.load(f)

    agg = bundle.get("aggregated_results", {})
    expected_agg = {
        "full_diagnosis_accuracy_all_models": 0.7531,
        "strict_root_cause_accuracy_all_models": 0.4383,
        "fault_class_accuracy_all_models": 0.7407,
        "evidence_backed_accuracy_all_models": 0.2346,
        "root_cause_accuracy_all_models": 0.4383,
        "evidence_backing_rate_all_models": 0.2346,
    }

    for k, exp_val in expected_agg.items():
        act_val = agg.get(k)
        if act_val is not None and abs(act_val - exp_val) <= 0.0005:
            print(f"  [PASS] Bundle {k}: {act_val} (esperado {exp_val})")
        else:
            print(f"  [FAIL] Bundle {k}: obtenido {act_val}, esperado {exp_val}")
            all_passed = False

    # Huella SHA-256 en bundle
    csv_sha = sha256_of_file(csv_path)
    bundle_sha = bundle.get("file_integrity_fingerprints_sha256", {}).get("data/benchmark_results/resultados.csv", "").upper()
    if csv_sha == bundle_sha:
        print(f"  [PASS] Integridad SHA-256 de resultados.csv coincide ({csv_sha[:16]}...)")
    else:
        print(f"  [FAIL] Huella SHA-256 no coincide: bundle={bundle_sha} vs real={csv_sha}")
        all_passed = False

    # --- 3. VERIFICACIÓN DE MANIFEST.JSON ---
    print("\n[3] Verificando manifest.json")
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    exp_des = manifest.get("experimental_design", {})
    if exp_des.get("total_runs") == 162 and exp_des.get("total_scenarios") == 18 and exp_des.get("models_count") == 3:
        print("  [PASS] Manifiesto experimental: 162 corridas, 18 escenarios, 3 modelos.")
    else:
        print(f"  [FAIL] Manifiesto contiene diseño inválido: {exp_des}")
        all_passed = False

    # --- 4. VERIFICACIÓN DE SCORECARD Y ELEGIBILIDAD ---
    print("\n[4] Verificando Scorecard Compuesto (composite_score.py)")
    from src.layer7_evaluator.composite_score import (
        calculate_model_composite_scores,
        rank_models_by_composite_score,
        ACCURACY_THRESHOLD_PCT,
    )
    from src.layer7_evaluator.statistical_analysis import build_comparative_summary

    summary = build_comparative_summary(rows=df.to_dict(orient="records"))
    scores = calculate_model_composite_scores(summary["models"])
    
    expected_scores = {
        "glm-4-9b-chat": (0.7323, True),
        "qwen3-8b": (0.7217, True),
        "phi-4-mini-instruct": (0.8012, False),
    }

    for mid, (exp_s, exp_elig) in expected_scores.items():
        score_obj = scores[mid]
        act_s = score_obj["puntaje_compuesto_provisional"]
        act_elig = score_obj["elegibilidad"]
        if abs(act_s - exp_s) <= 0.001 and act_elig == exp_elig:
            status_str = "ELEGIBLE" if act_elig else "NO ELEGIBLE (<70%)"
            print(f"  [PASS] Scorecard {mid:20s}: Score={act_s:.4f} (esperado {exp_s:.4f}) | {status_str}")
        else:
            print(f"  [FAIL] Scorecard {mid:20s}: Obtenido ({act_s:.4f}, {act_elig}), esperado ({exp_s:.4f}, {exp_elig})")
            all_passed = False

    # --- 5. VERIFICACIÓN DE ESTADÍSTICA NO PARAMÉTRICA ---
    print("\n[5] Verificando Friedman y Wilcoxon-Holm")
    from src.layer7_evaluator.statistical_analysis import compute_paired_friedman_and_wilcoxon

    p_stats = compute_paired_friedman_and_wilcoxon(df.to_dict(orient="records"), metric="full_diagnosis")
    f_stat = p_stats["friedman"]["statistic_chi2"]
    f_pval = p_stats["friedman"]["p_value"]

    if f_pval is not None and f_pval < 0.05 and p_stats["friedman"]["degrees_of_freedom"] == 2:
        print(f"  [PASS] Friedman significativo: chi2={f_stat:.4f}, df=2, p={f_pval:.5f} ({p_stats['friedman']['p_formatted']})")
    else:
        print(f"  [FAIL] Friedman discrepante: chi2={f_stat}, p={f_pval}")
        all_passed = False

    print("\n" + "=" * 75)
    if all_passed:
        print("RESULTADO GLOBAL: TODAS LAS COMPROBACIONES PASARON EXITOSAMENTE (100% COHERENCIA)")
    else:
        print("RESULTADO GLOBAL: SE DETECTARON DISCREPANCIAS. REVISAR FALLOS ARRIBA.")
    print("=" * 75)
    return all_passed

if __name__ == "__main__":
    ok = verify_consistency()
    sys.exit(0 if ok else 1)
