"""
NetDiagBench-L7: Layer 8 - Paquete Ciego de Fichas para Evaluación Humana (exporter_packet.py)
Genera el paquete HTML autocontenido (Paquete_Experto_<ID>_<sesion>.html) con portada,
etiqueta del experto y 54 fichas ciegas de diagnóstico con diseño neutro.
Garantiza cero fugas de marcas de modelos, proveedores y telemetría sensible.
"""

import html
from pathlib import Path
from typing import Any

from src.core.contracts import CorridaAnonimizada, EtiquetaExperto
from src.layer8_human_eval.sampler import (
    anonymize_text,
    check_forbidden_terms,
)

HTML_STYLE = """
<style>
  :root {
    --primary: #B03535;
    --primary-dark: #8F2B2B;
    --navy: #1E293B;
    --bg-light: #F8FAFC;
    --card-bg: #FFFFFF;
    --border: #E2E8F0;
    --text-main: #0F172A;
    --text-muted: #475569;
    --code-bg: #0F172A;
    --code-text: #38BDF8;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: Arial, Helvetica, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background-color: var(--bg-light);
    color: var(--text-main);
    line-height: 1.5;
    padding: 24px;
  }
  .container { max-width: 980px; margin: 0 auto; }
  
  /* Portada */
  .portada {
    background: var(--card-bg);
    border: 2px solid var(--primary);
    border-radius: 8px;
    padding: 36px;
    margin-bottom: 40px;
    page-break-after: always;
  }
  .header-banner {
    border-bottom: 2px solid var(--primary);
    padding-bottom: 16px;
    margin-bottom: 24px;
  }
  .header-banner h1 {
    font-size: 24px;
    color: var(--primary);
    margin-bottom: 6px;
  }
  .header-banner p {
    font-size: 13px;
    color: var(--text-muted);
  }
  .etiqueta-box {
    background: #FFF5F5;
    border: 1px solid #FECACA;
    border-radius: 6px;
    padding: 20px;
    margin: 20px 0;
  }
  .etiqueta-title {
    font-size: 14px;
    font-weight: bold;
    color: var(--primary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 12px;
  }
  .grid-2 {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    font-size: 13px;
  }
  .grid-full {
    grid-column: 1 / -1;
  }
  .field-label { font-weight: bold; color: var(--navy); }
  .field-value { color: var(--text-main); word-break: break-all; }
  .hash-code { font-family: monospace; font-size: 11px; background: #E2E8F0; padding: 2px 6px; border-radius: 4px; }
  
  .instrucciones-box {
    margin-top: 24px;
    font-size: 13px;
    color: var(--text-muted);
    border-left: 3px solid var(--primary);
    padding-left: 16px;
  }
  .instrucciones-box ol { margin-left: 18px; margin-top: 8px; }
  .instrucciones-box li { margin-bottom: 6px; }

  /* Fichas */
  .card {
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 24px;
    margin-bottom: 32px;
    page-break-after: always;
  }
  .card:last-child { page-break-after: auto; }
  
  .card-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 2px solid var(--border);
    padding-bottom: 12px;
    margin-bottom: 16px;
  }
  .card-badge {
    background: var(--primary);
    color: #FFFFFF;
    font-weight: bold;
    font-size: 16px;
    padding: 4px 12px;
    border-radius: 4px;
    letter-spacing: 1px;
  }
  .card-counter {
    font-size: 13px;
    font-weight: bold;
    color: var(--text-muted);
  }
  
  .section-title {
    font-size: 13px;
    font-weight: bold;
    color: var(--navy);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin: 16px 0 8px 0;
    border-bottom: 1px solid var(--border);
    padding-bottom: 4px;
  }
  
  .info-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
    margin-bottom: 16px;
  }
  .info-table th, .info-table td {
    border: 1px solid var(--border);
    padding: 8px 12px;
    vertical-align: top;
  }
  .info-table th {
    background: var(--bg-light);
    color: var(--navy);
    font-weight: bold;
    width: 25%;
  }
  
  .steps-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
    margin-bottom: 16px;
  }
  .steps-table th, .steps-table td {
    border: 1px solid var(--border);
    padding: 8px 10px;
    vertical-align: top;
  }
  .steps-table th {
    background: var(--navy);
    color: #FFFFFF;
    font-size: 11px;
    text-transform: uppercase;
  }
  
  pre.code-block {
    background: #0F172A;
    color: #F8FAFC;
    padding: 8px 12px;
    border-radius: 4px;
    font-family: Consolas, Monaco, "Courier New", monospace;
    font-size: 11px;
    white-space: pre-wrap;
    word-break: break-all;
    max-height: 220px;
    overflow-y: auto;
  }
  
  .verdict-box {
    background: #F8FAFC;
    border: 1px solid #CBD5E1;
    border-radius: 6px;
    padding: 14px;
    font-size: 13px;
  }
  .verdict-item { margin-bottom: 10px; }
  .verdict-item:last-child { margin-bottom: 0; }
  .verdict-label { font-weight: bold; color: var(--navy); display: block; margin-bottom: 2px; }
  
  @media print {
    body { padding: 0; background: #FFFFFF; font-size: 11pt; }
    .container { max-width: 100%; }
    .card, .portada { border: 1px solid #94A3B8; box-shadow: none; margin-bottom: 0; }
    pre.code-block { max-height: none; }
  }
</style>
"""


def render_card_html(card: CorridaAnonimizada, position: int, total: int) -> str:
    """Renderiza una ficha ciega individual en formato HTML neutro."""
    esc = html.escape

    # Pasos de herramientas
    steps_rows = ""
    for idx, s in enumerate(card.pasos_herramienta, start=1):
        cmd_escaped = esc(s.get("comando", ""))
        out_escaped = esc(s.get("salida", ""))
        hyp_escaped = esc(s.get("hipotesis", ""))
        tool_name = esc(s.get("herramienta", "network_tool"))

        steps_rows += f"""
        <tr>
          <td style="text-align: center; font-weight: bold; width: 40px;">{idx}</td>
          <td style="font-weight: bold; width: 110px;">{tool_name}</td>
          <td>
            <div style="font-weight: bold; margin-bottom: 4px; font-size: 11px;">Comando:</div>
            <pre class="code-block">{cmd_escaped}</pre>
            <div style="font-weight: bold; margin: 6px 0 4px 0; font-size: 11px;">Salida recibida:</div>
            <pre class="code-block" style="background: #1E293B;">{out_escaped}</pre>
            <div style="margin-top: 6px; font-size: 11px; color: #475569;"><strong>Hipótesis:</strong> {hyp_escaped}</div>
          </td>
        </tr>
        """

    if not steps_rows:
        steps_rows = """
        <tr>
          <td colspan="3" style="text-align: center; color: #64748B; padding: 12px;">
            No se requirieron herramientas de red activas para este diagnóstico (análisis de telemetría pasiva).
          </td>
        </tr>
        """

    veredicto = card.veredicto
    v_rc = esc(veredicto.get("causa_raiz", ""))
    v_comp = esc(veredicto.get("componente", ""))
    v_mit = esc(veredicto.get("mitigacion", ""))
    v_fund = esc(veredicto.get("fundamentacion", "")).replace("\n", "<br>")

    card_html = f"""
    <div class="card" id="{esc(card.codigo)}">
      <div class="card-top">
        <span class="card-badge">{esc(card.codigo)}</span>
        <span class="card-counter">Ficha {position} de {total} &bull; Escenario: {esc(card.scenario_id)}</span>
      </div>

      <!-- 1. Ficha del Escenario -->
      <div class="section-title">1. Ficha del Escenario (Contexto Operativo Ciego)</div>
      <table class="info-table">
        <tr>
          <th>Escenario Asignado</th>
          <td><strong>{esc(card.scenario_id)}</strong></td>
        </tr>
        <tr>
          <th>Síntoma Observado</th>
          <td>{esc(card.sintoma)}</td>
        </tr>
      </table>

      <!-- 2. Pasos de Verificación de Red -->
      <div class="section-title">2. Pasos de Verificación de Red (Herramientas Ejecutadas)</div>
      <table class="steps-table">
        <thead>
          <tr>
            <th style="width: 40px;">Paso</th>
            <th style="width: 110px;">Herramienta</th>
            <th>Comando, Salida e Hipótesis Evaluada</th>
          </tr>
        </thead>
        <tbody>
          {steps_rows}
        </tbody>
      </table>

      <!-- 3. Diagnóstico Emitido por el Sistema -->
      <div class="section-title">3. Diagnóstico Emitido por el Sistema (Veredicto Ciego)</div>
      <div class="verdict-box">
        <div class="verdict-item">
          <span class="verdict-label">Causa Raíz Propuesta:</span>
          <div>{v_rc}</div>
        </div>
        <div class="verdict-item">
          <span class="verdict-label">Componente Identificado:</span>
          <div>{v_comp}</div>
        </div>
        <div class="verdict-item">
          <span class="verdict-label">Mitigación Sugerida:</span>
          <div>{v_mit}</div>
        </div>
        <div class="verdict-item">
          <span class="verdict-label">Fundamentación Técnica y Normativa:</span>
          <div style="font-size: 12px; color: #334155; margin-top: 4px;">{v_fund}</div>
        </div>
      </div>
    </div>
    """
    return card_html


def export_expert_packet_html(
    etiqueta: EtiquetaExperto,
    cards: dict[str, CorridaAnonimizada],
    output_path: Path
) -> Path:
    """
    Genera el archivo Paquete_Experto_<ID>_<sesion>.html autocontenido y completamente limpio de fugas.
    """
    esc = html.escape
    total_cards = len(etiqueta.orden)

    # 1. Renderizar Portada
    portada_html = f"""
    <div class="portada">
      <div class="header-banner">
        <h1>NetDiagBench-L7 — Paquete de Evaluación Ciega</h1>
        <p>Instrumento Autocontenido de Calificación de Diagnósticos de Red L7 &bull; Estudio Inter-Evaluador</p>
      </div>

      <div class="etiqueta-box">
        <div class="etiqueta-title">Etiqueta Oficial del Evaluador</div>
        <div class="grid-2">
          <div><span class="field-label">Identificador de Experto:</span> <span class="field-value">{esc(etiqueta.expert_id)}</span></div>
          <div><span class="field-label">Rol Asignado:</span> <span class="field-value">{esc(etiqueta.rol)}</span></div>
          <div><span class="field-label">Alias Registrado:</span> <span class="field-value">{esc(etiqueta.alias)}</span></div>
          <div><span class="field-label">Identificador de Sesión:</span> <span class="field-value">{esc(etiqueta.sesion_id)}</span></div>
          <div><span class="field-label">Fecha de Emisión:</span> <span class="field-value">{esc(etiqueta.fecha_emision)}</span></div>
          <div><span class="field-label">Código de Acceso:</span> <span class="field-value" style="font-weight:bold; letter-spacing:1px;">{esc(etiqueta.codigo_acceso)}</span></div>
          <div class="grid-full">
            <span class="field-label">Huella Criptográfica SHA-256:</span><br>
            <span class="hash-code">{esc(etiqueta.huella_sha256)}</span>
          </div>
        </div>
      </div>

      <div class="instrucciones-box">
        <strong>Instrucciones para la Calificación:</strong>
        <ol>
          <li>Este paquete contiene <strong>{total_cards} fichas de diagnóstico</strong> organizadas estrictamente en el orden pseudoaleatorio correspondiente a su etiqueta.</li>
          <li>Cada ficha incluye el síntoma observado y contexto operativo del escenario, los comandos de red ejecutados en laboratorio y el veredicto diagnóstico ciego emitido por el sistema.</li>
          <li>Registre sus calificaciones en el libro de cálculo correspondiente (<code>Instrumento_Experto_{esc(etiqueta.expert_id)}_{esc(etiqueta.sesion_id)}.xlsx</code>), hoja <em>Evaluación</em>.</li>
          <li>Recuerde que si califica <strong>C1 = 0</strong> o <strong>S = No</strong>, debe justificar obligatoriamente en la columna <em>Observación</em>.</li>
        </ol>
      </div>
    </div>
    """

    # 2. Renderizar todas las fichas en el orden de la etiqueta
    cards_html_list = []
    for pos, code in enumerate(etiqueta.orden, start=1):
        card = cards.get(code)
        if not card:
            continue
        card_content = render_card_html(card, position=pos, total=total_cards)
        cards_html_list.append(card_content)

    full_cards_html = "\n".join(cards_html_list)

    full_document = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Paquete de Evaluación Ciega - Experto {esc(etiqueta.expert_id)}</title>
  {HTML_STYLE}
</head>
<body>
  <div class="container">
    {portada_html}
    {full_cards_html}
  </div>
</body>
</html>
"""

    # Post-procesamiento estricto de anonimización para asegurar cero fugas
    cleaned_doc = anonymize_text(full_document)

    # Verificación final automatizada
    leaks = check_forbidden_terms(cleaned_doc)
    if leaks:
        raise ValueError(f"Fuga crítica detectada en exportador de paquete ciego: {leaks}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(cleaned_doc)

    return output_path
