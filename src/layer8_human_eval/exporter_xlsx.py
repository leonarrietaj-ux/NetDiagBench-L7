"""
NetDiagBench-L7: Layer 8 - Exportador Excel del Instrumento de Evaluación Humana (exporter_xlsx.py)
Genera el libro Instrumento_Experto_<ID>_<sesion>.xlsx con 4 hojas:
1. Instrucciones (etiqueta del experto, materiales y reglas)
2. Guía (descriptores de rúbrica C1-C6, S, U y fila de ejemplo EV-000)
3. Evaluación (54 corridas en el orden de la etiqueta, validación de datos, fórmulas y protección)
4. Validación funcional (pruebas V1-V14 con dictamen de aceptación)
"""

from pathlib import Path
from typing import Any

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Protection, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from src.core.contracts import CorridaAnonimizada, EtiquetaExperto

# Paleta y Estilos Institucionales
COLOR_HEADER_BG = "B03535"       # Rojo institucional #B03535
COLOR_WHITE = "FFFFFF"
COLOR_GRAY_READONLY = "F1F5F9"   # Slate 100 para solo lectura
COLOR_YELLOW_INPUT = "FEF9C3"    # Amarillo claro para celdas editables
COLOR_BLUE_FORMULA = "E0F2FE"    # Azul claro para fórmulas automáticas
COLOR_BORDER = "CBD5E1"          # Borde suave

FONT_NAME = "Arial"
FONT_TITLE = Font(name=FONT_NAME, size=14, bold=True, color="000000")
FONT_SUBTITLE = Font(name=FONT_NAME, size=10, italic=True, color="475569")
FONT_SECTION = Font(name=FONT_NAME, size=11, bold=True, color="B03535")
FONT_HEADER = Font(name=FONT_NAME, size=10, bold=True, color=COLOR_WHITE)
FONT_REGULAR = Font(name=FONT_NAME, size=9, color="000000")
FONT_BOLD = Font(name=FONT_NAME, size=9, bold=True, color="000000")

FILL_HEADER = PatternFill(start_color=COLOR_HEADER_BG, end_color=COLOR_HEADER_BG, fill_type="solid")
FILL_READONLY = PatternFill(start_color=COLOR_GRAY_READONLY, end_color=COLOR_GRAY_READONLY, fill_type="solid")
FILL_INPUT = PatternFill(start_color=COLOR_YELLOW_INPUT, end_color=COLOR_YELLOW_INPUT, fill_type="solid")
FILL_FORMULA = PatternFill(start_color=COLOR_BLUE_FORMULA, end_color=COLOR_BLUE_FORMULA, fill_type="solid")

BORDER_THIN = Border(
    left=Side(style="thin", color=COLOR_BORDER),
    right=Side(style="thin", color=COLOR_BORDER),
    top=Side(style="thin", color=COLOR_BORDER),
    bottom=Side(style="thin", color=COLOR_BORDER),
)

ALIGN_CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
ALIGN_LEFT = Alignment(horizontal="left", vertical="center", wrap_text=True)
ALIGN_RIGHT = Alignment(horizontal="right", vertical="center")

PROT_LOCKED = Protection(locked=True)
PROT_UNLOCKED = Protection(locked=False)


def _setup_page_properties(ws):
    """Configura orientación horizontal y ajuste al ancho de página."""
    ws.page_setup.orientation = ws.ORIENTATION_LANDSCAPE
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True


def _auto_fit_columns(ws, min_width=10, max_width=45):
    """Ajusta anchos de columnas respetando márgenes legibles."""
    for col in ws.columns:
        col_letter = get_column_letter(col[0].column)
        max_len = 0
        for cell in col:
            val_str = str(cell.value or "")
            if "\n" in val_str:
                lines = val_str.split("\n")
                max_len = max(max_len, max(len(l) for l in lines))
            else:
                max_len = max(max_len, len(val_str))
        ws.column_dimensions[col_letter].width = max(min(max_len + 3, max_width), min_width)


def _create_sheet_instructions(ws, etiqueta: EtiquetaExperto):
    """Construye la hoja 'Instrucciones' con la etiqueta del evaluador y reglas del protocolo."""
    _setup_page_properties(ws)
    ws.views.sheetView[0].showGridLines = True

    ws["A1"] = "NetDiagBench-L7 — Instrumento de Validación Humana Ciega"
    ws["A1"].font = FONT_TITLE
    ws["A2"] = "Protocolo de Evaluación Inter-Evaluador y Calibración Técnica"
    ws["A2"].font = FONT_SUBTITLE

    # Etiqueta de Autenticación
    ws["A4"] = "ETIQUETA DE IDENTIFICACIÓN Y AUTENTICACIÓN DEL EVALUADOR"
    ws["A4"].font = FONT_SECTION

    fields = [
        ("Identificador del Experto:", etiqueta.expert_id),
        ("Rol en el Estudio:", etiqueta.rol),
        ("Alias Asignado:", etiqueta.alias),
        ("Identificador de Sesión:", etiqueta.sesion_id),
        ("Fecha de Emisión:", etiqueta.fecha_emision),
        ("Código de Acceso (8 caracteres):", etiqueta.codigo_acceso),
        ("Huella Criptográfica SHA-256:", etiqueta.huella_sha256),
        ("Semilla de Barajado:", str(etiqueta.semilla_orden)),
        ("Total de Corridas Asignadas:", str(len(etiqueta.orden))),
    ]

    for idx, (label, val) in enumerate(fields, start=5):
        ws[f"A{idx}"] = label
        ws[f"A{idx}"].font = FONT_BOLD
        ws[f"B{idx}"] = val
        ws[f"B{idx}"].font = FONT_REGULAR
        ws[f"A{idx}"].border = BORDER_THIN
        ws[f"B{idx}"].border = BORDER_THIN
        ws[f"A{idx}"].fill = FILL_READONLY

    # Propósito y Reglas
    start_r = 15
    ws[f"A{start_r}"] = "PROPÓSITO, MATERIALES Y REGLAS DE INDEPENDENCIA"
    ws[f"A{start_r}"].font = FONT_SECTION

    rules = [
        ("1. Propósito:", "Evaluar a ciegas e independientemente la precisión técnica, coherencia, fundamentación normativa y utilidad operativa de diagnósticos de incidentes de red L7 generados por sistemas inteligentes."),
        ("2. Materiales:", f"Este libro de cálculo y el paquete complementario autocontenido 'Paquete_Experto_{etiqueta.expert_id}_{etiqueta.sesion_id}.html'."),
        ("3. Regla de Independencia:", "Las calificaciones deben emitirse de forma estrictamente individual, sin consultar a otros expertos ni acceder a claves externas de correspondencia."),
        ("4. Estructura del Proceso:", "La Parte A (calificación de las 54 corridas en la hoja 'Evaluación') va primero; la Parte B (hoja 'Validación funcional'), solo después de entregar la Parte A."),
        ("5. Guardado y Entrega:", "Complete todas las celdas amarillas. Si C1=0 o S=No, la columna 'Observación' es de llenado obligatorio.")
    ]

    for idx, (title, text) in enumerate(rules, start=start_r + 1):
        ws[f"A{idx}"] = title
        ws[f"A{idx}"].font = FONT_BOLD
        ws[f"B{idx}"] = text
        ws[f"B{idx}"].font = FONT_REGULAR
        ws[f"A{idx}"].border = BORDER_THIN
        ws[f"B{idx}"].border = BORDER_THIN

    _auto_fit_columns(ws, min_width=25, max_width=80)
    ws.protection.sheet = True


def _create_sheet_guide(ws):
    """Construye la hoja 'Guía' con la rúbrica oficial y la fila de ejemplo EV-000."""
    _setup_page_properties(ws)
    ws.views.sheetView[0].showGridLines = True

    ws["A1"] = "Guía de Calificación y Descriptores de la Rúbrica"
    ws["A1"].font = FONT_TITLE
    ws["A2"] = "Criterios estandarizados de evaluación humana (Escalas C1 a C6, S y U)"
    ws["A2"].font = FONT_SUBTITLE

    headers = ["Ítem", "Criterio", "Escala", "Descriptores"]
    for col_idx, h in enumerate(headers, start=1):
        cell = ws.cell(row=4, column=col_idx, value=h)
        cell.font = FONT_HEADER
        cell.fill = FILL_HEADER
        cell.alignment = ALIGN_CENTER
        cell.border = BORDER_THIN

    guide_rows = [
        ("C1", "Corrección de la causa raíz", "0,1,2", "0 incorrecta o clase vecina; 1 parcial (familia correcta, causa o componente errado); 2 correcta"),
        ("C2", "Coherencia técnica", "0,1,2", "0 contradictorio; 1 coherente con saltos; 2 cadena síntoma → evidencia → causa"),
        ("C3", "Fundamentación normativa", "0,1,2", "0 no cita o cita mal; 1 cita correcta genérica; 2 cita precisa (RFC y sección o código) aplicada"),
        ("C4", "Componente", "0,1,2", "0 errado; 1 vecino; 2 exacto"),
        ("C5", "Mitigación", "0,1,2", "0 inútil o riesgosa; 1 genérica; 2 accionable y específica"),
        ("C6", "Exactitud factual", "0,1,2", "0 errores de protocolo (p. ej., RCODE 3 = SERVFAIL); 1 imprecisiones menores; 2 sin errores"),
        ("S", "Sustentado", "Sí/No", "La evidencia citada aparece en la salida de la traza y respalda la conclusión"),
        ("U", "Utilidad operativa", "1–5", "«¿Abriría un ticket con este diagnóstico tal como está?»"),
        ("Obs", "Observación", "Texto", "Obligatoria si C1 = 0 o S = No"),
    ]

    for r_idx, (item, crit, scale, desc) in enumerate(guide_rows, start=5):
        ws.cell(row=r_idx, column=1, value=item).alignment = ALIGN_CENTER
        ws.cell(row=r_idx, column=2, value=crit).alignment = ALIGN_LEFT
        ws.cell(row=r_idx, column=3, value=scale).alignment = ALIGN_CENTER
        ws.cell(row=r_idx, column=4, value=desc).alignment = ALIGN_LEFT
        for c in range(1, 5):
            ws.cell(row=r_idx, column=c).border = BORDER_THIN
            ws.cell(row=r_idx, column=c).font = FONT_REGULAR

    # Fila de Ejemplo fuera de la muestra
    start_ex = 16
    ws[f"A{start_ex}"] = "FILA DE EJEMPLO ILUSTRATIVO (FUERA DE LA MUESTRA)"
    ws[f"A{start_ex}"].font = FONT_SECTION

    ex_headers = ["Código", "C1", "C2", "C3", "C4", "C5", "C6", "S", "U", "Observación"]
    for c_idx, h in enumerate(ex_headers, start=1):
        c = ws.cell(row=start_ex + 1, column=c_idx, value=h)
        c.font = FONT_HEADER
        c.fill = PatternFill(start_color="334155", end_color="334155", fill_type="solid")
        c.alignment = ALIGN_CENTER
        c.border = BORDER_THIN

    ex_values = ["EV-000", 1, 2, 1, 0, 1, 0, "Sí", 2, "Ejemplo ilustrativo: causa identificada parcialmente pero con imprecisiones en el componente."]
    for c_idx, val in enumerate(ex_values, start=1):
        c = ws.cell(row=start_ex + 2, column=c_idx, value=val)
        c.font = FONT_BOLD if c_idx == 1 else FONT_REGULAR
        c.alignment = ALIGN_LEFT if c_idx == 10 else ALIGN_CENTER
        c.border = BORDER_THIN
        c.fill = FILL_READONLY

    _auto_fit_columns(ws, min_width=12, max_width=60)
    ws.protection.sheet = True


def _create_sheet_evaluation(ws, etiqueta: EtiquetaExperto, cards: dict[str, Any]):
    """
    Construye la hoja 'Evaluación' con 54 corridas en el orden de la etiqueta y fórmulas.
    Material estrictamente ciego: no contiene causa raíz esperada, componente esperado
    ni evidencia mínima requerida (Ground Truth).
    """
    _setup_page_properties(ws)
    ws.views.sheetView[0].showGridLines = True

    # Resumen superior con contadores por fórmula
    ws["A1"] = "Evaluación Ciega de Diagnósticos"
    ws["A1"].font = FONT_TITLE
    ws["A2"] = f"Experto: {etiqueta.expert_id} ({etiqueta.alias}) | Sesión: {etiqueta.sesion_id}"
    ws["A2"].font = FONT_SUBTITLE

    ws["K1"] = "Total Corridas:"
    ws["K1"].font = FONT_BOLD
    ws["L1"] = len(etiqueta.orden)
    ws["L1"].font = FONT_BOLD

    ws["K2"] = "Completas:"
    ws["K2"].font = FONT_BOLD
    first_row = 5
    last_row = first_row + len(etiqueta.orden) - 1
    ws["L2"] = f'=COUNTIF(P{first_row}:P{last_row},"Completa")'
    ws["L2"].font = FONT_BOLD

    ws["M2"] = "Estado Global:"
    ws["M2"].font = FONT_BOLD
    ws["N2"] = f'=IF(L2={len(etiqueta.orden)},"EVALUACIÓN COMPLETA","EN PROCESO")'
    ws["N2"].font = FONT_BOLD

    # Cabeceras de columnas estrictamente ciegas (sin verdad fundamental)
    headers = [
        ("N.º", FILL_HEADER, 6),
        ("Código", FILL_HEADER, 10),
        ("Escenario", FILL_HEADER, 14),
        ("Síntoma", FILL_HEADER, 32),
        ("C1", FILL_HEADER, 7),
        ("C2", FILL_HEADER, 7),
        ("C3", FILL_HEADER, 7),
        ("C4", FILL_HEADER, 7),
        ("C5", FILL_HEADER, 7),
        ("C6", FILL_HEADER, 7),
        ("S", FILL_HEADER, 7),
        ("U", FILL_HEADER, 7),
        ("Observación", FILL_HEADER, 32),
        ("Suma C2-C5", FILL_HEADER, 12),
        ("Rúbrica (0-5)", FILL_HEADER, 12),
        ("Completa", FILL_HEADER, 12),
    ]

    for col_idx, (h_text, fill, width) in enumerate(headers, start=1):
        cell = ws.cell(row=4, column=col_idx, value=h_text)
        cell.font = FONT_HEADER
        cell.fill = fill
        cell.alignment = ALIGN_CENTER
        cell.border = BORDER_THIN
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    # Reglas de Validación de Datos openpyxl
    dv_012 = DataValidation(type="list", formula1='"0,1,2"', allow_blank=True)
    dv_s = DataValidation(type="list", formula1='"Sí,No"', allow_blank=True)
    dv_u = DataValidation(type="list", formula1='"1,2,3,4,5"', allow_blank=True)

    ws.add_data_validation(dv_012)
    ws.add_data_validation(dv_s)
    ws.add_data_validation(dv_u)

    # Validaciones en columnas C1..C6 (E..J), S (K), U (L)
    dv_012.add(f"E{first_row}:J{last_row}")
    dv_s.add(f"K{first_row}:K{last_row}")
    dv_u.add(f"L{first_row}:L{last_row}")

    for idx, code in enumerate(etiqueta.orden, start=1):
        row = 4 + idx
        card = cards.get(code)
        sc_id = getattr(card, "scenario_id", "") if card else ""
        sintoma = getattr(card, "sintoma", "") if card else ""

        # Columnas A..D (Grises / Solo lectura)
        ws.cell(row=row, column=1, value=idx).alignment = ALIGN_CENTER
        ws.cell(row=row, column=2, value=code).alignment = ALIGN_CENTER
        ws.cell(row=row, column=3, value=sc_id).alignment = ALIGN_CENTER
        ws.cell(row=row, column=4, value=sintoma).alignment = ALIGN_LEFT

        for c in range(1, 5):
            cell = ws.cell(row=row, column=c)
            cell.font = FONT_REGULAR
            cell.fill = FILL_READONLY
            cell.border = BORDER_THIN
            cell.protection = PROT_LOCKED

        # Columnas E..M (Amarillas / Editables desbloqueadas: C1..C6, S, U, Observación)
        for c in range(5, 14):
            cell = ws.cell(row=row, column=c)
            cell.font = FONT_REGULAR
            cell.fill = FILL_INPUT
            cell.border = BORDER_THIN
            cell.protection = PROT_UNLOCKED
            cell.alignment = ALIGN_LEFT if c == 13 else ALIGN_CENTER

        # Columna N: Suma C2–C5 (0–8): =IF(COUNT(F:I)=4,SUM(F:I),"")
        formula_suma = f'=IF(COUNT(F{row}:I{row})=4,SUM(F{row}:I{row}),"")'
        cell_n = ws.cell(row=row, column=14, value=formula_suma)
        cell_n.font = FONT_BOLD
        cell_n.fill = FILL_FORMULA
        cell_n.alignment = ALIGN_CENTER
        cell_n.border = BORDER_THIN
        cell_n.protection = PROT_LOCKED

        # Columna O: Rúbrica 0–5: =ROUND(suma/8*5,2)
        formula_rubrica = f'=IF(N{row}<>"",ROUND(N{row}/8*5,2),"")'
        cell_o = ws.cell(row=row, column=15, value=formula_rubrica)
        cell_o.font = FONT_BOLD
        cell_o.fill = FILL_FORMULA
        cell_o.alignment = ALIGN_CENTER
        cell_o.border = BORDER_THIN
        cell_o.protection = PROT_LOCKED

        # Columna P: Estado («Completa» o «Falta»)
        # Dice "Falta" si hay ítems vacíos, o si C1 = 0 o S = No sin observación.
        formula_completa = (
            f'=IF(OR(COUNT(E{row}:J{row})<6,K{row}="",L{row}="",'
            f'AND(E{row}=0,TRIM(M{row})=""),AND(K{row}="No",TRIM(M{row})="")),"Falta","Completa")'
        )
        cell_p = ws.cell(row=row, column=16, value=formula_completa)
        cell_p.font = FONT_BOLD
        cell_p.fill = FILL_FORMULA
        cell_p.alignment = ALIGN_CENTER
        cell_p.border = BORDER_THIN
        cell_p.protection = PROT_LOCKED

    # Proteger la hoja sin contraseña
    ws.protection.sheet = True


def _create_sheet_validation(ws):
    """Construye la hoja 'Validación funcional' con las pruebas V1-V14 y dictamen de aceptación."""
    _setup_page_properties(ws)
    ws.views.sheetView[0].showGridLines = True

    ws["A1"] = "Validación Funcional de la Aplicación (Parte B)"
    ws["A1"].font = FONT_TITLE
    ws["A2"] = "Pruebas V1–V14 del sistema NetDiagBench-L7 (V5, V7, V9 y V13 son críticas)"
    ws["A2"].font = FONT_SUBTITLE

    # Dictamen por fórmula: "Aplicación validada" solo si las 4 críticas dicen Cumple
    # Filas estimadas: V1 (fila 6) .. V14 (fila 19)
    # V5 = fila 10, V7 = fila 12, V9 = fila 14, V13 = fila 18
    dictamen_formula = '=IF(AND(F10="Cumple",F12="Cumple",F14="Cumple",F18="Cumple"),"Aplicación validada","Pendiente / No validada")'

    ws["D2"] = "Dictamen del Sistema:"
    ws["D2"].font = FONT_BOLD
    ws["E2"] = dictamen_formula
    ws["E2"].font = FONT_BOLD
    ws["E2"].fill = FILL_FORMULA
    ws["E2"].border = BORDER_THIN
    ws["E2"].alignment = ALIGN_CENTER

    headers = ["Código", "Prueba", "Criterio de aceptación", "Paso", "Tipo", "Resultado", "Evidencia", "Observación"]
    for col_idx, h in enumerate(headers, start=1):
        cell = ws.cell(row=5, column=col_idx, value=h)
        cell.font = FONT_HEADER
        cell.fill = FILL_HEADER
        cell.alignment = ALIGN_CENTER
        cell.border = BORDER_THIN

    tests_v = [
        ("V1", "Entorno y modelos", "`benchapp doctor` sin errores críticos; `ollama list` muestra los 3 modelos", "Ejecutar diagnóstico de entorno", "Estándar"),
        ("V2", "Pruebas automatizadas", "Todas las pruebas de pytest aprobadas", "Ejecutar suite completa de tests", "Estándar"),
        ("V3", "Catálogo", "18 escenarios y 3 modelos listados", "Listar catálogo en CLI o interfaz", "Estándar"),
        ("V4", "Recuperación normativa", "`rag-query` devuelve fragmentos pertinentes al síntoma", "Consultar base vectorial RAG", "Estándar"),
        ("V5", "Ejecución local real", "«100% LOCAL» y «OLLAMA LIVE» en verde; no está en modo simulador", "Verificar badges y telemetría", "Crítica"),
        ("V6", "Flujo de diagnóstico", "Cinco fases completas; comando y salida visibles", "Ejecutar flujo completo de corrida", "Estándar"),
        ("V7", "Evidencia verificable", "El comando ejecutado por el evaluador da la misma salida", "Verificar comando empírico", "Crítica"),
        ("V8", "Veredicto frente a ficha", "Se registra si causa y componente coinciden; sin errores de protocolo", "Comparar contra ficha técnica", "Estándar"),
        ("V9", "Reproducibilidad", "Dos corridas iguales dan la misma causa raíz y componente", "Ejecutar dos veces con misma semilla", "Crítica"),
        ("V10", "Trazabilidad", "Traza con herramienta, comando, salida e hipótesis; commit, versión de Ollama y huella", "Auditar archivo traza.jsonl", "Estándar"),
        ("V11", "Operación sin nube", "El diagnóstico termina con la red desconectada", "Aislar interfaz de red externa", "Estándar"),
        ("V12", "Memoria de vídeo", "Pico medido con nvidia-smi < 8 GB (anotar medido y reportado)", "Monitorear memoria de vídeo durante inferencia", "Estándar"),
        ("V13", "Solo lectura", "Lista blanca correcta y pruebas de la capa 5 aprobadas", "Comprobar restricción de comandos", "Crítica"),
        ("V14", "Exportación", "Excel y PDF generados y legibles", "Generar y abrir artefactos", "Estándar"),
    ]

    dv_res = DataValidation(type="list", formula1='"Cumple,No cumple,No aplica"', allow_blank=True)
    ws.add_data_validation(dv_res)
    dv_res.add("F6:F19")

    for idx, (cod, desc, crit, step, tipo) in enumerate(tests_v, start=6):
        ws.cell(row=idx, column=1, value=cod).alignment = ALIGN_CENTER
        ws.cell(row=idx, column=2, value=desc).alignment = ALIGN_LEFT
        ws.cell(row=idx, column=3, value=crit).alignment = ALIGN_LEFT
        ws.cell(row=idx, column=4, value=step).alignment = ALIGN_LEFT
        ws.cell(row=idx, column=5, value=tipo).alignment = ALIGN_CENTER

        for c in range(1, 6):
            cell = ws.cell(row=idx, column=c)
            cell.font = FONT_BOLD if c in (1, 5) else FONT_REGULAR
            cell.fill = FILL_READONLY
            cell.border = BORDER_THIN
            cell.protection = PROT_LOCKED

        # Columnas editables: Resultado (F), Evidencia (G), Observación (H)
        for c in range(6, 9):
            cell = ws.cell(row=idx, column=c)
            cell.font = FONT_REGULAR
            cell.fill = FILL_INPUT
            cell.border = BORDER_THIN
            cell.protection = PROT_UNLOCKED
            cell.alignment = ALIGN_CENTER if c == 6 else ALIGN_LEFT

    _auto_fit_columns(ws, min_width=12, max_width=45)
    ws.protection.sheet = True


def export_expert_instrument(
    etiqueta: EtiquetaExperto,
    cards: dict[str, CorridaAnonimizada],
    output_path: Path
) -> Path:
    """
    Exporta el libro de cálculo Instrumento_Experto_<ID>_<sesion>.xlsx con las 4 hojas reglamentarias.
    Garantiza docProps anónimos y sin funciones dinámicas de Excel.
    """
    wb = openpyxl.Workbook()

    # 1. Hoja Instrucciones
    ws_inst = wb.active
    ws_inst.title = "Instrucciones"
    _create_sheet_instructions(ws_inst, etiqueta)

    # 2. Hoja Guía
    ws_guia = wb.create_sheet(title="Guía")
    _create_sheet_guide(ws_guia)

    # 3. Hoja Evaluación
    ws_eval = wb.create_sheet(title="Evaluación")
    _create_sheet_evaluation(ws_eval, etiqueta, cards)

    # 4. Hoja Validación funcional
    ws_val = wb.create_sheet(title="Validación funcional")
    _create_sheet_validation(ws_val)

    # Metadatos del documento completamente limpios de marcas de modelo
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.properties.creator = "NetDiagBench-L7"
    wb.properties.title = f"Instrumento de Validación Experto {etiqueta.expert_id}"
    wb.properties.subject = "Evaluación Humana Ciegas"
    wb.properties.description = "Instrumento de recolección de juicios de expertos para calibración diagnóstica"

    wb.save(output_path)
    return output_path
