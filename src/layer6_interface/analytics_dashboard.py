"""
NetDiagBench-L7: Layer 6 - Dashboard Analitico (OE4 + Tarea 4.1.2)
Dashboard visual 100% autonomo (SVG + JavaScript nativo, sin CDNs ni dependencias externas)
que presenta:
  - Informe Tecnico Comparativo y Matriz Multidimensional (OE4 / Tareas 4.2.2 y 4.3.1)
  - Analisis Correlacional y Significancia Estadistica (Tarea 4.1.2 / SciPy)

Consume los endpoints ``/api/comparative-report`` y ``/api/correlation-analysis``.
Se sirve en la ruta ``/analitica`` del dashboard FastAPI.
"""

ANALYTICS_DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>NetDiagBench-L7 | Informe Técnico Comparativo (OE4) &bull; Análisis Correlacional (Tarea 4.1.2)</title>
<script>
    (function() {
        try {
            const savedTheme = localStorage.getItem('netdiag_theme') || 'dark';
            document.documentElement.setAttribute('data-theme', savedTheme);
            if (savedTheme === 'dark') {
                document.documentElement.classList.add('dark');
            } else {
                document.documentElement.classList.remove('dark');
            }
        } catch(e) {}
    })();
</script>
<style>
    :root {
        --bg: #070e18; --surface: #0e1b2e; --surface2: #070e18; --border: rgba(218, 218, 218, 0.22);
        --inst-red: #ad3333; --inst-navy: #003366; --inst-gray: #DADADA;
        --primary: #ad3333; --accent: #003366; --success: #10b981; --warning: #f59e0b;
        --danger: #ad3333; --teal: #003366; --text: #f8fafc; --text-dim: #DADADA;
        --scrollbar-track: transparent;
        --scrollbar-thumb: rgba(148, 163, 184, 0.22);
        --scrollbar-thumb-hover: rgba(148, 163, 184, 0.42);
    }
    /* 1. Compatibilidad Firefox (W3C Standard) */
    * {
        scrollbar-width: thin;
        scrollbar-color: var(--scrollbar-thumb) var(--scrollbar-track);
    }
    /* 2. Compatibilidad WebKit (Chrome, Edge, Safari, Opera) */
    ::-webkit-scrollbar {
        width: 6px;
        height: 6px;
    }
    ::-webkit-scrollbar-track {
        background: var(--scrollbar-track);
    }
    ::-webkit-scrollbar-thumb {
        background-color: var(--scrollbar-thumb);
        border-radius: 10px;
        border: 1px solid transparent;
        background-clip: padding-box;
        transition: background-color 0.2s ease-in-out;
    }
    ::-webkit-scrollbar-thumb:hover {
        background-color: var(--scrollbar-thumb-hover);
    }
    ::-webkit-scrollbar-corner {
        background: transparent;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    body { background: var(--bg); color: var(--text); padding: 8px 12px; line-height: 1.5; }
    .container { max-width: 100%; width: 100%; margin: 0 auto; }
    header, .tabs, .hdr-actions { display: none !important; }
    h1 { font-size: 1.55rem; color: #ffffff; font-weight: 800; }
    .sub { color: #DADADA; font-size: 0.85rem; margin-top: 4px; }
    .btn { background: #003366; color: #ffffff; border: 1px solid #DADADA; padding: 8px 14px; border-radius: 6px;
           font-size: 0.82rem; font-weight: 600; cursor: pointer; text-decoration: none; transition: all 0.2s; }
    .btn:hover { background: #004080; border-color: #ffffff; }
    .panel { display: none; }
    .panel.active { display: block; }
    .kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; margin-bottom: 20px; }
    .kpi { background: var(--surface); border: 1px solid var(--border); border-left: 3px solid #003366; border-radius: 8px; padding: 14px 16px; }
    .kpi .v { font-size: 1.55rem; font-weight: 800; color: #ffffff; }
    .kpi .l { font-size: 0.72rem; text-transform: uppercase; letter-spacing: .04em; color: #DADADA; font-weight: 600; }
    .card { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 18px 20px; margin-bottom: 20px; box-shadow: 0 4px 12px rgba(0,0,0,0.2); }
    .card h2 { font-size: 1.05rem; color: #ffffff; margin-bottom: 4px; font-weight: 700; }
    .card .desc { font-size: 0.8rem; color: #DADADA; margin-bottom: 14px; }
    .card.comp { border-top: 3px solid #ad3333; }
    .card.corr { border-top: 3px solid #003366; }
    .grid2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(440px, 1fr)); gap: 20px; }
    .grid3 { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; }
    .grid4 { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 16px; }
    .chart-card { background: var(--surface2); border: 1px solid var(--border); border-radius: 8px; padding: 12px 14px; }
    .chart-title { font-size: 0.85rem; font-weight: 700; color: #ffffff; margin-bottom: 6px; display: flex; justify-content: space-between; gap: 8px; }
    .hint { font-size: 0.7rem; font-weight: 500; color: #DADADA; }
    svg.chart { width: 100%; height: auto; display: block; }
    svg text { fill: #DADADA; font-size: 11px; }
    svg text.dim { fill: #94a3b8; font-size: 10px; }
    svg text.val { fill: #ffffff; font-weight: 700; font-size: 11px; }
    svg text.lim { fill: var(--danger); font-size: 10px; font-weight: 700; }
    .model-card { background: var(--surface2); border: 1px solid var(--border); border-radius: 10px; padding: 16px; position: relative; }
    .model-card .rank { position: absolute; top: 12px; right: 14px; font-size: 0.75rem; color: #DADADA; font-weight: 700; }
    .model-card h3 { font-size: 1.05rem; display: flex; align-items: center; gap: 8px; color: #ffffff; }
    .dot { width: 12px; height: 12px; border-radius: 50%; display: inline-block; flex: none; }
    .role { display: inline-block; font-size: 0.7rem; font-weight: 700; padding: 2px 8px; border-radius: 4px; margin: 6px 0 10px; }
    .mstats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin: 12px 0; }
    .mstat { background: var(--bg); border: 1px solid var(--border); border-radius: 6px; padding: 8px; text-align: center; }
    .mstat b { display: block; font-size: 1rem; color: #ffffff; }
    .mstat span { font-size: 0.65rem; color: #DADADA; text-transform: uppercase; }
    .mdesc { font-size: 0.78rem; color: #cbd5e1; }
    .score-wrap { display: flex; align-items: center; gap: 14px; }
    .badge-rec { display: inline-block; font-size: 0.68rem; font-weight: 800; padding: 3px 8px; border-radius: 4px; margin-left: 4px; border: 1px solid #DADADA; }
    table.t { width: 100%; border-collapse: collapse; font-size: 0.8rem; }
    table.t th { text-align: left; background: #003366; color: #ffffff; font-weight: 700; font-size: 0.72rem; text-transform: uppercase;
                 border-bottom: 2px solid #ad3333; padding: 8px 8px; white-space: nowrap; }
    table.t td { border-bottom: 1px solid rgba(218, 218, 218, 0.15); padding: 8px 8px; white-space: nowrap; color: #f8fafc; }
    table.t tr:hover td { background: rgba(0, 51, 102, 0.2); }
    td.best { color: #ffffff; font-weight: 800; background: rgba(0, 51, 102, 0.35); }
    .table-wrap { overflow-x: auto; }
    .pill { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 0.7rem; font-weight: 800; }
    .pill.ok { background: rgba(16,185,129,0.18); color: #34d399; border: 1px solid rgba(16,185,129,0.4); }
    .pill.no { background: rgba(218,218,218,0.12); color: #DADADA; border: 1px solid rgba(218,218,218,0.3); }
    .pill.warn { background: rgba(245,158,11,0.15); color: #fbbf24; border: 1px solid rgba(245,158,11,0.4); }
    .pill.bad { background: rgba(173,51,51,0.2); color: #f87171; border: 1px solid rgba(173,51,51,0.5); }
    .heat td.cell { text-align: center; font-weight: 800; border: 2px solid var(--surface); border-radius: 4px; }
    .legend { display: flex; flex-wrap: wrap; gap: 14px; font-size: 0.78rem; color: #DADADA; margin-top: 8px; }
    .legend span { display: inline-flex; align-items: center; gap: 6px; cursor: pointer; user-select: none; }
    .legend span.off { opacity: 0.35; }
    .concl { border-left: 4px solid; background: var(--surface2); border: 1px solid var(--border); border-left-width: 4px; border-radius: 6px; padding: 14px 16px; }
    .concl h4 { font-size: 0.92rem; margin-bottom: 6px; }
    .concl p { font-size: 0.82rem; color: #cbd5e1; }
    .finding { display: flex; gap: 10px; align-items: flex-start; background: var(--surface2); border: 1px solid var(--border);
               border-radius: 8px; padding: 12px 14px; font-size: 0.83rem; margin-bottom: 10px; }
    .finding .ic { font-size: 1.1rem; line-height: 1.2; }
    select.sel { background: var(--bg); color: var(--text); border: 1px solid var(--border); padding: 6px 10px; border-radius: 6px; font-size: 0.8rem; }
    details.src { margin-top: 6px; }
    details.src summary { cursor: pointer; color: #DADADA; font-size: 0.8rem; font-weight: 600; }
    details.src pre { white-space: pre-wrap; word-break: break-all; overflow-wrap: anywhere; font-family: Consolas, monospace; font-size: 0.78rem; color: #cbd5e1; background: var(--bg);
                      padding: 14px; border-radius: 6px; margin-top: 10px; max-height: 420px; overflow: auto; border: 1px solid var(--border); }
    .loading { color: #DADADA; padding: 40px; text-align: center; }
    .err { color: var(--danger); padding: 20px; }
    .minibar { position: relative; height: 10px; background: var(--bg); border-radius: 5px; min-width: 120px; }
    .minibar i { position: absolute; top: 0; height: 10px; border-radius: 5px; }
    .minibar .mid { position: absolute; left: 50%; top: -2px; width: 1px; height: 14px; background: #DADADA; }
    footer { color: #DADADA; font-size: 0.75rem; text-align: center; margin-top: 20px; padding: 14px; border-top: 1px solid var(--border); }

    /* ================= MODO DE DÍA (LIGHT THEME) ================= */
    [data-theme="light"] {
        --bg: #f4f6f9;
        --surface: #ffffff;
        --surface2: #f8fafc;
        --border: #cbd5e1;
        --text: #0f172a;
        --text-dim: #334155;
        --scrollbar-track: transparent;
        --scrollbar-thumb: rgba(71, 85, 105, 0.25);
        --scrollbar-thumb-hover: rgba(71, 85, 105, 0.45);
    }
    [data-theme="light"] .kpi { background: #ffffff !important; border: 1px solid #cbd5e1 !important; border-left: 4px solid #003366 !important; box-shadow: 0 1px 3px rgba(0,51,102,0.08) !important; }
    [data-theme="light"] .kpi .v { color: #003366 !important; font-weight: 800 !important; }
    [data-theme="light"] .kpi .l { color: #334155 !important; font-weight: 700 !important; }
    [data-theme="light"] .card { background: #ffffff !important; border: 1px solid #cbd5e1 !important; box-shadow: 0 1px 3px rgba(0,0,0,0.05) !important; }
    [data-theme="light"] .card h2 { color: #003366 !important; font-weight: 800 !important; }
    [data-theme="light"] .card .desc { color: #334155 !important; font-weight: 500 !important; }
    [data-theme="light"] .chart-card { background: #ffffff !important; border: 1px solid #cbd5e1 !important; box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important; }
    [data-theme="light"] .chart-title { color: #003366 !important; font-weight: 800 !important; }
    [data-theme="light"] .hint { color: #475569 !important; font-weight: 600 !important; }
    [data-theme="light"] .legend { color: #1e293b !important; font-weight: 600 !important; }
    [data-theme="light"] svg text { fill: #1e293b; font-weight: 500; }
    [data-theme="light"] svg text.dim { fill: #475569; font-weight: 600; }
    [data-theme="light"] svg text.val { fill: #0f172a; font-weight: 700; }
    [data-theme="light"] svg text.lim { fill: #b91c1c; font-weight: 700; }
    [data-theme="light"] .model-card { background: #ffffff !important; border: 1px solid #cbd5e1 !important; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
    [data-theme="light"] .model-card h3 { color: #003366 !important; font-weight: 800 !important; }
    [data-theme="light"] .model-card .rank { color: #475569 !important; font-weight: 700 !important; }
    [data-theme="light"] .mstat { background: #f8fafc !important; border: 1px solid #cbd5e1 !important; }
    [data-theme="light"] .mstat b { color: #0f172a !important; font-weight: 800 !important; }
    [data-theme="light"] .mstat span { color: #334155 !important; font-weight: 700 !important; }
    [data-theme="light"] .mdesc { color: #334155 !important; font-weight: 500 !important; }
    [data-theme="light"] .model-selection-bar { background-color: #ffffff; border: 1px solid #cbd5e1; border-left: 4px solid #ad3333 !important; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }
    [data-theme="light"] .ms-title { color: #0f172a !important; }
    [data-theme="light"] .ms-sub { color: #475569 !important; font-weight: 500 !important; }
    [data-theme="light"] #hwInfo { color: #475569 !important; font-weight: 600 !important; }
    [data-theme="light"] .btn:not(.btn-apply):not(.btn-danger) { background: #f8fafc !important; color: #1e293b !important; border: 1px solid #cbd5e1 !important; font-weight: 600 !important; }
    [data-theme="light"] .btn:not(.btn-apply):not(.btn-danger):hover { background: #e2e8f0 !important; color: #003366 !important; border-color: #003366 !important; }
    [data-theme="light"] .ms-chip { background-color: #f1f5f9; color: #0f172a; border: 1px solid #cbd5e1; }
    [data-theme="light"] .ms-chip.active { background-color: #eff6ff !important; border-color: #003366 !important; color: #003366 !important; font-weight: 700; box-shadow: 0 0 6px rgba(0, 51, 102, 0.15); }
    [data-theme="light"] .ms-chip .runs-badge { background: #e2e8f0; color: #334155; font-weight: 600; }
    [data-theme="light"] table.t th { background: #003366 !important; color: #ffffff !important; font-weight: 700 !important; border-bottom: 2px solid #ad3333 !important; }
    [data-theme="light"] table.t td { color: #0f172a !important; border-bottom-color: #e2e8f0 !important; font-weight: 500 !important; }
    [data-theme="light"] table.t tr:hover td { background: #f1f5f9 !important; }
    [data-theme="light"] td.best { color: #003366 !important; background: #e0f2fe !important; font-weight: 800 !important; }
    [data-theme="light"] .minibar { background: #e2e8f0 !important; }
    [data-theme="light"] .minibar .mid { background: #64748b !important; }
    [data-theme="light"] .pill.no { background: #f1f5f9 !important; color: #334155 !important; border: 1px solid #cbd5e1 !important; }
    [data-theme="light"] .pill.ok { background: #dcfce7 !important; color: #15803d !important; border: 1px solid #86efac !important; }
    [data-theme="light"] .pill.warn { background: #fef3c7 !important; color: #b45309 !important; border: 1px solid #fcd34d !important; }
    [data-theme="light"] .pill.bad { background: #fee2e2 !important; color: #b91c1c !important; border: 1px solid #fca5a5 !important; }
    [data-theme="light"] .tab { background: #ffffff !important; color: #334155 !important; border: 1px solid #cbd5e1 !important; font-weight: 700 !important; box-shadow: 0 1px 3px rgba(0,0,0,0.05) !important; }
    [data-theme="light"] .tab:hover { background: #f1f5f9 !important; color: #003366 !important; border-color: #003366 !important; }
    [data-theme="light"] .tab.active.t-comp { background: #ad3333 !important; color: #ffffff !important; border-color: #ad3333 !important; box-shadow: 0 2px 8px rgba(173,51,51,0.25) !important; }
    [data-theme="light"] .tab.active.t-corr { background: #003366 !important; color: #ffffff !important; border-color: #003366 !important; box-shadow: 0 2px 8px rgba(0,51,102,0.25) !important; }
    [data-theme="light"] .concl { background: #f8fafc !important; border: 1px solid #cbd5e1 !important; }
    [data-theme="light"] .concl p { color: #1e293b !important; font-weight: 500 !important; }
    [data-theme="light"] .finding { background: #f8fafc !important; border: 1px solid #cbd5e1 !important; color: #0f172a !important; font-weight: 500 !important; }
    [data-theme="light"] select.sel { background: #ffffff !important; color: #0f172a !important; border: 1px solid #cbd5e1 !important; font-weight: 600 !important; }
    [data-theme="light"] details.src summary { color: #003366 !important; font-weight: 700 !important; }
    [data-theme="light"] details.src summary:hover { color: #ad3333 !important; }
    [data-theme="light"] details.src pre { background: #f8fafc !important; color: #0f172a !important; border: 1px solid #cbd5e1 !important; }
    [data-theme="light"] footer { color: #475569 !important; border-top-color: #cbd5e1 !important; font-weight: 500 !important; }

    /* ================= BOTÓN EN ESQUINA (MODO NOCTURNO / DÍA) ================= */
    .theme-toggle-wrapper {
        position: fixed;
        bottom: 24px;
        right: 24px;
        z-index: 99999;
        display: inline-flex;
        align-items: center;
        justify-content: center;
    }
    .theme-toggle-corner {
        width: 36px !important;
        height: 36px !important;
        min-width: 36px !important;
        padding: 0 !important;
        background: #003366;
        color: #ffffff;
        border: 2px solid #DADADA;
        border-radius: 50% !important;
        font-size: 1rem;
        font-weight: 700;
        cursor: pointer;
        box-shadow: 0 4px 16px rgba(0,0,0,0.35);
        display: inline-flex;
        align-items: center;
        justify-content: center;
        transition: all 0.25s ease;
        user-select: none;
        position: relative;
    }
    .theme-toggle-corner:hover {
        background: #004080;
        border-color: #ffffff;
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(0,0,0,0.45);
    }
    .theme-toggle-tooltip {
        position: absolute;
        bottom: 100%;
        right: 0;
        margin-bottom: 8px;
        background: #0f172a;
        border: 1px solid rgba(148, 163, 184, 0.35);
        color: #f8fafc;
        font-size: 0.72rem;
        font-weight: 600;
        padding: 4px 8px;
        border-radius: 6px;
        white-space: nowrap;
        box-shadow: 0 6px 16px rgba(0, 0, 0, 0.4);
        pointer-events: none;
        opacity: 0;
        transform: translateY(4px);
        transition: opacity 0.15s ease, transform 0.15s ease;
        z-index: 100000;
    }
    .theme-toggle-wrapper:hover .theme-toggle-tooltip {
        opacity: 1;
        transform: translateY(0);
    }
    [data-theme="light"] .theme-toggle-corner {
        background: #ffffff;
        color: #003366;
        border-color: #003366;
        box-shadow: 0 4px 16px rgba(0,51,102,0.22);
    }
    [data-theme="light"] .theme-toggle-corner:hover {
        background: #f8fafc;
        border-color: #ad3333;
        color: #ad3333;
    }
    [data-theme="light"] .theme-toggle-tooltip {
        background: #ffffff !important;
        border-color: #cbd5e1 !important;
        color: #003366 !important;
        box-shadow: 0 4px 12px rgba(0, 51, 102, 0.15) !important;
    }
    .theme-toggle-corner .sr-only {
        position: absolute;
        width: 1px;
        height: 1px;
        padding: 0;
        margin: -1px;
        overflow: hidden;
        clip: rect(0, 0, 0, 0);
        white-space: nowrap;
        border-width: 0;
    }

    /* ================= MODO EMBEBIDO AISLADO (SIN CABECERA NI PESTAÑAS) ================= */
    body.is-embedded {
        padding: 6px 8px !important;
        background: transparent !important;
    }
    body.is-embedded header,
    body.is-embedded .tabs,
    body.is-embedded .theme-toggle-corner,
    body.is-embedded .standalone-export-toolbar,
    body.is-embedded footer {
        display: none !important;
    }
    body.is-standalone .standalone-export-toolbar {
        display: flex !important;
    }
    .standalone-export-toolbar .view-header-btn {
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
    }
    .standalone-export-toolbar .view-header-btn svg {
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
    }
    body.is-embedded .container {
        max-width: 100% !important;
        width: 100% !important;
        margin: 0 !important;
        padding: 0 !important;
    }
    body.is-embedded .panel {
        margin-top: 0 !important;
    }
    body.is-embedded .kpis {
        display: grid !important;
        grid-template-columns: repeat(6, minmax(0, 1fr)) !important;
        gap: 6px !important;
        margin-bottom: 8px !important;
    }
    @media (max-width: 1050px) {
        body.is-embedded .kpis {
            grid-template-columns: repeat(3, minmax(0, 1fr)) !important;
        }
    }
    body.is-embedded .kpi {
        padding: 6px 8px !important;
        border-radius: 6px !important;
    }
    body.is-embedded .kpi .v {
        font-size: 1.15rem !important;
        line-height: 1.15 !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
    }
    body.is-embedded .kpi .l {
        font-size: 0.6rem !important;
        line-height: 1.1 !important;
        margin-top: 2px !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
    }
    body.is-embedded .card {
        padding: 10px 12px !important;
        margin-bottom: 8px !important;
        border-radius: 6px !important;
    }
    body.is-embedded .card h2 {
        font-size: 0.94rem !important;
        margin-bottom: 2px !important;
        padding-bottom: 4px !important;
    }
    body.is-embedded .card .desc {
        font-size: 0.72rem !important;
        margin-bottom: 6px !important;
    }
    body.is-embedded .model-card {
        padding: 8px 10px !important;
        border-radius: 6px !important;
    }
    body.is-embedded .model-card h3 {
        font-size: 0.88rem !important;
    }
    body.is-embedded .mstats {
        margin: 6px 0 !important;
        gap: 4px !important;
    }
    body.is-embedded .mstat {
        padding: 4px 6px !important;
    }
    body.is-embedded .mstat b {
        font-size: 0.86rem !important;
    }
    body.is-embedded .mstat span {
        font-size: 0.58rem !important;
    }
    body.is-embedded .mdesc {
        font-size: 0.72rem !important;
        line-height: 1.3 !important;
    }
    body.is-embedded .chart-card {
        padding: 6px 8px !important;
    }
    body.is-embedded .grid2 {
        gap: 8px !important;
    }
    body.is-embedded .grid3 {
        gap: 8px !important;
    }
    body.is-embedded .grid4 {
        gap: 8px !important;
    }
    body.is-embedded table.t th {
        padding: 5px 8px !important;
        font-size: 0.68rem !important;
    }
    body.is-embedded table.t td {
        padding: 4px 8px !important;
        font-size: 0.72rem !important;
    }

    /* Barra de Selección y Filtro de Modelos */
    .model-selection-bar {
        border-radius: 8px;
        padding: 12px 16px;
        margin-bottom: 18px;
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        border-left: 4px solid #ad3333 !important;
    }
    .dark .model-selection-bar, [data-theme="dark"] .model-selection-bar {
        background: #101624;
        border: 1px solid #1e293b;
        border-left: 4px solid #ad3333 !important;
        box-shadow: 0 4px 14px rgba(0,0,0,0.3);
    }
    .ms-left { display: flex; flex-direction: column; gap: 4px; }
    .ms-title { font-size: 0.82rem; font-weight: 700; display: flex; align-items: center; gap: 8px; }
    .ms-badge { background: #ad3333; color: #fff; font-size: 0.65rem; padding: 2px 7px; border-radius: 4px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.5px; }
    .ms-sub { font-size: 0.7rem; color: #94a3b8; }
    .ms-chips { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-top: 4px; }
    .ms-chip {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 5px 10px;
        border-radius: 6px;
        font-size: 0.75rem;
        cursor: pointer;
        user-select: none;
        transition: all 0.2s ease;
    }
    .dark .ms-chip, [data-theme="dark"] .ms-chip {
        background: #0A0E16;
        border: 1px solid #334155;
        color: #ffffff;
    }
    .ms-chip:hover { border-color: #003366; }
    .dark .ms-chip.active, [data-theme="dark"] .ms-chip.active { background: rgba(0, 51, 102, 0.6) !important; border-color: #0055a5 !important; font-weight: 700; box-shadow: 0 0 8px rgba(0, 85, 165, 0.4); }
    .ms-chip input { cursor: pointer; accent-color: #ad3333; }
    .dark .ms-chip .runs-badge, [data-theme="dark"] .ms-chip .runs-badge { font-size: 0.62rem; padding: 1px 5px; border-radius: 9999px; background: rgba(0,0,0,0.4); color: #cbd5e1; font-family: monospace; }
    .ms-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
    .btn-sm { padding: 5px 11px !important; font-size: 0.72rem !important; border-radius: 5px !important; }
    .btn-apply { background: #003366 !important; border-color: #DADADA !important; color: #fff !important; font-weight: 700; }
    .btn-apply:hover { background: #002244 !important; }
    .btn-danger { background: #ad3333 !important; border-color: #DADADA !important; color: #fff !important; }
    .btn-danger:hover { background: #8a2525 !important; }

    /* Modal de Gestión / Eliminación */
    .modal-overlay {
        position: fixed; inset: 0; background: rgba(0,0,0,0.8); backdrop-filter: blur(5px);
        display: none; align-items: center; justify-content: center; z-index: 99999;
    }
    .modal-box {
        background: #0e1b2e; border: 1px solid rgba(218,218,218,0.3); border-top: 4px solid #ad3333;
        border-radius: 10px; max-width: 680px; width: 92%; max-height: 85vh; overflow-y: auto; padding: 22px;
        box-shadow: 0 16px 40px rgba(0,0,0,0.8); color: #f8fafc;
    }
    .modal-hdr { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; border-bottom: 1px solid rgba(218,218,218,0.2); padding-bottom: 10px; }
    .modal-hdr h3 { margin: 0; font-size: 1.15rem; color: #fff; display: flex; align-items: center; gap: 8px; font-weight: 800; }
    .close-btn { background: transparent; border: none; font-size: 1.5rem; color: #DADADA; cursor: pointer; line-height: 1; }
    .model-manage-row {
        display: flex; justify-content: space-between; align-items: center; gap: 12px;
        padding: 10px 14px; border-radius: 7px; background: #070e18; border: 1px solid rgba(218,218,218,0.18); margin-bottom: 10px;
    }
    .model-manage-info { display: flex; flex-direction: column; gap: 3px; }
    .model-manage-name { font-weight: 700; font-size: 0.88rem; color: #ffffff; display: flex; align-items: center; gap: 8px; }
    .model-manage-sub { font-size: 0.72rem; color: #94a3b8; }
    .tag-base { background: #003366; color: #fff; font-size: 0.6rem; padding: 1px 6px; border-radius: 4px; font-weight: 700; }
    .tag-dyn { background: #0f766e; color: #fff; font-size: 0.6rem; padding: 1px 6px; border-radius: 4px; font-weight: 700; }

    /* ================= MODAL DE ALERTA PERSONALIZADO (REEMPLAZO WINDOW.ALERT) ================= */
    .custom-alert-overlay {
        position: fixed; inset: 0; background: rgba(3, 7, 18, 0.78); backdrop-filter: blur(8px);
        -webkit-backdrop-filter: blur(8px); display: none; align-items: center; justify-content: center;
        z-index: 1000000; opacity: 0; transition: opacity 0.2s ease-in-out; padding: 16px; box-sizing: border-box;
    }
    .custom-alert-overlay.active { display: flex; opacity: 1; }
    .custom-alert-box {
        background: #0e1b2e; border: 1px solid rgba(218, 218, 218, 0.25); border-top: 3px solid #f59e0b;
        border-radius: 12px; max-width: 460px; width: 100%; padding: 20px 22px 18px 22px;
        box-shadow: 0 20px 50px rgba(0, 0, 0, 0.8), 0 0 24px rgba(245, 158, 11, 0.15);
        color: #f8fafc; box-sizing: border-box; transform: scale(0.94) translateY(-4px);
        transition: transform 0.22s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.2s ease;
    }
    .custom-alert-overlay.active .custom-alert-box { transform: scale(1) translateY(0); }
    .custom-alert-top { display: flex; align-items: flex-start; gap: 14px; }
    .custom-alert-icon-wrapper {
        width: 40px; height: 40px; border-radius: 10px; display: flex; align-items: center; justify-content: center;
        flex-shrink: 0; background: rgba(245, 158, 11, 0.15); border: 1px solid rgba(245, 158, 11, 0.35);
        color: #fbbf24; transition: all 0.2s ease;
    }
    .custom-alert-icon-wrapper.type-error { background: rgba(173, 51, 51, 0.2); border-color: rgba(239, 68, 68, 0.4); color: #f87171; }
    .custom-alert-icon-wrapper.type-info { background: rgba(2, 132, 199, 0.2); border-color: rgba(56, 189, 248, 0.4); color: #38bdf8; }
    .custom-alert-icon-wrapper.type-success { background: rgba(16, 185, 129, 0.2); border-color: rgba(52, 211, 153, 0.4); color: #34d399; }
    .custom-alert-icon { width: 22px; height: 22px; }
    .custom-alert-content { flex: 1; min-width: 0; }
    .custom-alert-header { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 6px; }
    .custom-alert-title { margin: 0; font-size: 0.95rem; font-weight: 700; color: #ffffff; line-height: 1.25; letter-spacing: -0.01em; }
    .custom-alert-close {
        background: transparent; border: none; color: #94a3b8; font-size: 1.35rem; line-height: 1;
        cursor: pointer; padding: 0; width: 24px; height: 24px; display: flex; align-items: center; justify-content: center;
        border-radius: 4px; transition: color 0.15s ease, background 0.15s ease;
    }
    .custom-alert-close:hover { color: #ffffff; background: rgba(255, 255, 255, 0.1); }
    .custom-alert-msg { margin: 0; font-size: 0.8rem; color: #cbd5e1; line-height: 1.45; }
    .custom-alert-footer {
        display: flex; justify-content: flex-end; align-items: center; gap: 10px;
        margin-top: 18px; padding-top: 14px; border-top: 1px solid rgba(218, 218, 218, 0.12);
    }
    .custom-alert-btn {
        display: inline-flex; align-items: center; gap: 8px; padding: 7px 16px; border-radius: 7px;
        background: linear-gradient(135deg, #ad3333 0%, #801818 100%); border: 1px solid rgba(248, 113, 113, 0.5);
        color: #ffffff; font-size: 0.76rem; font-weight: 700; cursor: pointer;
        box-shadow: 0 4px 14px rgba(173, 51, 51, 0.4); transition: all 0.15s ease;
    }
    .custom-alert-btn:hover {
        background: linear-gradient(135deg, #bd3a3a 0%, #902020 100%); border-color: #fca5a5;
        box-shadow: 0 6px 18px rgba(173, 51, 51, 0.6); transform: translateY(-1px);
    }
    .custom-alert-btn:active { transform: translateY(0); }
    .custom-alert-kbd {
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 0.62rem;
        background: rgba(0, 0, 0, 0.35); border: 1px solid rgba(255, 255, 255, 0.25); border-radius: 4px;
        padding: 1px 5px; color: #fca5a5; font-weight: 600;
    }

    /* Adaptabilidad de Modales en Modo Claro */
    [data-theme="light"] .modal-overlay,
    [data-theme="light"] .custom-alert-overlay {
        background: rgba(15, 23, 42, 0.45) !important;
    }
    [data-theme="light"] .modal-box,
    [data-theme="light"] .custom-alert-box {
        background: #ffffff !important; border-color: #cbd5e1 !important; color: #0f172a !important;
        box-shadow: 0 20px 50px rgba(0, 51, 102, 0.2) !important;
    }
    [data-theme="light"] .modal-hdr { border-bottom-color: #e2e8f0 !important; }
    [data-theme="light"] .modal-hdr h3,
    [data-theme="light"] .custom-alert-title { color: #003366 !important; }
    [data-theme="light"] .close-btn,
    [data-theme="light"] .custom-alert-close { color: #64748b !important; }
    [data-theme="light"] .close-btn:hover,
    [data-theme="light"] .custom-alert-close:hover { color: #ad3333 !important; background: #f1f5f9 !important; }
    [data-theme="light"] .model-manage-row { background: #f8fafc !important; border-color: #cbd5e1 !important; }
    [data-theme="light"] .model-manage-name { color: #0f172a !important; }
    [data-theme="light"] .custom-alert-msg { color: #334155 !important; }
    [data-theme="light"] .custom-alert-footer { border-top-color: #e2e8f0 !important; }
    [data-theme="light"] .custom-alert-icon-wrapper { background: #fffbeb !important; border-color: #fde68a !important; color: #d97706 !important; }
    [data-theme="light"] .custom-alert-icon-wrapper.type-error { background: #fef2f2 !important; border-color: #fecaca !important; color: #dc2626 !important; }
    [data-theme="light"] .custom-alert-icon-wrapper.type-info { background: #f0f9ff !important; border-color: #bae6fd !important; color: #0284c7 !important; }
    [data-theme="light"] .custom-alert-icon-wrapper.type-success { background: #ecfdf5 !important; border-color: #a7f3d0 !important; color: #059669 !important; }

    .print-only-header { display: none; }

    @media print {
        body { background: #fff !important; color: #000 !important; padding: 10px !important; }
        .tabs, .hdr-actions, .model-selection-bar, details.src, .theme-toggle-corner, .standalone-export-toolbar, .btn, .ms-actions { display: none !important; }
        .panel { display: none !important; }
        .panel.active { display: block !important; page-break-before: auto !important; }
        .print-only-header {
            display: block !important;
            margin-bottom: 16px;
            padding-bottom: 8px;
            border-bottom: 2px solid #003366;
        }
        .print-only-header h1 {
            font-size: 1.35rem;
            color: #003366 !important;
            font-weight: 800;
            margin-bottom: 3px;
        }
        .print-only-header p {
            font-size: 0.78rem;
            color: #475569 !important;
            font-weight: 600;
        }
        .card, .kpi, .chart-card, .model-card, .concl, .finding { background: #fff !important; border-color: #cbd5e1 !important; color: #000 !important; box-shadow: none !important; break-inside: avoid; }
        svg text, svg text.val { fill: #111 !important; }
        .mdesc, .concl p, table.t td { color: #111 !important; }
    }
</style>
</head>
<body class="is-embedded">
<div class="container">
    <!-- STANDALONE_EXPORT_TOOLBAR -->
    <!-- Barra Dinámica de Selección de Modelos para el Informe -->
    <div class="model-selection-bar bg-white dark:bg-[#101624] border border-slate-200 dark:border-slate-800 shadow-sm" id="modelSelectionBar">
        <div class="ms-left">
            <div class="ms-title text-slate-800 dark:text-slate-200">
                <span class="ms-badge">Modelos en el Informe</span>
                <span class="text-slate-800 dark:text-slate-200">Selecciona qué modelos evaluar en las comparativas y exportables:</span>
                <span id="msSelectedCount" style="font-size:0.7rem;color:#38bdf8;font-mono;">(Cargando modelos...)</span>
            </div>
            <div class="ms-chips" id="modelSelectionChips">
                <!-- Se llena dinámicamente vía API -->
            </div>
            <div class="sub" id="hwInfo" style="font-size:0.72rem;color:#64748b;margin-top:4px;"></div>
        </div>
        <div class="ms-actions">
            <button type="button" class="btn btn-sm" onclick="selectAllModels(true)">Todos</button>
            <button type="button" class="btn btn-sm" onclick="selectAllModels(false)">Limpiar</button>
            <button type="button" class="btn btn-sm btn-apply" onclick="applyModelSelection()">✓ Aplicar al Informe</button>
            <button type="button" class="btn btn-sm btn-danger" onclick="openModelManageModal()">⚙️ Gestionar</button>
        </div>
    </div>

    <!-- ================= PANEL OE4 ================= -->
    <section class="panel" id="panel-comparativo">
        <div class="print-only-header">
            <h1>Informe Técnico Comparativo Multidimensional (OE4)</h1>
            <p>NetDiagBench-L7 &bull; Matriz Radar de Evaluación, Eficiencia y Rendimiento de Modelos</p>
        </div>
        <h2 class="sr-only" style="display:none;">Informe Técnico Comparativo (OE4)</h2>
        <div class="loading" id="compLoading">Cargando informe técnico comparativo...</div>
        <div id="compBody" style="display:none">
            <div class="kpis" id="compKpis"></div>

            <div class="card comp bg-white dark:bg-[#101624] border border-slate-200 dark:border-slate-800">
                <h2>Perfiles de Modelo y Score de Eficiencia Compuesto <span title="Score Compuesto OE4: 40% precisión + 20% rúbrica + 20% velocidad (tok/s) + 20% eficiencia VRAM." style="cursor:help;font-size:0.75rem;opacity:0.8;">ℹ️</span></h2>
                <div class="desc text-slate-600 dark:text-slate-400">Score = 40% precisión + 20% rúbrica + 20% velocidad (tok/s normalizada) + 20% eficiencia VRAM (VRAM mínima / VRAM del modelo).</div>
                <div class="grid3" id="modelCards"></div>
            </div>

            <div class="grid2">
                <div class="card comp bg-white dark:bg-[#101624] border border-slate-200 dark:border-slate-800">
                    <h2>Matriz Multidimensional (Radar) <span title="Radar Multidimensional OE4: normalización [0, 1] de 5 ejes críticos: Precisión, Rúbrica, TTFT, Throughput y Eficiencia VRAM." style="cursor:help;font-size:0.75rem;opacity:0.8;">ℹ️</span></h2>
                    <div class="desc text-slate-600 dark:text-slate-400">Cada eje normalizado a [0, 1]; 1 = mejor valor de la terna. Haga clic en la leyenda para ocultar/mostrar modelos.</div>
                    <div id="radarChart"></div>
                </div>
                <div class="card comp bg-white dark:bg-[#101624] border border-slate-200 dark:border-slate-800">
                    <h2>Descomposición del Score de Eficiencia <span title="Desglose analítico de los cuatro sumandos ponderados del Score de Eficiencia (máximo = 1.0)." style="cursor:help;font-size:0.75rem;opacity:0.8;">ℹ️</span></h2>
                    <div class="desc text-slate-600 dark:text-slate-400">Aporte de cada criterio ponderado al score compuesto (máximo teórico = 1,0).</div>
                    <div id="scoreChart"></div>
                    <div class="legend" id="scoreLegend"></div>
                </div>
            </div>

            <div class="card comp bg-white dark:bg-[#101624] border border-slate-200 dark:border-slate-800">
                <h2>Rendimiento de Inferencia y Recursos (Tarea 4.2.2) <span title="Métricas empíricas de cómputo: TTFT (ms), Throughput (tok/s), VRAM pico (GB) y Latencia total." style="cursor:help;font-size:0.75rem;opacity:0.8;">ℹ️</span></h2>
                <div class="desc text-slate-600 dark:text-slate-400">Promedios por modelo sobre todas las corridas. ★ = mejor valor.</div>
                <div class="grid4" id="perfCharts"></div>
            </div>

            <div class="card comp bg-white dark:bg-[#101624] border border-slate-200 dark:border-slate-800">
                <h2>Huella Energética y de Carbono (Tarea 4.2.2c)</h2>
                <div class="desc text-slate-600 dark:text-slate-400">Energía total y CO₂ estimados (CodeCarbon) y eficiencia energética en tokens por Wh.</div>
                <div class="grid3" id="energyCharts"></div>
            </div>

            <div class="card comp bg-white dark:bg-[#101624] border border-slate-200 dark:border-slate-800">
                <h2>Matriz de Evaluación Multidimensional (tabla)</h2>
                <div class="desc text-slate-600 dark:text-slate-400">Valores resaltados en verde = mejor de la columna.</div>
                <div class="table-wrap" id="matrixTable"></div>
            </div>

            <div class="card comp bg-white dark:bg-[#101624] border border-slate-200 dark:border-slate-800">
                <h2>Precisión Diagnóstica por Escenario y Modelo</h2>
                <div class="desc text-slate-600 dark:text-slate-400">Porcentaje de corridas con causa raíz correcta (todas las semillas). Verde = 100%, rojo = 0%.</div>
                <div class="table-wrap" id="scenarioHeat"></div>
            </div>

            <div class="card comp bg-white dark:bg-[#101624] border border-slate-200 dark:border-slate-800">
                <h2>Conclusión de Selección (OE4 / Tarea 4.3.1)</h2>
                <div class="desc text-slate-600 dark:text-slate-400">Configuración recomendada según el análisis de compromiso (trade-offs).</div>
                <div class="grid3" id="conclusions"></div>
                <details class="src"><summary>Ver fuente Markdown (resultados_resumen.md)</summary><pre id="compMd"></pre></details>
            </div>
        </div>
    </section>

    <!-- ================= PANEL 4.1.2 ================= -->
    <section class="panel" id="panel-correlacion">
        <div class="print-only-header">
            <h1>Análisis Correlacional y Significancia Estadística (SciPy)</h1>
            <p>NetDiagBench-L7 &bull; Kruskal-Wallis, Spearman &rho;, Pearson r e Intervalos de Confianza 95% Bootstrap</p>
        </div>
        <h2 class="sr-only" style="display:none;">Análisis Correlacional (Tarea 4.1.2)</h2>
        <div class="loading" id="corrLoading">Cargando análisis correlacional...</div>
        <div id="corrBody" style="display:none">
            <div class="kpis" id="corrKpis"></div>

            <div class="card corr bg-white dark:bg-[#101624] border border-slate-200 dark:border-slate-800">
                <h2>Hallazgos Principales</h2>
                <div class="desc text-slate-600 dark:text-slate-400">Interpretación automática a partir de los resultados estadísticos (α = 0,05).</div>
                <div id="findings"></div>
            </div>

            <div class="grid2">
                <div class="card corr bg-white dark:bg-[#101624] border border-slate-200 dark:border-slate-800">
                    <h2>1. Correlación: Parámetros del Modelo vs Métricas <span title="Spearman rho: asociación monótona (-1 a +1). Pearson r: correlación lineal estricta. Significancia con p < 0.05." style="cursor:help;font-size:0.75rem;opacity:0.8;">ℹ️</span></h2>
                    <div class="desc text-slate-600 dark:text-slate-400">Spearman ρ y Pearson r (rango −1 a +1). Barras sólidas = significativo (p &lt; 0,05).</div>
                    <div id="corrChart"></div>
                    <div class="legend"><span><i class="dot" style="background:#003366;border:1px solid #DADADA"></i>Spearman ρ</span><span><i class="dot" style="background:#ad3333"></i>Pearson r</span></div>
                </div>
                <div class="card corr bg-white dark:bg-[#101624] border border-slate-200 dark:border-slate-800">
                    <h2>2. Prueba de Kruskal-Wallis entre Modelos <span title="Prueba estadística no paramétrica H de Kruskal-Wallis. Evalúa si las distribuciones de los modelos SLM difieren significativamente (p < 0.05)." style="cursor:help;font-size:0.75rem;opacity:0.8;">ℹ️</span></h2>
                    <div class="desc text-slate-600 dark:text-slate-400">Estadístico H por métrica. La línea roja marca el valor crítico χ² (α = 0,05); H por encima ⇒ se rechaza H₀.</div>
                    <div id="kwChart"></div>
                </div>
            </div>

            <div class="card corr bg-white dark:bg-[#101624] border border-slate-200 dark:border-slate-800">
                <h2>Tabla de Correlaciones y Significancia <span title="Matriz de coeficientes de Spearman y Pearson con valores p exactos para cada métrica." style="cursor:help;font-size:0.75rem;opacity:0.8;">ℹ️</span></h2>
                <div class="desc text-slate-600 dark:text-slate-400">Fuerza según |ρ|: &lt;0,1 nula · &lt;0,3 débil · &lt;0,5 moderada · &lt;0,7 considerable · ≥0,7 fuerte.</div>
                <div class="table-wrap" id="corrTable"></div>
            </div>

            <div class="card corr bg-white dark:bg-[#101624] border border-slate-200 dark:border-slate-800">
                <h2>3. Intervalos de Confianza Bootstrap al 95% <span title="Intervalo de confianza al 95% obtenido mediante 1,000 iteraciones Bootstrap con remuestreo percentil." style="cursor:help;font-size:0.75rem;opacity:0.8;">ℹ️</span></h2>
                <div class="desc text-slate-600 dark:text-slate-400">Forest plot por métrica: punto = media, barra = IC 95% (1000 remuestreos, percentil). Intervalos que no se solapan indican diferencias robustas.</div>
                <div class="grid4" id="ciCharts"></div>
            </div>

            <div class="card corr bg-white dark:bg-[#101624] border border-slate-200 dark:border-slate-800">
                <h2>4. Tamaño del Efecto (d de Cohen) entre Pares de Modelos <span title="d de Cohen: cuantifica la magnitud estandarizada de la diferencia práctica entre modelos (|d| >= 0.8 grande)." style="cursor:help;font-size:0.75rem;opacity:0.8;">ℹ️</span></h2>
                <div class="desc text-slate-600 dark:text-slate-400">Umbrales de Cohen (1988): |d| &lt; 0,2 insignificante · &lt; 0,5 pequeño · &lt; 0,8 mediano · ≥ 0,8 grande.</div>
                <div class="table-wrap" id="effectTable"></div>
            </div>

            <div class="card corr bg-white dark:bg-[#101624] border border-slate-200 dark:border-slate-800">
                <h2>5. Estadísticos Descriptivos por Modelo</h2>
                <div class="desc text-slate-600 dark:text-slate-400" style="display:flex; justify-content:space-between; align-items:center; gap:10px; flex-wrap:wrap;">
                    <span>Media, desviación estándar, coeficiente de variación y percentiles. Barra = rango [mín, máx] con marcador en p50 y p95.</span>
                    <select class="sel" id="descMetric"></select>
                </div>
                <div class="table-wrap" id="descTable"></div>
                <details class="src"><summary>Ver fuente Markdown (analisis_correlacional.md)</summary><pre id="corrMd"></pre></details>
            </div>
        </div>
    </section>

    <footer>Dashboard autogenerado por NetDiagBench-L7 · 100% local, sin dependencias externas · <a href="/api/report-html" style="color:inherit;text-decoration:underline;" target="_blank">Informe Consolidado Global</a></footer>
</div>

<script>
function isLight() {
    return document.documentElement.getAttribute('data-theme') === 'light' ||
           (!document.documentElement.classList.contains('dark') && document.documentElement.getAttribute('data-theme') !== 'dark');
}

const COLORS_DARK = {
    "qwen3-8b": "#f87171",
    "glm-4-9b-chat": "#38bdf8",
    "phi-4-mini-instruct": "#e2e8f0"
};

const COLORS_LIGHT = {
    "qwen3-8b": "#b91c1c",       // Red-700
    "glm-4-9b-chat": "#0284c7",   // Sky-600
    "phi-4-mini-instruct": "#334155" // Slate-700 (High contrast dark slate)
};

const EXTRA_DARK = ["#fb7185", "#38bdf8", "#34d399", "#a78bfa", "#f59e0b", "#94a3b8"];
const EXTRA_LIGHT = ["#be123c", "#0284c7", "#047857", "#6d28d9", "#b45309", "#334155"];

function color(m, i) {
    const light = isLight();
    const map = light ? COLORS_LIGHT : COLORS_DARK;
    const extra = light ? EXTRA_LIGHT : EXTRA_DARK;
    if (m && map[m]) return map[m];
    return extra[(i || 0) % extra.length];
}
const COLORS = COLORS_DARK;
function esc(s) { return String(s === null || s === undefined ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }
function fmt(v, d) {
    if (v === null || v === undefined || isNaN(v)) return "—";
    d = (d === undefined) ? 1 : d;
    return Number(v).toLocaleString("es-CO", { maximumFractionDigits: d, minimumFractionDigits: 0 });
}
function fmtC(v) {
    if (v === null || v === undefined || isNaN(v)) return "—";
    const a = Math.abs(v);
    if (a >= 1e6) return fmt(v / 1e6, 2) + " M";
    if (a >= 1e4) return fmt(v / 1e3, 1) + " k";
    return fmt(v, a < 10 ? 3 : 1);
}
function fmtP(p) {
    if (p === null || p === undefined || isNaN(p)) return "—";
    if (p < 0.001) return "&lt; 0,001";
    return fmt(p, 4);
}

const METRIC_LABELS = {
    ttft_ms: "TTFT (ms)", tokens_per_sec: "Tokens/s", total_time_ms: "Latencia total (ms)",
    energy_kwh: "Energía (kWh)", rubric_score: "Rúbrica (0-5)", partial_match_score: "Coincidencia Parcial",
    peak_vram_gb: "VRAM (Declarada/Estimada) pico (GB)", peak_ram_mb: "RAM pico (MB)"
};
const lbl = k => METRIC_LABELS[k] || k;

let COMP = null, CORR = null;

function showTab(name) {
    document.querySelectorAll(".tab").forEach(t => t.classList.toggle("active", t.dataset.tab === name));
    document.querySelectorAll(".panel").forEach(p => p.classList.toggle("active", p.id === "panel-" + name));
    const btnComp = document.getElementById("btnAnalyticsPdfComp");
    const btnCorr = document.getElementById("btnAnalyticsPdfCorr");
    if (btnComp) btnComp.style.display = (name === "comparativo") ? "inline-flex" : "none";
    if (btnCorr) btnCorr.style.display = (name === "correlacion") ? "inline-flex" : "none";
    if (location.hash !== "#" + name) history.replaceState(null, "", "#" + name);

    // Sincronizar barra de exportación standalone
    const tbTitle = document.getElementById("standaloneToolbarTitle");
    const tbPdf = document.getElementById("standaloneBtnPdf");
    const tbPdfText = document.getElementById("standaloneBtnPdfText");
    const tbToolbar = document.getElementById("standaloneExportToolbar");
    const tbExcel = document.getElementById("standaloneBtnExcel");
    if (name === "correlacion") {
        if (tbTitle) tbTitle.textContent = "Informe de Análisis Correlacional y Significancia Estadística (SciPy)";
        if (tbPdf) {
            tbPdf.href = "/api/export/correlacional/pdf";
            tbPdf.setAttribute("data-base-href", "/api/export/correlacional/pdf");
        }
        if (tbPdfText) tbPdfText.textContent = "PDF Correlacional (SciPy)";
        if (tbToolbar) tbToolbar.setAttribute("data-view", "correlacion");
        if (tbExcel) tbExcel.style.display = "none";
    } else {
        if (tbTitle) tbTitle.textContent = "Informe Técnico Comparativo Multidimensional (OE4)";
        if (tbPdf) {
            tbPdf.href = "/api/export/comparativo/pdf";
            tbPdf.setAttribute("data-base-href", "/api/export/comparativo/pdf");
        }
        if (tbPdfText) tbPdfText.textContent = "PDF Comparativo (OE4)";
        if (tbToolbar) tbToolbar.setAttribute("data-view", "comparativo");
        if (tbExcel) tbExcel.style.display = "inline-flex";
    }
    if (typeof updateExportUrls === 'function') updateExportUrls();
}

function kpi(v, l, c, tip) { return `<div class="kpi"${tip ? ` title="${esc(tip)}" style="cursor:help;"` : ""}><div class="v" style="${c ? "color:" + c : ""}">${v}</div><div class="l">${l}${tip ? " ℹ️" : ""}</div></div>`; }

// ───────────────────────── Gráficos SVG genéricos ─────────────────────────
function hBarChart(o) {
    const items = o.items, W = 460, rowH = 34, padL = 150, padR = 96, top = 14;
    const H = top + items.length * rowH + 6;
    const vals = items.map(i => i.value);
    const maxV = (Math.max.apply(null, vals.concat([o.limit || 0])) * 1.08) || 1;
    const best = o.lowerIsBetter ? Math.min.apply(null, vals) : Math.max.apply(null, vals);
    const span = W - padL - padR;
    const light = isLight();
    const bgBar = light ? "#e2e8f0" : "#0f172a";
    let s = `<svg viewBox="0 0 ${W} ${H}" class="chart">`;
    items.forEach((it, i) => {
        const y = top + i * rowH, w = Math.max((it.value / maxV) * span, 1), isBest = it.value === best;
        s += `<text x="${padL - 8}" y="${y + rowH / 2 + 4}" text-anchor="end">${esc(it.label)}</text>`;
        s += `<rect x="${padL}" y="${y + 7}" width="${span}" height="${rowH - 14}" rx="4" fill="${bgBar}"/>`;
        s += `<rect x="${padL}" y="${y + 7}" width="${w}" height="${rowH - 14}" rx="4" fill="${it.color}" opacity="${isBest ? 1 : 0.75}"><title>${esc(it.label)}: ${fmt(it.value, o.decimals)} ${esc(o.unit)}</title></rect>`;
        s += `<text x="${padL + w + 6}" y="${y + rowH / 2 + 4}" class="val">${o.compact ? fmtC(it.value) : fmt(it.value, o.decimals)} ${esc(o.unit)}${isBest ? " ★" : ""}</text>`;
    });
    if (o.limit) {
        const x = padL + (o.limit / maxV) * span;
        s += `<line x1="${x}" x2="${x}" y1="4" y2="${H - 2}" stroke="#f87171" stroke-width="1.5" stroke-dasharray="4 3"/>`;
        s += `<text x="${x - 4}" y="11" text-anchor="end" class="lim">${esc(o.limitLabel || "")}</text>`;
    }
    s += "</svg>";
    const hint = o.lowerIsBetter ? "↓ menor es mejor" : "↑ mayor es mejor";
    return `<div class="chart-card"><div class="chart-title">${esc(o.title)}<span class="hint">${hint}</span></div>${s}</div>`;
}

function radarChart(models, ids, hidden) {
    const dims = [
        { k: "Precisión", f: m => m.accuracy_pct / 100 },
        { k: "Coincidencia Parcial", f: m => m.partial_f1 },
        { k: "Evidencia", f: m => m.evidence_rate_pct / 100 },
        { k: "Rúbrica", f: m => m.rubric / 5 },
        { k: "Velocidad tok/s", f: (m, a) => m.tokens_per_sec / a.maxTok },
        { k: "Rapidez TTFT", f: (m, a) => a.minTtft / m.ttft_ms },
        { k: "Rapidez latencia", f: (m, a) => a.minLat / m.latency_p50_ms },
        { k: "Eficiencia VRAM", f: (m, a) => a.minVram / m.vram_gb },
        { k: "Eficiencia energética", f: (m, a) => m.tokens_per_wh / a.maxTwh }
    ];
    const all = ids.map(i => models[i]);
    const agg = {
        maxTok: Math.max.apply(null, all.map(m => m.tokens_per_sec)) || 1,
        minTtft: Math.min.apply(null, all.map(m => m.ttft_ms)) || 1,
        minLat: Math.min.apply(null, all.map(m => m.latency_p50_ms)) || 1,
        minVram: Math.min.apply(null, all.map(m => m.vram_gb)) || 1,
        maxTwh: Math.max.apply(null, all.map(m => m.tokens_per_wh)) || 1
    };
    const W = 520, H = 420, cx = W / 2, cy = H / 2 + 4, R = 145, n = dims.length;
    const pt = (i, r) => { const a = -Math.PI / 2 + i * 2 * Math.PI / n; return [cx + r * Math.cos(a), cy + r * Math.sin(a)]; };
    const light = isLight();
    const gridLineCol = light ? "#cbd5e1" : "#334155";
    let s = `<svg viewBox="0 0 ${W} ${H}" class="chart">`;
    [0.25, 0.5, 0.75, 1].forEach(g => {
        const p = dims.map((d, i) => pt(i, R * g).join(",")).join(" ");
        s += `<polygon points="${p}" fill="none" stroke="${gridLineCol}" stroke-width="1"/>`;
        s += `<text x="${cx + 3}" y="${cy - R * g + 10}" class="dim">${fmt(g, 2)}</text>`;
    });
    dims.forEach((d, i) => {
        const [x, y] = pt(i, R), [lx, ly] = pt(i, R + 22);
        s += `<line x1="${cx}" y1="${cy}" x2="${x}" y2="${y}" stroke="${gridLineCol}"/>`;
        const anchor = Math.abs(lx - cx) < 8 ? "middle" : (lx > cx ? "start" : "end");
        s += `<text x="${lx}" y="${ly + 4}" text-anchor="${anchor}">${esc(d.k)}</text>`;
    });
    ids.forEach((id, idx) => {
        if (hidden.has(id)) return;
        const m = models[id], c = color(id, idx);
        const vals = dims.map(d => Math.max(0, Math.min(1, d.f(m, agg))));
        const p = vals.map((v, i) => pt(i, R * v).join(",")).join(" ");
        s += `<polygon points="${p}" fill="${c}" fill-opacity="${light ? '0.18' : '0.12'}" stroke="${c}" stroke-width="2.5"/>`;
        vals.forEach((v, i) => { const [x, y] = pt(i, R * v); s += `<circle cx="${x}" cy="${y}" r="4" fill="${c}"><title>${esc(id)} · ${esc(dims[i].k)}: ${fmt(v, 3)}</title></circle>`; });
    });
    s += "</svg>";
    const legend = ids.map((id, idx) => `<span class="${hidden.has(id) ? "off" : ""}" onclick="toggleRadar('${esc(id)}')"><i class="dot" style="background:${color(id, idx)}"></i>${esc(id)}</span>`).join("");
    return s + `<div class="legend">${legend}</div>`;
}
const radarHidden = new Set();
function toggleRadar(id) {
    radarHidden.has(id) ? radarHidden.delete(id) : radarHidden.add(id);
    document.getElementById("radarChart").innerHTML = radarChart(COMP.models, COMP.model_ids, radarHidden);
}

function scoreRing(score, c) {
    const r = 30, C = 2 * Math.PI * r, off = C * (1 - Math.max(0, Math.min(1, score)));
    const light = isLight();
    const trackCol = light ? "#e2e8f0" : "#1e293b";
    const textCol = light ? "#0f172a" : "#ffffff";
    return `<svg width="78" height="78" viewBox="0 0 78 78"><circle cx="39" cy="39" r="${r}" fill="none" stroke="${trackCol}" stroke-width="8"/>
        <circle cx="39" cy="39" r="${r}" fill="none" stroke="${c}" stroke-width="8" stroke-linecap="round" stroke-dasharray="${C}" stroke-dashoffset="${off}" transform="rotate(-90 39 39)"/>
        <text x="39" y="44" text-anchor="middle" style="font-size:15px;font-weight:800;fill:${textCol}">${fmt(score, 3)}</text></svg>`;
}

// ───────────────────────── Panel OE4 ─────────────────────────
function renderComparativo(d) {
    const ids = d.model_ids, M = d.models, rank = d.ranking;
    const recMap = {};
    (d.conclusions || []).forEach(c => {
        if (c.model_id) {
            recMap[c.model_id] = {
                badge: c.badge || (c.title && c.title.includes("NOC") ? "RECOMENDADO NOC" : (c.title && c.title.includes("Acotados") ? "RECOMENDADO RECURSOS ACOTADOS" : "TRIAJE PRELIMINAR (BORDE)")),
                color: c.badge_color || (c.badge && c.badge.includes("NOC") ? "#003366" : (c.badge && c.badge.includes("ACOTADO") ? "#ad3333" : "#475569"))
            };
        }
    });
    const hwEl = document.getElementById("hwInfo");
    if (hwEl) {
        hwEl.textContent = d.hardware_fingerprint ? "Huella de hardware: " + d.hardware_fingerprint : "";
    }

    const light = isLight();
    const bestAcc = Math.max.apply(null, ids.map(i => M[i].accuracy_pct));
    const fastest = ids.slice().sort((a, b) => M[b].tokens_per_sec - M[a].tokens_per_sec)[0];
    const lightest = ids.slice().sort((a, b) => M[a].vram_gb - M[b].vram_gb)[0];
    const bestAccCol = light ? "#047857" : "#34d399";
    document.getElementById("compKpis").innerHTML =
        kpi(d.n_total, "Corridas evaluadas", null, "Total de ensayos de diagnóstico ejecutados y registrados en el dataset") +
        kpi(d.n_models, "Modelos SLM (Q4_K_M)", null, "Modelos de lenguaje pequeños evaluados bajo cuantización Q4_K_M") +
        kpi(d.n_scenarios, "Escenarios en el dataset", null, "18 escenarios reproducibles categorizados por RFC (DNS, TLS, HTTP, API Gateway)") +
        kpi(fmt(bestAcc, 1) + "%", "Mejor precisión diagnóstica", bestAccCol, "Porcentaje máximo de diagnósticos con causa raíz y componente correctos") +
        kpi(esc(fastest), "Mayor velocidad (tok/s)", color(fastest), "Modelo con mayor tasa sostenida de generación de tokens durante la inferencia") +
        kpi(esc(lightest), "Menor huella de VRAM", color(lightest), "Modelo con menor consumo de memoria de GPU reportado durante la ejecución");

    // Tarjetas de modelo
    document.getElementById("modelCards").innerHTML = rank.map((id, pos) => {
        const m = M[id], c = color(id, ids.indexOf(id));
        const badgeBorder = light ? "#cbd5e1" : "#DADADA";
        const recInfo = recMap[id] || (m.profile && m.profile.badge ? { badge: m.profile.badge, color: m.profile.badge_color || "#475569" } : null);
        const rec = recInfo ? `<span class="badge-rec" style="background:${recInfo.color}; border: 1px solid ${badgeBorder}; color: #fff; margin-left:6px;">${esc(recInfo.badge)}</span>` : "";
        return `<div class="model-card bg-white dark:bg-[#101624] border border-slate-200 dark:border-slate-800" style="border-top:3px solid ${c} !important;">
            <div class="rank text-slate-500 dark:text-slate-400">#${pos + 1} por score</div>
            <h3><i class="dot" style="background:${c}"></i>${esc(id)} <span class="text-slate-500 dark:text-slate-400" style="font-size:.8rem">(${esc(m.size)})</span></h3>
            <span class="role" style="background:${c}22;color:${c};border:1px solid ${c}66">${esc(m.profile.role)}</span>${rec}
            <div class="score-wrap">${scoreRing(m.efficiency_score, c)}
                <div style="font-size:.78rem;" class="text-slate-700 dark:text-slate-400">Score de eficiencia compuesto<br>
                <b class="text-slate-900 dark:text-white">Precisión ${fmt(m.accuracy_pct)}%</b> · Rúbrica ${fmt(m.rubric, 2)}/5</div></div>
            <div class="mstats">
                <div class="mstat"><b>${fmt(m.ttft_ms)}</b><span>TTFT ms</span></div>
                <div class="mstat"><b>${fmt(m.tokens_per_sec)}</b><span>tok/s</span></div>
                <div class="mstat"><b>${fmt(m.vram_gb, 1)}</b><span>VRAM GB</span></div>
                <div class="mstat"><b>${fmt(m.latency_p50_ms / 1000, 2)}</b><span>Lat. p50 s</span></div>
                <div class="mstat"><b>${fmt(m.partial_f1, 3)}</b><span>Coincidencia Parcial</span></div>
                <div class="mstat"><b>${fmtC(m.tokens_per_wh)}</b><span>tok/Wh</span></div>
            </div>
            <div class="mdesc text-slate-700 dark:text-slate-400">${esc(m.profile.description)}</div></div>`;
    }).join("");

    document.getElementById("radarChart").innerHTML = radarChart(M, ids, radarHidden);

    // Descomposición del score (barras apiladas)
    const segs = [
        ["accuracy", "Precisión (40%)", "#ad3333"],
        ["rubric", "Rúbrica (20%)", "#003366"],
        ["speed", "Velocidad (20%)", light ? "#0284c7" : "#0055a5"],
        ["vram_efficiency", "Eficiencia VRAM (20%)", light ? "#475569" : "#DADADA"]
    ];
    const W = 520, rowH = 56, padL = 150, padR = 60, top = 24, span = W - padL - padR, H = top + rank.length * rowH + 10;
    const gridLineCol = light ? "#cbd5e1" : "#1f2a3d";
    let s = `<svg viewBox="0 0 ${W} ${H}" class="chart">`;
    [0, 0.25, 0.5, 0.75, 1].forEach(g => { const x = padL + g * span; s += `<line x1="${x}" x2="${x}" y1="${top - 6}" y2="${H - 6}" stroke="${gridLineCol}"/><text x="${x}" y="${top - 10}" text-anchor="middle" class="dim">${fmt(g, 2)}</text>`; });
    rank.forEach((id, i) => {
        const y = top + i * rowH + 10, comp = M[id].score_components; let x = padL;
        s += `<text x="${padL - 8}" y="${y + 20}" text-anchor="end" style="font-weight:700;fill:${color(id, ids.indexOf(id))}">${esc(id)}</text>`;
        segs.forEach(([k, name, c]) => {
            const w = (comp[k] || 0) * span;
            s += `<rect x="${x}" y="${y}" width="${Math.max(w, 0)}" height="30" fill="${c}" opacity="0.85"><title>${name}: ${fmt(comp[k], 4)}</title></rect>`;
            if (w > 34) s += `<text x="${x + w / 2}" y="${y + 19}" text-anchor="middle" style="font-size:10px;font-weight:700;fill:#ffffff">${fmt(comp[k], 3)}</text>`;
            x += w;
        });
        s += `<text x="${x + 6}" y="${y + 20}" class="val">${fmt(M[id].efficiency_score, 3)}</text>`;
    });
    s += "</svg>";
    document.getElementById("scoreChart").innerHTML = s;
    document.getElementById("scoreLegend").innerHTML = segs.map(([, n, c]) => `<span><i class="dot" style="background:${c}"></i>${n}</span>`).join("");

    // Gráficos de rendimiento
    const items = f => ids.map((id, i) => ({ label: id, value: f(M[id]), color: color(id, i) }));
    document.getElementById("perfCharts").innerHTML =
        hBarChart({ title: "TTFT promedio (prefill)", unit: "ms", items: items(m => m.ttft_ms), lowerIsBetter: true }) +
        hBarChart({ title: "Velocidad de decodificación", unit: "tok/s", items: items(m => m.tokens_per_sec) }) +
        hBarChart({ title: "Latencia total p50", unit: "ms", items: items(m => m.latency_p50_ms), lowerIsBetter: true, decimals: 0 }) +
        hBarChart({ title: "Latencia total p95", unit: "ms", items: items(m => m.latency_p95_ms), lowerIsBetter: true, decimals: 0 }) +
        hBarChart({ title: "VRAM (Declarada/Estimada) pico (límite de referencia 8 GB)", unit: "GB", items: items(m => m.vram_gb), lowerIsBetter: true, limit: d.vram_limit_gb, limitLabel: "8 GB" }) +
        hBarChart({ title: "Exactitud diagnóstica completa", unit: "%", items: items(m => m.accuracy_pct) }) +
        hBarChart({ title: "Causa raíz estricta", unit: "%", items: items(m => m.strict_root_cause_accuracy_pct !== undefined ? m.strict_root_cause_accuracy_pct : m.accuracy_pct) });

    document.getElementById("energyCharts").innerHTML =
        hBarChart({ title: "Energía total estimada", unit: "µWh", items: items(m => m.energy_uwh), lowerIsBetter: true, compact: true }) +
        hBarChart({ title: "CO₂ estimado", unit: "µg", items: items(m => m.co2_ug), lowerIsBetter: true, compact: true }) +
        hBarChart({ title: "Eficiencia energética", unit: "tok/Wh", items: items(m => m.tokens_per_wh), compact: true });

    // Tabla multidimensional
    const cols = [
        ["Diag. Completo", m => m.accuracy_pct, v => fmt(v) + "%", false],
        ["Causa Raíz Estricta", m => m.strict_root_cause_accuracy_pct !== undefined ? m.strict_root_cause_accuracy_pct : m.accuracy_pct, v => fmt(v) + "%", false],
        ["Puntaje de Coincidencia Parcial", m => m.partial_f1, v => fmt(v, 3), false],
        ["Evidencia", m => m.evidence_rate_pct, v => fmt(v) + "%", false],
        ["TTFT", m => m.ttft_ms, v => fmt(v) + " ms", true],
        ["Tok/s", m => m.tokens_per_sec, v => fmt(v), false],
        ["Lat. p50", m => m.latency_p50_ms, v => fmt(v, 0) + " ms", true],
        ["Lat. p95", m => m.latency_p95_ms, v => fmt(v, 0) + " ms", true],
        ["VRAM (Declarada/Estimada)", m => m.vram_gb, v => fmt(v, 1) + " GB", true],
        ["Rúbrica", m => m.rubric, v => fmt(v, 2) + " / 5", false],
        ["tok/Wh", m => m.tokens_per_wh, v => fmtC(v), false],
        ["Score", m => m.efficiency_score, v => fmt(v, 3), false]
    ];
    let t = `<table class="t"><thead><tr><th>Modelo</th><th>Parám.</th>${cols.map(c => `<th>${c[0]}</th>`).join("")}</tr></thead><tbody>`;
    const bests = cols.map(c => { const v = ids.map(i => c[1](M[i])); return c[3] ? Math.min.apply(null, v) : Math.max.apply(null, v); });
    rank.forEach(id => {
        t += `<tr><td><i class="dot" style="background:${color(id, ids.indexOf(id))}"></i> <b>${esc(id)}</b></td><td>${esc(M[id].size)}</td>`;
        cols.forEach((c, ci) => { const v = c[1](M[id]); t += `<td class="${v === bests[ci] ? "best" : ""}">${c[2](v)}</td>`; });
        t += "</tr>";
    });
    document.getElementById("matrixTable").innerHTML = t + "</tbody></table>";

    // Heatmap por escenario
    const heatColor = p => p === null ? "#1e293b" : `hsl(${Math.round(p * 1.3)}, 65%, ${p === 100 ? 28 : 32}%)`;
    let h = `<table class="t heat"><thead><tr><th>Categoría</th><th>Escenario</th><th>Clase de falla</th>${ids.map((id, i) => `<th style="text-align:center;color:${color(id, i)}">${esc(id)}</th>`).join("")}</tr></thead><tbody>`;
    d.scenario_ids.forEach(sid => {
        const meta = d.scenario_meta[sid] || {};
        h += `<tr><td>${esc(meta.category)}</td><td><b>${esc(sid)}</b></td><td style="color:var(--text-dim)">${esc(meta.fault_class)}</td>`;
        ids.forEach(id => { const p = d.scenario_matrix[sid][id]; h += `<td class="cell" style="background:${heatColor(p)}">${p === null ? "—" : fmt(p, 0) + "%"}</td>`; });
        h += "</tr>";
    });
    document.getElementById("scenarioHeat").innerHTML = h + "</tbody></table>";

    // Conclusiones
    document.getElementById("conclusions").innerHTML = (d.conclusions || []).map((c, i) => {
        const col = color(c.model_id, ids.indexOf(c.model_id));
        return `<div class="concl" style="border-left-color:${col}"><h4 style="color:${col}">${i + 1}. ${esc(c.title)}</h4><p>${esc(c.text)}</p></div>`;
    }).join("");
    document.getElementById("compMd").textContent = d.report_markdown || "(sin informe markdown)";
}

// ───────────────────────── Panel 4.1.2 ─────────────────────────
const CHI2_CRIT = { 1: 3.841, 2: 5.991, 3: 7.815, 4: 9.488, 5: 11.070, 6: 12.592 };
function strength(r) {
    const a = Math.abs(r);
    if (a < 0.1) return ["Nula", "no"];
    if (a < 0.3) return ["Débil", "no"];
    if (a < 0.5) return ["Moderada", "warn"];
    if (a < 0.7) return ["Considerable", "warn"];
    return ["Fuerte", "ok"];
}
function isUndefinedCorr(c) { return c.spearman_rho === 0 && c.spearman_p === 1 && c.pearson_r === 0 && c.pearson_p === 1; }
function effClass(d) { const a = Math.abs(d); return a < 0.2 ? "no" : a < 0.5 ? "warn" : a < 0.8 ? "warn" : "bad"; }

function renderCorrelacion(d) {
    const ids = d.model_ids, C = d.correlations, KW = d.kruskal_wallis, df = Math.max(1, (d.n_models || ids.length) - 1);
    const crit = CHI2_CRIT[df] || 5.991;
    const corrKeys = Object.keys(C), kwKeys = Object.keys(KW);
    const sigCorr = corrKeys.filter(k => C[k].significant_005);
    const sigKw = kwKeys.filter(k => KW[k].significant_005);
    let largeEff = 0, totalEff = 0;
    Object.values(d.effect_sizes).forEach(pairs => Object.values(pairs).forEach(e => { totalEff++; if (Math.abs(e.cohens_d) >= 0.8) largeEff++; }));

    document.getElementById("corrKpis").innerHTML =
        kpi(d.n_total, "Muestras (corridas)", null, "Tamaño muestral total para el cómputo de significancia estadística") +
        kpi(d.n_models, "Modelos comparados", null, "Número de arquitecturas SLM evaluadas en la matriz cruzada") +
        kpi(`${sigCorr.length}/${corrKeys.length}`, "Correlaciones significativas", "#14b8a6", "Métricas con Spearman rho y p < 0.05 frente al tamaño de parámetros del modelo") +
        kpi(`${sigKw.length}/${kwKeys.length}`, "Kruskal-Wallis con p < 0,05", "#818cf8", "Pruebas H de Kruskal-Wallis que rechazan la hipótesis nula H0 con 95% de confianza") +
        kpi(`${largeEff}/${totalEff}`, "Efectos grandes (|d| ≥ 0,8)", "#f87171", "Comparaciones por pares con magnitud d de Cohen superior al umbral estándar de efecto grande") +
        kpi("α = 0,05", "Nivel de significancia", null, "Nivel de significancia alfa estándar (probabilidad de error tipo I <= 5%)");

    // Hallazgos
    const F = [];
    corrKeys.filter(k => C[k].significant_005).sort((a, b) => Math.abs(C[b].spearman_rho) - Math.abs(C[a].spearman_rho)).forEach(k => {
        const c = C[k], dir = c.spearman_rho > 0 ? "aumenta" : "disminuye", [st] = strength(c.spearman_rho);
        F.push(["📈", `<b>${lbl(k)}</b> ${dir} con el tamaño del modelo: correlación <b>${st.toLowerCase()}</b> (ρ = ${fmt(c.spearman_rho, 3)}, r = ${fmt(c.pearson_r, 3)}, p ${fmtP(c.spearman_p).startsWith("&lt;") ? "" : "= "}${fmtP(c.spearman_p)}).`]);
    });
    const undef = corrKeys.filter(k => isUndefinedCorr(C[k]));
    if (undef.length) F.push(["⚖️", `<b>${undef.map(lbl).join(", ")}</b>: correlación no definida porque la métrica es constante entre modelos (varianza nula). Todos los modelos alcanzan el mismo desempeño diagnóstico, por lo que la calidad no depende del número de parámetros en este dataset.`]);
    if (sigKw.length) F.push(["🧪", `Kruskal-Wallis rechaza H₀ (p &lt; 0,05) en <b>${sigKw.map(lbl).join(", ")}</b>: la elección del modelo tiene un impacto estadísticamente significativo en el rendimiento computacional.`]);
    const nsKw = kwKeys.filter(k => !KW[k].significant_005);
    if (nsKw.length) F.push(["✅", `Sin diferencias significativas entre modelos en <b>${nsKw.map(lbl).join(", ")}</b>: la calidad diagnóstica es equivalente en la terna evaluada.`]);
    if (largeEff) F.push(["📏", `${largeEff} de ${totalEff} comparaciones por pares presentan un tamaño de efecto <b>grande</b> (|d| ≥ 0,8), lo que confirma que las diferencias no solo son significativas sino también relevantes en la práctica.`]);
    F.push(["ℹ️", `Advertencia metodológica: el eje X (parámetros) solo toma ${d.n_models} niveles distintos; las correlaciones reflejan diferencias entre modelos y pueden estar confundidas con la arquitectura (no solo con el tamaño).`]);
    document.getElementById("findings").innerHTML = F.map(([ic, tx]) => `<div class="finding"><span class="ic">${ic}</span><div>${tx}</div></div>`).join("");

    // Gráfico divergente de correlaciones
    {
        const W = 600, padL = 175, padR = 40, rowH = 46, top = 26, span = W - padL - padR, cx = padL + span / 2, H = top + corrKeys.length * rowH + 8;
        const light = isLight();
        const gridCol = light ? "#e2e8f0" : "#1f2a3d";
        const centerLineCol = light ? "#94a3b8" : "#64748b";
        let s = `<svg viewBox="0 0 ${W} ${H}" class="chart">`;
        [-1, -0.5, 0, 0.5, 1].forEach(g => { const x = cx + g * span / 2; s += `<line x1="${x}" x2="${x}" y1="${top - 6}" y2="${H - 4}" stroke="${g === 0 ? centerLineCol : gridCol}"/><text x="${x}" y="${top - 10}" text-anchor="middle" class="dim">${fmt(g, 1)}</text>`; });
        corrKeys.forEach((k, i) => {
            const c = C[k], y = top + i * rowH + 4, und = isUndefinedCorr(c);
            s += `<text x="${padL - 8}" y="${y + 20}" text-anchor="end">${esc(lbl(k))}</text>`;
            if (und) { s += `<text x="${cx + 6}" y="${y + 20}" class="dim">no definida (métrica constante)</text>`; return; }
            [[c.spearman_rho, c.spearman_p, "#0055a5", 0, "ρ"], [c.pearson_r, c.pearson_p, "#ad3333", 18, "r"]].forEach(([v, p, col, dy, name]) => {
                const w = Math.abs(v) * span / 2, x = v >= 0 ? cx : cx - w, sig = p < 0.05;
                s += `<rect x="${x}" y="${y + dy}" width="${Math.max(w, 1)}" height="14" rx="3" fill="${col}" opacity="${sig ? 0.95 : 0.3}" stroke="${col}"><title>${name} = ${fmt(v, 4)} · p = ${p}</title></rect>`;
                const tx = v >= 0 ? cx + w + 4 : cx - w - 4;
                s += `<text x="${tx}" y="${y + dy + 11}" text-anchor="${v >= 0 ? "start" : "end"}" class="val">${fmt(v, 3)}${sig ? " *" : ""}</text>`;
            });
        });
        document.getElementById("corrChart").innerHTML = s + "</svg>";
    }

    // Kruskal-Wallis
    {
        const items = kwKeys.map(k => ({ k, h: KW[k].H_statistic, p: KW[k].p_value, sig: KW[k].significant_005 }));
        const W = 600, padL = 175, padR = 140, rowH = 40, top = 18, span = W - padL - padR, H = top + items.length * rowH + 8;
        const maxH = Math.max.apply(null, items.map(i => i.h).concat([crit])) * 1.08 || 1;
        const light = isLight();
        const strokeBorder = light ? "#cbd5e1" : "#DADADA";
        let s = `<svg viewBox="0 0 ${W} ${H}" class="chart">`;
        items.forEach((it, i) => {
            const y = top + i * rowH, w = Math.max(it.h / maxH * span, 1);
            s += `<text x="${padL - 8}" y="${y + 22}" text-anchor="end">${esc(lbl(it.k))}</text>`;
            s += `<rect x="${padL}" y="${y + 9}" width="${w}" height="20" rx="4" fill="${it.sig ? "#ad3333" : "#003366"}" stroke="${strokeBorder}" stroke-width="0.5"><title>H = ${it.h} · p = ${it.p}</title></rect>`;
            s += `<text x="${padL + w + 6}" y="${y + 23}" class="val">H=${fmt(it.h, 2)} · p ${fmtP(it.p).startsWith("&lt;") ? "" : "= "}${fmtP(it.p)}</text>`;
        });
        const x = padL + crit / maxH * span;
        s += `<line x1="${x}" x2="${x}" y1="6" y2="${H - 2}" stroke="#ad3333" stroke-width="1.5" stroke-dasharray="4 3"/><text x="${x + 4}" y="12" class="lim">χ²(${df}; 0,05) = ${fmt(crit, 3)}</text>`;
        document.getElementById("kwChart").innerHTML = s + "</svg>";
    }

    // Tabla de correlaciones
    {
        let t = `<table class="t"><thead><tr><th>Métrica</th><th>Spearman ρ</th><th>p-value</th><th>Pearson r</th><th>p-value</th><th>Fuerza (|ρ|)</th><th>Dirección</th><th>Kruskal-Wallis H</th><th>p-value KW</th><th>Significativo</th></tr></thead><tbody>`;
        corrKeys.forEach(k => {
            const c = C[k], kw = KW[k] || {}, und = isUndefinedCorr(c), [st, cls] = strength(c.spearman_rho);
            const dir = und ? "—" : (c.spearman_rho > 0 ? "▲ positiva" : c.spearman_rho < 0 ? "▼ negativa" : "—");
            t += `<tr><td><b>${esc(lbl(k))}</b></td><td>${und ? "—" : fmt(c.spearman_rho, 4)}</td><td>${und ? "—" : fmtP(c.spearman_p)}</td>
                <td>${und ? "—" : fmt(c.pearson_r, 4)}</td><td>${und ? "—" : fmtP(c.pearson_p)}</td>
                <td>${und ? '<span class="pill no">No definida</span>' : `<span class="pill ${cls}">${st}</span>`}</td><td>${dir}</td>
                <td>${fmt(kw.H_statistic, 3)}</td><td>${fmtP(kw.p_value)}</td>
                <td>${c.significant_005 ? '<span class="pill ok">Sí (p &lt; 0,05)</span>' : '<span class="pill no">No</span>'}</td></tr>`;
        });
        document.getElementById("corrTable").innerHTML = t + "</tbody></table>";
    }

    // Forest plots bootstrap
    {
        const ciMetrics = Object.keys(d.bootstrap_ci_95[ids[0]] || {});
        const units = { ttft_ms: "ms", tokens_per_sec: "tok/s", total_time_ms: "ms", energy_kwh: "kWh" };
        const light = isLight();
        const gridCol = light ? "#cbd5e1" : "#1f2a3d";
        const centerFill = light ? "#ffffff" : "#0f172a";
        document.getElementById("ciCharts").innerHTML = ciMetrics.map(mk => {
            const rows = ids.map((id, i) => ({ id, lo: d.bootstrap_ci_95[id][mk][0], hi: d.bootstrap_ci_95[id][mk][1], mean: (d.descriptives[id][mk] || {}).mean, c: color(id, i) }));
            let mn = Math.min.apply(null, rows.map(r => r.lo)), mx = Math.max.apply(null, rows.map(r => r.hi));
            const pad = (mx - mn) * 0.12 || Math.abs(mx) * 0.1 || 1; mn -= pad; mx += pad;
            const W = 460, padL = 140, padR = 20, rowH = 40, top = 10, span = W - padL - padR, H = top + rows.length * rowH + 26;
            const X = v => padL + (v - mn) / (mx - mn) * span;
            const small = mk === "energy_kwh";
            const f = v => small ? (v * 1e6).toFixed(1) + " µWh" : fmt(v, 1);
            let s = `<svg viewBox="0 0 ${W} ${H}" class="chart">`;
            for (let g = 0; g <= 4; g++) { const v = mn + (mx - mn) * g / 4, x = X(v); s += `<line x1="${x}" x2="${x}" y1="${top}" y2="${H - 22}" stroke="${gridCol}"/><text x="${x}" y="${H - 8}" text-anchor="middle" class="dim">${f(v)}</text>`; }
            rows.forEach((r, i) => {
                const y = top + i * rowH + rowH / 2;
                s += `<text x="${padL - 8}" y="${y + 4}" text-anchor="end">${esc(r.id)}</text>`;
                s += `<line x1="${X(r.lo)}" x2="${X(r.hi)}" y1="${y}" y2="${y}" stroke="${r.c}" stroke-width="3"/>`;
                s += `<line x1="${X(r.lo)}" x2="${X(r.lo)}" y1="${y - 7}" y2="${y + 7}" stroke="${r.c}" stroke-width="2"/><line x1="${X(r.hi)}" x2="${X(r.hi)}" y1="${y - 7}" y2="${y + 7}" stroke="${r.c}" stroke-width="2"/>`;
                if (r.mean !== undefined) s += `<circle cx="${X(r.mean)}" cy="${y}" r="5" fill="${centerFill}" stroke="${r.c}" stroke-width="2.5"><title>${esc(r.id)} · media ${f(r.mean)} · IC95% [${f(r.lo)}, ${f(r.hi)}]</title></circle>`;
            });
            s += "</svg>";
            return `<div class="chart-card"><div class="chart-title">${esc(lbl(mk))}<span class="hint">IC 95% ${small ? "(µWh)" : "(" + (units[mk] || "") + ")"}</span></div>${s}</div>`;
        }).join("");
    }

    // Tabla de tamaño del efecto
    {
        const all = []; Object.values(d.effect_sizes).forEach(p => Object.values(p).forEach(e => all.push(Math.abs(e.cohens_d))));
        const maxD = Math.max.apply(null, all.concat([1]));
        let t = `<table class="t"><thead><tr><th>Métrica</th><th>Comparación</th><th>d de Cohen</th><th style="min-width:200px">Magnitud (− ← 0 → +)</th><th>Interpretación</th></tr></thead><tbody>`;
        Object.entries(d.effect_sizes).forEach(([mk, pairs]) => {
            Object.entries(pairs).forEach(([pk, e]) => {
                const v = e.cohens_d, w = Math.abs(v) / maxD * 50, left = v >= 0 ? 50 : 50 - w, col = Math.abs(v) >= 0.8 ? "#f87171" : Math.abs(v) >= 0.5 ? "#fbbf24" : Math.abs(v) >= 0.2 ? "#fde68a" : "#64748b";
                const [a, b] = pk.split(" vs ");
                t += `<tr><td><b>${esc(lbl(mk))}</b></td><td><span style="color:${color(a)};font-weight:700;">${esc(a)}</span> <span style="color:var(--text-dim);font-weight:600;">vs</span> <span style="color:${color(b)};font-weight:700;">${esc(b)}</span></td>
                    <td><b>${fmt(v, 3)}</b></td><td><div class="minibar"><span class="mid"></span><i style="left:${left}%;width:${w}%;background:${col}"></i></div></td>
                    <td><span class="pill ${effClass(v)}">${esc(e.interpretation)}</span></td></tr>`;
            });
        });
        document.getElementById("effectTable").innerHTML = t + "</tbody></table>";
    }

    // Descriptivos
    const sel = document.getElementById("descMetric");
    const dkeys = Object.keys(d.descriptives[ids[0]] || {});
    sel.innerHTML = dkeys.map(k => `<option value="${k}">${esc(lbl(k))}</option>`).join("");
    sel.onchange = () => renderDesc(d, sel.value);
    renderDesc(d, dkeys[0]);
    document.getElementById("corrMd").textContent = d.report_markdown || "";
}

function renderDesc(d, mk) {
    const ids = d.model_ids, small = mk === "energy_kwh";
    const f = v => small ? (v * 1e6).toFixed(2) + " µWh" : fmt(v, 2);
    const rows = ids.map(id => ({ id, s: d.descriptives[id][mk] }));
    const gmin = Math.min.apply(null, rows.map(r => r.s.min)), gmax = Math.max.apply(null, rows.map(r => r.s.max));
    const P = v => gmax === gmin ? 50 : (v - gmin) / (gmax - gmin) * 100;
    const light = isLight();
    const p50Col = light ? "#0f172a" : "#f8fafc";
    let t = `<table class="t"><thead><tr><th>Modelo</th><th>Media</th><th>σ</th><th>CV %</th><th>Mín</th><th>p50</th><th>p95</th><th>Máx</th><th>N</th><th style="min-width:220px">Rango comparado</th></tr></thead><tbody>`;
    rows.forEach((r, i) => {
        const s = r.s, c = color(r.id, i);
        t += `<tr><td><i class="dot" style="background:${c}"></i> <b style="color:${c}">${esc(r.id)}</b></td><td><b>${f(s.mean)}</b></td><td>${f(s.std)}</td><td>${fmt(s.cv, 2)}</td><td>${f(s.min)}</td><td>${f(s.p50)}</td><td>${f(s.p95)}</td><td>${f(s.max)}</td><td>${s.n}</td>
            <td><div class="minibar"><i style="left:${P(s.min)}%;width:${Math.max(P(s.max) - P(s.min), 1)}%;background:${c};opacity:${light ? '.65' : '.45'}"></i>
            <i style="left:calc(${P(s.p50)}% - 2px);width:4px;background:${p50Col}"></i><i style="left:calc(${P(s.p95)}% - 2px);width:4px;background:#f87171"></i></div></td></tr>`;
    });
    document.getElementById("descTable").innerHTML = t + "</tbody></table>";
}

// ───────────────────────── Selección y Gestión de Modelos ─────────────────────────
let AVAILABLE_MODELS = [];
let SELECTED_MODELS = new Set();

async function fetchModelSelection() {
    try {
        const r = await fetch("/api/models/selection");
        const data = await r.json();
        AVAILABLE_MODELS = data.available_models || [];
        SELECTED_MODELS = new Set(data.selected_models || []);
        renderModelChips();
        renderModelManageList();
        updateExportUrls();
    } catch(e) {
        console.error("Error al cargar selección de modelos:", e);
    }
}

function renderModelChips() {
    const container = document.getElementById("modelSelectionChips");
    if (!container) return;
    if (AVAILABLE_MODELS.length === 0) {
        container.innerHTML = '<span style="font-size:0.75rem;color:#94a3b8;">No se detectaron modelos con corridas registradas.</span>';
        return;
    }
    let html = "";
    AVAILABLE_MODELS.forEach((m, i) => {
        const isChecked = SELECTED_MODELS.has(m.id);
        const c = color(m.id, i);
        html += `
            <label class="ms-chip bg-slate-100 dark:bg-[#0A0E16] text-slate-800 dark:text-white border-slate-300 dark:border-slate-700 ${isChecked ? 'active' : ''}" id="chip_${esc(m.id)}">
                <input type="checkbox" ${isChecked ? 'checked' : ''} onchange="toggleModelChip('${esc(m.id)}', this.checked)">
                <i class="dot" style="background:${c}"></i>
                <span>${esc(m.name || m.id)}</span>
                <span class="runs-badge">${m.n_runs} corridas</span>
            </label>
        `;
    });
    container.innerHTML = html;
    const cnt = document.getElementById("msSelectedCount");
    if (cnt) cnt.textContent = `(${SELECTED_MODELS.size} de ${AVAILABLE_MODELS.length} incluidos)`;
}

function toggleModelChip(mid, checked) {
    if (checked) SELECTED_MODELS.add(mid);
    else SELECTED_MODELS.delete(mid);
    const chip = document.getElementById("chip_" + mid);
    if (chip) chip.classList.toggle("active", checked);
    const cnt = document.getElementById("msSelectedCount");
    if (cnt) cnt.textContent = `(${SELECTED_MODELS.size} de ${AVAILABLE_MODELS.length} incluidos)`;
}

function selectAllModels(checkAll) {
    SELECTED_MODELS.clear();
    if (checkAll) {
        AVAILABLE_MODELS.forEach(m => SELECTED_MODELS.add(m.id));
    }
    renderModelChips();
}

function updateExportUrls() {
    const list = Array.from(SELECTED_MODELS);
    const param = list.length === AVAILABLE_MODELS.length || list.length === 0 ? "" : "?models=" + encodeURIComponent(list.join(","));
    const excel = document.getElementById("btnAnalyticsExcel");
    const comp = document.getElementById("btnAnalyticsPdfComp");
    const corr = document.getElementById("btnAnalyticsPdfCorr");
    const cons = document.getElementById("btnAnalyticsPdfCons");
    const json = document.getElementById("btnAnalyticsJson");
    if (excel) excel.href = "/api/export/excel" + param;
    if (comp) comp.href = "/api/export/pdf/comparative" + param;
    if (corr) corr.href = "/api/export/pdf/correlation" + param;
    if (cons) cons.href = "/api/export/pdf/consolidated" + param;
    if (json) json.href = "/api/export/json" + param;

    // Actualizar enlaces en la barra standalone
    const sExcel = document.getElementById("standaloneBtnExcel");
    const sPdf = document.getElementById("standaloneBtnPdf");
    const sJson = document.getElementById("standaloneBtnJson");
    if (sExcel) sExcel.href = "/api/export/excel" + param;
    if (sPdf) {
        const base = sPdf.getAttribute("data-base-href") || sPdf.href.split("?")[0];
        sPdf.href = base + param;
    }
    if (sJson) sJson.href = "/api/export/json" + param;

    try {
        if (window.parent && window.parent !== window && typeof window.parent.onModelSelectionChanged === 'function') {
            window.parent.onModelSelectionChanged(param);
        }
    } catch(e) {}
}

async function applyModelSelection() {
    if (SELECTED_MODELS.size === 0) {
        showCustomAlert("Debe seleccionar al menos un modelo para generar los informes y entregables.", "Validación de Selección", "warning");
        return;
    }
    const list = Array.from(SELECTED_MODELS);
    try {
        const resp = await fetch("/api/models/selection", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ models: list })
        });
        if (!resp.ok) throw new Error("Fallo al persistir selección");
        updateExportUrls();
        loadActiveReports();
    } catch(e) {
        showCustomAlert("Error al aplicar selección: " + e.message, "Error al Aplicar", "error");
    }
}

// ───────────────────────── Modal de Alerta Personalizado (Sistema Anti-Native Alert) ─────────────────────────
function showCustomAlert(message, title, type) {
    title = title || "Validación de Selección";
    type = type || "warning";
    const modal = document.getElementById("customAlertModal");
    if (!modal) {
        console.warn("[CustomAlert]", title, message);
        return;
    }
    const titleEl = document.getElementById("customAlertTitle");
    const msgEl = document.getElementById("customAlertMsg");
    const iconWrapper = document.getElementById("customAlertIconWrapper");
    const iconEl = document.getElementById("customAlertIcon");
    const box = modal.querySelector(".custom-alert-box");

    if (titleEl) titleEl.textContent = title;
    if (msgEl) msgEl.textContent = message;

    if (iconWrapper) {
        iconWrapper.className = "custom-alert-icon-wrapper type-" + type;
    }

    if (box) {
        if (type === "error") {
            box.style.borderTopColor = "#ad3333";
            box.style.boxShadow = "0 20px 50px rgba(0, 0, 0, 0.8), 0 0 24px rgba(173, 51, 51, 0.25)";
        } else if (type === "info") {
            box.style.borderTopColor = "#0284c7";
            box.style.boxShadow = "0 20px 50px rgba(0, 0, 0, 0.8), 0 0 24px rgba(2, 132, 199, 0.25)";
        } else if (type === "success") {
            box.style.borderTopColor = "#10b981";
            box.style.boxShadow = "0 20px 50px rgba(0, 0, 0, 0.8), 0 0 24px rgba(16, 185, 129, 0.25)";
        } else {
            box.style.borderTopColor = "#f59e0b";
            box.style.boxShadow = "0 20px 50px rgba(0, 0, 0, 0.8), 0 0 24px rgba(245, 158, 11, 0.25)";
        }
    }

    if (iconEl) {
        if (type === "error") {
            iconEl.innerHTML = '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>';
        } else if (type === "info") {
            iconEl.innerHTML = '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>';
        } else if (type === "success") {
            iconEl.innerHTML = '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>';
        } else {
            iconEl.innerHTML = '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>';
        }
    }

    modal.classList.add("active");
    const btn = document.getElementById("customAlertBtn");
    if (btn) {
        setTimeout(() => btn.focus(), 50);
    }
}

function closeCustomAlert() {
    const modal = document.getElementById("customAlertModal");
    if (modal) {
        modal.classList.remove("active");
    }
}

// Sobreescritura universal del alert nativo del navegador para que NUNCA vuelva a salir el popup del SO
window.alert = function(msg) {
    showCustomAlert(msg, "Validación de Selección", "warning");
};

// Accesibilidad con teclado: Enter o Escape cierran la alerta
document.addEventListener("keydown", function(e) {
    const modal = document.getElementById("customAlertModal");
    if (modal && modal.classList.contains("active")) {
        if (e.key === "Escape" || e.key === "Enter") {
            e.preventDefault();
            closeCustomAlert();
        }
    }
});

function loadActiveReports() {
    const list = Array.from(SELECTED_MODELS);
    const param = list.length === AVAILABLE_MODELS.length || list.length === 0 ? "" : "?models=" + encodeURIComponent(list.join(","));
    load("/api/comparative-report" + param, "compLoading", "compBody", d => { COMP = d; renderComparativo(d); });
    load("/api/correlation-analysis" + param, "corrLoading", "corrBody", d => { CORR = d; renderCorrelacion(d); });
}

// ───────────────────────── Modal de Administración / Eliminación ─────────────────────────
function openModelManageModal() {
    renderModelManageList();
    const modal = document.getElementById("modelManageModal");
    if (modal) modal.style.display = "flex";
}

function closeModelManageModal() {
    const modal = document.getElementById("modelManageModal");
    if (modal) modal.style.display = "none";
}

function renderModelManageList() {
    const container = document.getElementById("modelManageList");
    if (!container) return;
    if (AVAILABLE_MODELS.length === 0) {
        container.innerHTML = '<p style="color:#94a3b8;font-size:0.8rem;">No hay modelos registrados actualmente.</p>';
        return;
    }
    let html = "";
    AVAILABLE_MODELS.forEach(m => {
        const badge = m.is_base ? '<span class="tag-base">Terna Base</span>' : '<span class="tag-dyn">Dinámico (Ollama)</span>';
        html += `
            <div class="model-manage-row">
                <div class="model-manage-info">
                    <div class="model-manage-name">
                        <span>${esc(m.name || m.id)}</span>
                        ${badge}
                    </div>
                    <div class="model-manage-sub">
                        <span>ID: <code>${esc(m.id)}</code></span> &bull;
                        <span>Tag: <code>${esc(m.ollama_tag)}</code></span> &bull;
                        <span>${m.n_runs} corridas en resultados.csv</span>
                    </div>
                </div>
                <div>
                    <button type="button" class="btn btn-sm btn-danger" onclick="deleteModelAction('${esc(m.id)}', '${esc(m.name || m.id)}', ${m.n_runs})">
                        🗑️ Eliminar
                    </button>
                </div>
            </div>
        `;
    });
    container.innerHTML = html;
}

window.onParentModelDeleted = async function(modelId) {
    SELECTED_MODELS.delete(modelId);
    await fetchModelSelection();
    loadActiveReports();
};

async function deleteModelAction(modelId, modelName, runsCount) {
    if (window.parent && window.parent !== window && typeof window.parent.triggerDeleteModel === 'function') {
        const modal = document.getElementById("modelManageModal");
        if (modal) modal.style.display = "none";
        window.parent.triggerDeleteModel(modelId, modelName, runsCount);
        return;
    }

    try {
        const resp = await fetch(`/api/models/${encodeURIComponent(modelId)}?purge_ollama=false`, {
            method: "DELETE",
            headers: { "Accept": "application/json" }
        });
        const data = await resp.json();
        if (resp.ok && data.status === "success") {
            SELECTED_MODELS.delete(modelId);
            await fetchModelSelection();
            loadActiveReports();
        }
    } catch(e) {
        console.error("Fallo al eliminar modelo:", e);
    }
}

// ───────────────────────── Inicialización ─────────────────────────
async function load(url, loadingId, bodyId, renderer) {
    const loading = document.getElementById(loadingId);
    try {
        const r = await fetch(url);
        const data = await r.json();
        if (data.error) throw new Error(data.error);
        renderer(data);
        loading.style.display = "none";
        document.getElementById(bodyId).style.display = "block";
        return data;
    } catch (e) {
        loading.className = "err";
        loading.textContent = "Error al cargar datos: " + e.message;
        console.error(e);
    }
}

window.addEventListener("load", () => {
    const isInIframe = (window.self !== window.top);
    if (isInIframe) {
        document.body.classList.add('is-embedded');
        const tb = document.getElementById('standaloneExportToolbar');
        if (tb) tb.style.display = 'none';
    } else {
        document.body.classList.remove('is-embedded');
        document.body.classList.add('is-standalone');
    }

    const params = new URLSearchParams(window.location.search);
    const viewParam = (params.get('view') || params.get('tab') || "").toLowerCase();

    let target = (viewParam || location.hash.slice(1) || "comparativo").toLowerCase();
    if (target.includes("corr")) target = "correlacion";
    else target = "comparativo";

    showTab(target);

    // Cargar selector de modelos y cargar reportes
    fetchModelSelection().then(() => {
        loadActiveReports();
    });
});
window.addEventListener("hashchange", () => {
    const h = location.hash.slice(1);
    if (h === "comparativo" || h === "correlacion") showTab(h);
});

// ================= GESTOR DE TEMA (DÍA / NOCTURNO) =================
function applyTheme(th) {
    document.documentElement.setAttribute('data-theme', th);
    if (th === 'dark') {
        document.documentElement.classList.add('dark');
    } else {
        document.documentElement.classList.remove('dark');
    }
    localStorage.setItem('netdiag_theme', th);
    const icon = document.getElementById('themeToggleIcon');
    const txt = document.getElementById('themeToggleText');
    const tt = document.getElementById('cornerThemeTooltip');
    if (th === 'light') {
        if (icon) icon.innerHTML = '<svg style="width:16px;height:16px;" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"/></svg>';
        if (txt) txt.textContent = 'Modo Noche';
        if (tt) tt.textContent = 'Cambiar a Modo Noche';
    } else {
        if (icon) icon.innerHTML = '<svg style="width:16px;height:16px;" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"/></svg>';
        if (txt) txt.textContent = 'Modo Día';
        if (tt) tt.textContent = 'Cambiar a Modo Día';
    }
    // Sincronizar y repintar gráficos con la paleta de alto contraste correspondiente
    try {
        const compPanel = document.getElementById('panel-comparativo');
        const corrPanel = document.getElementById('panel-correlacion');
        if (COMP && compPanel && compPanel.classList.contains('active')) {
            renderComparativo(COMP);
        } else if (CORR && corrPanel && corrPanel.classList.contains('active')) {
            renderCorrelacion(CORR);
        }
        if (typeof renderModelChips === 'function') {
            renderModelChips();
        }
    } catch(e) {}
}

function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme') || 'dark';
    applyTheme(current === 'light' ? 'dark' : 'light');
}

(function() {
    const saved = localStorage.getItem('netdiag_theme') || 'dark';
    applyTheme(saved);
})();
</script>

<!-- Modal Personalizado de Alerta y Validación (Reemplazo Visual de window.alert) -->
<div id="customAlertModal" class="custom-alert-overlay" onclick="if(event.target === this) closeCustomAlert()">
    <div class="custom-alert-box" role="dialog" aria-modal="true" aria-labelledby="customAlertTitle">
        <div class="custom-alert-top">
            <div class="custom-alert-icon-wrapper" id="customAlertIconWrapper">
                <svg id="customAlertIcon" class="custom-alert-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
                </svg>
            </div>
            <div class="custom-alert-content">
                <div class="custom-alert-header">
                    <h3 id="customAlertTitle" class="custom-alert-title">Validación de Selección</h3>
                    <button type="button" class="custom-alert-close" onclick="closeCustomAlert()" aria-label="Cerrar modal">&times;</button>
                </div>
                <p id="customAlertMsg" class="custom-alert-msg">Debe seleccionar al menos un modelo para generar los informes y entregables.</p>
            </div>
        </div>
        <div class="custom-alert-footer">
            <button type="button" id="customAlertBtn" class="custom-alert-btn" onclick="closeCustomAlert()">
                <span>Entendido</span>
                <kbd class="custom-alert-kbd">Enter</kbd>
            </button>
        </div>
    </div>
</div>

<!-- Modal de Administración / Eliminación de Modelos -->
<div id="modelManageModal" class="modal-overlay" onclick="if(event.target === this) closeModelManageModal()">
    <div class="modal-box">
        <div class="modal-hdr">
            <h3>⚙️ Administración y Eliminación de Modelos</h3>
            <button type="button" class="close-btn" onclick="closeModelManageModal()">&times;</button>
        </div>
        <p style="font-size:0.78rem;color:#cbd5e1;margin-bottom:14px;line-height:1.4;">
            Al eliminar un modelo, se purgan de forma segura todas sus corridas en <code>resultados.csv</code> (con respaldo automático previo),
            sus archivos de diagnóstico generados en <code>data/runs</code>, su registro en el sistema y opcionalmente sus pesos en Ollama.
        </p>
        <div id="modelManageList">
            <!-- Cargado dinámicamente -->
        </div>
        <div style="display:flex;justify-content:flex-end;margin-top:16px;">
            <button type="button" class="btn btn-sm" onclick="closeModelManageModal()">Cerrar</button>
        </div>
    </div>
</div>

<!-- Botón flotante en esquina para Modo Nocturno / Día -->
<div class="theme-toggle-wrapper">
    <button id="themeToggleBtn" class="theme-toggle-corner" onclick="toggleTheme()" aria-label="Alternar Modo Día / Noche">
        <span id="themeToggleIcon" style="display:flex;align-items:center;justify-content:center;"><svg style="width:16px;height:16px;" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"/></svg></span> <span id="themeToggleText" class="sr-only">Modo Día</span>
    </button>
    <div class="theme-toggle-tooltip" id="cornerThemeTooltip">Alternar Modo Día / Noche</div>
</div>
</body>
</html>
"""
