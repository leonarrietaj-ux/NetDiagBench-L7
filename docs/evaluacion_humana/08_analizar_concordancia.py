#!/usr/bin/env python3
"""
Analiza concordancia de dos evaluadores para NetDiagBench-L7.
Entrada CSV en formato largo: una fila por case_id y evaluator_id.
Requisitos: pandas, numpy, scikit-learn.
No modifica el CSV de origen.
"""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score

ORDINAL = ["C1", "C2", "C3", "C4", "C5", "C6"]
BINARY = ["S"]

def bootstrap_kappa(a, b, weights, n_boot=1000, seed=20261105):
    rng = np.random.default_rng(seed)
    n = len(a)
    vals = []
    if n < 5:
        return (np.nan, np.nan)
    for _ in range(n_boot):
        idx = rng.integers(0, n, size=n)
        aa, bb = a[idx], b[idx]
        try:
            k = cohen_kappa_score(aa, bb, weights=weights)
            if np.isfinite(k):
                vals.append(k)
        except Exception:
            pass
    if len(vals) < max(100, int(n_boot * 0.5)):
        return (np.nan, np.nan)
    return tuple(np.quantile(vals, [0.025, 0.975]))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", help="CSV largo de evaluaciones")
    ap.add_argument("--e1", default="E1")
    ap.add_argument("--e2", default="E2")
    ap.add_argument("--weights", choices=["linear", "quadratic"], default="quadratic")
    ap.add_argument("--bootstrap", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=20261105)
    ap.add_argument("--out", default="salida_concordancia")
    args = ap.parse_args()

    df = pd.read_csv(args.csv)
    required = {"case_id", "evaluator_id", *ORDINAL, *BINARY}
    missing = required - set(df.columns)
    if missing:
        raise SystemExit(f"Faltan columnas requeridas: {sorted(missing)}")

    df = df[df["evaluator_id"].isin([args.e1, args.e2])].copy()
    if df.duplicated(["case_id", "evaluator_id"]).any():
        raise SystemExit("Hay duplicados de case_id/evaluator_id. Resolver antes del análisis.")

    out = []
    for criterion in ORDINAL + BINARY:
        p = df.pivot(index="case_id", columns="evaluator_id", values=criterion)
        if args.e1 not in p.columns or args.e2 not in p.columns:
            continue
        p = p[[args.e1, args.e2]].dropna()
        n = len(p)
        if n == 0:
            continue
        a = p[args.e1].to_numpy()
        b = p[args.e2].to_numpy()
        if criterion in ORDINAL:
            # Validar valores numéricos ordinales; adaptar según escala formalizada en Actividad A1.3.
            a = pd.to_numeric(pd.Series(a), errors="coerce").to_numpy()
            b = pd.to_numeric(pd.Series(b), errors="coerce").to_numpy()
            valid = np.isfinite(a) & np.isfinite(b)
            a, b = a[valid], b[valid]
            k_weights = args.weights
        else:
            k_weights = None
        if len(a) == 0:
            continue
        agreement = float(np.mean(a == b))
        try:
            kappa = float(cohen_kappa_score(a, b, weights=k_weights))
        except Exception:
            kappa = np.nan
        lo, hi = bootstrap_kappa(a, b, k_weights, args.bootstrap, args.seed)
        out.append({
            "criterio": criterion,
            "n_pares_completos": len(a),
            "acuerdo_exacto": agreement,
            "kappa_cohen": kappa,
            "ponderacion": k_weights or "ninguna",
            "ic95_bootstrap_inferior": lo,
            "ic95_bootstrap_superior": hi,
            "bootstrap_replicas_solicitadas": args.bootstrap,
            "semilla": args.seed
        })

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    result = pd.DataFrame(out)
    result.to_csv(outdir / "concordancia_resultados.csv", index=False)
    with open(outdir / "informe_concordancia.md", "w", encoding="utf-8") as f:
        f.write("# Informe de concordancia entre evaluadores\\n\\n")
        f.write(f"- Evaluadores: {args.e1} y {args.e2}\\n")
        f.write(f"- Ponderación ordinal: {args.weights}\\n")
        f.write(f"- Bootstrap: {args.bootstrap} remuestreos; semilla {args.seed}\\n")
        f.write("- Los pares incompletos se excluyeron por criterio; no se imputaron.\\n")
        f.write("- La adjudicación por E3 debe realizarse después de este análisis y conservarse por separado.\\n\\n")
        if result.empty:
            f.write("No se pudieron calcular métricas. Verificar datos y columnas.\\n")
        else:
            f.write(result.to_markdown(index=False))
            f.write("\\n\\nInterpretar kappa junto con el acuerdo observado, distribución de categorías e intervalos.\\n")
    print(f"Resultados guardados en: {outdir.resolve()}")

if __name__ == "__main__":
    main()
