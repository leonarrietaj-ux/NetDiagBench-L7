"""
NetDiagBench-L7: Layer 7 - Exportador de Datos a Excel (OpenPyXL)
Genera un libro de cálculo multioja (.xlsx) profesional, formateado y estilizado
que contiene la totalidad de los datos y análisis del benchmark:
  1. Portada y Resumen Ejecutivo (OE4 / Tarea 4.3.1)
  2. Matriz Multidimensional (OE4 / Tarea 4.2.2)
  3. Desglose por Escenario y Modelo (18 escenarios x 3 modelos)
  4. Huella Energética y de Carbono (Tarea 4.2.2c)
  5. Análisis Correlacional Spearman y Pearson (Tarea 4.1.2)
  6. Prueba de Kruskal-Wallis (Significancia Estadística)
  7. Intervalos de Confianza Bootstrap 95%
  8. Tamaño del Efecto (d de Cohen)
  9. Estadísticos Descriptivos Consolidados
  10. Dataset Granular Completo (162 Corridas de Benchmark)
"""

from pathlib import Path
from typing import Any

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from src.core.config import PROJECT_ROOT
from src.core.logger import logger
from src.layer7_evaluator.statistical_analysis import (
    build_comparative_summary,
    run_correlation_analysis,
)


def sanitize_cell_value(val: Any) -> Any:
    """
    Sanitiza valores de celda para mitigar ataques de CSV/Excel Formula Injection (OWASP).
    Si el valor es una cadena de texto que comienza con '=', '+', '-', '@', '\t', '\r',
    antepone un apóstrofe para forzar el tratamiento del texto como literal de hoja de cálculo.
    También remueve tzinfo de objetos datetime/time para compatibilidad con openpyxl.
    """
    if hasattr(val, "tzinfo") and getattr(val, "tzinfo", None) is not None:
        try:
            return val.replace(tzinfo=None)
        except Exception:
            return str(val)
    if isinstance(val, str) and val:
        stripped = val.strip()
        if stripped and stripped[0] in ("=", "+", "-", "@", "\t", "\r"):
            if stripped.startswith("'"):
                return val
            try:
                float(stripped)
                return val
            except ValueError:
                return f"'{val}"
    return val

# ── Paleta de Colores y Estilos Institucionales ──────────────────────────
NAVY_HEADER = "1E293B"       # Slate / Navy oscuro
NAVY_SUBHEADER = "334155"    # Slate intermedio
ACCENT_BLUE = "0284C7"       # Azul primario
TEAL_HEADER = "0F766E"       # Teal para estadística
ZEBRA_FILL = "F8FAFC"        # Fondo suave alternado
HIGHLIGHT_GREEN = "D1FAE5"   # Verde pastel para mejores métricas
WHITE_TEXT = "FFFFFF"

FONT_NAME = "Segoe UI"
HEADER_FONT = Font(name=FONT_NAME, size=11, bold=True, color=WHITE_TEXT)
TITLE_FONT = Font(name=FONT_NAME, size=14, bold=True, color="0F172A")
SUBTITLE_FONT = Font(name=FONT_NAME, size=10, italic=True, color="64748B")
SECTION_FONT = Font(name=FONT_NAME, size=12, bold=True, color=ACCENT_BLUE)
BOLD_FONT = Font(name=FONT_NAME, size=10, bold=True, color="0F172A")
REGULAR_FONT = Font(name=FONT_NAME, size=10, color="0F172A")

THIN_BORDER_SIDE = Side(border_style="thin", color="CBD5E1")
THIN_BORDER = Border(
    left=THIN_BORDER_SIDE, right=THIN_BORDER_SIDE,
    top=THIN_BORDER_SIDE, bottom=THIN_BORDER_SIDE
)
DOUBLE_BOTTOM = Border(
    left=THIN_BORDER_SIDE, right=THIN_BORDER_SIDE,
    top=THIN_BORDER_SIDE, bottom=Side(border_style="double", color="334155")
)

ALIGN_LEFT = Alignment(horizontal="left", vertical="center")
ALIGN_CENTER = Alignment(horizontal="center", vertical="center")
ALIGN_RIGHT = Alignment(horizontal="right", vertical="center")


def _style_header_row(ws, row_idx: int, bg_hex: str = NAVY_HEADER):
    """Aplica formato de cabecera a una fila completa."""
    fill = PatternFill(start_color=bg_hex, end_color=bg_hex, fill_type="solid")
    for cell in ws[row_idx]:
        if cell.value is not None:
            cell.font = HEADER_FONT
            cell.fill = fill
            cell.alignment = ALIGN_CENTER
            cell.border = THIN_BORDER


def _auto_fit_columns(ws, max_cols: int = 30):
    """Ajusta automáticamente el ancho de las columnas con margen."""
    for col in ws.iter_cols(max_col=max_cols):
        col_letter = get_column_letter(col[0].column)
        max_len = 0
        for cell in col:
            val_str = str(cell.value or "")
            if "\n" in val_str:
                val_str = max(val_str.split("\n"), key=len)
            max_len = max(max_len, len(val_str))
        ws.column_dimensions[col_letter].width = max(max_len + 4, 12)


def export_benchmark_to_excel(
    output_path: Path | None = None,
    csv_path: Path | None = None,
    rows: list[dict[str, Any]] | None = None,
    models: str | list[str] | None = None,
) -> Path:
    """
    Construye y guarda el libro Excel completo con las 10 hojas de evaluación y análisis,
    respetando los modelos seleccionados para el informe.
    """
    if csv_path is None:
        csv_path = PROJECT_ROOT / "data" / "benchmark_results" / "resultados.csv"

    if output_path is None:
        output_path = PROJECT_ROOT / "data" / "benchmark_results" / "benchmark_l7_consolidado.xlsx"

    if rows is None:
        from src.layer7_evaluator.model_management import load_selected_rows
        models_param = ",".join(models) if isinstance(models, list) else models
        rows, _ = load_selected_rows(models_param)

    comp_summary = build_comparative_summary(rows=rows)
    corr_analysis = run_correlation_analysis(rows=rows)

    wb = openpyxl.Workbook()
    # Eliminar hoja por defecto
    default_sheet = wb.active

    # ── Hoja 1: Portada y Resumen Ejecutivo ───────────────────────────────
    ws_portada = wb.create_sheet(title="Resumen Ejecutivo")
    ws_portada.views.sheetView[0].showGridLines = True
    _build_sheet_portada(ws_portada, comp_summary, corr_analysis)

    # ── Hoja 2: Matriz Multidimensional (OE4) ────────────────────────────
    ws_matriz = wb.create_sheet(title="Matriz Multidimensional (OE4)")
    ws_matriz.views.sheetView[0].showGridLines = True
    _build_sheet_matriz(ws_matriz, comp_summary)

    # ── Hoja 3: Desglose por Escenario ────────────────────────────────────
    ws_esc = wb.create_sheet(title="Desglose por Escenario")
    ws_esc.views.sheetView[0].showGridLines = True
    _build_sheet_escenarios(ws_esc, comp_summary)

    # ── Hoja 4: Huella Energética (Tarea 4.2.2c) ─────────────────────────
    ws_energia = wb.create_sheet(title="Huella Energética y CO2")
    ws_energia.views.sheetView[0].showGridLines = True
    _build_sheet_energia(ws_energia, comp_summary)

    # ── Hoja 5: Análisis Correlacional (Tarea 4.1.2) ─────────────────────
    ws_corr = wb.create_sheet(title="Correlaciones (4.1.2)")
    ws_corr.views.sheetView[0].showGridLines = True
    _build_sheet_correlaciones(ws_corr, corr_analysis)

    # ── Hoja 6: Kruskal-Wallis ───────────────────────────────────────────
    ws_kw = wb.create_sheet(title="Kruskal-Wallis (Significancia)")
    ws_kw.views.sheetView[0].showGridLines = True
    _build_sheet_kruskal(ws_kw, corr_analysis)

    # ── Hoja 7: Intervalos de Confianza 95% Bootstrap ────────────────────
    ws_ci = wb.create_sheet(title="IC 95% Bootstrap")
    ws_ci.views.sheetView[0].showGridLines = True
    _build_sheet_bootstrap(ws_ci, corr_analysis)

    # ── Hoja 8: Tamaño del Efecto (d de Cohen) ───────────────────────────
    ws_eff = wb.create_sheet(title="Tamaño del Efecto (Cohen d)")
    ws_eff.views.sheetView[0].showGridLines = True
    _build_sheet_effect_size(ws_eff, corr_analysis)

    # ── Hoja 9: Estadísticos Descriptivos Consolidados ───────────────────
    ws_desc = wb.create_sheet(title="Estadísticos Descriptivos")
    ws_desc.views.sheetView[0].showGridLines = True
    _build_sheet_descriptivos(ws_desc, corr_analysis)

    # ── Hoja 10: Dataset Granular Raw (Corridas) ─────────────────────────
    raw_sheet_title = f"Dataset Raw ({len(rows)} Corridas)"
    ws_raw = wb.create_sheet(title=raw_sheet_title)
    ws_raw.views.sheetView[0].showGridLines = True
    _build_sheet_raw(ws_raw, rows)

    # Eliminar hoja por defecto si sigue presente
    if default_sheet in wb.worksheets:
        wb.remove(default_sheet)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    logger.info(f"Libro Excel generado exitosamente en {output_path}")
    return output_path


# ── Constructores de Hojas Individuales ──────────────────────────────────

def _build_sheet_portada(ws, comp: dict[str, Any], corr: dict[str, Any]):
    """Construye la portada ejecutiva con metadatos y recomendaciones de compromiso."""
    ws["B2"] = "NetDiagBench-L7: Benchmark de Diagnóstico L7 con SLMs Locales"
    ws["B2"].font = TITLE_FONT

    ws["B3"] = "Universidad de Pamplona · Facultad de Ingenierías y Arquitectura · Ingeniería en Telecomunicaciones"
    ws["B3"].font = SUBTITLE_FONT

    ws["B4"] = "Autor: Juan David León Arrieta | Director: Mg. Richard Eliseo Mendoza Gáfaro"
    ws["B4"].font = SUBTITLE_FONT

    # Metadatos del experimento
    ws["B6"] = "1. Metadatos de la Plataforma de Ejecución"
    ws["B6"].font = SECTION_FONT

    metadata = [
        ("Huella de Hardware:", comp.get("hardware_fingerprint", "N/A")),
        ("Presupuesto VRAM Límite:", f"{comp.get('vram_limit_gb', 8.0)} GB"),
        ("Formato de Cuantización:", "Q4_K_M (GGUF / Ollama)"),
        ("Total de Corridas:", comp.get("n_total", 99)),
        ("Modelos Evaluados:", ", ".join(comp.get("model_ids", []))),
        ("Escenarios L7:", comp.get("n_scenarios", 18)),
        ("Semillas Deterministas:", "42, 1337, 2026 (3 repeticiones fijas)"),
    ]

    r = 7
    for label, val in metadata:
        ws[f"B{r}"] = label
        ws[f"B{r}"].font = BOLD_FONT
        ws[f"C{r}"] = val
        ws[f"C{r}"].font = REGULAR_FONT
        r += 1

    # Conclusiones de compromiso
    r += 1
    ws[f"B{r}"] = "2. Conclusiones de Selección de Compromiso (OE4 / Tarea 4.3.1)"
    ws[f"B{r}"].font = SECTION_FONT
    r += 1

    for c in comp.get("conclusions", []):
        ws[f"B{r}"] = c["title"]
        ws[f"B{r}"].font = BOLD_FONT
        ws[f"B{r}"].fill = PatternFill(start_color="E0F2FE", end_color="E0F2FE", fill_type="solid")
        r += 1
        ws[f"B{r}"] = c["text"]
        ws[f"B{r}"].font = REGULAR_FONT
        ws[f"B{r}"].alignment = Alignment(wrap_text=True)
        ws.row_dimensions[r].height = 40
        r += 2

    _auto_fit_columns(ws, max_cols=5)
    ws.column_dimensions["B"].width = 32
    ws.column_dimensions["C"].width = 75


def _build_sheet_matriz(ws, comp: dict[str, Any]):
    """Construye la matriz multidimensional OE4 con desglose de ponderaciones."""
    ws["A1"] = "Matriz de Evaluación Multidimensional de Modelos SLM (OE4 / Tarea 4.2.2)"
    ws["A1"].font = TITLE_FONT

    headers = [
        "Modelo SLM", "Parámetros", "N Corridas", "Precisión Diagnóstica (%)",
        "Acierto Componente (%)", "Puntaje de Coincidencia Parcial", "Tasa Evidencia (%)",
        "TTFT Prom. (ms)", "Velocidad (tok/s)", "Latencia p50 (ms)",
        "Latencia p95 (ms)", "VRAM (Declarada/Estimada) Pico (GB)", "RAM Pico (MB)", "Rúbrica (0-5)",
        "Score Compuesto", "Peso Precisión (40%)", "Peso Rúbrica (20%)",
        "Peso Velocidad (20%)", "Peso VRAM (20%)", "Rol Recomendado"
    ]

    for col_idx, h in enumerate(headers, 1):
        ws.cell(row=3, column=col_idx, value=h)
    _style_header_row(ws, 3, NAVY_HEADER)

    row_idx = 4
    for mid in comp.get("ranking", comp.get("model_ids", [])):
        m = comp["models"][mid]
        sc = m.get("score_components", {})
        values = [
            m["model_id"], m["size"], m["n_runs"], m["accuracy_pct"],
            m["component_accuracy_pct"], m["partial_f1"], m["evidence_rate_pct"],
            m["ttft_ms"], m["tokens_per_sec"], m["latency_p50_ms"],
            m["latency_p95_ms"], m["vram_gb"], m["ram_mb"], m["rubric"],
            m["efficiency_score"], sc.get("accuracy", 0.0), sc.get("rubric", 0.0),
            sc.get("speed", 0.0), sc.get("vram_efficiency", 0.0),
            m.get("profile", {}).get("role", "")
        ]
        for col_idx, v in enumerate(values, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=v)
            cell.font = REGULAR_FONT
            cell.border = THIN_BORDER
            if col_idx in [4, 5, 7]:
                cell.number_format = '0.0"%"'
                cell.alignment = ALIGN_RIGHT
            elif col_idx in [6, 14, 15, 16, 17, 18, 19]:
                cell.number_format = "0.000"
                cell.alignment = ALIGN_RIGHT
            elif col_idx in [8, 9, 10, 11, 12, 13]:
                cell.number_format = "#,##0.0"
                cell.alignment = ALIGN_RIGHT
            else:
                cell.alignment = ALIGN_LEFT

        row_idx += 1

    _auto_fit_columns(ws, max_cols=len(headers))


def _build_sheet_escenarios(ws, comp: dict[str, Any]):
    """Matriz cruzada de escenarios x modelos con porcentaje de precisión."""
    ws["A1"] = "Precisión Diagnóstica Desglosada por Escenario y Modelo"
    ws["A1"].font = TITLE_FONT

    model_ids = comp.get("model_ids", [])
    headers = ["Escenario ID", "Categoría L7", "Clase de Falla"] + [f"{m} (%)" for m in model_ids]

    for col_idx, h in enumerate(headers, 1):
        ws.cell(row=3, column=col_idx, value=h)
    _style_header_row(ws, 3, NAVY_HEADER)

    row_idx = 4
    for sid in comp.get("scenario_ids", []):
        meta = comp.get("scenario_meta", {}).get(sid, {})
        row_vals = [sid, meta.get("category", ""), meta.get("fault_class", "")]
        for mid in model_ids:
            pct = comp.get("scenario_matrix", {}).get(sid, {}).get(mid)
            row_vals.append(pct if pct is not None else "—")

        for col_idx, v in enumerate(row_vals, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=v)
            cell.font = REGULAR_FONT
            cell.border = THIN_BORDER
            if col_idx > 3 and isinstance(v, (int, float)):
                cell.number_format = '0.0"%"'
                cell.alignment = ALIGN_RIGHT
                if v == 100.0:
                    cell.fill = PatternFill(start_color=HIGHLIGHT_GREEN, end_color=HIGHLIGHT_GREEN, fill_type="solid")
            else:
                cell.alignment = ALIGN_LEFT

        row_idx += 1

    _auto_fit_columns(ws, max_cols=len(headers))


def _build_sheet_energia(ws, comp: dict[str, Any]):
    """Estimación de huella energética y emisiones de carbono (Tarea 4.2.2c)."""
    ws["A1"] = "Estimación de Huella Energética y Emisiones de CO2 (Tarea 4.2.2c)"
    ws["A1"].font = TITLE_FONT

    headers = [
        "Modelo SLM", "Parámetros", "Energía Total (kWh)", "CO2 Estimado (kg)",
        "Eficiencia Energética (tok/kWh)", "Consumo Promedio por Inferencia (kWh)"
    ]

    for col_idx, h in enumerate(headers, 1):
        ws.cell(row=3, column=col_idx, value=h)
    _style_header_row(ws, 3, NAVY_HEADER)

    row_idx = 4
    for mid in comp.get("model_ids", []):
        m = comp["models"][mid]
        energy_kwh = m.get("energy_kwh", m.get("energy_uwh", 0.0) * 1e-6)
        co2_kg = m.get("co2_kg", m.get("co2_ug", 0.0) * 1e-6)
        avg_kwh = round(energy_kwh / max(m["n_runs"], 1), 6)
        tokens_per_kwh = round(m.get("tokens_per_wh", 0.0) * 1000.0, 1)
        values = [
            m["model_id"], m["size"], energy_kwh, co2_kg,
            tokens_per_kwh, avg_kwh
        ]
        for col_idx, v in enumerate(values, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=v)
            cell.font = REGULAR_FONT
            cell.border = THIN_BORDER
            if col_idx in [3, 4, 6]:
                cell.number_format = "0.000000"
                cell.alignment = ALIGN_RIGHT
            elif col_idx == 5:
                cell.number_format = "#,##0.0"
                cell.alignment = ALIGN_RIGHT
            else:
                cell.alignment = ALIGN_LEFT

        row_idx += 1

    _auto_fit_columns(ws, max_cols=len(headers))


def _build_sheet_correlaciones(ws, corr: dict[str, Any]):
    """Tabla de correlación Spearman y Pearson (Tarea 4.1.2)."""
    ws["A1"] = "Análisis Correlacional: Tamaño de Modelo vs Métricas (Tarea 4.1.2)"
    ws["A1"].font = TITLE_FONT

    headers = [
        "Métrica Evaluada", "Spearman rho", "p-value Spearman",
        "Pearson r", "p-value Pearson", "Significativo (p < 0.05)",
        "Fuerza de Relación", "Dirección"
    ]

    for col_idx, h in enumerate(headers, 1):
        ws.cell(row=3, column=col_idx, value=h)
    _style_header_row(ws, 3, TEAL_HEADER)

    metric_names = {
        "ttft_ms": "TTFT (Tiempo al Primer Token, ms)",
        "tokens_per_sec": "Velocidad de Decodificación (Tokens/s)",
        "total_time_ms": "Latencia Total de Inferencia (ms)",
        "energy_kwh": "Consumo Energético (kWh)",
        "rubric_score": "Calidad en Rúbrica (0-5)",
        "partial_match_score": "Puntaje de Coincidencia Parcial",
    }

    row_idx = 4
    for mk, c in corr.get("correlations", {}).items():
        rho = c["spearman_rho"]
        abs_rho = abs(rho)
        is_undef = (rho == 0.0 and c["spearman_p"] == 1.0 and c["pearson_r"] == 0.0)

        if is_undef:
            fuerza = "No definida (métrica constante)"
            direccion = "Constante"
        elif abs_rho < 0.1:
            fuerza = "Nula"
            direccion = "Neutral"
        elif abs_rho < 0.3:
            fuerza = "Débil"
            direccion = "Positiva" if rho > 0 else "Negativa"
        elif abs_rho < 0.5:
            fuerza = "Moderada"
            direccion = "Positiva" if rho > 0 else "Negativa"
        elif abs_rho < 0.7:
            fuerza = "Considerable"
            direccion = "Positiva" if rho > 0 else "Negativa"
        else:
            fuerza = "Fuerte"
            direccion = "Positiva" if rho > 0 else "Negativa"

        values = [
            metric_names.get(mk, mk),
            "—" if is_undef else rho,
            "—" if is_undef else c["spearman_p"],
            "—" if is_undef else c["pearson_r"],
            "—" if is_undef else c["pearson_p"],
            "Sí" if c["significant_005"] else "No",
            fuerza, direccion
        ]

        for col_idx, v in enumerate(values, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=v)
            cell.font = REGULAR_FONT
            cell.border = THIN_BORDER
            if col_idx in [2, 4] and isinstance(v, (int, float)):
                cell.number_format = "0.0000"
                cell.alignment = ALIGN_RIGHT
            elif col_idx in [3, 5] and isinstance(v, (int, float)):
                cell.number_format = "0.000000"
                cell.alignment = ALIGN_RIGHT
            else:
                cell.alignment = ALIGN_LEFT

        row_idx += 1

    _auto_fit_columns(ws, max_cols=len(headers))


def _build_sheet_kruskal(ws, corr: dict[str, Any]):
    """Prueba no paramétrica de Kruskal-Wallis entre modelos."""
    ws["A1"] = "Prueba de Kruskal-Wallis: Diferencias Significativas entre Modelos"
    ws["A1"].font = TITLE_FONT

    headers = [
        "Métrica Evaluada", "Estadístico H", "p-value",
        "Significativo (p < 0.05)", "Interpretación de Hipótesis H0"
    ]

    for col_idx, h in enumerate(headers, 1):
        ws.cell(row=3, column=col_idx, value=h)
    _style_header_row(ws, 3, TEAL_HEADER)

    metric_names = {
        "ttft_ms": "TTFT (ms)",
        "tokens_per_sec": "Tokens/s",
        "total_time_ms": "Latencia Total (ms)",
        "energy_kwh": "Energía (kWh)",
        "rubric_score": "Rúbrica (0-5)",
        "partial_match_score": "Puntaje de Coincidencia Parcial",
    }

    row_idx = 4
    for mk, kw in corr.get("kruskal_wallis", {}).items():
        sig = kw["significant_005"]
        interp = (
            "Se rechaza H0: Existen diferencias altamente significativas entre modelos."
            if sig else
            "No se rechaza H0: Distribuciones equivalentes entre modelos (sin diferencia medible)."
        )
        values = [
            metric_names.get(mk, mk), kw["H_statistic"], kw["p_value"],
            "Sí" if sig else "No", interp
        ]
        for col_idx, v in enumerate(values, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=v)
            cell.font = REGULAR_FONT
            cell.border = THIN_BORDER
            if col_idx == 2:
                cell.number_format = "#,##0.000"
                cell.alignment = ALIGN_RIGHT
            elif col_idx == 3:
                cell.number_format = "0.000000"
                cell.alignment = ALIGN_RIGHT
            else:
                cell.alignment = ALIGN_LEFT

        row_idx += 1

    _auto_fit_columns(ws, max_cols=len(headers))


def _build_sheet_bootstrap(ws, corr: dict[str, Any]):
    """Intervalos de confianza bootstrap al 95% por modelo y métrica."""
    ws["A1"] = "Intervalos de Confianza Bootstrap al 95% (1.000 Remuestreos Percentil por Conglomerados)"
    ws["A1"].font = TITLE_FONT

    headers = ["Modelo SLM", "Métrica Continua", "IC 95% Inferior", "IC 95% Superior", "Amplitud del IC"]

    for col_idx, h in enumerate(headers, 1):
        ws.cell(row=3, column=col_idx, value=h)
    _style_header_row(ws, 3, TEAL_HEADER)

    row_idx = 4
    for mid, metrics in corr.get("bootstrap_ci_95", {}).items():
        for mk, (lo, hi) in metrics.items():
            amp = round(hi - lo, 4)
            values = [mid, mk, lo, hi, amp]
            for col_idx, v in enumerate(values, 1):
                cell = ws.cell(row=row_idx, column=col_idx, value=v)
                cell.font = REGULAR_FONT
                cell.border = THIN_BORDER
                if col_idx in [3, 4, 5]:
                    cell.number_format = "#,##0.0000"
                    cell.alignment = ALIGN_RIGHT
                else:
                    cell.alignment = ALIGN_LEFT
            row_idx += 1

    _auto_fit_columns(ws, max_cols=len(headers))


def _build_sheet_effect_size(ws, corr: dict[str, Any]):
    """Tamaño del efecto estandarizado d de Cohen entre pares de modelos."""
    ws["A1"] = "Tamaño del Efecto (d de Cohen) entre Pares de Modelos"
    ws["A1"].font = TITLE_FONT

    headers = ["Métrica", "Comparación de Pares", "d de Cohen", "Interpretación (Cohen 1988)"]

    for col_idx, h in enumerate(headers, 1):
        ws.cell(row=3, column=col_idx, value=h)
    _style_header_row(ws, 3, TEAL_HEADER)

    row_idx = 4
    for mk, pairs in corr.get("effect_sizes", {}).items():
        for pair_name, es in pairs.items():
            values = [mk, pair_name, es["cohens_d"], es["interpretation"]]
            for col_idx, v in enumerate(values, 1):
                cell = ws.cell(row=row_idx, column=col_idx, value=v)
                cell.font = REGULAR_FONT
                cell.border = THIN_BORDER
                if col_idx == 3:
                    cell.number_format = "#,##0.0000"
                    cell.alignment = ALIGN_RIGHT
                else:
                    cell.alignment = ALIGN_LEFT
            row_idx += 1

    _auto_fit_columns(ws, max_cols=len(headers))


def _build_sheet_descriptivos(ws, corr: dict[str, Any]):
    """Estadísticos descriptivos consolidados por modelo y métrica."""
    ws["A1"] = "Estadísticos Descriptivos Consolidados por Modelo y Métrica"
    ws["A1"].font = TITLE_FONT

    headers = [
        "Modelo SLM", "Métrica", "Media", "Desviación (sigma)",
        "Coef. Variación (%)", "Mínimo", "p50 (Mediana)", "p95", "Máximo", "N Corridas"
    ]

    for col_idx, h in enumerate(headers, 1):
        ws.cell(row=3, column=col_idx, value=h)
    _style_header_row(ws, 3, TEAL_HEADER)

    row_idx = 4
    for mid, metrics in corr.get("descriptives", {}).items():
        for mk, ds in metrics.items():
            values = [
                mid, mk, ds["mean"], ds["std"], ds["cv"],
                ds["min"], ds["p50"], ds["p95"], ds["max"], ds["n"]
            ]
            for col_idx, v in enumerate(values, 1):
                cell = ws.cell(row=row_idx, column=col_idx, value=v)
                cell.font = REGULAR_FONT
                cell.border = THIN_BORDER
                if col_idx in [3, 4, 6, 7, 8, 9]:
                    cell.number_format = "#,##0.00"
                    cell.alignment = ALIGN_RIGHT
                elif col_idx == 5:
                    cell.number_format = '0.0"%"'
                    cell.alignment = ALIGN_RIGHT
                elif col_idx == 10:
                    cell.number_format = "#,##0"
                    cell.alignment = ALIGN_CENTER
                else:
                    cell.alignment = ALIGN_LEFT
            row_idx += 1

    _auto_fit_columns(ws, max_cols=len(headers))


def _build_sheet_raw(ws, rows: list[dict[str, Any]]):
    """Hoja con las 162 corridas del CSV original completas con autofilter."""
    if not rows:
        return

    columns = list(rows[0].keys())
    for col_idx, col_name in enumerate(columns, 1):
        ws.cell(row=1, column=col_idx, value=col_name)
    _style_header_row(ws, 1, NAVY_HEADER)

    for row_idx, r in enumerate(rows, 2):
        for col_idx, col_name in enumerate(columns, 1):
            val = sanitize_cell_value(r[col_name])
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            cell.font = REGULAR_FONT
            cell.border = THIN_BORDER
            if isinstance(val, (int, float)):
                cell.alignment = ALIGN_RIGHT
            elif isinstance(val, bool):
                cell.alignment = ALIGN_CENTER
            else:
                cell.alignment = ALIGN_LEFT

    last_col = get_column_letter(len(columns))
    ws.auto_filter.ref = f"A1:{last_col}{len(rows) + 1}"
    _auto_fit_columns(ws, max_cols=len(columns))


def export_suite_run_to_excel(
    run_id: str | None = None,
    output_path: Path | None = None,
) -> Path:
    """
    Construye un libro Excel con los resultados reales de la ejecución de la Suite (LangGraph).
    Convierte el historial real de la ejecución actual, fila por fila (las 18 pruebas),
    mostrando la respuesta real del modelo vs. la esperada, telemetría y CoT íntegro.
    """
    import pandas as pd

    from src.layer6_interface.suite_store import suite_store

    session = suite_store.get_session(run_id)
    if not session:
        raise ValueError(f"No se encontró una corrida de la suite con el identificador '{run_id or 'latest'}'.")

    if output_path is None:
        output_path = PROJECT_ROOT / "data" / "benchmark_results" / f"suite_observabilidad_{session.run_id}.xlsx"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df_cases = session.to_dataframe()
    for col in df_cases.columns:
        if df_cases[col].dtype == "object":
            df_cases[col] = df_cases[col].apply(sanitize_cell_value)
    m = session.summary_metrics or {}

    df_metrics = pd.DataFrame([
        {"Métrica": "Identificador de Corrida (Run ID)", "Valor": session.run_id},
        {"Métrica": "Modelo de Lenguaje (SLM)", "Valor": session.model_name or session.model_id},
        {"Métrica": "Semilla Determinista", "Valor": session.seed},
        {"Métrica": "Estado de Ejecución", "Valor": session.status},
        {"Métrica": "Casos Resueltos", "Valor": f"{session.completed_cases} / {session.total_cases}"},
        {"Métrica": "Fecha de Inicio", "Valor": session.start_time},
        {"Métrica": "Fecha de Finalización", "Valor": session.completed_at or session.updated_at},
        {"Métrica": "Precisión Causa Raíz", "Valor": f"{m.get('root_cause_accuracy', 0.0) * 100:.1f}%"},
        {"Métrica": "Precisión Componente Afectado", "Valor": f"{m.get('component_accuracy', 0.0) * 100:.1f}%"},
        {"Métrica": "Tasa de Invocación de Herramientas", "Valor": f"{m.get('tool_call_rate', 0.0) * 100:.1f}%"},
        {"Métrica": "TTFT Promedio (ms)", "Valor": m.get('avg_ttft_ms', 0.0)},
        {"Métrica": "Velocidad Promedio (tok/s)", "Valor": m.get('avg_tok_per_sec', 0.0)},
        {"Métrica": "Latencia Total Inferencia (ms)", "Valor": m.get('total_latency_ms', 0.0)},
        {"Métrica": "Pico de Consumo VRAM (Declarada/Estimada) (GB)", "Valor": m.get('vram_peak_gb', 0.0)},
        {"Métrica": "Tokens Totales Generados", "Valor": m.get('total_tokens_generated', 0)},
    ])

    with pd.ExcelWriter(str(output_path), engine="openpyxl") as writer:
        df_cases.to_excel(writer, sheet_name="Resultados_Reales_LangGraph", index=False)
        df_metrics.to_excel(writer, sheet_name="Metricas_Resumen", index=False)

    return output_path

