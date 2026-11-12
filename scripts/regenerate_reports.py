#!/usr/bin/env python3
"""
NetDiagBench-L7: Regenerador de Entregables y Reportes Consolidados (Capa 7).
Lee data/benchmark_results/resultados.csv y recompila de forma sincronizada:
1. Markdown: resultados_resumen.md y analisis_correlacional.md
2. JSON: informe_modelos_seleccionados.json y dataset_bundle.json (con hashes SHA-256)
3. Excel: benchmark_l7_consolidado.xlsx (10 hojas con análisis Kruskal-Wallis y Bootstrap)
4. PDF: informe_consolidado_netdiagbench.pdf, informe_comparativo_oe4.pdf y analisis_correlacional.pdf
5. HTML: informe_consolidado.html (Dashboard interactivo consolidado)
"""

import sys
import hashlib
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.core.config import PROJECT_ROOT as ROOT_DIR
from src.core.logger import logger
from src.layer7_evaluator.excel_exporter import export_benchmark_to_excel
from src.layer7_evaluator.pdf_exporter import (
    export_consolidated_report_pdf,
    export_comparative_report_pdf,
    export_correlation_report_pdf,
)
from src.layer7_evaluator.report_generator import generate_html_benchmark_report
from src.layer7_evaluator.model_management import export_selection_json, refresh_dataset_bundle
from src.layer7_evaluator.statistical_analysis import (
    load_benchmark_csv,
    run_correlation_analysis,
    generate_correlation_report,
    build_comparative_summary,
    generate_comparative_markdown,
)

def sha256_of_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def regenerate_all_reports() -> bool:
    csv_path = ROOT_DIR / "data" / "benchmark_results" / "resultados.csv"
    if not csv_path.exists():
        print(f"[ERROR] No se encontró el dataset en {csv_path}")
        return False

    rows = load_benchmark_csv(csv_path)
    print(f"\n=====================================================================")
    print(f"      REGENERACIÓN DE ENTREGABLES NETDIAGBENCH-L7 ({len(rows)} FILAS)     ")
    print(f"=====================================================================\n")

    # 1. Markdowns
    print("1. Generando informes en Markdown...")
    comp_md_path = ROOT_DIR / "data" / "benchmark_results" / "resultados_resumen.md"
    comp_summary = build_comparative_summary(rows=rows)
    generate_comparative_markdown(comp_summary, output_path=comp_md_path)
    print(f"   [OK] {comp_md_path.name}")

    corr_md_path = ROOT_DIR / "data" / "benchmark_results" / "analisis_correlacional.md"
    analysis = run_correlation_analysis(rows=rows)
    generate_correlation_report(analysis=analysis, output_path=corr_md_path)
    print(f"   [OK] {corr_md_path.name}")

    # 2. JSON de selección
    print("\n2. Generando informe en JSON...")
    sel_json = ROOT_DIR / "data" / "benchmark_results" / "informe_modelos_seleccionados.json"
    export_selection_json(output_path=sel_json)
    print(f"   [OK] {sel_json.name}")

    # 3. Libro Excel Multioja
    print("\n3. Generando libro Excel estructurado (.xlsx)...")
    excel_path = ROOT_DIR / "data" / "benchmark_results" / "benchmark_l7_consolidado.xlsx"
    export_benchmark_to_excel(output_path=excel_path, rows=rows)
    print(f"   [OK] {excel_path.name}")

    # 4. Reportes PDF (ReportLab)
    print("\n4. Generando reportes institucionales en PDF...")
    pdf_cons = ROOT_DIR / "data" / "benchmark_results" / "informe_consolidado_netdiagbench.pdf"
    export_consolidated_report_pdf(output_path=pdf_cons, rows=rows)
    print(f"   [OK] {pdf_cons.name}")

    pdf_oe4 = ROOT_DIR / "data" / "benchmark_results" / "informe_comparativo_oe4.pdf"
    export_comparative_report_pdf(output_path=pdf_oe4, rows=rows)
    print(f"   [OK] {pdf_oe4.name}")

    pdf_corr = ROOT_DIR / "data" / "benchmark_results" / "analisis_correlacional.pdf"
    export_correlation_report_pdf(output_path=pdf_corr, rows=rows)
    print(f"   [OK] {pdf_corr.name}")

    # 5. HTML Interactivo
    print("\n5. Generando Dashboard HTML interactivo...")
    html_path = ROOT_DIR / "data" / "benchmark_results" / "informe_consolidado.html"
    generate_html_benchmark_report(output_path=html_path, rows=rows)
    print(f"   [OK] {html_path.name}")

    # 6. Sincronización de dataset_bundle.json con SHA-256
    print("\n6. Sincronizando dataset_bundle.json con huellas criptográficas SHA-256...")
    refresh_dataset_bundle(full=True)
    bundle_path = ROOT_DIR / "data" / "benchmark_results" / "dataset_bundle.json"
    if bundle_path.exists():
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        bundle["total_registros"] = len(rows)
        manifest = bundle.get("manifiesto_archivos", {})
        for fname, finfo in manifest.items():
            fpath = ROOT_DIR / "data" / "benchmark_results" / fname
            if fpath.exists():
                finfo["sha256"] = sha256_of_file(fpath)
                finfo["tamano_bytes"] = fpath.stat().st_size
        fingerprints = bundle.get("file_integrity_fingerprints_sha256", {})
        if "data/benchmark_results/resultados.csv" in fingerprints and csv_path.exists():
            fingerprints["data/benchmark_results/resultados.csv"] = sha256_of_file(csv_path).upper()
        bundle_path.write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"   [OK] {bundle_path.name} sincronizado (SHA-256 actualizado).")

    print("\n=====================================================================")
    print("   TODOS LOS ENTREGABLES HAN SIDO REGENERADOS EXITOSAMENTE           ")
    print("=====================================================================\n")
    return True

if __name__ == "__main__":
    success = regenerate_all_reports()
    sys.exit(0 if success else 1)
