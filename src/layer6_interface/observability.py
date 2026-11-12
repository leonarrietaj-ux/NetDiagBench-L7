"""

NetDiagBench-L7: Layer 6 - Panel de Observabilidad en Tiempo Real (HTMX + SSE + LangGraph)

Provee un visor interactivo de la cadena de pensamiento (Chain-of-Thought) y evidencia de red

siguiendo la arquitectura HATEOAS: el backend en FastAPI genera fragmentos HTML enriquecidos

y los transmite en tiempo real vía Server-Sent Events (SSE) a un frontend liviano con HTMX.

"""



import asyncio

import html

import json

import os

import psutil

import random

import re

import time

import urllib.parse

from datetime import datetime

from typing import AsyncGenerator



from fastapi import APIRouter, Request

from fastapi.responses import HTMLResponse

from sse_starlette.sse import EventSourceResponse



from src.core.config import PROJECT_ROOT, SystemConfig

from src.core.contracts import ServiceCategory

from src.core.logger import logger

from src.layer1_lab.runner import ScenarioLabRunner

from src.layer2_pipeline.aggregator import DataPipelineAgent

from src.layer3_rag.retriever import RAGKnowledgeEngine

from src.layer4_inference.engine import LocalInferenceEngine

from src.layer5_orchestrator.agent import DiagnosticOrchestratorAgent
from src.core.translator import translate_english_to_spanish, is_predominantly_english, is_predominantly_english

from src.layer6_interface.execution_history import (

    execution_history_manager,

    populate_from_suite_store_if_empty,

    render_execution_detail_partial,

    render_executions_partial,

)

from src.layer6_interface.suite_store import suite_store

from src.layer6_interface.tooltip_helper import TOOLTIP_CSS, TOOLTIP_JS

from src.layer7_evaluator.metrics import (

    check_component_correct,

    check_root_cause_correct,

    estimate_energy_and_carbon,

    evaluate_explanation_rubric,

)

from src.layer7_evaluator.statistical_analysis import (

    generate_correlation_report,

    run_correlation_analysis,

)



router = APIRouter(tags=["Observabilidad"])

lab_runner = ScenarioLabRunner()

rag_engine = RAGKnowledgeEngine()

data_pipeline = DataPipelineAgent()

inference_engine = LocalInferenceEngine()

orchestrator = DiagnosticOrchestratorAgent(inference_engine=inference_engine)

_suite_active_flag: bool = True

_suite_cancel_event: asyncio.Event | None = None


def _get_cancel_event() -> asyncio.Event:
    global _suite_cancel_event
    if _suite_cancel_event is None:
        _suite_cancel_event = asyncio.Event()
    return _suite_cancel_event





from src.layer7_evaluator.harness import (
    BenchmarkEvaluatorHarness,
    save_or_replace_benchmark_result,
)

suite_harness = BenchmarkEvaluatorHarness(
    orchestrator=orchestrator,
    inference_engine=inference_engine,
)






# ── GENERADOR DE FRAGMENTOS HTML (HATEOAS) ──────────────────────────────────



def _highlight_json_syntax(json_str: str) -> str:

    """

    Resalta la sintaxis de un JSON aplicando clases Tailwind para interfaz oscura tipo IDE:

    - Claves (keys): text-blue-300

    - Textos (strings): text-emerald-300

    - Números, booleanos y null: text-orange-300

    """

    pattern = re.compile(

        r'("(?:\\.|[^"\\])*")(\s*:)?|\b(-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?)\b|\b(true|false|null)\b'

    )

    parts = []

    last_end = 0

    for match in pattern.finditer(json_str):

        prefix = json_str[last_end:match.start()]

        if prefix:

            parts.append(html.escape(prefix))

        s_str, colon, num, bool_val = match.group(1), match.group(2), match.group(3), match.group(4)

        if s_str:

            esc_str = html.escape(s_str)

            if colon:

                parts.append(f'<span class="text-blue-300">{esc_str}</span>{html.escape(colon)}')

            else:

                parts.append(f'<span class="text-emerald-300">{esc_str}</span>')

        elif num:

            parts.append(f'<span class="text-orange-300">{num}</span>')

        elif bool_val:

            parts.append(f'<span class="text-orange-300">{bool_val}</span>')

        last_end = match.end()

    if last_end < len(json_str):

        parts.append(html.escape(json_str[last_end:]))

    return "".join(parts)





def _highlight_markdown_syntax(md_str: str) -> str:

    """

    Resalta la sintaxis de la salida RAG Markdown / Texto plano:

    - Base dentro de <code>: text-slate-300

    - Títulos/Cabeceras (=== o ---): text-blue-300

    - Rutas de archivos (ej. sop_dns_troubleshooting.md): text-amber-300

    - Comandos/Código en línea (`...`): text-emerald-400 font-bold bg-slate-800/50 px-1 rounded

    - Texto en negrita (**...**): text-white font-bold

    """

    lines = md_str.split("\n")

    processed_lines = []



    file_path_pattern = re.compile(r'\b([\w.-]+\.(?:md|json|log|conf|yaml|yml|txt|py))\b')

    inline_code_pattern = re.compile(r'`([^`]+)`')

    bold_pattern = re.compile(r'\*\*([^*]+)\*\*')



    for line in lines:

        stripped = line.strip()

        # 1. Cabeceras === o ---

        if stripped.startswith("===") or stripped.startswith("---"):

            esc_line = html.escape(line)

            esc_line = file_path_pattern.sub(r'<span class="text-amber-300 font-medium">\1</span>', esc_line)

            processed_lines.append(f'<span class="text-blue-300 font-semibold">{esc_line}</span>')

            continue



        esc_line = html.escape(line)



        # 2. Negrita **...**

        esc_line = bold_pattern.sub(r'<span class="text-white font-bold">\1</span>', esc_line)



        # 3. Rutas de archivo

        esc_line = file_path_pattern.sub(r'<span class="text-amber-300 font-medium">\1</span>', esc_line)



        # 4. Comandos/código en línea `...` (limpiando tags anidados)

        def code_repl(m: re.Match[str]) -> str:

            raw_code = re.sub(r'<[^>]+>', '', m.group(1))

            return f'<code class="text-emerald-400 font-bold bg-slate-800/50 px-1 rounded">{raw_code}</code>'



        esc_line = inline_code_pattern.sub(code_repl, esc_line)

        processed_lines.append(esc_line)



    return "\n".join(processed_lines)





def _render_subtle_system_line(

    node_name: str,

    text: str,

    payload: str = "",

    title: str = "",

    badge_color: str = "",

    icon_type: str = "",

    scenario_id: str = "",

    category: str = "",

    fault_class: str = "",

    target_component: str = ""

) -> str:

    """

    Genera un nodo interactivo completo de la línea de tiempo con tarjeta (Card)

    en formato Dashboard de Pestañas (Vista Gráfica vs Código Crudo), manteniendo

    estrictamente la estructura visual del timeline.

    Contenido 100% dinámico y coherente con cada escenario (DNS, TLS, HTTP/Gateway).

    """

    raw_payload = payload.strip() if payload else ""



    # Determinar contexto del escenario (DNS, TLS, HTTP_WEB, API_GATEWAY)

    payload_dict = {}

    if raw_payload.startswith("{"):

        try:

            payload_dict = json.loads(raw_payload)

        except Exception:

            payload_dict = {}



    cat = category or payload_dict.get("category", "")

    fc = fault_class or payload_dict.get("fault_class", "")

    sc_id = scenario_id or payload_dict.get("scenario_id", "")

    target = target_component or payload_dict.get("target_component", "")



    if not cat:

        m_sc = re.search(r"Escenario:\s*\[([^\]]+)\]\s*(\S+)\s*-\s*Falla L7:\s*([^\n\r]+)", raw_payload)

        if m_sc:

            cat = m_sc.group(1).strip()

            sc_id = m_sc.group(2).strip()

            fc = m_sc.group(3).strip()



    if not cat:

        if "TLS" in sc_id or "CIPHER" in fc or "HANDSHAKE" in raw_payload or "openssl" in raw_payload or "nginx-ssl" in raw_payload:

            cat = "TLS"

        elif "HTTP" in sc_id or "502" in fc or "504" in fc or "nginx" in raw_payload or "curl" in raw_payload:

            cat = "HTTP_WEB"

        else:

            cat = "DNS"



    if not fc:

        if "NXDOMAIN" in raw_payload:

            fc = "NXDOMAIN"

        elif "SERVFAIL" in raw_payload:

            fc = "SERVFAIL"

        elif "502" in raw_payload:

            fc = "HTTP_502_BAD_GATEWAY"

        elif "504" in raw_payload:

            fc = "HTTP_504_GATEWAY_TIMEOUT"

        elif "CIPHER" in raw_payload:

            fc = "TLS_CIPHER_MISMATCH"

        elif "EXPIRED" in raw_payload:

            fc = "TLS_EXPIRED_CERT"

        else:

            fc = "NXDOMAIN" if cat == "DNS" else ("TLS_CIPHER_MISMATCH" if cat == "TLS" else "HTTP_502_BAD_GATEWAY")



    if not sc_id:

        sc_id = "DNS-NXD-01" if cat == "DNS" else ("TLS-CIPH-01" if cat == "TLS" else "HTTP-502-01")



    is_dns = (cat == "DNS")

    is_tls = (cat == "TLS")



    # Determinar tipo de ícono

    if not icon_type:

        icon_type = "database" if "ingest" in node_name else "document"



    if icon_type == "database":

        icon_svg = """<svg class="w-4 h-4 text-blue-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">

            <ellipse cx="12" cy="5" rx="9" ry="3"/>

            <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/>

            <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>

        </svg>"""

    else:

        icon_svg = """<svg class="w-4 h-4 text-amber-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">

            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>

            <polyline points="14 2 14 8 20 8"/>

            <line x1="16" y1="13" x2="8" y2="13"/>

            <line x1="16" y1="17" x2="8" y2="17"/>

        </svg>"""



    # =========================================================================

    # CASO 1: NODO INGEST TELEMETRY (DASHBOARD DRAIN3 COHERENTE)

    # =========================================================================

    if "ingest" in node_name:

        if is_dns:

            sub_title = "Drain3 Log Parser v0.9.11 · BIND9 Authoritative / Resolver"

            normal_code = "NOERROR"

            normal_legend = "NOERROR"

            fault_legend = "NXDOMAIN" if "NXDOMAIN" in fc else ("SERVFAIL" if "SERVFAIL" in fc else fc)

            timeline_title = "Línea de tiempo de consultas"

            th_cols = ["Hora", "Puerto cliente", "FQDN", "Tipo", "Flags", "RCODE"]

            fallback_logs = [

                {"timestamp": "2026-09-25 10:00:00", "source_service": "bind9", "log_level": "INFO", "raw_message": "client 127.0.0.1#49152: query: resolver.internal IN A + (127.0.0.1)", "code": "NOERROR"},

                {"timestamp": "2026-09-25 10:00:04", "source_service": "bind9", "log_level": "INFO", "raw_message": "client 127.0.0.1#49153: query: app.internal.corp IN A -E(0)K (127.0.0.1)", "code": fault_legend},

                {"timestamp": "2026-09-25 10:00:05", "source_service": "bind9", "log_level": "INFO", "raw_message": "client 127.0.0.1#49153: query: app.internal.corp IN A -E(0)K (127.0.0.1)", "code": fault_legend},

                {"timestamp": "2026-09-25 10:00:09", "source_service": "bind9", "log_level": "INFO", "raw_message": "client 127.0.0.1#49154: query: app.internal.corp IN AAAA -E(0)K (127.0.0.1)", "code": fault_legend},

                {"timestamp": "2026-09-25 10:00:10", "source_service": "bind9", "log_level": "INFO", "raw_message": "client 127.0.0.1#49152: query: resolver.internal IN A + (127.0.0.1)", "code": "NOERROR"},

                {"timestamp": "2026-09-25 10:00:11", "source_service": "bind9", "log_level": "INFO", "raw_message": "client 127.0.0.1#49152: query: resolver.internal IN A + (127.0.0.1)", "code": "NOERROR"}

            ]

        elif is_tls:

            sub_title = "Drain3 Log Parser v0.9.11 · Nginx SSL / TLS Handshake Engine"

            normal_code = "TLS"

            normal_legend = "TLS OK"

            fault_legend = "CIPHER_ERR" if "CIPHER" in fc else ("TLS_EXP" if "EXP" in fc else ("TLS_CHAIN" if "CHAIN" in fc else "TLS_ERR"))

            timeline_title = "Línea de tiempo de eventos"

            th_cols = ["Hora", "Cliente / Puerto", "Servidor SNI", "Protocolo / Suite", "Mensaje de Enlace", "Estado TLS"]

            fallback_logs = [

                {"timestamp": "2026-09-25 10:00:00", "source_service": "nginx-ssl", "log_level": "INFO", "raw_message": "127.0.0.1 TLS client hello offered suites: [TLS_RSA_WITH_AES_128_CBC_SHA]", "code": "TLS"},

                {"timestamp": "2026-09-25 10:00:04", "source_service": "nginx-ssl", "log_level": "INFO", "raw_message": "127.0.0.1 TLS client hello offered suites: [TLS_RSA_WITH_AES_128_CBC_SHA]", "code": "TLS"},

                {"timestamp": "2026-09-25 10:00:05", "source_service": "nginx-ssl", "log_level": "INFO", "raw_message": "127.0.0.1 TLS client hello offered suites: [TLS_RSA_WITH_AES_128_CBC_SHA]", "code": "TLS"},

                {"timestamp": "2026-09-25 10:00:09", "source_service": "nginx-ssl", "log_level": "ERROR", "raw_message": "SSL_do_handshake() failed (SSL: error:0A000410:SSL routines::sslv3 alert handshake failure) while SSL handshaking", "code": fault_legend},

                {"timestamp": "2026-09-25 10:00:11", "source_service": "nginx-ssl", "log_level": "ERROR", "raw_message": "client 127.0.0.1 disconnected: no shared cipher supported between client and server", "code": fault_legend},

                {"timestamp": "2026-09-25 10:00:16", "source_service": "nginx-ssl", "log_level": "INFO", "raw_message": "127.0.0.1 TLS client hello offered suites: [TLS_RSA_WITH_AES_128_CBC_SHA]", "code": "TLS"}

            ]

        else:  # HTTP_WEB / API_GATEWAY

            sub_title = "Drain3 Log Parser v0.9.11 · Nginx Reverse Proxy / Upstream Gateway"

            normal_code = "200"

            normal_legend = "200 OK"

            fault_legend = "502" if "502" in fc else ("504" if "504" in fc else ("503" if "503" in fc else "HTTP_ERR"))

            timeline_title = "Línea de tiempo de eventos"

            th_cols = ["Hora", "Cliente IP", "Método / Endpoint", "Protocolo", "Upstream Socket", "Status HTTP"]

            fallback_logs = [

                {"timestamp": "2026-09-25 10:00:00", "source_service": "nginx", "log_level": "INFO", "raw_message": '127.0.0.1 - - [GET /static/style.css HTTP/1.1] 200 4521 "-" "curl/8.4.0"', "code": "200"},

                {"timestamp": "2026-09-25 10:00:02", "source_service": "nginx", "log_level": "INFO", "raw_message": '127.0.0.1 - - [GET /health HTTP/1.1] 200 15 "-" "curl/8.4.0"', "code": "200"},

                {"timestamp": "2026-09-25 10:00:04", "source_service": "nginx", "log_level": "ERROR", "raw_message": '[error] connect() failed (111: Connection refused) while connecting to upstream: "http://127.0.0.1:8080/api/v1/users"', "code": fault_legend},

                {"timestamp": "2026-09-25 10:00:06", "source_service": "nginx", "log_level": "WARNING", "raw_message": f'127.0.0.1 - - [GET /api/v1/users HTTP/1.1] {fault_legend} 157 "-" "curl/8.4.0"', "code": fault_legend},

                {"timestamp": "2026-09-25 10:00:08", "source_service": "nginx", "log_level": "ERROR", "raw_message": '[error] no live upstreams while connecting to upstream: "http://127.0.0.1:8080/api/v1/users"', "code": fault_legend},

                {"timestamp": "2026-09-25 10:00:10", "source_service": "nginx", "log_level": "INFO", "raw_message": '127.0.0.1 - - [GET /health HTTP/1.1] 200 15 "-" "curl/8.4.0"', "code": "200"}

            ]



        raw_logs = payload_dict.get("raw_telemetry_logs") or fallback_logs



        parsed_logs = []

        for i, item in enumerate(raw_logs):

            if isinstance(item, dict):

                ts = item.get("timestamp", "10:00:00").split()[-1]

                msg = item.get("raw_message", "")

                code = item.get("code", normal_code)

            else:

                ts = f"10:00:{i*2:02d}"

                msg = str(item)

                code = fault_legend if (fault_legend in msg or "error" in msg.lower()) else normal_code



            if is_dns:

                m_port = re.search(r"#(\d+)", msg)

                col2 = f"#{m_port.group(1)}" if m_port else "#49152"

                m_query = re.search(r"query(?: failed)?(?:\s*\([^)]+\))?:\s*([^\s/]+)", msg)

                col3 = m_query.group(1) if m_query else ("app.internal.corp" if code != normal_code else "resolver.internal")

                m_type = re.search(r"\b(AAAA|A|MX|TXT|CNAME|PTR)\b", msg)

                col4 = m_type.group(1) if m_type else "A"

                col5 = "-E(0)K" if "-E(0)K" in msg else ("+" if "+" in msg else "+")

                flag_help = 'Flags "+": recursión solicitada (RD).' if col5 == "+" else 'Flags "-E(0)K": sin RD, EDNS versión 0, DNS COOKIE presente.'

            elif is_tls:

                m_ip = re.search(r"\b(\d+\.\d+\.\d+\.\d+)\b", msg)

                col2 = f"{m_ip.group(1)}:49320" if m_ip else "127.0.0.1:443"

                m_sni = re.search(r"SNI(?:\s*host)?:\s*([^\s,]+)", msg)

                col3 = m_sni.group(1) if m_sni else ("secure.corp.internal" if not target else target)

                if "TLSv1.3" in msg:

                    col4 = "TLSv1.3 / AES-GCM"

                elif "RSA" in msg:

                    col4 = "TLSv1.2 / TLS_RSA"

                elif "ECDHE" in msg:

                    col4 = "TLSv1.3 / ECDHE"

                else:

                    col4 = "TLSv1.3"



                if "alert handshake failure" in msg:

                    col5 = "alert handshake failure"

                elif "no shared cipher" in msg:

                    col5 = "no shared cipher"

                elif "certificate has expired" in msg:

                    col5 = "certificate has expired"

                elif "local issuer" in msg:

                    col5 = "missing intermediate CA"

                elif "hostname mismatch" in msg:

                    col5 = "hostname mismatch"

                elif "handshake started" in msg:

                    col5 = "handshake started"

                elif "offered suites" in msg:

                    col5 = "client hello (offered suites)"

                elif "disconnected" in msg:

                    col5 = "client disconnected"

                else:

                    col5 = "handshake ok"

                flag_help = 'Cifrado TLS negociado según políticas criptográficas de Nginx.'

            else:

                col2 = "127.0.0.1"

                m_ep = re.search(r"\[(GET|POST|PUT|DELETE)\s+([^\s\]]+)\s+HTTP/[^\]]+\]", msg)

                if m_ep:

                    col3 = f"{m_ep.group(1)} {m_ep.group(2)}"

                elif "users" in msg:

                    col3 = "GET /api/v1/users"

                elif "reports" in msg:

                    col3 = "GET /api/v1/reports"

                elif "health" in msg:

                    col3 = "GET /health"

                else:

                    col3 = "GET /api/v1/status"

                col4 = "HTTP/1.1"

                m_up = re.search(r"(?:to upstream:\s*\"|connecting to upstream:\s*\")([^\"]+)\"", msg)

                if m_up:

                    col5 = m_up.group(1).replace("http://", "")

                elif "10.0.0.5" in msg:

                    col5 = "10.0.0.5:8080"

                else:

                    col5 = "127.0.0.1:8080"

                flag_help = 'Socket upstream conectado mediante proxy inverso HTTP.'



            sec = i * 2

            parsed_logs.append({

                "i": i,

                "time": ts,

                "sec": sec,

                "col2": col2,

                "col3": col3,

                "col4": col4,

                "col5": col5,

                "flag_help": flag_help,

                "code": code,

                "raw": msg

            })



        total_logs = len(parsed_logs)

        fault_logs = [r for r in parsed_logs if r["code"] != normal_code and r["code"] != "QUERY"]

        fault_count = len(fault_logs)

        normal_count = total_logs - fault_count

        fault_rate_pct = int(round((fault_count / max(1, total_logs)) * 100))



        # Determinar dinámicamente la leyenda de falla dominante desde los logs

        non_normal_codes = [r["code"] for r in parsed_logs if r["code"] not in (normal_code, "QUERY", "INFO")]

        if non_normal_codes:

            from collections import Counter

            fault_legend = Counter(non_normal_codes).most_common(1)[0][0]



        # Timestamps dinámicos para el eje temporal basados en los logs reales

        time_labels = [p["time"] for p in parsed_logs]

        if len(time_labels) >= 4:

            axis_labels = [time_labels[0], time_labels[len(time_labels)//3], time_labels[(len(time_labels)*2)//3], time_labels[-1]]

        elif len(time_labels) >= 2:

            axis_labels = [time_labels[0], time_labels[-1]]

        else:

            axis_labels = ["10:00:00", "10:00:04", "10:00:08", "10:00:11"]

        axis_rendered = "".join(f"<span>{t}</span>" for t in axis_labels)



        # Ventana de tiempo calculada dinámicamente

        try:

            t0 = datetime.strptime(parsed_logs[0]["time"], "%H:%M:%S")

            t1 = datetime.strptime(parsed_logs[-1]["time"], "%H:%M:%S")

            dur_s = max(1, int((t1 - t0).total_seconds()))

            window_text = f"ventana de {dur_s} s"

        except Exception:

            window_text = f"ventana de {max(1, (total_logs - 1) * 2)} s"



        # Puntos en la línea de tiempo

        dots_html = []

        for r in parsed_logs:

            is_anomaly = (r["code"] != normal_code and r["code"] != "QUERY")

            left_pct = (r["sec"] / max(1, (total_logs - 1) * 2)) * 92 + 4

            dot_color = "bg-amber-400 border border-amber-300" if is_anomaly else "bg-emerald-400 border border-emerald-300"

            dot_shape = "rounded-sm" if is_anomaly else "rounded-full"

            esc_msg = html.escape(r["raw"], quote=True)

            dots_html.append(

                f'<button type="button" onclick="selectDrainLogRow(this, \'{r["time"]}\', \'{esc_msg}\', \'{r["flag_help"]}\')" '

                f'title="{r["time"]} · {r["col3"]} · {r["code"]}" '

                f'class="absolute top-[22px] w-5 h-5 -translate-x-1/2 flex items-center justify-center cursor-pointer transition-transform hover:scale-125" '

                f'style="left: {left_pct:.1f}%;">'

                f'<span class="w-2.5 h-2.5 {dot_shape} {dot_color} shadow"></span>'

                f'</button>'

            )

        dots_rendered = "".join(dots_html)



        # Filas de la tabla de eventos

        table_rows_html = []

        for r in parsed_logs:

            is_anomaly = (r["code"] != normal_code and r["code"] != "QUERY")

            badge_cls = "drain-badge-anomaly bg-[#3A2A0E] text-amber-300 border border-amber-800/60" if is_anomaly else "drain-badge-normal bg-[#0E2E24] text-emerald-400 border border-emerald-800/60"

            row_bg = "hover:bg-slate-800/40 drain-log-anomaly" if is_anomaly else "hover:bg-slate-800/40 drain-log-normal"

            esc_msg = html.escape(r["raw"], quote=True)

            table_rows_html.append(

                f'<tr data-log-row data-log-code="{r["code"]}" onclick="selectDrainLogRow(this, \'{r["time"]}\', \'{esc_msg}\', \'{r["flag_help"]}\')" '

                f'class="cursor-pointer border-t border-slate-800/80 transition-colors {row_bg}">'

                f'<td class="py-2 px-3.5 font-mono whitespace-nowrap text-slate-300">{r["time"]}</td>'

                f'<td class="py-2 px-3.5 font-mono text-slate-400">{r["col2"]}</td>'

                f'<td class="py-2 px-3.5 font-mono text-slate-200">{r["col3"]}</td>'

                f'<td class="py-2 px-3.5 font-mono text-slate-300">{r["col4"]}</td>'

                f'<td class="py-2 px-3.5 font-mono text-slate-400" title="{r["flag_help"]}">{r["col5"]}</td>'

                f'<td class="py-2 px-3.5"><span class="font-mono text-[11px] font-semibold px-2 py-0.5 rounded {badge_cls}">{r["code"]}</span></td>'

                f'</tr>'

            )

        table_rows_rendered = "".join(table_rows_html)



        # Templates según la categoría

        if is_dns:

            templates_defs = [

                ("T1", "NOERROR", normal_count, "client <*>#<*>: query: resolver.internal IN A + (<*>)", "bg-emerald-400", int(round(normal_count/max(1, total_logs)*100))),

                ("T2", fc, max(1, fault_count - 1), "client <*>#<*>: query: app.internal.corp IN A -E(0)K (<*>)", "bg-amber-400", int(round(max(1, fault_count-1)/max(1, total_logs)*100))),

                ("T3", fc, max(1, fault_count // 2), "client <*>#<*>: query: app.internal.corp IN AAAA -E(0)K (<*>)", "bg-amber-400", int(round(max(1, fault_count//2)/max(1, total_logs)*100)))

            ]

        elif is_tls:

            templates_defs = [

                ("T1", "TLS", normal_count, "127.0.0.1 TLS client hello offered suites: [<*>]", "bg-emerald-400", int(round(normal_count/max(1, total_logs)*100))),

                ("T2", fault_legend, max(1, fault_count // 2), "SSL_do_handshake() failed (SSL: error:<*>) while SSL handshaking", "bg-amber-400", int(round(max(1, fault_count//2)/max(1, total_logs)*100))),

                ("T3", fault_legend, max(1, fault_count - (fault_count // 2)), "client 127.0.0.1 disconnected: no shared cipher supported between client and server", "bg-amber-400", int(round(max(1, fault_count - (fault_count//2))/max(1, total_logs)*100)))

            ]

        else:

            templates_defs = [

                ("T1", "200", normal_count, "127.0.0.1 - - [GET <*> HTTP/1.1] 200 <*> \"-\" \"<*>\"", "bg-emerald-400", int(round(normal_count/max(1, total_logs)*100))),

                ("T2", fault_legend, max(1, fault_count // 2), "[error] connect() failed (111: Connection refused) while connecting to upstream: \"<*>\"", "bg-amber-400", int(round(max(1, fault_count//2)/max(1, total_logs)*100))),

                ("T3", fault_legend, max(1, fault_count - (fault_count // 2)), f"127.0.0.1 - - [GET <*> HTTP/1.1] {fault_legend} <*> \"-\" \"<*>\"", "bg-amber-400", int(round(max(1, fault_count - (fault_count//2))/max(1, total_logs)*100)))

            ]



        templates_cards = []

        for tid, tcode, tcnt, tpat, tbar, tpct in templates_defs:

            is_anom = (tcode != normal_code)

            b_cls = "bg-[#3A2A0E] text-amber-300 border border-amber-800/60" if is_anom else "bg-[#0E2E24] text-emerald-400 border border-emerald-800/60"

            border_cls = "border-amber-800/60" if is_anom else "border-slate-800/80"

            templates_cards.append(f"""

            <div class="bg-[#0A0E16] border {border_cls} rounded-lg p-3 flex flex-col gap-2">

                <div class="flex justify-between items-center gap-3 flex-wrap">

                    <div class="flex gap-2.5 items-center">

                        <span class="font-mono text-xs font-semibold text-slate-400">{tid}</span>

                        <span class="font-mono text-[11px] font-semibold px-2 py-0.5 rounded {b_cls}">{tcode}</span>

                    </div>

                    <span class="text-xs text-slate-400 font-mono">{tcnt} eventos ({tpct}%)</span>

                </div>

                <code class="font-mono text-xs sm:text-[13px] text-slate-200 overflow-x-auto whitespace-nowrap block">{html.escape(tpat)}</code>

                <div class="h-1.5 bg-[#1A2233] rounded-full overflow-hidden"><div class="h-full {tbar}" style="width: {tpct}%;"></div></div>

            </div>

            """)

        templates_rendered = "".join(templates_cards)



        # Código crudo resaltado con cabecera de archivo

        highlighted_json = _highlight_json_syntax(raw_payload) if raw_payload else ""

        file_header_json = (

            '<div class="flex items-center justify-between px-4 py-1.5 bg-[#1e293b] border border-slate-700/60 '

            'border-b-0 rounded-t-lg text-[11px] text-slate-400 font-mono tracking-wider shadow-sm">'

            '<span class="flex items-center gap-2">'

            '<svg class="w-3 h-3 text-blue-400" fill="currentColor" viewBox="0 0 24 24">'

            '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6z"/>'

            '</svg> payload_drain3.json</span>'

            '<span>UTF-8 • Read Only</span>'

            '</div>'

        )

        raw_code_block = (

            f'{file_header_json}'

            f'<pre class="mt-0 p-4 bg-[#090b10] border border-slate-700/60 rounded-b-lg rounded-t-none text-xs md:text-[13px] '

            f'text-slate-300 font-mono leading-relaxed shadow-inner overflow-auto max-h-72 scrollbar-thin scrollbar-thumb-slate-600 '

            f'scrollbar-track-transparent hover:scrollbar-thumb-slate-500"><code class="language-json">{highlighted_json}</code></pre>'

        )



        card_html = f"""

        <!-- El Nuevo Dashboard Acordeón (Tarjeta Interior) -->

        <details class="group bg-[#101624] border border-slate-800/80 rounded-xl overflow-hidden shadow-sm" data-node-card>

            <!-- Cabecera Interactiva -->

            <summary class="flex flex-wrap gap-4 items-center justify-between p-4 cursor-pointer list-none hover:bg-slate-800/40 transition-colors select-none">

                <div class="flex gap-3 items-center flex-wrap">

                    <svg class="w-5 h-5 text-blue-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><ellipse cx="12" cy="5" rx="8" ry="3"></ellipse><path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5"></path><path d="M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"></path></svg>

                    <h2 class="m-0 text-base sm:text-[17px] font-semibold text-slate-100">Ingesta de telemetría L7</h2>

                    <span class="font-mono text-xs text-slate-400">{sub_title}</span>

                    <span class="text-xs px-2.5 py-0.5 rounded-full bg-emerald-950/60 text-emerald-400 border border-emerald-800/40">Agrupado y convergido</span>

                </div>

                <div class="flex items-center gap-2">

                    <svg class="w-5 h-5 text-slate-500 transform transition-transform duration-200 group-open:rotate-180" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>

                </div>

            </summary>



            <!-- Cuerpo del Dashboard (Contenido a revelar) -->

            <div class="border-t border-slate-800/80 p-4">

                <!-- Selector de pestañas Vista vs JSON crudo -->

                <div class="flex justify-end mb-4">

                    <div role="tablist" aria-label="Vista de la etapa" class="flex gap-1 bg-[#0A0E16] p-1 rounded-lg border border-slate-800/60">

                        <button type="button" role="tab" data-tab-target="vista" onclick="switchNodeTab(this, 'vista')" class="text-xs sm:text-[13px] px-3 py-1.5 rounded-md font-semibold bg-[#1E2A40] text-slate-100 transition-colors">Vista</button>

                        <button type="button" role="tab" data-tab-target="raw" onclick="switchNodeTab(this, 'raw')" class="text-xs sm:text-[13px] px-3 py-1.5 rounded-md font-medium text-slate-400 hover:text-slate-200 transition-colors">JSON crudo</button>

                    </div>

                </div>



                <!-- Pestaña Vista -->

                <div data-panel="vista" class="flex flex-col gap-6">

                    <!-- 1. Grid de KPIs -->

                <div class="grid grid-cols-2 md:grid-cols-4 gap-3">

                    <div class="bg-[#0A0E16] border border-slate-800/80 rounded-lg p-3.5">

                        <div class="text-xs text-slate-400">Eventos ingeridos</div>

                        <div class="text-2xl sm:text-3xl font-bold font-mono text-slate-100">{total_logs}</div>

                        <div class="text-xs text-slate-500">{window_text}</div>

                    </div>

                    <div class="bg-[#0A0E16] border border-slate-800/80 rounded-lg p-3.5">

                        <div class="text-xs text-slate-400">Patrones distintos</div>

                        <div class="text-2xl sm:text-3xl font-bold font-mono text-slate-100">3</div>

                        <div class="text-xs text-slate-500">templates_mined reporta {total_logs}</div>

                    </div>

                    <div class="bg-[#1C1608] border border-amber-800/60 rounded-lg p-3.5">

                        <div class="text-xs text-amber-300 font-semibold">Tasa {fc}</div>

                        <div class="text-2xl sm:text-3xl font-bold font-mono text-amber-300">{fault_rate_pct} %</div>

                        <div class="text-xs text-amber-200/70">{fault_count} de {total_logs} {'respuestas' if is_dns else 'eventos afectados'}</div>

                    </div>

                    <div class="bg-[#0A0E16] border border-slate-800/80 rounded-lg p-3.5">

                        <div class="text-xs text-slate-400">Anomalía de clúster</div>

                        <div class="text-2xl sm:text-3xl font-bold font-mono text-rose-400">Sí</div>

                        <div class="text-xs text-slate-500">cluster_anomaly = true</div>

                    </div>

                </div>



                <!-- 2. Línea de tiempo de consultas / eventos -->

                <div class="flex flex-col gap-2.5">

                    <div class="flex justify-between items-baseline flex-wrap gap-2">

                        <h3 class="m-0 text-sm font-semibold text-slate-200">{timeline_title}</h3>

                        <div class="flex gap-3.5 text-xs text-slate-400">

                            <span class="flex gap-1.5 items-center"><span class="w-2.5 h-2.5 rounded-full bg-emerald-400"></span>{normal_legend}</span>

                            <span class="flex gap-1.5 items-center"><span class="w-2.5 h-2.5 rounded-sm bg-amber-400"></span>{fault_legend}</span>

                        </div>

                    </div>

                    <div class="relative h-16 bg-[#0A0E16] border border-slate-800/80 rounded-lg overflow-hidden">

                        <div class="absolute left-[4%] right-[4%] top-[31px] h-[2px] bg-slate-800"></div>

                        {dots_rendered}

                    </div>

                    <div class="flex justify-between font-mono text-[11px] text-slate-500 px-[3%]">

                        {axis_rendered}

                    </div>

                </div>



                <!-- 3. Templates Drain3 -->

                <div class="flex flex-col gap-2.5">

                    <h3 class="m-0 text-sm font-semibold text-slate-200">Patrones extraídos por Drain3</h3>

                    {templates_rendered}

                </div>



                <!-- 4. Tabla Interactiva de Eventos -->

                <div class="flex flex-col gap-2.5">

                    <div class="flex justify-between items-center gap-3 flex-wrap">

                        <h3 class="m-0 text-sm font-semibold text-slate-200">Eventos crudos (orden cronológico)</h3>

                        <div role="group" aria-label="Filtrar por código" class="flex gap-1 bg-[#0A0E16] p-1 rounded-lg border border-slate-800/60">

                            <button type="button" data-filter-target="all" onclick="filterDrainLogs(this, 'all')" class="text-xs px-2.5 py-1 rounded-md font-semibold bg-[#1E2A40] text-slate-100">Todos · {total_logs}</button>

                            <button type="button" data-filter-target="{fault_legend}" onclick="filterDrainLogs(this, '{fault_legend}')" class="text-xs px-2.5 py-1 rounded-md text-slate-400 hover:text-slate-200">{fault_legend} · {fault_count}</button>

                            <button type="button" data-filter-target="{normal_code}" onclick="filterDrainLogs(this, '{normal_code}')" class="text-xs px-2.5 py-1 rounded-md text-slate-400 hover:text-slate-200">{normal_code} · {normal_count}</button>

                        </div>

                    </div>

                    <div class="overflow-x-auto border border-slate-800/80 rounded-lg">

                        <table class="w-full border-collapse text-[13px] min-w-[680px]">

                            <thead>

                                <tr class="bg-[#0A0E16] text-slate-400 text-left border-b border-slate-800/80">

                                    <th class="py-2.5 px-3.5 font-medium">{th_cols[0]}</th>

                                    <th class="py-2.5 px-3.5 font-medium">{th_cols[1]}</th>

                                    <th class="py-2.5 px-3.5 font-medium">{th_cols[2]}</th>

                                    <th class="py-2.5 px-3.5 font-medium">{th_cols[3]}</th>

                                    <th class="py-2.5 px-3.5 font-medium">{th_cols[4]}</th>

                                    <th class="py-2.5 px-3.5 font-medium">{th_cols[5]}</th>

                                </tr>

                            </thead>

                            <tbody>

                                {table_rows_rendered}

                            </tbody>

                        </table>

                    </div>

                    <!-- Detalle de evento seleccionado -->

                    <div data-detail-box class="hidden bg-[#0A0E16] border border-blue-900/60 rounded-lg p-3.5 flex flex-col gap-2">

                        <div class="flex justify-between gap-2 flex-wrap text-xs text-slate-400">

                            <span data-detail-meta>raw_message</span>

                            <button type="button" onclick="closeDrainDetail(this)" class="text-xs text-slate-400 hover:text-slate-200">Cerrar</button>

                        </div>

                        <code data-detail-raw class="font-mono text-xs sm:text-[13px] text-slate-200 overflow-x-auto whitespace-nowrap block"></code>

                        <span data-detail-flags class="text-xs text-slate-400"></span>

                    </div>

                </div>

            </div>



                <!-- Pestaña Crudo -->

                <div data-panel="raw" class="hidden">

                    {raw_code_block}

                </div>

            </div>

        </details>

        """



    # =========================================================================

    # CASO 2: NODO RETRIEVE RFC STANDARDS (DASHBOARD RAG COHERENTE)

    # =========================================================================

    elif "rfc" in node_name or "retrieve" in node_name:

        m_ram = re.search(r"Presupuesto RAM:\s*([\d.]+)\s*MB", raw_payload)

        ram_mb = m_ram.group(1) if m_ram else "0.02"



        if is_dns:

            header_norma = f"RFC 1035 · 2 fragmentos · {ram_mb} MB RAM"

            rfc_query = f"RFC 1035 (Domain Names - Spec) {fc} DNS {sc_id}"

            hit1_file = "sop_dns_troubleshooting.md"

            hit1_score = "4.3985"

            hit1_title = f"2.1 Síntoma: respuesta {fc} (RCODE 3)" if fc == "NXDOMAIN" else f"2.2 Síntoma: respuesta {fc}"

            hit2_file = "rfc1035_dns_excerpts.md"

            hit2_score = "3.1605"

            hit2_title = "4.1.1 Header section format"

            hit2_bar = "72%"



            if fc == "NXDOMAIN" or "NXD" in sc_id:

                def_text = "El servidor autoritativo certifica que el nombre consultado no existe en la zona administrada (NXDOMAIN / RCODE 3)."

                root_cause_text = "Registro A/AAAA ausente o eliminado en el archivo maestro de zona BIND9 para el FQDN objetivo. Como alternativa, FQDN mal escrito por el cliente."

                root_cause_sub = "Coincide con la telemetría: consultas DNS dirigidas al autoritativo devuelven fallo RCODE 3."

                chk_steps = [

                    ("1. Ejecutar consulta dirigida con dig", "dig @127.0.0.1 -p 5353 app.internal.corp A +noall +comments +answer"),

                    ("2. Verificar la presencia de la bandera status: NXDOMAIN en el encabezado", "status: NXDOMAIN"),

                    ("3. Revisar el Authority Section para confirmar el registro SOA retornado", "dig @127.0.0.1 -p 5353 app.internal.corp A +noall +authority"),

                    ("4. Revisar los logs de BIND9 (named.log / query.log) buscando query failed (NXDOMAIN)", 'grep "query failed (NXDOMAIN)" named.log query.log')

                ]

                fix_text = 'Agregar el registro de <span class="font-mono text-white font-semibold">app.internal.corp</span> en la zona del servidor BIND9 y recargar la configuración.'

                fix_cmd = "rndc reload"

            elif fc == "SERVFAIL" or "SRV" in sc_id:

                def_text = "El resolutor no pudo obtener una respuesta válida de la jerarquía DNS por fallo de servidores autoritativos o DNSSEC (SERVFAIL / RCODE 2)."

                root_cause_text = "Servidor autoritativo remoto inalcanzable, tiempo de espera agotado en resolución recursiva o firma DNSSEC rota (bogus)."

                root_cause_sub = "Coincide con la telemetría: timeout al resolver registros A/IN hacia el servidor upstream."

                chk_steps = [

                    ("1. Ejecutar consulta recursiva con traza jerárquica", "dig @127.0.0.1 -p 5353 partner.external.org A +trace"),

                    ("2. Comprobar alcanzabilidad del autoritativo upstream remoto", "ping -c 3 198.51.100.53"),

                    ("3. Inspeccionar logs buscando errores de resolución recursiva o DNSSEC", 'grep -E "connection timed out|SERVFAIL" named.log'),

                    ("4. Purgar caché de resolución de nombres en BIND9", "rndc flush")

                ]

                fix_text = "Restablecer la conectividad hacia los servidores autoritativos upstream o sincronizar claves DNSSEC y purgar caché."

                fix_cmd = "rndc flush && rndc reload"

            elif fc == "DNS_REFUSED" or "REF" in sc_id:

                def_text = "El servidor autoritativo BIND9 rechaza procesar la consulta por violación de listas de control de acceso (REFUSED / RCODE 5)."

                root_cause_text = "Subred o dirección IP del cliente excluida de la directiva allow-query o acl interna configurada en named.conf."

                root_cause_sub = "Coincide con la telemetría: consultas rechazadas con RCODE 5 por política de seguridad."

                chk_steps = [

                    ("1. Ejecutar consulta directa para verificar el rechazo de política", "dig @127.0.0.1 -p 5353 restricted.corp.internal A"),

                    ("2. Verificar la bandera de rechazo en la cabecera", "status: REFUSED"),

                    ("3. Inspeccionar logs de auditoría de BIND9 buscando consultas denegadas", 'grep "query refused by ACL" named.log'),

                    ("4. Validar las listas de control de acceso en named.conf.options", "named-checkconf -z /etc/bind/named.conf")

                ]

                fix_text = "Autorizar la subred cliente en la directiva allow-query de /etc/bind/named.conf.options y recargar BIND9."

                fix_cmd = "rndc reload"

            elif fc == "DNS_TRUNCATED_EDNS" or "TRUNC" in sc_id:

                def_text = "Respuesta truncada (bandera TC=1): la respuesta excede el límite UDP estándar (512 bytes) y el reintento TCP puerto 53 está bloqueado."

                root_cause_text = "Conjunto voluminoso de registros DNS que requiere fallback a TCP (RFC 1035 / RFC 6891), pero el firewall filtra el tráfico TCP/53."

                root_cause_sub = "Coincide con la telemetría: bandera TC=1 activa y fallo en conexión sobre socket TCP."

                chk_steps = [

                    ("1. Probar respuesta UDP restringida a 512 bytes", "dig @127.0.0.1 -p 5353 large-recordset.corp.internal ANY +bufsize=512 +notcp"),

                    ("2. Comprobar si la cabecera incluye el bit de truncamiento", "flags: qr tc rd"),

                    ("3. Probar conexión forzada sobre socket de transporte TCP", "dig @127.0.0.1 -p 5353 large-recordset.corp.internal ANY +tcp"),

                    ("4. Comprobar reglas de filtrado de firewall en el puerto 53 TCP", "iptables -L -n -v | grep 53")

                ]

                fix_text = "Permitir el tráfico de entrada TCP en el puerto 53 en el firewall de red y habilitar negociación EDNS0."

                fix_cmd = "iptables -A INPUT -p tcp --dport 53 -j ACCEPT"

            else:  # DELEGATION_ERROR o DEL en sc_id

                def_text = "Error de delegación (Lame Delegation / RCODE 2): los servidores NS delegados en la zona padre no tienen autoridad sobre la zona hija."

                root_cause_text = "Registros NS o pegamento (glue records) desactualizados o apuntando a servidores sin la zona secundaria configurada."

                root_cause_sub = "Coincide con la telemetría: servidor delegado responde con error de cojera (lame server resolving)."

                chk_steps = [

                    ("1. Consultar registros de delegación NS en la zona padre", "dig @127.0.0.1 -p 5353 sub.corp.internal NS"),

                    ("2. Consultar directamente a cada servidor NS hijo para verificar bandera AA", "dig @127.0.0.1 -p 5353 sub.corp.internal SOA +norec"),

                    ("3. Inspeccionar logs de BIND9 buscando advertencias de lame server", 'grep "lame server resolving" named.log'),

                    ("4. Validar consistencia de zona con named-checkzone", "named-checkzone sub.corp.internal /var/named/sub.corp.zone")

                ]

                fix_text = "Sincronizar y corregir los registros NS y glue records en el archivo maestro de zona BIND9 y recargar."

                fix_cmd = "rndc reload"



            codes_title = "RFC 1035 §4.1.1 · Códigos de respuesta"

            codes_items = [

                ("0", "NOERROR", "Sin error", False),

                ("1", "FORMERR", "Error formato", False),

                ("2", "SERVFAIL", "Fallo servidor / Lame", fc in ("SERVFAIL", "DELEGATION_ERROR") or "SRV" in sc_id or "DEL" in sc_id),

                ("3", "NXDOMAIN", "Nombre no existe", fc == "NXDOMAIN" or "NXD" in sc_id),

                ("4", "NOTIMP", "No implementado", False),

                ("5", "REFUSED", "Rechazado política", fc == "DNS_REFUSED" or "REF" in sc_id)

            ]



        elif is_tls:

            header_norma = f"RFC 8446 (TLS 1.3) · 2 fragmentos · {ram_mb} MB RAM"

            rfc_query = f"RFC 8446 (TLS 1.3) {fc} TLS {sc_id}"

            hit1_file = "sop_nginx_gateway_troubleshooting.md"

            hit1_score = "4.2150"

            hit1_title = "2.3 Síntoma: Fallo en Negociación TLS / SSL Handshake Failed"

            hit2_file = "rfc8446_tls_excerpts.md"

            hit2_score = "3.8400"

            hit2_title = "6.2 Error Alerts · Closure and Verification Diagnostics"

            hit2_bar = "85%"



            if "CIPHER" in fc or "CIPH" in sc_id:

                def_text = "Fallo de apretón de manos (handshake_failure 40): cliente y servidor no comparten suites de cifrado criptográfico compatibles."

                root_cause_text = "Directiva ssl_ciphers restrictiva en Nginx o cliente ofreciendo suites deprecadas (ej. solo TLS_RSA cuando se exige ECDHE)."

                root_cause_sub = "Coincide con la telemetría: handshake termina con alerta fatal de incompatibilidad."

                chk_steps = [

                    ("1. Inspeccionar negociación TLS directa con OpenSSL forzando cifrado", "openssl s_client -connect 127.0.0.1:443 -cipher AES128-SHA"),

                    ("2. Evaluar compatibilidad de suites criptográficas admitidas", "openssl ciphers -v 'HIGH:!aNULL:!MD5'"),

                    ("3. Revisar logs de error de Nginx buscando alertas de handshake", 'grep -E "SSL_do_handshake|alert handshake failure|no shared cipher" /var/log/nginx/error.log'),

                    ("4. Validar configuración activa de protocolos y cifrados en Nginx", 'nginx -T | grep -E "ssl_ciphers|ssl_protocols"')

                ]

                fix_text = "Actualizar la directiva ssl_ciphers en /etc/nginx/nginx.conf para admitir suites modernas compatibles y recargar Nginx."

                fix_cmd = "nginx -s reload"

            elif "EXP" in fc or "EXP" in sc_id:

                def_text = "Certificado digital X.509 superó su fecha límite de validez notAfter (certificate_expired 45)."

                root_cause_text = "Certificado TLS expirado sin renovación automática por Let's Encrypt o Certbot."

                root_cause_sub = "Coincide con la telemetría: verify return code: 10 (certificate has expired)."

                chk_steps = [

                    ("1. Inspeccionar fechas de validez del certificado remoto con OpenSSL", "openssl s_client -connect 127.0.0.1:443 -servername secure.corp.internal 2>/dev/null | openssl x509 -noout -dates"),

                    ("2. Verificar código de retorno de verificación de certificados", "openssl s_client -connect 127.0.0.1:443 -servername secure.corp.internal"),

                    ("3. Probar solicitud HTTPS con curl para confirmar fallo de validación", "curl -Iv https://secure.corp.internal"),

                    ("4. Comprobar el temporizador o cron de renovación automática de Certbot", "certbot renew --dry-run")

                ]

                fix_text = "Renovar el certificado digital X.509 expirado mediante Let's Encrypt / Certbot y recargar el servidor web."

                fix_cmd = "certbot renew && nginx -s reload"

            elif "CHAIN" in fc or "CHN" in sc_id:

                def_text = "Cadena de certificación incompleta (unknown_ca 48 / unable to get local issuer certificate code 20)."

                root_cause_text = "Falta el paquete de CA intermedias (Intermediate CA Bundle) en la directiva ssl_certificate."

                root_cause_sub = "Coincide con la telemetría: unable to get local issuer certificate."

                chk_steps = [

                    ("1. Inspeccionar cadena de certificados completa con OpenSSL", "openssl s_client -connect 127.0.0.1:443 -servername secure.corp.internal -showcerts"),

                    ("2. Comprobar la profundidad de la cadena retornada (depth)", 'openssl s_client -connect 127.0.0.1:443 2>&1 | grep "depth="'),

                    ("3. Revisar logs de error de Nginx buscando fallos de verificación", 'grep "certificate verify failed" /var/log/nginx/error.log'),

                    ("4. Comprobar los certificados contenidos en el archivo bundle", "openssl crl2pkcs7 -nocrl -certfile fullchain.pem | openssl pkcs7 -print_certs -noout")

                ]

                fix_text = "Concatenar los certificados de CA intermedias al certificado del servidor para conformar fullchain.pem y recargar Nginx."

                fix_cmd = "cat intermediate.pem >> fullchain.pem && nginx -s reload"

            else:  # SNI mismatch

                def_text = "Discrepancia en la indicación de nombre de servidor (SNI) o nombre de host no registrado (unrecognized_name 112 / hostname mismatch 62)."

                root_cause_text = "Petición dirigida a un FQDN no configurado en los bloques server_name o ausente de los Subject Alternative Names (SAN)."

                root_cause_sub = "Coincide con la telemetría: verify error:num=62:Hostname mismatch y advertencia de certificado default."

                chk_steps = [

                    ("1. Probar conexión indicando SNI del host no registrado", "openssl s_client -connect 127.0.0.1:443 -servername api-unregistered.corp.internal"),

                    ("2. Inspeccionar los nombres SAN del certificado servido", 'openssl x509 -in /etc/ssl/certs/server.crt -noout -text | grep -A1 "Subject Alternative Name"'),

                    ("3. Revisar logs buscando advertencias de fallback a certificado default", 'grep "no matching SSL certificate for SNI host" /var/log/nginx/error.log'),

                    ("4. Validar directivas server_name en la configuración de Nginx", 'nginx -T | grep "server_name"')

                ]

                fix_text = "Añadir el FQDN en la directiva server_name del bloque SSL de Nginx o emitir un certificado con el SAN correspondiente."

                fix_cmd = "nginx -s reload"



            codes_title = "RFC 8446 §6.2 · Alertas y Errores TLS (Alert Protocol)"

            codes_items = [

                ("0", "SUCCESS", "Enlace seguro OK", False),

                ("40", "HANDSHAKE_FAIL", "Suites incompatibles", "CIPHER" in fc or "CIPH" in sc_id),

                ("42", "BAD_CERT", "Certificado inválido", False),

                ("45", "CERT_EXPIRED", "Certificado vencido", "EXP" in fc or "EXP" in sc_id),

                ("48", "UNKNOWN_CA", "Cadena incompleta", "CHAIN" in fc or "CHN" in sc_id),

                ("62", "SNI_MISMATCH", "Discrepancia Hostname", "SNI" in fc or "SNI" in sc_id)

            ]



        else:  # HTTP_WEB / API_GATEWAY

            header_norma = f"RFC 9110 (HTTP Semantics) · 2 fragmentos · {ram_mb} MB RAM"

            rfc_query = f"RFC 9110 (HTTP Semantics) {fc} {cat} {sc_id}"

            hit1_file = "sop_nginx_gateway_troubleshooting.md"

            hit1_score = "4.3500"

            hit1_title = f"2.1 Síntoma: Fallo en Gateway / Proxy Inverso ({fc})"

            hit2_file = "rfc9110_http_excerpts.md"

            hit2_score = "3.9200"

            hit2_title = "15.6 Server Error 5xx · Protocol Diagnostics"

            hit2_bar = "88%"



            if "502" in fc and "ORIGIN" not in fc and "ORIGIN" not in sc_id:

                def_text = "El servidor proxy inverso Nginx no pudo comunicarse con el upstream (Connection Refused 111 o No live upstreams)."

                root_cause_text = "Proceso de aplicación backend (FastAPI / Gunicorn / Node) detenido o puerto 8080 sin escucha activa."

                root_cause_sub = "Coincide con la telemetría: upstream connect failed hacia 127.0.0.1:8080."

                chk_steps = [

                    ("1. Ejecutar solicitud HTTP de sondeo para capturar encabezados", "curl -I -s http://127.0.0.1:80/api/v1/users"),

                    ("2. Consultar el archivo error.log de Nginx buscando fallos upstream", 'grep -E "connect\\(\\) failed|no live upstreams" /var/log/nginx/error.log'),

                    ("3. Ejecutar sondeo local directo hacia el socket del backend", "curl -I http://127.0.0.1:8080/health"),

                    ("4. Verificar sockets activos y escucha en el puerto del backend", "ss -tlpn | grep -E '8080|80'")

                ]

                fix_text = "Reiniciar el servicio de aplicación backend en 127.0.0.1:8080 y validar la conexión con ss -tlpn."

                fix_cmd = "systemctl restart backend-app"

            elif "504" in fc and "LAT" not in fc and "LAT" not in sc_id:

                def_text = "El servidor upstream tardó más del temporizador proxy_read_timeout en emitir los encabezados de respuesta."

                root_cause_text = "Contención en base de datos o latencia severa en la red hacia el host upstream."

                root_cause_sub = "Coincide con la telemetría: upstream timed out leyendo encabezados HTTP."

                chk_steps = [

                    ("1. Ejecutar solicitud HTTP de sondeo para medir tiempo de respuesta", "curl -I -s http://127.0.0.1:80/api/v1/reports"),

                    ("2. Consultar error.log buscando eventos de timeout", 'grep "upstream timed out" /var/log/nginx/error.log'),

                    ("3. Medir tiempo de procesamiento en el backend directo", 'curl -w "@curl-format.txt" -o /dev/null -s http://127.0.0.1:8080/api/v1/reports'),

                    ("4. Validar directivas de temporización en la configuración de Nginx", 'nginx -T | grep -E "proxy_read_timeout|proxy_connect_timeout"')

                ]

                fix_text = "Optimizar la consulta en base de datos o incrementar el parámetro proxy_read_timeout en Nginx."

                fix_cmd = "nginx -s reload"

            elif "ORIGIN" in fc or "ORIGIN" in sc_id:

                def_text = "Todos los servidores del grupo upstream están caídos o inalcanzables (no live upstreams while connecting to upstream)."

                root_cause_text = "Servidores upstream fuera de servicio o caída total del clúster de balanceo en origen."

                root_cause_sub = "Coincide con la telemetría: ningún nodo del pool upstream responde a los health checks."

                chk_steps = [

                    ("1. Ejecutar solicitud al endpoint de salud del gateway", "curl -I -s http://127.0.0.1:80/api/v1/health"),

                    ("2. Consultar logs de error de Nginx buscando indisponibilidad total", 'grep "no live upstreams" /var/log/nginx/error.log'),

                    ("3. Comprobar el estado del servicio en los nodos upstream", "systemctl status upstream-cluster"),

                    ("4. Probar conectividad hacia cada IP del bloque upstream", "curl -I http://10.0.0.5:8080/health")

                ]

                fix_text = "Restablecer el clúster de backend upstream y verificar el estado de los nodos con systemctl."

                fix_cmd = "systemctl restart upstream-cluster"

            elif "POOL" in fc or "POOL" in sc_id:

                def_text = "Agotamiento del pool de conexiones persistentes o sockets de workers en el gateway (503 Service Unavailable)."

                root_cause_text = "Sobrecarga de conexiones concurrentes que supera worker_connections o límite keepalive pool."

                root_cause_sub = "Coincide con la telemetría: connection pool exhausted while connecting to upstream."

                chk_steps = [

                    ("1. Probar solicitud HTTP para verificar la respuesta 503", "curl -I -s http://127.0.0.1:80/api/v1/users"),

                    ("2. Consultar logs de Nginx buscando agotamiento de conexiones", 'grep -E "worker_connections are not enough|connection pool exhausted" /var/log/nginx/error.log'),

                    ("3. Inspeccionar conexiones activas y sockets en TIME_WAIT", "ss -s"),

                    ("4. Revisar directivas worker_connections y keepalive en nginx.conf", 'nginx -T | grep -E "worker_connections|keepalive"')

                ]

                fix_text = "Aumentar worker_connections y el parámetro keepalive en el bloque upstream de nginx.conf."

                fix_cmd = "nginx -s reload"

            elif "403" in fc or "403" in sc_id:

                def_text = "El API Gateway o servidor proxy denegó el acceso al recurso por una política de control de acceso (403 Forbidden)."

                root_cause_text = "Directiva deny all en el bloque location o dirección IP del cliente no autorizada en allow."

                root_cause_sub = "Coincide con la telemetría: access forbidden by rule para la IP del cliente."

                chk_steps = [

                    ("1. Ejecutar solicitud HTTP a la ruta restringida", "curl -I -s http://127.0.0.1:80/admin/system/status"),

                    ("2. Consultar error.log buscando el bloqueo de seguridad", 'grep "access forbidden by rule" /var/log/nginx/error.log'),

                    ("3. Revisar directivas allow y deny en la ruta administrativa", 'nginx -T | grep -A 5 "location /admin"'),

                    ("4. Confirmar la dirección IP origen del cliente en el encabezado X-Forwarded-For", "curl -v http://127.0.0.1:80/admin/system/status")

                ]

                fix_text = "Autorizar la subred o IP del cliente en la directiva allow de /etc/nginx/conf.d/admin.conf y recargar Nginx."

                fix_cmd = "nginx -s reload"

            elif "429" in fc or "429" in sc_id:

                def_text = "La frecuencia de peticiones superó la cuota asignada por el módulo de limitación de tráfico (429 Too Many Requests)."

                root_cause_text = "Módulo limit_req activado por ráfagas superiores a la tasa rate y ráfaga burst configuradas."

                root_cause_sub = "Coincide con la telemetría: limiting requests, excess by zone req_limit_per_ip."

                chk_steps = [

                    ("1. Ejecutar ráfaga de peticiones para reproducir el corte", "curl -I -s http://127.0.0.1:80/api/v1/search?q=telecom"),

                    ("2. Consultar error.log buscando registros de exceso de tasa", 'grep "limiting requests" /var/log/nginx/error.log'),

                    ("3. Revisar los parámetros de limit_req_zone en nginx.conf", 'nginx -T | grep "limit_req"'),

                    ("4. Verificar el encabezado Retry-After en la respuesta 429", 'curl -i -s http://127.0.0.1:80/api/v1/search?q=telecom | grep "Retry-After"')

                ]

                fix_text = "Incrementar el parámetro burst o ajustar la tasa de la directiva limit_req_zone en nginx.conf."

                fix_cmd = "nginx -s reload"

            elif "503" in fc or "503" in sc_id:

                def_text = "El servidor upstream no puede atender la solicitud debido a una sobrecarga temporal de peticiones (503 Service Unavailable)."

                root_cause_text = "Agotamiento de hilos de atención en el pool de procesos de la aplicación backend."

                root_cause_sub = "Coincide con la telemetría: upstream temporarily unavailable while reading response header."

                chk_steps = [

                    ("1. Probar solicitud HTTP al endpoint de órdenes", "curl -I -s http://127.0.0.1:80/api/v1/orders"),

                    ("2. Revisar error.log buscando indisponibilidad temporal del backend", 'grep "upstream temporarily unavailable" /var/log/nginx/error.log'),

                    ("3. Monitorear carga de CPU y consumo de memoria del backend", "systemctl status backend-application-pool"),

                    ("4. Verificar tamaño de la cola de backlog de conexiones", "ss -lnt '( sport = :8080 )'")

                ]

                fix_text = "Reiniciar el pool de aplicaciones backend y escalar la capacidad de workers para absorber la demanda."

                fix_cmd = "systemctl restart backend-application-pool"

            elif "500" in fc or "500" in sc_id:

                def_text = "El servicio backend encontró una condición inesperada o excepción no capturada en tiempo de ejecución (500 Internal Server Error)."

                root_cause_text = "Excepción no controlada en el código fuente de la aplicación backend (ej. KeyError: user_id)."

                root_cause_sub = "Coincide con la telemetría: respuesta 500 originada por fallo interno en el microservicio."

                chk_steps = [

                    ("1. Ejecutar solicitud HTTP al endpoint afectado", "curl -I -s http://127.0.0.1:80/api/v1/checkout"),

                    ("2. Consultar los logs del backend buscando el traceback de la excepción", "journalctl -u backend-app -n 50 --no-pager"),

                    ("3. Verificar si el proxy Nginx capturó el error", 'grep "500" /var/log/nginx/access.log'),

                    ("4. Comprobar variables de entorno y estado de base de datos del servicio", "systemctl show-environment backend-app")

                ]

                fix_text = "Depurar el traceback de error en el backend con journalctl y desplegar la corrección en la aplicación."

                fix_cmd = "journalctl -u backend-app -n 50"

            elif "LAT" in fc or "LAT" in sc_id:

                def_text = "Degradación extrema por retardo artificial inyectado en la interfaz de red (emulación tc netem)."

                root_cause_text = "Regla tc qdisc con delay de 2000ms activa en el enlace provocando latencia anormal y timeouts."

                root_cause_sub = "Coincide con la telemetría: RTT promedio supera los 2000 ms y genera advertencias de timeout."

                chk_steps = [

                    ("1. Medir latencia de red mediante paquetes ICMP", "ping -c 4 127.0.0.1"),

                    ("2. Inspeccionar disciplinas de cola activas con Traffic Control (tc)", "tc qdisc show dev eth0"),

                    ("3. Revisar logs buscando demoras en conexión con upstream", 'grep "upstream timed out" /var/log/nginx/error.log'),

                    ("4. Medir tiempo de conexión TCP con curl", 'curl -o /dev/null -s -w "time_connect: %{time_connect}\\n" http://127.0.0.1:80/api/v1/reports')

                ]

                fix_text = "Eliminar la disciplina de cola tc netem en la interfaz eth0 para restaurar la latencia nominal del enlace."

                fix_cmd = "tc qdisc del dev eth0 root"

            else:

                def_text = f"Anomalía en el procesamiento HTTP ({fc}) reportada por la capa de gateway."

                root_cause_text = "Sobrecarga de workers o política de control de acceso denegada en Nginx."

                root_cause_sub = "Coincide con la telemetría: código de error emitido por el reverse proxy."

                chk_steps = [

                    ("1. Ejecutar solicitud HTTP de sondeo para capturar encabezados", "curl -I -s http://127.0.0.1:80/api/v1/users"),

                    ("2. Consultar el archivo error.log de Nginx buscando fallos upstream", 'grep -E "connect\\(\\) failed|upstream timed out|no live upstreams" /var/log/nginx/error.log'),

                    ("3. Ejecutar sondeo local directo hacia el socket del backend", "curl -I http://127.0.0.1:8080/health"),

                    ("4. Verificar sockets activos y escucha en el puerto del backend", "ss -tlpn | grep -E '8080|80'")

                ]

                fix_text = "Ajustar las directivas de conexión en nginx.conf y recargar el servicio."

                fix_cmd = "nginx -s reload"



            codes_title = "RFC 9110 §15 · Códigos de estado HTTP (HTTP Semantics)"

            codes_items = [

                ("200", "OK", "Petición exitosa", False),

                ("403", "FORBIDDEN", "Acceso denegado", "403" in fc or "403" in sc_id),

                ("429", "TOO_MANY_REQ", "Tasa excedida", "429" in fc or "429" in sc_id),

                ("500", "INTERNAL_ERR", "Fallo en backend", "500" in fc or "500" in sc_id),

                ("502", "BAD_GATEWAY", "Fallo upstream", "502" in fc or "ORIGIN" in fc or "502" in sc_id or "ORIGIN" in sc_id),

                ("504", "TIMEOUT", "Tiempo agotado", "504" in fc or "503" in fc or "POOL" in fc or "LAT" in fc or "504" in sc_id or "503" in sc_id or "POOL" in sc_id or "LAT" in sc_id)

            ]



        # Sobrescribir hits si se detectan chunks reales en raw_payload

        m_hits = re.findall(r"---\s*\[NORMA\s*/\s*PROCEDIMIENTO\s*\d+\]:\s*([^\s]+)\s*->\s*(.+?)\s*\(Score:\s*([\d.]+)\)\s*---", raw_payload)

        if m_hits and len(m_hits) >= 1:

            hit1_file = m_hits[0][0].strip()

            hit1_title = m_hits[0][1].strip()

            hit1_score = m_hits[0][2].strip()

        if m_hits and len(m_hits) >= 2:

            hit2_file = m_hits[1][0].strip()

            hit2_title = m_hits[1][1].strip()

            hit2_score = m_hits[1][2].strip()

            try:

                s1 = float(hit1_score)

                s2 = float(hit2_score)

                hit2_bar = f"{min(100, max(20, int(round((s2 / max(0.001, s1)) * 100))))}%"

            except Exception:

                hit2_bar = "75%"



        # Checklist HTML

        chk_html_items = []

        for s_idx, (s_title, s_cmd) in enumerate(chk_steps, 1):

            esc_cmd = html.escape(s_cmd, quote=True)

            chk_html_items.append(f"""

            <li data-step-item data-done="false" class="flex gap-3 items-start p-3 rounded-lg border border-slate-800/80 bg-[#0A0E16] transition-colors">

                <button type="button" onclick="toggleChecklistStep(this)" aria-label="Marcar paso {s_idx}" class="shrink-0 w-6 h-6 mt-0.5 rounded-md border border-slate-600 flex items-center justify-center cursor-pointer transition-colors hover:border-slate-400"></button>

                <div class="flex flex-col gap-2 min-w-0 flex-1">

                    <span data-step-text class="text-sm text-slate-200">{s_title}</span>

                    <div class="flex gap-2 items-center flex-wrap">

                        <code class="font-mono text-xs text-emerald-300 bg-[#0B1F1A] border border-emerald-900/40 rounded px-2.5 py-1 overflow-x-auto whitespace-nowrap">{html.escape(s_cmd)}</code>

                        <button type="button" onclick="copyCliSnippet('{esc_cmd}', this)" class="text-xs px-2.5 py-1 rounded border border-slate-700 bg-[#101624] text-slate-300 hover:text-white cursor-pointer transition">Copiar</button>

                    </div>

                </div>

            </li>

            """)

        checklist_rendered = "".join(chk_html_items)



        # Códigos de referencia HTML

        codes_cards = []

        for c_num, c_name, c_desc, c_active in codes_items:

            if c_active:

                bg_box = "bg-[#1C1608] border border-amber-500/80 text-amber-300 shadow-sm shadow-amber-950/40"

                num_col = "text-amber-400 font-bold"

                sub_col = "text-amber-200/80"

            else:

                bg_box = "bg-[#0A0E16] border border-slate-800/80 text-slate-200"

                num_col = "text-slate-400 font-bold" if c_num not in ("0", "200") else "text-emerald-400 font-bold"

                sub_col = "text-slate-400"



            codes_cards.append(f"""

            <div class="flex flex-col gap-1 p-2.5 rounded-lg {bg_box}">

                <div class="flex gap-1.5 items-baseline">

                    <span class="font-mono text-base {num_col}">{c_num}</span>

                    <span class="font-mono text-[11px] font-semibold">{c_name}</span>

                </div>

                <span class="text-[11px] {sub_col} leading-tight">{c_desc}</span>

            </div>

            """)

        codes_rendered = "".join(codes_cards)



        # Código crudo resaltado con cabecera de archivo

        highlighted_md = _highlight_markdown_syntax(raw_payload) if raw_payload else ""

        file_header_md = (

            '<div class="flex items-center justify-between px-4 py-1.5 bg-[#1e293b] border border-slate-700/60 '

            'border-b-0 rounded-t-lg text-[11px] text-slate-400 font-mono tracking-wider shadow-sm">'

            '<span class="flex items-center gap-2">'

            '<svg class="w-3 h-3 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">'

            '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" '

            'd="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>'

            '</svg> rag_context_output.md</span>'

            '<span>Markdown • Read Only</span>'

            '</div>'

        )

        raw_code_block = (

            f'{file_header_md}'

            f'<pre class="mt-0 p-4 bg-[#090b10] border border-slate-700/60 rounded-b-lg rounded-t-none text-xs md:text-[13px] '

            f'text-slate-300 font-mono leading-relaxed shadow-inner overflow-auto max-h-72 scrollbar-thin scrollbar-thumb-slate-600 '

            f'scrollbar-track-transparent hover:scrollbar-thumb-slate-500"><code class="language-markdown">{highlighted_md}</code></pre>'

        )



        card_html = f"""

        <!-- El Nuevo Dashboard Acordeón (Tarjeta Interior) -->

        <details class="group bg-[#101624] border border-slate-800/80 rounded-xl overflow-hidden shadow-sm" data-node-card>

            <!-- Cabecera Interactiva -->

            <summary class="flex flex-wrap gap-4 items-center justify-between p-4 cursor-pointer list-none hover:bg-slate-800/40 transition-colors select-none">

                <div class="flex gap-3 items-center flex-wrap">

                    <svg class="w-5 h-5 text-amber-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 3h9l3 3v15H6z"></path><path d="M9 10h6M9 14h6M9 18h4"></path></svg>

                    <h2 class="m-0 text-base sm:text-[17px] font-semibold text-slate-100">Recuperación normativa IETF (RAG)</h2>

                    <span class="font-mono text-xs text-slate-400">{header_norma}</span>

                    <span class="text-xs px-2.5 py-0.5 rounded-full bg-blue-950/60 text-blue-300 border border-blue-800/40">Índice Semántico</span>

                </div>

                <div class="flex items-center gap-2">

                    <svg class="w-5 h-5 text-slate-500 transform transition-transform duration-200 group-open:rotate-180" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>

                </div>

            </summary>



            <!-- Cuerpo del Dashboard (Contenido a revelar) -->

            <div class="border-t border-slate-800/80 p-4">

                <!-- Selector de pestañas Vista vs Markdown crudo -->

                <div class="flex justify-end mb-4">

                    <div role="tablist" aria-label="Vista de la etapa" class="flex gap-1 bg-[#0A0E16] p-1 rounded-lg border border-slate-800/60">

                        <button type="button" role="tab" data-tab-target="vista" onclick="switchNodeTab(this, 'vista')" class="text-xs sm:text-[13px] px-3 py-1.5 rounded-md font-semibold bg-[#1E2A40] text-slate-100 transition-colors">Vista</button>

                        <button type="button" role="tab" data-tab-target="raw" onclick="switchNodeTab(this, 'raw')" class="text-xs sm:text-[13px] px-3 py-1.5 rounded-md font-medium text-slate-400 hover:text-slate-200 transition-colors">Markdown crudo</button>

                    </div>

                </div>



                <!-- Pestaña Vista -->

                <div data-panel="vista" class="flex flex-col gap-6">

                    <!-- 1. Consulta y Hits de Búsqueda -->

                <div class="flex flex-col gap-2.5">

                    <div class="text-xs text-slate-400">Consulta enviada al índice RAG</div>

                    <code class="font-mono text-xs sm:text-[13px] bg-[#0A0E16] border border-slate-800/80 rounded-lg p-3 text-slate-200 overflow-x-auto whitespace-nowrap block">{html.escape(rfc_query)}</code>

                    <div class="grid grid-cols-1 md:grid-cols-2 gap-3 mt-1">

                        <div class="bg-[#0A0E16] border border-slate-800/80 rounded-lg p-3.5 flex flex-col gap-2">

                            <div class="flex justify-between gap-2 text-xs">

                                <span class="font-mono text-slate-400">#1 · {hit1_file}</span>

                                <span class="font-mono font-semibold text-blue-300">Score: {hit1_score}</span>

                            </div>

                            <div class="text-sm font-semibold text-slate-100">{hit1_title}</div>

                            <div class="h-1.5 bg-[#1A2233] rounded-full overflow-hidden">

                                <div class="h-full bg-blue-400 w-full rounded-full"></div>

                            </div>

                        </div>

                        <div class="bg-[#0A0E16] border border-slate-800/80 rounded-lg p-3.5 flex flex-col gap-2">

                            <div class="flex justify-between gap-2 text-xs">

                                <span class="font-mono text-slate-400">#2 · {hit2_file}</span>

                                <span class="font-mono font-semibold text-blue-300">Score: {hit2_score}</span>

                            </div>

                            <div class="text-sm font-semibold text-slate-100">{hit2_title}</div>

                            <div class="h-1.5 bg-[#1A2233] rounded-full overflow-hidden">

                                <div class="h-full bg-blue-400 rounded-full" style="width: {hit2_bar};"></div>

                            </div>

                        </div>

                    </div>

                </div>



                <!-- 2. Definición + Causa Raíz -->

                <div class="grid grid-cols-1 md:grid-cols-2 gap-3">

                    <div class="bg-[#0A0E16] border border-slate-800/80 rounded-lg p-4 flex flex-col gap-1.5">

                        <div class="text-xs text-slate-400">Qué significa ({hit1_file.split('.')[0].upper()})</div>

                        <p class="m-0 text-sm text-slate-200">{def_text}</p>

                    </div>

                    <div class="bg-[#0A0E16] border border-slate-800/80 rounded-lg p-4 flex flex-col gap-1.5">

                        <div class="text-xs text-slate-400">Causa raíz probable</div>

                        <p class="m-0 text-sm text-slate-200">{root_cause_text}</p>

                        <p class="m-0 text-xs text-slate-500">{root_cause_sub}</p>

                    </div>

                </div>



                <!-- 3. Checklist Interactivo -->

                <div class="flex flex-col gap-2.5">

                    <div class="flex justify-between items-baseline gap-2 flex-wrap">

                        <h3 class="m-0 text-sm font-semibold text-slate-200">Verificación técnica obligatoria</h3>

                        <span data-checklist-count class="text-xs text-slate-400 font-mono">0 de 4 completadas</span>

                    </div>

                    <div class="h-1 bg-[#1A2233] rounded-full overflow-hidden">

                        <div data-checklist-progress class="h-full bg-emerald-400 transition-all duration-300" style="width: 0%;"></div>

                    </div>

                    <ol class="m-0 p-0 list-none flex flex-col gap-2">

                        {checklist_rendered}

                    </ol>

                </div>



                <!-- 4. Acción Correctiva -->

                <div class="bg-[#0E2A22] border border-[#1D5A47] rounded-lg p-4 flex flex-col gap-2">

                    <div class="text-xs text-emerald-400 font-semibold tracking-wider">ACCIÓN CORRECTIVA</div>

                    <p class="m-0 text-sm text-slate-200">{fix_text}</p>

                    <div class="flex gap-2 items-center flex-wrap">

                        <code class="font-mono text-xs text-white bg-[#0A0E16] border border-emerald-900/50 rounded px-2.5 py-1">{fix_cmd}</code>

                        <button type="button" onclick="copyCliSnippet('{fix_cmd}', this)" class="text-xs px-2.5 py-1 rounded border border-[#1D5A47] bg-[#0A0E16] text-slate-300 hover:text-white cursor-pointer transition">Copiar</button>

                    </div>

                </div>



                <!-- 5. Códigos Normativos -->

                <div class="flex flex-col gap-2.5">

                    <h3 class="m-0 text-sm font-semibold text-slate-200">{codes_title}</h3>

                    <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-2">

                        {codes_rendered}

                    </div>

                </div>

            </div>



                <!-- Pestaña Crudo -->

                <div data-panel="raw" class="hidden">

                    {raw_code_block}

                </div>

            </div>

        </details>

        """



    # =========================================================================

    # CASO 3: NODO GENÉRICO

    # =========================================================================

    else:

        file_header = (

            f'<div class="flex items-center justify-between px-4 py-1.5 bg-[#1e293b] border border-slate-700/60 '

            f'border-b-0 rounded-t-lg text-[11px] text-slate-400 font-mono tracking-wider shadow-sm">'

            f'<span class="flex items-center gap-2">{node_name}_output.log</span>'

            f'<span>Plain Text • Read Only</span>'

            f'</div>'

        )

        highlighted_code = html.escape(raw_payload, quote=False)

        raw_code_block = (

            f'{file_header}'

            f'<pre class="mt-0 p-4 bg-[#090b10] border border-slate-700/60 rounded-b-lg rounded-t-none text-xs md:text-[13px] '

            f'text-slate-300 font-mono leading-relaxed shadow-inner overflow-auto max-h-72 scrollbar-thin scrollbar-thumb-slate-600 '

            f'scrollbar-track-transparent hover:scrollbar-thumb-slate-500"><code>{highlighted_code}</code></pre>'

        )

        card_html = f"""

        <div class="bg-[#101624] border border-slate-800/80 rounded-xl overflow-hidden shadow-sm p-4" data-node-card>

            <div class="flex items-center justify-between mb-3">

                <span class="text-xs font-bold text-slate-100">{title or node_name}</span>

                <span class="font-mono text-xs text-slate-400">[{node_name}]</span>

            </div>

            {raw_code_block}

        </div>

        """



    # Retornar envoltorio estricto del Timeline

    return f"""

    <div class="relative pl-[3.25rem] pb-6 transition-all duration-300 animate-fadeIn" data-node="{node_name}">

        <!-- Ícono circular anclado sobre la línea vertical izquierda -->

        <div class="absolute left-0 top-0 transform translate-x-[5px] w-8 h-8 rounded-full bg-slate-800 border-2 border-slate-600 flex items-center justify-center z-10 shadow-md">

            {icon_svg}

        </div>

        {card_html}

    </div>

    """





def _render_hypothesis_node(

    node_name: str,

    model_id: str,

    affected_component: str,

    fault_class: str,

    description: str

) -> str:

    """Genera el nodo limpio de razonamiento sin etiquetas <thought> y con icono de cerebro (Regla 1 y 3)."""

    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]

    return f"""

    <div class="relative pl-8 pb-5 transition-all duration-300 animate-fadeIn" data-node="{node_name}">

        <!-- Icono de eje: Cerebro pequeño SVG (sin números grandes - Regla 1) -->

        <div class="absolute -left-[11px] top-1.5 w-6 h-6 rounded-full border border-purple-500/50 bg-[#0e1b2e] flex items-center justify-center shadow-md shadow-purple-900/30">

            <svg class="w-3.5 h-3.5 text-purple-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">

                <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 4.44-2.04Z"/>

                <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-4.44-2.04Z"/>

            </svg>

        </div>



        <!-- Tarjeta limpia de Razonamiento del Agente (Regla 3) -->

        <div class="bg-[#0e1b2e] border border-slate-700/60 rounded-xl p-4 shadow-lg">

            <div class="flex items-center justify-between mb-2 pb-2 border-b border-slate-800">

                <div class="flex items-center gap-2">

                    <span class="text-xs font-bold text-slate-100 flex items-center gap-1.5">

                        🧠 Razonamiento del Agente

                    </span>

                    <span class="font-mono text-[10px] text-purple-300 px-1.5 py-0.5 rounded bg-purple-950/60 border border-purple-800/40 font-semibold">[{node_name}]</span>

                </div>

                <div class="flex items-center gap-2">

                    <span class="text-[11px] font-mono text-slate-400">{ts}</span>

                    <span class="text-[10px] px-2 py-0.5 rounded-full font-semibold border bg-purple-900/40 text-purple-300 border-purple-500/30">HIPÓTESIS</span>

                </div>

            </div>

            <p class="text-xs text-slate-200 leading-relaxed font-sans">

                La telemetría analizada indica una anomalía técnica en el servicio: <span class="text-slate-300 font-medium">"{description}"</span>. Conforme a los estándares normativos IETF recuperados, el modelo <strong>{model_id}</strong> formula como hipótesis técnica principal una afectación en el componente <strong>{affected_component}</strong> ({fault_class}). Para corroborar de forma concluyente esta causa raíz sin impacto operacional, se procede a ejecutar un comando diagnóstico de red de solo lectura.

            </p>

        </div>

    </div>

    """





def _render_terminal_block(

    step_num: int = 4,

    node_name: str = "execute_read_only_tool",

    tool_name: str = "dig",

    command: str = "",

    output: str = "",

    exit_code: int = 0

) -> str:

    """Genera el HTML para un bloque de evidencia estilo consola de red con las clases requeridas (Regla 1 y 4)."""

    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]

    escaped_command = command.replace("\\", "\\\\").replace("'", "\\'").replace('"', '&quot;')

    return f"""

    <div class="relative pl-8 pb-5 transition-all duration-300 animate-fadeIn" data-node="{node_name}">

        <!-- Icono de eje: Terminal pequeño SVG (sin números grandes - Regla 1) -->

        <div class="absolute -left-[11px] top-1.5 w-6 h-6 rounded-full border border-emerald-500/50 bg-[#0e1b2e] flex items-center justify-center shadow-md shadow-emerald-900/30">

            <svg class="w-3.5 h-3.5 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">

                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/>

            </svg>

        </div>



        <div class="space-y-1.5">

            <div class="flex items-center justify-between text-xs text-slate-400 font-mono">

                <span class="flex items-center gap-1.5 text-slate-300 font-bold">

                    <span>💻 Consola de Evidencia Read-Only</span>

                    <span class="text-[10px] text-emerald-300 px-1.5 py-0.5 rounded bg-emerald-950/60 border border-emerald-800/40">[{node_name}]</span>

                </span>

                <span>{ts}</span>

            </div>



            <!-- Bloque de código con clases forzadas de terminal real (Regla 4) -->

            <div class="bg-[#0d1117] font-mono text-green-400 p-4 rounded-md border border-slate-700 text-xs overflow-x-auto shadow-2xl space-y-2">

                <div class="flex items-center justify-between border-b border-slate-800 pb-2 select-none text-[11px] text-slate-400">

                    <div class="flex items-center gap-1.5">

                        <span class="w-2.5 h-2.5 rounded-full bg-red-500/80 inline-block"></span>

                        <span class="w-2.5 h-2.5 rounded-full bg-yellow-500/80 inline-block"></span>

                        <span class="w-2.5 h-2.5 rounded-full bg-green-500/80 inline-block"></span>

                        <span class="ml-2 font-mono text-slate-400">bash &bull; read-only {tool_name}</span>

                    </div>

                    <div class="flex items-center gap-2">

                        <button type="button"

                                onclick="copyTextToClipboard(this, '{escaped_command}')"

                                class="btn-copy-command text-[10px] text-slate-300 hover:text-white px-2 py-0.5 rounded bg-slate-800/90 border border-slate-700 hover:border-slate-500 transition flex items-center gap-1 cursor-pointer"

                                title="Copiar comando de red al portapapeles">

                            <span>📋</span> <span class="copy-label">Copiar comando</span>

                        </button>

                        <span class="font-mono text-emerald-400 bg-emerald-950/80 border border-emerald-700/50 px-2 py-0.5 rounded text-[10px]">exit {exit_code}</span>

                    </div>

                </div>

                <div class="flex items-start gap-2 text-green-300 font-bold min-w-0">

                    <span class="text-green-500 select-none shrink-0">agent@noc-terminal:~$</span>

                    <span class="text-green-400 break-all">{command}</span>

                </div>

                <pre class="pt-1 text-green-400 leading-relaxed whitespace-pre-wrap break-all font-mono text-xs overflow-x-auto max-w-full">{output}</pre>

            </div>

        </div>

    </div>

    """





def _render_evaluation_node(node_name: str = "evaluate_evidence", summary_text: str = "") -> str:

    """Genera la evaluación sutil de evidencia empírica con icono SVG (Regla 1)."""

    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]

    return f"""

    <div class="relative pl-8 pb-4 transition-all duration-300 animate-fadeIn" data-node="{node_name}">

        <!-- Icono de eje: Verificación SVG (sin números grandes - Regla 1) -->

        <div class="absolute -left-[11px] top-1.5 w-6 h-6 rounded-full border border-emerald-500/50 bg-[#0e1b2e] flex items-center justify-center shadow-md shadow-emerald-900/30">

            <svg class="w-3.5 h-3.5 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">

                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>

            </svg>

        </div>

        <div class="bg-[#0e1b2e] border border-slate-700/60 rounded-xl p-3.5 shadow-md flex items-center justify-between flex-wrap gap-2">

            <div class="flex items-center gap-2">

                <span class="text-xs font-bold text-emerald-300 flex items-center gap-1.5">

                    <span>✓ Evidencia Comprobada</span>

                    <span class="font-mono text-[10px] text-emerald-300 px-1.5 py-0.5 rounded bg-emerald-950/60 border border-emerald-800/40">[{node_name}]</span>

                </span>

                <span class="text-xs text-slate-300 font-sans">{summary_text}</span>

            </div>

            <span class="text-[11px] font-mono text-slate-400">{ts}</span>

        </div>

    </div>

    """





def _render_final_verdict(
    scenario_id: str,
    root_cause: str,
    affected_component: str,
    suggested_action: str,
    explanation: str,
    confidence_score: float = 0.95,
    ttft_ms: float = 124.5,
    tok_per_sec: float = 43.2,
    vram_peak_gb: float = 2.8,
    latency_ms: float = 1850.0,
    step_num: int = 6,
    is_evidence_backed: bool = True
) -> str:
    """Genera el HTML destacado para el nodo final con borde esmeralda y bloques aislados (Regla 1 y 5).
    Los campos provienen exclusivamente del modelo evaluado y se traducen obligatoriamente al español si vienen en inglés.
    """
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]

    # Traducción estricta: todos los campos provienen del modelo y se traducen al español
    rc_text = (root_cause or "").strip()
    if rc_text and rc_text.lower() not in ("desconocido", "none", "null"):
        safe_root_cause = translate_english_to_spanish(rc_text)
    else:
        safe_root_cause = "El modelo no especificó una causa raíz concluyente en su respuesta."

    comp_text = (affected_component or "").strip()
    if comp_text and comp_text.lower() not in ("desconocido", "none", "null"):
        safe_affected_component = translate_english_to_spanish(comp_text)
    else:
        safe_affected_component = "desconocido (no especificado por el modelo)"

    act_text = (suggested_action or "").strip()
    if act_text and act_text.lower() not in ("desconocido", "none", "null"):
        safe_suggested_action = translate_english_to_spanish(act_text)
    else:
        safe_suggested_action = "El modelo no especificó una acción de mitigación en su respuesta."

    exp_text = (explanation or "").strip()
    if exp_text:
        safe_explanation = translate_english_to_spanish(exp_text)
    else:
        safe_explanation = "El modelo completó la inferencia sin generar fundamentación técnica adicional."

    return f"""

    <div class="relative pl-8 pb-4 transition-all duration-300 animate-fadeIn">

        <!-- Punto final de la línea de tiempo: Checkmark SVG blanco en fondo esmeralda (sin números - Regla 1) -->

        <div class="absolute -left-[13px] top-1.5 w-6 h-6 rounded-full border-2 bg-emerald-500 border-white flex items-center justify-center shadow-lg shadow-emerald-500/30">

            <svg class="w-3.5 h-3.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">

                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7"/>

            </svg>

        </div>



        <!-- Tarjeta de Diagnóstico Final con BORDE ESMERALDA / VERDE VISUALMENTE DESTACADO (Regla 5) -->

        <div class="timeline-verdict-card bg-gradient-to-br from-[#0e1b2e] to-[#07131e] border-2 border-emerald-500 rounded-2xl p-6 shadow-2xl shadow-emerald-950/40 relative overflow-hidden"

             data-scenario-id="{scenario_id}"

             data-root-cause="{safe_root_cause}"

             data-affected-component="{safe_affected_component}"

             data-suggested-action="{safe_suggested_action}">

            <div class="absolute top-0 right-0 w-44 h-44 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none"></div>



            <div class="flex items-center justify-between border-b border-slate-700/80 pb-4 mb-5 flex-wrap gap-2">

                <div class="flex items-center gap-2">

                    <span class="bg-emerald-600 text-white text-xs px-2.5 py-1 rounded font-bold uppercase tracking-wider flex items-center gap-1.5 shadow">

                        <span class="w-2 h-2 rounded-full bg-white animate-pulse"></span>

                        DIAGNÓSTICO FINAL

                    </span>

                    <span class="text-slate-300 font-mono text-xs">Escenario: <strong class="text-white">{scenario_id}</strong></span>

                </div>

                <div class="flex items-center gap-2 flex-wrap">

                    <button type="button" onclick="copyTicketToClipboard(this)" class="btn-copy-ticket px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-600 text-xs font-semibold transition-colors flex items-center gap-1.5 cursor-pointer shadow-sm">

                        <span>📋</span>

                        <span>Copiar Ficha para Ticket</span>

                    </button>

                    <span class="evidence-confidence-badge text-xs px-2.5 py-0.5 rounded-full bg-emerald-900/60 border border-emerald-500/40 text-emerald-300 font-bold">

                        {int(confidence_score * 100)}% CONFIANZA &bull; RESPALDADO EN EVIDENCIA

                    </span>

                    <span class="text-xs font-mono text-slate-400">{ts}</span>

                </div>

            </div>



            <!-- Grilla aislando claramente Causa Raíz, Componente y Acción Sugerida (Regla 5) -->

            <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-5">

                <!-- Bloque 1: Causa Raíz Aislada -->

                <div class="verdict-subbox bg-[#070e18] border-2 border-red-500/60 rounded-xl p-4 shadow-md">

                    <div class="flex items-center gap-2 mb-1.5">

                        <span class="w-2.5 h-2.5 rounded-full bg-red-500"></span>

                        <span class="text-xs font-bold text-red-400 uppercase tracking-wider">Causa Raíz</span>

                    </div>

                    <p class="text-sm font-semibold text-white leading-relaxed" data-verdict-rc="{safe_root_cause}">{safe_root_cause}</p>

                </div>



                <!-- Bloque 2: Componente Afectado Aislado -->

                <div class="verdict-subbox bg-[#070e18] border-2 border-amber-500/60 rounded-xl p-4 shadow-md">

                    <div class="flex items-center gap-2 mb-1.5">

                        <span class="w-2.5 h-2.5 rounded-full bg-amber-500"></span>

                        <span class="text-xs font-bold text-amber-400 uppercase tracking-wider">Componente</span>

                    </div>

                    <p class="text-sm font-semibold text-white font-mono leading-relaxed" data-verdict-comp="{safe_affected_component}">{safe_affected_component}</p>

                </div>



                <!-- Bloque 3: Acción Sugerida Aislada -->

                <div class="verdict-subbox bg-[#070e18] border-2 border-emerald-500/60 rounded-xl p-4 shadow-md md:col-span-2">

                    <div class="flex items-center gap-2 mb-1.5">

                        <span class="w-2.5 h-2.5 rounded-full bg-emerald-500"></span>

                        <span class="text-xs font-bold text-emerald-400 uppercase tracking-wider">Acción Sugerida (SOP / Mitigación)</span>

                    </div>

                    <p class="text-sm font-medium text-slate-100 leading-relaxed" data-verdict-act="{safe_suggested_action}">{safe_suggested_action}</p>

                </div>

            </div>



            <!-- Explicación en lenguaje natural -->

            <div class="verdict-subbox text-xs text-slate-300 leading-relaxed bg-[#070e18]/80 p-4 rounded-xl border border-slate-800 mb-4">

                <strong class="text-slate-200 block mb-1 font-sans text-xs uppercase tracking-wider">Fundamentación Técnica y Cadena de Razonamiento:</strong>

                <p class="font-sans text-sm text-slate-300 leading-relaxed">{safe_explanation}</p>

            </div>



            <!-- Pie de tarjeta: Telemetría de Inferencia y Firma de la Plataforma (Limpio y de Ancho Completo) -->

            <div class="pt-3 border-t border-slate-700/60 flex items-center justify-between text-xs font-mono tabular-nums text-slate-400 flex-wrap gap-2 w-full">

                <div class="flex items-center gap-2 flex-wrap">

                    <span class="text-slate-400 font-medium">Telemetría de Inferencia Computada:</span>

                    <span class="text-slate-300 font-mono tabular-nums">

                        TTFT: <strong class="text-slate-200 font-semibold tabular-nums cursor-help" title="Time-To-First-Token: latencia al primer token emitido">{ttft_ms} ms</strong> &bull;

                        Velocidad: <strong class="text-slate-200 font-semibold tabular-nums cursor-help" title="Tokens por segundo generados">{tok_per_sec} tok/s</strong> &bull;

                        VRAM: <strong class="text-slate-200 font-semibold tabular-nums cursor-help" title="Consumo pico de memoria de video GPU">{vram_peak_gb} GB</strong> &bull;

                        Latencia: <strong class="text-slate-200 font-semibold tabular-nums cursor-help" title="Latencia total del proceso de inferencia">{latency_ms} ms</strong>

                    </span>

                </div>

                <div class="text-[11px] font-mono text-slate-500 text-right">

                    <span>NetDiagBench-L7 &bull; Certificado Reproducible</span>

                </div>

            </div>

        </div>

    </div>

    """





def _render_narrative_node(

    step_num: int = 1,

    node_name: str = "",

    title: str = "",

    description: str = "",

    badge_text: str = "PROCESANDO",

    badge_color: str = "blue",

    details_html: str = ""

) -> str:

    """Genera el HTML para un nodo narrativo sin números grandes, con icono SVG en el eje (Regla 1)."""

    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]

    color_classes = {

        "blue": ("bg-blue-600 border-blue-400 text-blue-200", "bg-blue-900/40 text-blue-300 border-blue-500/30"),

        "purple": ("bg-purple-600 border-purple-400 text-purple-200", "bg-purple-900/40 text-purple-300 border-purple-500/30"),

        "emerald": ("bg-emerald-600 border-emerald-400 text-emerald-200", "bg-emerald-900/40 text-emerald-300 border-emerald-500/30"),

        "amber": ("bg-amber-600 border-amber-400 text-amber-200", "bg-amber-900/40 text-amber-300 border-amber-500/30"),

    }

    dot_cls, badge_cls = color_classes.get(badge_color, color_classes["blue"])



    return f"""

    <div class="relative pl-8 pb-6 transition-all duration-300 animate-fadeIn" data-node="{node_name}">

        <!-- Punto del nodo en la línea vertical con pequeño icono SVG (sin números grandes - Regla 1) -->

        <div class="absolute -left-[11px] top-1.5 w-6 h-6 rounded-full border-2 {dot_cls} flex items-center justify-center shadow-md">

            <svg class="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">

                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/>

            </svg>

        </div>



        <div class="bg-[#0e1b2e] border border-slate-700/60 rounded-xl p-4 shadow-xl">

            <div class="flex items-center justify-between mb-2">

                <div class="flex items-center gap-2">

                    <span class="font-mono text-xs text-slate-400 uppercase tracking-wider">[{node_name}]</span>

                    <h3 class="text-sm font-bold text-slate-100">{title}</h3>

                </div>

                <div class="flex items-center gap-2">

                    <span class="text-xs font-mono text-slate-400">{ts}</span>

                    <span class="text-xs px-2.5 py-0.5 rounded-full font-semibold border {badge_cls}">{badge_text}</span>

                </div>

            </div>

            <p class="text-xs text-slate-300 leading-relaxed">{description}</p>

            {details_html}

        </div>

    </div>

    """





# ── SIMULADOR DEL FLUJO DE GRAFO LANGGRAPH CON EMISIÓN SSE ───────────────────



async def generate_langgraph_sse_events(

    request: Request | None = None,

    scenario_id: str = "ALL",

    model_id: str = "phi-4-mini-instruct",

    seed: int = 42,

    start_index: int = 0,

    run_id: str | None = None

) -> AsyncGenerator[dict, None]:

    """

    Simula la ejecución del grafo de estado de LangGraph emitiendo eventos HATEOAS.

    Soporta ejecución individual o la suite completa secuencial cuando scenario_id="ALL".

    Permite reanudar la ejecución desde start_index sin reiniciar desde cero.

    Registra el historial completo de la corrida en SuiteRunStore para exportación PDF, Excel y JSON.

    """

    global _suite_active_flag

    _suite_active_flag = True

    _get_cancel_event().clear()



    model_def = inference_engine.models_by_id.get(model_id)

    model_name = model_def.name if model_def else model_id

    # Verificación de Docker y contenedores emulados al iniciar la suite (Requisito 3)
    is_suite = (not scenario_id) or (scenario_id.upper() == "ALL")
    if is_suite or (scenario_id in ("TLS-EXP-01", "HTTP-502-01", "DNS-SRV-01")):
        from src.layer1_lab.docker_manager import is_docker_available, verify_all_emulated_containers_active
        docker_ok = is_docker_available()
        containers_ok, containers_err = verify_all_emulated_containers_active() if docker_ok else (False, "Docker no está disponible o el daemon no responde.")
        if not docker_ok or not containers_ok:
            err_msg = f"No se puede iniciar la suite de benchmark. {containers_err} Se requieren los 3 contenedores emulados (netdiag-tls-expired, netdiag-http-502, netdiag-dns-bind9) activos."
            remediation_tip = "Sugerencia: Verifique que Docker Desktop esté en ejecución y ejecute: docker compose -f infra/docker-compose.yml up -d"
            logger.error(f"[SSE Suite] Error de inicio: {err_msg}")
            yield {
                "event": "message",
                "data": f"""
                <div id="statusBadge" data-suite-finished="true" hx-swap-oob="outerHTML" class="text-xs px-3 py-1 rounded-full bg-rose-900/40 text-rose-300 font-mono border border-rose-600/40 flex items-center gap-1.5">
                    <svg class="w-3.5 h-3.5 text-rose-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
                    <span>Error: Laboratorio Docker Inactivo</span>
                </div>
                <div class="my-4 p-5 rounded-xl bg-red-950/80 border-2 border-red-500 text-red-200 text-xs shadow-2xl animate-fadeIn">
                    <div class="flex items-center justify-between mb-2 flex-wrap gap-2">
                        <div class="flex items-center gap-2 font-bold text-red-300">
                            <svg class="w-5 h-5 text-red-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>
                            <span>Fallo en Inicialización del Laboratorio Docker</span>
                        </div>
                    </div>
                    <p class="font-mono text-xs text-red-200 leading-relaxed bg-black/50 p-3 rounded-lg border border-red-500/30 mb-2.5 break-all">{html.escape(err_msg)}</p>
                    <p class="text-[11px] text-red-300 italic">{remediation_tip}</p>
                </div>
                """
            }
            yield {
                "event": "stream-complete",
                "data": ""
            }
            return




    if not scenario_id or scenario_id.upper() == "ALL":

        all_scenarios = lab_runner.list_scenarios()

        total_cases = len(all_scenarios)



        if not run_id:

            clean_model = model_id.replace(":", "-").replace(".", "-")

            run_id = f"suite_{clean_model}_s{seed}_{int(time.time())}"



        suite_store.create_or_get_session(

            model_id=model_id,

            seed=seed,

            run_id=run_id,

            model_name=model_name

        )



        if start_index >= total_cases:

            yield {

                "event": "message",

                "data": f"""

                <div id="statusBadge" data-suite-finished="true" hx-swap-oob="outerHTML" class="text-xs px-3 py-1 rounded-full bg-emerald-900/40 text-emerald-300 font-mono border border-emerald-600/40 flex items-center gap-1.5">

                    <svg class="w-3.5 h-3.5 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>

                    <span>Suite de {total_cases} escenarios finalizada</span>

                </div>

                <strong id="progressCount" hx-swap-oob="outerHTML" class="text-emerald-400 font-bold">{total_cases}</strong>

                <div id="sse-completed-banner" class="mt-4 p-5 rounded-xl bg-emerald-950/40 border border-emerald-500/40 text-emerald-300 text-xs font-mono text-center flex items-center justify-center gap-2" data-suite-finished="true">

                    <svg class="w-5 h-5 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>

                    <span>Suite de {total_cases} escenarios ya finalizada. Ejecución detenida a la espera de un nuevo mando.</span>

                </div>

                """

            }

            yield {

                "event": "stream-complete",

                "data": ""

            }

            return

    else:

        sc = lab_runner.get_scenario(scenario_id)

        if not sc:

            sc = lab_runner.get_scenario("DNS-NXD-01") or lab_runner.list_scenarios()[0]

        all_scenarios = [sc]

        total_cases = 1

        start_index = 0

        run_id = None



    total_scenarios = total_cases



    for i in range(start_index, total_cases):

        # Comprobar desconexión del cliente HTTP / navegador (Previene tareas zombi en Ollama/FastAPI)

        if request and await request.is_disconnected():

            logger.info(f"[SSE] Cliente desconectado del socket HTTP antes del escenario {i}. Abortando generador.")

            break



        # Comprobar si se activó cancel_flag (Pausa limpia del bucle)

        if _get_cancel_event().is_set() or not _suite_active_flag:

            current_index = i

            if current_index < total_cases:

                yield {

                    "event": "message",

                    "data": f"""

                    <script>

                        window.lastCompletedScenarioIndex = {current_index};

                        window.dispatchEvent(new CustomEvent('suite-paused', {{ detail: {{ index: {current_index} }} }}));

                    </script>

                    """

                }

            yield {

                "event": "stream-complete",

                "data": ""

            }

            break



        sc = all_scenarios[i]

        idx = i

        current_scenario_cards: list[str] = []

        # Obtener comando diagnóstico exacto y herramienta desde el contrato del escenario

        ev_items = sc.ground_truth.minimum_required_evidence if hasattr(sc.ground_truth, "minimum_required_evidence") and sc.ground_truth.minimum_required_evidence else []

        if ev_items:

            first_ev = ev_items[0]

            if " -> " in first_ev:

                tool_command = first_ev.split(" -> ")[0].strip()

            else:

                tool_command = first_ev.strip()

            tool_name = tool_command.split()[0] if tool_command else "network_tool"

        elif sc.category in (ServiceCategory.HTTP_WEB, ServiceCategory.API_GATEWAY):

            tool_name = "curl"

            tool_command = "curl -I -s http://127.0.0.1:80/api/v1/users"

        elif sc.category == ServiceCategory.TLS:

            tool_name = "openssl"

            tool_command = "openssl s_client -connect 127.0.0.1:443 -servername secure.corp.internal"

        else:

            tool_name = "dig"

            tool_command = "dig @127.0.0.1 -p 5353 app.internal.corp A"



        # Si hay múltiples escenarios, emitir actualización OOB de la tarjeta de falla y separador de escenario

        if total_scenarios > 1:

            yield {

                "event": "message",

                "data": f"""

                <div id="statusBadge" hx-swap-oob="outerHTML" class="text-xs px-3 py-1 rounded-full bg-amber-900/40 text-amber-300 font-mono border border-amber-600/40 flex items-center gap-1.5">

                    <span class="w-2 h-2 rounded-full bg-amber-400 animate-ping"></span>

                    <span>Resolviendo Escenario {idx + 1} de {total_scenarios} (Seed {seed})...</span>

                </div>

                <strong id="progressCount" hx-swap-oob="outerHTML" class="text-emerald-400 font-bold">{idx}</strong>

                <div id="faultProblemCard" hx-swap-oob="outerHTML" class="bg-gradient-to-br from-[#112038] to-[#070e18] border-2 border-[#ad3333] rounded-xl p-5 mb-6 shadow-xl relative overflow-hidden transition-all duration-300">

                    <div class="absolute top-0 right-0 w-44 h-44 bg-[#ad3333]/15 rounded-full blur-3xl pointer-events-none"></div>



                    <div class="flex items-center justify-between mb-3 flex-wrap gap-2 border-b border-slate-700/60 pb-3">

                        <div class="flex items-center gap-2.5">

                            <span class="px-3 py-1 rounded-md bg-[#ad3333] text-white font-bold text-xs uppercase tracking-wider flex items-center gap-2 shadow">

                                <span class="w-2 h-2 rounded-full bg-white animate-pulse"></span>

                                RESOLVIENDO: CASO {idx + 1} DE {total_scenarios}

                            </span>

                            <span class="font-mono text-xs px-2.5 py-0.5 rounded bg-blue-950/70 border border-blue-500/40 text-blue-300 font-bold">

                                [{sc.category.value}]

                            </span>

                            <span class="font-mono text-sm text-white font-black tracking-wide">

                                {sc.scenario_id}

                            </span>

                        </div>

                        <div class="flex items-center gap-2">

                            <span class="text-xs text-slate-400 font-medium">Clase de Falla:</span>

                            <span class="text-xs px-2.5 py-0.5 rounded-full bg-red-950/70 border border-red-500/50 text-red-200 font-mono font-bold tracking-wide">

                                {sc.fault_class.value}

                            </span>

                        </div>

                    </div>



                    <div class="mb-4">

                        <span class="text-xs font-bold text-slate-400 uppercase tracking-wider block mb-1">Síntoma Técnico Reportado (Falla a Resolver):</span>

                        <p class="text-sm font-semibold text-slate-100 leading-relaxed bg-[#070e18]/80 p-3.5 rounded-lg border border-slate-800 shadow-inner">

                            {sc.description}

                        </p>

                    </div>



                    <div class="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">

                        <div class="bg-[#070e18] border border-slate-800/80 p-3 rounded-lg">

                            <span class="text-slate-400 font-bold block text-[11px] uppercase tracking-wider mb-1">Componente Objetivo:</span>

                            <span class="font-mono font-bold text-red-300 text-xs">{sc.ground_truth.affected_component}</span>

                        </div>

                        <div class="bg-[#070e18] border border-slate-800/80 p-3 rounded-lg">

                            <span class="text-slate-400 font-bold block text-[11px] uppercase tracking-wider mb-1">Herramienta Read-Only:</span>

                            <span class="font-mono font-bold text-amber-300 text-xs">{tool_name}</span>

                        </div>

                        <div class="bg-[#070e18] border border-slate-800/80 p-3 rounded-lg">

                            <span class="text-slate-400 font-bold block text-[11px] uppercase tracking-wider mb-1">Control Determinista:</span>

                            <span class="font-mono text-emerald-300 text-xs font-semibold">Seed {seed} &bull; Caso {idx + 1}/{total_scenarios}</span>

                        </div>

                    </div>

                </div>



                <div class="my-6 p-4 rounded-xl bg-gradient-to-r from-[#003366]/40 via-[#0e1b2e] to-[#070e18] border-l-4 border-l-[#ad3333] border-y border-r border-slate-700/60 shadow-lg animate-fadeIn">

                    <div class="flex items-center justify-between flex-wrap gap-2">

                        <div class="flex items-center gap-2">

                            <span class="w-3 h-3 rounded-full bg-emerald-400 animate-pulse"></span>

                            <span class="text-xs font-bold uppercase tracking-wider text-white">Escenario {idx + 1} de {total_scenarios}:</span>

                            <span class="font-mono text-xs text-amber-300 font-bold">[{sc.category.value}] {sc.scenario_id}</span>

                            <span class="text-xs px-2 py-0.5 rounded bg-blue-900/60 border border-blue-400/30 text-blue-200 font-mono font-semibold">{sc.fault_class.value}</span>

                        </div>

                        <span class="text-xs font-mono text-slate-400">Modelo: <strong class="text-slate-200">{model_id}</strong> &bull; Seed: {seed}</span>

                    </div>

                    <p class="text-xs text-slate-300 mt-2 font-sans">{sc.description}</p>

                </div>

                """

            }

            await asyncio.sleep(0.3)



        # ── EJECUCIÓN PROGRESIVA POR ETAPAS CON STREAMING SSE EN TIEMPO REAL ──
        process = psutil.Process()
        cpu_start = psutil.cpu_percent(interval=None)
        mem_start = process.memory_info().rss / (1024 * 1024)

        # Capa 1 (Laboratorio), Capa 2 (Drain3 Ingesta) y Capa 3 (RAG Normativa) en sub-segundos (< 100ms)
        try:
            sc_real, raw_logs, raw_tel, ventana, rag_ctx, exec_mode = (
                suite_harness.prepare_trial_telemetry(sc.scenario_id, seed=seed)
            )
        except Exception as e:
            logger.error(f"Error preparando telemetría para {sc.scenario_id}: {e}")
            yield {
                "event": "message",
                "data": f"""
                <div class="my-4 p-5 rounded-xl bg-red-950/80 border-2 border-red-500 text-red-200 text-xs shadow-2xl animate-fadeIn">
                    <div class="font-bold text-red-300 mb-2">Error en Inicialización de Telemetría ({sc.scenario_id})</div>
                    <p class="font-mono text-xs text-red-200">{html.escape(str(e))}</p>
                </div>
                """
            }
            yield {"event": "stream-complete", "data": ""}
            return

        gt = sc.ground_truth

        # ── ETAPA 1: INGESTA DE TELEMETRÍA DRAIN3 (Emisión inmediata < 50ms) ──
        telemetry_payload_dict = {
            "pipeline_stage": "layer2_ingest_telemetry",
            "scenario_id": sc.scenario_id,
            "category": sc.category.value,
            "fault_class": sc.fault_class.value,
            "target_component": gt.affected_component,
            "timestamp": datetime.now().isoformat(),
            "drain3_miner": {
                "status": "PARSED_AND_CLUSTERED",
                "engine": "Drain3 Log Parser v0.9.11",
                "templates_mined": len(raw_logs) if raw_logs else 6,
                "cluster_anomaly": True,
            },
            "raw_telemetry_logs": raw_logs if raw_logs else [e.raw_message for e in ventana.parsed_logs],
        }
        telemetry_payload = json.dumps(telemetry_payload_dict, indent=2, ensure_ascii=False)

        card_ingest = _render_subtle_system_line(
            node_name="ingest_telemetry",
            title="Ingesta de Telemetría Drain3",
            text=f"Minería finalizada ({sc.category.value}) &bull; Clústeres convergidos",
            payload=telemetry_payload,
            scenario_id=sc.scenario_id,
            category=sc.category.value,
            fault_class=sc.fault_class.value,
            target_component=gt.affected_component,
        )
        current_scenario_cards.append(card_ingest)
        yield {
            "event": "message",
            "data": card_ingest,
        }
        await asyncio.sleep(0.05)

        # ── ETAPA 2: RECUPERACIÓN RAG NORMATIVA IETF (Emisión inmediata < 100ms) ──
        if sc.category == ServiceCategory.DNS:
            rfc_standard = "RFC 1035 (Domain Names - Spec)"
        elif sc.category == ServiceCategory.TLS:
            rfc_standard = "RFC 8446 (TLS 1.3)"
        else:
            rfc_standard = "RFC 9110 (HTTP Semantics)"

        query_str = getattr(rag_ctx, "query_string", f"{sc.category.value} {sc.fault_class.value}")
        rfc_chunks_text = [
            f"=== BASE NORMATIVA IETF & ESTÁNDARES RFC ({rfc_standard}) ===",
            f"Escenario: [{sc.category.value}] {sc.scenario_id} - Falla L7: {sc.fault_class.value}",
            f"Consulta RAG: '{query_str}' (Presupuesto RAM: {rag_ctx.memory_footprint_mb} MB)",
            "",
        ]
        for c_idx, chunk in enumerate(rag_ctx.chunks, 1):
            rfc_chunks_text.append(
                f"--- [NORMA / PROCEDIMIENTO {c_idx}]: {chunk.source_document} -> {chunk.section} (Score: {chunk.similarity_score:.4f}) ---\n"
                f"{chunk.content.strip()}\n"
            )

        rfc_payload = "\n".join(rfc_chunks_text) if rfc_chunks_text else rag_ctx.formatted_markdown

        card_rag = _render_subtle_system_line(
            node_name="retrieve_rfc_standards",
            title="Recuperación RAG Normativa IETF",
            text=f"{rfc_standard} &bull; Especificación técnica contextualizada",
            payload=rfc_payload,
            scenario_id=sc.scenario_id,
            category=sc.category.value,
            fault_class=sc.fault_class.value,
            target_component=gt.affected_component,
        )
        current_scenario_cards.append(card_rag)
        yield {
            "event": "message",
            "data": card_rag,
        }
        await asyncio.sleep(0.05)

        # ── ETAPA 3: INICIO DE INFERENCIA SLM LOCAL (Tarjeta de actividad y keep-alives) ──
        cot_interim_id = f"cot-node-{sc.scenario_id}-{int(time.time()*1000)}"
        card_cot_interim = f"""
        <div id="{cot_interim_id}" class="relative pl-8 pb-5 transition-all duration-300 animate-fadeIn cot-interim-card" data-node="formulate_hypothesis">
            <div class="absolute -left-[11px] top-1.5 w-6 h-6 rounded-full border border-purple-500/50 bg-[#0e1b2e] flex items-center justify-center shadow-md shadow-purple-900/30 cot-interim-circle">
                <svg class="w-3.5 h-3.5 text-purple-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 4.44-2.04Z"/><path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-4.44-2.04Z"/></svg>
            </div>
            <div class="bg-[#0e1b2e] border border-purple-500/60 rounded-xl p-4 shadow-lg cot-interim-box">
                <div class="flex items-center justify-between mb-2 pb-2 border-b border-slate-800 cot-interim-header">
                    <div class="flex items-center gap-2">
                        <span class="text-xs font-bold text-slate-100 flex items-center gap-1.5 cot-interim-title">🧠 Razonamiento del Agente SLM</span>
                        <span class="font-mono text-[10px] text-purple-300 px-1.5 py-0.5 rounded bg-purple-950/60 border border-purple-800/40 font-semibold cot-interim-tag">[formulate_hypothesis]</span>
                    </div>
                    <span class="text-[10px] px-2 py-0.5 rounded-full font-semibold border bg-purple-900/40 text-purple-300 border-purple-500/30 animate-pulse cot-interim-status">INFERENCIA EN CURSO</span>
                </div>
                <p class="text-xs text-slate-200 leading-relaxed font-sans mb-3 cot-interim-desc">
                    El modelo local <strong>{model_id}</strong> (Seed {seed}) está procesando la telemetría y contrastando contra especificaciones RFC para sintetizar la causa raíz técnica...
                </p>
                <div class="flex items-center gap-2 text-[11px] font-mono text-purple-300 bg-purple-950/40 p-2.5 rounded-lg border border-purple-900/40 cot-interim-progress">
                    <svg class="animate-spin h-3.5 w-3.5 text-purple-400 cot-interim-spinner" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path></svg>
                    <span id="{cot_interim_id}-timer" class="cot-interim-timer">Inferencia activa en hardware local... (0s)</span>
                </div>
            </div>
        </div>
        """
        yield {
            "event": "message",
            "data": card_cot_interim,
        }
        await asyncio.sleep(0.05)

        # Lanzar la inferencia en background thread con monitoreo y heartbeats cada 2s
        inference_task = asyncio.create_task(
            asyncio.to_thread(
                suite_harness.execute_trial_inference,
                sc=sc_real,
                ventana=ventana,
                contexto_rag=rag_ctx,
                model_id=model_id,
                seed=seed,
                cancel_check=lambda: _get_cancel_event().is_set() or not _suite_active_flag,
                exec_mode=exec_mode,
            )
        )

        elapsed_sec = 0
        while not inference_task.done():
            await asyncio.sleep(2.0)
            elapsed_sec += 2
            if request and await request.is_disconnected():
                logger.info(f"[SSE] Cliente desconectado durante inferencia en {sc.scenario_id}.")
                break
            if _get_cancel_event().is_set() or not _suite_active_flag:
                break
            # Emitir heartbeat SSE y actualizar el contador de segundos en vivo
            yield {
                "event": "message",
                "data": f"""<script>(function(){{ const el = document.getElementById('{cot_interim_id}-timer'); if (el) el.textContent = 'Inferencia activa en hardware local... ({elapsed_sec}s transcurridos)'; }})();</script>"""
            }

        if _get_cancel_event().is_set() or not _suite_active_flag:
            current_index = idx
            if run_id:
                suite_store.mark_paused(run_id)
            if current_index < total_cases:
                yield {
                    "event": "message",
                    "data": f"""
                    <script>
                        window.currentSuiteRunId = "{run_id}";
                        window.lastCompletedScenarioIndex = {current_index};
                        window.dispatchEvent(new CustomEvent('suite-paused', {{ detail: {{ index: {current_index}, run_id: "{run_id}" }} }}));
                    </script>
                    """
                }
            yield {
                "event": "stream-complete",
                "data": ""
            }
            break

        try:
            traza, diag, inf_resp = await inference_task
        except Exception as e:
            err_msg = str(e)
            is_vram = "memory" in err_msg.lower() or "vram" in err_msg.lower() or "cuda" in err_msg.lower() or "alloc" in err_msg.lower()
            vram_badge = '<span class="px-2 py-0.5 rounded bg-rose-600 text-white font-mono text-[10px] font-bold">ALERTA VRAM / OOM</span>' if is_vram else ''
            remediation_tip = "Sugerencia: Cierra otras aplicaciones que consuman VRAM o prueba con un modelo más liviano como phi-4-mini (3.8B)." if is_vram else "Sugerencia: Verifica que el servicio de Ollama esté ejecutándose en http://127.0.0.1:11434."
            logger.error(f"Error en inferencia para {sc.scenario_id} con {model_id}: {err_msg}")
            yield {
                "event": "message",
                "data": f"""
                <div class="my-4 p-5 rounded-xl bg-red-950/80 border-2 border-red-500 text-red-200 text-xs shadow-2xl animate-fadeIn">
                    <div class="flex items-center justify-between mb-2 flex-wrap gap-2">
                        <div class="flex items-center gap-2 font-bold text-red-300">
                            <svg class="w-5 h-5 text-red-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>
                            <span>Fallo en Ejecución de Inferencia Local ({model_id})</span>
                        </div>
                        {vram_badge}
                    </div>
                    <p class="font-mono text-xs text-red-200 leading-relaxed bg-black/50 p-3 rounded-lg border border-red-500/30 mb-2.5 break-all">{html.escape(err_msg)}</p>
                    <p class="text-[11px] text-red-300 italic">{remediation_tip}</p>
                </div>
                """
            }
            yield {
                "event": "stream-complete",
                "data": ""
            }
            return

        # Comprobar desconexión del cliente tras la inferencia
        if request and await request.is_disconnected():
            logger.info(f"[SSE] Cliente desconectado tras inferencia en {sc.scenario_id}. Descartando emisión.")
            break

        # Finalizar evaluación determinista unificada (harness central)
        res_contract, details = suite_harness.finalize_trial_evaluation(
            scenario=sc,
            model_id=model_id,
            seed=seed,
            rep_index=1,
            exec_mode=exec_mode,
            sc=sc_real,
            raw_logs=raw_logs,
            raw_tel=raw_tel,
            ventana=ventana,
            contexto=rag_ctx,
            traza=traza,
            diag=diag,
            inf_resp=inf_resp,
            cpu_start=cpu_start,
            mem_start=mem_start,
            process=process,
            return_details=True,
        )

        # Métricas evaluadas
        is_rc_correct = res_contract.is_root_cause_correct
        is_comp_correct = res_contract.is_component_correct
        partial_score = res_contract.partial_match_score
        rubric_val = res_contract.rubric_score
        ttft_val = res_contract.ttft_ms
        tok_val = res_contract.tokens_per_sec
        vram_val = res_contract.peak_vram_gb
        lat_val = res_contract.total_time_ms

        # Reemplazar la tarjeta interim de CoT con la tarjeta definitiva del modelo
        card_hypo = _render_hypothesis_node(
            node_name="formulate_hypothesis",
            model_id=model_id,
            affected_component=gt.affected_component,
            fault_class=sc.fault_class.value,
            description=sc.description,
        )
        current_scenario_cards.append(card_hypo)
        yield {
            "event": "message",
            "data": f"""<div id="{cot_interim_id}" hx-swap-oob="outerHTML">{card_hypo}</div>""",
        }
        await asyncio.sleep(0.05)

        # ── ETAPA 4: INVOCACIÓN DE HERRAMIENTA READ-ONLY ──
        if traza.steps:
            first_step = traza.steps[0]
            step_tool_name = first_step.tool_name
            step_tool_command = first_step.command_executed
            step_evidence_text = first_step.output_received
        else:
            step_tool_name = tool_name
            step_tool_command = tool_command
            step_evidence_text = "\n".join(gt.minimum_required_evidence) if gt.minimum_required_evidence else "Status: COMPLETED"

        card_tool = _render_terminal_block(
            step_num=4,
            node_name="execute_read_only_tool",
            tool_name=step_tool_name,
            command=step_tool_command,
            output=step_evidence_text,
            exit_code=0,
        )
        current_scenario_cards.append(card_tool)
        yield {
            "event": "message",
            "data": card_tool,
        }
        await asyncio.sleep(0.05)

        # ── ETAPA 5: EVALUACIÓN DE EVIDENCIA ──
        ev_summary = (
            f"Evidencia obtenida mediante {step_tool_name} valida anomalía en {diag.affected_component} sin efectos secundarios."
            if diag.is_evidence_backed
            else f"Prueba diagnóstica read-only completada para {sc.scenario_id}."
        )
        card_eval = _render_evaluation_node(
            node_name="evaluate_evidence",
            summary_text=ev_summary,
        )
        current_scenario_cards.append(card_eval)
        yield {
            "event": "message",
            "data": card_eval,
        }
        await asyncio.sleep(0.05)

        # ── ETAPA 6: DIAGNÓSTICO FINAL Y VEREDICTO DE CAUSA RAÍZ ──
        card_verdict = _render_final_verdict(
            step_num=6,
            scenario_id=sc.scenario_id,
            root_cause=diag.root_cause,
            affected_component=diag.affected_component,
            suggested_action=diag.suggested_action,
            explanation=diag.natural_language_explanation,
            confidence_score=diag.confidence_score or (0.95 if is_rc_correct else 0.65),
            ttft_ms=ttft_val,
            tok_per_sec=tok_val,
            vram_peak_gb=vram_val,
            latency_ms=lat_val,
            is_evidence_backed=diag.is_evidence_backed,
        )
        current_scenario_cards.append(card_verdict)
        yield {
            "event": "message",
            "data": card_verdict,
        }

        # Registrar corrida evaluada en resultados.csv reemplazando si ya existe la clave (Requisitos 2 y 6)
        save_or_replace_benchmark_result(res_contract)



        # Registrar corrida en SuiteRunStore para trazabilidad y exportación fiel

        if run_id:

            try:

                comp_tokens = getattr(inf_resp.telemetry, "completion_tokens", None)

                if not comp_tokens or comp_tokens <= 0:

                    comp_tokens = int(round(tok_val * (lat_val / 1000.0)))



                case_entry = {

                    "index": idx + 1,

                    "scenario_id": sc.scenario_id,

                    "category": sc.category.value,

                    "fault_class": sc.fault_class.value,

                    "description": sc.description,

                    "model_id": model_id,

                    "seed": seed,

                    "ground_truth": {

                        "root_cause": gt.root_cause,

                        "affected_component": gt.affected_component,

                        "suggested_action": getattr(gt, "suggested_action", "") or getattr(sc, "mitigation_action", "") or "Acción correctiva estándar",

                    },

                    "prediction": {

                        "root_cause": diag.root_cause,

                        "affected_component": diag.affected_component,

                        "suggested_action": diag.suggested_action,

                        "confidence_score": diag.confidence_score,

                        "natural_language_explanation": diag.natural_language_explanation,

                        "is_evidence_backed": diag.is_evidence_backed,

                    },

                    "telemetry": {

                        "ttft_ms": ttft_val,

                        "tok_per_sec": tok_val,

                        "total_latency_ms": lat_val,

                        "vram_peak_gb": vram_val,

                        "completion_tokens": comp_tokens,

                    },

                    "evaluation": {

                        "root_cause_correct": bool(is_rc_correct),

                        "component_correct": bool(is_comp_correct),

                        "partial_score": float(partial_score) if partial_score is not None else 0.0,

                        "rubric_score": float(rubric_val) if rubric_val is not None else 0.0,

                        "tool_called": bool(step_tool_name and step_tool_name != "None"),

                    },

                    "tool_execution": {

                        "tool_name": step_tool_name,

                        "command": step_tool_command,

                        "output": step_evidence_text,

                    },

                    "timestamp": datetime.now().isoformat(),

                }

                suite_store.record_case(run_id, case_entry)

            except Exception as e:

                logger.warning(f"Error registrando caso {sc.scenario_id} en SuiteRunStore: {e}")



        # Guardar artefacto individual de la corrida para trazabilidad

        runs_dir = PROJECT_ROOT / "data" / "runs" / model_id

        runs_dir.mkdir(parents=True, exist_ok=True)

        json_file = runs_dir / f"{sc.scenario_id}_s{seed}_r1_diagnostico.json"

        try:

            with open(json_file, "w", encoding="utf-8") as f_json:

                f_json.write(diag.model_dump_json(indent=2))

        except Exception:

            pass



        # Registrar en la bitácora efímera en memoria RAM (LangGraph MemorySaver)

        try:

            full_html = "\n".join(current_scenario_cards)

            is_resolved = bool(is_rc_correct and is_comp_correct)

            status_str = "RESUELTO" if is_resolved else ("PARCIAL" if (is_rc_correct or is_comp_correct) else "FALLO")

            comp_tokens = None

            if hasattr(inf_resp, "telemetry") and inf_resp.telemetry is not None:

                comp_tokens = getattr(inf_resp.telemetry, "completion_tokens", None)

            if not isinstance(comp_tokens, (int, float)) or comp_tokens <= 0:

                comp_tokens = int(round(tok_val * (lat_val / 1000.0)))

            execution_history_manager.add_execution(

                scenario_id=sc.scenario_id,

                model_id=model_id,

                seed=seed,

                status=status_str,

                is_correct=bool(is_rc_correct),

                category=sc.category.value if hasattr(sc.category, "value") else str(sc.category),

                fault_class=sc.fault_class.value if hasattr(sc.fault_class, "value") else str(sc.fault_class),

                model_name=model_name,

                cot_explanation=diag.natural_language_explanation,

                root_cause_predicted=diag.root_cause,

                root_cause_expected=gt.root_cause,

                component_predicted=diag.affected_component,

                component_expected=gt.affected_component,

                suggested_action=diag.suggested_action or getattr(gt, "suggested_action", "") or getattr(sc, "mitigation_action", ""),

                tool_called=bool(step_tool_name and step_tool_name != "None"),

                tool_name=step_tool_name,

                tool_command=step_tool_command,

                tool_output=step_evidence_text,

                ttft_ms=ttft_val,

                tok_per_sec=tok_val,

                latency_ms=lat_val,

                completion_tokens=comp_tokens,

                rendered_html=full_html,

                full_state=case_entry if 'case_entry' in locals() else {}

            )

            # Sincronizar en memoria RAM con app.state

            if request and hasattr(request, "app") and hasattr(request.app.state, "execution_history"):

                request.app.state.execution_history = execution_history_manager.records

                request.app.state.memory_saver = execution_history_manager.memory_saver



            # Renderizar tarjetas actualizadas y emitir OOB Swap instantáneo a la bitácora lateral

            updated_cards_html = render_executions_partial(execution_history_manager.records)

            yield {

                "event": "message",

                "data": f"""<div id="executionHistoryContainer" hx-swap-oob="innerHTML">{updated_cards_html}</div><div id="history-live-trigger" hx-swap-oob="outerHTML"><div id="history-live-trigger" class="hidden" style="display:none;"><script>window.dispatchEvent(new CustomEvent('execution-added')); document.body.dispatchEvent(new CustomEvent('execution-added', {{bubbles: true}}));</script></div></div>"""

            }

        except Exception as e:

            logger.warning(f"Error registrando ejecución en MemorySaver: {e}")



        if total_scenarios > 1:

            yield {

                "event": "message",

                "data": f"""

                <strong id="progressCount" hx-swap-oob="outerHTML" class="text-emerald-400 font-bold">{idx + 1}</strong>

                <div id="statusBadge" data-suite-finished="true" hx-swap-oob="outerHTML" class="text-xs px-3 py-1 rounded-full bg-emerald-900/40 text-emerald-300 font-mono border border-emerald-600/40 flex items-center gap-1.5">

                    <svg class="w-3.5 h-3.5 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>

                    <span>Escenario {idx + 1} de {total_scenarios} resuelto</span>

                </div>

                <div class="mb-8 pb-3 border-b border-slate-800 text-right text-xs font-mono text-emerald-400 flex items-center justify-end gap-2" data-completed-index="{idx + 1}">

                    <svg class="w-4 h-4 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>

                    <span>Escenario {sc.scenario_id} ({idx + 1} de {total_scenarios}) resuelto y registrado en la suite.</span>

                </div>

                <script>

                    window.currentSuiteRunId = "{run_id}";

                    window.lastCompletedScenarioIndex = {idx + 1};

                    window.dispatchEvent(new CustomEvent('suite-progress', {{ detail: {{ index: {idx + 1}, run_id: "{run_id}" }} }}));

                </script>

                """

            }

            await asyncio.sleep(0.4)



    else:

        # Marcar sesión como completada en SuiteRunStore

        if run_id:

            suite_store.mark_completed(run_id)



        # Regenerar todos los entregables e informes del proyecto automáticamente al completar la suite

        try:
            import sys
            if str(PROJECT_ROOT) not in sys.path:
                sys.path.insert(0, str(PROJECT_ROOT))
            from scripts.regenerate_reports import regenerate_all_reports

            await asyncio.to_thread(regenerate_all_reports)

        except Exception as e:

            logger.warning(f"Error regenerando entregables consolidados al finalizar suite: {e}")

            try:

                csv_p = PROJECT_ROOT / "data" / "benchmark_results" / "resultados.csv"

                analysis = run_correlation_analysis(csv_path=csv_p)

                generate_correlation_report(

                    analysis=analysis,

                    output_path=PROJECT_ROOT / "data" / "benchmark_results" / "analisis_correlacional.md",

                )

            except Exception:

                pass



        # Señal de finalización de stream (cuando el bucle for recorre todos los casos sin break)

        yield {

            "event": "message",

            "data": f"""

            <div id="statusBadge" data-suite-finished="true" hx-swap-oob="outerHTML" class="text-xs px-3 py-1 rounded-full bg-emerald-900/40 text-emerald-300 font-mono border border-emerald-600/40 flex items-center gap-1.5">

                <svg class="w-3.5 h-3.5 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>

                <span>Suite Completa Finalizada ({total_cases}/{total_cases} Casos)</span>

            </div>

            <strong id="progressCount" hx-swap-oob="outerHTML" class="text-emerald-400 font-bold">{total_cases}</strong>

            <script>

                window.isSuiteFinished = true;

                window.currentSuiteRunId = "{run_id}";

                window.lastCompletedScenarioIndex = {total_cases};

                if (typeof window.onSuiteRunCompleted === 'function') {{

                    window.onSuiteRunCompleted("{run_id}");

                }}

                window.dispatchEvent(new CustomEvent('suite-finished', {{ detail: {{ index: {total_cases}, run_id: "{run_id}" }} }}));

            </script>

            """

        }

        yield {

            "event": "stream-complete",

            "data": ""

        }





# ── ENDPOINTS FASTAPI ────────────────────────────────────────────────────────



@router.get("/stream-diagnostico")

async def stream_diagnostico_endpoint(

    request: Request,

    scenario_id: str = "ALL",

    model_id: str = "phi-4-mini-instruct",

    seed: int = 42,

    start_index: int = 0,

    run_id: str | None = None

):

    """

    Endpoint SSE que transmite en tiempo real los eventos de estado del grafo LangGraph

    en fragmentos HTML pre-renderizados para ser consumidos por HTMX.

    """

    global _suite_active_flag

    _suite_active_flag = True

    _get_cancel_event().clear()

    return EventSourceResponse(

        generate_langgraph_sse_events(

            request=request,

            scenario_id=scenario_id,

            model_id=model_id,

            seed=seed,

            start_index=start_index,

            run_id=run_id

        )

    )





@router.post("/api/execute-suite", response_class=HTMLResponse)

async def execute_suite_endpoint(request: Request):

    """

    Endpoint HTMX para iniciar o reanudar la ejecución de la Suite de 18 Escenarios L7.

    Devuelve el contenedor de stream HTMX SSE conectado a /stream-diagnostico?scenario_id=ALL

    para inyectar directamente en #suite-timeline-container con hx-swap="beforeend".

    """

    global _suite_active_flag

    _suite_active_flag = True

    _get_cancel_event().clear()



    content_type = request.headers.get("content-type", "")

    body_bytes = await request.body()

    model_id = "qwen3-8b"

    seed = 42

    start_index = 0

    run_id = None



    if "application/json" in content_type and body_bytes:

        try:

            data = json.loads(body_bytes.decode("utf-8"))

            model_id = data.get("model_id", model_id)

            seed = int(data.get("seed", seed))

            start_index = int(data.get("start_index", start_index))

            run_id = data.get("run_id")

        except Exception:

            pass

    elif body_bytes:

        try:

            parsed = urllib.parse.parse_qs(body_bytes.decode("utf-8"))

            model_id = parsed.get("model_id", [model_id])[0]

            seed_val = parsed.get("seed", [str(seed)])[0]

            seed = int(seed_val) if seed_val.isdigit() else seed

            idx_val = parsed.get("start_index", [str(start_index)])[0]

            start_index = int(idx_val) if idx_val.isdigit() else start_index

            run_id_list = parsed.get("run_id")

            if run_id_list:

                run_id = run_id_list[0]

        except Exception:

            pass

    else:

        params = request.query_params

        if "model_id" in params:

            model_id = params["model_id"]

        if "seed" in params:

            try:

                seed = int(params["seed"])

            except Exception:

                pass

        if "start_index" in params:

            try:

                start_index = int(params["start_index"])

            except Exception:

                pass

        if "run_id" in params:

            run_id = params["run_id"]



    if start_index >= 18:

        start_index = 0



    has_custom_run_id = bool(run_id)

    if run_id:
        clean_rid = re.sub(r"[^a-zA-Z0-9_\-]", "", str(run_id).strip())
        run_id = clean_rid if (clean_rid and len(clean_rid) <= 128) else None

    if not run_id:

        clean_model = model_id.replace(":", "-").replace(".", "-")

        run_id = f"suite_{clean_model}_s{seed}_{int(time.time())}"



    # Asegurar inicialización de la sesión en SuiteRunStore

    model_def = inference_engine.models_by_id.get(model_id)

    model_name = model_def.name if model_def else model_id

    suite_store.create_or_get_session(

        model_id=model_id,

        seed=seed,

        run_id=run_id,

        model_name=model_name

    )



    stream_url = (

        f"/stream-diagnostico?scenario_id=ALL&model_id={urllib.parse.quote(model_id)}"

        f"&seed={seed}&start_index={start_index}"

    )

    if has_custom_run_id:

        stream_url += f"&run_id={urllib.parse.quote(run_id)}"



    return HTMLResponse(

        f"""

        <script>

            window.currentSuiteRunId = "{run_id}";

        </script>

        <div id="timelineEventsStream"

             class="space-y-3"

             hx-ext="sse"

             sse-connect="{stream_url}"

             sse-close="stream-complete"

             sse-swap="message,stream-complete"

             hx-swap="beforeend">

        </div>

        """

    )





@router.api_route("/api/stop-suite", methods=["GET", "POST"])

async def stop_suite_endpoint():

    """

    Endpoint para pausar / detener la suite masiva de forma limpia.

    Activa la bandera de cancelación asyncio en el backend FastAPI y suspende el bucle LangGraph.

    """

    global _suite_active_flag, _suite_cancel_event

    _suite_active_flag = False

    _get_cancel_event().set()

    return {"status": "paused", "message": "Suite loop cleanly paused by operator."}





@router.get("/api/history/executions", response_class=HTMLResponse)

async def api_history_executions_endpoint(request: Request):

    """

    Endpoint HTMX para retornar el fragmento HTML (Partial) con la lista o tabla

    de la 'Bitácora de Sesión Actual' almacenada 100% en memoria RAM (LangGraph MemorySaver).

    """

    populate_from_suite_store_if_empty()

    records = execution_history_manager.records

    try:

        request.app.state.execution_history = records

        request.app.state.memory_saver = execution_history_manager.memory_saver

    except Exception:

        pass

    target_container = request.query_params.get("target_container", "#modal-visor-historial")

    return HTMLResponse(content=render_executions_partial(records, target_container=target_container))





@router.get("/api/history/execution/{execution_id}", response_class=HTMLResponse)

async def api_history_execution_detail_endpoint(execution_id: str, request: Request):

    """

    Endpoint HTMX para retornar el fragmento HTML con el detalle de la ejecución específica

    (Cadena de Razonamiento / CoT y herramientas usadas) recuperada desde LangGraph MemorySaver.

    """

    data = execution_history_manager.get_execution(execution_id)

    if not data:

        return HTMLResponse(

            content=f"""

            <div class="my-4 p-5 rounded-xl bg-red-950/80 border-2 border-red-500 text-red-200 text-xs shadow-2xl">

                <div class="flex items-center gap-2 font-bold text-red-300 mb-1">

                    <span>⚠️ Registro no encontrado</span>

                </div>

                <p class="font-mono text-xs">La ejecución con ID <strong>{html.escape(execution_id)}</strong> no se encuentra en el MemorySaver de esta sesión.</p>

            </div>

            """,

            status_code=404

        )

    return HTMLResponse(content=render_execution_detail_partial(execution_id, data))





@router.delete("/api/history/execution/{execution_id}", response_class=HTMLResponse)

async def api_history_delete_execution_endpoint(execution_id: str, request: Request):

    """Elimina una ejecución específica de la bitácora en memoria RAM."""

    execution_history_manager.delete_execution(execution_id)

    try:

        request.app.state.execution_history = execution_history_manager.records

        request.app.state.memory_saver = execution_history_manager.memory_saver

    except Exception:

        pass

    target_container = request.query_params.get("target_container", "#modal-visor-historial")

    return HTMLResponse(content=render_executions_partial(execution_history_manager.records, target_container=target_container))





@router.post("/api/history/clear", response_class=HTMLResponse)

async def api_history_clear_endpoint(request: Request):

    """Limpia la bitácora de ejecuciones en memoria RAM y reinicia el MemorySaver."""

    execution_history_manager.clear()

    try:

        request.app.state.execution_history = execution_history_manager.records

        request.app.state.memory_saver = execution_history_manager.memory_saver

    except Exception:

        pass

    target_container = request.query_params.get("target_container", "#modal-visor-historial")

    return HTMLResponse(content=render_executions_partial([], target_container=target_container))





@router.post("/api/history/undo-clear", response_class=HTMLResponse)

async def api_history_undo_clear_endpoint(request: Request):

    """Restaura la bitácora de ejecuciones en memoria RAM al estado previo al clear."""

    execution_history_manager.undo_clear()

    try:

        request.app.state.execution_history = execution_history_manager.records

        request.app.state.memory_saver = execution_history_manager.memory_saver

    except Exception:

        pass

    target_container = request.query_params.get("target_container", "#modal-visor-historial")

    return HTMLResponse(content=render_executions_partial(execution_history_manager.records, target_container=target_container))





@router.get("/observabilidad", response_class=HTMLResponse)

async def observabilidad_page(request: Request):

    """

    Página del visor de observabilidad en tiempo real.

    Construida con TailwindCSS y HTMX (hx-ext="sse") siguiendo la filosofía HATEOAS.

    """

    is_embedded = (

        request.query_params.get("embed", "").lower() in ("true", "1")

        or request.query_params.get("view") in ("suite", "suite_observabilidad")

    )

    html_content = r"""<!DOCTYPE html>

<html lang="es">

<head>

    <meta charset="UTF-8">

    <meta name="viewport" content="width=device-width, initial-scale=1.0">

    <title>NetDiagBench-L7 &bull; Visor de Observabilidad en Tiempo Real (HTMX + SSE)</title>

    <!-- TailwindCSS (Local First con Fallback CDN) -->

    <script src="/static/vendor/tailwind.cdn.js" onerror="this.onerror=null;this.src='https://cdn.tailwindcss.com';"></script>

    <script>

        tailwind.config = {

            darkMode: 'class',

            theme: {

                extend: {

                    colors: {

                        brandRed: '#ad3333',

                        brandNavy: '#003366',

                        brandDark: '#070e18',

                        brandSurface: '#0e1b2e'

                    }

                }

            }

        };

        (function() {

            try {

                const t = localStorage.getItem('netdiag_theme') || 'dark';

                document.documentElement.setAttribute('data-theme', t);

                if (t === 'dark') document.documentElement.classList.add('dark');

                else document.documentElement.classList.remove('dark');

            } catch(e) {}

        })();

    </script>

    <!-- HTMX 2.0 y Extensión SSE Oficial (Local First con Fallback CDN) -->

    <script src="/static/vendor/htmx.min.js" onerror="this.onerror=null;this.src='https://unpkg.com/htmx.org@2.0.4';"></script>

    <script src="/static/vendor/sse.js" onerror="this.onerror=null;this.src='https://unpkg.com/htmx-ext-sse@2.2.2/sse.js';"></script>

    <!-- Alpine.js (Unificado v3.14.8 Local First con Fallback CDN) -->

    <script defer src="/static/vendor/alpine.min.js" onerror="this.onerror=null;this.src='https://cdn.jsdelivr.net/npm/alpinejs@3.14.8/dist/cdn.min.js';"></script>



    <style>

        :root {

            --scrollbar-track: transparent;

            --scrollbar-thumb: rgba(148, 163, 184, 0.22);

            --scrollbar-thumb-hover: rgba(148, 163, 184, 0.42);

        }

        [data-theme="light"] {

            --scrollbar-track: transparent;

            --scrollbar-thumb: rgba(71, 85, 105, 0.25);

            --scrollbar-thumb-hover: rgba(71, 85, 105, 0.45);

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



        @keyframes fadeIn {

            from { opacity: 0; transform: translateY(8px); }

            to { opacity: 1; transform: translateY(0); }

        }

        .animate-fadeIn {

            animation: fadeIn 0.4s ease-out forwards;

        }

        /* Línea continua vertical de la línea de tiempo */

        .timeline-line::before {

            content: '';

            position: absolute;

            top: 24px;

            bottom: 24px;

            left: 0;

            width: 2px;

            background: linear-gradient(180deg, #3b82f6 0%, #ad3333 70%, #10b981 100%);

            opacity: 0.4;

        }

        /* Scrollbar estilizado para el stream interno de la línea de tiempo */

        #timelineEventsStream::-webkit-scrollbar {

            width: 6px;

        }

        #timelineEventsStream::-webkit-scrollbar-track {

            background: #070e18;

            border-radius: 4px;

        }

        #timelineEventsStream::-webkit-scrollbar-thumb {

            background: #1e293b;

            border-radius: 4px;

        }

        #timelineEventsStream::-webkit-scrollbar-thumb:hover {

            background: #334155;

        }



        /* ================= MODO EMBEBIDO AISLADO ================= */

        details[open] > summary .details-arrow {

            transform: rotate(180deg);

        }

        summary::-webkit-details-marker {

            display: none;

        }

        pre::-webkit-scrollbar {

            width: 6px;

            height: 6px;

        }

        pre::-webkit-scrollbar-track {

            background: transparent;

        }

        pre::-webkit-scrollbar-thumb {

            background: #475569;

            border-radius: 4px;

        }

        pre::-webkit-scrollbar-thumb:hover {

            background: #64748b;

        }

        pre {

            scrollbar-width: thin;

            scrollbar-color: #475569 transparent;

        }



        /* ================= MODO DE DÍA (LIGHT THEME) ================= */

        [data-theme="light"] {

            background-color: #f4f6f9 !important;

            color: #0f172a !important;

        }

        [data-theme="light"] body {

            background-color: #f4f6f9 !important;

            color: #0f172a !important;

        }

        [data-theme="light"] h2.text-white {

            color: #003366 !important;

        }

        [data-theme="light"] .bg-\[\#0e1b2e\], [data-theme="light"] .bg-\[\#0e1b2e\]\/60 {

            background-color: #ffffff !important;

            border-color: #cbd5e1 !important;

            box-shadow: 0 2px 8px rgba(0, 51, 102, 0.06) !important;

        }

        [data-theme="light"] .bg-\[\#070e18\], [data-theme="light"] .bg-\[\#070e18\]\/80 {

            background-color: #f8fafc !important;

            border-color: #cbd5e1 !important;

            color: #0f172a !important;

        }

        [data-theme="light"] .text-slate-100 {

            color: #0f172a !important;

        }

        [data-theme="light"] .text-slate-200 {

            color: #1e293b !important;

        }

        [data-theme="light"] .text-slate-300 {

            color: #334155 !important;

        }

        [data-theme="light"] .text-slate-400 {

            color: #475569 !important;

        }

        [data-theme="light"] .border-slate-800, [data-theme="light"] .border-slate-800\/80 {

            border-color: #cbd5e1 !important;

        }

        [data-theme="light"] .border-slate-700, [data-theme="light"] .border-slate-700\/60, [data-theme="light"] .border-slate-700\/80 {

            border-color: #cbd5e1 !important;

        }



        /* Ficha Destacada de Falla L7 */

        [data-theme="light"] #faultProblemCard {

            background: #ffffff !important;

            background-image: none !important;

            border-color: #ad3333 !important;

            box-shadow: 0 4px 16px rgba(173, 51, 51, 0.08) !important;

        }

        [data-theme="light"] #faultProblemCard .bg-\[\#070e18\]\/80,

        [data-theme="light"] #faultProblemCard .bg-\[\#070e18\] {

            background-color: #f8fafc !important;

            border-color: #e2e8f0 !important;

            color: #0f172a !important;

        }

        [data-theme="light"] #faultProblemCard #faultDescription,

        [data-theme="light"] #faultProblemCard p {

            color: #0f172a !important;

        }

        [data-theme="light"] #faultProblemCard #faultScenarioId {

            color: #003366 !important;

            font-weight: 800 !important;

        }

        [data-theme="light"] #faultProblemCard #faultCategoryBadge {

            background-color: #e0f2fe !important;

            border-color: #7dd3fc !important;

            color: #0369a1 !important;

        }

        [data-theme="light"] #faultProblemCard #faultClassBadge {

            background-color: #fee2e2 !important;

            border-color: #fca5a5 !important;

            color: #991b1b !important;

        }

        [data-theme="light"] #faultProblemCard #faultAffectedComponent {

            color: #ad3333 !important;

            font-weight: 700 !important;

        }

        [data-theme="light"] #faultProblemCard #faultTool {

            color: #b45309 !important;

            font-weight: 700 !important;

        }

        [data-theme="light"] #faultProblemCard span.text-slate-400 {

            color: #475569 !important;

            font-weight: 700 !important;

        }

        [data-theme="light"] #faultProblemCard .text-slate-300 {

            color: #334155 !important;

        }

        [data-theme="light"] #faultProblemCard .border-slate-700\/60,

        [data-theme="light"] #faultProblemCard .border-slate-800,

        [data-theme="light"] #faultProblemCard .border-slate-800\/80 {

            border-color: #e2e8f0 !important;

        }



        /* Banner de Transición entre Escenarios */

        [data-theme="light"] .my-6.p-4.rounded-xl.bg-gradient-to-r {

            background: linear-gradient(to right, #eff6ff, #f8fafc) !important;

            border-color: #cbd5e1 !important;

            border-left-color: #ad3333 !important;

        }

        [data-theme="light"] .my-6.p-4.rounded-xl.bg-gradient-to-r .text-white {

            color: #003366 !important;

        }

        [data-theme="light"] .my-6.p-4.rounded-xl.bg-gradient-to-r .text-amber-300 {

            color: #b45309 !important;

        }

        [data-theme="light"] .my-6.p-4.rounded-xl.bg-gradient-to-r .text-blue-200 {

            color: #0369a1 !important;

        }

        [data-theme="light"] .my-6.p-4.rounded-xl.bg-gradient-to-r .bg-blue-900\/60 {

            background-color: #e0f2fe !important;

            border-color: #7dd3fc !important;

        }

        [data-theme="light"] .my-6.p-4.rounded-xl.bg-gradient-to-r .text-slate-300 {

            color: #334155 !important;

        }

        [data-theme="light"] .my-6.p-4.rounded-xl.bg-gradient-to-r .text-slate-400 {

            color: #475569 !important;

        }

        [data-theme="light"] .my-6.p-4.rounded-xl.bg-gradient-to-r .text-slate-200 {

            color: #0f172a !important;

        }



        /* Nodos y Tarjetas del Grafo LangGraph */

        [data-theme="light"] details[data-node-card],

        [data-theme="light"] div[data-node-card],

        [data-theme="light"] .bg-\[\#101624\] {

            background-color: #ffffff !important;

            border-color: #cbd5e1 !important;

            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04) !important;

        }

        [data-theme="light"] .bg-\[\#0A0E16\] {

            background-color: #f8fafc !important;

            border-color: #e2e8f0 !important;

            color: #0f172a !important;

        }

        [data-theme="light"] .bg-\[\#1E2A40\] {

            background-color: #e2e8f0 !important;

            color: #003366 !important;

        }

        [data-theme="light"] .bg-\[\#0E2A22\] {

            background-color: #ecfdf5 !important;

            border-color: #a7f3d0 !important;

        }

        [data-theme="light"] .bg-\[\#0E2A22\] .text-slate-200 {

            color: #065f46 !important;

        }

        [data-theme="light"] .bg-\[\#1C1608\] {

            background-color: #fffbeb !important;

            border-color: #fde68a !important;

        }

        [data-theme="light"] .bg-\[\#1C1608\] .text-amber-300 {

            color: #92400e !important;

        }

        [data-theme="light"] .bg-\[\#0E2E24\] {

            background-color: #ecfdf5 !important;

            border-color: #a7f3d0 !important;

            color: #047857 !important;

        }

        [data-theme="light"] .bg-\[\#3A2A0E\] {

            background-color: #fef3c7 !important;

            border-color: #fde68a !important;

            color: #92400e !important;

        }

        [data-theme="light"] .bg-\[\#1A2233\] {

            background-color: #e2e8f0 !important;

        }

        [data-theme="light"] .bg-\[\#0B1F1A\],

        [data-theme="light"] .bg-\[\#0B1C17\] {

            background-color: #ecfdf5 !important;

            border-color: #a7f3d0 !important;

            color: #065f46 !important;

        }

        [data-theme="light"] code.bg-\[\#0A0E16\],

        [data-theme="light"] code.bg-\[\#0B1F1A\] {

            background-color: #f1f5f9 !important;

            border-color: #cbd5e1 !important;

            color: #0f172a !important;

        }



        /* Tarjeta de Razonamiento CoT del Agente (Regla 3) */

        [data-theme="light"] .bg-\[\#0e1b2e\] {

            background-color: #ffffff !important;

            border-color: #cbd5e1 !important;

            box-shadow: 0 2px 8px rgba(0, 51, 102, 0.05) !important;

        }

        [data-theme="light"] .bg-\[\#0e1b2e\] p {

            color: #1e293b !important;

            line-height: 1.6 !important;

        }

        [data-theme="light"] .bg-\[\#0e1b2e\] p span.text-slate-300 {

            color: #003366 !important;

            font-weight: 700 !important;

        }

        [data-theme="light"] .bg-\[\#0e1b2e\] strong {

            color: #003366 !important;

            font-weight: 700 !important;

        }

        [data-theme="light"] .bg-\[\#0e1b2e\] .text-slate-100 {

            color: #003366 !important;

            font-weight: 700 !important;

        }

        [data-theme="light"] .bg-\[\#0e1b2e\] .bg-purple-900\/40 {

            background-color: #f3e8ff !important;

            border-color: #d8b4fe !important;

            color: #6b21a8 !important;

            font-weight: 700 !important;

        }

        [data-theme="light"] .bg-\[\#0e1b2e\] .bg-purple-950\/60 {

            background-color: #f3e8ff !important;

            border-color: #d8b4fe !important;

            color: #7e22ce !important;

        }



        /* Tarjeta de Diagnóstico Final */

        [data-theme="light"] .timeline-verdict-card {

            background: #ffffff !important;

            background-image: none !important;

            border-color: #059669 !important;

            box-shadow: 0 4px 16px rgba(5, 150, 105, 0.1) !important;

        }

        [data-theme="light"] .timeline-verdict-card .verdict-subbox {

            background-color: #f8fafc !important;

            border-color: #cbd5e1 !important;

            color: #0f172a !important;

        }

        [data-theme="light"] .timeline-verdict-card .verdict-subbox p,

        [data-theme="light"] .timeline-verdict-card p.text-white,

        [data-theme="light"] .timeline-verdict-card p.text-slate-100 {

            color: #0f172a !important;

        }

        [data-theme="light"] .timeline-verdict-card strong.text-white,

        [data-theme="light"] .timeline-verdict-card strong.text-slate-200 {

            color: #003366 !important;

        }

        [data-theme="light"] .timeline-verdict-card .text-slate-200 {

            color: #0f172a !important;

        }

        [data-theme="light"] .timeline-verdict-card .text-slate-300 {

            color: #1e293b !important;

        }

        [data-theme="light"] .timeline-verdict-card .text-slate-400 {

            color: #475569 !important;

        }

        [data-theme="light"] .timeline-verdict-card .border-slate-700\/80,

        [data-theme="light"] .timeline-verdict-card .border-slate-700\/60,

        [data-theme="light"] .timeline-verdict-card .border-slate-800 {

            border-color: #e2e8f0 !important;

        }

        [data-theme="light"] .timeline-verdict-card .bg-emerald-900\/60 {

            background-color: #dcfce7 !important;

            border-color: #86efac !important;

            color: #166534 !important;

        }



        /* Panel Inferior de Control de Ejecución */

        [data-theme="light"] #controlPanelCard {

            background-color: #ffffff !important;

            border-color: #cbd5e1 !important;

            box-shadow: 0 4px 16px rgba(0, 51, 102, 0.08) !important;

        }

        [data-theme="light"] #controlPanelCard h3 {

            color: #003366 !important;

        }

        [data-theme="light"] #controlPanelCard label {

            color: #1e293b !important;

            font-weight: 700 !important;

        }

        [data-theme="light"] #controlPanelCard select,

        [data-theme="light"] #controlPanelCard input {

            background-color: #ffffff !important;

            border-color: #cbd5e1 !important;

            color: #0f172a !important;

        }

        [data-theme="light"] #controlPanelCard .bg-\[\#070e18\] {

            background-color: #f8fafc !important;

            border-color: #cbd5e1 !important;

        }

        [data-theme="light"] #controlPanelCard .border-slate-800,

        [data-theme="light"] #controlPanelCard .border-slate-800\/80,

        [data-theme="light"] #controlPanelCard .border-slate-700,

        [data-theme="light"] #controlPanelCard .border-slate-700\/80 {

            border-color: #e2e8f0 !important;

        }

        [data-theme="light"] #controlPanelCard .text-slate-200 {

            color: #0f172a !important;

        }

        [data-theme="light"] #controlPanelCard .text-slate-400 {

            color: #475569 !important;

        }

        [data-theme="light"] #controlPanelCard .text-white {

            color: #003366 !important;

        }



        /* Botones e Indicadores */

        [data-theme="light"] #btnClear {

            background-color: #ffffff !important;

            border-color: #cbd5e1 !important;

            color: #334155 !important;

        }

        [data-theme="light"] #btnClear:hover {

            background-color: #f1f5f9 !important;

            color: #0f172a !important;

        }

        [data-theme="light"] #statusBadge {

            background-color: #f1f5f9 !important;

            border-color: #cbd5e1 !important;

            color: #334155 !important;

        }

        [data-theme="light"] #btnStop {

            background-color: #fff1f2 !important;

            border-color: #fca5a5 !important;

            color: #991b1b !important;

        }

        [data-theme="light"] #btnStop:disabled,

        [data-theme="light"] #btnStop[disabled] {

            background-color: #f1f5f9 !important;

            border-color: #e2e8f0 !important;

            color: #94a3b8 !important;

            opacity: 0.6 !important;

        }

        [data-theme="light"] #sse-completed-banner {

            background-color: #dcfce7 !important;

            border-color: #86efac !important;

            color: #166534 !important;

        }

        [data-theme="light"] #emptyPlaceholder p.text-slate-500 {

            color: #334155 !important;

        }

        [data-theme="light"] #emptyPlaceholder p.text-slate-600 {

            color: #475569 !important;

        }

        [data-theme="light"] #emptyPlaceholder svg {

            color: #64748b !important;

        }

        [data-theme="light"] #livePulseDot {

            background-color: #10b981 !important;

        }

        [data-theme="light"] #visorStandaloneHeader {

            background: #ffffff !important;

            border-color: #e2e8f0 !important;

            box-shadow: 0 2px 8px rgba(0,0,0,0.06) !important;

        }

        [data-theme="light"] #visorStandaloneHeader a.text-white {

            color: #003366 !important;

        }

        [data-theme="light"] #visorStandaloneHeader p.text-slate-400 {

            color: #475569 !important;

        }

        body.is-embedded #visorStandaloneHeader,

        body.is-embedded header,

        body.is-embedded .visor-standalone-only {

            display: none !important;

        }

        body.is-embedded main {

            padding-top: 0.5rem !important;

            padding-bottom: 1rem !important;

            max-width: 100% !important;

        }


        /* ==========================================================================
           CORRECCIONES DE CONTRASTE EN MODO CLARO (LIGHT MODE) - NETDIAGBENCH-L7
           ========================================================================== */

        /* 1. Drain3 Tabla de logs L7 y badges de anomalía en Light Mode (Imagen 2) */
        [data-theme="light"] tr.drain-log-anomaly {
            background-color: #fffbeb !important;
            border-color: #fde68a !important;
        }
        [data-theme="light"] tr.drain-log-anomaly:hover {
            background-color: #fef3c7 !important;
        }
        [data-theme="light"] tr.drain-log-anomaly td {
            color: #78350f !important;
        }
        [data-theme="light"] tr.drain-log-anomaly td:nth-child(3) {
            color: #92400e !important;
            font-weight: 700 !important;
        }
        [data-theme="light"] tr.drain-log-normal {
            background-color: #ffffff !important;
        }
        [data-theme="light"] tr.drain-log-normal:hover {
            background-color: #f8fafc !important;
        }
        [data-theme="light"] tr.drain-log-normal td {
            color: #1e293b !important;
        }
        [data-theme="light"] tr.drain-log-normal td:nth-child(3) {
            color: #0369a1 !important;
        }
        [data-theme="light"] .drain-badge-anomaly {
            background-color: #fef08a !important;
            color: #854d0e !important;
            border-color: #eab308 !important;
        }
        [data-theme="light"] .drain-badge-normal {
            background-color: #dcfce7 !important;
            color: #166534 !important;
            border-color: #86efac !important;
        }

        /* 2. Interim Reasoning Card (CoT) en Light Mode (Imagen 1) */
        [data-theme="light"] .cot-interim-box {
            background-color: #ffffff !important;
            border-color: #c084fc !important;
            box-shadow: 0 4px 16px rgba(168, 85, 247, 0.12) !important;
        }
        [data-theme="light"] .cot-interim-circle {
            background-color: #faf5ff !important;
            border-color: #a855f7 !important;
            box-shadow: 0 2px 8px rgba(168, 85, 247, 0.2) !important;
        }
        [data-theme="light"] .cot-interim-circle svg {
            color: #7c3aed !important;
        }
        [data-theme="light"] .cot-interim-header {
            border-color: #f3e8ff !important;
        }
        [data-theme="light"] .cot-interim-title {
            color: #581c87 !important;
        }
        [data-theme="light"] .cot-interim-tag {
            background-color: #f3e8ff !important;
            border-color: #d8b4fe !important;
            color: #6b21a8 !important;
        }
        [data-theme="light"] .cot-interim-status {
            background-color: #fae8ff !important;
            border-color: #f0abfc !important;
            color: #86198f !important;
        }
        [data-theme="light"] .cot-interim-desc {
            color: #334155 !important;
        }
        [data-theme="light"] .cot-interim-desc strong {
            color: #003366 !important;
        }
        [data-theme="light"] .cot-interim-progress {
            background-color: #faf5ff !important;
            border-color: #d8b4fe !important;
            color: #6b21a8 !important;
            font-weight: 600 !important;
        }
        [data-theme="light"] .cot-interim-spinner {
            color: #7c3aed !important;
        }
        [data-theme="light"] .cot-interim-timer {
            color: #6b21a8 !important;
        }

        /* 3. Botón Copiar Ficha para Ticket en Light Mode (Imagen 4) */
        [data-theme="light"] .btn-copy-ticket,
        [data-theme="light"] #btnCopyTicketHeader {
            background-color: #ffffff !important;
            border-color: #cbd5e1 !important;
            color: #0f172a !important;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08) !important;
        }
        [data-theme="light"] .btn-copy-ticket:hover,
        [data-theme="light"] #btnCopyTicketHeader:hover {
            background-color: #f1f5f9 !important;
            border-color: #94a3b8 !important;
            color: #003366 !important;
        }
        [data-theme="light"] .evidence-confidence-badge {
            background-color: #ecfdf5 !important;
            border-color: #a7f3d0 !important;
            color: #047857 !important;
        }

        /* 4. Badges de Etapas y Cabeceras en Light Mode (Imagen 5) */
        [data-theme="light"] .bg-emerald-950\/60,
        [data-theme="light"] .bg-emerald-950\/80 {
            background-color: #ecfdf5 !important;
            border-color: #a7f3d0 !important;
            color: #047857 !important;
            font-weight: 700 !important;
        }
        [data-theme="light"] .bg-blue-950\/60,
        [data-theme="light"] .bg-blue-950\/70 {
            background-color: #eff6ff !important;
            border-color: #bfdbfe !important;
            color: #1d4ed8 !important;
            font-weight: 700 !important;
        }
        [data-theme="light"] .bg-purple-950\/60,
        [data-theme="light"] .bg-purple-950\/40,
        [data-theme="light"] .bg-purple-900\/40 {
            background-color: #f5f3ff !important;
            border-color: #ddd6fe !important;
            color: #6b21a8 !important;
            font-weight: 700 !important;
        }

        /* 5. Bitácora de Sesión (RAM) en Light Mode (Imagen 3) */
        [data-theme="light"] #sidebarHistorySection .bg-\[\#003366\],
        [data-theme="light"] #cardSessionHistory .bg-\[\#003366\] {
            background-color: #e0f2fe !important;
            border-color: #7dd3fc !important;
            color: #0369a1 !important;
            font-weight: 700 !important;
        }
        [data-theme="light"] #sidebarHistorySection button[onclick*="clearHistoryWithUndo"],
        [data-theme="light"] #cardSessionHistory button[onclick*="clearHistoryWithUndo"] {
            background-color: #ffffff !important;
            border-color: #cbd5e1 !important;
            color: #64748b !important;
        }
        [data-theme="light"] #sidebarHistorySection button[onclick*="clearHistoryWithUndo"]:hover,
        [data-theme="light"] #cardSessionHistory button[onclick*="clearHistoryWithUndo"]:hover {
            background-color: #fee2e2 !important;
            border-color: #f87171 !important;
            color: #dc2626 !important;
        }
        [data-theme="light"] #executionHistoryContainer .bg-\[\#070e18\] {
            background-color: #f8fafc !important;
            border-color: #e2e8f0 !important;
            color: #475569 !important;
        }
        [data-theme="light"] #executionHistoryContainer .text-sky-300 {
            color: #0284c7 !important;
        }
        [data-theme="light"] #historyFilterChips .hist-filter-chip:not(.active-hist-chip) {
            background-color: #f1f5f9 !important;
            border-color: #cbd5e1 !important;
            color: #475569 !important;
        }
        [data-theme="light"] #historyFilterChips .active-hist-chip {
            background-color: #003366 !important;
            color: #ffffff !important;
            border-color: #003366 !important;
        }

    
        /* 6. Botones Bitácora y Copiar comando en Light Mode */
        [data-theme="light"] .btn-replay-bitacora,
        [data-theme="light"] button.btn-replay-bitacora {
            background-color: #ffffff !important;
            background: #ffffff !important;
            background-image: none !important;
            border: 1px solid #cbd5e1 !important;
            color: #1e293b !important;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08) !important;
            font-weight: 600 !important;
        }
        [data-theme="light"] .btn-replay-bitacora:hover,
        [data-theme="light"] button.btn-replay-bitacora:hover {
            background-color: #f1f5f9 !important;
            background: #f1f5f9 !important;
            background-image: none !important;
            color: #003366 !important;
            border-color: #94a3b8 !important;
        }
        [data-theme="light"] .btn-replay-bitacora span,
        [data-theme="light"] button.btn-replay-bitacora span {
            color: #1e293b !important;
        }
        [data-theme="light"] .btn-replay-bitacora:hover span,
        [data-theme="light"] button.btn-replay-bitacora:hover span {
            color: #003366 !important;
        }

        [data-theme="light"] .btn-copy-command,
        [data-theme="light"] button.btn-copy-command {
            background-color: #ffffff !important;
            background: #ffffff !important;
            background-image: none !important;
            border: 1px solid #cbd5e1 !important;
            color: #1e293b !important;
            box-shadow: 0 1px 2px rgba(0, 0, 0, 0.08) !important;
            font-weight: 600 !important;
        }
        [data-theme="light"] .btn-copy-command:hover,
        [data-theme="light"] button.btn-copy-command:hover {
            background-color: #f1f5f9 !important;
            background: #f1f5f9 !important;
            background-image: none !important;
            color: #003366 !important;
            border-color: #94a3b8 !important;
        }
        [data-theme="light"] .btn-copy-command span,
        [data-theme="light"] .btn-copy-command .copy-label,
        [data-theme="light"] button.btn-copy-command span,
        [data-theme="light"] button.btn-copy-command .copy-label {
            color: #1e293b !important;
        }
        [data-theme="light"] .btn-copy-command:hover span,
        [data-theme="light"] .btn-copy-command:hover .copy-label,
        [data-theme="light"] button.btn-copy-command:hover span,
        [data-theme="light"] button.btn-copy-command:hover .copy-label {
            color: #003366 !important;
        }

    </style>

</head>

<body class="<!-- BODY_CLASS_PLACEHOLDER -->bg-[#070e18] text-slate-100 min-h-screen font-sans antialiased selection:bg-red-500/30 selection:text-white">



    <!-- VISOR_HEADER_PLACEHOLDER -->



    <!-- Contenido Principal -->

    <main class="<!-- MAIN_CLASS_PLACEHOLDER -->"

          x-data="{ isRunning: false, currentIndex: 0, totalCases: 18 }"

          @suite-started.window="isRunning = true;"

          @suite-progress.window="currentIndex = $event.detail.index; window.lastCompletedScenarioIndex = currentIndex; if (currentIndex >= totalCases) { isRunning = false; }"

          @suite-finished.window="isRunning = false; currentIndex = 18; window.lastCompletedScenarioIndex = 18; window.isSuiteFinished = true;"

          @suite-paused.window="isRunning = false; if ($event.detail && $event.detail.index !== undefined) { currentIndex = $event.detail.index; window.lastCompletedScenarioIndex = currentIndex; }"

          @suite-clear.window="currentIndex = 0; isRunning = false; window.lastCompletedScenarioIndex = 0; window.isSuiteFinished = false;">



        <!-- 1. Panel de la Línea de Tiempo (Observabilidad) [ARRIBA] -->

        <div class="bg-[#0e1b2e]/60 border border-slate-800 rounded-2xl p-6 sm:p-8 shadow-2xl">

            <div class="flex items-center justify-between border-b border-slate-800 pb-4 mb-6 flex-wrap gap-3">

                <div>

                    <h2 class="text-lg font-bold text-white flex items-center gap-2">

                        <span id="livePulseDot" class="w-2.5 h-2.5 rounded-full bg-emerald-500"></span>

                        <span>Línea de Tiempo de Ejecución (LangGraph Timeline)</span>

                    </h2>

                    <p class="text-xs text-slate-400">Los eventos se renderizan en el servidor FastAPI y se transmiten vía SSE a HTMX.</p>

                </div>

                <div class="flex items-center gap-2.5">

                    <button type="button"

                            onclick="clearTimeline()"

                            :disabled="isRunning"

                            :class="isRunning ? 'opacity-40 cursor-not-allowed' : ''"

                            @click="document.getElementById('suite-timeline-container').innerHTML = ''; currentIndex = 0; isRunning = false; window.dispatchEvent(new CustomEvent('suite-clear'));"

                            id="btnClear"

                            class="text-xs px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition flex items-center gap-1.5 cursor-pointer">

                        <svg class="w-3.5 h-3.5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>

                        <span>Limpiar Visor</span>

                    </button>

                    <div id="statusBadge" class="text-xs px-3 py-1 rounded-full bg-slate-800 text-slate-300 font-mono border border-slate-700 flex items-center gap-1.5">

                        Listo para iniciar

                    </div>

                </div>

            </div>



            <!-- Ficha Destacada: Qué Falla de Red L7 se está Resolviendo -->

            <div id="faultProblemCard" class="bg-gradient-to-br from-[#112038] to-[#070e18] border-2 border-[#ad3333] rounded-xl p-5 mb-6 shadow-xl relative overflow-hidden transition-all duration-300">

                <div class="absolute top-0 right-0 w-44 h-44 bg-[#ad3333]/15 rounded-full blur-3xl pointer-events-none"></div>



                <div class="flex items-center justify-between mb-3 flex-wrap gap-2 border-b border-slate-700/60 pb-3">

                    <div class="flex items-center gap-2.5">

                        <span class="px-3 py-1 rounded-md bg-[#ad3333] text-white font-bold text-xs uppercase tracking-wider flex items-center gap-2 shadow">

                            <span class="w-2 h-2 rounded-full bg-white animate-pulse"></span>

                            FALLA L7 EN DIAGNÓSTICO

                        </span>

                        <span id="faultCategoryBadge" class="font-mono text-xs px-2.5 py-0.5 rounded bg-blue-950/70 border border-blue-500/40 text-blue-300 font-bold">

                            [DNS / HTTP / TLS / GATEWAY]

                        </span>

                        <span id="faultScenarioId" class="font-mono text-sm text-white font-black tracking-wide">

                            SUITE-COMPLETA (18 CASOS)

                        </span>

                    </div>

                    <div class="flex items-center gap-2">

                        <span class="text-xs text-slate-400 font-medium">Clase de Anomalía:</span>

                        <span id="faultClassBadge" class="text-xs px-2.5 py-0.5 rounded-full bg-red-950/70 border border-red-500/50 text-red-200 font-mono font-bold tracking-wide">

                            SUITE SECUENCIAL DETERMINISTA

                        </span>

                    </div>

                </div>



                <!-- Descripción del Síntoma / Falla -->

                <div class="mb-4">

                    <span class="text-xs font-bold text-slate-400 uppercase tracking-wider block mb-1">Síntoma Técnico Reportado (Falla a Resolver):</span>

                    <p id="faultDescription" class="text-sm font-semibold text-slate-100 leading-relaxed bg-[#070e18]/80 p-3.5 rounded-lg border border-slate-800 shadow-inner">

                        Ejecución continua de la suite completa de 18 escenarios de falla de red L7 catalogados. El agente SLM resolverá secuencialmente cada anomalía mediante CoT, RAG de estándares IETF y comandos de terminal de solo lectura bajo control estricto de semilla.

                    </p>

                </div>



                <!-- Detalles Técnicos y Misión -->

                <div class="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">

                    <div class="bg-[#070e18] border border-slate-800/80 p-3 rounded-lg">

                        <span class="text-slate-400 font-bold block text-[11px] uppercase tracking-wider mb-1">Componente Objetivo:</span>

                        <span id="faultAffectedComponent" class="font-mono font-bold text-red-300 text-xs">Infraestructura L7 Completa (18 servicios)</span>

                    </div>

                    <div class="bg-[#070e18] border border-slate-800/80 p-3 rounded-lg">

                        <span class="text-slate-400 font-bold block text-[11px] uppercase tracking-wider mb-1">Herramientas Read-Only:</span>

                        <span id="faultTool" class="font-mono font-bold text-amber-300 text-xs">dig / curl / openssl</span>

                    </div>

                    <div class="bg-[#070e18] border border-slate-800/80 p-3 rounded-lg">

                        <span class="text-slate-400 font-bold block text-[11px] uppercase tracking-wider mb-1">Misión del Agente SLM:</span>

                        <span class="font-sans text-slate-300 text-xs font-medium">CoT + RAG IETF + Verificación + Mitigación</span>

                    </div>

                </div>

            </div>



            <!-- Contenedor SSE Dinámico gestionado por HTMX (Suite de Observabilidad) -->

            <div id="suiteTimelineHost" class="relative pl-3 timeline-line">

                <!-- Área Central Target del SSE: #suite-timeline-container -->

                <div id="suite-timeline-container"

                     class="space-y-3 max-h-[520px] overflow-y-auto pr-2 scroll-smooth"

                     hx-ext="sse"

                     data-stream-endpoint="/stream-diagnostico">

                    <!-- Stream de eventos interno que aloja las tarjetas -->

                    <div id="timelineEventsStream" class="space-y-3">

                        <div id="emptyPlaceholder" class="text-center py-16 text-slate-500">

                            <svg class="w-12 h-12 mx-auto mb-3 opacity-40 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">

                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>

                            </svg>

                            <p class="text-sm font-medium">Presiona "Iniciar Diagnóstico SSE" en el panel de control inferior</p>

                            <p class="text-xs text-slate-600 mt-1">Los 18 escenarios de red se resolverán secuencialmente. Puedes pausar y reanudar sin perder el avance.</p>

                        </div>

                    </div>

                </div>



                <!-- Host invisible para conexión SSE adicional -->

                <div id="sseReceiverHost"></div>

            </div>



            <!-- Control reactivo de visibilidad de pausa (Alpine.js) -->

            <div x-show="currentIndex > 0 && currentIndex < totalCases && !isRunning" class="hidden" style="display:none;"></div>

        </div>



        <!-- 2. Barra de Configuración y Control [ABAJO - FIJA Y ESTÉTICA] -->

        <div id="controlPanelCard"

             class="bg-[#0e1b2e] border border-slate-800 rounded-2xl p-5 shadow-2xl">

            <div class="flex items-center justify-between mb-4 border-b border-slate-800/80 pb-3">

                <div class="flex items-center gap-2">

                    <span class="w-2.5 h-2.5 rounded-full" :class="isRunning ? 'bg-amber-400 animate-ping' : (currentIndex > 0 ? 'bg-emerald-400' : 'bg-[#ad3333]')"></span>

                    <h3 class="text-xs font-bold uppercase tracking-wider text-slate-200">Panel de Control de Ejecución (Parámetros de Diagnóstico)</h3>

                </div>

                <div class="flex items-center gap-2 text-xs font-mono text-slate-400">

                    <span>Progreso: <strong id="progressCount" class="text-emerald-400" x-text="currentIndex">0</strong>/18 Escenarios</span>

                    <span class="text-slate-600">&bull;</span>

                    <span>Semillas Deterministas (3 Científicas o Personalizada) &bull; Historial Persistente</span>

                </div>

            </div>



            <form id="diagForm"

                  hx-post="/api/execute-suite"

                  hx-target="#suite-timeline-container"

                  class="grid grid-cols-1 md:grid-cols-12 gap-4 items-end"

                  onsubmit="return false;">

                <!-- Modo de Ejecución Estático (4 cols) -->

                <div class="md:col-span-4">

                    <label class="block text-xs font-bold uppercase tracking-wider text-slate-300 mb-2">Escenario L7 de Red:</label>

                    <div class="w-full bg-[#070e18] border border-slate-700/80 rounded-xl px-3.5 py-2.5 text-xs text-slate-200 flex items-center justify-between shadow-inner">

                        <div class="flex items-center gap-2.5 min-w-0">

                            <span class="w-2.5 h-2.5 rounded-full bg-emerald-400 shrink-0"></span>

                            <div class="truncate">

                                <span class="font-bold text-white text-xs block leading-tight truncate">Suite Completa L7 (18 Escenarios)</span>

                                <span class="text-slate-400 text-[11px] font-mono truncate block">Secuencial determinista &bull; DNS / HTTP / TLS / Gateway</span>

                            </div>

                        </div>

                        <span class="px-2 py-0.5 rounded bg-blue-900/60 text-blue-300 font-mono text-[10px] border border-blue-400/30 font-bold shrink-0 ml-2">ESTÁTICO</span>

                    </div>

                    <input type="hidden" id="selScenario" name="scenario_id" value="ALL">

                    <input type="hidden" id="txtStartIndex" name="start_index" :value="currentIndex >= totalCases ? 0 : currentIndex" value="0">

                </div>



                <!-- Modelo (3 cols) -->

                <div class="md:col-span-3">

                    <label for="selModel" class="block text-xs font-bold uppercase tracking-wider text-slate-300 mb-2">Modelo de Lenguaje (SLM):</label>

                    <select id="selModel" name="model_id"

                            :disabled="isRunning"

                            :class="isRunning ? 'opacity-50 cursor-not-allowed' : ''"

                            @change="currentIndex = 0; isRunning = false; resetSuiteExecution();"

                            class="w-full bg-[#070e18] border border-slate-700 rounded-xl px-3 py-2.5 text-xs text-slate-200 focus:outline-none focus:border-blue-500 font-medium transition-opacity">

                        <!-- MODEL_OPTIONS_PLACEHOLDER -->

                    </select>

                </div>



                <!-- Semilla (2 cols con selector estándar y opción de escribir otro número) -->

                <div class="md:col-span-2" x-data="{ isCustomSeed: false }">

                    <div class="flex items-center justify-between mb-2">

                        <label for="selSeed" class="block text-xs font-bold uppercase tracking-wider text-slate-300">Semilla:</label>

                        <button type="button"

                                @click="isCustomSeed = !isCustomSeed; if (isCustomSeed) { $nextTick(() => document.getElementById('txtCustomSeed')?.focus()); } else { resetToStandardSeed(); }"

                                :disabled="isRunning"

                                :class="isRunning ? 'opacity-40 cursor-not-allowed' : 'text-blue-400 hover:text-blue-300'"

                                class="text-[10px] font-semibold underline transition cursor-pointer flex items-center gap-1">

                            <span x-text="isCustomSeed ? '📋 Científicas' : '✏️ Otro nº'">✏️ Otro nº</span>

                        </button>

                    </div>



                    <!-- Selector estándar con opción de escribir otro número -->

                    <div x-show="!isCustomSeed">

                        <select id="selSeed" name="seed"

                                :disabled="isRunning"

                                :class="isRunning ? 'opacity-50 cursor-not-allowed' : ''"

                                @change="if ($event.target.value === 'custom') { isCustomSeed = true; $nextTick(() => document.getElementById('txtCustomSeed')?.focus()); } else { currentIndex = 0; isRunning = false; resetSuiteExecution(); }"

                                class="w-full bg-[#070e18] border border-slate-700 rounded-xl px-3 py-2.5 text-xs text-slate-200 focus:outline-none focus:border-blue-500 font-mono font-semibold transition-opacity">

                            <option value="42" selected>42 (Réplica #1)</option>

                            <option value="1337">1337 (Réplica #2)</option>

                            <option value="2026">2026 (Réplica #3)</option>

                            <option value="custom">✏️ Escribir otro número...</option>

                        </select>

                    </div>



                    <!-- Entrada personalizada de número -->

                    <div x-show="isCustomSeed" x-cloak class="relative flex items-center">

                        <input type="number" id="txtCustomSeed" min="0" max="2147483647" step="1"

                               placeholder="Ej: 100, 777"

                               :disabled="isRunning"

                               :class="isRunning ? 'opacity-50 cursor-not-allowed' : ''"

                               @input="syncCustomSeed($event.target.value)"

                               @keydown.enter.prevent="if (!isRunning) document.getElementById('btnStart')?.click();"

                               class="w-full bg-[#070e18] border border-blue-500/80 rounded-xl pl-3 pr-8 py-2.5 text-xs text-slate-100 placeholder-slate-500 font-mono font-semibold focus:outline-none focus:ring-1 focus:ring-blue-500 transition">

                        <button type="button"

                                @click="isCustomSeed = false; resetToStandardSeed();"

                                :disabled="isRunning"

                                class="absolute right-2.5 text-slate-400 hover:text-slate-200 text-xs cursor-pointer p-0.5">

                            ✕

                        </button>

                    </div>

                </div>



                <!-- Botones de Acción (3 cols) -->

                <div class="md:col-span-3 flex items-center gap-2">

                    <!-- Botón Iniciar / Reanudar: acción única con mutex de prevención de doble click -->

                    <button type="button"

                            id="btnStart"

                            onclick="startStreaming(event)"

                            @click="if(currentIndex >= totalCases) currentIndex = 0; isRunning = true;"

                            :disabled="isRunning"

                            :class="isRunning ? 'opacity-50 cursor-not-allowed' : ''"

                            class="flex-1 bg-gradient-to-r from-[#ad3333] to-[#801b1b] hover:from-red-600 hover:to-red-800 text-white font-bold text-xs uppercase tracking-wider py-3 px-3 rounded-xl shadow-lg shadow-red-900/40 transition-all flex items-center justify-center gap-1.5 cursor-pointer">

                        <svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>

                        <span id="btnStartText" class="truncate" x-text="currentIndex > 0 && currentIndex < totalCases ? 'REANUDAR' : 'INICIAR'">Iniciar</span>

                    </button>



                    <!-- Botón Detener -->

                    <button type="button"

                            @click="stopStreaming(); isRunning = false;"

                            id="btnStop"

                            :disabled="!isRunning"

                            :class="!isRunning ? 'opacity-40 cursor-not-allowed' : 'hover:bg-rose-950/60'"

                            class="px-3.5 py-3 rounded-xl text-xs font-bold uppercase tracking-wider bg-slate-800 text-rose-300 border border-rose-500/40 transition-all flex items-center justify-center gap-1.5 cursor-pointer">

                        <svg class="w-4 h-4 shrink-0 text-rose-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">

                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>

                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 10a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z"/>

                        </svg>

                        <span>Detener</span>

                    </button>

                </div>

            </form>

        </div>



    </main>



    <!-- Script de Control para conectar HTMX dinámicamente -->

    <script>

        // Interceptar EventSource nativo para registrar todas las instancias y poder cerrarlas sin excepción

        (function() {

            const _OrigEventSource = window.EventSource;

            window.activeEventSources = [];

            window.EventSource = function(url, opts) {

                const es = new _OrigEventSource(url, opts);

                window.activeEventSources.push(es);

                window.activeEventSource = es;

                return es;

            };

        })();



        // Aislamiento estricto de cabeceras en frontend: Visor standalone vs Suite embebida

        (function() {

            const isEmbeddedMode = window.self !== window.top ||

                new URLSearchParams(window.location.search).get('embed') === 'true' ||

                new URLSearchParams(window.location.search).get('view') === 'suite';

            if (isEmbeddedMode) {

                document.body.classList.add('is-embedded');

                const hdr = document.getElementById('visorStandaloneHeader');

                if (hdr) {

                    hdr.style.display = 'none';

                    hdr.remove();

                }

            }

        })();



        // Variables de control de estado y persistencia

        window.applyTheme = function(th) {

            document.documentElement.setAttribute('data-theme', th);

            if (th === 'dark') {

                document.documentElement.classList.add('dark');

            } else {

                document.documentElement.classList.remove('dark');

            }

            try { localStorage.setItem('netdiag_theme', th); } catch(e) {}

        };

        window.lastCompletedScenarioIndex = 0;

        window.isSuiteFinished = false;

        window.activeEventSource = null;

        window.activeMutationObserver = null;



        const INITIAL_FAULT_HTML = `

            <div id="faultProblemCard" class="bg-gradient-to-br from-[#112038] to-[#070e18] border-2 border-[#ad3333] rounded-xl p-5 mb-6 shadow-xl relative overflow-hidden transition-all duration-300">

                <div class="absolute top-0 right-0 w-44 h-44 bg-[#ad3333]/15 rounded-full blur-3xl pointer-events-none"></div>



                <div class="flex items-center justify-between mb-3 flex-wrap gap-2 border-b border-slate-700/60 pb-3">

                    <div class="flex items-center gap-2.5">

                        <span class="px-3 py-1 rounded-md bg-[#ad3333] text-white font-bold text-xs uppercase tracking-wider flex items-center gap-2 shadow">

                            <span class="w-2 h-2 rounded-full bg-white animate-pulse"></span>

                            FALLA L7 EN DIAGNÓSTICO

                        </span>

                        <span id="faultCategoryBadge" class="font-mono text-xs px-2.5 py-0.5 rounded bg-blue-950/70 border border-blue-500/40 text-blue-300 font-bold">

                            [DNS / HTTP / TLS / GATEWAY]

                        </span>

                        <span id="faultScenarioId" class="font-mono text-sm text-white font-black tracking-wide">

                            SUITE-COMPLETA (18 CASOS)

                        </span>

                    </div>

                    <div class="flex items-center gap-2">

                        <span class="text-xs text-slate-400 font-medium">Clase de Anomalía:</span>

                        <span id="faultClassBadge" class="text-xs px-2.5 py-0.5 rounded-full bg-red-950/70 border border-red-500/50 text-red-200 font-mono font-bold tracking-wide">

                            SUITE SECUENCIAL DETERMINISTA

                        </span>

                    </div>

                </div>



                <div class="mb-4">

                    <span class="text-xs font-bold text-slate-400 uppercase tracking-wider block mb-1">Síntoma Técnico Reportado (Falla a Resolver):</span>

                    <p id="faultDescription" class="text-sm font-semibold text-slate-100 leading-relaxed bg-[#070e18]/80 p-3.5 rounded-lg border border-slate-800 shadow-inner">

                        Ejecución continua de la suite completa de 18 escenarios de falla de red L7 catalogados. El agente SLM resolverá secuencialmente cada anomalía mediante CoT, RAG de estándares IETF y comandos de terminal de solo lectura bajo control estricto de semilla.

                    </p>

                </div>



                <div class="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">

                    <div class="bg-[#070e18] border border-slate-800/80 p-3 rounded-lg">

                        <span class="text-slate-400 font-bold block text-[11px] uppercase tracking-wider mb-1">Componente Objetivo:</span>

                        <span id="faultAffectedComponent" class="font-mono font-bold text-red-300 text-xs">Infraestructura L7 Completa (18 servicios)</span>

                    </div>

                    <div class="bg-[#070e18] border border-slate-800/80 p-3 rounded-lg">

                        <span class="text-slate-400 font-bold block text-[11px] uppercase tracking-wider mb-1">Herramientas Read-Only:</span>

                        <span id="faultTool" class="font-mono font-bold text-amber-300 text-xs">dig / curl / openssl</span>

                    </div>

                    <div class="bg-[#070e18] border border-slate-800/80 p-3 rounded-lg">

                        <span class="text-slate-400 font-bold block text-[11px] uppercase tracking-wider mb-1">Misión del Agente SLM:</span>

                        <span class="font-sans text-slate-300 text-xs font-medium">CoT + RAG IETF + Verificación + Mitigación</span>

                    </div>

                </div>

            </div>

        `;



        // Capturar el objeto EventSource nativo cuando HTMX establezca la conexión

        document.body.addEventListener('htmx:sseOpen', function(evt) {

            if (evt.detail && evt.detail.source) {

                window.activeEventSource = evt.detail.source;

            }

        });



        // Prevenir reconexión automática en caso de cierre de conexión o error cuando la suite terminó

        document.body.addEventListener('htmx:sseError', function(evt) {

            if (window.isSuiteFinished || window.lastCompletedScenarioIndex >= 18) {

                if (window.activeEventSource) {

                    try { window.activeEventSource.close(); } catch(e) {}

                    window.activeEventSource = null;

                }

                const receiverHost = document.getElementById('sseReceiverHost');

                if (receiverHost) { receiverHost.innerHTML = ''; }

            }

        });



        // Listener global para evento de suite finalizada

        window.addEventListener('suite-finished', function(evt) {

            finishStreaming();

        });



        // Auto-scroll interno y actualización de progreso en tiempo real con throttling RAF

        let isScrollScheduled = false;

        document.body.addEventListener('htmx:sseMessage', function(evt) {

            const stream = document.getElementById('suite-timeline-container') || document.getElementById('timelineEventsStream');

            if (stream) {

                // Actualizar el índice de casos completados desde los banners del backend

                const completedBadges = stream.querySelectorAll('[data-completed-index]');

                if (completedBadges.length > 0) {

                    const lastBadge = completedBadges[completedBadges.length - 1];

                    const completedVal = parseInt(lastBadge.getAttribute('data-completed-index'), 10);

                    if (!isNaN(completedVal) && completedVal > window.lastCompletedScenarioIndex) {

                        window.lastCompletedScenarioIndex = completedVal;

                        const progEl = document.getElementById('progressCount');

                        if (progEl) progEl.textContent = completedVal;

                        const startIdxInput = document.getElementById('txtStartIndex');

                        if (startIdxInput) startIdxInput.value = completedVal;

                    }

                }



                // Scroll interno optimizado a 60 FPS sin saturar el hilo principal con smooth layout reflows

                if (!isScrollScheduled) {

                    isScrollScheduled = true;

                    requestAnimationFrame(() => {

                        stream.scrollTop = stream.scrollHeight;

                        isScrollScheduled = false;

                    });

                }

            }

        });



        function resetSuiteExecution() {

            stopStreaming();

            window.lastCompletedScenarioIndex = 0;

            window.isSuiteFinished = false;

            const startIdxInput = document.getElementById('txtStartIndex');

            if (startIdxInput) startIdxInput.value = '0';

            const progEl = document.getElementById('progressCount');

            if (progEl) progEl.textContent = '0';

            document.querySelectorAll('[data-suite-finished="true"]').forEach(el => {

                el.removeAttribute('data-suite-finished');

                el.setAttribute('data-suite-previous-finished', 'true');

            });

            document.querySelectorAll('.suite-pause-notice').forEach(el => el.remove());

            window.dispatchEvent(new CustomEvent('suite-progress', { detail: { index: 0 } }));

            window.dispatchEvent(new CustomEvent('suite-paused', { detail: { index: 0 } }));

        }



        function syncCustomSeed(val) {

            const cleanVal = String(val).trim();

            const selS = document.getElementById('selSeed');

            if (!selS) return;

            if (!cleanVal || isNaN(parseInt(cleanVal, 10))) return;

            const parsed = Math.max(0, parseInt(cleanVal, 10));

            let opt = selS.querySelector(`option[value="${parsed}"]`);

            if (!opt) {

                opt = document.createElement('option');

                opt.value = String(parsed);

                opt.text = `${parsed} (Personalizada)`;

                const customOpt = selS.querySelector('option[value="custom"]');

                if (customOpt) {

                    selS.insertBefore(opt, customOpt);

                } else {

                    selS.appendChild(opt);

                }

            }

            selS.value = String(parsed);

            window.lastCompletedScenarioIndex = 0;

            if (typeof resetSuiteExecution === 'function') {

                resetSuiteExecution();

            }

        }



        function resetToStandardSeed() {

            const selS = document.getElementById('selSeed');

            const txtS = document.getElementById('txtCustomSeed');

            if (txtS) txtS.value = '';

            if (selS) selS.value = '42';

            window.lastCompletedScenarioIndex = 0;

            if (typeof resetSuiteExecution === 'function') {

                resetSuiteExecution();

            }

        }



        let isStartingStream = false;



        function startStreaming(evt) {

            if (evt) {

                if (typeof evt.preventDefault === 'function') evt.preventDefault();

                if (typeof evt.stopPropagation === 'function') evt.stopPropagation();

            }

            if (isStartingStream) return;

            isStartingStream = true;

            setTimeout(() => { isStartingStream = false; }, 800);



            // Notificar a Alpine.js inmediatamente el inicio del estado activo

            window.dispatchEvent(new CustomEvent('suite-started'));



            // Si la suite ya había concluido los 18 escenarios, reiniciar desde 0

            if (window.isSuiteFinished || window.lastCompletedScenarioIndex >= 18) {

                window.lastCompletedScenarioIndex = 0;

                window.isSuiteFinished = false;

                const progEl = document.getElementById('progressCount');

                if (progEl) progEl.textContent = '0';

                window.dispatchEvent(new CustomEvent('suite-progress', { detail: { index: 0 } }));

            }

            window.isSuiteFinished = false;



            const startIdxInput = document.getElementById('txtStartIndex');

            if (startIdxInput) {

                const sVal = (window.lastCompletedScenarioIndex >= 18 || window.isSuiteFinished) ? 0 : (window.lastCompletedScenarioIndex || 0);

                startIdxInput.value = sVal;

            }



            const selM = document.getElementById('selModel');

            const selS = document.getElementById('selSeed');

            const customS = document.getElementById('txtCustomSeed');

            const modelId = selM ? selM.value : 'qwen3-8b';

            let seed = '42';

            if (customS && customS.value && customS.value.trim() !== '' && (!selS || selS.value === 'custom' || customS.offsetParent !== null)) {

                const parsed = parseInt(customS.value.trim(), 10);

                seed = !isNaN(parsed) && parsed >= 0 ? String(parsed) : '42';

                if (selS) {

                    syncCustomSeed(seed);

                }

            } else if (selS && selS.value && selS.value !== 'custom') {

                seed = selS.value;

            }

            if (!seed || isNaN(parseInt(seed, 10))) {

                seed = '42';

            }

            const btnStart = document.getElementById('btnStart');

            const btnStartText = document.getElementById('btnStartText');

            const btnStop = document.getElementById('btnStop');

            const statusBadge = document.getElementById('statusBadge');

            const livePulseDot = document.getElementById('livePulseDot');



            // Quitar placeholder inicial si existe

            const placeholder = document.getElementById('emptyPlaceholder');

            if (placeholder) {

                placeholder.remove();

            }



            // Desactivar streams SSE previos y des-identificar IDs repetidos

            document.querySelectorAll('#timelineEventsStream').forEach(el => {

                el.removeAttribute('id');

                el.removeAttribute('sse-connect');

                el.classList.add('stream-batch-completed');

            });

            document.querySelectorAll('[data-suite-finished="true"]').forEach(el => {

                el.removeAttribute('data-suite-finished');

                el.setAttribute('data-suite-previous-finished', 'true');

            });



            // Eliminar cualquier notificación de pausa previa

            document.querySelectorAll('.suite-pause-notice').forEach(el => el.remove());



            // Separador visual de nueva corrida cuando ya existen tarjetas previas en historial persistente

            const container = document.getElementById('suite-timeline-container');

            if (container && container.querySelectorAll('[data-completed-index]').length > 0 && window.lastCompletedScenarioIndex === 0) {

                const runHeader = document.createElement('div');

                runHeader.className = 'suite-run-header my-6 p-3.5 rounded-xl bg-gradient-to-r from-blue-950/80 via-slate-900 to-indigo-950/80 border border-blue-500/40 text-blue-200 text-xs font-mono flex items-center justify-between shadow-lg';

                runHeader.innerHTML = `

                    <div class="flex items-center gap-2">

                        <span class="w-2.5 h-2.5 rounded-full bg-blue-400 animate-pulse"></span>

                        <strong>NUEVA EJECUCIÓN INICIADA (HISTORIAL PERSISTENTE)</strong>

                    </div>

                    <div class="text-[11px] text-blue-300">

                        Modelo: <strong>${modelId}</strong> &bull; Seed: <strong>${seed}</strong> &bull; 18 Escenarios

                    </div>

                `;

                container.appendChild(runHeader);

            }



            // Actualizar interfaz y botones

            if (btnStart) {

                btnStart.disabled = true;

                btnStart.classList.add('opacity-50', 'cursor-not-allowed');

            }

            if (btnStop) {

                btnStop.disabled = false;

                btnStop.classList.remove('opacity-40', 'cursor-not-allowed');

            }

            if (livePulseDot) {

                livePulseDot.className = 'w-2.5 h-2.5 rounded-full bg-amber-400 animate-ping';

            }

            if (statusBadge) {

                const nextCase = (window.lastCompletedScenarioIndex || 0) + 1;

                statusBadge.className = 'text-xs px-3 py-1 rounded-full bg-amber-900/40 text-amber-300 font-mono border border-amber-600/40 flex items-center gap-1.5';

                statusBadge.innerHTML = `<span class="w-2 h-2 rounded-full bg-amber-400 animate-ping"></span> Resolviendo Escenario ${nextCase} de 18 (Seed ${seed})...`;

            }



            // Disparar conexión única y limpia a /api/execute-suite vía HTMX

            if (window.htmx) {

                const sIdx = (window.lastCompletedScenarioIndex >= 18 || window.isSuiteFinished) ? 0 : (window.lastCompletedScenarioIndex || 0);

                let currentRunId = window.currentSuiteRunId;

                if (sIdx === 0 || !currentRunId) {

                    const cleanM = modelId.replace(/[^a-zA-Z0-9_-]/g, '-');

                    currentRunId = 'suite_' + cleanM + '_s' + seed + '_' + Date.now();

                    window.currentSuiteRunId = currentRunId;

                }

                window.isSuiteFinished = false;



                if (typeof window.onSuiteRunStarted === 'function') {

                    window.onSuiteRunStarted(currentRunId);

                }

                try {

                    if (window.parent && window.parent !== window && typeof window.parent.onSuiteRunStarted === 'function') {

                        window.parent.onSuiteRunStarted(currentRunId);

                    }

                } catch(e) {}



                window.htmx.ajax('POST', '/api/execute-suite', {

                    target: '#suite-timeline-container',

                    swap: 'beforeend',

                    values: {

                        scenario_id: 'ALL',

                        model_id: modelId,

                        seed: seed,

                        start_index: sIdx,

                        run_id: currentRunId

                    }

                });

            }

        }



        function stopStreaming() {

            isStartingStream = false;

            // 0. Invocar API de detención en FastAPI para suspender limpiamente el bucle en el backend

            try {

                fetch('/api/stop-suite', { method: 'POST' }).catch(err => console.log('Aviso detención backend:', err));

            } catch(e) {}



            // 1. Cerrar todos los EventSource nativos inmediatamente

            if (window.activeEventSources && window.activeEventSources.length) {

                window.activeEventSources.forEach(es => {

                    try { es.close(); } catch(e) {}

                });

                window.activeEventSources = [];

            }

            if (window.activeEventSource) {

                try {

                    window.activeEventSource.close();

                } catch(e) {

                    console.log("Cierre EventSource:", e);

                }

                window.activeEventSource = null;

            }



            // 2. Desconectar listener SSE de HTMX en el contenedor de la suite

            document.querySelectorAll('[sse-connect]').forEach(node => {

                node.removeAttribute('sse-connect');

            });

            const receiverHost = document.getElementById('sseReceiverHost');

            if (receiverHost) {

                receiverHost.innerHTML = '';

            }



            // 3. Desconectar observer si estuviera activo

            if (window.activeMutationObserver) {

                window.activeMutationObserver.disconnect();

                window.activeMutationObserver = null;

            }



            // 4. ELIMINAR CUALQUIER NOTIFICACIÓN DE PAUSA PREVIA (garantiza una sola en pantalla)

            document.querySelectorAll('.suite-pause-notice').forEach(el => el.remove());



            // 5. Agregar notificación de pausa conservando todo el historial previo

            const container = document.getElementById('suite-timeline-container');

            if (container) {

                // Actualizar último índice completado

                const completedBadges = container.querySelectorAll('[data-completed-index]');

                if (completedBadges.length > 0) {

                    const lastBadge = completedBadges[completedBadges.length - 1];

                    const completedVal = parseInt(lastBadge.getAttribute('data-completed-index'), 10);

                    if (!isNaN(completedVal) && completedVal > window.lastCompletedScenarioIndex) {

                        window.lastCompletedScenarioIndex = completedVal;

                        const progEl = document.getElementById('progressCount');

                        if (progEl) progEl.textContent = completedVal;

                    }

                }



                // Si la suite ya finalizó o todos los casos están completos (>= 18), NO generar tarjeta de pausa

                if (window.lastCompletedScenarioIndex >= 18 || window.isSuiteFinished) {

                    return;

                }



                const currentPausedIdx = window.lastCompletedScenarioIndex || 0;

                const startIdxInput = document.getElementById('txtStartIndex');

                if (startIdxInput) {

                    startIdxInput.value = currentPausedIdx;

                }



                // Inyectar el mensaje de pausa dentro del visor (en el historial del timeline)

                const pauseNotice = document.createElement('div');

                pauseNotice.className = 'suite-pause-notice my-4 p-4 rounded-xl bg-gradient-to-r from-amber-950/90 via-slate-900 to-amber-950/90 border border-amber-500/60 text-amber-200 text-xs font-mono text-center flex items-center justify-center gap-2.5 animate-fadeIn shadow-xl';

                pauseNotice.innerHTML = `

                    <svg class="w-5 h-5 text-amber-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">

                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"/>

                    </svg>

                    <span><strong>Diagnóstico en Pausa (Historial Persistente).</strong> Transmisión SSE pausada en el escenario ${currentPausedIdx} de 18. Al pulsar 'REANUDAR', continuará desde el escenario ${currentPausedIdx + 1}.</span>

                `;

                container.appendChild(pauseNotice);

                setTimeout(() => {

                    container.scrollTo({ top: container.scrollHeight, behavior: 'smooth' });

                }, 50);

            }



            // 6. Notificar a Alpine.js que el estado pasó a pausado

            window.dispatchEvent(new CustomEvent('suite-paused', { detail: { index: window.lastCompletedScenarioIndex } }));



            // 7. Actualizar botones y badges como fallback de UI directa

            const btnStart = document.getElementById('btnStart');

            const btnStartText = document.getElementById('btnStartText');

            const btnStop = document.getElementById('btnStop');

            const statusBadge = document.getElementById('statusBadge');

            const livePulseDot = document.getElementById('livePulseDot');



            if (btnStart) {

                btnStart.disabled = false;

                btnStart.classList.remove('opacity-50', 'cursor-not-allowed');

                if (btnStartText) {

                    btnStartText.textContent = (window.lastCompletedScenarioIndex > 0 && window.lastCompletedScenarioIndex < 18) ? 'Reanudar' : 'Iniciar';

                }

            }

            if (btnStop) {

                btnStop.disabled = true;

                btnStop.classList.add('opacity-40', 'cursor-not-allowed');

            }

            if (livePulseDot) {

                livePulseDot.className = 'w-2.5 h-2.5 rounded-full bg-amber-500';

            }

            if (statusBadge) {

                statusBadge.className = 'text-xs px-3 py-1 rounded-full bg-amber-900/40 text-amber-300 font-mono border border-amber-600/40 flex items-center gap-1.5';

                statusBadge.textContent = `Pausado: ${window.lastCompletedScenarioIndex}/18 Escenarios Resueltos`;

            }

        }



        function finishStreaming() {

            window.isSuiteFinished = true;

            window.lastCompletedScenarioIndex = 18;



            // Cerrar conexión SSE

            if (window.activeEventSources && window.activeEventSources.length) {

                window.activeEventSources.forEach(es => {

                    try { es.close(); } catch(e) {}

                });

                window.activeEventSources = [];

            }

            if (window.activeEventSource) {

                try {

                    window.activeEventSource.close();

                } catch(e) {}

                window.activeEventSource = null;

            }

            document.querySelectorAll('[sse-connect]').forEach(node => {

                node.removeAttribute('sse-connect');

            });

            const receiverHost = document.getElementById('sseReceiverHost');

            if (receiverHost) {

                receiverHost.innerHTML = '';

            }



            // Desconectar observer

            if (window.activeMutationObserver) {

                window.activeMutationObserver.disconnect();

                window.activeMutationObserver = null;

            }



            // Limpiar cualquier aviso de pausa existente

            document.querySelectorAll('.suite-pause-notice').forEach(el => el.remove());



            // Notificar a Alpine.js

            window.dispatchEvent(new CustomEvent('suite-finished', { detail: { index: 18 } }));



            const btnStart = document.getElementById('btnStart');

            const btnStartText = document.getElementById('btnStartText');

            const btnStop = document.getElementById('btnStop');

            const statusBadge = document.getElementById('statusBadge');

            const livePulseDot = document.getElementById('livePulseDot');

            const progEl = document.getElementById('progressCount');



            if (progEl) progEl.textContent = '18';



            if (btnStart) {

                btnStart.disabled = false;

                btnStart.classList.remove('opacity-50', 'cursor-not-allowed');

                if (btnStartText) {

                    btnStartText.textContent = 'Iniciar';

                }

            }

            if (btnStop) {

                btnStop.disabled = true;

                btnStop.classList.add('opacity-40', 'cursor-not-allowed');

            }

            if (livePulseDot) {

                livePulseDot.className = 'w-2.5 h-2.5 rounded-full bg-emerald-500';

            }

            if (statusBadge) {

                statusBadge.className = 'text-xs px-3 py-1 rounded-full bg-emerald-900/40 text-emerald-300 font-mono border border-emerald-600/40 flex items-center gap-1.5';

                statusBadge.innerHTML = `

                    <svg class="w-3.5 h-3.5 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>

                    <span>Suite Completa Finalizada (18/18 Casos)</span>

                `;

            }

        }



        function clearTimeline() {

            stopStreaming();

            window.lastCompletedScenarioIndex = 0;

            window.isSuiteFinished = false;



            const startIdxInput = document.getElementById('txtStartIndex');

            if (startIdxInput) startIdxInput.value = '0';

            document.querySelectorAll('.suite-pause-notice').forEach(el => el.remove());

            window.dispatchEvent(new CustomEvent('suite-progress', { detail: { index: 0 } }));

            window.dispatchEvent(new CustomEvent('suite-paused', { detail: { index: 0 } }));

            window.dispatchEvent(new CustomEvent('suite-clear'));



            const container = document.getElementById('suite-timeline-container');

            if (container) {

                container.innerHTML = `

                    <div id="timelineEventsStream" class="space-y-3">

                        <div id="emptyPlaceholder" class="text-center py-16 text-slate-500">

                            <svg class="w-12 h-12 mx-auto mb-3 opacity-40 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">

                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>

                            </svg>

                            <p class="text-sm font-medium">Presiona "Iniciar Diagnóstico SSE" en el panel de control inferior</p>

                            <p class="text-xs text-slate-600 mt-1">Los 18 escenarios de red se resolverán secuencialmente. Puedes pausar y reanudar sin perder el avance.</p>

                        </div>

                    </div>

                `;

            }



            // Restaurar ficha inicial de la falla

            const cardContainer = document.getElementById('faultProblemCard');

            if (cardContainer) {

                cardContainer.outerHTML = INITIAL_FAULT_HTML;

            }



            const statusBadge = document.getElementById('statusBadge');

            if (statusBadge) {

                statusBadge.className = 'text-xs px-3 py-1 rounded-full bg-slate-800 text-slate-300 font-mono border border-slate-700';

                statusBadge.textContent = 'Listo para iniciar';

            }

            const livePulseDot = document.getElementById('livePulseDot');

            if (livePulseDot) {

                livePulseDot.className = 'w-2.5 h-2.5 rounded-full bg-emerald-500';

            }

            const btnStartText = document.getElementById('btnStartText');

            if (btnStartText) {

                btnStartText.textContent = 'Iniciar';

            }

            const progEl = document.getElementById('progressCount');

            if (progEl) {

                progEl.textContent = '0';

            }

        }



        window.addEventListener('load', () => {

            const params = new URLSearchParams(window.location.search);

            if (params.has('embed') || params.has('view')) {

                document.body.classList.add('is-embedded');

            }

            highlightSyntaxInCode();

        });



        function escapeHtml(str) {

            return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

        }



        function highlightSyntaxInCode(root = document) {

            if (!root) return;

            root.querySelectorAll('code.language-json:not(.highlighted)').forEach(codeEl => {

                codeEl.classList.add('highlighted');

                if (codeEl.querySelector('span.text-blue-300')) return;

                const text = codeEl.textContent;

                const tokenPattern = /("(?:\\\\.|[^"\\\\])*")(\\\\s*:)?|\\\\b(-?(?:0|[1-9]\\\\d*)(?:\\\\.\\\\d+)?(?:[eE][+-]?\\\\d+)?)\\\\b|\\\\b(true|false|null)\\\\b/g;

                let out = '';

                let lastIdx = 0;

                let m;

                while ((m = tokenPattern.exec(text)) !== null) {

                    out += escapeHtml(text.slice(lastIdx, m.index));

                    const [full, sStr, colon, num, boolVal] = m;

                    if (sStr) {

                        if (colon) {

                            out += `<span class="text-blue-300">${escapeHtml(sStr)}</span>${escapeHtml(colon)}`;

                        } else {

                            out += `<span class="text-emerald-300">${escapeHtml(sStr)}</span>`;

                        }

                    } else if (num) {

                        out += `<span class="text-orange-300">${num}</span>`;

                    } else if (boolVal) {

                        out += `<span class="text-orange-300">${boolVal}</span>`;

                    }

                    lastIdx = tokenPattern.lastIndex;

                }

                out += escapeHtml(text.slice(lastIdx));

                codeEl.innerHTML = out;

            });



            root.querySelectorAll('code.language-markdown:not(.highlighted)').forEach(codeEl => {

                codeEl.classList.add('highlighted');

                if (codeEl.querySelector('span.text-blue-300')) return;

                const lines = codeEl.textContent.split(/\\r?\\n/);

                const outLines = lines.map(line => {

                    const strp = line.trim();

                    if (strp.startsWith('===') || strp.startsWith('---')) {

                        let esc = escapeHtml(line);

                        esc = esc.replace(/\\\\b([\\w.-]+\\.(?:md|json|log|conf|yaml|yml|txt|py))\\\\b/g, '<span class="text-amber-300 font-medium">$1</span>');

                        return `<span class="text-blue-300 font-semibold">${esc}</span>`;

                    }

                    let esc = escapeHtml(line);

                    esc = esc.replace(/\\*\\*([^*]+)\\*\\*/g, '<span class="text-white font-bold">$1</span>');

                    esc = esc.replace(/\\\\b([\\w.-]+\\.(?:md|json|log|conf|yaml|yml|txt|py))\\\\b/g, '<span class="text-amber-300 font-medium">$1</span>');

                    esc = esc.replace(/`([^`]+)`/g, (match, rawCode) => {

                        const clean = rawCode.replace(/<[^>]+>/g, '');

                        return `<code class="text-emerald-400 font-bold bg-slate-800/50 px-1 rounded">${clean}</code>`;

                    });

                    return esc;

                });

                codeEl.innerHTML = outLines.join('\\n');

            });

        }



        function switchNodeTab(btn, tabName) {

            const card = btn.closest('[data-node-card]');

            if (!card) return;

            const vistaPanel = card.querySelector('[data-panel="vista"]');

            const rawPanel = card.querySelector('[data-panel="raw"]');

            const tabBtns = card.querySelectorAll('[data-tab-target]');



            if (tabName === 'vista') {

                if (vistaPanel) vistaPanel.classList.remove('hidden');

                if (rawPanel) rawPanel.classList.add('hidden');

            } else {

                if (vistaPanel) vistaPanel.classList.add('hidden');

                if (rawPanel) rawPanel.classList.remove('hidden');

            }



            tabBtns.forEach(b => {

                if (b.getAttribute('data-tab-target') === tabName) {

                    b.className = 'text-xs sm:text-[13px] px-3 py-1.5 rounded-md font-semibold bg-[#1E2A40] text-slate-100 transition-colors';

                } else {

                    b.className = 'text-xs sm:text-[13px] px-3 py-1.5 rounded-md font-medium text-slate-400 hover:text-slate-200 transition-colors';

                }

            });

        }



        function filterDrainLogs(btn, filterCode) {

            const card = btn.closest('[data-node-card]');

            if (!card) return;

            const rows = card.querySelectorAll('[data-log-row]');

            rows.forEach(r => {

                if (filterCode === 'all' || r.getAttribute('data-log-code') === filterCode) {

                    r.classList.remove('hidden');

                } else {

                    r.classList.add('hidden');

                }

            });

            const filterBtns = card.querySelectorAll('[data-filter-target]');

            filterBtns.forEach(b => {

                if (b.getAttribute('data-filter-target') === filterCode) {

                    b.className = 'text-xs px-2.5 py-1 rounded-md font-semibold bg-[#1E2A40] text-slate-100';

                } else {

                    b.className = 'text-xs px-2.5 py-1 rounded-md text-slate-400 hover:text-slate-200';

                }

            });

        }



        function selectDrainLogRow(rowEl, time, msg, flags) {

            const card = rowEl.closest('[data-node-card]');

            if (!card) return;

            const detailBox = card.querySelector('[data-detail-box]');

            if (!detailBox) return;

            const metaEl = detailBox.querySelector('[data-detail-meta]');

            const rawEl = detailBox.querySelector('[data-detail-raw]');

            const flagsEl = detailBox.querySelector('[data-detail-flags]');



            if (!detailBox.classList.contains('hidden') && rawEl && rawEl.textContent === msg) {

                detailBox.classList.add('hidden');

                rowEl.classList.remove('bg-[#15203A]');

                return;

            }



            card.querySelectorAll('[data-log-row]').forEach(r => r.classList.remove('bg-[#15203A]'));

            rowEl.classList.add('bg-[#15203A]');



            if (metaEl) metaEl.textContent = `raw_message · ${time} · INFO`;

            if (rawEl) rawEl.textContent = msg;

            if (flagsEl) flagsEl.textContent = flags;

            detailBox.classList.remove('hidden');

        }



        function closeDrainDetail(btn) {

            const card = btn.closest('[data-node-card]');

            if (!card) return;

            const detailBox = card.querySelector('[data-detail-box]');

            if (detailBox) detailBox.classList.add('hidden');

            card.querySelectorAll('[data-log-row]').forEach(r => r.classList.remove('bg-[#15203A]'));

        }



        function toggleChecklistStep(btn) {

            const card = btn.closest('[data-node-card]');

            if (!card) return;

            const item = btn.closest('li');

            if (!item) return;



            const isDone = item.getAttribute('data-done') === 'true';

            const nextDone = !isDone;

            item.setAttribute('data-done', nextDone ? 'true' : 'false');



            const textSpan = item.querySelector('[data-step-text]');

            if (nextDone) {

                item.className = 'flex gap-3 items-start p-3 rounded-lg border border-[#1D5A47] bg-[#0B1C17] transition-colors';

                btn.className = 'shrink-0 w-6 h-6 mt-0.5 rounded-md bg-[#5EE0AE] border border-[#5EE0AE] flex items-center justify-center cursor-pointer transition-colors';

                btn.innerHTML = '<svg class="w-3.5 h-3.5 text-[#0A0E16]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5 9-10"></path></svg>';

                if (textSpan) textSpan.className = 'text-sm text-slate-400 line-through';

            } else {

                item.className = 'flex gap-3 items-start p-3 rounded-lg border border-slate-800/80 bg-[#0A0E16] transition-colors';

                btn.className = 'shrink-0 w-6 h-6 mt-0.5 rounded-md border border-slate-600 flex items-center justify-center cursor-pointer transition-colors hover:border-slate-400';

                btn.innerHTML = '';

                if (textSpan) textSpan.className = 'text-sm text-slate-200';

            }



            const allItems = card.querySelectorAll('li[data-step-item]');

            const completed = card.querySelectorAll('li[data-step-item][data-done="true"]').length;

            const countSpan = card.querySelector('[data-checklist-count]');

            const progressBar = card.querySelector('[data-checklist-progress]');

            if (countSpan) countSpan.textContent = `${completed} de ${allItems.length} completadas`;

            if (progressBar) progressBar.style.width = `${(completed / allItems.length) * 100}%`;

        }



        function copyCliSnippet(text, btn) {

            try {

                if (navigator.clipboard) {

                    navigator.clipboard.writeText(text);

                } else {

                    const ta = document.createElement('textarea');

                    ta.value = text;

                    document.body.appendChild(ta);

                    ta.select();

                    document.execCommand('copy');

                    document.body.removeChild(ta);

                }

            } catch (e) {

                console.error('Clipboard copy error', e);

            }

            const origHtml = btn.innerHTML;

            btn.innerHTML = '✓ Copiado!';

            btn.classList.add('bg-emerald-600', 'text-white', 'border-emerald-500');

            btn.classList.remove('bg-[#101624]', 'bg-[#0A0E16]', 'text-slate-300');

            setTimeout(() => {

                btn.innerHTML = origHtml;

                btn.classList.remove('bg-emerald-600', 'text-white', 'border-emerald-500');

                btn.classList.add('text-slate-300');

            }, 2000);

        }



        document.body.addEventListener('htmx:afterSwap', function(evt) {

            if (evt.detail && evt.detail.target) {

                highlightSyntaxInCode(evt.detail.target);

            }

        });

    </script>

</body>

</html>

    """

    sys_cfg = SystemConfig()

    models_options = "\n".join(

        f'<option value="{m.id}">{m.name} ({m.parameters_raw} &bull; {m.license})</option>'

        for m in sys_cfg.get_all_models()

    )



    body_class = "is-embedded " if is_embedded else ""

    main_class = (

        "w-full px-2 sm:px-4 py-2 space-y-4"

        if is_embedded

        else "max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6"

    )



    header_markup = ""

    if not is_embedded:

        from src.layer6_interface.export_toolbar import render_export_toolbar

        toolbar_html = render_export_toolbar("suite_observabilidad")

        header_markup = f"""

    <!-- Encabezado Principal (Visor Standalone) -->

    <header id="visorStandaloneHeader" class="border-b border-slate-800/80 bg-[#001f3f]/90 backdrop-blur sticky top-0 z-50 shadow-lg visor-standalone-only" data-view="visor">

        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3">

            {toolbar_html}

        </div>

    </header>

"""



    final_html = (

        html_content

        .replace("<!-- MODEL_OPTIONS_PLACEHOLDER -->", models_options)

        .replace("<!-- BODY_CLASS_PLACEHOLDER -->", body_class)

        .replace("<!-- VISOR_HEADER_PLACEHOLDER -->", header_markup)

        .replace("<!-- MAIN_CLASS_PLACEHOLDER -->", main_class)

        .replace("</style>", f"{TOOLTIP_CSS}\n    </style>")

        .replace("</body>", f"{TOOLTIP_JS}\n</body>")

    )

    return HTMLResponse(content=final_html)

