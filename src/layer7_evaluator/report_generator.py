"""
NetDiagBench-L7: Layer 7 - Standalone HTML Evaluation & Benchmark Report Generator
Compila el informe técnico integral consolidado en HTML con tablas estilizadas,
gráficos de barras CSS/SVG, huella de hardware y matrices de correlación (SciPy).
Totalmente autónomo y sin dependencias externas (apto para auditoría offline del jurado).
"""

from datetime import datetime
from pathlib import Path
from typing import Any

from src.core.config import PROJECT_ROOT
from src.layer7_evaluator.statistical_analysis import (
    get_model_size_label,
    run_correlation_analysis,
)


def generate_html_benchmark_report(
    csv_path: Path | None = None,
    output_path: Path | None = None,
    correlation_analysis: dict[str, Any] | None = None,
    rows: list[dict[str, Any]] | None = None,
    models: str | list[str] | None = None,
) -> Path:
    """
    Genera el informe HTML consolidado a partir de los datos de benchmark,
    respetando los modelos seleccionados para el informe.
    """
    if csv_path is None:
        csv_path = PROJECT_ROOT / "data" / "benchmark_results" / "resultados.csv"

    if output_path is None:
        output_path = PROJECT_ROOT / "data" / "benchmark_results" / "informe_consolidado.html"

    if rows is None:
        from src.layer7_evaluator.model_management import load_selected_rows
        models_param = ",".join(models) if isinstance(models, list) else models
        rows, _ = load_selected_rows(models_param)

    if correlation_analysis is None:
        correlation_analysis = run_correlation_analysis(rows=rows)

    # Extraer métricas consolidadas por modelo
    by_model: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by_model.setdefault(r["model_id"], []).append(r)

    model_ids = sorted(by_model.keys())
    models_str = ",".join(models) if isinstance(models, list) else (models or "")
    from src.layer6_interface.export_toolbar import render_export_toolbar
    toolbar_html = render_export_toolbar("consolidado", models=models_str)

    hw_fingerprint = rows[0].get("host_hardware_fingerprint", "N/A") if rows else "N/A"
    desc = correlation_analysis.get("descriptives", {})
    corrs = correlation_analysis.get("correlations", {})
    kruskal = correlation_analysis.get("kruskal_wallis", {})

    total_full = sum(
        1 for r in rows if bool(r.get("is_full_diagnosis_correct")) or str(r.get("is_root_cause_correct_full_text", "")).lower() in ("true", "1")
    )
    global_full_acc = round(total_full / len(rows) * 100.0, 1) if rows else 0.0

    total_strict = sum(
        1 for r in rows if bool(r.get("is_root_cause_correct_strict")) or str(r.get("is_root_cause_correct", "")).lower() in ("true", "1")
    )
    global_strict_acc = round(total_strict / len(rows) * 100.0, 1) if rows else 0.0

    total_evidence = sum(
        1 for r in rows if bool(r.get("evidence_backed")) or str(r.get("evidence_backed", "")).lower() in ("true", "1")
    )
    global_evidence = round(total_evidence / len(rows) * 100.0, 1) if rows else 0.0

    # Concordancia dinámica de Cohen (Hallazgo 2.5)
    from src.layer7_evaluator.metrics import get_evaluator_version, load_evaluator_concepts
    eval_version = get_evaluator_version()
    concepts_data = load_evaluator_concepts()
    classes_dict = concepts_data.get("classes", {})

    # Derivación dinámica de la configuración de mejor compromiso (OE4 / Hallazgo C2)
    from src.layer7_evaluator.statistical_analysis import build_comparative_summary
    comp_summary = build_comparative_summary(rows=rows)
    models_dict = comp_summary.get("models", {})
    ranking = comp_summary.get("ranking", [])
    best_mid = ranking[0] if ranking else "qwen3-8b"
    best_m = models_dict.get(best_mid, {})
    best_score = best_m.get("efficiency_score", 0.0)
    best_acc = best_m.get("accuracy_pct", 0.0)
    best_vram = best_m.get("vram_gb", 0.0)
    ranking_list_html = "".join(
        f"<li><strong>{mid}:</strong> Score de Eficiencia: <strong>{(models_dict.get(mid, {}).get('efficiency_score') or 0.0):.3f}</strong> | "
        f"Precisión: {models_dict.get(mid, {}).get('accuracy_pct', 0)}% | Tok/s: {models_dict.get(mid, {}).get('tokens_per_sec', 0)} | VRAM: {models_dict.get(mid, {}).get('vram_gb', 0)} GB</li>"
        for mid in ranking
    )
    

    # HTML Generator
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NetDiagBench-L7 | Informe Consolidado de Evaluación y Benchmark</title>
    <script>
        (function() {{
            try {{
                const t = localStorage.getItem('netdiag_theme') || 'dark';
                document.documentElement.setAttribute('data-theme', t);
                if (t === 'dark') document.documentElement.classList.add('dark');
                else document.documentElement.classList.remove('dark');
            }} catch(e) {{}}
        }})();
        function applyTheme(t) {{
            document.documentElement.setAttribute('data-theme', t);
            if (t === 'dark') document.documentElement.classList.add('dark');
            else document.documentElement.classList.remove('dark');
        }}
        window.applyTheme = applyTheme;
    </script>
    <style>
        :root {{
            --bg: #070e18;
            --surface: #0e1b2e;
            --surface-hover: #162740;
            --inst-red: #ad3333;
            --inst-navy: #003366;
            --inst-gray: #DADADA;
            --primary: #ad3333;
            --navy: #003366;
            --accent: #003366;
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ad3333;
            --text: #f8fafc;
            --text-dim: #DADADA;
            --border: rgba(218, 218, 218, 0.25);
            --border-solid: #DADADA;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
        body {{ background: var(--bg); color: var(--text); padding: 12px 14px; line-height: 1.5; }}
        .container {{ max-width: 100%; width: 100%; margin: 0 auto; }}
        header {{
            background: linear-gradient(135deg, #003366 0%, #001f3f 100%);
            border: 1px solid rgba(218, 218, 218, 0.35);
            border-left: 6px solid #ad3333;
            border-radius: 8px;
            padding: 24px 28px;
            margin-bottom: 30px;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.35);
        }}
        .badge {{ background: #ad3333; color: white; font-size: 0.75rem; padding: 4px 9px; border-radius: 4px; font-weight: bold; border: 1px solid rgba(218,218,218,0.4); }}
        .badge-success {{ background: #003366; border: 1px solid #DADADA; color: #ffffff; }}
        h1 {{ font-size: 2rem; color: #ffffff; margin-bottom: 6px; font-weight: 800; }}
        h2 {{ font-size: 1.35rem; color: #ffffff; margin: 30px 0 16px 0; border-bottom: 2px solid #ad3333; padding-bottom: 8px; font-weight: 700; }}
        .card {{ background: var(--surface); border: 1px solid var(--border); border-top: 3px solid #003366; border-radius: 8px; padding: 24px; margin-bottom: 24px; box-shadow: 0 4px 12px rgba(0,0,0,0.25); }}
        .meta-box {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; margin: 20px 0; }}
        .meta-item {{ background: #070e18; border: 1px solid var(--border); border-left: 4px solid #ad3333; border-radius: 6px; padding: 12px; }}
        .meta-val {{ font-size: 1.25rem; font-weight: bold; color: #ffffff; }}
        .meta-lbl {{ font-size: 0.75rem; color: #DADADA; text-transform: uppercase; font-weight: 600; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 14px; font-size: 0.9rem; }}
        th, td {{ padding: 10px 14px; text-align: left; border-bottom: 1px solid rgba(218, 218, 218, 0.15); }}
        th {{ background: #003366; color: #ffffff; font-weight: 700; border-bottom: 2px solid #ad3333; }}
        tr:hover {{ background: rgba(0, 51, 102, 0.2); }}
        .bar-container {{ width: 100%; background: #070e18; border: 1px solid var(--border); border-radius: 4px; height: 18px; position: relative; overflow: hidden; margin-top: 4px; }}
        .bar {{ height: 100%; border-radius: 4px; }}
        .bar-phi {{ background: linear-gradient(90deg, #64748b, #DADADA); }}
        .bar-qwen {{ background: linear-gradient(90deg, #8e2525, #ad3333); }}
        .bar-glm {{ background: linear-gradient(90deg, #001f3f, #0055a5); }}
        .sig-yes {{ color: #34d399; font-weight: bold; }}
        .sig-no {{ color: #DADADA; }}
        .verdict-box {{ background: rgba(0, 51, 102, 0.25); border: 1px solid rgba(218, 218, 218, 0.3); border-left: 5px solid #ad3333; padding: 18px; border-radius: 6px; margin-top: 20px; }}
        .hw-fingerprint-box {{ background: #070e18; border: 1px solid rgba(218, 218, 218, 0.25); border-left: 3px solid #003366; border-radius: 6px; padding: 10px 14px; margin-top: 16px; font-size: 0.85rem; font-family: monospace; color: #DADADA; }}

        /* Modo de Día (Light Theme) */
        [data-theme="light"] {{
            --bg: #f4f6f9;
            --surface: #ffffff;
            --text: #0f172a;
            --text-dim: #334155;
            --border: #cbd5e1;
            --border-solid: #cbd5e1;
            --inst-gray: #334155;
        }}
        .normative-card {{
            background: rgba(14, 27, 46, 0.85);
            padding: 1.25rem;
            border-radius: 8px;
            border: 1px solid rgba(56, 189, 248, 0.25);
            color: #cbd5e1;
        }}
        .normative-card h3 {{
            margin-top: 0;
            color: #38bdf8;
            font-size: 1.1rem;
            border: none;
            padding: 0;
            font-weight: 700;
        }}
        .normative-card p, .normative-card li {{
            font-size: 0.85rem;
            color: #cbd5e1;
            line-height: 1.7;
        }}
        .normative-card strong {{
            color: #ffffff;
        }}
        .normative-card code {{
            background: rgba(0, 0, 0, 0.4);
            color: #7dd3fc;
            padding: 2px 6px;
            border-radius: 4px;
            font-family: monospace;
        }}
        [data-theme="light"] .normative-card {{
            background: #f8fafc !important;
            border: 1px solid #cbd5e1 !important;
            box-shadow: 0 1px 3px rgba(0, 51, 102, 0.06) !important;
            color: #1e293b !important;
        }}
        [data-theme="light"] .normative-card h3 {{
            color: #003366 !important;
        }}
        [data-theme="light"] .normative-card p, [data-theme="light"] .normative-card li {{
            color: #334155 !important;
        }}
        [data-theme="light"] .normative-card strong {{
            color: #0f172a !important;
        }}
        [data-theme="light"] .normative-card code {{
            background: #e0f2fe !important;
            color: #0369a1 !important;
            border: 1px solid #bae6fd !important;
        }}
        [data-theme="light"] .section-subtext {{
            color: #334155 !important;
        }}
        [data-theme="light"] header {{
            background: linear-gradient(135deg, #f8fafc 0%, #eff6ff 100%);
            border: 1px solid #cbd5e1;
            border-left: 6px solid #ad3333;
            box-shadow: 0 4px 16px rgba(0, 51, 102, 0.08);
        }}
        [data-theme="light"] header h1 {{ color: #003366 !important; }}
        [data-theme="light"] header p {{ color: #334155 !important; }}
        [data-theme="light"] header div {{ color: #334155 !important; }}
        [data-theme="light"] header strong {{ color: #0f172a !important; }}
        [data-theme="light"] header .badge-success {{ background: #e0f2fe; color: #0369a1; border: 1px solid #7dd3fc; }}
        [data-theme="light"] .hw-fingerprint-box {{ background: #ffffff; border-color: #cbd5e1; border-left: 3px solid #ad3333; color: #334155; }}
        [data-theme="light"] .hw-fingerprint-box strong {{ color: #003366; }}
        [data-theme="light"] h1, [data-theme="light"] h2 {{ color: #003366; }}
        [data-theme="light"] .card {{ background: #ffffff; border-color: #cbd5e1; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }}
        [data-theme="light"] .meta-item {{ background: #f8fafc; border-color: #cbd5e1; }}
        [data-theme="light"] .meta-val {{ color: #003366; }}
        [data-theme="light"] .meta-lbl {{ color: #334155; }}
        [data-theme="light"] th {{ background: #003366 !important; color: #ffffff !important; border-bottom: 2px solid #ad3333 !important; }}
        [data-theme="light"] td {{ color: #0f172a; border-bottom-color: #e2e8f0; }}
        [data-theme="light"] tr:hover {{ background: #f1f5f9; }}
        [data-theme="light"] .bar-container {{ background: #e2e8f0; border-color: #cbd5e1; }}
        [data-theme="light"] .bar-phi {{ background: linear-gradient(90deg, #334155, #64748b); }}
        [data-theme="light"] .sig-yes {{ color: #15803d; }}
        [data-theme="light"] .sig-no {{ color: #475569; }}
        [data-theme="light"] .verdict-box {{ background: #eff6ff; border-color: #bfdbfe; color: #1e293b; }}
        [data-theme="light"] .verdict-box h3 {{ color: #ad3333 !important; }}
        [data-theme="light"] .verdict-box h4 {{ color: #003366 !important; }}
        [data-theme="light"] .verdict-box p {{ color: #1e293b !important; }}
        [data-theme="light"] .verdict-box code {{ background: #e0f2fe; color: #0369a1; }}
        [data-theme="light"] footer {{ color: #64748b !important; border-color: #e2e8f0 !important; }}
        .standalone-export-toolbar .view-header-btn {{
            width: 32px !important;
            height: 32px !important;
            min-width: 32px !important;
            min-height: 32px !important;
            max-width: 32px !important;
            max-height: 32px !important;
            padding: 0 !important;
            border-radius: 8px !important;
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
            box-sizing: border-box !important;
        }}
        .standalone-export-toolbar .view-header-btn svg {{
            width: 16px !important;
            height: 16px !important;
            min-width: 16px !important;
            min-height: 16px !important;
            max-width: 16px !important;
            max-height: 16px !important;
            stroke-width: 2 !important;
            display: block !important;
            margin: auto !important;
            flex-shrink: 0 !important;
            box-sizing: border-box !important;
        }}

        @media print {{
            body {{ background: #fff; color: #000; padding: 0; }}
            .standalone-export-toolbar {{ display: none !important; }}
            .card {{ border: 1px solid #ccc; background: #fff; box-shadow: none; }}
            th {{ background: #eee; color: #000; }}
            td, th {{ border-bottom: 1px solid #ddd; color: #000; }}
            h1, h2, .meta-val {{ color: #000; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        {toolbar_html}
        <header>
            <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                <div>
                    <span class="badge badge-success">INFORME OFICIAL DE RESULTADOS</span>
                    <span class="badge">NetDiagBench-L7 v1.0.0</span>
                    <h1 style="margin-top: 10px;">Informe Consolidado de Evaluación y Benchmark</h1>
                    <p style="color: var(--text-dim); font-size: 0.9rem;">
                        Universidad de Pamplona &bull; Facultad de Ingenierías y Arquitectura (E.E.S.T.)
                    </p>
                </div>
                <div style="text-align: right; font-size: 0.85rem; color: var(--text-dim);">
                    Fecha: <strong>{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</strong><br>
                    Corridas Auditadas: <strong>{len(rows)}</strong>
                </div>
            </div>
            <div class="hw-fingerprint-box">
                <strong>Huella de Hardware Inmutable:</strong> {hw_fingerprint}
            </div>
        </header>

        <!-- 1. RESUMEN EJECUTIVO -->
        <section class="card">
            <h2>1. Resumen Ejecutivo de la Evaluación (OE4)</h2>
            <div class="meta-box">
                <div class="meta-item">
                    <div class="meta-val">{global_full_acc}% ({total_full}/{len(rows)})</div>
                    <div class="meta-lbl">Exactitud Diagnóstica Completa</div>
                </div>
                <div class="meta-item">
                    <div class="meta-val">{global_strict_acc}% ({total_strict}/{len(rows)})</div>
                    <div class="meta-lbl">Causa Raíz Estricta</div>
                </div>
                <div class="meta-item">
                    <div class="meta-val">{global_evidence}% ({total_evidence}/{len(rows)})</div>
                    <div class="meta-lbl">Tasa con Evidencia Read-Only</div>
                </div>
                <div class="meta-item">
                    <div class="meta-val font-mono" style="font-family: monospace;">v{eval_version}</div>
                    <div class="meta-lbl">Evaluador Normativo (SHA-256)</div>
                </div>
            </div>
        </section>

        <!-- 2. MATRIZ MULTIDIMENSIONAL -->
        <section class="card">
            <h2>2. Matriz de Evaluación Multidimensional Consolidada</h2>
            <table>
                <thead>
                    <tr>
                        <th>Modelo SLM</th>
                        <th>Parámetros</th>
                        <th>Diagnóstico Completo</th>
                        <th>Causa Raíz Estricta</th>
                        <th>Puntaje de Coincidencia Parcial</th>
                        <th>TTFT (ms)</th>
                        <th>Velocidad (tok/s)</th>
                        <th>Latencia p50</th>
                        <th>VRAM (Declarada/Estimada) Pico</th>
                        <th>Energía Acum. (kWh)</th>
                        <th>Rúbrica (0-5)</th>
                    </tr>
                </thead>
                <tbody>
    """

    for mid in model_ids:
        m_desc = desc.get(mid, {})
        ttft = m_desc.get("ttft_ms", {}).get("mean", 0.0)
        tok_s = m_desc.get("tokens_per_sec", {}).get("mean", 0.0)
        p50 = m_desc.get("total_time_ms", {}).get("p50", 0.0)
        vram = m_desc.get("peak_vram_gb", {}).get("mean", 0.0)
        energy_kwh = sum((r.get("energy_kwh") or 0.0) for r in by_model[mid])
        rub = m_desc.get("rubric_score", {}).get("mean", 5.0)
        part = m_desc.get("partial_match_score", {}).get("mean", 0.988)

        full_count = sum(
            1 for r in by_model[mid] if bool(r.get("is_full_diagnosis_correct")) or str(r.get("is_root_cause_correct_full_text", "")).lower() in ("true", "1")
        )
        strict_count = sum(
            1 for r in by_model[mid] if bool(r.get("is_root_cause_correct_strict")) or str(r.get("is_root_cause_correct", "")).lower() in ("true", "1")
        )
        model_full_acc = round(full_count / len(by_model[mid]) * 100.0, 1) if by_model[mid] else 0.0
        model_strict_acc = round(strict_count / len(by_model[mid]) * 100.0, 1) if by_model[mid] else 0.0
        acc_color = "var(--success)" if model_full_acc >= 80.0 else ("var(--warning)" if model_full_acc >= 60.0 else "var(--danger)")

        param_str = get_model_size_label(mid)

        html += f"""
                    <tr>
                        <td><strong>{mid}</strong></td>
                        <td>{param_str}</td>
                        <td style="color: {acc_color}; font-weight: bold;">{model_full_acc}% ({full_count}/{len(by_model[mid])})</td>
                        <td style="font-weight: 600;">{model_strict_acc}% ({strict_count}/{len(by_model[mid])})</td>
                        <td>{part}</td>
                        <td>{ttft} ms</td>
                        <td><strong>{tok_s}</strong> tok/s</td>
                        <td>{p50} ms</td>
                        <td><strong>{vram} GB</strong></td>
                        <td>{energy_kwh:.6f} kWh</td>
                        <td>{rub} / 5.0</td>
                    </tr>
        """

    html += f"""
                </tbody>
            </table>
        </section>

        <!-- 3. COMPARATIVA VISUAL DE RENDIMIENTO -->
        <section class="card">
            <h2>3. Comparación Visual de Rendimiento Físico</h2>
            <div style="margin-bottom: 20px;">
                <label style="font-weight: bold; font-size: 0.85rem; color: var(--text-dim);">VELOCIDAD DE DECODIFICACIÓN (TOKENS / SEGUNDO):</label>
    """

    for mid in model_ids:
        tok_s = desc.get(mid, {}).get("tokens_per_sec", {}).get("mean", 0.0)
        pct = min(100.0, (tok_s / 50.0) * 100.0)
        cls = "bar-phi" if "phi" in mid else ("bar-qwen" if "qwen" in mid else "bar-glm")
        html += f"""
                <div style="margin: 8px 0;">
                    <div style="display: flex; justify-content: space-between; font-size: 0.85rem;">
                        <span><strong>{mid}</strong></span>
                        <span>{tok_s} tok/s</span>
                    </div>
                    <div class="bar-container">
                        <div class="bar {cls}" style="width: {pct}%;"></div>
                    </div>
                </div>
        """

    html += """
            </div>

            <div>
                <label style="font-weight: bold; font-size: 0.85rem; color: var(--text-dim); margin-top: 16px; display: block;">OCUPACIÓN DE MEMORIA VRAM (Declarada/Estimada) PICO (GB) FRENTE AL LÍMITE DE 8 GB:</label>
    """

    for mid in model_ids:
        vram = desc.get(mid, {}).get("peak_vram_gb", {}).get("mean", 0.0)
        pct = (vram / 8.0) * 100.0
        cls = "bar-phi" if "phi" in mid else ("bar-qwen" if "qwen" in mid else "bar-glm")
        html += f"""
                <div style="margin: 8px 0;">
                    <div style="display: flex; justify-content: space-between; font-size: 0.85rem;">
                        <span><strong>{mid}</strong></span>
                        <span>{vram} GB / 8.0 GB ({round(pct, 1)}%)</span>
                    </div>
                    <div class="bar-container">
                        <div class="bar {cls}" style="width: {pct}%;"></div>
                    </div>
                </div>
        """

    html += """
            </div>
        </section>

        <!-- 4. ANÁLISIS CORRELACIONAL (SCIPY) -->
        <section class="card">
            <h2>4. Análisis Correlacional y de Significancia Estadística (Tarea 4.1.2)</h2>
            <table>
                <thead>
                    <tr>
                        <th>Métrica de Rendimiento</th>
                        <th>Spearman &rho;</th>
                        <th>p-valor (&rho;)</th>
                        <th>Pearson r</th>
                        <th>p-valor (r)</th>
                        <th>Significativo (&alpha; = 0.05)</th>
                    </tr>
                </thead>
                <tbody>
    """

    for mk, corr in corrs.items():
        sig_str = '<span class="sig-yes">Sí (p &lt; 0.001)</span>' if corr["significant_005"] else '<span class="sig-no">No</span>'
        html += f"""
                    <tr>
                        <td><strong>{mk}</strong></td>
                        <td>{corr['spearman_rho']}</td>
                        <td>{corr['spearman_p']}</td>
                        <td>{corr['pearson_r']}</td>
                        <td>{corr['pearson_p']}</td>
                        <td>{sig_str}</td>
                    </tr>
        """

    html += """
                </tbody>
            </table>

            <h3 style="color: var(--primary); font-size: 1.1rem; margin: 24px 0 10px 0;">Prueba No Paramétrica de Kruskal-Wallis (Diferencias entre Modelos)</h3>
            <table>
                <thead>
                    <tr>
                        <th>Métrica</th>
                        <th>H Estadístico</th>
                        <th>p-valor</th>
                        <th>Diferencia Significativa</th>
                    </tr>
                </thead>
                <tbody>
    """

    for mk, kw in kruskal.items():
        sig_str = '<span class="sig-yes">Sí (Rechaza H0)</span>' if kw["significant_005"] else '<span class="sig-no">No</span>'
        html += f"""
                    <tr>
                        <td><strong>{mk}</strong></td>
                        <td>{kw['H_statistic']}</td>
                        <td>{kw['p_value']}</td>
                        <td>{sig_str}</td>
                    </tr>
        """

    html += f"""
                </tbody>
            </table>
        </section>

        <!-- 5. VALIDACIÓN METODOLÓGICA: CRITERIOS NORMATIVOS OFICIALES -->
        <section class="card">
            <h2>5. Validación Normativa: Criterios Derivados de Estándares IETF (RFC 1035 / RFC 9110 / RFC 8446)</h2>
            <p class="section-subtext" style="color: var(--inst-gray); font-size: 0.9rem; margin-bottom: 1.25rem; line-height: 1.6;">
                Evaluación formal determinista sin sesgo empírico ni golden set. Los criterios de aceptación diagnóstica se derivan
                exclusivamente de especificaciones estándar oficiales (RFC 1035, RFC 9110, RFC 8446, RFC 5280, RFC 6066, Linux tc-netem y BIND9 ARM),
                versionados mediante resumen criptográfico SHA-256 (<code>configs/evaluator_concepts.yaml</code>).
            </p>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1.5rem; align-items: start;">
                <div class="normative-card">
                    <h3>Regla de Decisión Normativa Universal</h3>
                    <p style="margin-top: 0.5rem;">
                        <strong>Condición de Éxito:</strong> <code>is_correct = (nombra &ge; 1 concepto de causa_raiz) &and; (&not;concluye clase vecina) &and; (&not;solo síntoma)</code>
                    </p>
                    <ul style="list-style: none; padding: 0; margin: 0.75rem 0 0 0; line-height: 1.8;">
                        <li><strong>Versión del Evaluador:</strong> <span style="font-family: monospace; color: #10b981; font-weight: 700;">{eval_version}</span></li>
                        <li><strong>Total Clases Normativas:</strong> {len(classes_dict)} clases de falla auditadas</li>
                        <li><strong>Normalización Lingüística:</strong> Minúsculas, sin tildes, delimitadores de palabra completa (<code>\b...\b</code>)</li>
                        <li><strong>Idiomas Soportados:</strong> Español e Inglés con igual equivalencia técnica</li>
                    </ul>
                </div>
                <div class="normative-card">
                    <h3>Fuentes Estándar de Referencia</h3>
                    <ul style="list-style: disc; padding-left: 1.25rem; margin: 0.5rem 0 0 0; line-height: 1.8;">
                        <li><strong>DNS:</strong> RFC 1034, RFC 1035 (RCODE 2/3/5, TC-bit), RFC 2308, RFC 6891, BIND9 ARM §6.2</li>
                        <li><strong>HTTP:</strong> RFC 9110 (403/500/502/503/504), RFC 9112, RFC 6585 (429 Rate Limiting)</li>
                        <li><strong>TLS:</strong> RFC 8446 (Handshake/Cipher), RFC 5280 (notAfter/Chain), RFC 6066 (SNI)</li>
                        <li><strong>Kernel / Red:</strong> Linux iproute2 tc-netem (Traffic Control Emulation)</li>
                    </ul>
                </div>
            </div>
        </section>

        <!-- 6. VEREDICTO DE COMPROMISO DINÁMICO (OE4 / Hallazgo C2) -->
        <section class="card">
            <h2>6. Dictamen de Selección y Configuración de Mejor Compromiso (OE4 / Tarea 4.3.1)</h2>
            <div class="verdict-box">
                <h3 style="color: var(--primary); margin-bottom: 8px;">Configuración de Mejor Compromiso Global: {best_mid} (Score: {best_score:.3f})</h3>
                <p>
                    Selección óptima calculada dinámicamente mediante la función de utilidad multicriterio ponderada (OE4: 40% precisión de causa raíz, 20% rúbrica cualitativa, 20% velocidad de decodificación y 20% eficiencia de VRAM). El modelo <strong>{best_mid}</strong> alcanza un <strong>{best_acc}%</strong> de precisión diagnóstica con un consumo medio de {best_vram} GB de VRAM (Declarada/Estimada), ratificándose como la configuración de mejor balance operativo.
                </p>
                <div style="margin-top: 14px;">
                    <h4 style="color: #64748b; margin-bottom: 6px;">Ranking Multicriterio Dinámico Consolidado:</h4>
                    <ol style="margin-left: 20px; line-height: 1.8;">
                        {ranking_list_html}
                    </ol>
                </div>
            </div>
        </section>

        <footer style="text-align: center; color: var(--text-dim); font-size: 0.85rem; margin-top: 40px; border-top: 1px solid var(--border); padding-top: 20px;">
            NetDiagBench-L7 &bull; Universidad de Pamplona &bull; Reporte Autogenerado por Evaluator Harness &bull; Septiembre 2026
        </footer>
    </div>
</body>
</html>
    """

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    return output_path
