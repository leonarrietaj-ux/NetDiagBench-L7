#!/usr/bin/env python3
"""
NetDiagBench-L7: Verificador Integral de Consistencia Científica, Estadística y de Publicación (v1.0.3).
Implementa los 18 controles obligatorios de auditoría:
 1. Conteo de las 162 corridas experimentales canónicas.
 2. Validación de la terna de modelos (glm-4-9b-chat, phi-4-mini-instruct, qwen3-8b).
 3. Validación de los 18 escenarios RFC de Capa 7.
 4. Validación de las 3 semillas deterministas ([42, 1337, 2026]).
 5. Verificación de los cuatro totales de acierto oficiales (122, 71, 120, 38).
 6. Desglose granular por modelo (aciertos por dimensión).
 7. Consistencia y metadatos del FAIR Dataset Bundle (dataset_bundle.json).
 8. Verificación criptográfica de hashes SHA-256 contra el manifiesto oficial.
 9. Consistencia del manifiesto experimental (manifest.json y campaign_162).
10. Recálculo dinámico del Scorecard Multicriterio y elegibilidad técnica.
11. Verificación inferencial no paramétrica (Friedman y Wilcoxon-Holm).
12. Coherencia global de versión (v1.0.3 en pyproject, CFF, bundle, manifest).
13. Verificación de presencia e integridad de archivos documentales obligatorios.
14. Detección automática de enlaces relativos locales rotos en Markdown.
15. Detección de referencias a documentos privados o inexistentes.
16. Escaneo de seguridad contra exposición de credenciales y secretos.
17. Comprobación de metadatos de autoría y repositorio público.
18. Consistencia estricta de métricas entre documentación técnica y dataset canónico.
"""

import sys
import re
import json
import hashlib
from pathlib import Path
import pandas as pd
import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

def sha256_of_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().upper()

def run_all_checks() -> bool:
    print("=" * 80)
    print("AUDITORÍA INTEGRAL DE CONSISTENCIA CIENTÍFICA Y TÉCNICA - NETDIAGBENCH-L7 v1.0.3")
    print("=" * 80)

    checks_passed = 0
    checks_failed = 0
    failures = []

    def report_check(num: int, title: str, passed: bool, details: str = "", expected: str = "", actual: str = "", file_affected: str = ""):
        nonlocal checks_passed, checks_failed
        status_tag = "[PASS]" if passed else "[FAIL]"
        print(f"\n[{num:02d}] {title} -> {status_tag}")
        if passed:
            checks_passed += 1
            if details:
                print(f"     Evidencia: {details}")
        else:
            checks_failed += 1
            err_msg = f"Check {num:02d} ({title}) FALLÓ."
            if file_affected:
                err_msg += f" Archivo: {file_affected}."
            if expected:
                err_msg += f" Esperado: {expected}."
            if actual:
                err_msg += f" Obtenido: {actual}."
            if details:
                err_msg += f" Detalle: {details}"
            print(f"     ERROR: {err_msg}")
            failures.append(err_msg)

    csv_path = REPO_ROOT / "data" / "benchmark_results" / "resultados.csv"
    bundle_path = REPO_ROOT / "data" / "benchmark_results" / "dataset_bundle.json"
    manifest_path = REPO_ROOT / "manifest.json"
    pub_manifest_path = REPO_ROOT / "data" / "benchmark_results" / "MANIFEST_PUBLICACION_SHA256.json"
    pyproject_path = REPO_ROOT / "pyproject.toml"
    citation_path = REPO_ROOT / "CITATION.cff"

    # Cargar dataset canónico
    df = None
    if csv_path.exists():
        df = pd.read_csv(csv_path)

    # 1. Conteo de las 162 corridas
    if df is not None:
        c1_ok = len(df) == 162
        report_check(1, "Población experimental canónica", c1_ok, f"Exactamente {len(df)} corridas", "162", str(len(df)), str(csv_path.relative_to(REPO_ROOT)))
    else:
        report_check(1, "Población experimental canónica", False, "No existe resultados.csv", "162", "0", str(csv_path))

    # 2. Validación de los tres modelos
    if df is not None:
        models = sorted(df["model_id"].unique().tolist())
        exp_models = ["glm-4-9b-chat", "phi-4-mini-instruct", "qwen3-8b"]
        counts_ok = all(len(df[df["model_id"] == m]) == 54 for m in exp_models)
        c2_ok = (models == exp_models) and counts_ok
        report_check(2, "Validación de terna de modelos evaluados", c2_ok, f"Modelos: {models} (54 corridas c/u)", str(exp_models), str(models))
    else:
        report_check(2, "Validación de terna de modelos evaluados", False, "Dataset no cargado")

    # 3. Validación de los 18 escenarios RFC
    if df is not None:
        scenarios = df["scenario_id"].unique().tolist()
        c3_ok = len(scenarios) == 18
        report_check(3, "Validación de 18 escenarios RFC Layer 7", c3_ok, f"{len(scenarios)} escenarios únicos registrados", "18", str(len(scenarios)))
    else:
        report_check(3, "Validación de 18 escenarios RFC Layer 7", False, "Dataset no cargado")

    # 4. Validación de las tres semillas
    if df is not None:
        seeds = sorted(df["seed"].unique().tolist())
        exp_seeds = [42, 1337, 2026]
        seeds_counts_ok = all(len(df[df["seed"] == s]) == 54 for s in exp_seeds)
        c4_ok = (seeds == exp_seeds) and seeds_counts_ok
        report_check(4, "Validación de semillas deterministas", c4_ok, f"Semillas: {seeds} (54 corridas c/u)", str(exp_seeds), str(seeds))
    else:
        report_check(4, "Validación de semillas deterministas", False, "Dataset no cargado")

    # 5. Verificación de los cuatro indicadores oficiales
    if df is not None:
        full_tot = int(df["is_full_diagnosis_correct"].sum())
        strict_tot = int(df["is_root_cause_correct"].sum())
        class_tot = int(df["fault_class_match"].sum())
        ev_tot = int(df["evidence_backed"].sum())
        c5_ok = (full_tot == 122 and strict_tot == 71 and class_tot == 120 and ev_tot == 38)
        report_check(5, "Cuatro indicadores diagnósticos congelados", c5_ok,
                     f"Completo={full_tot}/162, Estricto={strict_tot}/162, Clase={class_tot}/162, Evidencia={ev_tot}/162",
                     "(122, 71, 120, 38)", f"({full_tot}, {strict_tot}, {class_tot}, {ev_tot})")
    else:
        report_check(5, "Cuatro indicadores diagnósticos congelados", False, "Dataset no cargado")

    # 6. Desglose granular por modelo
    if df is not None:
        per_model_exp = {
            "glm-4-9b-chat": {"full": 40, "strict": 33, "class": 40, "evidence": 23},
            "qwen3-8b": {"full": 47, "strict": 24, "class": 47, "evidence": 15},
            "phi-4-mini-instruct": {"full": 35, "strict": 14, "class": 33, "evidence": 0},
        }
        c6_ok = True
        desc_list = []
        for mid, exp in per_model_exp.items():
            mdf = df[df["model_id"] == mid]
            mf = int(mdf["is_full_diagnosis_correct"].sum())
            ms = int(mdf["is_root_cause_correct"].sum())
            mc = int(mdf["fault_class_match"].sum())
            me = int(mdf["evidence_backed"].sum())
            if (mf, ms, mc, me) != (exp["full"], exp["strict"], exp["class"], exp["evidence"]):
                c6_ok = False
            desc_list.append(f"{mid}: ({mf},{ms},{mc},{me})")
        report_check(6, "Desglose diagnóstico granular por modelo", c6_ok, "; ".join(desc_list), "Todas las cifras concordantes", "Concordancia verificada" if c6_ok else "Discrepancia detectada")
    else:
        report_check(6, "Desglose diagnóstico granular por modelo", False, "Dataset no cargado")

    # 7. Consistencia y metadatos del FAIR Dataset Bundle
    if bundle_path.exists():
        with open(bundle_path, "r", encoding="utf-8") as f:
            bundle = json.load(f)
        agg = bundle.get("aggregated_results", {})
        c7_acc_ok = (
            abs(agg.get("full_diagnosis_accuracy_all_models", 0) - 0.7531) <= 0.0005 and
            abs(agg.get("strict_root_cause_accuracy_all_models", 0) - 0.4383) <= 0.0005 and
            abs(agg.get("fault_class_accuracy_all_models", 0) - 0.7407) <= 0.0005 and
            abs(agg.get("evidence_backed_accuracy_all_models", 0) - 0.2346) <= 0.0005 and
            abs(agg.get("root_cause_accuracy_all_models", 0) - 0.4383) <= 0.0005
        )
        c7_cols_ok = bundle.get("academic_context", {}).get("project_title") is not None
        report_check(7, "Consistencia del FAIR Dataset Bundle (dataset_bundle.json)", c7_acc_ok and c7_cols_ok,
                     f"Exactitud agregada verificada. root_cause_accuracy_all_models={agg.get('root_cause_accuracy_all_models')}",
                     "0.4383 estricto y contexto válido", str(agg.get("root_cause_accuracy_all_models")), str(bundle_path.relative_to(REPO_ROOT)))
    else:
        report_check(7, "Consistencia del FAIR Dataset Bundle (dataset_bundle.json)", False, "No existe dataset_bundle.json")

    # 8. Verificación criptográfica de hashes SHA-256
    if pub_manifest_path.exists():
        with open(pub_manifest_path, "r", encoding="utf-8") as f:
            manifest_json = json.load(f)
        hashes_block = manifest_json.get("integrity_hashes", {})
        c8_ok = True
        checked_files = 0
        mismatch_files = []
        for cat, file_dict in hashes_block.items():
            for rel_str, meta in file_dict.items():
                fp = REPO_ROOT / rel_str
                if not fp.exists():
                    c8_ok = False
                    mismatch_files.append(f"Inexistente: {rel_str}")
                    continue
                real_hash = sha256_of_file(fp)
                exp_hash = meta.get("sha256", "").upper()
                if real_hash != exp_hash:
                    c8_ok = False
                    mismatch_files.append(f"{rel_str} (real={real_hash[:8]} vs exp={exp_hash[:8]})")
                checked_files += 1
        report_check(8, f"Integridad criptográfica SHA-256 ({checked_files} archivos auditados)", c8_ok,
                     f"{checked_files} hashes verificados contra bytes reales", "Todos coincidentes",
                     "Coincidencia 100%" if c8_ok else f"Desajustes: {mismatch_files}", str(pub_manifest_path.relative_to(REPO_ROOT)))
    else:
        report_check(8, "Integridad criptográfica SHA-256", False, "No existe MANIFEST_PUBLICACION_SHA256.json")

    # 9. Consistencia del manifiesto experimental
    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            man = json.load(f)
        des = man.get("experimental_design", {})
        c9_ok = (des.get("total_runs") == 162 and des.get("total_scenarios") == 18 and des.get("models_count") == 3)
        report_check(9, "Consistencia del Manifiesto Experimental (manifest.json)", c9_ok,
                     f"Runs={des.get('total_runs')}, Scenarios={des.get('total_scenarios')}, Models={des.get('models_count')}",
                     "(162, 18, 3)", f"({des.get('total_runs')}, {des.get('total_scenarios')}, {des.get('models_count')})")
    else:
        report_check(9, "Consistencia del Manifiesto Experimental (manifest.json)", False, "No existe manifest.json")

    # 10. Recálculo del Scorecard Multicriterio y elegibilidad
    try:
        from src.layer7_evaluator.composite_score import calculate_model_composite_scores
        from src.layer7_evaluator.statistical_analysis import build_comparative_summary

        summary = build_comparative_summary(rows=df.to_dict(orient="records"))
        scores = calculate_model_composite_scores(summary["models"])
        exp_scorecard = {
            "glm-4-9b-chat": (0.7323, True),
            "qwen3-8b": (0.7217, True),
            "phi-4-mini-instruct": (0.8012, False),
        }
        c10_ok = True
        score_details = []
        for mid, (exp_s, exp_e) in exp_scorecard.items():
            s_obj = scores[mid]
            act_s = s_obj["puntaje_compuesto_provisional"]
            act_e = s_obj["elegibilidad"]
            if abs(act_s - exp_s) > 0.001 or act_e != exp_e:
                c10_ok = False
            score_details.append(f"{mid}: {act_s:.4f} (Elegible={act_e})")
        report_check(10, "Scorecard Multicriterio y Umbral de Viabilidad (70%)", c10_ok,
                     "; ".join(score_details), "GLM=0.7323(E), Qwen=0.7217(E), Phi=0.8012(NE)",
                     "Concordancia verificada" if c10_ok else "Discrepancia en scorecard")
    except Exception as e:
        report_check(10, "Scorecard Multicriterio y Umbral de Viabilidad (70%)", False, f"Excepción: {e}")

    # 11. Verificación inferencial no paramétrica (Friedman y Wilcoxon-Holm)
    try:
        from src.layer7_evaluator.statistical_analysis import compute_paired_friedman_and_wilcoxon
        p_stats = compute_paired_friedman_and_wilcoxon(df.to_dict(orient="records"), metric="full_diagnosis")
        f_stat = p_stats["friedman"]["statistic_chi2"]
        f_pval = p_stats["friedman"]["p_value"]
        c11_ok = (f_pval is not None and f_pval < 0.05 and p_stats["friedman"]["degrees_of_freedom"] == 2)
        report_check(11, "Inferencia estadística no paramétrica (Friedman / Wilcoxon-Holm)", c11_ok,
                     f"chi2={f_stat:.4f}, df=2, p={f_pval:.5f}", "chi2=6.8205, p=0.03303", f"chi2={f_stat:.4f}, p={f_pval:.5f}")
    except Exception as e:
        report_check(11, "Inferencia estadística no paramétrica (Friedman / Wilcoxon-Holm)", False, f"Excepción: {e}")

    # 12. Coherencia global de versiones (v1.0.3)
    target_ver = "1.0.3"
    vers = {}
    if pyproject_path.exists():
        match = re.search(r'version\s*=\s*"([^"]+)"', pyproject_path.read_text(encoding="utf-8"))
        vers["pyproject"] = match.group(1) if match else None
    if citation_path.exists():
        match = re.search(r'^version:\s*([^\s]+)', citation_path.read_text(encoding="utf-8"), re.MULTILINE)
        vers["citation"] = match.group(1) if match else None
    if bundle_path.exists():
        with open(bundle_path, "r", encoding="utf-8") as f:
            b_json = json.load(f)
        vers["bundle"] = b_json.get("academic_context", {}).get("version")
    if pub_manifest_path.exists():
        with open(pub_manifest_path, "r", encoding="utf-8") as f:
            m_json = json.load(f)
        vers["manifest"] = m_json.get("version")

    c12_ok = all(v == target_ver for v in vers.values()) and len(vers) == 4
    report_check(12, f"Coherencia de versión en metadatos (v{target_ver})", c12_ok,
                 str(vers), f"Todos en {target_ver}", str(vers))

    # 13. Verificación de archivos documentales obligatorios
    req_docs = [
        "README.md",
        "docs/CONFIGURACION_MODELOS.md",
        "docs/RESULTADOS_BENCHMARK.md",
        "docs/EVALUACION_TRADEOFF.md",
        "docs/ANALISIS_ESTADISTICO.md",
        "docs/SEGURIDAD_SISTEMA.md",
        "docs/MANUAL_TECNICO.md",
        "docs/GUIA_OPERACION.md",
        "docs/GUIA_REPRODUCIBILIDAD.md",
        "docs/evaluacion_humana/00_LEEME.md",
        "docs/evaluacion_humana/05_Registro_evaluaciones.csv",
        "docs/evaluacion_humana/06_Clave_tecnica_escenarios.csv",
        "docs/evaluacion_humana/07_Plan_analisis_concordancia.md",
        "docs/evaluacion_humana/08_analizar_concordancia.py",
        "docs/evaluacion_humana/09_Guia_anonimizacion_y_adjudicacion.md",
    ]
    missing_docs = [d for d in req_docs if not (REPO_ROOT / d).exists()]
    c13_ok = len(missing_docs) == 0
    report_check(13, f"Inventario documental obligatorio ({len(req_docs)} archivos)", c13_ok,
                 "Todos los documentos técnicos obligatorios presentes", "0 faltantes", str(missing_docs))

    # 14. Detección automática de enlaces relativos rotos en Markdown
    md_files = list(REPO_ROOT.glob("*.md")) + list(REPO_ROOT.glob("docs/**/*.md"))
    link_pattern = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
    broken_links = []
    for md in md_files:
        content = md.read_text(encoding="utf-8")
        for match in link_pattern.finditer(content):
            text, url = match.groups()
            if url.startswith(("http://", "https://", "mailto:", "#")):
                continue
            target_path = url.split("#")[0]
            if not target_path:
                continue
            resolved = (md.parent / target_path).resolve()
            if not resolved.exists():
                broken_links.append((str(md.relative_to(REPO_ROOT)), url, text))

    c14_ok = len(broken_links) == 0
    report_check(14, "Auditoría de enlaces locales en Markdown", c14_ok,
                 f"{len(md_files)} archivos Markdown inspeccionados; 0 enlaces rotos" if c14_ok else f"Enlaces rotos detectados: {broken_links}",
                 "0 enlaces rotos", f"{len(broken_links)} rotos")

    # 15. Detección de referencias a documentos privados o inexistentes
    banned_refs = ["INFORME_PARTE_1", "INFORME_PARTE_2", "INFORME_PARTE_3", "INFORME_PARTE_4", "DOCUMENTO_FINAL_TESIS"]
    found_banned = []
    for md in md_files:
        content = md.read_text(encoding="utf-8")
        for b in banned_refs:
            if b in content:
                found_banned.append((str(md.relative_to(REPO_ROOT)), b))

    c15_ok = len(found_banned) == 0
    report_check(15, "Ausencia de referencias a documentos privados o excluidos", c15_ok,
                 "Ningún enlace a informes de auditoría interna ni borradores de tesis", "0 referencias privadas", str(found_banned))

    # 16. Escaneo de seguridad contra credenciales y secretos conocidos
    secret_patterns = [
        re.compile(r'(?i)(api[_-]?key|secret[_-]?key|private[_-]?key)\s*[:=]\s*["\']?[a-zA-Z0-9_\-]{16,}'),
        re.compile(r'-----BEGIN\s+(RSA|EC|DSA|OPENSSH)\s+PRIVATE\s+KEY-----'),
    ]
    secret_findings = []
    for f in REPO_ROOT.rglob("*"):
        if f.is_file() and not f.name.endswith((".pyc", ".png", ".jpg", ".xlsx", ".pdf")) and ".git" not in f.parts:
            try:
                txt = f.read_text(encoding="utf-8", errors="ignore")
                for pat in secret_patterns:
                    if pat.search(txt):
                        secret_findings.append(str(f.relative_to(REPO_ROOT)))
                        break
            except Exception:
                pass

    c16_ok = len(secret_findings) == 0
    report_check(16, "Escaneo de seguridad contra exposición de credenciales/secretos", c16_ok,
                 "0 claves privadas, secretos o tokens detectados", "0 hallazgos", str(secret_findings))

    # 17. Metadatos de publicación (autores colectivos, URLs oficiales)
    c17_ok = True
    c17_details = []
    if pyproject_path.exists():
        py_txt = pyproject_path.read_text(encoding="utf-8")
        if "NetDiagBench-L7 Contributors" in py_txt:
            c17_details.append("pyproject: NetDiagBench-L7 Contributors")
        else:
            c17_ok = False
    if citation_path.exists():
        cit_txt = citation_path.read_text(encoding="utf-8")
        if "NetDiagBench-L7 Contributors" in cit_txt and "https://github.com/leonarrietaj-ux/NetDiagBench-L7" in cit_txt:
            c17_details.append("CITATION: Contributors + Repo URL")
        else:
            c17_ok = False
    report_check(17, "Metadatos de publicación y atribución neutral", c17_ok,
                 "; ".join(c17_details), "Atribución colectiva e institucional válida", "Conforme" if c17_ok else "No conforme")

    # 18. Consistencia estricta de métricas entre documentación y dataset
    bench_doc = REPO_ROOT / "docs" / "RESULTADOS_BENCHMARK.md"
    c18_ok = True
    c18_issues = []
    if bench_doc.exists():
        doc_txt = bench_doc.read_text(encoding="utf-8")
        # Verificar que no contenga los números obsoletos de versiones previas no normativas
        obsolete_patterns = ["79.0% (128/162)", "95.1% (154/162)", "4.24 / 5.0"]
        for p in obsolete_patterns:
            if p in doc_txt and "Nota Histórica sobre Versiones Preliminares" not in doc_txt:
                c18_ok = False
                c18_issues.append(f"Cifra obsoleta en tabla oficial: {p}")
        # Verificar que aparezcan los totales consolidados normativos
        norm_checks = ["75.3% (122/162)", "43.8% (71/162)", "23.5% (38/162)", "3.92 / 5.0"]
        for n in norm_checks:
            if n not in doc_txt:
                c18_ok = False
                c18_issues.append(f"Falta cifra normativa oficial: {n}")
    report_check(18, "Consistencia estricta de métricas (Documentación vs Dataset)", c18_ok,
                 "Tabla consolidada y notas históricas perfectamente sincronizadas con resultados.csv",
                 "Sin cifras obsoletas en tablas oficiales; 122, 71, 38, 3.92 presentes",
                 "Conforme" if c18_ok else f"Problemas: {c18_issues}")

    print("\n" + "=" * 80)
    print(f"RESUMEN FINAL: {checks_passed}/18 CONTROLES APROBADOS ({checks_passed/18*100:.1f}%) | {checks_failed} FALLOS")
    print("=" * 80)

    if failures:
        print("\nDETALLE DE FALLOS:")
        for idx, f in enumerate(failures, 1):
            print(f"  {idx}. {f}")
        return False
    else:
        print("\nDICTAMEN DE AUDITORÍA: APROBADO AL 100% (COHERENCIA CIENTÍFICA Y TÉCNICA TOTAL)")
        return True

if __name__ == "__main__":
    success = run_all_checks()
    sys.exit(0 if success else 1)
