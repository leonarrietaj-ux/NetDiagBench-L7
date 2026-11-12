"""
NetDiagBench-L7: Generador de Manual Técnico y Manual de Usuario en PDF
Produce dos documentos PDF de nivel editorial y académico con ReportLab:
  1. docs/MANUAL_TECNICO_SISTEMA.pdf
  2. docs/MANUAL_USUARIO_SISTEMA.pdf (con capturas reales embebidas)
Además genera las versiones Markdown en docs/ para referencia directa.
"""

import os
import sys
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT_DIR = Path(r"c:\Users\USUARIO\OneDrive\Escritorio\benchapp-ip")
DOCS_DIR = ROOT_DIR / "docs"
SHOTS_DIR = Path(r"C:\Users\USUARIO\.gemini\antigravity\brain\eb62072c-416e-46a9-9abd-43786a28da76\scratch\shots")
PROBE_DIR = Path(r"C:\Users\USUARIO\.gemini\antigravity\brain\eb62072c-416e-46a9-9abd-43786a28da76\scratch\probe")
LOGO_UNIPAMPLONA = ROOT_DIR / "static" / "img" / "unipamplona_logo.png"
LOGO_TELECOM = ROOT_DIR / "static" / "img" / "telecomunicaciones_logo.png"

# Colores Institucionales
COLOR_RED = colors.HexColor("#ad3333")
COLOR_NAVY = colors.HexColor("#003366")
COLOR_DARK = colors.HexColor("#0f172a")
COLOR_TEXT = colors.HexColor("#1e293b")
COLOR_MUTED = colors.HexColor("#64748b")
COLOR_LIGHT_BG = colors.HexColor("#f8fafc")
COLOR_CODE_BG = colors.HexColor("#f1f5f9")
COLOR_BORDER = colors.HexColor("#cbd5e1")
COLOR_GREEN = colors.HexColor("#10b981")


class BaseNumberedCanvas(canvas.Canvas):
    doc_title = "NetDiagBench-L7"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._saved_page_states: list[dict[str, Any]] = []

    def showPage(self) -> None:
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_decorations(self, total_pages: int) -> None:
        self.saveState()
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(COLOR_MUTED)

        # Encabezado (desde página 2)
        if self._pageNumber > 1:
            self.drawString(40, 11 * inch - 36, self.doc_title.upper())
            self.drawRightString(8.5 * inch - 40, 11 * inch - 36, "UNIVERSIDAD DE PAMPLONA • E.E.S.T.")
            self.setStrokeColor(COLOR_BORDER)
            self.setLineWidth(0.6)
            self.line(40, 11 * inch - 42, 8.5 * inch - 40, 11 * inch - 42)

        # Pie de página
        page_str = f"Página {self._pageNumber} de {total_pages}"
        self.setFont("Helvetica", 8)
        self.drawString(40, 30, "NetDiagBench-L7 • Diagnóstico Reproducible de Red L7 con SLMs Locales")
        self.drawRightString(8.5 * inch - 40, 30, page_str)
        self.setStrokeColor(COLOR_BORDER)
        self.setLineWidth(0.6)
        self.line(40, 40, 8.5 * inch - 40, 40)
        self.restoreState()


class ManualTecnicoCanvas(BaseNumberedCanvas):
    doc_title = "NetDiagBench-L7 • Manual Técnico del Sistema"


class ManualUsuarioCanvas(BaseNumberedCanvas):
    doc_title = "NetDiagBench-L7 • Manual de Usuario y Guía Operativa"


def create_styles():
    ss = getSampleStyleSheet()

    title = ParagraphStyle(
        "CoverTitle",
        parent=ss["Normal"],
        fontName="Helvetica-Bold",
        fontSize=24,
        leading=30,
        textColor=COLOR_NAVY,
        alignment=1,
    )

    subtitle = ParagraphStyle(
        "CoverSubtitle",
        parent=ss["Normal"],
        fontName="Helvetica",
        fontSize=12,
        leading=16,
        textColor=COLOR_RED,
        alignment=1,
    )

    cover_meta = ParagraphStyle(
        "CoverMeta",
        parent=ss["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=14,
        textColor=COLOR_DARK,
        alignment=1,
    )

    h1 = ParagraphStyle(
        "SecH1",
        parent=ss["Normal"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=19,
        textColor=COLOR_NAVY,
        spaceBefore=14,
        spaceAfter=7,
        keepWithNext=True,
    )

    h2 = ParagraphStyle(
        "SecH2",
        parent=ss["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11.5,
        leading=15,
        textColor=COLOR_RED,
        spaceBefore=9,
        spaceAfter=4,
        keepWithNext=True,
    )

    h3 = ParagraphStyle(
        "SecH3",
        parent=ss["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13.5,
        textColor=COLOR_DARK,
        spaceBefore=7,
        spaceAfter=3,
        keepWithNext=True,
    )

    body = ParagraphStyle(
        "BodyTextCustom",
        parent=ss["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=COLOR_TEXT,
        spaceAfter=5,
    )

    bullet = ParagraphStyle(
        "BulletCustom",
        parent=ss["Normal"],
        fontName="Helvetica",
        fontSize=8.8,
        leading=12.5,
        textColor=COLOR_TEXT,
        leftIndent=14,
        firstLineIndent=-9,
        spaceAfter=3,
    )

    code = ParagraphStyle(
        "CodeCustom",
        parent=ss["Normal"],
        fontName="Courier",
        fontSize=7.8,
        leading=10.5,
        textColor=COLOR_DARK,
    )

    callout = ParagraphStyle(
        "CalloutText",
        parent=ss["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=8.8,
        leading=12.5,
        textColor=COLOR_DARK,
    )

    caption = ParagraphStyle(
        "FigCaption",
        parent=ss["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11.5,
        textColor=COLOR_NAVY,
        alignment=1,
        spaceBefore=4,
        spaceAfter=9,
    )

    th = ParagraphStyle(
        "TableHead",
        parent=ss["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.2,
        leading=10.5,
        textColor=colors.white,
        alignment=1,
    )

    td = ParagraphStyle(
        "TableCell",
        parent=ss["Normal"],
        fontName="Helvetica",
        fontSize=7.8,
        leading=10.5,
        textColor=COLOR_TEXT,
    )

    td_code = ParagraphStyle(
        "TableCellCode",
        parent=ss["Normal"],
        fontName="Courier",
        fontSize=7.5,
        leading=9.5,
        textColor=COLOR_NAVY,
    )

    return {
        "title": title,
        "subtitle": subtitle,
        "cover_meta": cover_meta,
        "h1": h1,
        "h2": h2,
        "h3": h3,
        "body": body,
        "bullet": bullet,
        "code": code,
        "callout": callout,
        "caption": caption,
        "th": th,
        "td": td,
        "td_code": td_code,
    }


def make_callout(text: str, styles, title: str = "NOTA TÉCNICA", border_color=COLOR_NAVY):
    p = Paragraph(f"<b>{title}:</b> {text}", styles["callout"])
    t = Table([[p]], colWidths=[532])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), COLOR_LIGHT_BG),
                ("BOX", (0, 0), (-1, -1), 0.8, border_color),
                ("LINELEFT", (0, 0), (0, -1), 3.5, border_color),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 9),
                ("RIGHTPADDING", (0, 0), (-1, -1), 9),
            ]
        )
    )
    return t


def make_code_box(code_text: str, styles):
    lines = code_text.strip().split("\n")
    formatted = "<br/>".join(
        line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace(" ", "&nbsp;")
        for line in lines
    )
    p = Paragraph(formatted, styles["code"])
    t = Table([[p]], colWidths=[532])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), COLOR_CODE_BG),
                ("BOX", (0, 0), (-1, -1), 0.6, COLOR_BORDER),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return t


def make_table(headers, rows, col_widths, styles, code_cols=None):
    if code_cols is None:
        code_cols = []
    data = []
    head_cells = [Paragraph(f"<b>{h}</b>", styles["th"]) for h in headers]
    data.append(head_cells)
    for r in rows:
        row_cells = []
        for i, val in enumerate(r):
            s = styles["td_code"] if i in code_cols else styles["td"]
            row_cells.append(Paragraph(str(val), s))
        data.append(row_cells)

    t = Table(data, colWidths=col_widths)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), COLOR_NAVY),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, COLOR_LIGHT_BG]),
                ("TOPPADDING", (0, 0), (-1, -1), 3.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return t


def add_cover(story, title_text, subtitle_text, styles):
    story.append(Spacer(1, 10))
    if LOGO_UNIPAMPLONA.exists() and LOGO_TELECOM.exists():
        img1 = Image(str(LOGO_UNIPAMPLONA), width=1.1 * inch, height=1.1 * inch)
        img2 = Image(str(LOGO_TELECOM), width=1.1 * inch, height=1.1 * inch)
        logo_table = Table([[img1, "", img2]], colWidths=[1.3 * inch, 4.8 * inch, 1.3 * inch])
        logo_table.setStyle(
            TableStyle(
                [
                    ("ALIGN", (0, 0), (0, 0), "LEFT"),
                    ("ALIGN", (2, 0), (2, 0), "RIGHT"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        story.append(logo_table)
    story.append(Spacer(1, 25))

    story.append(
        Paragraph("UNIVERSIDAD DE PAMPLONA<br/>FACULTAD DE INGENIERÍAS Y ARQUITECTURA<br/>DEPARTAMENTO E.E.S.T. — INGENIERÍA DE TELECOMUNICACIONES", styles["cover_meta"])
    )
    story.append(Spacer(1, 30))

    story.append(Paragraph(title_text, styles["title"]))
    story.append(Spacer(1, 10))
    story.append(
        HRFlowable(width="65%", thickness=2.5, color=COLOR_RED, spaceBefore=4, spaceAfter=14, hAlign="CENTER")
    )
    story.append(Paragraph(subtitle_text, styles["subtitle"]))
    story.append(Spacer(1, 35))

    meta_text = """
    <b>Proyecto de Grado:</b> Benchmark Reproducible para Diagnóstico de Fallas L7 con SLMs Locales<br/><br/>
    <b>Autor:</b> Juan David León Arrieta (<code>juan.leon22@unipamplona.edu.co</code>)<br/>
    <b>Director:</b> Mg. Richard Eliseo Mendoza Gáfaro (<code>richard.mendoza@unipamplona.edu.co</code>)<br/>
    <b>Versión del Software:</b> v1.0.0 • <b>Fecha:</b> Noviembre 2026<br/>
    <b>Arquitectura:</b> 7 Capas Desacopladas • RAG BM25 (≤0.05 MB) • LangGraph Read-Only • Typer CLI + FastAPI/HTMX<br/>
    <b>Entorno de Ejecución:</b> 100% Local • 8 GB VRAM • Ollama / llama.cpp (GGUF Q4_K_M)
    """
    box = Table([[Paragraph(meta_text, styles["cover_meta"])]], colWidths=[480])
    box.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), COLOR_LIGHT_BG),
                ("BOX", (0, 0), (-1, -1), 1, COLOR_NAVY),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                ("LEFTPADDING", (0, 0), (-1, -1), 16),
                ("RIGHTPADDING", (0, 0), (-1, -1), 16),
            ]
        )
    )
    story.append(box)
    story.append(PageBreak())


def make_image_box(img_path: Path, caption_text: str, styles, width_in: float = 6.8, height_in: float = 3.8):
    """Crea una tarjeta enmarcada para pantallazos con pie de figura institucional."""
    is_readable = False
    if img_path.exists():
        try:
            with open(img_path, "rb") as f_test:
                f_test.read(10)
            is_readable = True
        except Exception:
            is_readable = False

    if not is_readable:
        cap_fallback = Paragraph(f"<b>{caption_text}</b> <i>(Captura del aplicativo disponible en el dashboard web)</i>", styles["caption"])
        return KeepTogether([cap_fallback, Spacer(1, 4)])

    img = Image(str(img_path), width=width_in * inch, height=height_in * inch)
    t = Table([[img]], colWidths=[width_in * inch])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#0f172a")),
                ("BOX", (0, 0), (-1, -1), 1, COLOR_BORDER),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ]
        )
    )
    cap = Paragraph(f"<b>{caption_text}</b>", styles["caption"])
    return KeepTogether([t, cap, Spacer(1, 4)])


# ============================================================================
# CONSTRUCCIÓN DEL MANUAL TÉCNICO
# ============================================================================

def build_manual_tecnico_story(styles):
    story = []
    add_cover(
        story,
        "MANUAL TÉCNICO DEL SISTEMA",
        "Arquitectura, Contratos de Intercambio, Módulos por Capas (1 a 7), RAG BM25, Inferencia Local y Orquestación Agéntica",
        styles,
    )

    # 1. Introducción
    story.append(Paragraph("1. Introducción y Marco del Sistema", styles["h1"]))
    story.append(Paragraph(
        "<b>NetDiagBench-L7</b> es un entorno experimental reproducible concebido para evaluar rigurosamente "
        "la capacidad diagnóstica de modelos de lenguaje pequeños (SLMs) ejecutados de forma 100% local "
        "en hardware de consumo restringido (GPU con 8 GB de VRAM, 32 GB de RAM del sistema). "
        "El sistema aborda fallas complejas en la capa de aplicación sobre IP (Capa 7 OSI), concentrándose "
        "en servicios críticos como DNS (BIND9), servidores web HTTP/HTTPS (Nginx) y pasarelas de API (API Gateway).",
        styles["body"],
    ))
    story.append(Paragraph(
        "Para garantizar reproducibilidad absoluta, rigor científico y aislamiento estricto de red, "
        "el software opera bajo seis principios inquebrantables:",
        styles["body"],
    ))
    story.append(Paragraph("• <b>Ejecución 100% Local:</b> Cero telemetría hacia la nube y prohibición de APIs comerciales externas.", styles["bullet"]))
    story.append(Paragraph("• <b>Hardware Acotado:</b> Modelos cuantizados en 4 bits (GGUF Q4_K_M) con consumo de VRAM inferior a 8.0 GB.", styles["bullet"]))
    story.append(Paragraph("• <b>Terna Homogénea de Modelos:</b> Qwen3-8B (8.2B), GLM-4-9B-Chat (9.0B) y Phi-4-mini-instruct (3.8B).", styles["bullet"]))
    story.append(Paragraph("• <b>RAG Ultraliviano:</b> Recuperador léxico acotado BM25 con huella en memoria RAM ≤ 0.05 MB (límite arquitectónico: 0.45 GB).", styles["bullet"]))
    story.append(Paragraph("• <b>Seguridad Read-Only:</b> El agente de diagnóstico opera herramientas de red exclusivamente en modo de solo lectura (dig, curl, openssl).", styles["bullet"]))
    story.append(Paragraph("• <b>Determinismo Experimental:</b> Temperatura fijada en 0.0, semillas pseudoaleatorias reproducibles [42, 1337, 2026] y 3 repeticiones por escenario.", styles["bullet"]))

    story.append(Spacer(1, 8))
    story.append(make_callout(
        "El sistema implementa trazabilidad MLOps completa: cada inferencia y veredicto registra el commit hash de Git, "
        "la versión del motor Ollama, huella de hardware del host, tokens de razonamiento CoT (&lt;think&gt;) y digest criptográfico SHA-256.",
        styles,
        "CONTROL DE REPRODUCIBILIDAD MLOPS",
        COLOR_RED,
    ))

    # 2. Arquitectura de 7 Capas
    story.append(Spacer(1, 10))
    story.append(Paragraph("2. Arquitectura Global en 7 Capas Desacopladas", styles["h1"]))
    story.append(Paragraph(
        "La arquitectura del sistema sigue un modelo estrictamente desacoplado en 7 capas funcionales. "
        "Cada capa se encuentra encapsulada en su propio paquete dentro de <code>src/</code> y se comunica "
        "con las capas adyacentes a través de contratos tipados con Pydantic v2 (<code>src/core/contracts.py</code>).",
        styles["body"],
    ))

    capas_headers = ["Capa", "Agente / Subsistema", "Artefacto Emitido", "Módulo en src/", "Recurso Clave"]
    capas_rows = [
        ["1. Laboratorio", "ScenarioLabAgent", "escenario.yaml + Logs", "src/layer1_lab/", "Docker / Containerlab / BIND9 / Nginx"],
        ["2. Preproceso", "DataPipelineAgent", "ventana.jsonl", "src/layer2_pipeline/", "Drain3 (Log Clustering) + Jinja2"],
        ["3. RAG", "RAGKnowledgeAgent", "contexto.md", "src/layer3_rag/", "BM25 Retriever (RAM <= 0.05 MB)"],
        ["4. Inferencia", "InferenceEngineAgent", "respuesta.json", "src/layer4_inference/", "Ollama / GGUF Q4_K_M (VRAM <= 8GB)"],
        ["5. Orquestación", "DiagnosticOrchestratorAgent", "traza.jsonl", "src/layer5_orchestrator/", "LangGraph StateGraph + Tools Read-Only"],
        ["6. Interfaz", "InterfaceCLIAgent", "diagnostico.json/md", "src/layer6_interface/", "Typer CLI + FastAPI / HTMX / SSE"],
        ["7. Evaluación", "BenchmarkEvaluatorAgent", "resultados.csv", "src/layer7_evaluator/", "psutil / SciPy (Kruskal, Spearman, d)"],
    ]
    story.append(make_table(capas_headers, capas_rows, [70, 115, 110, 115, 122], styles, code_cols=[2, 3]))

    # 3. Contratos de Intercambio
    story.append(Spacer(1, 10))
    story.append(Paragraph("3. Especificación de Contratos de Datos (Pydantic v2)", styles["h1"]))
    story.append(Paragraph(
        "Los contratos definidos en <code>src/core/contracts.py</code> garantizan la interoperabilidad sin acoplamiento "
        "directo entre las capas. Entre los principales modelos de datos destacan:",
        styles["body"],
    ))
    story.append(Paragraph("• <b>EscenarioLabContract:</b> Modela el escenario inyectado, categoría (<code>DNS</code>, <code>HTTP_WEB</code>, <code>API_GATEWAY</code>, <code>TLS</code>), clase de falla (18 clases normalizadas), topología de red y ficha de Ground Truth (causa raíz, componente afectado, acción de mitigación y evidencia mínima requerida).", styles["bullet"]))
    story.append(Paragraph("• <b>VentanaLogContract:</b> Agrupa los registros normalizados por Drain3 (<code>ParsedLogEntry</code> con <code>template_id</code>, parámetros extraídos y nivel de severidad) junto a la telemetría resumida (tasa de error, latencia p50/p95).", styles["bullet"]))
    story.append(Paragraph("• <b>ContextoRAGContract:</b> Contiene la consulta realizada, los fragmentos normativos recuperados (<code>RAGDocumentChunk</code> con score BM25 y documento fuente), la concatenación Markdown formateada y la huella de memoria RAM consumida.", styles["bullet"]))
    story.append(Paragraph("• <b>RespuestaInferenciaContract:</b> Captura la respuesta cruda del modelo, texto de razonamiento CoT desacoplado de bloques <code>&lt;think&gt;</code>, tokens de entrada/salida, TTFT (ms), velocidad de decodificación (tok/s) y pico de VRAM.", styles["bullet"]))
    story.append(Paragraph("• <b>TrazaOrquestacionContract:</b> Bitácora de ejecución del grafo LangGraph con cada paso de herramienta ejecutado (<code>ToolExecutionStep</code>), comando exacto, salida obtenida e hipótesis contrastada.", styles["bullet"]))
    story.append(Paragraph("• <b>DiagnosticoFinalContract:</b> Dictamen final estructurado con causa raíz, componente identificado, acción recomendada, nivel de confianza, respaldado en evidencia y penalización por herramientas bloqueadas.", styles["bullet"]))
    story.append(Paragraph("• <b>ResultadoEvaluacionContract:</b> Fila canónica del dataset <code>resultados.csv</code> (27 columnas) integrando precisión booleana, coincidencia parcial continua (0.0-1.0), rúbrica explicativa (0-5), latencias p50/p95, energía estimada (kWh) y emisiones de CO2 (kg).", styles["bullet"]))

    # 4. Catálogo de Escenarios L7
    story.append(Spacer(1, 10))
    story.append(Paragraph("4. Catálogo de 18 Escenarios de Falla L7 sobre IP", styles["h1"]))
    story.append(Paragraph(
        "El catálogo cubre 18 anomalías operativas de alta recurrencia en infraestructuras de telecomunicaciones "
        "e Internet, organizadas en cuatro dominios:",
        styles["body"],
    ))

    sc_headers = ["ID Escenario", "Categoría", "Clase de Falla", "Componente Afectado", "Causa Raíz Esperada"]
    sc_rows = [
        ["DNS-DEL-01", "DNS", "DELEGATION_ERROR", "bind9-zone-delegation", "Error de delegación NS cojo (Lame Delegation)"],
        ["DNS-NXD-01", "DNS", "NXDOMAIN", "bind9-authoritative", "Registro de zona faltante o FQDN inexistente (RCODE 3)"],
        ["DNS-REF-01", "DNS", "DNS_REFUSED", "bind9-authoritative", "Consulta rechazada por lista de control de acceso ACL (RCODE 5)"],
        ["DNS-SRV-01", "DNS", "SERVFAIL", "bind9-recursive-resolver", "Falla de resolución recursiva o timeout hacia servidor raíz"],
        ["DNS-TRUNC-01", "DNS", "DNS_TRUNCATED_EDNS", "bind9-resolver-firewall", "Respuesta truncada TC=1 por buffer EDNS0 bloqueado en firewall"],
        ["HTTP-POOL-01", "API_GATEWAY", "CONNECTION_POOL_EXHAUSTED", "upstream-backend-api", "Agotamiento de pool de conexiones concurrentes en backend"],
        ["HTTP-403-01", "API_GATEWAY", "HTTP_403_FORBIDDEN", "nginx-api-gateway", "Acceso denegado por reglas de autorización o IP restringida"],
        ["HTTP-429-01", "API_GATEWAY", "HTTP_429_RATE_LIMITED", "nginx-rate-limiter", "Límite de tasa de peticiones excedido (Rate Limiting activo)"],
        ["HTTP-500-01", "HTTP_WEB", "HTTP_500_INTERNAL", "backend-application-code", "Excepción no controlada en el código de la aplicación backend"],
        ["HTTP-502-01", "API_GATEWAY", "HTTP_502_BAD_GATEWAY", "upstream-backend-api", "Conexión rechazada o caída del servicio upstream backend"],
        ["HTTP-503-01", "HTTP_WEB", "HTTP_503_SERVICE_UNAVAILABLE", "backend-application-pool", "Servicio sobrecargado o en mantenimiento temporal"],
        ["HTTP-504-01", "API_GATEWAY", "HTTP_504_GATEWAY_TIMEOUT", "upstream-backend-database", "Timeout de espera de respuesta desde el microservicio backend"],
        ["NET-LAT-01", "HTTP_WEB", "NETWORK_LATENCY_TC", "network-infrastructure", "Degradación por latencia anómala inyectada con tc-netem"],
        ["HTTP-ORIGIN-01", "API_GATEWAY", "ORIGIN_DOWN", "upstream-cluster", "Servidor de origen fuera de línea o sin conectividad de red"],
        ["TLS-CHN-01", "TLS", "TLS_CHAIN_INVALID", "nginx-tls-termination", "Cadena de confianza rota por omisión de certificado intermedio CA"],
        ["TLS-CIPH-01", "TLS", "TLS_CIPHER_MISMATCH", "nginx-tls-crypto-engine", "Negociación fallida por conjuntos de cifrado (ciphers) incompatibles"],
        ["TLS-EXP-01", "TLS", "TLS_EXPIRED_CERT", "nginx-tls-termination", "Certificado digital X.509 expirado en endpoint seguro"],
        ["TLS-SNI-01", "TLS", "TLS_SNI_MISMATCH", "nginx-tls-termination", "Discrepancia entre Server Name Indication (SNI) y certificado presentado"],
    ]
    story.append(make_table(sc_headers, sc_rows, [70, 75, 115, 115, 157], styles, code_cols=[0, 3]))

    # 5. RAG y Base Normativa
    story.append(Spacer(1, 10))
    story.append(Paragraph("5. Base de Conocimiento Normativo RAG BM25", styles["h1"]))
    story.append(Paragraph(
        "El módulo <code>src/layer3_rag/retriever.py</code> implementa un motor RAG basado en recuperación léxica "
        "acotada Okapi BM25 mediante <code>langchain_community.retrievers.BM25Retriever</code>. "
        "A diferencia de los enfoques vectoriales densos tradicionales que requieren modelos de embeddings de gran tamaño "
        "y bases de datos vectoriales en RAM, BM25 opera con una huella extremadamente ligera:",
        styles["body"],
    ))
    story.append(Paragraph("• <b>Consumo de RAM Verificado:</b> ≤ 0.05 MB (frente al límite máximo estipulado de 0.45 GB).", styles["bullet"]))
    story.append(Paragraph("• <b>Corpus Normativo:</b> 36 fragmentos técnicos indexados derivados de estándares de la IETF: <b>RFC 1035</b> (DNS), <b>RFC 9110</b> (Semántica HTTP), <b>RFC 8446</b> (Protocolo TLS 1.3) y Procedimientos Operativos Estándar (SOP) de telecomunicaciones.", styles["bullet"]))
    story.append(Paragraph("• <b>Parámetro k de Recuperación:</b> Top-k fijado en 2 fragmentos altamente relevantes incorporados dinámicamente al prompt.", styles["bullet"]))

    # 6. Inferencia Local y Terna de Modelos
    story.append(Spacer(1, 10))
    story.append(Paragraph("6. Subsistema de Inferencia Local y Terna de Modelos", styles["h1"]))
    story.append(Paragraph(
        "El motor <code>LocalInferenceEngine</code> (<code>src/layer4_inference/engine.py</code>) interactúa "
        "directamente con el daemon local de Ollama (o emulador sintético calibrado en ausencia de GPU activa). "
        "Todos los modelos operan con temperatura = 0.0 y cuantización Q4_K_M:",
        styles["body"],
    ))

    mod_headers = ["Modelo", "Proveedor", "Parámetros", "Licencia", "VRAM Aprox.", "Ventana Contexto", "Mecanismo Tools"]
    mod_rows = [
        ["Qwen3-8B", "Alibaba", "8.2B (6.95B sin emb)", "Apache 2.0", "5.5 GB", "32,768 tok", "Nativo / Razonamiento conmutable"],
        ["GLM-4-9B-Chat", "Zhipu AI", "9.0B", "GLM-4 License", "5.9 GB", "131,072 tok", "Berkeley Function Calling (81%)"],
        ["Phi-4-mini-instruct", "Microsoft", "3.8B", "MIT", "2.8 GB", "131,072 tok", "JSON Schema Tool Format"],
    ]
    story.append(make_table(mod_headers, mod_rows, [85, 65, 85, 75, 65, 75, 82], styles, code_cols=[0]))

    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "<b>Medición de Telemetría:</b> El subsistema instrumenta con precisión de microsegundos el "
        "<i>Time to First Token</i> (TTFT = t_primer_token - t_envio_prompt) y la velocidad de decodificación "
        "<i>Tokens por Segundo</i> (tok/s = tokens_generados / t_generacion). "
        "Asimismo, desacopla mediante expresiones regulares los bloques de razonamiento interno "
        "<code>&lt;think&gt;...&lt;/think&gt;</code> para auditar la cadena de pensamiento (Chain-of-Thought).",
        styles["body"],
    ))

    # 7. Orquestación LangGraph y Herramientas Read-Only
    story.append(Spacer(1, 10))
    story.append(Paragraph("7. Orquestación Agéntica LangGraph y Seguridad Read-Only", styles["h1"]))
    story.append(Paragraph(
        "El diagnóstico de fallas no se realiza en una sola llamada generativa pasiva, sino a través de un "
        "grafo de estados determinista (<code>src/layer5_orchestrator/agent.py</code>) construido con <b>LangGraph</b>. "
        "El ciclo operativo transita por 6 nodos:",
        styles["body"],
    ))
    story.append(Paragraph("1. <code>ingest_telemetry:</code> Carga la ventana de logs normalizada con Drain3 y métricas de error.", styles["bullet"]))
    story.append(Paragraph("2. <code>retrieve_rag_knowledge:</code> Recupera fragmentos de RFCs relevantes según el síntoma observado.", styles["bullet"]))
    story.append(Paragraph("3. <code>formulate_hypothesis:</code> El SLM propone una hipótesis técnica y selecciona una herramienta de verificación.", styles["bullet"]))
    story.append(Paragraph("4. <code>execute_read_only_tool:</code> Ejecuta el comando de red verificado por la lista blanca de seguridad.", styles["bullet"]))
    story.append(Paragraph("5. <code>evaluate_evidence:</code> El agente contrasta la salida del comando con la hipótesis planteada.", styles["bullet"]))
    story.append(Paragraph("6. <code>synthesize_diagnosis:</code> Emite el veredicto estructurado con causa raíz, componente y mitigación NOC.", styles["bullet"]))

    story.append(Spacer(1, 6))
    story.append(make_callout(
        "<b>Política de Solo Lectura:</b> <code>src/layer5_orchestrator/tools.py</code> restringe la ejecución a una lista blanca "
        "estricta de utilitarios (<code>dig</code>, <code>curl</code>, <code>openssl s_client</code>). "
        "Cualquier intento de concatenación de comandos (<code>;</code>, <code>&amp;&amp;</code>, <code>|</code>), redirección o "
        "modificación del sistema operativo (<code>rm</code>, <code>iptables</code>, <code>systemctl</code>) es interceptado y bloqueado, "
        "aplicando una penalización de 1.0 punto al score del modelo.",
        styles,
        "SEGURIDAD OPERATIVA Y SANDBOXING READ-ONLY",
        COLOR_NAVY,
    ))

    # 8. Métricas y Análisis Estadístico SciPy
    story.append(Spacer(1, 10))
    story.append(Paragraph("8. Métricas de Evaluación y Análisis Estadístico SciPy", styles["h1"]))
    story.append(Paragraph(
        "El módulo <code>src/layer7_evaluator/</code> somete el desempeño de los modelos a un análisis multidimensional riguroso:",
        styles["body"],
    ))
    story.append(Paragraph("• <b>Exactitud de Causa Raíz (Booleana):</b> Concordancia estricta con la ficha de Ground Truth mediante conceptos canónicos normalizados (<code>configs/evaluator_concepts.yaml</code>).", styles["bullet"]))
    story.append(Paragraph("• <b>Score de Coincidencia Parcial (0.0 - 1.0):</b> Evaluación léxico-semántica continua calculada mediante distancia de tokens y cobertura de conceptos clave.", styles["bullet"]))
    story.append(Paragraph("• <b>Rúbrica de Explicación (0 a 5 puntos):</b> Califica coherencia técnica, fundamentación con normas RFC, correcta identificación del componente y pertinencia de la mitigación sugerida.", styles["bullet"]))
    story.append(Paragraph("• <b>Score de Eficiencia Compuesto (OE4):</b> Combina precisión diagnóstica (40%), rúbrica de explicación (20%), velocidad de inferencia normalizada (20%) y eficiencia de VRAM (20%).", styles["bullet"]))
    story.append(Paragraph("• <b>Pruebas de Hipótesis SciPy (Tarea 4.1.2):</b>", styles["body"]))
    story.append(Paragraph("  - <i>Kruskal-Wallis H-test:</i> Prueba no paramétrica para contrastar diferencias entre los 3 modelos (confirmando significancia p &lt; 0.001 en TTFT, tok/s, latencia y energía).", styles["bullet"]))
    story.append(Paragraph("  - <i>Correlación de Spearman (ρ) y Pearson (r):</i> Evalúa la relación entre tamaño de parámetros y latencia/precisión.", styles["bullet"]))
    story.append(Paragraph("  - <i>Tamaño del Efecto d de Cohen:</i> Cuantifica la magnitud de la diferencia entre pares (confirmando efectos grandes |d| ≥ 0.8 en 6 de 9 comparaciones).", styles["bullet"]))
    story.append(Paragraph("  - <i>Intervalos de Confianza al 95%:</i> Calculados vía estimación asintótica / bootstrap para cada métrica clave.", styles["bullet"]))

    # 9. Referencia API REST y CLI
    story.append(Spacer(1, 10))
    story.append(Paragraph("9. Referencia de la API REST y Comandos CLI", styles["h1"]))
    story.append(Paragraph(
        "El sistema provee interfaces duales: una interfaz de línea de comandos basada en <b>Typer</b> "
        "(<code>benchapp</code>) para automatización por lotes, y un servidor web <b>FastAPI</b> "
        "con endpoints REST y streaming por Server-Sent Events (SSE).",
        styles["body"],
    ))

    api_headers = ["Método", "Ruta del Endpoint", "Módulo", "Descripción Funcional"]
    api_rows = [
        ["GET", "/api/scenarios", "web.py", "Lista los 18 escenarios de falla con su Ground Truth"],
        ["GET", "/api/models", "web.py", "Consulta la terna de modelos y estado en Ollama"],
        ["POST", "/api/models/pull", "web.py", "Descarga dinámica de nuevos modelos SLM desde Ollama"],
        ["GET", "/api/health", "web.py", "Diagnóstico de salud del subsistema Ollama, VRAM y modos"],
        ["POST", "/api/ejecutar", "web.py", "Inicia diagnóstico interactivo vía HTMX devolviendo visor SSE"],
        ["GET", "/stream-diagnostico", "observability.py", "Flujo SSE en tiempo real de eventos del grafo LangGraph"],
        ["POST", "/api/execute-suite", "observability.py", "Ejecuta la suite continua de 18 escenarios en secuencia"],
        ["GET", "/vistas/comparativo", "web.py", "Fragmento HTML de la matriz comparativa de modelos (OE4)"],
        ["GET", "/vistas/correlacion", "web.py", "Fragmento HTML del análisis correlacional y estadístico SciPy"],
        ["GET", "/api/export/excel", "web.py", "Exporta libro Excel multioja profesional (.xlsx)"],
        ["GET", "/api/export/pdf/comparative", "web.py", "Descarga reporte institucional en PDF del OE4"],
    ]
    story.append(make_table(api_headers, api_rows, [50, 150, 95, 237], styles, code_cols=[1, 2]))

    story.append(Spacer(1, 8))
    story.append(Paragraph("<b>Comandos de la CLI (<code>benchapp</code>):</b>", styles["body"]))
    story.append(make_code_box(
        "# Listar catálogo de escenarios y modelos\n"
        ".venv\\Scripts\\benchapp.exe list-scenarios\n"
        ".venv\\Scripts\\benchapp.exe list-models\n\n"
        "# Consulta léxica RAG contra corpus normativo\n"
        ".venv\\Scripts\\benchapp.exe rag-query \"falla de certificado expirado\"\n\n"
        "# Ejecutar diagnóstico de un escenario individual\n"
        ".venv\\Scripts\\benchapp.exe run-scenario DNS-NXD-01 --model phi-4-mini-instruct --seed 42\n\n"
        "# Ejecutar benchmark automatizado (3 modelos x 18 escenarios x 3 semillas)\n"
        ".venv\\Scripts\\benchapp.exe run-benchmark --seeds 42,1337,2026 --repetitions 1\n\n"
        "# Análisis estadístico y exportación de entregables\n"
        ".venv\\Scripts\\benchapp.exe analyze-correlation\n"
        ".venv\\Scripts\\benchapp.exe export-excel\n"
        ".venv\\Scripts\\benchapp.exe export-pdf --type all\n\n"
        "# Iniciar servidor web de observabilidad\n"
        ".venv\\Scripts\\benchapp.exe serve-dashboard --host 127.0.0.1 --port 8000",
        styles,
    ))

    # 10. Despliegue y Pruebas
    story.append(Spacer(1, 10))
    story.append(Paragraph("10. Procedimiento de Despliegue y Batería de Pruebas", styles["h1"]))
    story.append(Paragraph(
        "El framework cuenta con una suite integral de <b>160 pruebas automatizadas</b> "
        "(158 unitarias deterministas y 2 de integración en contenedores Docker reales):",
        styles["body"],
    ))
    story.append(Paragraph("• <code>tests/test_contracts.py:</code> Validación de esquemas Pydantic y serialización JSON de las 7 capas.", styles["bullet"]))
    story.append(Paragraph("• <code>tests/test_layer1_lab.py:</code> Carga e integridad técnica de los 18 archivos YAML del catálogo.", styles["bullet"]))
    story.append(Paragraph("• <code>tests/test_layer2_pipeline.py:</code> Agrupamiento de logs con Drain3 y renderizado de plantillas Jinja2.", styles["bullet"]))
    story.append(Paragraph("• <code>tests/test_layer3_rag.py:</code> Medición de huella RAM de BM25 (≤ 0.05 MB) y relevancia de fragmentos.", styles["bullet"]))
    story.append(Paragraph("• <code>tests/test_layer4_inference.py:</code> Telemetría de TTFT, tok/s y desacoplamiento de bloques &lt;think&gt;.", styles["bullet"]))
    story.append(Paragraph("• <code>tests/test_layer5_orchestrator.py:</code> Transiciones del grafo LangGraph y lista blanca de herramientas de red.", styles["bullet"]))
    story.append(Paragraph("• <code>tests/test_statistical_analysis.py:</code> Verificación de cálculos de Kruskal-Wallis, Spearman y Cohen's d.", styles["bullet"]))
    story.append(Paragraph("• <code>tests/test_exporters.py:</code> Generación correcta de archivos Excel (.xlsx) y reportes en PDF.", styles["bullet"]))

    story.append(Spacer(1, 8))
    story.append(Paragraph("<b>Ejecución de Pruebas:</b>", styles["body"]))
    story.append(make_code_box(
        "# Ejecutar todas las pruebas unitarias deterministas (tiempo < 5 segundos)\n"
        ".venv\\Scripts\\pytest.exe -v tests/\n\n"
        "# Ejecutar verificación integral de pre-vuelo del sistema\n"
        ".venv\\Scripts\\benchapp.exe doctor",
        styles,
    ))

    return story


# ============================================================================
# CONSTRUCCIÓN DEL MANUAL DE USUARIO (CON PANTALLAZOS REALES)
# ============================================================================

def build_manual_usuario_story(styles):
    story = []
    add_cover(
        story,
        "MANUAL DE USUARIO Y GUÍA OPERATIVA",
        "Operación del Dashboard Interactivo, Diagnóstico en Streaming en Vivo, Gestión de Modelos y Análisis Comparativo con Pantallazos Reales",
        styles,
    )

    # 1. Bienvenida y Requisitos
    story.append(Paragraph("1. Bienvenida y Requisitos del Entorno", styles["h1"]))
    story.append(Paragraph(
        "Bienvenido a la <b>Guía de Usuario de NetDiagBench-L7</b>. Esta aplicación web y CLI permite a operadores "
        "de Centros de Operaciones de Red (NOC), administradores de sistemas e investigadores evaluar "
        "y operar asistentes inteligentes basados en Modelos de Lenguaje Pequeños (SLMs) locales para diagnosticar "
        "fallas en servicios de red L7 sobre IP en tiempo real.",
        styles["body"],
    ))
    story.append(Paragraph(
        "<b>Requisitos Recomendados de Hardware y Software:</b>",
        styles["body"],
    ))
    story.append(Paragraph("• <b>Sistema Operativo:</b> Windows 11 / 10 (64-bit) o Linux Ubuntu 22.04+.", styles["bullet"]))
    story.append(Paragraph("• <b>GPU Dedicada:</b> NVIDIA GeForce RTX con mínimo 8 GB de VRAM (CUDA ≥ 12.0) o procesador CPU de 8 núcleos para modo determinista.", styles["bullet"]))
    story.append(Paragraph("• <b>Memoria RAM:</b> 32 GB RAM recomendados (16 GB mínimo para ejecución de modelos 8B/9B).", styles["bullet"]))
    story.append(Paragraph("• <b>Almacenamiento:</b> 25 GB libres en disco de estado sólido (NVMe/SSD) para almacenar modelos GGUF y registros.", styles["bullet"]))
    story.append(Paragraph("• <b>Software Requerido:</b> Python 3.11+, Ollama (opcional para inferencia en GPU en vivo) y navegador web moderno (Chrome / Edge / Firefox).", styles["bullet"]))

    # 2. Puesta en Marcha
    story.append(Spacer(1, 10))
    story.append(Paragraph("2. Inicio Rápido de la Aplicación", styles["h1"]))
    story.append(Paragraph(
        "Para iniciar el sistema de diagnóstico interactivo existen dos métodos directos:",
        styles["body"],
    ))
    story.append(Paragraph("<b>Opción A: Lanzador rápido PowerShell (Demostración y Sustentación):</b>", styles["body"]))
    story.append(make_code_box(
        "# En la raíz del proyecto, ejecute el script oficial de lanzamiento:\n"
        "powershell -ExecutionPolicy Bypass -File scripts\\launch_demo.ps1",
        styles,
    ))
    story.append(Spacer(1, 4))
    story.append(Paragraph("<b>Opción B: Arranque manual mediante la CLI:</b>", styles["body"]))
    story.append(make_code_box(
        "# 1. Activar el entorno virtual\n"
        ".\\.venv\\Scripts\\Activate.ps1\n\n"
        "# 2. Iniciar el servidor web interactivo FastAPI\n"
        "benchapp serve-dashboard --host 127.0.0.1 --port 8000\n\n"
        "# 3. Abra su navegador en: http://localhost:8000",
        styles,
    ))

    # 3. Recorrido por la Interfaz de Usuario
    story.append(Spacer(1, 10))
    story.append(Paragraph("3. Recorrido General por la Interfaz Web", styles["h1"]))
    story.append(Paragraph(
        "La interfaz del sistema está construida con arquitectura <b>Local-First</b> utilizando Tailwind CSS, "
        "HTMX para interactividad reactiva sin recarga de página, Alpine.js para control modal y Server-Sent Events (SSE) "
        "para transmitir la telemetría en streaming mientras el agente SLM razona y diagnostica.",
        styles["body"],
    ))

    # Pantallazo 1: Pantalla Principal
    story.append(make_image_box(
        SHOTS_DIR / "u01_inicio.png",
        "Figura 1: Pantalla principal de NetDiagBench-L7 mostrando el Visor de Diagnóstico, barra lateral de navegación y panel de configuración inicial.",
        styles,
        width_in=6.8,
        height_in=3.8,
    ))

    story.append(Paragraph(
        "La interfaz se estructura en cuatro cuadrantes principales:",
        styles["body"],
    ))
    story.append(Paragraph("1. <b>Barra de Navegación Lateral (Izquierda):</b> Permite conmutar instantáneamente entre las 5 vistas maestras: Visor de Diagnóstico (1), Informe Comparativo OE4 (2), Análisis Correlacional SciPy (3), Informe Consolidado HTML (4) y Suite de Observabilidad (5).", styles["bullet"]))
    story.append(Paragraph("2. <b>Panel de Ground Truth y Bitácora (Lateral Inferior):</b> Presenta los datos de verdad terreno del escenario activo y el historial en memoria de los diagnósticos previos.", styles["bullet"]))
    story.append(Paragraph("3. <b>Barra Superior (Header):</b> Muestra la insignia de ejecución 100% Local, el estado de conectividad en vivo con Ollama (latencia ping en milisegundos y modelos cargados), monitor de VRAM y botón de cambio de tema visual.", styles["bullet"]))
    story.append(Paragraph("4. <b>Espacio de Trabajo Central (Workspace):</b> Área reactiva donde se configuran los parámetros de prueba y se renderiza el streaming en tiempo real.", styles["bullet"]))

    # Pantallazo 2: Encabezado y Telemetría
    story.append(Spacer(1, 8))
    story.append(Paragraph("4. Barra Superior y Monitor de Recursos", styles["h1"]))
    story.append(make_image_box(
        SHOTS_DIR / "u02_encabezado.png",
        "Figura 2: Encabezado institucional con estado de Ollama Live, latencia de ping, conteo de modelos locales y huella de VRAM cuantizada (Q4_K_M).",
        styles,
        width_in=6.8,
        height_in=1.1,
    ))
    story.append(Paragraph(
        "La barra superior garantiza que el jurado evaluador o el operador verifiquen en todo momento "
        "que el sistema no depende de internet externo y que la GPU opera dentro del límite de 8 GB VRAM. "
        "El badge verde <b>OLLAMA LIVE</b> pulsa activamente mientras el motor de inferencia responde a las peticiones locales.",
        styles["body"],
    ))

    # Pantallazo 3: Filtro de Categorías L7
    story.append(Spacer(1, 10))
    story.append(Paragraph("5. Selección y Filtrado Rápido de Escenarios", styles["h1"]))
    story.append(Paragraph(
        "El operador puede filtrar rápidamente los 18 escenarios de red por su tecnología específica "
        "utilizando las píldoras de filtro: <b>Todos</b>, <b>DNS</b>, <b>TLS</b>, <b>HTTP</b> y <b>GW</b> (API Gateway).",
        styles["body"],
    ))
    story.append(make_image_box(
        SHOTS_DIR / "u03_filtro_tls.png",
        "Figura 3: Filtro por categoría 'TLS' seleccionando el escenario TLS-EXP-01 con carga automática de la ficha técnica.",
        styles,
        width_in=6.8,
        height_in=3.8,
    ))

    # Pantallazo 4: Ficha Ground Truth
    story.append(Spacer(1, 8))
    story.append(Paragraph("6. Ficha Técnica de Ground Truth (Verdad Terreno)", styles["h1"]))
    story.append(make_image_box(
        SHOTS_DIR / "u04_ground_truth.png",
        "Figura 4: Ficha lateral de Ground Truth detallando la causa raíz esperada, componente afectado y el Procedimiento Operativo Estándar (SOP).",
        styles,
        width_in=3.6,
        height_in=3.8,
    ))
    story.append(Paragraph(
        "Al seleccionar un escenario, la ficha lateral izquierda se actualiza automáticamente indicando "
        "el diagnóstico de referencia establecido por el laboratorio. Esto permite contrastar visualmente "
        "la predicción del modelo con la verdad técnica inyectada en el tráfico de red.",
        styles["body"],
    ))

    # Pantallazo 5: Paleta de Comandos Ctrl+K
    story.append(Spacer(1, 10))
    story.append(Paragraph("7. Paleta de Comandos de Acceso Rápido (Ctrl + K)", styles["h1"]))
    story.append(Paragraph(
        "Para operadores avanzados, la aplicación incorpora una paleta de comandos tipo terminal "
        "accesible mediante la combinación de teclas <code>Ctrl + K</code> o haciendo clic en el buscador superior:",
        styles["body"],
    ))
    story.append(make_image_box(
        SHOTS_DIR / "u05_paleta_comandos.png",
        "Figura 5: Paleta de comandos modal rápida para navegación entre vistas, ejecución de diagnósticos y alternancia de temas.",
        styles,
        width_in=6.0,
        height_in=3.4,
    ))

    # Pantallazo 6: Gestor de Modelos Ollama
    story.append(Spacer(1, 10))
    story.append(Paragraph("8. Gestor Interactivo de Modelos SLM (Ollama Hub)", styles["h1"]))
    story.append(Paragraph(
        "Haciendo clic en el botón <b>+ Añadir nuevo modelo</b> en la barra de configuración, se despliega "
        "un catálogo categorizado de modelos ligeros disponibles para ser descargados directamente en local:",
        styles["body"],
    ))
    story.append(make_image_box(
        SHOTS_DIR / "u06_modal_agregar_modelo.png",
        "Figura 6: Gestor de modelos SLM locales organizado por categorías: Ultraligeros (≤2B), Razonamiento CoT (DeepSeek-R1), Intermedios (3B-4B), Código y Capacidad Completa (7B-9B).",
        styles,
        width_in=6.8,
        height_in=3.8,
    ))
    story.append(Paragraph(
        "El usuario puede pulsar sobre cualquier etiqueta (por ejemplo <code>phi4-mini:instruct</code> o <code>qwen2.5:1.5b</code>) "
        "para iniciar la descarga con barra de progreso en vivo vía Server-Sent Events, o ingresar una etiqueta personalizada.",
        styles["body"],
    ))

    # Pantallazo 7: Tema Claro
    story.append(Spacer(1, 8))
    story.append(Paragraph("9. Soporte para Modo Claro / Diurno", styles["h1"]))
    story.append(make_image_box(
        SHOTS_DIR / "u07_modo_claro.png",
        "Figura 7: Visualización del sistema en Tema Claro con alto contraste y paleta institucional (Rojo Pamplona #ad3333 y Azul Marino #003366).",
        styles,
        width_in=6.8,
        height_in=3.8,
    ))

    # Pantallazos 8 y 9: Ejecución en Streaming
    story.append(Spacer(1, 10))
    story.append(Paragraph("10. Ejecución del Diagnóstico y Streaming en Vivo", styles["h1"]))
    story.append(Paragraph(
        "Para ejecutar un diagnóstico interactivo, seleccione el escenario deseado (ej. <code>DNS-NXD-01</code>), "
        "el modelo de lenguaje (ej. <code>Phi-4-mini-instruct</code>), la semilla determinista (<code>42</code>) y presione "
        "el botón rojo <b>Ejecutar Diagnóstico (CTRL + ↵)</b>.",
        styles["body"],
    ))
    story.append(make_image_box(
        SHOTS_DIR / "u22_diagnostico_streaming.png",
        "Figura 8: Terminal de Observabilidad en streaming mostrando el Stepper de 5 fases activas y la ingesta de telemetría y RAG en tiempo real.",
        styles,
        width_in=6.8,
        height_in=3.8,
    ))
    story.append(Paragraph(
        "Durante el procesamiento, el Stepper superior ilustra el avance por las 5 etapas del agente LangGraph: "
        "<b>1. TELEMETRÍA</b> (Drain3 PCAP) → <b>2. RAG IETF</b> (Normas RFC) → <b>3. RAZONAMIENTO</b> (CoT Hipótesis) → "
        "<b>4. CONSOLA CLI</b> (Read-Only Tool) → <b>5. VEREDICTO</b> (Causa & Mitigación).",
        styles["body"],
    ))

    # Pantallazo 10: Evidencias de Terminal Read-Only
    story.append(Spacer(1, 8))
    story.append(Paragraph("11. Verificación de Evidencia en Terminal Read-Only", styles["h1"]))
    story.append(make_image_box(
        SHOTS_DIR / "u24_diagnostico_detalle_1.png",
        "Figura 9: Consola de evidencia donde el agente SLM ejecuta herramientas de red de solo lectura (dig @127.0.0.1 A) para comprobar su hipótesis.",
        styles,
        width_in=6.8,
        height_in=3.8,
    ))
    story.append(Paragraph(
        "El operador puede inspeccionar la caja de terminal verde tipo bash donde se aprecia el comando exacto "
        "invocado por el modelo (<code>dig @127.0.0.1 -p 5353 app.internal.corp A</code>) y la respuesta del servidor BIND9 "
        "(<code>status: NXDOMAIN</code>), garantizando total auditabilidad.",
        styles["body"],
    ))

    # Pantallazo 11: Veredicto Final y Mitigación
    story.append(Spacer(1, 10))
    story.append(Paragraph("12. Veredicto Final, Confianza y Mitigación NOC", styles["h1"]))
    story.append(make_image_box(
        SHOTS_DIR / "u23_diagnostico_final.png",
        "Figura 10: Tarjeta de Veredicto Final con causa raíz sintetizada, componente culpable, acción correctiva SOP, fundamentación técnica y nivel de confianza.",
        styles,
        width_in=6.8,
        height_in=3.8,
    ))
    story.append(Paragraph(
        "Una vez concluido el ciclo, el sistema genera la tarjeta formal de diagnóstico destacando:",
        styles["body"],
    ))
    story.append(Paragraph("• <b>Causa Raíz Identificada:</b> Explicación concisa del origen del fallo.", styles["bullet"]))
    story.append(Paragraph("• <b>Componente Afectado:</b> Elemento de red o microservicio específico que debe ser intervenido.", styles["bullet"]))
    story.append(Paragraph("• <b>Acción Sugerida (SOP):</b> Procedimiento operativo recomendado para restaurar el servicio.", styles["bullet"]))
    story.append(Paragraph("• <b>Botón 'Copiar Ficha para Ticket':</b> Permite copiar al portapapeles el dictamen en formato Markdown para abrir un ticket de soporte en Jira o ServiceNow.", styles["bullet"]))

    # Pantallazo 12: Bitácora de Sesión
    story.append(Spacer(1, 8))
    story.append(Paragraph("13. Bitácora de Sesión en Memoria RAM", styles["h1"]))
    story.append(make_image_box(
        SHOTS_DIR / "u25_bitacora.png",
        "Figura 11: Bitácora de sesión interactiva registrando diagnósticos previos, aciertos, fallas y uso de memoria LangGraph MemorySaver.",
        styles,
        width_in=3.6,
        height_in=3.8,
    ))
    story.append(Paragraph(
        "La bitácora lateral almacena las ejecuciones recientes de la sesión. Permite al usuario hacer clic "
        "en cualquier diagnóstico histórico para recargar instantáneamente su traza completa sin reejecutar la inferencia.",
        styles["body"],
    ))

    # Pantallazo 13: Informe Comparativo OE4
    story.append(Spacer(1, 10))
    story.append(Paragraph("14. Informe Técnico Comparativo Multidimensional (OE4)", styles["h1"]))
    story.append(Paragraph(
        "Al seleccionar la pestaña <b>Informe Comparativo (OE4)</b> en el menú lateral, se presenta el "
        "análisis consolidado de las 162 corridas experimentales evaluando los 3 modelos de la terna:",
        styles["body"],
    ))
    story.append(make_image_box(
        PROBE_DIR / "comparativo.png",
        "Figura 12: Informe Comparativo Multidimensional (OE4) con tarjetas de perfil de modelo, scores de compromiso compuesto (0.860 vs 0.850 vs 0.746) y métricas de trade-off.",
        styles,
        width_in=6.8,
        height_in=3.8,
    ))
    story.append(Paragraph(
        "La vista clasifica a los modelos según su caso de uso óptimo en infraestructura:",
        styles["body"],
    ))
    story.append(Paragraph("• <b>GLM-4-9B-Chat (Score 0.860):</b> <i>Recomendado para Centro de Operaciones (NOC)</i> por su precisión superior (88.9%), soporte de contexto de 128k y robustez en seguimiento de herramientas.", styles["bullet"]))
    story.append(Paragraph("• <b>Qwen3-8B (Score 0.850):</b> <i>Recomendado para Recursos Acotados</i> por su equilibrio en razonamiento CoT (&lt;thought&gt;), alta fidelidad en componentes (74.1%) y 4.48/5.0 en rúbrica.", styles["bullet"]))
    story.append(Paragraph("• <b>Phi-4-mini-instruct (Score 0.746):</b> <i>Orientado a Triaje de Borde (Edge Triage)</i> por su mínima huella de VRAM (2.8 GB), bajísimo TTFT (84.4 ms) y alta velocidad (4.5 tok/s).", styles["bullet"]))

    # Pantallazo 14: Análisis Correlacional SciPy
    story.append(Spacer(1, 10))
    story.append(Paragraph("15. Análisis Correlacional y Significancia Estadística", styles["h1"]))
    story.append(make_image_box(
        PROBE_DIR / "correlacion.png",
        "Figura 13: Vista de Análisis Correlacional (Tarea 4.1.2) con pruebas Kruskal-Wallis, coeficientes de Spearman/Pearson, intervalos de confianza 95% y tamaños de efecto d de Cohen.",
        styles,
        width_in=6.8,
        height_in=3.8,
    ))
    story.append(Paragraph(
        "Esta sección valida científicamente ante el jurado que las diferencias observadas no se deben al azar. "
        "Las 6 pruebas de Kruskal-Wallis rechazan la hipótesis nula (p &lt; 0.001) para TTFT, tokens/s, latencia y energía, "
        "confirmando que el tamaño del modelo tiene un impacto significativo en los recursos computacionales consumidos.",
        styles["body"],
    ))

    # Pantallazo 15: Suite de Observabilidad
    story.append(Spacer(1, 10))
    story.append(Paragraph("16. Suite de Observabilidad Continua (18 Escenarios)", styles["h1"]))
    story.append(make_image_box(
        PROBE_DIR / "observabilidad.png",
        "Figura 14: Suite de Observabilidad completa para la ejecución secuencial desatendida de los 18 escenarios catalogados.",
        styles,
        width_in=6.8,
        height_in=3.8,
    ))
    story.append(Paragraph(
        "La Suite de Observabilidad permite poner a prueba la batería completa de 18 escenarios de forma secuencial "
        "y determinista. El operador puede iniciar o detener la prueba con un solo clic, visualizando el avance acumulado "
        "y exportando al finalizar el reporte integral en PDF o Excel.",
        styles["body"],
    ))

    # 17. Exportación de Entregables
    story.append(Spacer(1, 10))
    story.append(Paragraph("17. Barra de Herramientas de Exportación", styles["h1"]))
    story.append(Paragraph(
        "En la esquina superior derecha de cada vista se encuentra la barra flotante de exportación, "
        "la cual permite descargar los resultados en múltiples formatos estándar de la industria:",
        styles["body"],
    ))
    story.append(Paragraph("• <b>Descargar Excel (.xlsx):</b> Genera el libro multioja con tablas dinámicas de resultados, comparativas y análisis correlacional.", styles["bullet"]))
    story.append(Paragraph("• <b>Exportar Reporte PDF:</b> Descarga el documento formal en PDF listo para impresión o anexar al trabajo de grado.", styles["bullet"]))
    story.append(Paragraph("• <b>Descargar CSV / JSON:</b> Permite a investigadores cargar las 162 filas de datos en Python (Pandas), R o MATLAB.", styles["bullet"]))
    story.append(Paragraph("• <b>Botón de Imprimir:</b> Formatea la vista web para impresión limpia o guardado directo a PDF del navegador.", styles["bullet"]))

    # 18. Solución de Problemas Frecuentes
    story.append(Spacer(1, 10))
    story.append(Paragraph("18. Preguntas Frecuentes y Solución de Problemas (FAQ)", styles["h1"]))
    story.append(Paragraph(
        "<b>P: ¿Qué hacer si Ollama muestra estado desconectado (badge rojo)?</b><br/>"
        "R: El sistema activa automáticamente el <i>Simulador Sintético Calibrado</i> de alta fidelidad, permitiendo "
        "la demostración completa sin interrupciones. Para levantar Ollama, abra una terminal y ejecute <code>ollama serve</code>.",
        styles["body"],
    ))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "<b>P: ¿Cómo verificar que no se sobrepasan los 8 GB de VRAM?</b><br/>"
        "R: El monitor superior y el comando <code>benchapp doctor</code> auditan el consumo de VRAM en tiempo real. "
        "Ningún modelo de la terna supera los 5.9 GB de VRAM en su cuantización Q4_K_M.",
        styles["body"],
    ))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "<b>P: ¿Dónde se guardan los reportes y diagnósticos exportados?</b><br/>"
        "R: Todos los artefactos se depositan de manera determinista en el directorio <code>data/benchmark_results/</code> "
        "y los registros individuales en <code>data/runs/</code>.",
        styles["body"],
    ))

    return story


# ============================================================================
# EXPORTACIÓN A MARKDOWN PARA EL REPOSITORIO
# ============================================================================

def export_markdown_files():
    """Genera las versiones completas en Markdown en docs/ para trazabilidad en Git."""
    # Manual Técnico Markdown
    tecnico_md = DOCS_DIR / "MANUAL_TECNICO_SISTEMA.md"
    tecnico_md.write_text("""# NetDiagBench-L7 • Manual Técnico del Sistema
**Proyecto de Grado — Universidad de Pamplona**  
**Facultad de Ingenierías y Arquitectura — Departamento E.E.S.T.**  
**Autor:** Juan David León Arrieta (`juan.leon22@unipamplona.edu.co`)  
**Director:** Mg. Richard Eliseo Mendoza Gáfaro (`richard.mendoza@unipamplona.edu.co`)  
**Versión:** 1.0.0 | **Fecha:** Noviembre 2026 | **Aislamiento:** 100% Local (8GB VRAM)

---

## 1. Introducción y Arquitectura General
NetDiagBench-L7 es un framework experimental diseñado para evaluar de forma reproducible el desempeño de Modelos de Lenguaje Pequeños (SLMs) en el diagnóstico de fallas complejas de Capa 7 (DNS, HTTP y TLS) bajo restricciones estrictas de hardware (8 GB VRAM, 32 GB RAM).

### Principios Fundamentales
1. **Ejecución 100% Local:** Ningún dato, registro ni petición sale a internet.
2. **Cuantización a 4 bits:** Formato GGUF Q4_K_M con Ollama / llama.cpp.
3. **Terna Homogénea:** Qwen3-8B (8.2B), GLM-4-9B-Chat (9.0B) y Phi-4-mini-instruct (3.8B).
4. **RAG BM25 Ultraliviano:** Huella en RAM ≤ 0.05 MB (frente al límite máximo de 0.45 GB).
5. **Seguridad Read-Only:** El agente solo opera herramientas de red no invasivas (`dig`, `curl`, `openssl`).
6. **Determinismo Científico:** Temperatura = 0.0, semillas `[42, 1337, 2026]` y 3 réplicas por escenario.

---

## 2. Contratos de Intercambio de Artefactos (src/core/contracts.py)
El sistema opera desacoplado en 7 capas funcionales mediante contratos Pydantic v2:
- **Capa 1 (Laboratorio):** `EscenarioLabContract` (`escenario.yaml` + Logs).
- **Capa 2 (Preproceso):** `VentanaLogContract` (`ventana.jsonl` con Drain3 y telemetría).
- **Capa 3 (RAG):** `ContextoRAGContract` (`contexto.md` con 2 fragmentos IETF).
- **Capa 4 (Inferencia):** `RespuestaInferenciaContract` (`respuesta.json` con TTFT y tok/s).
- **Capa 5 (Orquestación):** `TrazaOrquestacionContract` (`traza.jsonl` del grafo LangGraph).
- **Capa 6 (Interfaz):** `DiagnosticoFinalContract` (`diagnostico.json` y `diagnostico.md`).
- **Capa 7 (Evaluación):** `ResultadoEvaluacionContract` (`resultados.csv` con 27 columnas).

---

## 3. Catálogo de los 18 Escenarios de Falla L7
| ID Escenario | Categoría | Clase de Falla | Componente Afectado | Causa Raíz Esperada |
|---|---|---|---|---|
| `DNS-DEL-01` | DNS | DELEGATION_ERROR | `bind9-zone-delegation` | Error de delegación NS cojo (Lame Delegation) |
| `DNS-NXD-01` | DNS | NXDOMAIN | `bind9-authoritative` | Registro de zona faltante o FQDN inexistente (RCODE 3) |
| `DNS-REF-01` | DNS | DNS_REFUSED | `bind9-authoritative` | Consulta rechazada por lista de control de acceso ACL |
| `DNS-SRV-01` | DNS | SERVFAIL | `bind9-recursive-resolver` | Falla de resolución recursiva o timeout hacia servidor raíz |
| `DNS-TRUNC-01` | DNS | DNS_TRUNCATED_EDNS | `bind9-resolver-firewall` | Respuesta truncada TC=1 por buffer EDNS0 bloqueado |
| `HTTP-POOL-01` | API_GATEWAY | CONNECTION_POOL_EXHAUSTED | `upstream-backend-api` | Agotamiento de pool de conexiones concurrentes en backend |
| `HTTP-403-01` | API_GATEWAY | HTTP_403_FORBIDDEN | `nginx-api-gateway` | Acceso denegado por reglas de autorización o IP |
| `HTTP-429-01` | API_GATEWAY | HTTP_429_RATE_LIMITED | `nginx-rate-limiter` | Límite de tasa de peticiones excedido (Rate Limiting) |
| `HTTP-500-01` | HTTP_WEB | HTTP_500_INTERNAL | `backend-application-code` | Excepción no controlada en el código backend |
| `HTTP-502-01` | API_GATEWAY | HTTP_502_BAD_GATEWAY | `upstream-backend-api` | Conexión rechazada o caída del servicio upstream |
| `HTTP-503-01` | HTTP_WEB | HTTP_503_SERVICE_UNAVAILABLE | `backend-application-pool` | Servicio sobrecargado o en mantenimiento temporal |
| `HTTP-504-01` | API_GATEWAY | HTTP_504_GATEWAY_TIMEOUT | `upstream-backend-database` | Timeout de espera de respuesta desde microservicio |
| `NET-LAT-01` | HTTP_WEB | NETWORK_LATENCY_TC | `network-infrastructure` | Degradación por latencia anómala inyectada con tc-netem |
| `HTTP-ORIGIN-01`| API_GATEWAY | ORIGIN_DOWN | `upstream-cluster` | Servidor de origen fuera de línea o sin conectividad |
| `TLS-CHN-01` | TLS | TLS_CHAIN_INVALID | `nginx-tls-termination` | Cadena de confianza rota por omisión de certificado CA |
| `TLS-CIPH-01` | TLS | TLS_CIPHER_MISMATCH | `nginx-tls-crypto-engine` | Negociación fallida por conjuntos de cifrado incompatibles |
| `TLS-EXP-01` | TLS | TLS_EXPIRED_CERT | `nginx-tls-termination` | Certificado digital X.509 expirado en endpoint seguro |
| `TLS-SNI-01` | TLS | TLS_SNI_MISMATCH | `nginx-tls-termination` | Discrepancia entre SNI y certificado presentado |

---

## 4. Orquestación Agéntica LangGraph y Herramientas Read-Only
El agente opera un `StateGraph` de 6 nodos:
1. `ingest_telemetry`: Recibe logs preprocesados por Drain3.
2. `retrieve_rag_knowledge`: Indexa normativas RFC vía BM25.
3. `formulate_hypothesis`: El modelo plantea una causa probable y elije una herramienta.
4. `execute_read_only_tool`: Invoca `dig`, `curl` u `openssl s_client` bajo sandbox seguro.
5. `evaluate_evidence`: Verifica la concordancia del síntoma técnico.
6. `synthesize_diagnosis`: Estructura el veredicto y plan de mitigación SOP.

---

## 5. Referencia de API REST y CLI
Comandos principales de la CLI Typer:
```bash
# Listar escenarios y modelos
benchapp list-scenarios
benchapp list-models

# Ejecutar escenario individual
benchapp run-scenario DNS-NXD-01 --model phi-4-mini-instruct --seed 42

# Ejecutar benchmark y análisis correlacional
benchapp run-benchmark --quick
benchapp analyze-correlation
benchapp export-excel
benchapp export-pdf --type all

# Servidor web interactivo
benchapp serve-dashboard --port 8000
```
""", encoding="utf-8")

    # Manual de Usuario Markdown
    usuario_md = DOCS_DIR / "MANUAL_USUARIO_SISTEMA.md"
    usuario_md.write_text("""# NetDiagBench-L7 • Manual de Usuario y Guía Operativa
**Proyecto de Grado — Universidad de Pamplona**  
**Facultad de Ingenierías y Arquitectura — Departamento E.E.S.T.**  
**Autor:** Juan David León Arrieta (`juan.leon22@unipamplona.edu.co`)  
**Director:** Mg. Richard Eliseo Mendoza Gáfaro (`richard.mendoza@unipamplona.edu.co`)  
**Versión:** 1.0.0 | **Fecha:** Noviembre 2026 | **Entorno:** Local-First Web Dashboard

---

## 1. Guía de Inicio Rápido
1. Ejecute el script de inicio rápido:
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\\launch_demo.ps1
   ```
2. Abra su navegador web en `http://localhost:8000`.

---

## 2. Vistas Principales de la Aplicación
1. **Visor de Diagnóstico (Tecla 1):** Permite configurar escenario, modelo y semilla para ejecutar el diagnóstico interactivo en streaming con observabilidad en tiempo real.
2. **Informe Comparativo OE4 (Tecla 2):** Matriz multidimensional con perfiles de modelo (NOC vs Recursos Acotados vs Triaje Rápido), scores compuestos y descomposiciones de latencia y VRAM.
3. **Análisis Correlacional SciPy (Tecla 3):** Pruebas de hipótesis no paramétricas Kruskal-Wallis, correlación de Spearman, intervalos de confianza al 95% y tamaños de efecto d de Cohen.
4. **Informe Consolidado HTML (Tecla 4):** Vista documental interactiva para consulta unificada de todos los entregables.
5. **Suite de Observabilidad (Tecla 5):** Ejecución desatendida y secuencial de los 18 escenarios catalogados.

---

## 3. Atajos de Teclado y Paleta de Comandos
- `Ctrl + K`: Abrir paleta de comandos rápida.
- `Ctrl + Enter`: Ejecutar diagnóstico del escenario activo.
- `1` a `5`: Conmutar instantáneamente entre vistas principales.
- Botón de Luna / Sol: Alternar entre Tema Oscuro y Tema Claro.

---

## 4. Exportación de Resultados
La barra flotante superior derecha permite exportar en:
- **Excel (.xlsx):** Libro multioja con fórmulas, formato condicional y gráficos.
- **PDF Institucional:** Reporte formal para sustentación y archivo académico.
- **JSON / CSV:** Archivos planos de datos para análisis externo en Python o R.
""", encoding="utf-8")

    print(f"Markdown manuals generated in {DOCS_DIR}")


# ============================================================================
# COMPILACIÓN PRINCIPAL
# ============================================================================

def main():
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    styles = create_styles()

    # 1. Compilar Manual Técnico PDF
    tecnico_pdf_path = DOCS_DIR / "MANUAL_TECNICO_SISTEMA.pdf"
    print(f"Generando {tecnico_pdf_path}...")
    doc_t = SimpleDocTemplate(
        str(tecnico_pdf_path),
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=48,
        bottomMargin=48,
    )
    story_t = build_manual_tecnico_story(styles)
    doc_t.build(story_t, canvasmaker=ManualTecnicoCanvas)
    print(f"Manual Técnico generado con éxito ({tecnico_pdf_path.stat().st_size} bytes).")

    # 2. Compilar Manual de Usuario PDF
    usuario_pdf_path = DOCS_DIR / "MANUAL_USUARIO_SISTEMA.pdf"
    print(f"Generando {usuario_pdf_path}...")
    doc_u = SimpleDocTemplate(
        str(usuario_pdf_path),
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=48,
        bottomMargin=48,
    )
    story_u = build_manual_usuario_story(styles)
    doc_u.build(story_u, canvasmaker=ManualUsuarioCanvas)
    print(f"Manual de Usuario generado con éxito ({usuario_pdf_path.stat().st_size} bytes).")

    # 3. Exportar Markdown
    export_markdown_files()


if __name__ == "__main__":
    main()
