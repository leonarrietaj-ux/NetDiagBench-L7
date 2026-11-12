"""
NetDiagBench-L7: Layer 6 - Execution History Manager (In-Memory + LangGraph MemorySaver)
Almacenamiento 100% en memoria RAM para la bitácora de ejecuciones de la sesión actual.
Utiliza el MemorySaver nativo de LangGraph para guardar el estado de grafo con latencia cero.
"""

from __future__ import annotations

import html
import json
from pathlib import Path
import urllib.parse
import uuid
from datetime import datetime
from typing import Any

from langgraph.checkpoint.base import empty_checkpoint
from langgraph.checkpoint.memory import MemorySaver

from src.core.config import PROJECT_ROOT
from src.core.logger import logger

HISTORY_STATE_FILE = PROJECT_ROOT / "data" / "runs" / "bitacora_state.json"


class ExecutionHistoryManager:
    """
    Gestor en memoria (RAM) de la bitácora de ejecuciones del Visor de Observabilidad.
    Utiliza LangGraph MemorySaver para persistencia efímera del estado de grafo
    durante el ciclo de vida del proceso del servidor FastAPI.
    """

    def __init__(self, max_records: int = 150, enable_persistence: bool = False) -> None:
        self._max_records = max_records
        self._enable_persistence = enable_persistence
        self._records: list[dict[str, Any]] = []
        self._memory_saver = MemorySaver()
        self._backup_records: list[dict[str, Any]] = []
        self._backup_memory_saver: MemorySaver | None = None
        self._is_cleared: bool = False
        self._deleted_ids: set[str] = set()
        self._deleted_scenarios: set[str] = set()
        if self._enable_persistence:
            self._load_state_from_disk()

    @property
    def is_cleared(self) -> bool:
        return self._is_cleared

    @property
    def deleted_scenarios(self) -> set[str]:
        return self._deleted_scenarios

    @property
    def deleted_ids(self) -> set[str]:
        return self._deleted_ids

    @property
    def records(self) -> list[dict[str, Any]]:
        return self._records

    @property
    def memory_saver(self) -> MemorySaver:
        return self._memory_saver

    def _save_state_to_disk(self) -> None:
        if not self._enable_persistence:
            return
        try:
            HISTORY_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "records": self._records,
                "is_cleared": self._is_cleared,
                "deleted_ids": list(self._deleted_ids),
                "deleted_scenarios": list(self._deleted_scenarios),
                "updated_at": datetime.now().isoformat(),
            }
            HISTORY_STATE_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            logger.debug(f"Aviso guardando estado de bitacora en disco: {e}")

    def _load_state_from_disk(self) -> bool:
        if not self._enable_persistence or not HISTORY_STATE_FILE.exists():
            return False
        try:
            data = json.loads(HISTORY_STATE_FILE.read_text(encoding="utf-8"))
            self._is_cleared = bool(data.get("is_cleared", False))
            self._deleted_ids = set(data.get("deleted_ids", []))
            self._deleted_scenarios = set(data.get("deleted_scenarios", []))
            self._records = list(data.get("records", []))
            for record in self._records:
                r_id = record.get("id")
                if r_id:
                    try:
                        cfg = {"configurable": {"thread_id": r_id, "checkpoint_ns": ""}}
                        chk = empty_checkpoint()
                        payload = {"record": record, "full_state": {}, "rendered_html": ""}
                        chk["channel_values"] = payload
                        chk["channel_versions"] = {k: 1 for k in payload}
                        self._memory_saver.put(cfg, chk, {}, {k: 1 for k in payload})
                    except Exception:
                        pass
            return True
        except Exception as e:
            logger.debug(f"Aviso cargando estado de bitacora desde disco: {e}")
            return False

    def add_execution(
        self,
        scenario_id: str,
        model_id: str,
        seed: int,
        status: str,
        is_correct: bool,
        category: str = "RED_L7",
        fault_class: str = "",
        model_name: str | None = None,
        cot_explanation: str = "",
        root_cause_predicted: str = "",
        root_cause_expected: str = "",
        component_predicted: str = "",
        component_expected: str = "",
        suggested_action: str = "",
        tool_called: bool = False,
        tool_name: str | None = None,
        tool_command: str | None = None,
        tool_output: str | None = None,
        ttft_ms: float = 0.0,
        tok_per_sec: float = 0.0,
        latency_ms: float = 0.0,
        completion_tokens: int = 0,
        rendered_html: str = "",
        full_state: dict[str, Any] | None = None,
        exec_id: str | None = None
    ) -> dict[str, Any]:
        """
        Registra una ejecución en la lista global en memoria y crea un checkpoint
        en el MemorySaver nativo de LangGraph.
        """
        now = datetime.now()
        if not exec_id:
            uid = uuid.uuid4().hex[:8]
            clean_sc = scenario_id.replace(" ", "_")
            exec_id = f"exec-{now.strftime('%Y%m%d-%H%M%S')}-{clean_sc}-{uid}"

        record: dict[str, Any] = {
            "id": exec_id,
            "timestamp": now.strftime("%H:%M:%S"),
            "timestamp_iso": now.isoformat(),
            "modelo": model_name or model_id,
            "model_id": model_id,
            "escenario_id": scenario_id,
            "categoria": category,
            "fault_class": fault_class,
            "seed": seed,
            "status": status,
            "is_correct": is_correct,
            "tool_called": tool_called,
            "tool_name": tool_name or ("" if not tool_called else "read_only_tool"),
            "tool_command": tool_command or "",
            "tool_output": tool_output or "",
            "cot_explanation": cot_explanation,
            "root_cause_predicted": root_cause_predicted,
            "root_cause_expected": root_cause_expected,
            "component_predicted": component_predicted,
            "component_expected": component_expected,
            "suggested_action": suggested_action,
            "ttft_ms": round(float(ttft_ms), 1),
            "tok_per_sec": round(float(tok_per_sec), 1),
            "latency_ms": round(float(latency_ms), 1),
            "completion_tokens": int(completion_tokens),
        }

        # Guardar en la estructura global en memoria (FIFO con límite max_records)
        self._records.insert(0, record)
        if len(self._records) > self._max_records:
            self._records = self._records[: self._max_records]

        # Guardar estado de grafo en el MemorySaver de LangGraph
        try:
            cfg = {"configurable": {"thread_id": exec_id, "checkpoint_ns": ""}}
            chk = empty_checkpoint()
            payload = {
                "record": record,
                "full_state": full_state or {},
                "rendered_html": rendered_html
            }
            chk["channel_values"] = payload
            chk["channel_versions"] = {k: 1 for k in payload}
            self._memory_saver.put(cfg, chk, {}, {k: 1 for k in payload})
        except Exception as e:
            logger.warning(f"Error guardando checkpoint en LangGraph MemorySaver ({exec_id}): {e}")

        self._is_cleared = False
        self._deleted_scenarios.discard(scenario_id)
        self._save_state_to_disk()
        return record

    def get_execution(self, exec_id: str) -> dict[str, Any] | None:
        """
        Recupera el estado de una ejecución desde el MemorySaver de LangGraph.
        """
        try:
            cfg = {"configurable": {"thread_id": exec_id, "checkpoint_ns": ""}}
            tuple_res = self._memory_saver.get_tuple(cfg)
            if tuple_res and tuple_res.checkpoint:
                vals = tuple_res.checkpoint.get("channel_values", {})
                if vals:
                    return vals
        except Exception as e:
            logger.warning(f"Error recuperando checkpoint de LangGraph MemorySaver ({exec_id}): {e}")

        # Fallback a la lista en memoria si por alguna razón no está en MemorySaver
        rec = next((r for r in self._records if r.get("id") == exec_id), None)
        if rec:
            return {"record": rec, "rendered_html": "", "full_state": {}}
        return None

    def delete_execution(self, exec_id: str) -> bool:
        """Elimina una ejecución específica de la bitácora en memoria y del MemorySaver."""
        initial_len = len(self._records)
        del_item = next((r for r in self._records if r.get("id") == exec_id), None)
        if del_item:
            self._deleted_ids.add(exec_id)
            sc_id = del_item.get("escenario_id")
            if sc_id:
                self._deleted_scenarios.add(sc_id)
        self._records = [r for r in self._records if r.get("id") != exec_id]
        if len(self._records) == 0:
            self._is_cleared = True
        self._save_state_to_disk()
        return len(self._records) < initial_len

    def clear(self) -> None:
        """Limpia el historial en memoria y reinicia el MemorySaver (guardando copia de seguridad para Deshacer)."""
        if self._records:
            self._backup_records = list(self._records)
            self._backup_memory_saver = self._memory_saver
        self._records.clear()
        self._memory_saver = MemorySaver()
        self._is_cleared = True
        self._save_state_to_disk()

    def undo_clear(self) -> bool:
        """Restaura los registros previamente respaldados antes del último clear."""
        if not self._backup_records:
            return False
        self._records = list(self._backup_records)
        if self._backup_memory_saver is not None:
            self._memory_saver = self._backup_memory_saver
        self._backup_records.clear()
        self._backup_memory_saver = None
        self._is_cleared = False
        self._save_state_to_disk()
        return True


# Instancia global en memoria RAM
execution_history_manager = ExecutionHistoryManager(enable_persistence=True)


def render_executions_partial(records: list[dict[str, Any]], target_container: str = "#modal-visor-historial") -> str:
    """
    Renderiza el fragmento HTML (Partial) de la bitácora de sesión actual en memoria RAM
    para el menú lateral (Sidebar) con diseño compacto de alta densidad (NOC).
    Mantiene fielmente el diseño del Visor de Diagnóstico (#003366, #0d1e33, bordes rgba(0,82,163,0.4), hover #38bdf8).
    """
    count = len(records)
    if count == 0:
        return """
        <div class="flex flex-col items-center justify-center py-5 px-3 text-center bg-[#070e18]/80 rounded-lg border border-dashed border-slate-800">
            <div class="w-7 h-7 rounded flex items-center justify-center bg-gradient-to-br from-[#003366] to-[#001f3f] shadow-sm border border-sky-500/20 text-sky-400 mb-2">
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>
                </svg>
            </div>
            <span class="text-xs font-bold text-slate-200 font-sans block">Bitácora en RAM Vacía</span>
            <span class="text-[10px] text-slate-400 font-sans block mt-0.5">Ejecuta un diagnóstico para registrar</span>
        </div>
        """

    resueltos = sum(1 for r in records if r.get("status") == "RESUELTO" or r.get("is_correct"))
    fallos = count - resueltos
    ram_pct = min(100, round((count / 150) * 100))

    cards_html: list[str] = []
    for r in records:
        r_id = html.escape(r.get("id", ""))
        sc_id = html.escape(r.get("escenario_id", ""))
        mod = html.escape(r.get("modelo", ""))
        seed = html.escape(str(r.get("seed", 42)))
        ts_full = html.escape(r.get("timestamp", ""))
        # Hora compacta HH:MM (ej. 14:22)
        time_str = ts_full[:5] if len(ts_full) >= 5 else ts_full
        status = r.get("status", "RESUELTO")
        is_correct = r.get("is_correct", False)

        # Indicador visual de estado idéntico a streamIndicatorDot del visor
        if status == "RESUELTO" or is_correct:
            dot_style = "background: #10b981; box-shadow: 0 0 6px #10b981;"
            status_text = "Resuelto"
            status_filter_val = "RESUELTO"
        elif status == "PARCIAL":
            dot_style = "background: #f59e0b; box-shadow: 0 0 6px #f59e0b;"
            status_text = "Parcial"
            status_filter_val = "FALLO"
        else:
            dot_style = "background: #ef4444; box-shadow: 0 0 6px #ef4444;"
            status_text = "Fallo"
            status_filter_val = "FALLO"

        cards_html.append(f"""
        <div class="hist-card group flex items-center justify-between px-2 py-1.5 rounded-md transition-all duration-200 cursor-pointer shadow-sm relative overflow-hidden"
             id="hist-card-{r_id}"
             data-status="{status_filter_val}"
             data-correct="{'true' if (status == 'RESUELTO' or is_correct) else 'false'}"
             data-scenario="{sc_id}"
             style="background: linear-gradient(135deg, #0d1e33 0%, #081424 100%); border: 1px solid rgba(0, 82, 163, 0.4);"
             onmouseover="if(document.documentElement.getAttribute('data-theme') !== 'light' && !this.classList.contains('active-history-card')) {{ this.style.background='linear-gradient(135deg, #132d4d 0%, #0b1c31 100%)'; this.style.borderColor='#38bdf8'; this.style.boxShadow='0 4px 12px rgba(0, 82, 163, 0.35)'; this.style.transform='translateY(-1px)'; }}"
             onmouseout="if(document.documentElement.getAttribute('data-theme') !== 'light' && !this.classList.contains('active-history-card')) {{ this.style.background='linear-gradient(135deg, #0d1e33 0%, #081424 100%)'; this.style.borderColor='rgba(0, 82, 163, 0.4)'; this.style.boxShadow='0 2px 6px rgba(0, 0, 0, 0.2)'; this.style.transform='none'; }}"
             hx-get="/api/history/execution/{r_id}"
             hx-target="{target_container}"
             hx-swap="innerHTML"
             onclick="if(window.markActiveHistoryCard) window.markActiveHistoryCard(this);">
            <div class="flex items-center gap-1.5 min-w-0">
                <span class="inline-block shrink-0" style="width: 6px; height: 6px; border-radius: 50%; {dot_style}"></span>
                <div class="truncate leading-tight">
                    <span class="font-mono text-xs font-bold text-slate-100 group-hover:text-white transition-colors block truncate">
                        {sc_id}
                    </span>
                    <span class="text-[9px] text-slate-400 group-hover:text-slate-300 font-sans block truncate">
                        {mod} &bull; s:{seed}
                    </span>
                </div>
            </div>
            <div class="flex items-center gap-1 shrink-0 ml-1.5">
                <span class="text-[10px] font-mono text-slate-400 group-hover:text-sky-300 font-semibold transition-colors">
                    {time_str}
                </span>
                <button type="button"
                        hx-delete="/api/history/execution/{r_id}"
                        hx-target="#executionHistoryContainer"
                        hx-swap="innerHTML"
                        hx-confirm="¿Eliminar esta sesión de la RAM?"
                        onclick="event.stopPropagation();"
                        class="p-0.5 hover:text-rose-400 text-slate-500 hover:bg-rose-950/60 rounded transition-all cursor-pointer opacity-70 group-hover:opacity-100">
                    <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
                </button>
            </div>
        </div>
        """)

    all_cards = "\n".join(cards_html)

    return f"""
    <div class="space-y-1.5">
        <!-- Indicador de Capacidad en RAM & Contadores de Veredicto -->
        <div class="flex items-center justify-between text-[9px] font-mono text-slate-400 px-2 py-0.5 rounded bg-[#070e18] border border-slate-800/80 mb-1 shadow-inner">
            <span class="cursor-help" title="Almacenamiento en memoria RAM: cola FIFO con retención en caliente de hasta 150 ejecuciones (LangGraph MemorySaver)">RAM: <strong class="text-sky-300 font-bold">{count}/150</strong> <span class="text-slate-500 text-[8px]">({ram_pct}%)</span></span>
            <span class="text-slate-700">&bull;</span>
            <span>Aciertos: <strong class="text-emerald-400 font-bold">{resueltos}</strong></span>
            <span class="text-slate-700">&bull;</span>
            <span>Fallos: <strong class="text-rose-400 font-bold">{fallos}</strong></span>
        </div>

        <!-- Micro-Chips de Filtrado Rápido en Cliente -->
        <div class="flex items-center gap-1 text-[9px] font-mono pb-1" id="historyFilterChips">
            <button type="button" onclick="filterHistoryStatus('ALL', this)" class="hist-filter-chip active-hist-chip px-1.5 py-0.5 rounded text-[9px] font-semibold bg-[#003366] text-white border border-sky-400/40 cursor-pointer shadow-sm">Todos ({count})</button>
            <button type="button" onclick="filterHistoryStatus('RESUELTO', this)" class="hist-filter-chip px-1.5 py-0.5 rounded text-[9px] font-semibold bg-slate-900/80 hover:bg-emerald-950/60 text-emerald-400 border border-slate-800 hover:border-emerald-600/40 cursor-pointer transition-colors">✓ Resueltos ({resueltos})</button>
            <button type="button" onclick="filterHistoryStatus('FALLO', this)" class="hist-filter-chip px-1.5 py-0.5 rounded text-[9px] font-semibold bg-slate-900/80 hover:bg-rose-950/60 text-rose-400 border border-slate-800 hover:border-rose-600/40 cursor-pointer transition-colors">✗ Fallos ({fallos})</button>
        </div>

        <!-- Lista de Tarjetas Históricas -->
        <div id="histCardsList" class="space-y-1.5">
            {all_cards}
        </div>
    </div>
    """


def render_execution_detail_partial(exec_id: str, data: dict[str, Any]) -> str:
    """
    Renderiza el fragmento HTML del detalle de una ejecución histórica almacenada
    en LangGraph MemorySaver para ser inyectado en #suite-timeline-container.
    """
    record = data.get("record", {})
    rendered_cards = data.get("rendered_html", "").strip()

    sc_id = html.escape(record.get("escenario_id", "DESCONOCIDO"))
    model = html.escape(record.get("modelo", ""))
    seed = html.escape(str(record.get("seed", 42)))
    ts = html.escape(record.get("timestamp", ""))
    status = record.get("status", "RESUELTO")
    is_correct = record.get("is_correct", False)
    cot = html.escape(record.get("cot_explanation", "") or "No se registró explicación de razonamiento.")
    pred_rc = html.escape(record.get("root_cause_predicted", ""))
    exp_rc = html.escape(record.get("root_cause_expected", ""))
    pred_comp = html.escape(record.get("component_predicted", ""))
    exp_comp = html.escape(record.get("component_expected", ""))
    action = html.escape(record.get("suggested_action", ""))
    tool_cmd = html.escape(record.get("tool_command", ""))
    tool_out = html.escape(record.get("tool_output", ""))
    ttft = record.get("ttft_ms", 0.0)
    tok_s = record.get("tok_per_sec", 0.0)
    lat = record.get("latency_ms", 0.0)
    toks = record.get("completion_tokens", 0)

    raw_sc = urllib.parse.quote(str(record.get("escenario_id", "")))
    raw_model = urllib.parse.quote(str(record.get("model_id", "")))

    # Status badge coherente con el visor
    if status == "RESUELTO" or is_correct:
        status_banner = '<span class="px-2.5 py-0.5 rounded bg-emerald-950/80 text-emerald-300 font-bold border border-emerald-500/40 text-xs font-mono">RESUELTO / CORRECTO</span>'
    elif status == "PARCIAL":
        status_banner = '<span class="px-2.5 py-0.5 rounded bg-amber-950/80 text-amber-300 font-bold border border-amber-500/40 text-xs font-mono">PARCIALMENTE CORRECTO</span>'
    else:
        status_banner = '<span class="px-2.5 py-0.5 rounded bg-rose-950/80 text-rose-300 font-bold border border-rose-500/40 text-xs font-mono">DIAGNÓSTICO ERRÓNEO</span>'

    # Reporte estructurado Markdown para exportación rápida a tickets NOC / Jira
    ticket_md = f"""# REPORTE DE INCIDENTE L7 (NOC TICKET)
- **ID de Corrida:** {exec_id}
- **Timestamp:** {ts}
- **Escenario:** {sc_id} ({record.get('categoria', 'RED_L7')} - {record.get('fault_class', '')})
- **Modelo SLM:** {model} ({record.get('model_id', '')}) | Semilla: {seed}
- **Estado Diagnóstico:** {status} ({'CORRECTO' if is_correct else 'FALLO'})

## Diagnóstico Técnico
- **Causa Raíz Diagnosticada:** {pred_rc or 'No registrada'}
- **Causa Raíz Esperada:** {exp_rc or 'No registrada'}
- **Componente Afectado:** {pred_comp or 'No registrado'}
- **Acción Sugerida (SOP):** {action or 'No registrada'}

## Evidencia CLI & Telemetría
- **Comando Ejecutado:** {tool_cmd or 'Ninguno'}
- **Telemetría:** TTFT: {ttft:.1f}ms | Latencia: {lat:.0f}ms | Velocidad: {tok_s:.1f} tok/s | Tokens: {toks}
"""
    escaped_ticket_md = html.escape(ticket_md)

    # Banner de Cabecera de Replay Histórico con diseño del Visor de Diagnóstico
    header_banner = f"""
    <div class="suite-run-header my-3 p-4 rounded-xl bg-gradient-to-br from-[#0e1b2e] to-[#07131e] border border-slate-700/80 text-slate-200 text-xs font-sans shadow-xl flex items-center justify-between flex-wrap gap-3 animate-fadeIn">
        <textarea id="ticket-raw-{html.escape(exec_id)}" class="hidden" style="display:none;">{escaped_ticket_md}</textarea>
        <div class="flex items-center gap-3">
            <span class="inline-block shrink-0" style="width: 8px; height: 8px; border-radius: 50%; background: #10b981; box-shadow: 0 0 6px #10b981;"></span>
            <div>
                <div class="font-bold text-white text-xs uppercase tracking-wider flex items-center gap-2 flex-wrap">
                    <span>REPRODUCCIÓN HISTÓRICA EN RAM (LangGraph MemorySaver)</span>
                    <span class="px-2 py-0.5 rounded bg-[#003366] text-sky-200 text-[10px] border border-sky-400/40 font-mono font-bold">{html.escape(exec_id)}</span>
                    {status_banner}
                </div>
                <div class="text-xs text-slate-600 dark:text-slate-300 font-sans mt-1.5 flex items-center gap-2 flex-wrap">
                    <span>Ejecutado a las <strong class="text-slate-900 dark:text-slate-100 font-bold font-mono">{ts}</strong></span>
                    <span class="text-slate-400">&bull;</span>
                    <span>Modelo: <strong class="text-slate-900 dark:text-white font-bold">{model}</strong></span>
                    <span class="text-slate-400">&bull;</span>
                    <span>Seed: <strong class="text-slate-900 dark:text-amber-400 font-bold font-mono">{seed}</strong></span>
                    <span class="text-slate-400">&bull;</span>
                    <span>Escenario: <strong class="text-[#003366] dark:text-emerald-400 font-bold font-mono">{sc_id}</strong></span>
                </div>
            </div>
        </div>
        <div class="flex items-center gap-2 flex-wrap">
            <!-- Acción 1: Re-ejecutar corrida idéntica (cierra el modal e inicia diagnóstico) -->
            <button type="button"
                    onclick="document.getElementById('modal-visor-historial').innerHTML=''; rerunExecution('{sc_id}', '{record.get('model_id', '')}', {seed});"
                    class="px-2.5 py-1.5 rounded-lg bg-gradient-to-r from-red-600 to-rose-700 hover:from-red-500 hover:to-rose-600 text-white border border-red-400/40 text-xs font-bold transition-all flex items-center gap-1.5 cursor-pointer shadow-md shadow-red-950/40">
                <svg class="w-3.5 h-3.5 text-white" fill="currentColor" viewBox="0 0 20 20">
                    <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clip-rule="evenodd"/>
                </svg>
                <span>Re-ejecutar</span>
            </button>
            <!-- Acción 2: Copiar ficha Markdown para Jira/Ticket -->
            <button type="button"
                    onclick="copyExecutionTicketMarkdown('{html.escape(exec_id)}', this)"
                    class="px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-600 text-xs font-semibold transition-colors flex items-center gap-1.5 cursor-pointer shadow-sm">
                <span>📋</span>
                <span>Copiar Ficha</span>
            </button>
            <!-- Acción 3: Ir a la Bitácora lateral (cierra el modal y salta a la bitácora) -->
            <button type="button"
                    onclick="if(window.goToSidebarBitacora) {{ window.goToSidebarBitacora(); }} else {{ document.getElementById('modal-visor-historial').innerHTML=''; document.getElementById('sidebarHistorySection')?.scrollIntoView({{behavior: 'smooth'}}); }}"
                    class="btn-replay-bitacora px-2.5 py-1.5 rounded-lg bg-gradient-to-r from-[#003366] to-[#001f3f] hover:from-[#0052a3] hover:to-[#003366] text-white border border-sky-500/40 text-xs font-semibold transition-colors flex items-center gap-1.5 cursor-pointer shadow-sm">
                <span>🕒</span>
                <span>Bitácora</span>
            </button>
        </div>
    </div>
    """

    # Construir cuerpo estructurado si no viene pre-renderizado
    tool_section = ""
    if tool_cmd:
        tool_section = f"""
        <!-- Nodo 4: Herramienta de Red Read-Only Ejecutada -->
        <div class="p-4 rounded-xl bg-[#0e1b2e] border border-slate-700/80 text-slate-200 text-xs shadow-xl space-y-2">
            <div class="flex items-center justify-between border-b border-slate-700/60 pb-2 mb-3">
                <span class="bg-[#003366] text-white text-xs px-2.5 py-1 rounded font-bold uppercase tracking-wider flex items-center gap-1.5 shadow">
                    <span>🔧</span> CONSOLA CLI (READ-ONLY TOOL)
                </span>
                <span class="font-mono text-[10px] text-emerald-400 font-semibold">Solo Lectura &bull; Modo Seguro</span>
            </div>
            <div class="bg-[#070e18] p-3 rounded-lg border border-slate-800 font-mono text-xs text-emerald-400 mb-2 overflow-x-auto">
                $ {tool_cmd}
            </div>
            {f'<div class="bg-[#070e18] p-3 rounded-lg border border-slate-800 font-mono text-xs text-slate-300 max-h-48 overflow-y-auto whitespace-pre-wrap">{tool_out}</div>' if tool_out else ''}
        </div>
        """

    match_rc = pred_rc.strip().lower() == exp_rc.strip().lower() if (pred_rc and exp_rc) else is_correct
    rc_color = "text-emerald-300" if match_rc else "text-rose-300"
    match_comp = pred_comp.strip().lower() == exp_comp.strip().lower() if (pred_comp and exp_comp) else is_correct
    comp_color = "text-emerald-300" if match_comp else "text-amber-300"

    reconstructed_body = f"""
    <!-- Nodo 3: Cadena de Razonamiento CoT -->
    <div class="p-4 rounded-xl bg-[#0e1b2e] border border-slate-700/80 text-slate-200 text-xs shadow-xl space-y-3">
        <div class="flex items-center justify-between border-b border-slate-700/60 pb-2 mb-2">
            <span class="bg-[#003366] text-white text-xs px-2.5 py-1 rounded font-bold uppercase tracking-wider flex items-center gap-1.5 shadow">
                <span>🧠</span> CADENA DE RAZONAMIENTO COT
            </span>
            <span class="font-mono text-xs text-sky-400 font-semibold">SLM Local: {model} &bull; Seed: {seed}</span>
        </div>
        <div class="bg-[#070e18] p-4 rounded-lg border border-slate-800 font-sans text-xs text-slate-200 leading-relaxed whitespace-pre-wrap">
            {cot}
        </div>
    </div>

    {tool_section}

    <!-- Nodo 5: Veredicto Técnico Final & Métricas -->
    <div class="timeline-verdict-card bg-gradient-to-br from-[#0e1b2e] to-[#07131e] border-2 border-emerald-500 rounded-2xl p-6 shadow-2xl shadow-emerald-950/40 relative overflow-hidden space-y-4">
        <div class="flex items-center justify-between border-b border-slate-700/80 pb-3 flex-wrap gap-2">
            <span class="bg-emerald-600 text-white text-xs px-2.5 py-1 rounded font-bold uppercase tracking-wider flex items-center gap-1.5 shadow">
                <span class="w-2 h-2 rounded-full bg-white animate-pulse"></span>
                VEREDICTO TÉCNICO REGISTRADO
            </span>
            <span class="text-slate-400 font-mono text-xs">Escenario: <strong class="text-white">{sc_id}</strong></span>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
            <div class="verdict-subbox bg-[#070e18] border-2 border-red-500/60 rounded-xl p-4 shadow-md">
                <div class="flex items-center gap-2 mb-1.5">
                    <span class="w-2.5 h-2.5 rounded-full bg-red-500"></span>
                    <span class="text-xs font-bold text-red-400 uppercase tracking-wider">Causa Raíz</span>
                </div>
                <div class="{rc_color} font-bold text-xs">{pred_rc or 'No registrada'}</div>
                {f'<div class="text-slate-500 text-[10px] mt-1.5 pt-1 border-t border-slate-800/80">Esperada: {exp_rc}</div>' if exp_rc else ''}
            </div>
            <div class="verdict-subbox bg-[#070e18] border-2 border-emerald-500/60 rounded-xl p-4 shadow-md">
                <div class="flex items-center gap-2 mb-1.5">
                    <span class="w-2.5 h-2.5 rounded-full bg-emerald-500"></span>
                    <span class="text-xs font-bold text-emerald-400 uppercase tracking-wider">Componente Afectado</span>
                </div>
                <div class="{comp_color} font-bold text-xs font-mono">{pred_comp or 'No registrado'}</div>
                {f'<div class="text-slate-500 text-[10px] mt-1.5 pt-1 border-t border-slate-800/80 font-sans">Esperado: {exp_comp}</div>' if exp_comp else ''}
            </div>
        </div>

        {f'''<div class="bg-[#070e18] p-4 rounded-xl border border-slate-800 text-xs">
            <span class="text-slate-400 font-bold block text-[11px] uppercase tracking-wider mb-1">Acción Sugerida / Mitigación (SOP):</span>
            <p class="text-blue-300 font-medium font-sans leading-relaxed m-0">{action}</p>
        </div>''' if action else ''}

        <!-- Telemetría Registrada -->
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2 border-t border-slate-800 text-center font-mono text-xs">
            <div class="bg-slate-900/60 p-2 rounded-lg border border-slate-800">
                <span class="text-slate-500 text-[10px] block uppercase">TTFT</span>
                <span class="text-white font-bold">{ttft:.1f} ms</span>
            </div>
            <div class="bg-slate-900/60 p-2 rounded-lg border border-slate-800">
                <span class="text-slate-500 text-[10px] block uppercase">Velocidad</span>
                <span class="text-white font-bold">{tok_s:.1f} tok/s</span>
            </div>
            <div class="bg-slate-900/60 p-2 rounded-lg border border-slate-800">
                <span class="text-slate-500 text-[10px] block uppercase">Latencia</span>
                <span class="text-white font-bold">{lat:.0f} ms</span>
            </div>
            <div class="bg-slate-900/60 p-2 rounded-lg border border-slate-800">
                <span class="text-slate-500 text-[10px] block uppercase">Tokens</span>
                <span class="text-white font-bold">{toks}</span>
            </div>
        </div>
    </div>
    """

    body_content = rendered_cards if rendered_cards else reconstructed_body

    return f"""
    <div id="modal-visor-backdrop"
         class="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4 transition-all animate-fadeIn"
         onclick="if(event.target === this) {{ if(window.closeVisorModal) window.closeVisorModal(); else document.getElementById('modal-visor-historial').innerHTML=''; }}">
        <div class="bg-slate-900 border border-slate-700 w-11/12 max-w-6xl max-h-[90vh] overflow-y-auto rounded-lg p-6 relative shadow-2xl custom-scrollbar text-slate-100">
            <!-- Botón ✕ Cerrar Superior Derecho -->
            <button type="button"
                    onclick="if(window.closeVisorModal) window.closeVisorModal(); else document.getElementById('modal-visor-historial').innerHTML='';"
                    class="absolute top-4 right-4 z-20 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-600 text-xs font-semibold flex items-center gap-1.5 transition-all cursor-pointer shadow-md"
                    title="Cerrar modal (Esc)">
                <span>✕ Cerrar</span>
                <kbd class="text-[10px] font-mono bg-slate-900 px-1 py-0.5 rounded text-slate-400 border border-slate-700">Esc</kbd>
            </button>

            <!-- Contenido de Detalle Histórico (Cadena de Razonamiento y Comandos) -->
            <div class="historical-replay-wrapper space-y-4 pt-1">
                {header_banner}
                <div class="historical-timeline-body space-y-3">
                    {body_content}
                </div>
            </div>
        </div>
    </div>
    """


def populate_from_suite_store_if_empty() -> None:
    """Sincroniza en memoria las corridas ya existentes en suite_store para visibilidad inmediata."""
    if execution_history_manager.records or execution_history_manager.is_cleared:
        return
    if HISTORY_STATE_FILE.exists() and execution_history_manager.is_cleared:
        return
    try:
        from src.layer6_interface.suite_store import suite_store
        sess = suite_store.get_session("latest")
        if not sess or not sess.cases:
            return
        for c in reversed(sess.cases):
            sc_id = c.get("scenario_id", "DESCONOCIDO")
            if sc_id in execution_history_manager.deleted_scenarios:
                continue
            idx = c.get("index", 1)
            case_exec_id = f"exec-{sess.run_id}-case{idx}"
            if case_exec_id in execution_history_manager.deleted_ids:
                continue
            gt = c.get("ground_truth", {})
            pred = c.get("prediction", {})
            tel = c.get("telemetry", {})
            ev = c.get("evaluation", {})
            tool = c.get("tool_execution", {})
            is_rc = bool(ev.get("root_cause_correct"))
            is_comp = bool(ev.get("component_correct"))
            status = "RESUELTO" if (is_rc and is_comp) else ("PARCIAL" if (is_rc or is_comp) else "FALLO")
            execution_history_manager.add_execution(
                scenario_id=sc_id,
                model_id=sess.model_id,
                model_name=sess.model_name or sess.model_id,
                seed=sess.seed,
                status=status,
                is_correct=is_rc,
                category=c.get("category", "RED_L7"),
                fault_class=c.get("fault_class", ""),
                cot_explanation=pred.get("natural_language_explanation", ""),
                root_cause_predicted=pred.get("root_cause", ""),
                root_cause_expected=gt.get("root_cause", ""),
                component_predicted=pred.get("affected_component", ""),
                component_expected=gt.get("affected_component", ""),
                suggested_action=pred.get("suggested_action", "") or gt.get("suggested_action", ""),
                tool_called=bool(tool.get("command") or tool.get("tool_name")),
                tool_name=tool.get("tool_name"),
                tool_command=tool.get("command"),
                tool_output=tool.get("output"),
                ttft_ms=tel.get("ttft_ms", 0.0),
                tok_per_sec=tel.get("tok_per_sec", 0.0),
                latency_ms=tel.get("total_latency_ms", 0.0),
                completion_tokens=tel.get("completion_tokens", 0),
                exec_id=case_exec_id
            )
    except Exception as e:
        logger.debug(f"Aviso poblando historial desde suite_store: {e}")

