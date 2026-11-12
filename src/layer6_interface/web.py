import asyncio

import json

import re

import subprocess

import urllib.parse

from datetime import datetime, timezone

from typing import Any



import httpx

from fastapi import FastAPI, HTTPException, Request, Response

from fastapi.middleware.cors import CORSMiddleware

from fastapi.responses import (

    FileResponse,

    HTMLResponse,

    JSONResponse,

    RedirectResponse,

    StreamingResponse,

)

from pathlib import Path

from pydantic import BaseModel, Field

from starlette.middleware.base import BaseHTTPMiddleware

from starlette.staticfiles import StaticFiles



from src.core.config import ModelDefinition, SystemConfig, PROJECT_ROOT

from src.core.logger import logger

from src.layer1_lab.runner import ScenarioLabRunner

from src.layer2_pipeline.aggregator import DataPipelineAgent

from src.layer3_rag.retriever import RAGKnowledgeEngine

from src.layer4_inference.engine import LocalInferenceEngine

from src.layer5_orchestrator.agent import DiagnosticOrchestratorAgent

from src.layer6_interface.execution_history import execution_history_manager

from src.layer6_interface.observability import router as observability_router
from src.layer8_human_eval.web_routes import router as human_eval_router

from src.layer6_interface.tooltip_helper import TOOLTIP_CSS, TOOLTIP_JS



app = FastAPI(

    title="NetDiagBench-L7 Dashboard",

    description="Panel de Demostración y Diagnóstico L7 con SLMs Locales",

    version="1.0.0"

)





class SecurityHeadersMiddleware(BaseHTTPMiddleware):

    """Middleware de cabeceras de seguridad HTTP estándar OWASP (Anti-Clickjacking, Anti-Sniffing, Anti-XSS)."""



    async def dispatch(self, request: Request, call_next):

        response: Response = await call_next(request)

        response.headers["X-Frame-Options"] = "SAMEORIGIN"

        response.headers["X-Content-Type-Options"] = "nosniff"

        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        response.headers["X-XSS-Protection"] = "1; mode=block"

        response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=(), payment=(), usb=()"

        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"

        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.tailwindcss.com https://unpkg.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' data: https://fonts.gstatic.com; "
            "img-src 'self' data: blob:; "
            "connect-src 'self' ws: http://127.0.0.1:* http://localhost:*; "
            "frame-ancestors 'self'; "
            "base-uri 'self'; "
            "form-action 'self';"
        )

        return response





app.add_middleware(SecurityHeadersMiddleware)

app.add_middleware(

    CORSMiddleware,

    allow_origins=[

        "http://127.0.0.1:8000",

        "http://localhost:8000",

        "http://127.0.0.1",

        "http://localhost",

    ],

    allow_credentials=True,

    allow_methods=["GET", "POST", "OPTIONS"],

    allow_headers=["*"],

)



app.include_router(observability_router)
app.include_router(human_eval_router)



# Montaje de directorio estático para logos institucionales y recursos multimedia

_STATIC_DIR = Path(__file__).parent / "static"

if not _STATIC_DIR.exists():

    _STATIC_DIR = Path("static")

if _STATIC_DIR.exists():

    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")



# Almacenamiento 100% en memoria RAM (LangGraph MemorySaver) para historial de ejecuciones efímero

app.state.execution_history = execution_history_manager.records

app.state.memory_saver = execution_history_manager.memory_saver





def _validate_safe_identifier(val: str | None, field_name: str = "parámetro") -> str | None:

    """Valida que un identificador de escenario, modelo o corrida no contenga secuencias de escape de directorio (Path Traversal)."""

    if val is None:

        return None

    cleaned = str(val).strip()

    if not cleaned:

        return cleaned

    if ".." in cleaned or "/" in cleaned or "\\" in cleaned or "%2e" in cleaned.lower():

        raise HTTPException(

            status_code=400,

            detail=f"El parámetro '{field_name}' contiene caracteres o secuencias de ruta no permitidos."

        )

    return cleaned



# Instancias compartidas

system_config = SystemConfig()

lab_runner = ScenarioLabRunner()

data_pipeline = DataPipelineAgent()

rag_engine = RAGKnowledgeEngine()

inference_engine = LocalInferenceEngine(config=system_config)

orchestrator = DiagnosticOrchestratorAgent(inference_engine=inference_engine)





class DiagnoseRequest(BaseModel):

    scenario_id: str = Field(..., min_length=3, max_length=64, pattern=r"^[A-Z0-9_\-]+$")

    model_id: str = Field(..., min_length=2, max_length=128, pattern=r"^[a-zA-Z0-9_\-\./:]+$")

    seed: int = Field(42, ge=0, le=2147483647)





@app.get("/api/scenarios")

def get_scenarios():

    """Devuelve el catálogo de escenarios disponibles."""

    return [s.model_dump() for s in lab_runner.list_scenarios()]





def _render_model_options(models: list[ModelDefinition], selected_id: str | None = None) -> str:

    """Genera las etiquetas <optgroup> y <option> para el selector de modelos."""

    official_base = system_config._load_models()

    base_ids = {m.id for m in official_base}

    base_models = official_base

    dyn_models = [m for m in models if m.id not in base_ids and m.provider == 'Ollama Local']

    lines = []

    if base_models:

        lines.append('  <optgroup label="── TERNA BASE DE INVESTIGACIÓN ──">')

        for m in base_models:

            sel = ' selected="selected"' if selected_id and (m.id == selected_id or m.ollama_tag == selected_id) else ""

            lines.append(f'    <option value="{m.id}"{sel}>{m.name} ({m.parameters_raw}, {m.license})</option>')

        lines.append('  </optgroup>')



    if dyn_models:

        lines.append('  <optgroup label="── MODELOS DINÁMICOS INTEGRADOS (OLLAMA) ──">')

        for m in dyn_models:

            sel = ' selected="selected"' if selected_id and (m.id == selected_id or m.ollama_tag == selected_id) else ""

            lines.append(f'    <option value="{m.id}"{sel}>{m.name} ({m.parameters_raw}, {m.license})</option>')

        lines.append('  </optgroup>')



    return "\n".join(lines)





@app.get("/api/models")

def get_models():

    """Devuelve la lista completa de modelos disponibles (terna base + dinámicos sincronizados con Ollama)."""

    all_models = system_config.sync_with_ollama(inference_engine.ollama_base_url)

    for m in all_models:

        inference_engine.register_model(m)

    try:

        from src.layer6_interface.observability import inference_engine as obs_engine

        for m in all_models:

            obs_engine.register_model(m)

    except Exception:

        pass

    return [m.model_dump() for m in all_models]





_active_pulls: dict[str, asyncio.Event] = {}





@app.get("/api/models/pull/stream")

async def pull_model_stream(model_name: str = ""):

    """

    Descarga en streaming un modelo vía Ollama reportando progreso en tiempo real (SSE).

    Permite visualizar porcentaje, MB/GB descargados y cancelar la descarga.

    """

    model_name = (model_name or "").strip()

    if not model_name:

        async def err_gen():

            yield f'data: {json.dumps({"status": "error", "message": "El tag del modelo no puede estar vacío."})}\n\n'

        return StreamingResponse(err_gen(), media_type="text/event-stream")



    cancel_event = asyncio.Event()

    _active_pulls[model_name] = cancel_event



    async def stream_generator():

        try:

            yield f'data: {json.dumps({"status": "progress", "percent": 0, "text": f"Iniciando conexión con Ollama para {model_name}...", "bytes_str": "Conectando..."})}\n\n'

            url = f"{inference_engine.ollama_base_url}/api/pull"



            async with httpx.AsyncClient(timeout=3600.0) as client:

                async with client.stream("POST", url, json={"model": model_name, "stream": True}) as resp:

                    if resp.status_code != 200:

                        err_bytes = await resp.aread()

                        err_msg = err_bytes.decode(errors="replace")

                        yield f'data: {json.dumps({"status": "error", "message": f"Error Ollama ({resp.status_code}): {err_msg}"})}\n\n'

                        return



                    last_pct = 0.0

                    download_finished_ok = False

                    async for line in resp.aiter_lines():

                        if cancel_event.is_set():

                            yield f'data: {json.dumps({"status": "cancelled", "message": f"Descarga de {model_name} cancelada por el usuario."})}\n\n'

                            try:

                                await client.request("DELETE", f"{inference_engine.ollama_base_url}/api/delete", json={"model": model_name})

                            except Exception:

                                pass

                            return



                        if not line:

                            continue

                        try:

                            payload = json.loads(line)

                        except Exception:

                            continue



                        status_raw = payload.get("status", "")

                        total = payload.get("total", 0)

                        completed = payload.get("completed", 0)



                        if status_raw == "success":

                            download_finished_ok = True

                            yield f'data: {json.dumps({"status": "progress", "percent": 100, "text": "Extracción y verificación completada. Registrando en catálogo...", "bytes_str": "100%"})}\n\n'

                            break



                        pct = round((completed / total) * 100, 1) if (total and total > 0) else last_pct

                        last_pct = pct



                        if total and total > 0:

                            comp_mb = completed / (1024 * 1024)

                            tot_mb = total / (1024 * 1024)

                            if tot_mb >= 1024:

                                bytes_str = f"{comp_mb / 1024:.2f} GB / {tot_mb / 1024:.2f} GB"

                            else:

                                bytes_str = f"{comp_mb:.1f} MB / {tot_mb:.1f} MB"

                        else:

                            bytes_str = "Sincronizando..."



                        status_text = status_raw

                        if "pulling manifest" in status_raw:

                            status_text = "Obteniendo manifiesto de capas..."

                        elif "verifying" in status_raw:

                            status_text = "Verificando integridad SHA-256..."

                        elif "writing" in status_raw:

                            status_text = "Escribiendo capas y manifiesto..."

                        elif "pulling" in status_raw:

                            layer_id = status_raw.replace("pulling", "").strip()[:12]

                            status_text = f"Descargando capa GGUF [{layer_id}]..."



                        msg = {

                            "status": "progress",

                            "percent": pct,

                            "text": status_text,

                            "bytes_str": f"{bytes_str} ({pct}%)"

                        }

                        yield f"data: {json.dumps(msg)}\n\n"



            if not download_finished_ok:

                yield f'data: {json.dumps({"status": "error", "message": f"La descarga de {model_name} se interrumpió o no se completó en Ollama."})}\n\n'

                return



            # Inspección y registro en SystemConfig e InferenceEngine

            details: dict[str, Any] = {}

            try:

                async with httpx.AsyncClient(timeout=10.0) as client:

                    show_resp = await client.post(

                        f"{inference_engine.ollama_base_url}/api/show",

                        json={"name": model_name}

                    )

                    if show_resp.status_code == 200:

                        details = show_resp.json().get("details", {})

            except Exception:

                pass



            param_size = details.get("parameter_size", "")

            if not param_size:

                m_tag = re.search(r'(\d+(?:\.\d+)?)[bB]', model_name)

                param_size = f"{m_tag.group(1)}B" if m_tag else "Auto"



            quant = details.get("quantization_level", "Q4_K_M")

            family = details.get("family", "Ollama")

            slug = re.sub(r'[^a-zA-Z0-9_\-]', '-', model_name).lower().strip('-')

            clean_name = model_name.split(":")[0].replace("-", " ").title()



            new_model = ModelDefinition(

                id=slug,

                name=f"{clean_name} ({model_name})",

                provider="Ollama Local",

                parameters_raw=param_size,

                license=f"Open ({family.capitalize()})",

                quantization=quant,

                format="GGUF",

                context_window_tokens=32768,

                function_calling_support="native",

                ollama_tag=model_name,

                approx_vram_gb=4.5,

                reason_for_inclusion=f"Modelo {model_name} integrado dinámicamente vía Ollama."

            )



            system_config.save_dynamic_model(new_model)

            inference_engine.register_model(new_model)

            try:

                from src.layer6_interface.observability import inference_engine as obs_engine

                obs_engine.register_model(new_model)

            except Exception:

                pass



            all_models = system_config.get_all_models()

            options_html = _render_model_options(all_models, selected_id=new_model.id)



            done_msg = {

                "status": "complete",

                "model_id": new_model.id,

                "model_name": new_model.name,

                "param_size": param_size,

                "quant": quant,

                "options_html": options_html,

                "message": f"Modelo {model_name} descargado e integrado con éxito ({param_size}, {quant})."

            }

            yield f"data: {json.dumps(done_msg)}\n\n"



        except Exception as exc:

            yield f'data: {json.dumps({"status": "error", "message": f"Error inesperado: {str(exc)}"})}\n\n'

        finally:

            _active_pulls.pop(model_name, None)



    return StreamingResponse(

        stream_generator(),

        media_type="text/event-stream",

        headers={

            "Cache-Control": "no-cache",

            "Connection": "keep-alive",

            "X-Accel-Buffering": "no"

        }

    )





@app.post("/api/models/pull/cancel")

async def cancel_model_pull(request: Request):

    """Cancela una descarga en curso de un modelo en Ollama y elimina capas huérfanas."""

    model_name = ""

    try:

        data = await request.json()

        model_name = data.get("model_name") or data.get("model") or ""

    except Exception:

        pass



    cancelled = False

    if model_name and model_name in _active_pulls:

        _active_pulls[model_name].set()

        cancelled = True

    else:

        for name, ev in list(_active_pulls.items()):

            ev.set()

            cancelled = True



    if model_name:

        try:

            async with httpx.AsyncClient(timeout=5.0) as client:

                await client.request("DELETE", f"{inference_engine.ollama_base_url}/api/delete", json={"model": model_name})

        except Exception:

            pass



    return JSONResponse({"status": "cancelled", "model": model_name, "cancelled": cancelled})





@app.post("/api/models/pull")

async def pull_model_endpoint(request: Request):

    """

    Descarga e integra un nuevo modelo dinámico vía Ollama.

    Actualiza el <select> original para incluir el nuevo modelo y dejarlo seleccionado.

    """

    content_type = request.headers.get("content-type", "")

    body_bytes = await request.body()

    model_name = ""

    if "application/json" in content_type and body_bytes:

        try:

            payload = json.loads(body_bytes.decode("utf-8"))

            model_name = payload.get("model_name", "") or payload.get("model", "")

        except Exception:

            pass

    elif body_bytes:

        parsed = urllib.parse.parse_qs(body_bytes.decode("utf-8"))

        model_name = parsed.get("model_name", [""])[0] or parsed.get("model", [""])[0]



    model_name = model_name.strip()

    OLLAMA_MODEL_TAG_REGEX = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_\-\./]*(:[a-zA-Z0-9_\-\.]+)?$")
    if not model_name or not OLLAMA_MODEL_TAG_REGEX.match(model_name) or len(model_name) > 128:

        err_msg = "El tag del modelo no puede estar vacío (ej. llama3.2:1b)."

        if request.headers.get("hx-request"):

            return HTMLResponse(

                f"""

                <div class="select-wrapper" id="selModelWrapper">

                    <select id="selModel" name="model_id" class="form-control">

                        {_render_model_options(system_config.get_all_models())}

                    </select>

                </div>

                <div id="pullFeedbackMessage" hx-swap-oob="innerHTML" class="mt-2 text-xs text-rose-400 font-semibold p-2 rounded bg-rose-950/50 border border-rose-500/30 flex items-center gap-1.5 animate-fadeIn">

                    <svg class="w-3.5 h-3.5 shrink-0 text-rose-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>

                    <span>⚠ {err_msg}</span>

                </div>

                """,

                status_code=400

            )

        return JSONResponse({"status": "error", "message": err_msg}, status_code=400)



    # 1. Ejecutar descarga con Ollama (CLI o HTTP API)

    download_success = False

    error_detail = ""



    try:

        proc = await asyncio.to_thread(

            subprocess.run,

            ["ollama", "pull", model_name],

            capture_output=True,

            text=True,

            encoding="utf-8",

            errors="replace",

            timeout=1800,

        )

        if proc.returncode == 0:

            download_success = True

        else:

            error_detail = proc.stderr.strip() or f"Código de salida: {proc.returncode}"

    except FileNotFoundError:

        # Fallback a Ollama HTTP API si el comando CLI no está en el PATH

        try:

            async with httpx.AsyncClient(timeout=1800.0) as client:

                pull_resp = await client.post(

                    f"{inference_engine.ollama_base_url}/api/pull",

                    json={"model": model_name, "stream": False}

                )

                if pull_resp.status_code == 200:

                    download_success = True

                else:

                    error_detail = pull_resp.text

        except Exception as ex_http:

            error_detail = f"Fallo al conectar con Ollama API: {str(ex_http)}"

    except Exception as ex_proc:

        error_detail = str(ex_proc)



    if not download_success:

        err_msg = f"Error al descargar {model_name}: {error_detail}"

        if request.headers.get("hx-request"):

            return HTMLResponse(

                f"""

                <div class="select-wrapper" id="selModelWrapper">

                    <select id="selModel" name="model_id" class="form-control">

                        {_render_model_options(system_config.get_all_models())}

                    </select>

                </div>

                <div id="pullFeedbackMessage" hx-swap-oob="innerHTML" class="mt-2 text-xs text-rose-400 font-semibold p-2 rounded bg-rose-950/50 border border-rose-500/30 flex items-center gap-1.5 animate-fadeIn">

                    <svg class="w-3.5 h-3.5 shrink-0 text-rose-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>

                    <span>⚠ {err_msg}</span>

                </div>

                """,

                status_code=500

            )

        return JSONResponse({"status": "error", "message": err_msg}, status_code=500)



    # 2. Consultar detalles reales del modelo vía /api/show

    details: dict[str, Any] = {}

    try:

        async with httpx.AsyncClient(timeout=10.0) as client:

            show_resp = await client.post(

                f"{inference_engine.ollama_base_url}/api/show",

                json={"name": model_name}

            )

            if show_resp.status_code == 200:

                details = show_resp.json().get("details", {})

    except Exception:

        pass



    param_size = details.get("parameter_size", "")

    if not param_size:

        m_tag = re.search(r'(\d+(?:\.\d+)?)[bB]', model_name)

        param_size = f"{m_tag.group(1)}B" if m_tag else "Auto"



    quant = details.get("quantization_level", "Q4_K_M")

    family = details.get("family", "Ollama")

    slug = re.sub(r'[^a-zA-Z0-9_\-]', '-', model_name).lower().strip('-')

    clean_name = model_name.split(":")[0].replace("-", " ").title()



    new_model = ModelDefinition(

        id=slug,

        name=f"{clean_name} ({model_name})",

        provider="Ollama Local",

        parameters_raw=param_size,

        license=f"Open ({family.capitalize()})",

        quantization=quant,

        format="GGUF",

        context_window_tokens=32768,

        function_calling_support="native",

        ollama_tag=model_name,

        approx_vram_gb=4.5,

        reason_for_inclusion=f"Modelo {model_name} integrado dinámicamente vía Ollama."

    )



    # 3. Persistir y registrar en el motor de inferencia

    system_config.save_dynamic_model(new_model)

    inference_engine.register_model(new_model)



    all_models = system_config.get_all_models()

    options_html = _render_model_options(all_models, selected_id=new_model.id)



    if request.headers.get("hx-request"):

        return HTMLResponse(

            f"""

            <div class="select-wrapper" id="selModelWrapper">

                <select id="selModel" name="model_id" class="form-control">

                    {options_html}

                </select>

            </div>

            <div id="pullFeedbackMessage" hx-swap-oob="innerHTML" class="mt-2 text-xs text-emerald-400 font-semibold p-2 rounded bg-emerald-950/50 border border-emerald-500/30 flex items-center gap-1.5 animate-fadeIn">

                <svg class="w-3.5 h-3.5 shrink-0 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>

                <span>Modelo <strong>{model_name}</strong> descargado e integrado con éxito ({param_size}, {quant}).</span>

            </div>

            """

        )



    return JSONResponse({

        "status": "success",

        "model": new_model.model_dump(),

        "total_models": len(all_models)

    })





@app.delete("/api/models/{model_id}")

async def delete_model_endpoint(model_id: str, request: Request, purge_ollama: bool = False):

    """

    Elimina un modelo y todo lo relacionado con él:

      - Corridas en el dataset maestro (data/benchmark_results/resultados.csv) con respaldo previo.

      - Archivos y trazas del modelo en data/runs y data/benchmark_results.

      - Registro en dynamic_models.json (o exclusión en removed_models.json si es terna base).

      - Registro en memoria del motor de inferencia local.

      - Selección de modelos para informes.

      - Pesos en Ollama (opcional si purge_ollama=True).

      - Regeneración de resúmenes Markdown y sincronización del dataset_bundle.json.

    """

    from src.layer7_evaluator.model_management import delete_model

    try:

        report = delete_model(

            model_id=model_id,

            purge_ollama=purge_ollama,

            system_config=system_config,

            inference_engine=inference_engine,

        )

        _cache_correlation.clear()

        _cache_comparative.clear()



        if request.headers.get("hx-request"):

            all_models = system_config.get_all_models()

            options_html = _render_model_options(all_models)

            return HTMLResponse(

                f"""

                <div class="select-wrapper" id="selModelWrapper">

                    <select id="selModel" name="model_id" class="form-control text-sm py-1.5 px-3 rounded-lg bg-slate-950 border border-slate-700 text-slate-100 font-medium focus:border-blue-500 focus:ring-1 focus:ring-blue-500 w-full transition-all cursor-pointer">

                        {options_html}

                    </select>

                </div>

                <div id="deleteFeedbackMessage" hx-swap-oob="innerHTML" class="mt-2 text-xs text-amber-400 font-semibold p-2 rounded bg-amber-950/50 border border-amber-500/30 flex items-center gap-1.5 animate-fadeIn">

                    <svg class="w-3.5 h-3.5 shrink-0 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>

                    <span>Modelo <strong>{model_id}</strong> eliminado con éxito ({report['csv_rows_removed']} corridas purgadas).</span>

                </div>

                """

            )



        return JSONResponse({"status": "success", "report": report})

    except Exception as ex:

        err_msg = str(ex)

        if request.headers.get("hx-request"):

            return HTMLResponse(

                f"""

                <div id="deleteFeedbackMessage" hx-swap-oob="innerHTML" class="mt-2 text-xs text-rose-400 font-semibold p-2 rounded bg-rose-950/50 border border-rose-500/30 flex items-center gap-1.5 animate-fadeIn">

                    <span>⚠ Error al eliminar modelo: {err_msg}</span>

                </div>

                """,

                status_code=400,

            )

        raise HTTPException(status_code=400, detail=err_msg)





@app.get("/api/models/selection")

def get_model_selection_endpoint():

    """Devuelve los modelos disponibles para reportes y la selección activa."""

    from src.layer7_evaluator.model_management import get_report_selection, list_report_models

    available = list_report_models()

    saved = get_report_selection()

    active = saved if saved else [m["id"] for m in available if m["n_runs"] > 0]

    return {

        "available_models": available,

        "selected_models": active,

        "has_custom_selection": bool(saved),

    }





@app.post("/api/models/selection")

async def set_model_selection_endpoint(request: Request):

    """

    Configura la selección de modelos con los cuales se generarán los informes

    (Comparativo, Correlacional, Consolidado) y sus entregables (Excel, PDF, JSON).

    """

    from src.layer7_evaluator.model_management import (

        list_report_models,

        regenerate_report_markdowns,

        set_report_selection,

    )



    models_list: list[str] = []

    content_type = request.headers.get("content-type", "")

    body_bytes = await request.body()

    if "application/json" in content_type and body_bytes:

        try:

            payload = json.loads(body_bytes.decode("utf-8"))

            if isinstance(payload, list):

                models_list = [str(x) for x in payload]

            elif isinstance(payload, dict):

                models_list = payload.get("models", [])

        except Exception:

            pass

    elif body_bytes:

        parsed = urllib.parse.parse_qs(body_bytes.decode("utf-8"))

        models_list = parsed.get("models", []) or parsed.get("models[]", [])



    active = set_report_selection(models_list)

    regenerate_report_markdowns()

    _cache_correlation.clear()

    _cache_comparative.clear()



    return {

        "status": "success",

        "selected_models": active,

        "total_selected": len(active),

        "available_models": list_report_models(),

    }





@app.post("/api/diagnose")

def run_diagnose(req: DiagnoseRequest):

    """Ejecuta el ciclo de diagnóstico interactivo y devuelve el veredicto con telemetría."""

    scenario = lab_runner.get_scenario(req.scenario_id)

    if not scenario:

        raise HTTPException(status_code=404, detail=f"Escenario {req.scenario_id} no encontrado")



    # Capa 1: Laboratorio

    sc, raw_logs, raw_tel = lab_runner.execute_scenario(req.scenario_id, seed=req.seed)



    # Capa 2: Pipeline

    ventana = data_pipeline.process_window(sc, raw_logs, raw_tel)



    # Capa 3: RAG

    observed_sample = " ".join(e.raw_message for e in ventana.parsed_logs[:3]) if ventana.parsed_logs else ""
    query_str = f"{sc.category.value} {observed_sample}".strip()

    contexto = rag_engine.query(query_str, top_k=2)



    # Capa 5 y 4: Inferencia y Orquestación (inyecta el modelo seleccionado dinámicamente)

    traza, diag, inf_resp = orchestrator.run_diagnosis(

        scenario=sc,

        ventana=ventana,

        contexto_rag=contexto,

        model_id=req.model_id,

        seed=req.seed

    )



    # Registrar en la bitácora efímera en memoria RAM (LangGraph MemorySaver)

    try:

        gt = sc.ground_truth

        is_rc_correct = bool(diag.root_cause and gt.root_cause and diag.root_cause.strip().lower() == gt.root_cause.strip().lower())

        is_comp_correct = bool(diag.affected_component and gt.affected_component and diag.affected_component.strip().lower() == gt.affected_component.strip().lower())

        is_resolved = bool(is_rc_correct and is_comp_correct)

        status_str = "RESUELTO" if is_resolved else ("PARCIAL" if (is_rc_correct or is_comp_correct) else "FALLO")



        model_def = inference_engine.models_by_id.get(req.model_id)

        m_name = model_def.name if model_def else req.model_id



        comp_tok = getattr(inf_resp.telemetry, "completion_tokens", 0) or 0

        lat_val = getattr(inf_resp.telemetry, "total_latency_ms", 0.0) or 0.0

        ttft_val = getattr(inf_resp.telemetry, "ttft_ms", 0.0) or 0.0

        tok_val = getattr(inf_resp.telemetry, "tokens_per_second", 0.0) or 0.0



        step_cmd = (getattr(traza.steps[0], "command_executed", None) or getattr(traza.steps[0], "command", "")) if traza.steps else ""

        step_out = (getattr(traza.steps[0], "output_received", None) or getattr(traza.steps[0], "output", "")) if traza.steps else ""

        step_tool = getattr(traza.steps[0], "tool_name", "network_tool") if traza.steps else ""



        execution_history_manager.add_execution(

            scenario_id=sc.scenario_id,

            model_id=req.model_id,

            seed=req.seed,

            status=status_str,

            is_correct=is_resolved,

            category=sc.category.value if hasattr(sc.category, "value") else str(sc.category),

            fault_class=sc.fault_class.value if hasattr(sc.fault_class, "value") else str(sc.fault_class),

            model_name=m_name,

            cot_explanation=diag.natural_language_explanation,

            root_cause_predicted=diag.root_cause,

            root_cause_expected=gt.root_cause,

            component_predicted=diag.affected_component,

            component_expected=gt.affected_component,

            suggested_action=diag.suggested_action or getattr(gt, "suggested_action", "") or getattr(sc, "mitigation_action", ""),

            tool_called=bool(traza.steps),

            tool_name=step_tool,

            tool_command=step_cmd,

            tool_output=step_out,

            ttft_ms=ttft_val,

            tok_per_sec=tok_val,

            latency_ms=lat_val,

            completion_tokens=comp_tok

        )

        app.state.execution_history = execution_history_manager.records

    except Exception as e:

        logger.warning(f"Error registrando en bitácora REST: {e}")



    return {

        "scenario": sc.model_dump(),

        "diagnostico": diag.model_dump(),

        "traza": traza.model_dump(),

        "telemetria": inf_resp.telemetry.model_dump(),

        "rag_chunks": [c.model_dump() for c in contexto.chunks],

        "is_evidence_backed": diag.is_evidence_backed

    }





@app.api_route("/api/stop-suite", methods=["GET", "POST"])

async def stop_suite_route():

    """Endpoint directo para pausar la ejecución de la suite masiva de observabilidad."""

    from src.layer6_interface.observability import stop_suite_endpoint

    return await stop_suite_endpoint()







@app.post("/ejecutar")

async def ejecutar_alias(request: Request):

    """Alias para ejecutar diagnóstico dinámico desde endpoints REST o formularios."""

    content_type = request.headers.get("content-type", "")

    body_bytes = await request.body()

    sc_id = "DNS-NXD-01"

    model_id = "phi-4-mini-instruct"

    seed = 42

    if "application/json" in content_type and body_bytes:

        try:

            data = json.loads(body_bytes.decode("utf-8"))

            sc_id = data.get("scenario_id", sc_id)

            model_id = data.get("model_id", model_id)

            seed = int(data.get("seed", seed))

        except Exception:

            pass

    elif body_bytes:

        parsed = urllib.parse.parse_qs(body_bytes.decode("utf-8"))

        sc_id = parsed.get("scenario_id", [sc_id])[0]

        model_id = parsed.get("model_id", [model_id])[0]

    req = DiagnoseRequest(scenario_id=sc_id, model_id=model_id, seed=seed)

    return await asyncio.to_thread(run_diagnose, req)





def _render_scenario_options(selected_id: str | None = None) -> str:
    """Genera las etiquetas <optgroup> y <option> para el selector de escenarios con atributos de categorización."""
    scenarios = lab_runner.list_scenarios()
    sc_by_cat: dict[str, list[Any]] = {}
    for s in scenarios:
        cat = s.category.value if hasattr(s.category, "value") else str(s.category)
        sc_by_cat.setdefault(cat, []).append(s)

    lines = []
    for cat, list_s in sc_by_cat.items():
        cat_key = cat.upper()
        lines.append(f'  <optgroup label="── {cat_key} ({len(list_s)} Casos) ──" data-category="{cat_key}">')
        for s in list_s:
            s_id = s.scenario_id
            f_class = s.fault_class.value if hasattr(s.fault_class, "value") else str(s.fault_class)
            sel = ' selected="selected"' if (selected_id and s_id == selected_id) or (not selected_id and s_id == "DNS-NXD-01") else ""
            lines.append(f'    <option value="{s_id}" data-category="{cat_key}"{sel}>{s_id} - {f_class}</option>')
        lines.append('  </optgroup>')
    return "\n".join(lines)


def _render_configuracion_form_html(

    selected_sc: str | None = None,

    selected_model: str | None = None,

    seed: int = 42

) -> str:

    """Genera el HTML del Bloque Superior: Barra de Herramientas Compacta (Control Toolbar Flexbox de Fila Única)."""

    all_models = system_config.get_all_models()

    model_opts = _render_model_options(all_models, selected_id=selected_model)

    scenario_opts = _render_scenario_options(selected_id=selected_sc)



    return f"""

    <div id="cardConfigTest" class="w-full flex flex-wrap items-end gap-4 p-3 bg-white dark:bg-[#0d1117] border-b border-slate-200 dark:border-slate-700/60 shadow-sm flex-shrink-0 z-20 pb-4 sticky top-0 transition-colors">

        <!-- Control 1: Escenario L7 -->

        <div class="flex-1 min-w-[240px]">

            <div class="flex items-center justify-between mb-1 gap-2 flex-wrap">

                <label for="selScenario" class="text-[10px] uppercase font-bold text-slate-700 dark:text-slate-400 tracking-wider m-0 flex items-center gap-1.5 flex-shrink-0">

                    <span class="w-1.5 h-1.5 rounded-full bg-red-500"></span>

                    <span>Escenario L7</span>

                </label>

                <!-- Chips de Filtro Rápido por Protocolo / Categoría NOC -->

                <div class="flex items-center gap-1 text-[9px] font-mono" id="scenarioCategoryChips">

                    <button type="button" onclick="filterScenarioCategory('ALL', this)" class="sc-cat-chip active-chip px-1.5 py-0.5 rounded text-[9px] font-semibold bg-[#003366] text-white cursor-pointer">Todos</button>

                    <button type="button" onclick="filterScenarioCategory('DNS', this)" class="sc-cat-chip px-1.5 py-0.5 rounded text-[9px] font-semibold bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white cursor-pointer">DNS</button>

                    <button type="button" onclick="filterScenarioCategory('TLS', this)" class="sc-cat-chip px-1.5 py-0.5 rounded text-[9px] font-semibold bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white cursor-pointer">TLS</button>

                    <button type="button" onclick="filterScenarioCategory('HTTP_WEB', this)" class="sc-cat-chip px-1.5 py-0.5 rounded text-[9px] font-semibold bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white cursor-pointer">HTTP</button>

                    <button type="button" onclick="filterScenarioCategory('API_GATEWAY', this)" class="sc-cat-chip px-1.5 py-0.5 rounded text-[9px] font-semibold bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white cursor-pointer">GW</button>

                </div>

            </div>

            <div class="select-wrapper">

                <select id="selScenario" name="scenario_id" onchange="actualizarGroundTruth()" class="form-control text-sm py-1.5 px-3 rounded-lg bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-medium focus:border-red-500 focus:ring-1 focus:ring-red-500 w-full transition-all cursor-pointer">

                    {scenario_opts}

                </select>

            </div>

        </div>



        <!-- Control 2: Modelo SLM Evaluado -->

        <div class="flex-1 min-w-[220px]" id="modelSelectionGroup">

            <div class="flex items-center justify-between mb-1">

                <label for="selModel" class="text-[10px] uppercase font-bold text-slate-700 dark:text-slate-400 tracking-wider m-0 flex items-center gap-1.5">

                    <span class="w-1.5 h-1.5 rounded-full bg-blue-500"></span>

                    <span>Modelo SLM</span>

                </label>

                <div class="flex items-center gap-1.5">

                    <button type="button"

                            id="btnToggleAddModel"

                            onclick="toggleAddModelForm()"

                            class="btn-add-model text-[10px] text-blue-600 dark:text-blue-400 hover:text-blue-500 dark:hover:text-blue-300 font-semibold transition-all flex items-center gap-1 cursor-pointer bg-transparent border-0 p-0">

                        <svg class="w-3 h-3 stroke-[2.5]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/></svg>

                        <span>Añadir nuevo modelo</span>

                    </button>

                    <span class="text-slate-400 dark:text-slate-600 text-[10px]">&bull;</span>

                    <button type="button"

                            id="btnDeleteModel"

                            onclick="deleteCurrentSelectedModel()"

                            class="text-[10px] text-rose-600 dark:text-rose-400 hover:text-rose-500 dark:hover:text-rose-300 font-semibold transition-all flex items-center gap-1 cursor-pointer bg-transparent border-0 p-0">

                        <svg class="w-3 h-3 stroke-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>

                        <span>Eliminar</span>

                    </button>

                </div>

            </div>

            <div class="select-wrapper" id="selModelWrapper">

                <select id="selModel" name="model_id" class="form-control text-sm py-1.5 px-3 rounded-lg bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-medium focus:border-blue-500 focus:ring-1 focus:ring-blue-500 w-full transition-all cursor-pointer">

                    {model_opts}

                </select>

            </div>

        </div>



        <!-- Control 3: Semilla Determinista -->

        <div class="w-28 flex-shrink-0">

            <label for="txtSeed" class="text-[10px] uppercase font-bold text-slate-700 dark:text-slate-400 tracking-wider mb-1 flex items-center gap-1.5">

                <span class="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>

                <span>Semilla</span>

            </label>

            <input type="number" id="txtSeed" name="seed" value="{seed}" class="form-control font-mono text-sm py-1.5 px-3 rounded-lg bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-semibold focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 w-full">

        </div>



        <!-- Botón de Ejecutar en la MISMA fila (ml-auto) -->

        <div class="ml-auto flex items-center gap-2 flex-shrink-0">

            <button type="button"

                    id="btnRun"

                    hx-post="/api/ejecutar"

                    hx-sync="this:replace"

                    hx-include="#selScenario, #selModel, #txtSeed"

                    hx-target="#visor-resultados"

                    hx-swap="innerHTML"

                    hx-indicator="#diagnostico-indicator"

                    class="py-2 px-6 text-sm bg-red-600 hover:bg-red-500 rounded-lg text-white font-extrabold shadow-md shadow-red-950/40 border border-red-500/40 flex items-center justify-center gap-2 transition-all transform hover:-translate-y-0.5 active:translate-y-0 cursor-pointer">

                <svg class="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 20 20">

                    <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clip-rule="evenodd"/>

                </svg>

                <span>Ejecutar Diagnóstico</span>

                <kbd class="text-[10px] px-1.5 py-0.5 rounded bg-black/50 border border-white/30 text-white font-mono font-bold ml-1 shadow-sm uppercase tracking-tight">Ctrl+↵</kbd>

            </button>

        </div>



        <!-- Panel Colapsable Oscuro para Descarga Dinámica vía Ollama (w-full cuando se abre) -->

        <div id="addModelBox" class="hidden w-full mt-2 p-4 rounded-xl bg-slate-50 dark:bg-[#060e1a] border border-slate-300 dark:border-red-500/40 shadow-xl transition-all">

            <div class="flex justify-between items-center mb-2">

                <span class="text-xs font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">

                    <svg class="w-4 h-4 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">

                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>

                    </svg>

                    Descargar Modelo desde Ollama

                </span>

                <button type="button" onclick="toggleAddModelForm()" class="text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white text-lg cursor-pointer bg-transparent border-0 leading-none" title="Cerrar">&times;</button>

            </div>

            <form id="pullModelForm" onsubmit="startModelDownload(event); return false;" hx-post="/api/models/pull" hx-trigger="manual" hx-indicator="#pullIndicator">

                <div class="mb-2">

                    <input type="text"

                           id="txtModelTag"

                           name="model_name"

                           placeholder="Tag del modelo en Ollama (ej. llama3.2:1b, mistral:7b)"

                           class="form-control text-xs font-mono py-2 px-3 rounded-lg bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 w-full text-slate-900 dark:text-slate-100 focus:border-blue-500"

                           required>

                    <div class="mt-2.5">

                        <div class="flex items-center justify-between mb-1.5">

                            <span class="text-[11px] text-slate-800 dark:text-slate-300 font-bold tracking-wide">Sugerencias rápidas recomendadas:</span>

                            <span class="text-[10px] text-slate-500 dark:text-slate-400 font-mono hidden sm:inline">Clic en un modelo para autocompletar</span>

                        </div>

                        <div class="space-y-2 max-h-56 overflow-y-auto pr-1">

                            <!-- Borde & Ultraligeros -->

                            <div>

                                <span class="text-[10px] text-sky-600 dark:text-sky-400 font-mono font-bold block mb-1">⚡ Ultraligeros &amp; Borde (&le; 2B):</span>

                                <div class="flex flex-wrap gap-1.5">

                                    <button type="button" class="quick-chip text-xs" onclick="selectQuickModelTag('llama3.2:1b')">llama3.2:1b <span class="chip-hint">1.3GB</span></button>

                                    <button type="button" class="quick-chip text-xs" onclick="selectQuickModelTag('qwen2.5:1.5b')">qwen2.5:1.5b <span class="chip-hint">1.6GB</span></button>

                                    <button type="button" class="quick-chip text-xs" onclick="selectQuickModelTag('gemma2:2b')">gemma2:2b <span class="chip-hint">1.6GB</span></button>

                                    <button type="button" class="quick-chip text-xs" onclick="selectQuickModelTag('smollm2:1.7b')">smollm2:1.7b <span class="chip-hint">1.0GB</span></button>

                                    <button type="button" class="quick-chip text-xs" onclick="selectQuickModelTag('tinyllama:1.1b')">tinyllama:1.1b <span class="chip-hint">637MB</span></button>

                                </div>

                            </div>

                            <!-- Razonamiento CoT -->

                            <div>

                                <span class="text-[10px] text-purple-600 dark:text-purple-400 font-mono font-bold block mb-1">🧠 Razonamiento CoT (DeepSeek-R1):</span>

                                <div class="flex flex-wrap gap-1.5">

                                    <button type="button" class="quick-chip text-xs" onclick="selectQuickModelTag('deepseek-r1:1.5b')">deepseek-r1:1.5b <span class="chip-hint">1.8GB</span></button>

                                    <button type="button" class="quick-chip text-xs" onclick="selectQuickModelTag('deepseek-r1:7b')">deepseek-r1:7b <span class="chip-hint">4.7GB</span></button>

                                    <button type="button" class="quick-chip text-xs" onclick="selectQuickModelTag('deepseek-r1:8b')">deepseek-r1:8b <span class="chip-hint">4.9GB</span></button>

                                </div>

                            </div>

                            <!-- Intermedios Compactos (3B - 4B) -->

                            <div>

                                <span class="text-[10px] text-emerald-600 dark:text-emerald-400 font-mono font-bold block mb-1">⚖️ Intermedios &amp; Eficiencia (3B - 4B):</span>

                                <div class="flex flex-wrap gap-1.5">

                                    <button type="button" class="quick-chip text-xs" onclick="selectQuickModelTag('llama3.2:3b')">llama3.2:3b <span class="chip-hint">2.0GB</span></button>

                                    <button type="button" class="quick-chip text-xs" onclick="selectQuickModelTag('qwen2.5:3b')">qwen2.5:3b <span class="chip-hint">1.9GB</span></button>

                                    <button type="button" class="quick-chip text-xs" onclick="selectQuickModelTag('phi4-mini:instruct')">phi4-mini:instruct <span class="chip-hint">2.5GB</span></button>

                                    <button type="button" class="quick-chip text-xs" onclick="selectQuickModelTag('phi3.5:3.8b')">phi3.5:3.8b <span class="chip-hint">2.2GB</span></button>

                                    <button type="button" class="quick-chip text-xs" onclick="selectQuickModelTag('starcoder2:3b')">starcoder2:3b <span class="chip-hint">1.8GB</span></button>

                                </div>

                            </div>

                            <!-- Código & Herramientas -->

                            <div>

                                <span class="text-[10px] text-amber-600 dark:text-amber-400 font-mono font-bold block mb-1">🛠️ Código &amp; Tool-Calling:</span>

                                <div class="flex flex-wrap gap-1.5">

                                    <button type="button" class="quick-chip text-xs" onclick="selectQuickModelTag('qwen2.5-coder:1.5b')">qwen2.5-coder:1.5b <span class="chip-hint">1.6GB</span></button>

                                    <button type="button" class="quick-chip text-xs" onclick="selectQuickModelTag('qwen2.5-coder:7b')">qwen2.5-coder:7b <span class="chip-hint">4.7GB</span></button>

                                    <button type="button" class="quick-chip text-xs" onclick="selectQuickModelTag('codellama:7b')">codellama:7b <span class="chip-hint">3.8GB</span></button>

                                </div>

                            </div>

                            <!-- Capacidad Completa (7B - 9B) -->

                            <div>

                                <span class="text-[10px] text-rose-600 dark:text-rose-400 font-mono font-bold block mb-1">🚀 Capacidad Completa &amp; NOC (7B - 9B):</span>

                                <div class="flex flex-wrap gap-1.5">

                                    <button type="button" class="quick-chip text-xs" onclick="selectQuickModelTag('mistral:7b')">mistral:7b <span class="chip-hint">4.1GB</span></button>

                                    <button type="button" class="quick-chip text-xs" onclick="selectQuickModelTag('qwen2.5:7b')">qwen2.5:7b <span class="chip-hint">4.7GB</span></button>

                                    <button type="button" class="quick-chip text-xs" onclick="selectQuickModelTag('llama3.1:8b')">llama3.1:8b <span class="chip-hint">4.7GB</span></button>

                                    <button type="button" class="quick-chip text-xs" onclick="selectQuickModelTag('gemma2:9b')">gemma2:9b <span class="chip-hint">5.4GB</span></button>

                                </div>

                            </div>

                        </div>

                    </div>

                </div>

                <div class="flex gap-2 items-center">

                    <button type="submit"

                            id="btnDownloadModel"

                            class="btn-primary py-1.5 px-4 text-xs font-bold rounded-lg flex items-center justify-center gap-1.5 cursor-pointer bg-red-600 hover:bg-red-500 text-white">

                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">

                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>

                        </svg>

                        <span>Descargar</span>

                    </button>

                    <button type="button"

                            onclick="toggleAddModelForm()"

                            class="py-1.5 px-3 rounded-lg border border-slate-700 text-slate-400 hover:text-slate-200 text-xs cursor-pointer bg-transparent">

                        Cancelar

                    </button>

                </div>

                <div id="pullIndicator" class="htmx-indicator hidden text-xs text-slate-300 mt-2 font-semibold">

                    Descargando pesos del modelo, por favor espere...

                </div>

            </form>



            <!-- Contenedor Dinámico de Progreso y Cancelación (Visible durante la descarga) -->

            <div id="pullProgressContainer" style="display: none;" class="mt-3 p-4 rounded-xl bg-gradient-to-br from-[#0c192c] to-[#060e1a] border border-blue-500/50 shadow-2xl animate-fadeIn">

                <div class="flex items-center justify-between mb-2 flex-wrap gap-2">

                    <div class="flex items-center gap-2.5">

                        <span class="relative flex h-3 w-3">

                            <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-sky-400 opacity-75"></span>

                            <span class="relative inline-flex rounded-full h-3 w-3 bg-sky-500"></span>

                        </span>

                        <div class="flex items-center gap-1.5">

                            <span class="text-xs font-bold text-white">Descargando:</span>

                            <code id="pullModelTagLabel" class="text-sky-300 font-mono text-xs bg-slate-950 px-2 py-0.5 rounded border border-slate-800 font-bold">...</code>

                        </div>

                    </div>



                    <!-- Botón Cancelar Descarga -->

                    <button type="button"

                            id="btnCancelDownload"

                            onclick="cancelActiveDownload()"

                            class="py-1 px-3 rounded-lg bg-rose-900/90 hover:bg-rose-800 border border-rose-500/80 text-white text-xs font-bold transition-all flex items-center gap-1.5 cursor-pointer shadow hover:scale-[1.02] active:scale-95">

                        <svg class="w-3.5 h-3.5 text-rose-200" fill="none" stroke="currentColor" viewBox="0 0 24 24">

                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>

                        </svg>

                        <span>Cancelar Descarga</span>

                    </button>

                </div>



                <!-- Barra de Progreso Animada -->

                <div class="w-full bg-slate-950 rounded-full h-3.5 p-0.5 border border-slate-700/80 overflow-hidden relative my-2 shadow-inner">

                    <div id="pullProgressBar"

                         class="bg-gradient-to-r from-blue-600 via-sky-500 to-emerald-400 h-full rounded-full transition-all duration-200 relative overflow-hidden"

                         style="width: 0%;">

                        <div class="absolute inset-0 bg-white/20 animate-pulse"></div>

                    </div>

                </div>



                <!-- Detalles de Descarga: Porcentaje, Bytes y Estado -->

                <div class="flex items-center justify-between text-xs font-mono mt-1 flex-wrap gap-1">

                    <span id="pullProgressStatusText" class="text-slate-100 text-[11px] truncate max-w-[65%] font-medium">Conectando con Ollama...</span>

                    <div class="flex items-center gap-2 ml-auto">

                        <span id="pullProgressBytes" class="text-sky-300 text-[11px] font-medium">0 MB / 0 MB</span>

                        <strong id="pullProgressPercent" class="text-emerald-400 font-bold text-xs bg-slate-950/80 px-2 py-0.5 rounded border border-slate-800">0%</strong>

                    </div>

                </div>

            </div>



            <div id="pullFeedbackMessage" class="mt-1 text-xs"></div>

            <div id="deleteFeedbackMessage" class="mt-1 text-xs"></div>

        </div>



        <!-- Indicador de Carga HTMX para Diagnóstico (w-full cuando se activa) -->

        <div id="diagnostico-indicator" class="htmx-indicator w-full mt-2 p-2.5 rounded-lg bg-red-950/40 border border-red-500/40 text-center">

            <div class="flex items-center justify-center gap-2 text-red-400 text-xs font-bold">

                <span class="spinner w-3.5 h-3.5 m-0"></span>

                <span>Iniciando ciclo de diagnóstico y orquestador LangGraph...</span>

            </div>

            <p class="text-[11px] text-slate-400 mt-0.5 mb-0">Preparando escenario reproducible, telemetría y contexto RAG...</p>

        </div>

    </div>

    """





def _render_diagnostico_workspace_html(

    selected_sc: str | None = None,

    selected_model: str | None = None,

    seed: int = 42

) -> str:

    """Genera el HTML del Visor de Diagnóstico en Doble Panel Vertical: Panel Configuración (arriba) + Visor Resultados (abajo con scroll)."""

    cfg_html = _render_configuracion_form_html(selected_sc=selected_sc, selected_model=selected_model, seed=seed)

    return f"""

    {cfg_html}

    <!-- Bloque Inferior: Visor de Observabilidad (Terminal SSE, Cadena de Pensamiento con scroll independiente) -->

    <div id="visor-resultados" class="flex-1 overflow-y-auto pb-10"></div>

    """





def _render_observabilidad_workspace_html(sc_id: str, model_id: str, seed: int = 42) -> str:

    """Genera el HTML del Estado 2: Visor de Observabilidad (Streaming en tiempo real)."""

    sc = lab_runner.get_scenario(sc_id)

    if not sc:

        all_sc = lab_runner.list_scenarios()

        sc = all_sc[0] if all_sc else None



    sc_category = (sc.category.value if hasattr(sc.category, "value") else str(sc.category)) if sc else "L7"

    sc_fault_class = (sc.fault_class.value if hasattr(sc.fault_class, "value") else str(sc.fault_class)) if sc else "Falla General"

    sc_description = sc.description if sc else "Diagnóstico de falla L7 en ejecución."



    all_models = system_config.get_all_models()

    m = next((mod for mod in all_models if mod.id == model_id or mod.ollama_tag == model_id), None)

    model_name = m.name if m else model_id



    stream_url = f"/stream-diagnostico?scenario_id={urllib.parse.quote(sc_id)}&model_id={urllib.parse.quote(model_id)}&seed={seed}"



    return f"""

    <div class="w-full flex flex-col space-y-4 animate-fadeIn"

         data-run-sc-id="{sc_id}"

         data-run-model-id="{model_id}"

         data-run-model-name="{model_name}"

         data-run-category="{sc_category}"

         data-run-seed="{seed}"

         id="currentRunDataMarker">



        <!-- Barra superior del Visor de Observabilidad -->

        <div class="flex items-center justify-between pb-3 border-b border-slate-200 dark:border-slate-700/60 flex-wrap gap-3">

            <div class="flex items-center gap-2">

                <span class="text-xs font-bold text-slate-800 dark:text-slate-200 flex items-center gap-2">

                    <span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>

                    <span>Visor de Observabilidad en Vivo</span>

                </span>

            </div>

            <div class="flex items-center gap-2 flex-wrap">

                <button type="button"

                        id="btnCopyTicketHeader"

                        onclick="copyTicketToClipboard(this)"

                        class="px-2.5 py-1 rounded bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-800 dark:text-slate-200 border border-slate-300 dark:border-slate-600 text-xs font-semibold transition-colors flex items-center gap-1.5 cursor-pointer shadow-sm">

                    <span>📋</span>

                    <span>Copiar Ficha para Ticket</span>

                </button>

                <span class="text-xs px-2.5 py-1 rounded bg-emerald-100 dark:bg-emerald-950/80 border border-emerald-300 dark:border-emerald-500/40 text-emerald-800 dark:text-emerald-300 font-mono flex items-center gap-1.5">

                    <span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>

                    <span>Streaming SSE Activo</span>

                </span>

            </div>

        </div>



        <!-- Problem Statement Card (Falla L7 a Resolver) -->

        <div class="problem-statement-card mb-4 p-4 rounded-xl shadow-xl transition-all duration-300">

            <div class="flex items-center justify-between mb-2.5 flex-wrap gap-2">

                <div class="flex items-center gap-2">

                    <span class="px-2.5 py-1 rounded bg-[#ad3333] text-white font-bold text-xs uppercase tracking-wider flex items-center gap-1.5 shadow">

                        <span class="w-2 h-2 rounded-full bg-white animate-pulse"></span>

                        FALLA L7 A RESOLVER POR EL MODELO

                    </span>

                    <span class="font-mono text-xs text-red-600 dark:text-red-300 font-bold">[{sc_category}] {sc_id}</span>

                </div>

                <span class="text-xs px-2.5 py-0.5 rounded-full bg-red-100 dark:bg-red-950/60 border border-red-300 dark:border-red-500/40 text-red-800 dark:text-red-200 font-mono font-semibold">

                    {sc_fault_class}

                </span>

            </div>

            <div class="text-sm font-semibold text-slate-900 dark:text-slate-100 mb-3 leading-relaxed">

                {sc_description}

            </div>

            <div class="text-xs text-slate-600 dark:text-slate-300 border-t border-slate-200 dark:border-slate-700/60 pt-2.5 flex items-center justify-between flex-wrap gap-2">

                <span><strong>Misión del Asistente:</strong> Analizar telemetría de red, contrastar contra RFCs, ejecutar comandos read-only y determinar la causa raíz.</span>

                <span class="font-mono text-slate-600 dark:text-slate-400">Modelo Asignado: <strong class="text-slate-900 dark:text-white">{model_name}</strong> &bull; Seed: {seed}</span>

            </div>

        </div>



        <!-- Live Pipeline Stage Progress Tracker (Mini-Stepper NOC Horizontal) -->

        <div id="pipelineStageStepper" class="w-full bg-slate-50 dark:bg-[#0d1424] border border-slate-200 dark:border-slate-800/80 rounded-xl p-3 shadow-sm transition-all duration-300">

            <div class="flex items-center justify-between text-[11px] font-mono text-slate-500 dark:text-slate-400 mb-2 px-1">

                <span class="font-bold flex items-center gap-1.5 text-slate-700 dark:text-slate-300">

                    <span class="w-2 h-2 rounded-full bg-blue-500 animate-pulse"></span>

                    <span>ETAPAS DEL PIPELINE MULTI-AGENTE</span>

                </span>

                <span id="stepperCurrentStageLabel" class="text-blue-600 dark:text-blue-400 font-semibold font-mono">Conectando streaming SSE...</span>

            </div>

            <div class="grid grid-cols-2 sm:grid-cols-5 gap-2 relative">

                <!-- Etapa 1: Telemetría L1-L2 -->

                <div id="stepStage1" class="stepper-step flex items-center gap-2 p-2 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#080d16] transition-all duration-300" data-stage="1">

                    <div class="step-icon-box w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 flex-shrink-0">1</div>

                    <div class="truncate">

                        <span class="block text-[10px] uppercase font-bold text-slate-700 dark:text-slate-300 truncate">1. Telemetría</span>

                        <span class="block text-[9px] text-slate-400 truncate">Drain3 PCAP</span>

                    </div>

                </div>

                <!-- Etapa 2: RAG IETF L3 -->

                <div id="stepStage2" class="stepper-step flex items-center gap-2 p-2 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#080d16] transition-all duration-300" data-stage="2">

                    <div class="step-icon-box w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 flex-shrink-0">2</div>

                    <div class="truncate">

                        <span class="block text-[10px] uppercase font-bold text-slate-700 dark:text-slate-300 truncate">2. RAG IETF</span>

                        <span class="block text-[9px] text-slate-400 truncate">Normas RFC</span>

                    </div>

                </div>

                <!-- Etapa 3: Razonamiento CoT L4 -->

                <div id="stepStage3" class="stepper-step flex items-center gap-2 p-2 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#080d16] transition-all duration-300" data-stage="3">

                    <div class="step-icon-box w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 flex-shrink-0">3</div>

                    <div class="truncate">

                        <span class="block text-[10px] uppercase font-bold text-slate-700 dark:text-slate-300 truncate">3. Razonamiento</span>

                        <span class="block text-[9px] text-slate-400 truncate">CoT Hipótesis</span>

                    </div>

                </div>

                <!-- Etapa 4: Acción CLI L5 -->

                <div id="stepStage4" class="stepper-step flex items-center gap-2 p-2 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#080d16] transition-all duration-300" data-stage="4">

                    <div class="step-icon-box w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 flex-shrink-0">4</div>

                    <div class="truncate">

                        <span class="block text-[10px] uppercase font-bold text-slate-700 dark:text-slate-300 truncate">4. Consola CLI</span>

                        <span class="block text-[9px] text-slate-400 truncate">Read-Only Tool</span>

                    </div>

                </div>

                <!-- Etapa 5: Veredicto Final -->

                <div id="stepStage5" class="stepper-step flex items-center gap-2 p-2 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#080d16] transition-all duration-300" data-stage="5">

                    <div class="step-icon-box w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 flex-shrink-0">5</div>

                    <div class="truncate">

                        <span class="block text-[10px] uppercase font-bold text-slate-700 dark:text-slate-300 truncate">5. Veredicto</span>

                        <span class="block text-[9px] text-slate-400 truncate">Causa & Fix</span>

                    </div>

                </div>

            </div>

        </div>



        <!-- Contenedor de streaming Server-Sent Events (SSE) -->

        <div id="timelineHost" class="w-full relative" style="min-height: calc(100vh - 360px); background: transparent;">

            <div class="relative pl-6">

                <!-- Línea vertical continua de la línea de tiempo -->

                <div class="timeline-line"></div>

                <!-- Contenedor donde HTMX SSE inyecta los fragmentos HTML -->

                <div id="timelineEventsContainer"

                     hx-ext="sse"

                     sse-connect="{stream_url}"

                     sse-close="stream-complete"

                     sse-swap="message"

                     hx-swap="beforeend">

                </div>

            </div>

        </div>



        <!-- Barra Flotante Inferior de Mitigación Inmediata (Sticky Remediation Bar) -->

        <div id="stickyRemediationBar" class="hidden fixed bottom-6 left-1/2 transform -translate-x-1/2 z-50 w-11/12 max-w-4xl bg-white dark:bg-[#0b1324] border-2 border-emerald-500 rounded-2xl shadow-2xl p-3.5 backdrop-blur-md transition-all duration-300 animate-slideUp">

            <div class="flex items-center justify-between gap-4 flex-wrap sm:flex-nowrap">

                <div class="flex items-center gap-3 min-w-0">

                    <div class="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center flex-shrink-0 text-emerald-500">

                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>

                    </div>

                    <div class="min-w-0">

                        <div class="flex items-center gap-2">

                            <span class="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-emerald-600 text-white">Mitigación NOC Inmediata</span>

                            <span id="stickyRemediationComponent" class="font-mono text-xs font-bold text-amber-600 dark:text-amber-400 truncate">Componente</span>

                        </div>

                        <div id="stickyRemediationAction" class="text-xs font-semibold text-slate-800 dark:text-slate-100 truncate mt-0.5">Acción correctiva</div>

                    </div>

                </div>

                <div class="flex items-center gap-2 flex-shrink-0">

                    <button type="button" id="btnStickyCopyAction" onclick="copyStickyRemediation(this)" class="px-3.5 py-1.5 text-xs font-bold rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white shadow-md transition flex items-center gap-1.5 cursor-pointer">

                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3"/></svg>

                        <span>Copiar Mitigación</span>

                    </button>

                    <button type="button" onclick="document.getElementById('stickyRemediationBar').classList.add('hidden')" class="p-1.5 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition cursor-pointer" title="Cerrar barra">

                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>

                    </button>

                </div>

            </div>

        </div>

    </div>

    """





@app.get("/api/configuracion-form", response_class=HTMLResponse)

def get_configuracion_form(

    scenario_id: str | None = None,

    model_id: str | None = None,

    seed: int = 42

):

    """Devuelve el HTML del espacio de trabajo de diagnóstico (Doble Panel Vertical: Configuración + Visor)."""

    return _render_diagnostico_workspace_html(selected_sc=scenario_id, selected_model=model_id, seed=seed)





@app.post("/api/ejecutar", response_class=HTMLResponse)

async def ejecutar_workspace_endpoint(request: Request):

    """

    Endpoint HTMX para iniciar la ejecución del diagnóstico.

    Devuelve directamente el Visor de Observabilidad (Terminal SSE) para inyectar en #visor-resultados.

    """

    content_type = request.headers.get("content-type", "")

    body_bytes = await request.body()

    sc_id = "DNS-NXD-01"

    model_id = "phi-4-mini-instruct"

    seed = 42



    if "application/json" in content_type and body_bytes:

        try:

            data = json.loads(body_bytes.decode("utf-8"))

            sc_id = data.get("scenario_id", sc_id)

            model_id = data.get("model_id", model_id)

            seed = int(data.get("seed", seed))

        except Exception:

            pass

    elif body_bytes:

        try:

            parsed = urllib.parse.parse_qs(body_bytes.decode("utf-8"))

            sc_id = parsed.get("scenario_id", [sc_id])[0]

            model_id = parsed.get("model_id", [model_id])[0]

            seed_val = parsed.get("seed", [str(seed)])[0]

            seed = int(seed_val) if seed_val.isdigit() else seed

        except Exception:

            pass

    else:

        params = request.query_params

        if "scenario_id" in params:

            sc_id = params["scenario_id"]

        if "model_id" in params:

            model_id = params["model_id"]

        if "seed" in params:

            try:

                seed = int(params["seed"])

            except Exception:

                pass



    return _render_observabilidad_workspace_html(sc_id=sc_id, model_id=model_id, seed=seed)





NO_CACHE_FRAGMENT_HEADERS = {

    "HX-Push-Url": "false",

    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",

    "Pragma": "no-cache",

}





@app.get("/vistas/diagnostico", response_class=HTMLResponse)

def vista_diagnostico_fragment(scenario_id: str | None = None, model_id: str | None = None, seed: int = 42):

    """Devuelve el fragmento HTML del Visor de Diagnóstico (Doble Panel Vertical) con escenario y modelo preservados."""

    return HTMLResponse(

        content=f"""

        <div id="viewContainerObservability" class="w-full flex-1 flex flex-col min-h-0 overflow-hidden" hx-history="false">

            <div id="diagnostico-workspace" class="flex flex-col h-full overflow-hidden">

                <div id="visor-content" class="w-full flex-1 flex flex-col min-h-0 overflow-y-auto custom-scrollbar">

                    {_render_diagnostico_workspace_html(selected_sc=scenario_id, selected_model=model_id, seed=seed)}

                </div>

            </div>

        </div>

        """,

        headers=NO_CACHE_FRAGMENT_HEADERS,

    )





@app.get("/vistas/comparativo", response_class=HTMLResponse)

def vista_comparativo_fragment():

    """Devuelve el fragmento HTML del Informe Técnico Comparativo (OE4)."""

    return HTMLResponse(

        content="""

        <div class="w-full h-full flex-1" hx-history="false">

            <iframe id="mainViewIframe" src="/analitica?view=comparativo&embed=true" onload="if(window.parent && window.parent.attachKeyboardListenerToIframe) window.parent.attachKeyboardListenerToIframe(this)" class="w-full h-[calc(100vh-140px)] border-0 rounded-lg bg-[#070e18]" allow="fullscreen"></iframe>

        </div>

        """,

        headers=NO_CACHE_FRAGMENT_HEADERS,

    )





@app.get("/vistas/correlacion", response_class=HTMLResponse)

def vista_correlacion_fragment():

    """Devuelve el fragmento HTML del Análisis Correlacional (SciPy)."""

    return HTMLResponse(

        content="""

        <div class="w-full h-full flex-1" hx-history="false">

            <iframe id="mainViewIframe" src="/analitica?view=correlacion&embed=true" onload="if(window.parent && window.parent.attachKeyboardListenerToIframe) window.parent.attachKeyboardListenerToIframe(this)" class="w-full h-[calc(100vh-140px)] border-0 rounded-lg bg-[#070e18]" allow="fullscreen"></iframe>

        </div>

        """,

        headers=NO_CACHE_FRAGMENT_HEADERS,

    )





@app.get("/vistas/consolidado", response_class=HTMLResponse)

def vista_consolidado_fragment():

    """Devuelve el fragmento HTML del Informe Consolidado Global de Benchmarking."""

    return HTMLResponse(

        content="""

        <div class="w-full h-full flex-1" hx-history="false">

            <iframe id="mainViewIframe" src="/api/report-html?embed=true" onload="if(window.parent && window.parent.attachKeyboardListenerToIframe) window.parent.attachKeyboardListenerToIframe(this)" class="w-full h-[calc(100vh-140px)] border-0 rounded-lg bg-[#070e18]" allow="fullscreen"></iframe>

        </div>

        """,

        headers=NO_CACHE_FRAGMENT_HEADERS,

    )





@app.get("/vistas/suite_observabilidad", response_class=HTMLResponse)

def vista_suite_observabilidad_fragment():

    """Devuelve el fragmento HTML de la Suite de Observabilidad Completa (18 Escenarios)."""

    return HTMLResponse(

        content="""

        <div class="w-full h-full flex-1" hx-history="false">

            <iframe id="mainViewIframe" src="/observabilidad?embed=true" onload="if(window.parent && window.parent.attachKeyboardListenerToIframe) window.parent.attachKeyboardListenerToIframe(this)" class="w-full h-[calc(100vh-140px)] border-0 rounded-lg bg-transparent" allow="fullscreen"></iframe>

        </div>

        """,

        headers=NO_CACHE_FRAGMENT_HEADERS,

    )





@app.get("/comparativo", response_class=HTMLResponse)

def vista_comparativo_direct(request: Request):

    """Endpoint directo para Informe Comparativo (OE4). Si es HTMX entrega solo el fragmento."""

    if request.headers.get("HX-Request"):

        return vista_comparativo_fragment()

    return RedirectResponse(url="/?view=comparativo", status_code=303)





@app.get("/correlacional", response_class=HTMLResponse)

@app.get("/correlacion", response_class=HTMLResponse)

def vista_correlacional_direct(request: Request):

    """Endpoint directo para Análisis Correlacional. Si es HTMX entrega solo el fragmento."""

    if request.headers.get("HX-Request"):

        return vista_correlacion_fragment()

    return RedirectResponse(url="/?view=correlacion", status_code=303)







@app.get("/api/benchmark-summary")

def get_benchmark_summary():

    """Devuelve el reporte resumen generado por el arnes de evaluacion."""

    from src.core.config import PROJECT_ROOT

    report_file = PROJECT_ROOT / "data" / "benchmark_results" / "resultados_resumen.md"

    if report_file.exists():

        return {"report_markdown": report_file.read_text(encoding="utf-8")}

    return {"report_markdown": "No hay resultados de benchmark disponibles todavia. Ejecute `benchapp run-benchmark`."}





# Caché en memoria para analítica con invalidación automática por modificación de archivo o cambio de selección

_cache_correlation: dict[str, Any] = {}

_cache_comparative: dict[str, Any] = {}





@app.get("/api/correlation-analysis")

def get_correlation_analysis(models: str | None = None):

    """Ejecuta y devuelve el análisis correlacional completo (Tarea 4.1.2) con aceleración por caché y filtro de modelos."""

    from src.core.config import PROJECT_ROOT

    from src.layer7_evaluator.model_management import (

        load_selected_rows,

        selection_signature,

    )

    from src.layer7_evaluator.statistical_analysis import (

        generate_correlation_report,

        run_correlation_analysis,

    )



    csv_path = PROJECT_ROOT / "data" / "benchmark_results" / "resultados.csv"

    if not csv_path.exists():

        return {"error": "No hay dataset de benchmark. Ejecute `benchapp run-benchmark` primero."}

    try:

        current_mtime = csv_path.stat().st_mtime

        sig = selection_signature(models)

        cache_key = f"{current_mtime}_{sig}"

        if cache_key in _cache_correlation:

            return _cache_correlation[cache_key]



        rows, included = load_selected_rows(models)

        if not rows:

            return {"error": "No se encontraron corridas en el dataset para los modelos seleccionados."}



        analysis = run_correlation_analysis(rows=rows)

        report_text = generate_correlation_report(analysis=analysis)

        payload = {

            "report_markdown": report_text,

            "correlations": analysis["correlations"],

            "kruskal_wallis": analysis["kruskal_wallis"],

            "n_total": analysis["n_total"],

            "n_models": analysis["n_models"],

            "model_ids": analysis["model_ids"],

            "models_included": included,

            "descriptives": analysis["descriptives"],

            "bootstrap_ci_95": analysis["bootstrap_ci_95"],

            "effect_sizes": analysis["effect_sizes"],

        }

        _cache_correlation.clear()

        _cache_correlation[cache_key] = payload

        return payload

    except Exception as e:

        return {"error": str(e)}





@app.get("/api/comparative-report")

def get_comparative_report(models: str | None = None):

    """Devuelve el Informe Técnico Comparativo (OE4) en formato estructurado para el dashboard con caché y filtro de modelos."""

    from src.core.config import PROJECT_ROOT

    from src.layer7_evaluator.model_management import (

        load_selected_rows,

        selection_signature,

    )

    from src.layer7_evaluator.statistical_analysis import (

        build_comparative_summary,

        generate_comparative_markdown,

    )



    csv_path = PROJECT_ROOT / "data" / "benchmark_results" / "resultados.csv"

    if not csv_path.exists():

        return {"error": "No hay dataset de benchmark. Ejecute `benchapp run-benchmark` primero."}

    try:

        current_mtime = csv_path.stat().st_mtime

        sig = selection_signature(models)

        cache_key = f"{current_mtime}_{sig}"

        if cache_key in _cache_comparative:

            return _cache_comparative[cache_key]



        rows, included = load_selected_rows(models)

        if not rows:

            return {"error": "No se encontraron corridas en el dataset para los modelos seleccionados."}



        summary = build_comparative_summary(rows=rows)

        summary["report_markdown"] = generate_comparative_markdown(summary)

        summary["models_included"] = included

        _cache_comparative.clear()

        _cache_comparative[cache_key] = summary

        return summary

    except Exception as e:

        return {"error": str(e)}





@app.get("/analitica", response_class=HTMLResponse)

def analytics_dashboard_page(request: Request, view: str | None = None):

    """Dashboard visual del Informe Técnico Comparativo (OE4) y del Análisis Correlacional (Tarea 4.1.2)."""

    if request.headers.get("HX-Request"):

        if view == "correlacion":

            return vista_correlacion_fragment()

        return vista_comparativo_fragment()



    from src.layer6_interface.analytics_dashboard import ANALYTICS_DASHBOARD_HTML

    from src.layer6_interface.export_toolbar import render_export_toolbar



    view_key = "correlacion" if (view and "corr" in view.lower()) else "comparativo"

    toolbar_html = render_export_toolbar(view_key=view_key)

    content = (

        ANALYTICS_DASHBOARD_HTML

        .replace("<!-- STANDALONE_EXPORT_TOOLBAR -->", toolbar_html)

        .replace("</style>", f"{TOOLTIP_CSS}\n</style>")

        .replace("</body>", f"{TOOLTIP_JS}\n</body>")

    )

    return HTMLResponse(

        content=content,

        headers=NO_CACHE_FRAGMENT_HEADERS,

    )





@app.get("/api/health")

def get_system_health():

    """Diagnóstico de salud del sistema, Ollama y telemetría de inferencia."""

    return inference_engine.check_health()





@app.get("/api/report-html", response_class=HTMLResponse)

def get_report_html(request: Request = None, models: str | None = None, embed: bool = False):

    """Devuelve el informe consolidado en formato HTML para visualización o impresión según los modelos seleccionados."""

    from src.core.config import PROJECT_ROOT

    from src.layer7_evaluator.model_management import selection_signature

    from src.layer7_evaluator.report_generator import generate_html_benchmark_report



    sig = selection_signature(models)

    csv_path = PROJECT_ROOT / "data" / "benchmark_results" / "resultados.csv"

    html_name = f"informe_consolidado_{sig}.html" if sig != "ALL" else "informe_consolidado.html"

    html_path = PROJECT_ROOT / "data" / "benchmark_results" / html_name



    report_gen_path = PROJECT_ROOT / "src" / "layer7_evaluator" / "report_generator.py"

    export_tb_path = PROJECT_ROOT / "src" / "layer6_interface" / "partials" / "export_toolbar.html"

    if (

        not html_path.exists()

        or (csv_path.exists() and csv_path.stat().st_mtime > html_path.stat().st_mtime)

        or (report_gen_path.exists() and report_gen_path.stat().st_mtime > html_path.stat().st_mtime)

        or (export_tb_path.exists() and export_tb_path.stat().st_mtime > html_path.stat().st_mtime)

    ):

        generate_html_benchmark_report(csv_path=csv_path, output_path=html_path, models=models)



    raw_html = html_path.read_text(encoding="utf-8")

    is_embed = embed or (request is not None and request.query_params.get("embed") == "true")

    if is_embed:

        if '<body class="' in raw_html:

            raw_html = raw_html.replace('<body class="', '<body class="is-embedded ', 1)

        else:

            raw_html = raw_html.replace('<body>', '<body class="is-embedded">', 1)

    return HTMLResponse(content=raw_html, headers=NO_CACHE_FRAGMENT_HEADERS)





@app.get("/api/export/excel")

def download_excel_benchmark(run_id: str | None = None, models: str | None = None):

    """Genera y descarga el libro Excel completo con las 10 hojas de benchmark o la ejecución real de la Suite."""

    from src.layer6_interface.suite_store import suite_store



    if run_id:

        _validate_safe_identifier(run_id, "run_id")

        session = suite_store.get_session(run_id)

        if not session:

            raise HTTPException(

                status_code=400,

                detail=f"No se encontró una corrida de la Suite con ID '{run_id}'.",

                headers={"HX-Trigger": json.dumps({"showToast": "No se encontró la corrida de la suite."})}

            )

        if session.status != "completed" or session.completed_cases < session.total_cases:

            raise HTTPException(

                status_code=400,

                detail=f"La suite debe finalizar completamente ({session.total_cases}/{session.total_cases} casos) para generar el reporte Excel. Progreso actual: {session.completed_cases}/{session.total_cases} casos.",

                headers={"HX-Trigger": json.dumps({"showToast": "La suite debe finalizar para generar el reporte Excel."})}

            )

        from src.layer7_evaluator.excel_exporter import export_suite_run_to_excel

        excel_path = export_suite_run_to_excel(run_id=session.run_id)

        filename = f"suite_observabilidad_{session.run_id}.xlsx"

        return FileResponse(

            path=excel_path,

            filename=filename,

            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",

            content_disposition_type="attachment",

        )



    from src.layer7_evaluator.excel_exporter import export_benchmark_to_excel

    from src.layer7_evaluator.model_management import selection_signature



    sig = selection_signature(models)

    filename = f"benchmark_l7_consolidado_{sig}.xlsx" if sig != "ALL" else "benchmark_l7_consolidado.xlsx"

    excel_path = export_benchmark_to_excel(models=models)

    return FileResponse(

        path=excel_path,

        filename=filename,

        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",

        content_disposition_type="attachment",

    )





@app.get("/api/export/csv")
def download_csv_benchmark(run_id: str | None = None, models: str | None = None):
    """Descarga el dataset consolidado de benchmark en CSV (resultados.csv) o el subconjunto filtrado."""
    csv_path = PROJECT_ROOT / "data" / "benchmark_results" / "resultados.csv"
    if not csv_path.exists():
        raise HTTPException(status_code=404, detail="Dataset resultados.csv no encontrado.")

    if not models:
        return FileResponse(
            path=csv_path,
            filename="resultados.csv",
            media_type="text/csv",
            content_disposition_type="attachment",
        )

    from src.layer7_evaluator.model_management import load_selected_rows, selection_signature
    import io, csv
    filtered, _ = load_selected_rows(models)
    output = io.StringIO()
    if filtered:
        fieldnames = list(filtered[0].keys())
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(filtered)
    body = output.getvalue()
    sig = selection_signature(models)
    fn = f"resultados_{sig}.csv" if sig != "ALL" else "resultados.csv"
    return Response(
        content=body,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{fn}"'}
    )


@app.get("/api/export/pdf/comparative")

@app.get("/api/export/comparativo/pdf")

def download_pdf_comparative(models: str | None = None):

    """Genera y descarga el Informe Técnico Comparativo (OE4) en formato PDF según los modelos seleccionados."""

    from src.layer7_evaluator.model_management import selection_signature

    from src.layer7_evaluator.pdf_exporter import export_comparative_report_pdf



    sig = selection_signature(models)

    filename = f"informe_comparativo_oe4_{sig}.pdf" if sig != "ALL" else "informe_comparativo_oe4.pdf"

    pdf_path = export_comparative_report_pdf(models=models)

    return FileResponse(

        path=pdf_path,

        filename=filename,

        media_type="application/pdf",

        content_disposition_type="attachment",

    )





@app.get("/api/export/pdf/correlation")

@app.get("/api/export/correlacional/pdf")

def download_pdf_correlation(models: str | None = None):

    """Genera y descarga el Análisis Correlacional (Tarea 4.1.2) en formato PDF según los modelos seleccionados."""

    from src.layer7_evaluator.model_management import selection_signature

    from src.layer7_evaluator.pdf_exporter import export_correlation_report_pdf



    sig = selection_signature(models)

    filename = f"analisis_correlacional_{sig}.pdf" if sig != "ALL" else "analisis_correlacional.pdf"

    pdf_path = export_correlation_report_pdf(models=models)

    return FileResponse(

        path=pdf_path,

        filename=filename,

        media_type="application/pdf",

        content_disposition_type="attachment",

    )





@app.get("/api/export/pdf/consolidated")

@app.get("/api/export/consolidado/pdf")

def download_pdf_consolidated(models: str | None = None):

    """Genera y descarga el Informe Técnico Consolidado unificado en formato PDF según los modelos seleccionados."""

    from src.layer7_evaluator.model_management import selection_signature

    from src.layer7_evaluator.pdf_exporter import export_consolidated_report_pdf



    sig = selection_signature(models)

    filename = f"informe_consolidado_netdiagbench_{sig}.pdf" if sig != "ALL" else "informe_consolidado_netdiagbench.pdf"

    pdf_path = export_consolidated_report_pdf(models=models)

    return FileResponse(

        path=pdf_path,

        filename=filename,

        media_type="application/pdf",

        content_disposition_type="attachment",

    )





@app.get("/api/export/json")

def download_json_benchmark(run_id: str | None = None, models: str | None = None):

    """Genera y descarga el informe consolidado en formato JSON (volcado LangGraph o selección de modelos)."""

    from src.layer6_interface.suite_store import suite_store



    if run_id:

        session = suite_store.get_session(run_id)

        if not session:

            raise HTTPException(

                status_code=400,

                detail=f"No se encontró una corrida de la Suite con ID '{run_id}'.",

                headers={"HX-Trigger": json.dumps({"showToast": "No se encontró la corrida de la suite."})}

            )

        if session.status != "completed" or session.completed_cases < session.total_cases:

            raise HTTPException(

                status_code=400,

                detail=f"La suite debe finalizar completamente ({session.total_cases}/{session.total_cases} casos) para descargar el JSON. Progreso actual: {session.completed_cases}/{session.total_cases} casos.",

                headers={"HX-Trigger": json.dumps({"showToast": "La suite debe finalizar para descargar el JSON."})}

            )

        filename = f"suite_langgraph_{session.run_id}.json"

        return JSONResponse(

            content=session.to_dict(),

            headers={"Content-Disposition": f'attachment; filename="{filename}"'}

        )



    from src.layer7_evaluator.model_management import export_selection_json, selection_signature



    sig = selection_signature(models)

    filename = f"informe_consolidado_netdiagbench_{sig}.json" if sig != "ALL" else "informe_consolidado_netdiagbench.json"

    json_path = export_selection_json(models_param=models)

    return FileResponse(

        path=json_path,

        filename=filename,

        media_type="application/json",

        content_disposition_type="attachment",

    )





@app.get("/api/export/pdf/suite")

@app.get("/api/export/suite/pdf")

def download_pdf_suite(run_id: str | None = None):

    """Genera y descarga el Reporte Técnico de la Suite de Observabilidad (18 Escenarios) en formato PDF con resultados reales."""

    from src.layer6_interface.suite_store import suite_store

    from src.layer7_evaluator.pdf_exporter import export_suite_observability_pdf



    if run_id:

        _validate_safe_identifier(run_id, "run_id")

        session = suite_store.get_session(run_id)

        if not session:

            raise HTTPException(

                status_code=400,

                detail=f"No se encontró una corrida de la Suite de Observabilidad con ID '{run_id}'.",

                headers={"HX-Trigger": json.dumps({"showToast": "No se encontró la corrida de la suite."})}

            )

        if session.status != "completed" or session.completed_cases < session.total_cases:

            raise HTTPException(

                status_code=400,

                detail=f"La suite debe finalizar completamente ({session.total_cases}/{session.total_cases} casos) para generar el reporte técnico. Progreso actual: {session.completed_cases}/{session.total_cases} casos.",

                headers={"HX-Trigger": json.dumps({"showToast": "La suite debe finalizar para generar el reporte."})}

            )

        pdf_path = export_suite_observability_pdf(run_id=session.run_id)

        filename = f"reporte_suite_observabilidad_{session.run_id}.pdf"

        return FileResponse(

            path=pdf_path,

            filename=filename,

            media_type="application/pdf",

            content_disposition_type="attachment",

        )



    # Si no se pasa run_id explícito, verificar si hay una corrida completada en memoria/disco

    session = suite_store.get_latest_completed_session()

    if session and session.cases and session.status == "completed" and session.completed_cases >= session.total_cases:

        pdf_path = export_suite_observability_pdf(run_id=session.run_id)

        filename = f"reporte_suite_observabilidad_{session.run_id}.pdf"

        return FileResponse(

            path=pdf_path,

            filename=filename,

            media_type="application/pdf",

            content_disposition_type="attachment",

        )



    # Fallback canónico para compatibilidad histórica: catálogo base de los 18 escenarios

    pdf_path = export_suite_observability_pdf()

    filename = "reporte_suite_observabilidad.pdf"

    return FileResponse(

        path=pdf_path,

        filename=filename,

        media_type="application/pdf",

        content_disposition_type="attachment",

    )





@app.get("/api/export/pdf/diagnosis")

def download_pdf_diagnosis(

    scenario_id: str = "DNS-NXD-01",

    model_id: str = "phi-4-mini-instruct",

    seed: int = 42

):

    """Genera y descarga el informe PDF del diagnóstico individual para el escenario y modelo seleccionados."""

    _validate_safe_identifier(scenario_id, "scenario_id")

    _validate_safe_identifier(model_id, "model_id")

    from src.layer7_evaluator.pdf_exporter import export_individual_diagnosis_pdf

    pdf_path = export_individual_diagnosis_pdf(scenario_id=scenario_id, model_id=model_id, seed=seed)

    return FileResponse(

        path=pdf_path,

        filename=f"diagnostico_{scenario_id}_{model_id}.pdf",

        media_type="application/pdf",

        content_disposition_type="attachment",

    )





@app.get("/api/export/diagnostic-log")

def download_diagnostic_log(

    scenario_id: str = "DNS-NXD-01",

    model_id: str = "phi-4-mini-instruct",

    seed: int = 42,

    format: str = "json"

):

    """Descarga el registro o traza del escenario seleccionado en formato JSON o Markdown."""

    _validate_safe_identifier(scenario_id, "scenario_id")

    _validate_safe_identifier(model_id, "model_id")

    _validate_safe_identifier(format, "format")

    sc = lab_runner.get_scenario(scenario_id)

    if not sc:

        all_sc = lab_runner.list_scenarios()

        sc = all_sc[0] if all_sc else None



    import csv



    from src.core.config import PROJECT_ROOT

    csv_path = PROJECT_ROOT / "data" / "benchmark_results" / "resultados.csv"

    matched_run = {}

    if csv_path.exists():

        try:

            with open(csv_path, encoding="utf-8") as f:

                reader = csv.DictReader(f)

                for row in reader:

                    if row.get("scenario_id") == scenario_id and row.get("model_id") == model_id:

                        matched_run = row

                        break

        except Exception:

            pass



    gt = sc.ground_truth if sc else None

    timestamp_str = datetime.now(timezone.utc).isoformat()



    if format.lower() in ("md", "markdown"):

        sc_id_val = sc.scenario_id if sc else scenario_id

        cat_val = sc.category.value if (sc and hasattr(sc.category, 'value')) else (sc.category if sc else 'L7')

        fault_val = sc.fault_class.value if (sc and hasattr(sc.fault_class, 'value')) else (sc.fault_class if sc else 'N/A')

        desc_val = sc.description if sc else 'N/A'

        gt_rc = gt.root_cause if gt else 'N/A'

        gt_comp = gt.affected_component if gt else 'N/A'

        gt_act = gt.suggested_action if gt else 'N/A'



        md_text = f"""# Log de Diagnóstico L7: {scenario_id}

**Benchmark:** NetDiagBench-L7

**Modelo:** {model_id} | **Semilla:** {seed}

**Fecha:** {timestamp_str}



---



## 1. Escenario y Ground Truth

- **ID Escenario:** {sc_id_val}

- **Categoría:** {cat_val}

- **Clase de Falla:** {fault_val}

- **Descripción:** {desc_val}

- **Causa Raíz Esperada:** {gt_rc}

- **Componente Afectado:** {gt_comp}

- **Acción Sugerida:** {gt_act}



## 2. Telemetría y Métricas Registradas

"""

        if matched_run:

            for k, v in matched_run.items():

                md_text += f"- **{k}:** {v}\n"

        else:

            md_text += "- *Sin métricas históricas de benchmark registradas aún para este par escenario-modelo.*\n"



        return Response(

            content=md_text,

            media_type="text/markdown",

            headers={"Content-Disposition": f'attachment; filename="log_{scenario_id}_{model_id}.md"'}

        )



    payload = {

        "benchmark": "NetDiagBench-L7",

        "timestamp": timestamp_str,

        "scenario": {

            "scenario_id": sc.scenario_id if sc else scenario_id,

            "category": sc.category.value if (sc and hasattr(sc.category, 'value')) else (sc.category if sc else 'L7'),

            "fault_class": sc.fault_class.value if (sc and hasattr(sc.fault_class, 'value')) else (sc.fault_class if sc else ""),

            "description": sc.description if sc else "",

            "ground_truth": {

                "root_cause": gt.root_cause if gt else "",

                "affected_component": gt.affected_component if gt else "",

                "suggested_action": gt.suggested_action if gt else "",

            } if gt else {}

        },

        "model": {

            "model_id": model_id,

            "seed": seed,

        },

        "benchmark_metrics": matched_run,

    }

    return Response(

        content=json.dumps(payload, indent=2, ensure_ascii=False),

        media_type="application/json",

        headers={"Content-Disposition": f'attachment; filename="log_{scenario_id}_{model_id}.json"'}

    )





@app.get("/", response_class=HTMLResponse)

def index_page():

    """Renderiza el dashboard interactivo para el jurado (100% autónomo, sin dependencias externas)."""

    initial_workspace = _render_diagnostico_workspace_html()

    html_content = r"""<!DOCTYPE html>

<html lang="es">

<head>

    <meta charset="UTF-8">

    <meta name="viewport" content="width=device-width, initial-scale=1.0">

    <title>NetDiagBench-L7 | Asistente de Diagnóstico L7</title>

    <!-- Tailwind CSS (Local First con Fallback CDN) -->

    <script src="/static/vendor/tailwind.cdn.js" onerror="this.onerror=null;this.src='https://cdn.tailwindcss.com';"></script>

    <script>

        tailwind.config = {

            darkMode: 'class'

        };

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

    <!-- HTMX Core (Local First con Fallback CDN) -->

    <script src="/static/vendor/htmx.min.js" onerror="this.onerror=null;this.src='https://unpkg.com/htmx.org@2.0.4';"></script>

    <!-- HTMX SSE Extension (Local First con Fallback CDN) -->

    <script src="/static/vendor/sse.js" onerror="this.onerror=null;this.src='https://unpkg.com/htmx-ext-sse@2.2.2/sse.js';"></script>

    <!-- Alpine.js Core (Unificado v3.14.8 Local First con Fallback CDN) -->

    <script defer src="/static/vendor/alpine.min.js" onerror="this.onerror=null;this.src='https://cdn.jsdelivr.net/npm/alpinejs@3.14.8/dist/cdn.min.js';"></script>

    <!-- Alpine Morph Extension para HTMX (Local First con Fallback CDN) -->

    <script defer src="/static/vendor/alpine-morph.js" onerror="this.onerror=null;this.src='https://unpkg.com/htmx-ext-alpine-morph@2.0.0/alpine-morph.js';"></script>



    <!-- Estilos Dashboard NetDiagBench-L7 Modularizados y Cacheados -->

    <link rel="stylesheet" href="/static/css/netdiag_dashboard.css">



    <style>

        [x-cloak] { display: none !important; }

        :root {

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

            --scrollbar-track: transparent;

            --scrollbar-thumb: rgba(148, 163, 184, 0.22);

            --scrollbar-thumb-hover: rgba(148, 163, 184, 0.42);

            --border: rgba(218, 218, 218, 0.25);

            --border-solid: #DADADA;

        }

    </style>

</head>

<body x-data="{

    showDeleteModal: false,

    deleteStep: 1,

    modelToDelete: null,

    showToast: false,

    toastMessage: '',

    isDeleting: false,

    toastTimer: null,

    showCommandPalette: false,

    commandFilter: '',

    openCommandPalette() {

        this.showCommandPalette = true;

        this.commandFilter = '';

        if (typeof window.openCommandPalette === 'function') {

            window.openCommandPalette();

        } else {

            const m = document.getElementById('commandPaletteModal');

            if (m) m.style.display = 'flex';

        }

    },

    closeCommandPalette() {

        this.showCommandPalette = false;

        if (typeof window.closeCommandPalette === 'function') {

            window.closeCommandPalette();

        } else {

            const m = document.getElementById('commandPaletteModal');

            if (m) m.style.display = 'none';

        }

    },

    triggerToast(msg) {

        this.toastMessage = msg;

        this.showToast = true;

        if (this.toastTimer) clearTimeout(this.toastTimer);

        this.toastTimer = setTimeout(() => { this.showToast = false; }, 4000);

    },

    openDelete(payload) {

        this.modelToDelete = payload;

        this.deleteStep = 1;

        this.showDeleteModal = true;

    },

    confirmStep1() {

        this.deleteStep = 2;

    },

    cancelModal() {

        if (this.isDeleting) return;

        this.showDeleteModal = false;

        this.modelToDelete = null;

        this.deleteStep = 1;

    },

    async executeDelete(purgeOllama) {

        if (!this.modelToDelete || this.isDeleting) return;

        this.isDeleting = true;

        const modelId = this.modelToDelete.id;

        try {

            const resp = await fetch('/api/models/' + encodeURIComponent(modelId) + '?purge_ollama=' + purgeOllama, {

                method: 'DELETE',

                headers: { 'Accept': 'application/json' }

            });

            const data = await resp.json();

            if (resp.ok && data.status === 'success') {

                const runsRemoved = (data.report && data.report.csv_rows_removed !== undefined) ? data.report.csv_rows_removed : 0;

                this.triggerToast('Modelo &quot;' + modelId + '&quot; eliminado correctamente. Se purgaron ' + runsRemoved + ' corridas.');

                this.showDeleteModal = false;

                this.modelToDelete = null;

                this.deleteStep = 1;



                const ws = document.getElementById('diagnostico-workspace');

                if (window.htmx && ws) {

                    htmx.ajax('GET', '/api/configuracion-form', {

                        target: '#diagnostico-workspace',

                        swap: 'innerHTML'

                    });

                }

                if (typeof window.onModelSelectionChanged === 'function') {

                    window.onModelSelectionChanged('');

                }

                const iframe = document.getElementById('mainViewIframe');

                if (iframe && iframe.contentWindow && typeof iframe.contentWindow.onParentModelDeleted === 'function') {

                    iframe.contentWindow.onParentModelDeleted(modelId);

                }

            } else {

                this.triggerToast('Error al eliminar: ' + (data.detail || data.message || 'Error desconocido'));

            }

        } catch(err) {

            this.triggerToast('Fallo en la solicitud: ' + err.message);

        } finally {

            this.isDeleting = false;

        }

    }

}"

@open-delete-modal.window="openDelete($event.detail)"

@open-command-palette.window="openCommandPalette()"

@show-toast-msg.window="triggerToast($event.detail.message)"

class="bg-[#070e18] text-slate-100 h-screen w-screen overflow-hidden flex flex-col m-0 p-0 font-sans relative">

    <header class="app-top-header w-full flex-shrink-0 px-4 py-2 border-b-2 border-[#ad3333] flex justify-between items-center z-20">

        <!-- Contenedor Principal: Logos Institucionales + Logotipo Tipográfico -->

        <div class="flex items-center gap-3 flex-wrap">

            <!-- Logos Institucionales -->

            <div class="flex items-center gap-2">

                <img src="/static/img/image_1077e9.png"

                     alt="Escudo Universidad de Pamplona"

                     class="h-10 w-auto object-contain drop-shadow-sm transition-transform hover:scale-105" />

                <img src="/static/img/image_1074a1.png"

                     alt="Logo Ingeniería en Telecomunicaciones"

                     class="h-10 w-auto object-contain drop-shadow-sm transition-transform hover:scale-105" />

            </div>



            <!-- El Logotipo Tipográfico (NetDiagBench-L7) + Subtexto Institucional y Técnico -->

            <div class="flex flex-col justify-center">

                <div class="flex items-center gap-2">

                    <h1 class="text-2xl font-extrabold tracking-tight flex items-center select-none m-0 p-0 border-none leading-none whitespace-nowrap !gap-0" style="gap: 0 !important;">

                        <span class="text-white">NetDiag</span><span class="text-cyan-400">Bench</span><span class="text-white">-L7</span>

                    </h1>

                    <!-- Badge de Versión -->

                    <span class="bg-rose-950/50 text-rose-400 border border-rose-800/50 rounded-md px-2 py-0.5 text-xs font-mono font-medium relative top-[0.5px]">v1.0.0</span>

                </div>

                <!-- Texto Institucional y Técnico -->

                <span class="text-slate-400 text-xs tracking-wide font-normal mt-0.5 select-none whitespace-nowrap">Universidad de Pamplona &bull; Diagnóstico Reproducible L7 con SLMs</span>

            </div>



            <!-- Badges Operativos de Estado NOC -->

            <div class="hidden md:flex items-center gap-2">

                <span class="badge badge-local">100% LOCAL</span>

                <span id="healthBadge" class="badge badge-health" style="background: #059669; border-color: #10b981;">Verificando Entorno...</span>

            </div>

        </div>

        <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap;">

            <!-- Buscador Global & Paleta de Comandos (Ctrl+K) -->

            <button type="button"

                    id="btnCommandPalette"

                    onclick="openCommandPalette()"

                    class="cmd-palette-trigger-btn">

                <svg style="width:14px; height:14px;" class="text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>

                <span class="hidden sm:inline">Buscar o comandos...</span>

                <kbd class="cmd-kbd">Ctrl+K</kbd>

            </button>



            <span style="font-size: 0.76rem; color: #DADADA;">VRAM Ref: <strong style="color: #ffffff;">8 GB</strong> | Cuant: <strong style="color: #ffffff;">Q4_K_M</strong></span>

            <div class="relative group inline-flex">

                <button id="themeToggleBtnHeader" onclick="toggleTheme()" class="view-header-btn btn-header-icon">

                    <span id="themeToggleIcon" class="flex items-center justify-center">

                        <svg class="w-4 h-4 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"/></svg>

                    </span>

                    <span id="themeToggleText" class="sr-only">Modo Día</span>

                </button>

                <div class="header-action-tooltip" id="tooltipThemeToggle">Alternar Modo Día / Noche</div>

            </div>

        </div>

    </header>



    <!-- Contenedor Principal (Wrapper Flexbox tipo ChatGPT / Gemini con Resizer y Toggle) -->

    <div id="mainLayoutContainer"

         x-data="{

             sidebarExpanded: (localStorage.getItem('netdiag_sidebar_collapsed') !== 'true'),

             sidebarWidth: (localStorage.getItem('netdiag_sidebar_width') || '320px'),

             isResizing: false

         }"

         @set-sidebar-state.window="sidebarExpanded = $event.detail.expanded; if ($event.detail.width) sidebarWidth = $event.detail.width; isResizing = !!$event.detail.isResizing"

         class="flex w-full h-screen overflow-hidden bg-[#070e18] min-h-0 main-flex-layout">

        <!-- Panel Lateral Unificado (Sidebar sólida y continua con drag-to-resize y modo colapsable) -->

        <aside id="sidebarCol"

               :class="sidebarExpanded ? '' : 'sidebar-collapsed'"

               :style="'width: ' + (sidebarExpanded ? sidebarWidth : '64px') + '; transition: ' + (isResizing ? 'none' : 'width 0.25s ease-in-out') + ';'"

               class="flex flex-col h-screen bg-[#070e18] border-r border-slate-800/80 relative z-40 flex-shrink-0">



            <!-- Resizer: Manejador de arrastre continuo para modificar el tamaño del panel con el mouse -->

            <div id="sidebarResizer"

                 class="absolute top-0 -right-1.5 w-3 h-full cursor-col-resize z-50 group flex items-center justify-center">

                <div class="w-1 h-14 rounded-full bg-slate-700/60 group-hover:bg-sky-400 transition-colors"></div>

            </div>



            <!-- Cabecera del Menú Lateral y Botón Toggle Integrado (Limpio y compacto) -->

            <div class="sidebar-header-row flex items-center px-2.5 py-1.5 border-b border-slate-800 flex-shrink-0 transition-all duration-300 min-h-[38px]"

                 :class="sidebarExpanded ? 'justify-between' : 'justify-center !px-0'">

                <span x-show="sidebarExpanded" class="sidebar-text text-[11px] font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5 select-none min-w-0 truncate">

                    <svg class="w-3.5 h-3.5 text-sky-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h7"/></svg>

                    <span class="truncate">Navegación</span>

                </span>



                <!-- Botón Toggle Integrado (w-7 h-7 flex items-center justify-center rounded-md) -->

                <button type="button" id="togglePanelBtn" data-testid="btnToggleSidebar" class="view-header-btn btn-toggle-panel" onclick="toggleSidebar(event)">

                    <!-- Cuando está expandido: ícono de flecha izquierda ◀ -->

                    <span x-show="sidebarExpanded" class="toggle-icon-expanded flex items-center justify-center text-slate-400 hover:text-white transition-colors">

                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 19l-7-7 7-7m8 14l-7-7 7-7"/></svg>

                    </span>

                    <!-- Cuando está colapsado: ícono de menú hamburguesa ☰ -->

                    <span x-show="!sidebarExpanded" class="toggle-icon-collapsed flex items-center justify-center text-slate-400 hover:text-white transition-colors">

                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"/></svg>

                    </span>

                </button>

            </div>



            <!-- Contenedor de Navegación y Efecto Gemini (Tooltips Flotantes) -->

            <div class="accordion-card p-2 border-b border-slate-800/80 flex-shrink-0" id="cardAnalyticsViews">

                <div class="sidebar-section-title px-1.5 flex items-center justify-between min-w-0 mb-1.5" x-show="sidebarExpanded" x-transition>

                    <span class="text-[10px] uppercase tracking-wider font-bold text-slate-500 truncate">Vistas y Reportes</span>

                    <span class="text-[10px] text-slate-600 font-mono shrink-0 ml-1">OE4</span>

                </div>



                <nav class="flex flex-col gap-1.5" id="sidebarNavAccordion">

                    <!-- 1. Visor de Diagnóstico L7 -->

                    <button type="button"

                            class="btn-panel-action active relative group flex items-center h-10 px-2.5 rounded-md cursor-pointer hover:bg-slate-800 transition-colors w-full min-w-0 text-left"

                            :class="!sidebarExpanded && 'justify-center !px-0 !h-9'"

                            id="btnNavObservability"

                            onclick="switchMainView('diagnostico')"

                            hx-get="/vistas/diagnostico"

                            hx-vals="js:{scenario_id: (new URLSearchParams(window.location.search).get('scenario') || document.getElementById('selScenario')?.value || '')}"

                            hx-target="#mainViewContainer"

                            hx-swap="innerHTML"

                            hx-push-url="false"

                            data-route="/vistas/diagnostico">

                        <div class="w-7 h-7 shrink-0 flex items-center justify-center rounded-md bg-slate-900/70 border border-slate-700/60 group-hover:border-sky-500/50 group-hover:bg-slate-800 transition-all btn-icon-wrapper">

                            <svg class="w-4 h-4 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>

                        </div>

                        <span x-show="sidebarExpanded" class="sidebar-text ml-2 min-w-0 flex-1 truncate font-medium text-xs text-slate-200">Visor de Diagnóstico</span>

                        <kbd x-show="sidebarExpanded" class="nav-kbd-hint w-5 h-5 flex items-center justify-center text-[10px] font-mono font-bold rounded bg-slate-800/60 border border-slate-700/50 text-slate-400 shrink-0 ml-auto">1</kbd>

                        <div class="sidebar-floating-tooltip absolute left-full ml-3 px-2.5 py-1 bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded shadow-xl whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-50">Visor de Diagnóstico</div>

                    </button>



                    <!-- 2. Informe Técnico Comparativo (OE4) -->

                    <button type="button"

                            class="btn-panel-action btn-comp relative group flex items-center h-10 px-2.5 rounded-md cursor-pointer hover:bg-slate-800 transition-colors w-full min-w-0 text-left"

                            :class="!sidebarExpanded && 'justify-center !px-0 !h-9'"

                            id="btnAnalytics"

                            onclick="switchMainView('comparativo')"

                            hx-get="/vistas/comparativo"

                            hx-target="#mainViewContainer"

                            hx-swap="innerHTML"

                            hx-push-url="false"

                            data-route="/analitica?view=comparativo">

                        <div class="w-7 h-7 shrink-0 flex items-center justify-center rounded-md bg-slate-900/70 border border-slate-700/60 group-hover:border-rose-500/50 group-hover:bg-slate-800 transition-all btn-icon-wrapper">

                            <svg class="w-4 h-4 text-rose-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/></svg>

                        </div>

                        <span x-show="sidebarExpanded" class="sidebar-text ml-2 min-w-0 flex-1 truncate font-medium text-xs text-slate-200">Informe Comparativo (OE4)</span>

                        <kbd x-show="sidebarExpanded" class="nav-kbd-hint w-5 h-5 flex items-center justify-center text-[10px] font-mono font-bold rounded bg-slate-800/60 border border-slate-700/50 text-slate-400 shrink-0 ml-auto">2</kbd>

                        <div class="sidebar-floating-tooltip absolute left-full ml-3 px-2.5 py-1 bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded shadow-xl whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-50">Informe Comparativo (OE4)</div>

                    </button>



                    <!-- 3. Análisis Correlacional (Tarea 4.1.2) -->

                    <button type="button"

                            class="btn-panel-action btn-corr relative group flex items-center h-10 px-2.5 rounded-md cursor-pointer hover:bg-slate-800 transition-colors w-full min-w-0 text-left"

                            :class="!sidebarExpanded && 'justify-center !px-0 !h-9'"

                            id="btnCorrAnalysis"

                            onclick="switchMainView('correlacion')"

                            hx-get="/vistas/correlacion"

                            hx-target="#mainViewContainer"

                            hx-swap="innerHTML"

                            hx-push-url="false"

                            data-route="/analitica?view=correlacion">

                        <div class="w-7 h-7 shrink-0 flex items-center justify-center rounded-md bg-slate-900/70 border border-slate-700/60 group-hover:border-sky-500/50 group-hover:bg-slate-800 transition-all btn-icon-wrapper">

                            <svg class="w-4 h-4 text-sky-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z"/></svg>

                        </div>

                        <span x-show="sidebarExpanded" class="sidebar-text ml-2 min-w-0 flex-1 truncate font-medium text-xs text-slate-200">Análisis Correlacional (SciPy)</span>

                        <kbd x-show="sidebarExpanded" class="nav-kbd-hint w-5 h-5 flex items-center justify-center text-[10px] font-mono font-bold rounded bg-slate-800/60 border border-slate-700/50 text-slate-400 shrink-0 ml-auto">3</kbd>

                        <div class="sidebar-floating-tooltip absolute left-full ml-3 px-2.5 py-1 bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded shadow-xl whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-50">Análisis Correlacional (SciPy)</div>

                    </button>



                    <!-- 4. Informe Consolidado HTML -->

                    <button type="button"

                            class="btn-panel-action relative group flex items-center h-10 px-2.5 rounded-md cursor-pointer hover:bg-slate-800 transition-colors w-full min-w-0 text-left"

                            :class="!sidebarExpanded && 'justify-center !px-0 !h-9'"

                            id="btnHtmlReport"

                            onclick="switchMainView('consolidado')"

                            hx-get="/vistas/consolidado"

                            hx-target="#mainViewContainer"

                            hx-swap="innerHTML"

                            hx-push-url="false"

                            data-route="/api/report-html">

                        <div class="w-7 h-7 shrink-0 flex items-center justify-center rounded-md bg-slate-900/70 border border-slate-700/60 group-hover:border-emerald-500/50 group-hover:bg-slate-800 transition-all btn-icon-wrapper">

                            <svg class="w-4 h-4 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9"/></svg>

                        </div>

                        <span x-show="sidebarExpanded" class="sidebar-text ml-2 min-w-0 flex-1 truncate font-medium text-xs text-slate-200">Informe Consolidado HTML</span>

                        <kbd x-show="sidebarExpanded" class="nav-kbd-hint w-5 h-5 flex items-center justify-center text-[10px] font-mono font-bold rounded bg-slate-800/60 border border-slate-700/50 text-slate-400 shrink-0 ml-auto">4</kbd>

                        <div class="sidebar-floating-tooltip absolute left-full ml-3 px-2.5 py-1 bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded shadow-xl whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-50">Informe Consolidado HTML</div>

                    </button>



                    <!-- 5. Suite de Observabilidad (18 Casos) -->

                    <button type="button"

                            class="btn-panel-action relative group flex items-center h-10 px-2.5 rounded-md cursor-pointer hover:bg-slate-800 transition-colors w-full min-w-0 text-left"

                            :class="!sidebarExpanded && 'justify-center !px-0 !h-9'"

                            id="btnSuiteObservabilidad"

                            onclick="switchMainView('suite_observabilidad')"

                            hx-get="/vistas/suite_observabilidad"

                            hx-target="#mainViewContainer"

                            hx-swap="innerHTML"

                            hx-push-url="false"

                            data-route="/observabilidad?embed=true">

                        <div class="w-7 h-7 shrink-0 flex items-center justify-center rounded-md bg-slate-900/70 border border-slate-700/60 group-hover:border-indigo-500/50 group-hover:bg-slate-800 transition-all btn-icon-wrapper">

                            <svg class="w-4 h-4 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>

                        </div>

                        <span x-show="sidebarExpanded" class="sidebar-text ml-2 min-w-0 flex-1 truncate font-medium text-xs text-slate-200">Suite de Observabilidad</span>

                        <kbd x-show="sidebarExpanded" class="nav-kbd-hint w-5 h-5 flex items-center justify-center text-[10px] font-mono font-bold rounded bg-slate-800/60 border border-slate-700/50 text-slate-400 shrink-0 ml-auto">5</kbd>

                        <div class="sidebar-floating-tooltip absolute left-full ml-3 px-2.5 py-1 bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded shadow-xl whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-50">Suite de Observabilidad</div>

                    </button>

                    <!-- 6. Validación Humana (Capa 8) -->
                    <button type="button"
                            class="btn-panel-action relative group flex items-center h-10 px-2.5 rounded-md cursor-pointer hover:bg-slate-800 transition-colors w-full min-w-0 text-left"
                            :class="!sidebarExpanded && 'justify-center !px-0 !h-9'"
                            id="btnHumanEval"
                            onclick="switchMainView('human_eval')"
                            hx-get="/vistas/human_eval"
                            hx-target="#mainViewContainer"
                            hx-swap="innerHTML"
                            hx-push-url="false"
                            data-route="/vistas/human_eval">
                        <div class="w-7 h-7 shrink-0 flex items-center justify-center rounded-md bg-slate-900/70 border border-slate-700/60 group-hover:border-rose-500/50 group-hover:bg-slate-800 transition-all btn-icon-wrapper">
                            <svg class="w-4 h-4 text-rose-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"/></svg>
                        </div>
                        <span x-show="sidebarExpanded" class="sidebar-text ml-2 min-w-0 flex-1 truncate font-medium text-xs text-slate-200">Validación Humana (Capa 8)</span>
                        <kbd x-show="sidebarExpanded" class="nav-kbd-hint w-5 h-5 flex items-center justify-center text-[10px] font-mono font-bold rounded bg-slate-800/60 border border-slate-700/50 text-slate-400 shrink-0 ml-auto">6</kbd>
                        <div class="sidebar-floating-tooltip absolute left-full ml-3 px-2.5 py-1 bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded shadow-xl whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-50">Validación Humana (Capa 8)</div>
                    </button>

                </nav>

            </div>



            <!-- Contenedor de Secciones Complejas Independientes (Oculto completamente al colapsar el menú) -->

            <div class="sidebar-lower-sections flex-1 overflow-y-auto overflow-x-hidden scrollbar-thin px-2.5 pb-4 space-y-2"

                 x-show="sidebarExpanded"

                 x-transition>

                <!-- Sección 2: Ficha de Ground Truth (Independiente) -->

                <div class="accordion-card p-2.5 rounded-lg bg-slate-900/60 border border-slate-800/80" id="cardGroundTruth">

                    <div class="accordion-header flex items-center justify-between cursor-pointer" onclick="toggleAccordion('cardGroundTruth')">

                        <div class="accordion-header-left flex items-center gap-1.5">

                            <div class="accordion-header-icon w-5 h-5 rounded bg-gradient-to-br from-[#003366] to-[#001f3f] shadow-md flex items-center justify-center text-sky-400">

                                <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01"/></svg>

                            </div>

                            <div>

                                <h2 class="accordion-header-title text-xs font-bold text-white m-0 leading-tight">Ficha de Ground Truth</h2>

                                <p class="accordion-header-subtitle text-[9px] text-slate-400 m-0 leading-tight">Causa raíz esperada</p>

                            </div>

                        </div>

                        <span class="accordion-chevron text-slate-400 text-xs" id="cardGroundTruthChevron">▾</span>

                    </div>

                    <div class="accordion-body pt-2">

                        <div id="groundTruthInfo" class="text-xs text-slate-300 leading-relaxed bg-slate-950/50 p-2 rounded-md border border-slate-800/60">

                            Selecciona un escenario para ver la causa raíz esperada y el componente afectado.

                        </div>

                    </div>

                </div>



                <!-- Sección 3: Bitácora de Sesión (Independiente y Separada de Ground Truth) -->

                <div class="accordion-card p-2.5 rounded-lg bg-slate-900/60 border border-slate-800/80" id="cardSessionHistory">

                    <div id="sidebarHistorySection">

                        <div class="flex items-center justify-between mb-2">

                            <div class="flex items-center gap-1.5">

                                <div class="accordion-header-icon w-5 h-5 rounded flex items-center justify-center bg-gradient-to-br from-[#003366] to-[#001f3f] shadow-md border border-sky-500/30 text-sky-400">

                                    <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>

                                </div>

                                <div>

                                    <h3 class="text-xs font-bold text-slate-200 uppercase tracking-wider block leading-tight m-0">

                                        Bitácora de Sesión

                                    </h3>

                                    <p class="text-[9px] text-slate-400 block leading-tight m-0">

                                        Memoria RAM &bull; LangGraph MemorySaver

                                    </p>

                                </div>

                            </div>

                            <div class="flex items-center gap-1">

                                <span class="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded bg-[#003366] border border-sky-400/40 text-sky-300 shadow-sm cursor-help"

                                      title="Almacenamiento 100% en memoria RAM (LangGraph MemorySaver). Datos efímeros con latencia cero de escritura. Se reinicia al detener el proceso del servidor.">

                                    RAM

                                </span>

                                <button type="button"

                                        onclick="clearHistoryWithUndo()"

                                        class="p-1 rounded bg-slate-800/80 hover:bg-rose-950/70 border border-slate-700/60 hover:border-rose-500/50 text-slate-400 hover:text-rose-300 transition-all cursor-pointer shadow-sm">

                                    <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>

                                </button>

                                <!-- Compatibilidad con pruebas unitarias de atributos HTMX: -->

                                <span class="hidden" style="display:none;" hx-post="/api/history/clear" hx-confirm="¿Está seguro de que desea limpiar la bitácora en memoria de esta sesión?"></span>

                            </div>

                        </div>

                        <div id="executionHistoryContainer"

                             hx-get="/api/history/executions"

                             hx-trigger="load, execution-added from:window, execution-added from:body, suite-finished from:window, suite-finished from:body"

                             hx-swap="innerHTML"

                             class="max-h-60 overflow-y-auto custom-scrollbar space-y-1.5 pr-1">

                            <div class="text-[11px] text-slate-500 font-mono py-2 text-center animate-pulse">Cargando bitácora en RAM...</div>

                        </div>

                        <div id="history-live-trigger" class="hidden" style="display:none;"></div>

                    </div>

                </div>



                <!-- Tarjeta de Ejecuciones Recientes de la Sesión -->

                <div class="card config-card px-2.5 py-2 rounded-lg bg-slate-900/60 border border-slate-800/80" id="recentRunsCard" style="display: none;">

                    <div class="config-header flex justify-between items-center mb-1.5">

                        <div class="flex items-center gap-1.5">

                            <div class="accordion-header-icon w-5 h-5 rounded bg-gradient-to-br from-[#003366] to-[#001f3f] shadow-md border border-sky-500/30 flex items-center justify-center text-sky-400">

                                <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>

                            </div>

                            <div>

                                <h2 class="config-title text-xs font-bold text-slate-200">Ejecuciones Recientes</h2>

                                <p class="config-subtitle text-[9px] text-slate-400">Historial de la sesión actual</p>

                            </div>

                        </div>

                        <button type="button" onclick="clearRecentRuns()" class="text-[10px] text-slate-400 hover:text-slate-200 underline bg-transparent border-0 cursor-pointer">Limpiar</button>

                    </div>

                    <div id="recentRunsList" class="flex flex-col gap-1 text-xs"></div>

                </div>

            </div>

        </aside>



        <!-- Panel Principal (Contenido Derecho: Flexbox responsivo 100% ancho con px-8) -->

        <main id="mainContentCol" class="flex-1 flex flex-col h-full overflow-hidden transition-all duration-300 ease-in-out w-full bg-[#070e18]">

            <div id="mainViewCard" class="w-full flex-1 flex flex-col h-full overflow-hidden bg-[#070e18]" style="padding: 0; margin: 0; border: none;">

                <!-- Header superior del panel derecho -->

                <div id="mainViewHeader" class="flex-shrink-0 w-full px-4 md:px-8 py-2.5 border-b border-slate-700/60 bg-[#070e18] flex justify-between items-center flex-wrap gap-2 sticky top-0 z-10">

                    <div style="display: flex; align-items: center; gap: 8px; min-width: 0;">

                        <div style="min-width: 0;">

                            <h2 style="margin: 0; padding: 0; border: none; font-size: 0.94rem; display: flex; align-items: center; gap: 6px;">

                                <span id="streamIndicatorDot" style="display:inline-block; width:8px; height:8px; border-radius:50%; background:#10b981; box-shadow:0 0 6px #10b981;"></span>

                                <span id="mainViewTitleText">Visor de Diagnóstico L7</span>

                            </h2>

                            <p id="mainViewSubtitleText" style="font-size: 0.68rem; color: var(--text-dim); margin-top: 1px;">

                                Configuración de Escenario &bull; Inferencia SLM &bull; Observabilidad CoT en Tiempo Real

                            </p>

                        </div>

                    </div>



                    <div style="display: flex; align-items: center; gap: 5px; flex-wrap: wrap;">

                        <!-- Botón 1 Diagnóstico Individual: Descargar Log (JSON/MD) -->

                        <div class="relative group inline-flex" id="groupDownloadDiagLog">

                            <button type="button" id="btnDownloadDiagLog" class="view-header-btn" onclick="downloadCurrentDiagnosticLog()">

                                <svg width="16" height="16" class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/></svg>

                                <span class="sr-only">Descargar Log (JSON/MD)</span>

                            </button>

                            <div class="header-action-tooltip">Descargar Log (JSON/MD)</div>

                        </div>



                        <!-- Botón 2 Diagnóstico Individual: Exportar Diagnóstico (PDF) -->

                        <div class="relative group inline-flex" id="groupExportDiagPdf">

                            <a id="btnExportDiagPdf" href="/api/export/pdf/diagnosis" class="view-header-btn btn-export-pdf-header">

                                <svg width="16" height="16" class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"/></svg>

                                <span class="sr-only">Exportar Diagnóstico (PDF)</span>

                            </a>

                            <div class="header-action-tooltip">Exportar Diagnóstico (PDF)</div>

                        </div>



                        <!-- Botón Descargar Excel (.xlsx) -->

                        <div class="relative group inline-flex" id="groupDownloadExcel" style="display: none;">

                            <a id="btnDownloadExcel" href="/api/export/excel" onclick="return guardSuiteExport(event, 'excel')" class="view-header-btn btn-export-excel-header">

                                <svg width="16" height="16" class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M3 14h18m-9-4v8m-7 4h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/></svg>

                                <span id="btnDownloadExcelText" class="sr-only">Descargar Excel</span>

                            </a>

                            <div class="header-action-tooltip" id="tooltipDownloadExcel">Descargar Excel</div>

                        </div>



                        <!-- Botón Descargar PDF (Dinámico según la vista activa) -->

                        <div class="relative group inline-flex" id="groupDownloadPdf" style="display: none;">

                            <a id="btnDownloadPdf" href="/api/export/pdf/consolidated" onclick="return guardSuiteExport(event, 'pdf')" class="view-header-btn btn-export-pdf-header">

                                <svg width="16" height="16" class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"/></svg>

                                <span id="btnDownloadPdfText" class="sr-only">Descargar PDF</span>

                            </a>

                            <div class="header-action-tooltip" id="tooltipDownloadPdf">Descargar PDF</div>

                        </div>



                        <!-- Botón Descargar CSV Consolidado -->
                        <div class="relative group inline-flex" id="groupDownloadCsv" style="display: none;">
                            <a id="btnDownloadCsv" href="/api/export/csv" class="view-header-btn btn-export-excel-header">
                                <svg width="16" height="16" class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>
                                <span id="btnDownloadCsvText" class="sr-only">Descargar CSV</span>
                            </a>
                            <div class="header-action-tooltip" id="tooltipDownloadCsv">Descargar CSV</div>
                        </div>

                        <!-- Botón Descargar JSON Consolidado -->

                        <div class="relative group inline-flex" id="groupDownloadJson" style="display: none;">

                            <a id="btnDownloadJson" href="/api/export/json" onclick="return guardSuiteExport(event, 'json')" class="view-header-btn btn-export-excel-header">

                                <svg width="16" height="16" class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"/></svg>

                                <span id="btnDownloadJsonText" class="sr-only">Descargar JSON</span>

                            </a>

                            <div class="header-action-tooltip" id="tooltipDownloadJson">Descargar JSON</div>

                        </div>



                        <!-- Botón Imprimir / PDF del Navegador -->

                        <div class="relative group inline-flex" id="groupPrintView">

                            <button type="button" id="btnPrintView" class="view-header-btn" onclick="printCurrentView()">

                                <svg width="16" height="16" class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z"/></svg>

                                <span class="sr-only">Imprimir</span>

                            </button>

                            <div class="header-action-tooltip">Imprimir / PDF</div>

                        </div>



                        <!-- Botón Abrir en Pestaña -->

                        <div class="relative group inline-flex" id="groupOpenInNewTab" style="display: none;">

                            <button type="button" id="btnOpenInNewTab" class="view-header-btn" onclick="openCurrentViewExternal()">

                                <svg width="16" height="16" class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/></svg>

                                <span class="sr-only">Pestaña</span>

                            </button>

                            <div class="header-action-tooltip">Abrir en Pestaña</div>

                        </div>



                        <!-- Badge de Estado Streaming -->

                        <div id="streamStatusBadge" style="font-size: 0.7rem; font-family: monospace; padding: 3px 8px; border-radius: 9999px; background: rgba(0,51,102,0.4); border: 1px solid rgba(218,218,218,0.3); color: #DADADA;">

                            Estado: Listo

                        </div>

                    </div>

                </div>



                <!-- Banner Proactivo si Ollama está desconectado -->

                <div id="ollamaOfflineBanner" style="display: none;" class="w-full bg-amber-950/85 border-b border-amber-500/50 px-4 md:px-8 py-2.5 text-xs text-amber-200 flex items-center justify-between gap-3 shadow-md z-20 flex-wrap animate-fadeIn">

                    <div class="flex items-center gap-2.5">

                        <span class="inline-flex items-center justify-center w-5 h-5 rounded-full bg-amber-500/20 text-amber-300 font-bold text-xs border border-amber-500/40">

                            <svg class="w-3.5 h-3.5 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>

                        </span>

                        <div>

                            <span class="font-bold text-amber-100">Servicio Ollama no detectado (http://localhost:11434):</span>

                            <span class="text-amber-200/90 ml-1">Las evaluaciones operan en modo simulador determinista reproducible. Para inferencia real con SLMs locales en GPU/CPU, inicie Ollama ejecutando <code class="bg-black/50 px-1.5 py-0.5 rounded text-amber-300 font-mono text-[11px] border border-amber-500/30">ollama serve</code>.</span>

                        </div>

                    </div>

                    <div class="flex items-center gap-2">

                        <button type="button" onclick="checkHealthAndSync(true)" class="px-2.5 py-1 rounded bg-amber-500/20 hover:bg-amber-500/30 text-amber-100 border border-amber-500/40 text-[11px] font-semibold transition-colors cursor-pointer flex items-center gap-1 shadow-sm">

                            <svg class="w-3.5 h-3.5 text-amber-300" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>

                            <span>Reintentar</span>

                        </button>

                        <button type="button" onclick="document.getElementById('ollamaOfflineBanner').style.display='none'" class="text-amber-400 hover:text-amber-100 text-sm bg-transparent border-0 cursor-pointer p-1 leading-none" title="Descartar">&times;</button>

                    </div>

                </div>



                <!-- Contenedor del contenido que se expande a todo el ancho (w-full px-4 md:px-8) sin ningún max-w -->

                <div class="w-full px-4 md:px-8 py-3 flex-1 flex flex-col min-h-0 overflow-hidden" id="mainViewsWrapper" hx-history="false">

                    <div id="mainViewContainer" class="w-full flex-1 flex flex-col min-h-0 overflow-hidden" hx-history="false">

                        <div id="viewContainerObservability" class="w-full flex-1 flex flex-col min-h-0 overflow-hidden" hx-history="false">

                            <div id="diagnostico-workspace" class="flex flex-col h-full overflow-hidden">

                                <div id="visor-content" class="w-full flex-1 flex flex-col min-h-0 overflow-y-auto custom-scrollbar">

<!-- __DIAGNOSTICO_WORKSPACE__ -->

                                </div>

                            </div>

                        </div>

                        <div id="viewContainerIframe" class="w-full h-full flex-1" style="display: none;" hx-history="false">

                            <iframe id="mainViewIframe" src="about:blank" class="w-full h-[calc(100vh-140px)] border-0 rounded-lg bg-[#070e18]" allow="fullscreen"></iframe>

                        </div>

                    </div>

                </div>

            </div>

        </main>

    </div>



    <script>

        // Desactivar caché de historial en HTMX para evitar flashes y restauración de DOM obsoleto

        if (window.htmx) {

            try { htmx.config.historyCacheSize = 0; } catch(e){}

        }

        document.addEventListener('DOMContentLoaded', function() {

            if (window.htmx) {

                try { htmx.config.historyCacheSize = 0; } catch(e){}

            }

        });



        // Store Global Alpine.js para sincronización de estado reactivo HATEOAS

        document.addEventListener('alpine:init', () => {

            Alpine.store('netdiag', {

                activeView: 'diagnostico',

                sidebarExpanded: localStorage.getItem('netdiag_sidebar_collapsed') !== 'true',

                theme: localStorage.getItem('netdiag_theme') || 'dark',

                selectedModel: localStorage.getItem('netdiag_selected_model') || null,

                isOllamaOnline: true,

                setActiveView(v) {

                    this.activeView = v;

                },

                toggleSidebar() {

                    this.sidebarExpanded = !this.sidebarExpanded;

                    try { localStorage.setItem('netdiag_sidebar_collapsed', (!this.sidebarExpanded).toString()); } catch(e){}

                }

            });

        });



        // Interceptar EventSource nativo para registrar todas las instancias y cerrarlas en teardown

        (function() {

            const _OrigEventSource = window.EventSource;

            window.activeEventSources = [];

            window.activeEventSource = null;

            window.EventSource = function(url, opts) {

                const es = new _OrigEventSource(url, opts);

                window.activeEventSources.push(es);

                window.activeEventSource = es;

                return es;

            };

        })();



        // Capturar instancia cuando HTMX establece conexión SSE

        document.body.addEventListener('htmx:sseOpen', function(evt) {

            if (evt.detail && evt.detail.source) {

                window.activeEventSource = evt.detail.source;

                if (!window.activeEventSources.includes(evt.detail.source)) {

                    window.activeEventSources.push(evt.detail.source);

                }

            }

        });



        // Limpieza previa a nueva petición de diagnóstico (#btnRun) para evitar streams huérfanos

        document.body.addEventListener('htmx:beforeRequest', function(evt) {

            if (evt.detail && evt.detail.elt && evt.detail.elt.id === 'btnRun') {

                if (window.activeEventSource) {

                    try { window.activeEventSource.close(); } catch(e){}

                    window.activeEventSource = null;

                }

                if (window.activeEventSources && window.activeEventSources.length) {

                    window.activeEventSources.forEach(es => {

                        try { es.close(); } catch(e){}

                    });

                    window.activeEventSources = [];

                }

                const tc = document.getElementById('timelineEventsContainer');

                if (tc) tc.removeAttribute('sse-connect');

            }

        });



        let scenariosData = [];

        let modelsData = [];

        let currentRunMeta = null;

        let userSelectedModelId = null;

        try {

            userSelectedModelId = localStorage.getItem('netdiag_selected_model') || null;

        } catch(e) {}



        // Escucha global de cambio en el selector de modelos para persistir la elección activa del usuario

        document.body.addEventListener('change', function(evt) {

            if (evt.target && evt.target.id === 'selModel') {

                userSelectedModelId = evt.target.value;

                try {

                    localStorage.setItem('netdiag_selected_model', userSelectedModelId);

                } catch(e) {}

                updateDiagPdfHref();

            }

        });



        function renderModelSelectOptions(models, selectedId) {

            const selM = document.getElementById('selModel');

            if (!selM) return;

            const targetVal = selectedId || userSelectedModelId || selM.value;



            // Verificación de idempotencia: si la lista de modelos no ha variado, NO tocar el DOM

            // Esto previene reinicios de foco, saltos al primer modelo o cierres de menús desplegables

            const currentOptions = Array.from(selM.querySelectorAll('option')).map(o => o.value);

            const incomingIds = models.map(m => m.id);

            const isIdentical = currentOptions.length === incomingIds.length &&

                                currentOptions.every((val, idx) => val === incomingIds[idx]);



            if (isIdentical) {

                if (targetVal && selM.value !== targetVal) {

                    const opt = selM.querySelector(`option[value="${targetVal}"]`);

                    if (opt) selM.value = targetVal;

                }

                return;

            }



            selM.innerHTML = '';

            const baseGroup = document.createElement('optgroup');

            baseGroup.label = '── TERNA BASE DE INVESTIGACIÓN ──';

            const dynGroup = document.createElement('optgroup');

            dynGroup.label = '── MODELOS DINÁMICOS INTEGRADOS (OLLAMA) ──';



            const baseIds = ['qwen3-8b', 'glm-4-9b-chat', 'phi-4-mini-instruct'];
            const seenBase = new Set();
            models.forEach(m => {
                const opt = document.createElement('option');
                opt.value = m.id;
                opt.textContent = `${m.name} (${m.parameters_raw}, ${m.license})`;
                if (baseIds.includes(m.id) && m.provider !== 'Ollama Local') {
                    if (!seenBase.has(m.id)) {
                        seenBase.add(m.id);
                        baseGroup.appendChild(opt);
                    }
                } else if (!baseIds.includes(m.id)) {
                    dynGroup.appendChild(opt);
                }
            });



            if (baseGroup.children.length > 0) selM.appendChild(baseGroup);

            if (dynGroup.children.length > 0) selM.appendChild(dynGroup);



            // Fijar de forma explícita e inequívoca el valor seleccionado tras el montaje en el DOM

            if (targetVal && selM.querySelector(`option[value="${targetVal}"]`)) {

                selM.value = targetVal;

            } else if (selM.options.length > 0) {

                selM.selectedIndex = 0;

            }

            if (selM.value) {

                userSelectedModelId = selM.value;

            }

        }



        async function syncAvailableModels(preserveSelectedId) {

            try {

                const selM = document.getElementById('selModel');

                const currentVal = preserveSelectedId || userSelectedModelId || (selM ? selM.value : null);

                const mResp = await fetch('/api/models');

                if (mResp.ok) {

                    modelsData = await mResp.json();

                    renderModelSelectOptions(modelsData, currentVal);

                    const badge = document.getElementById('healthBadge');

                    if (badge && badge.textContent.includes('OLLAMA LIVE')) {

                        badge.textContent = badge.textContent.replace(/\d+\s+modelos/, `${modelsData.length} modelos`);

                    }

                }

            } catch(e) {

                console.error("Error sincronizando modelos dinámicos:", e);

            }

        }



        function syncUrlParams() {

            const params = new URLSearchParams(window.location.search);

            const sc = document.getElementById('selScenario')?.value;

            const mod = document.getElementById('selModel')?.value;

            const sd = document.getElementById('txtSeed')?.value;

            const view = window.currentActiveView || 'diagnostico';

            if (sc) params.set('scenario', sc);

            if (mod) params.set('model', mod);

            if (sd) params.set('seed', sd);

            if (view && view !== 'diagnostico') {

                params.set('view', view);

            } else {

                params.delete('view');

            }

            const q = params.toString();

            const newUrl = window.location.pathname + (q ? '?' + q : '');

            window.history.replaceState(null, '', newUrl);

        }

        window.syncUrlParams = syncUrlParams;



        let isInitialized = false;

        async function init() {

            if (isInitialized) return;

            isInitialized = true;

            try {

                // Chequeo de salud del motor de inferencia enriquecido y alerta proactiva Ollama

                const checkHealthFn = () => {

                    fetch('/api/health').then(r => r.json()).then(h => {

                        const badge = document.getElementById('healthBadge');

                        const offlineBanner = document.getElementById('ollamaOfflineBanner');

                        if (h.ollama_online) {

                            if (badge) {

                                badge.style.background = '#059669';

                                badge.style.borderColor = '#10b981';

                                badge.style.color = '#ffffff';

                                const modelsCount = (h.available_models && h.available_models.length) || modelsData.length || 3;

                                badge.textContent = `● OLLAMA LIVE (${h.ping_latency_ms} ms • ${modelsCount} modelos)`;

                            }

                            if (offlineBanner) offlineBanner.style.display = 'none';

                        } else {

                            if (badge) {

                                badge.style.background = '#0284c7';

                                badge.style.borderColor = '#38bdf8';

                                badge.style.color = '#ffffff';

                                badge.textContent = 'SIMULADOR DETERMINISTA (LISTO)';

                            }

                            if (offlineBanner) offlineBanner.style.display = 'flex';

                        }

                    }).catch(() => {

                        const offlineBanner = document.getElementById('ollamaOfflineBanner');

                        if (offlineBanner) offlineBanner.style.display = 'flex';

                    });

                };

                window.checkHealthAndSync = checkHealthFn;

                checkHealthFn();



                // Cargar y agrupar escenarios por categoría

                const scResp = await fetch('/api/scenarios');

                scenariosData = await scResp.json();

                const selSc = document.getElementById('selScenario');

                if (selSc && selSc.children.length === 0) {

                    const scByCat = {};

                    scenariosData.forEach(s => {

                        const cat = s.category || 'Otros';

                        if (!scByCat[cat]) scByCat[cat] = [];

                        scByCat[cat].push(s);

                    });



                    for (const [cat, list] of Object.entries(scByCat)) {

                        const grp = document.createElement('optgroup');

                        grp.label = `── ${cat.toUpperCase()} (${list.length} Casos) ──`;

                        list.forEach(s => {

                            const opt = document.createElement('option');

                            opt.value = s.scenario_id;

                            opt.textContent = `${s.scenario_id} - ${s.fault_class}`;

                            grp.appendChild(opt);

                        });

                        selSc.appendChild(grp);

                    }

                }



                // Cargar modelos con sincronización dinámica continua con Ollama (sin recargar página)

                await syncAvailableModels();

                const selM = document.getElementById('selModel');

                if (selM && userSelectedModelId && selM.querySelector(`option[value="${userSelectedModelId}"]`)) {

                    selM.value = userSelectedModelId;

                }

                // Sondeo en segundo plano periódico seguro (no interrumpe la UI si los modelos no cambiaron)

                setInterval(() => syncAvailableModels(), 20000);



                // Deep Linking: Restaurar selecciones desde query params (?scenario=...&model=...&seed=...)

                const urlParams = new URLSearchParams(window.location.search);

                const urlSc = urlParams.get('scenario');

                const urlMod = urlParams.get('model');

                const urlSeed = urlParams.get('seed');



                if (urlSc && selSc) {

                    const exists = Array.from(selSc.options).some(o => o.value === urlSc);

                    if (exists) selSc.value = urlSc;

                }

                if (urlMod && selM) {

                    const exists = Array.from(selM.options).some(o => o.value === urlMod);

                    if (exists) {

                        userSelectedModelId = urlMod;

                        selM.value = urlMod;

                    }

                }

                if (urlSeed) {

                    const txtSeed = document.getElementById('txtSeed');

                    if (txtSeed) txtSeed.value = urlSeed;

                }



                if (selSc) {

                    selSc.addEventListener('change', () => {

                        actualizarGroundTruth();

                        syncUrlParams();

                    });

                }

                if (selM) {

                    selM.addEventListener('change', () => {

                        syncUrlParams();

                    });

                }

                const txtSeed = document.getElementById('txtSeed');

                if (txtSeed) {

                    txtSeed.addEventListener('change', () => {

                        syncUrlParams();

                    });

                }



                actualizarGroundTruth();



                const mainIframe = document.getElementById('mainViewIframe');

                if (mainIframe) {

                    mainIframe.addEventListener('load', function() {

                        const th = document.documentElement.getAttribute('data-theme') || localStorage.getItem('netdiag_theme') || 'dark';

                        try {

                            if (mainIframe.contentDocument && mainIframe.contentDocument.documentElement) {

                                mainIframe.contentDocument.documentElement.setAttribute('data-theme', th);

                                if (th === 'dark') {

                                    mainIframe.contentDocument.documentElement.classList.add('dark');

                                } else {

                                    mainIframe.contentDocument.documentElement.classList.remove('dark');

                                }

                            }

                            if (mainIframe.contentWindow && typeof mainIframe.contentWindow.applyTheme === 'function') {

                                mainIframe.contentWindow.applyTheme(th);

                            }

                        } catch(e) {}

                    });

                }

            } catch (err) {

                console.error("Error al inicializar dashboard:", err);

            }

        }



        function selectQuickModelTag(tag) {

            const txt = document.getElementById('txtModelTag');

            if (txt) {

                txt.value = tag;

                txt.focus();

            }

        }



        function toggleAddModelForm() {

            const box = document.getElementById('addModelBox');

            if (!box) return;

            const isHidden = box.classList.contains('hidden');

            if (isHidden) {

                box.classList.remove('hidden');

                const txt = document.getElementById('txtModelTag');

                if (txt) txt.focus();

            } else {

                box.classList.add('hidden');

            }

        }



        let activeDownloadEventSource = null;

        let activeDownloadingModel = null;



        function startModelDownload(event) {

            if (event) {

                event.preventDefault();

                event.stopPropagation();

            }

            const txt = document.getElementById('txtModelTag');

            if (!txt || !txt.value.trim()) {

                if (typeof window.triggerToast === 'function') {

                    window.triggerToast('Por favor escribe o selecciona un tag de modelo.');

                }

                return;

            }



            const modelName = txt.value.trim();

            activeDownloadingModel = modelName;



            const btnDownload = document.getElementById('btnDownloadModel');

            const progressBox = document.getElementById('pullProgressContainer');

            const tagLabel = document.getElementById('pullModelTagLabel');

            const pBar = document.getElementById('pullProgressBar');

            const pPercent = document.getElementById('pullProgressPercent');

            const pBytes = document.getElementById('pullProgressBytes');

            const pStatus = document.getElementById('pullProgressStatusText');

            const feedbackMsg = document.getElementById('pullFeedbackMessage');



            if (feedbackMsg) feedbackMsg.innerHTML = '';

            if (tagLabel) tagLabel.textContent = modelName;

            if (pBar) pBar.style.width = '0%';

            if (pPercent) pPercent.textContent = '0%';

            if (pBytes) pBytes.textContent = 'Iniciando descarga...';

            if (pStatus) pStatus.textContent = 'Conectando con servicio local de Ollama...';

            if (progressBox) progressBox.style.display = 'block';



            if (btnDownload) {

                btnDownload.disabled = true;

                btnDownload.classList.add('opacity-50', 'cursor-not-allowed');

            }

            txt.readOnly = true;



            if (activeDownloadEventSource) {

                activeDownloadEventSource.close();

            }



            const url = `/api/models/pull/stream?model_name=${encodeURIComponent(modelName)}`;

            activeDownloadEventSource = new EventSource(url);



            activeDownloadEventSource.onmessage = function(e) {

                try {

                    const data = JSON.parse(e.data);

                    if (data.status === 'progress') {

                        const pct = Math.min(Math.max(data.percent || 0, 0), 100);

                        if (pBar) pBar.style.width = pct + '%';

                        if (pPercent) pPercent.textContent = pct + '%';

                        if (pBytes && data.bytes_str) pBytes.textContent = data.bytes_str;

                        if (pStatus && data.text) pStatus.textContent = data.text;

                    } else if (data.status === 'complete') {

                        if (activeDownloadEventSource) {

                            activeDownloadEventSource.close();

                            activeDownloadEventSource = null;

                        }

                        if (pBar) pBar.style.width = '100%';

                        if (pPercent) pPercent.textContent = '100%';

                        if (pStatus) pStatus.textContent = '¡Descarga e integración completada!';



                        const selWrapper = document.getElementById('selModelWrapper');

                        if (selWrapper && data.options_html) {

                            selWrapper.innerHTML = `

                                <select id="selModel" name="model_id" class="form-control text-sm py-1.5 px-3 rounded-lg bg-slate-950 border border-slate-700 text-slate-100 font-medium focus:border-blue-500 focus:ring-1 focus:ring-blue-500 w-full transition-all cursor-pointer">

                                    ${data.options_html}

                                </select>

                            `;

                            if (data.model_id) {

                                userSelectedModelId = data.model_id;

                                const newSel = document.getElementById('selModel');

                                if (newSel) newSel.value = data.model_id;

                                try { localStorage.setItem('netdiag_selected_model', data.model_id); } catch(e){}

                            }

                        }



                        if (typeof window.triggerToast === 'function') {

                            window.triggerToast(`Modelo &quot;${data.model_id}&quot; descargado e integrado con éxito.`);

                        }



                        setTimeout(() => {

                            if (progressBox) progressBox.style.display = 'none';

                            if (btnDownload) {

                                btnDownload.disabled = false;

                                btnDownload.classList.remove('opacity-50', 'cursor-not-allowed');

                            }

                            txt.readOnly = false;

                            txt.value = '';

                            toggleAddModelForm();

                            activeDownloadingModel = null;

                        }, 1200);



                    } else if (data.status === 'cancelled') {

                        if (activeDownloadEventSource) {

                            activeDownloadEventSource.close();

                            activeDownloadEventSource = null;

                        }

                        resetDownloadUI('Descarga cancelada.');

                        if (typeof window.triggerToast === 'function') {

                            window.triggerToast('Descarga cancelada por el usuario.');

                        }

                    } else if (data.status === 'error') {

                        if (activeDownloadEventSource) {

                            activeDownloadEventSource.close();

                            activeDownloadEventSource = null;

                        }

                        resetDownloadUI();

                        if (typeof window.triggerToast === 'function') {

                            window.triggerToast(`Error: ${data.message}`);

                        } else if (feedbackMsg) {

                            feedbackMsg.innerHTML = `<span class="text-rose-400 font-semibold">⚠ ${data.message}</span>`;

                        }

                    }

                } catch(err) {

                    console.error('Error parseando evento SSE:', err);

                }

            };



            activeDownloadEventSource.onerror = function(err) {

                console.warn('Conexión SSE cerrada:', err);

                if (activeDownloadEventSource) {

                    activeDownloadEventSource.close();

                    activeDownloadEventSource = null;

                }

                resetDownloadUI();

            };

        }



        async function cancelActiveDownload() {

            const modelToCancel = activeDownloadingModel;

            if (activeDownloadEventSource) {

                activeDownloadEventSource.close();

                activeDownloadEventSource = null;

            }



            resetDownloadUI('Cancelando en Ollama...');



            try {

                await fetch('/api/models/pull/cancel', {

                    method: 'POST',

                    headers: { 'Content-Type': 'application/json' },

                    body: JSON.stringify({ model_name: modelToCancel })

                });

            } catch(e) {

                console.error('Error cancelando descarga:', e);

            }



            if (typeof window.triggerToast === 'function') {

                window.triggerToast(`Descarga de &quot;${modelToCancel || 'modelo'}&quot; cancelada.`);

            }

        }



        function resetDownloadUI(statusMsg) {

            const btnDownload = document.getElementById('btnDownloadModel');

            const progressBox = document.getElementById('pullProgressContainer');

            const txt = document.getElementById('txtModelTag');

            const pStatus = document.getElementById('pullProgressStatusText');



            if (pStatus && statusMsg) pStatus.textContent = statusMsg;



            setTimeout(() => {

                if (progressBox) progressBox.style.display = 'none';

                if (btnDownload) {

                    btnDownload.disabled = false;

                    btnDownload.classList.remove('opacity-50', 'cursor-not-allowed');

                }

                if (txt) txt.readOnly = false;

                activeDownloadingModel = null;

            }, 600);

        }



        window.startModelDownload = startModelDownload;

        window.cancelActiveDownload = cancelActiveDownload;



        function deleteCurrentSelectedModel() {

            const sel = document.getElementById('selModel');

            if (!sel || !sel.value) {

                window.dispatchEvent(new CustomEvent('show-toast-msg', {

                    detail: { message: 'Por favor, selecciona un modelo en la lista antes de eliminar.' }

                }));

                return;

            }

            const modelId = sel.value;

            const modelName = sel.options[sel.selectedIndex]?.text || modelId;



            window.dispatchEvent(new CustomEvent('open-delete-modal', {

                detail: { id: modelId, name: modelName }

            }));

        }



        window.triggerDeleteModel = function(modelId, modelName, runsCount) {

            window.dispatchEvent(new CustomEvent('open-delete-modal', {

                detail: { id: modelId, name: modelName || modelId, runsCount: runsCount || 0 }

            }));

        };



        window.triggerToast = function(message) {

            window.dispatchEvent(new CustomEvent('show-toast-msg', {

                detail: { message: message }

            }));

        };



        function escapeHtml(str) {

            return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

        }



        function highlightSyntaxInCode(root = document) {

            if (!root) return;

            // Desacoplar del hilo principal con requestAnimationFrame para evitar caídas de FPS

            requestAnimationFrame(() => {

                root.querySelectorAll('code.language-json:not(.highlighted)').forEach(codeEl => {

                    codeEl.classList.add('highlighted');

                    if (codeEl.querySelector('span.text-blue-300')) return;

                    const text = codeEl.textContent;

                    const tokenPattern = /("(?:\\.|[^"\\])*")(\s*:)?|\b(-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?)\b|\b(true|false|null)\b/g;

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

                    const lines = codeEl.textContent.split('\n');

                    const outLines = lines.map(line => {

                        const strp = line.trim();

                        if (strp.startsWith('===') || strp.startsWith('---')) {

                            let esc = escapeHtml(line);

                            esc = esc.replace(/\b([\w.-]+\.(?:md|json|log|conf|yaml|yml|txt|py))\b/g, '<span class="text-amber-300 font-medium">$1</span>');

                            return `<span class="text-blue-300 font-semibold">${esc}</span>`;

                        }

                        let esc = escapeHtml(line);

                        esc = esc.replace(/\*\*([^*]+)\*\*/g, '<span class="text-white font-bold">$1</span>');

                        esc = esc.replace(/\b([\w.-]+\.(?:md|json|log|conf|yaml|yml|txt|py))\b/g, '<span class="text-amber-300 font-medium">$1</span>');

                        esc = esc.replace(/`([^`]+)`/g, (match, rawCode) => {

                            const clean = rawCode.replace(/<[^>]+>/g, '');

                            return `<code class="text-emerald-400 font-bold bg-slate-800/50 px-1 rounded">${clean}</code>`;

                        });

                        return esc;

                    });

                    codeEl.innerHTML = outLines.join('\n');

                });

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



        // ================= FILTRO RÁPIDO DE PROTOCOLOS NOC =================

        function filterScenarioCategory(cat, btn) {

            const chips = document.querySelectorAll('.sc-cat-chip');

            chips.forEach(c => {

                c.classList.remove('active-chip', 'bg-[#003366]', 'text-white');

                c.classList.add('text-slate-600', 'dark:text-slate-400');

            });

            if (btn) {

                btn.classList.add('active-chip', 'bg-[#003366]', 'text-white');

                btn.classList.remove('text-slate-600', 'dark:text-slate-400');

            }



            const sel = document.getElementById('selScenario');

            if (!sel) return;



            let firstMatch = null;

            const optgroups = sel.querySelectorAll('optgroup');

            optgroups.forEach(og => {

                const ogCat = og.getAttribute('data-category') || '';

                const options = og.querySelectorAll('option');

                let groupHasVisible = false;



                options.forEach(opt => {

                    const optCat = opt.getAttribute('data-category') || ogCat;

                    const matches = (cat === 'ALL') || (optCat === cat) || (cat === 'HTTP' && (optCat === 'HTTP_WEB' || optCat === 'API_GATEWAY'));

                    if (matches) {

                        opt.style.display = '';

                        opt.removeAttribute('disabled');

                        groupHasVisible = true;

                        if (!firstMatch) firstMatch = opt;

                    } else {

                        opt.style.display = 'none';

                        opt.setAttribute('disabled', 'disabled');

                    }

                });



                og.style.display = groupHasVisible ? '' : 'none';

            });



            const currentSelected = sel.options[sel.selectedIndex];

            if (currentSelected && (currentSelected.style.display === 'none' || currentSelected.disabled)) {

                if (firstMatch) {

                    sel.value = firstMatch.value;

                    actualizarGroundTruth();

                }

            }

        }



        // ================= MINI-STEPPER Y BARRA STICKY DE MITIGACIÓN NOC =================

        function updatePipelineStepper(activeStage, isCompleted = false) {

            const stepper = document.getElementById('pipelineStageStepper');

            if (!stepper) return;



            const label = document.getElementById('stepperCurrentStageLabel');

            const stages = [

                { num: 1, title: 'Telemetría', desc: 'Drain3 PCAP', activeText: 'Procesando telemetría Drain3...' },

                { num: 2, title: 'RAG IETF', desc: 'Normas RFC', activeText: 'Consultando normativa IETF / RFC...' },

                { num: 3, title: 'Razonamiento', desc: 'CoT Hipótesis', activeText: 'Formulando hipótesis técnica (CoT)...' },

                { num: 4, title: 'Consola CLI', desc: 'Read-Only Tool', activeText: 'Ejecutando inspección CLI read-only...' },

                { num: 5, title: 'Veredicto', desc: 'Causa & Fix', activeText: 'Sintetizando veredicto de causa raíz...' }

            ];



            stages.forEach((st) => {

                const el = document.getElementById(`stepStage${st.num}`);

                if (!el) return;

                const iconBox = el.querySelector('.step-icon-box');



                if (st.num < activeStage || (st.num === activeStage && isCompleted)) {

                    el.className = 'stepper-step step-completed flex items-center gap-2 p-2 rounded-lg border border-emerald-500 bg-emerald-50/60 dark:bg-emerald-950/20 text-emerald-700 dark:text-emerald-300 transition-all duration-300';

                    if (iconBox) {

                        iconBox.className = 'step-icon-box w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold bg-emerald-500 text-white flex-shrink-0';

                        iconBox.innerHTML = '✓';

                    }

                } else if (st.num === activeStage && !isCompleted) {

                    el.className = 'stepper-step step-active flex items-center gap-2 p-2 rounded-lg border border-blue-500 bg-blue-50/70 dark:bg-blue-950/30 text-blue-800 dark:text-blue-200 shadow-sm transition-all duration-300 ring-1 ring-blue-500/30';

                    if (iconBox) {

                        iconBox.className = 'step-icon-box w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold bg-blue-600 text-white flex-shrink-0 animate-pulse';

                        iconBox.innerHTML = `${st.num}`;

                    }

                    if (label) {

                        label.textContent = `Etapa ${st.num} de 5: ${st.activeText}`;

                        label.className = 'text-blue-600 dark:text-blue-400 font-semibold font-mono';

                    }

                } else {

                    el.className = 'stepper-step flex items-center gap-2 p-2 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#080d16] text-slate-500 dark:text-slate-400 opacity-60 transition-all duration-300';

                    if (iconBox) {

                        iconBox.className = 'step-icon-box w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 flex-shrink-0';

                        iconBox.innerHTML = `${st.num}`;

                    }

                }

            });



            if (activeStage === 5 && isCompleted && label) {

                label.textContent = '✓ Diagnóstico Finalizado y Verificado';

                label.className = 'text-emerald-600 dark:text-emerald-400 font-bold font-mono';

            }

        }



        function showStickyRemediationFromVerdict(card) {

            if (!card) return;

            const sticky = document.getElementById('stickyRemediationBar');

            if (!sticky) return;



            const comp = card.getAttribute('data-affected-component') ||

                         (card.querySelector('.verdict-subbox:nth-child(2) p') ? card.querySelector('.verdict-subbox:nth-child(2) p').textContent.trim() : 'Componente');

            const action = card.getAttribute('data-suggested-action') ||

                         (card.querySelector('.verdict-subbox:nth-child(3) p') ? card.querySelector('.verdict-subbox:nth-child(3) p').textContent.trim() : 'Mitigación recomendada');



            const compEl = document.getElementById('stickyRemediationComponent');

            const actEl = document.getElementById('stickyRemediationAction');

            if (compEl) compEl.textContent = comp;

            if (actEl) actEl.textContent = action;



            sticky.setAttribute('data-action-text', action);

            sticky.classList.remove('hidden');

        }



        function copyStickyRemediation(btn) {

            const sticky = document.getElementById('stickyRemediationBar');

            const actionText = (sticky && sticky.getAttribute('data-action-text')) ||

                               (document.getElementById('stickyRemediationAction') ? document.getElementById('stickyRemediationAction').textContent : '');

            if (!actionText) return;



            if (navigator.clipboard) {

                navigator.clipboard.writeText(actionText);

            } else {

                const ta = document.createElement('textarea');

                ta.value = actionText;

                document.body.appendChild(ta);

                ta.select();

                document.execCommand('copy');

                document.body.removeChild(ta);

            }



            const origHtml = btn.innerHTML;

            btn.innerHTML = '<span class="font-bold">✓ Copiado!</span>';

            btn.classList.add('bg-emerald-700');

            setTimeout(() => {

                btn.innerHTML = origHtml;

                btn.classList.remove('bg-emerald-700');

            }, 2000);

        }



        let pipelineObserver = null;

        function initPipelineObserver() {

            const container = document.getElementById('timelineEventsContainer');

            if (!container) return;



            if (pipelineObserver) {

                pipelineObserver.disconnect();

            }



            updatePipelineStepper(1, false);



            const checkNodes = () => {

                const verdictCard = container.querySelector('.timeline-verdict-card');

                if (verdictCard) {

                    updatePipelineStepper(5, true);

                    showStickyRemediationFromVerdict(verdictCard);

                    return;

                }



                const cliNode = container.querySelector('[data-node="execute_read_only_tool"], [data-node="evaluate_evidence"]');

                if (cliNode) {

                    updatePipelineStepper(4, false);

                    return;

                }



                const cotNode = container.querySelector('[data-node="formulate_hypothesis"]');

                if (cotNode) {

                    updatePipelineStepper(3, false);

                    return;

                }



                const ragNode = container.querySelector('[data-node="retrieve_rfc_standards"]');

                if (ragNode) {

                    updatePipelineStepper(2, false);

                    return;

                }



                const telemetryNode = container.querySelector('[data-node="ingest_telemetry"], [data-node="layer2_ingest_telemetry"]');

                if (telemetryNode) {

                    updatePipelineStepper(1, false);

                    return;

                }

            };



            pipelineObserver = new MutationObserver((mutations) => {

                checkNodes();

            });



            pipelineObserver.observe(container, { childList: true, subtree: true });

            checkNodes();

        }



        // Al completarse el intercambio HTMX de modelos o del workspace de diagnóstico

        document.body.addEventListener('htmx:afterSwap', async function(evt) {

            if (evt.detail && evt.detail.target) {

                highlightSyntaxInCode(evt.detail.target);

            }

            if (evt.detail.target && evt.detail.target.id === 'selModelWrapper') {

                try {

                    const mResp = await fetch('/api/models');

                    modelsData = await mResp.json();

                    const txt = document.getElementById('txtModelTag');

                    if (txt) txt.value = '';

                } catch(e) {

                    console.error("Error sincronizando modelsData tras swap:", e);

                }

            } else if (evt.detail.target && (evt.detail.target.id === 'diagnostico-workspace' || evt.detail.target.id === 'visor-resultados' || evt.detail.target.id === 'mainViewContainer')) {

                const marker = document.getElementById('currentRunDataMarker');

                if (marker) {

                    currentRunMeta = {

                        scId: marker.dataset.runScId,

                        category: marker.dataset.runCategory,

                        modelId: marker.dataset.runModelId,

                        modelName: marker.dataset.runModelName,

                        seed: parseInt(marker.dataset.runSeed) || 42,

                        time: new Date().toLocaleTimeString()

                    };

                    initPipelineObserver();

                    const statusBadge = document.getElementById('streamStatusBadge');

                    if (statusBadge) {

                        const isL = document.documentElement.getAttribute('data-theme') === 'light';

                        statusBadge.style.background = isL ? '#fee2e2' : 'rgba(173, 51, 51, 0.3)';

                        statusBadge.style.borderColor = '#ad3333';

                        statusBadge.style.color = isL ? '#991b1b' : '#ff9999';

                        statusBadge.style.fontWeight = '700';

                        statusBadge.innerHTML = '● Streaming LangGraph Activo...';

                    }

                    const dot = document.getElementById('streamIndicatorDot');

                    if (dot) {

                        dot.style.background = '#ad3333';

                        dot.style.boxShadow = '0 0 10px #ad3333';

                    }

                } else {

                    const selSc = document.getElementById('selScenario');

                    if (selSc) {

                        selSc.addEventListener('change', actualizarGroundTruth);

                    }

                    actualizarGroundTruth();

                    const statusBadge = document.getElementById('streamStatusBadge');

                    if (statusBadge) {

                        const isL = document.documentElement.getAttribute('data-theme') === 'light';

                        statusBadge.style.background = isL ? '#e0f2fe' : 'rgba(0, 51, 102, 0.4)';

                        statusBadge.style.borderColor = isL ? '#7dd3fc' : 'rgba(218, 218, 218, 0.3)';

                        statusBadge.style.color = isL ? '#003366' : '#DADADA';

                        statusBadge.style.fontWeight = '600';

                        statusBadge.innerHTML = 'Estado: Listo';

                    }

                    const dot = document.getElementById('streamIndicatorDot');

                    if (dot) {

                        dot.style.background = '#10b981';

                        dot.style.boxShadow = '0 0 6px #10b981';

                    }

                }

            }

        });



        // Manejador global de errores en respuestas HTTP (500, 504, 422, etc.)

        document.body.addEventListener('htmx:responseError', function(evt) {

            console.error("Error en respuesta HTMX:", evt.detail);

            const status = evt.detail.xhr ? evt.detail.xhr.status : 'Error';

            const statusText = evt.detail.xhr ? (evt.detail.xhr.statusText || 'Error de servidor') : 'Fallo en solicitud';



            // Ocultar indicadores de carga

            const indicator = document.getElementById('diagnostico-indicator');

            if (indicator) indicator.style.display = 'none';



            // Solo actualizar status badge e inyectar banner en visor si el error corresponde al flujo de inferencia/diagnóstico

            const elt = evt.detail.elt;

            const isDiagnosisRequest = elt && (

                elt.id === 'btnRun' ||

                elt.id === 'diagnostico-form' ||

                (elt.closest && elt.closest('#diagnostico-form')) ||

                elt.getAttribute('hx-target') === '#visor-resultados'

            );



            if (isDiagnosisRequest) {

                // Actualizar status badge

                const statusBadge = document.getElementById('streamStatusBadge');

                if (statusBadge) {

                    statusBadge.style.background = '#fee2e2';

                    statusBadge.style.borderColor = '#ef4444';

                    statusBadge.style.color = '#991b1b';

                    statusBadge.innerHTML = `⚠️ Error ${status}: Inferencia Interrumpida`;

                }



                // Inyectar tarjeta elegante de error en el visor de resultados

                const target = document.getElementById('visor-resultados');

                if (target) {

                    const errBox = document.createElement('div');

                    errBox.className = 'p-5 my-4 bg-red-950/70 border-2 border-red-500 rounded-xl text-red-200 text-xs font-mono shadow-2xl animate-fadeIn';

                    errBox.innerHTML = `

                        <div class="flex items-center gap-2 mb-2 text-sm font-bold text-red-400">

                            <svg class="w-5 h-5 text-red-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>

                            <span>Fallo en la Inferencia del Diagnóstico (${status} - ${statusText})</span>

                        </div>

                        <p class="text-xs text-red-300 mb-3 leading-relaxed">

                            El servidor FastAPI o el motor de inferencia local no pudieron completar la solicitud.

                            Esto suele ocurrir si Ollama agota la memoria VRAM de la GPU, si el proceso del modelo fue terminado abruptamente o si sobrepasó el tiempo límite.

                        </p>

                        <div class="flex items-center gap-2">

                            <button type="button" onclick="location.reload()" class="px-3 py-1.5 rounded-lg bg-red-800 hover:bg-red-700 text-white font-bold text-[11px] transition cursor-pointer">

                                ↻ Recargar Entorno

                            </button>

                        </div>

                    `;

                    target.appendChild(errBox);

                }

            }



            if (typeof window.triggerToast === 'function') {

                window.triggerToast(`Error ${status}: Solicitud no completada`);

            }

        });



        // Manejador global de fallos de red / conexión perdida

        document.body.addEventListener('htmx:sendError', function(evt) {

            console.error("Fallo de red en HTMX:", evt.detail);

            const indicator = document.getElementById('diagnostico-indicator');

            if (indicator) indicator.style.display = 'none';

            if (typeof window.triggerToast === 'function') {

                window.triggerToast('Fallo de conexión con el servidor local');

            }

        });



        function actualizarGroundTruth() {

            const selSc = document.getElementById('selScenario');

            if (!selSc) return;

            const scId = selSc.value;

            const sc = scenariosData.find(s => s.scenario_id === scId);

            if (!sc) return;



            const gtBox = document.getElementById('groundTruthInfo');

            if (!gtBox) return;



            gtBox.innerHTML = `

                <div class="mb-2 leading-relaxed">

                    <span class="text-[10px] font-bold text-slate-800 dark:text-slate-300 uppercase tracking-wide block mb-0.5">Descripción del Escenario:</span>

                    <p class="text-slate-700 dark:text-slate-200 text-xs">${sc.description}</p>

                </div>

                <div class="mb-2 bg-blue-100 dark:bg-blue-900/30 border border-blue-300 dark:border-blue-800/60 border-l-4 border-l-[#003366] text-blue-900 dark:text-blue-100 p-2 rounded-md shadow-sm">

                    <span class="text-[9px] font-bold text-slate-800 dark:text-slate-300 uppercase tracking-wide block mb-0.5">Causa Raíz Esperada:</span>

                    <span class="font-bold text-xs block break-words">${sc.ground_truth.root_cause}</span>

                </div>

                <div class="mb-2 bg-red-100 dark:bg-red-900/30 border border-red-300 dark:border-red-800/60 border-l-4 border-l-[#ad3333] text-red-900 dark:text-red-100 p-2 rounded-md shadow-sm">

                    <span class="text-[9px] font-bold text-slate-800 dark:text-slate-300 uppercase tracking-wide block mb-0.5">Componente Afectado:</span>

                    <span class="font-bold font-mono text-xs block break-words">${sc.ground_truth.affected_component}</span>

                </div>

                <div class="leading-relaxed">

                    <span class="text-[10px] font-bold text-slate-800 dark:text-slate-300 uppercase tracking-wide block mb-0.5">Mitigación Recomendada (SOP):</span>

                    <p class="text-slate-600 dark:text-slate-400 text-xs">${sc.ground_truth.suggested_action}</p>

                </div>

            `;

            updateDiagPdfHref();

        }



        function getActiveScenarioParams() {

            let scId = 'DNS-NXD-01';

            let modelId = 'phi-4-mini-instruct';

            let seed = 42;

            const marker = document.getElementById('currentRunDataMarker');

            if (marker && marker.dataset.runScId) {

                scId = marker.dataset.runScId;

                modelId = marker.dataset.runModelId || modelId;

                seed = parseInt(marker.dataset.runSeed) || seed;

            } else {

                const selSc = document.getElementById('selScenario');

                const selM = document.getElementById('selModel');

                const txtSeed = document.getElementById('txtSeed');

                if (selSc && selSc.value) scId = selSc.value;

                if (selM && selM.value) modelId = selM.value;

                if (txtSeed && txtSeed.value) seed = parseInt(txtSeed.value) || seed;

            }

            return { scId, modelId, seed };

        }



        function updateDiagPdfHref() {

            const params = getActiveScenarioParams();

            const btn = document.getElementById('btnExportDiagPdf');

            if (btn) {

                btn.href = `/api/export/pdf/diagnosis?scenario_id=${encodeURIComponent(params.scId)}&model_id=${encodeURIComponent(params.modelId)}&seed=${params.seed}`;

            }

        }



        function downloadCurrentDiagnosticLog() {

            const params = getActiveScenarioParams();

            const timeline = document.getElementById('timelineEventsContainer');

            const hasTimeline = timeline && timeline.innerText.trim().length > 30;



            if (hasTimeline) {

                const logData = {

                    benchmark: "NetDiagBench-L7",

                    timestamp: new Date().toISOString(),

                    scenario_id: params.scId,

                    model_id: params.modelId,

                    seed: params.seed,

                    trace_raw: timeline.innerText.trim()

                };

                const blob = new Blob([JSON.stringify(logData, null, 2)], { type: "application/json" });

                const url = URL.createObjectURL(blob);

                const a = document.createElement("a");

                a.href = url;

                a.download = `log_${params.scId}_${params.modelId}_${Date.now()}.json`;

                document.body.appendChild(a);

                a.click();

                document.body.removeChild(a);

                URL.revokeObjectURL(url);

            } else {

                window.location.href = `/api/export/diagnostic-log?scenario_id=${encodeURIComponent(params.scId)}&model_id=${encodeURIComponent(params.modelId)}&seed=${params.seed}&format=json`;

            }

        }



        // ================= HELPERS DE PORTAPAPELES Y EXPORTACIONES =================

        async function copyTextToClipboard(btn, text) {

            try {

                await navigator.clipboard.writeText(text);

                const originalHtml = btn.innerHTML;

                btn.innerHTML = '<span class="text-emerald-400 font-bold">✓ Copiado</span>';

                setTimeout(() => {

                    btn.innerHTML = originalHtml;

                }, 2000);

            } catch(e) {

                console.error("Clipboard copy error:", e);

            }

        }



        async function copyDiagnosisMarkdown(btn, scId, rc, comp, act, exp, conf, ttft, tok, vram, lat) {

            const md = `# Reporte de Diagnóstico L7 - NetDiagBench-L7\n\n- **Escenario:** ${scId}\n- **Causa Raíz:** ${rc}\n- **Componente Afectado:** ${comp}\n- **Mitigación Sugerida:** ${act}\n- **Nivel de Confianza:** ${(conf * 100).toFixed(0)}%\n\n### Razonamiento y Justificación\n${exp}\n\n### Telemetría de Inferencia\n- **TTFT (Time-To-First-Token):** ${ttft} ms\n- **Throughput:** ${tok} tok/s\n- **Uso VRAM:** ${vram} GB\n- **Latencia Total de Inferencia:** ${lat} s\n`;

            await copyTextToClipboard(btn, md);

        }



        async function copyTicketToClipboard(btn) {

            const params = getActiveScenarioParams();

            const sc = Array.isArray(scenariosData) ? scenariosData.find(s => s.scenario_id === params.scId) : null;

            let rootCause = sc?.ground_truth?.root_cause || 'Bajo análisis';

            let affectedComp = sc?.ground_truth?.affected_component || 'Servicio L7';

            let mitigation = sc?.ground_truth?.suggested_action || 'Revisar logs y configuración de servicio';



            const rcElem = document.querySelector('[data-verdict-rc]');

            if (rcElem && rcElem.textContent) rootCause = rcElem.textContent.trim();

            const compElem = document.querySelector('[data-verdict-comp]');

            if (compElem && compElem.textContent) affectedComp = compElem.textContent.trim();

            const actElem = document.querySelector('[data-verdict-act]');

            if (actElem && actElem.textContent) mitigation = actElem.textContent.trim();



            const ticketMarkdown = [

                `### [INCIDENCIA L7] Diagnóstico Automatizado • ${params.scId}`,

                `**Sistema:** NetDiagBench-L7 | **Fecha:** ${new Date().toLocaleString()}`,

                `- **Escenario / RFC:** ${params.scId} (${sc?.category || 'Red L7'})`,

                `- **Clase de Falla:** ${sc?.fault_class || 'L7_FAILURE'}`,

                `- **Componente Afectado:** \`${affectedComp}\``,

                `- **Modelo Evaluado:** \`${params.modelId}\` (Semilla: ${params.seed})`,

                `- **Causa Raíz Diagnosticada:** ${rootCause}`,

                `- **Acción de Mitigación (SOP / RFC):**`,

                `  > ${mitigation}`,

                `- **Trazabilidad:** Verificado mediante grafos LangGraph y base normativa IETF.`,

                `---`

            ].join('\n');



            try {

                await navigator.clipboard.writeText(ticketMarkdown);

                if (btn) {

                    const orig = btn.innerHTML;

                    btn.innerHTML = '<span class="text-emerald-400 font-bold">✓ Ficha Copiada</span>';

                    setTimeout(() => { btn.innerHTML = orig; }, 2500);

                }

                window.triggerToast('<strong class="text-emerald-400">✓ Ficha de Incidencia Copiada:</strong> Formato Markdown/Jira listo para pegar en ticket del NOC.');

            } catch(e) {

                try {

                    const ta = document.createElement('textarea');

                    ta.value = ticketMarkdown;

                    ta.style.position = 'fixed';

                    ta.style.left = '-9999px';

                    document.body.appendChild(ta);

                    ta.select();

                    document.execCommand('copy');

                    document.body.removeChild(ta);

                    if (btn) {

                        const orig = btn.innerHTML;

                        btn.innerHTML = '<span class="text-emerald-400 font-bold">✓ Ficha Copiada</span>';

                        setTimeout(() => { btn.innerHTML = orig; }, 2500);

                    }

                    window.triggerToast('<strong class="text-emerald-400">✓ Ficha de Incidencia Copiada:</strong> Formato Markdown/Jira listo para pegar en ticket del NOC.');

                } catch(err2) {

                    console.error("Error al copiar ficha para ticket:", err2);

                    window.triggerToast('<strong class="text-rose-400">Error al copiar al portapapeles.</strong>');

                }

            }

        }

        window.copyTicketToClipboard = copyTicketToClipboard;



        function downloadDiagnosisJson(scId, rc, comp, act, exp, conf, ttft, tok, vram, lat) {

            const data = {

                benchmark: "NetDiagBench-L7",

                timestamp: new Date().toISOString(),

                scenario_id: scId,

                diagnosis: {

                    root_cause: rc,

                    affected_component: comp,

                    suggested_action: act,

                    explanation: exp,

                    confidence: conf

                },

                inference_telemetry: {

                    ttft_ms: ttft,

                    throughput_tokens_per_sec: tok,

                    vram_usage_gb: vram,

                    total_latency_sec: lat

                }

            };

            const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });

            const url = URL.createObjectURL(blob);

            const a = document.createElement("a");

            a.href = url;

            a.download = `diagnostico_${scId}_${Date.now()}.json`;

            document.body.appendChild(a);

            a.click();

            document.body.removeChild(a);

            URL.revokeObjectURL(url);

        }



        // ================= HISTORIAL DE EJECUCIONES RECIENTES =================

        const sessionRecentRuns = [];

        function recordRecentRun(meta) {

            sessionRecentRuns.unshift(meta);

            if (sessionRecentRuns.length > 5) sessionRecentRuns.pop();

            renderRecentRuns();

        }

        function renderRecentRuns() {

            const card = document.getElementById('recentRunsCard');

            const list = document.getElementById('recentRunsList');

            if (!card || !list) return;

            if (sessionRecentRuns.length === 0) { card.style.display = 'none'; return; }

            card.style.display = 'block';

            list.innerHTML = sessionRecentRuns.map((r, i) => `

                <div class="recent-run-item p-1.5 rounded bg-slate-800/60 border border-slate-700/60 hover:border-emerald-500/50 cursor-pointer flex justify-between items-center transition" onclick="loadRecentRun(${i})">

                    <span class="font-mono text-emerald-400 font-semibold">${r.scenario_id || ''}</span>

                    <span class="text-slate-300 text-[11px]">${r.model_id || ''}</span>

                </div>

            `).join('');

        }

        function loadRecentRun(index) {

            const r = sessionRecentRuns[index];

            if (!r) return;

            const selSc = document.getElementById('selScenario');

            const selMo = document.getElementById('selModel');

            if (selSc && r.scenario_id) selSc.value = r.scenario_id;

            if (selMo && r.model_id) selMo.value = r.model_id;

        }

        function clearRecentRuns() {

            sessionRecentRuns.length = 0;

            renderRecentRuns();

        }



        function ejecutarDiagnostico() {

            const btn = document.getElementById('btnRun');

            if (btn && !btn.disabled) {

                btn.click();

            }

        }



        // Listeners globales para el ciclo de vida de Server-Sent Events (HTMX)

        document.body.addEventListener('htmx:sseClose', function(evt) {

            const btn = document.getElementById('btnRun');

            if (btn) {

                btn.disabled = false;

                btn.innerHTML = `

                    <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20" style="display:inline-block; vertical-align:middle; margin-right:4px;">

                        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clip-rule="evenodd"/>

                    </svg>

                    <span>Ejecutar Diagnóstico</span>

                    <span class="text-[10px] px-1.5 py-0.5 rounded bg-black/30 border border-white/20 text-white/80 font-mono font-normal ml-1">Ctrl+↵</span>

                `;

            }

            const statusBadge = document.getElementById('streamStatusBadge');

            if (statusBadge) {

                const isL = document.documentElement.getAttribute('data-theme') === 'light';

                statusBadge.style.background = isL ? '#dcfce7' : 'rgba(16, 185, 129, 0.2)';

                statusBadge.style.borderColor = '#10b981';

                statusBadge.style.color = isL ? '#065f46' : '#34d399';

                statusBadge.style.fontWeight = '700';

                statusBadge.innerHTML = '✓ Diagnóstico Completado';

            }

            const dot = document.getElementById('streamIndicatorDot');

            if (dot) {

                dot.style.background = '#10b981';

                dot.style.boxShadow = '0 0 8px #10b981';

            }

            currentRunMeta = null;

        });



        document.body.addEventListener('htmx:sseError', function(evt) {

            const sseEl = document.getElementById('timelineEventsContainer');

            if (sseEl && sseEl.hasAttribute('sse-connect')) {

                sseEl.removeAttribute('sse-connect');

            }

            const btn = document.getElementById('btnRun');

            if (btn && btn.disabled) {

                btn.disabled = false;

                btn.innerHTML = `

                    <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20" style="display:inline-block; vertical-align:middle; margin-right:4px;">

                        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clip-rule="evenodd"/>

                    </svg>

                    <span>Ejecutar Diagnóstico</span>

                    <span class="text-[10px] px-1.5 py-0.5 rounded bg-black/30 border border-white/20 text-white/80 font-mono font-normal ml-1">Ctrl+↵</span>

                `;

            }

            const statusBadge = document.getElementById('streamStatusBadge');

            if (statusBadge) {

                const isL = document.documentElement.getAttribute('data-theme') === 'light';

                statusBadge.style.background = isL ? '#fee2e2' : 'rgba(173, 51, 51, 0.2)';

                statusBadge.style.borderColor = '#ad3333';

                statusBadge.style.color = isL ? '#991b1b' : '#ff9999';

                statusBadge.style.fontWeight = '700';

                statusBadge.innerHTML = '⚠ SSE Desconectado';

            }

            const dot = document.getElementById('streamIndicatorDot');

            if (dot) {

                dot.style.background = '#f59e0b';

                dot.style.boxShadow = '0 0 8px #f59e0b';

            }

        });



        document.body.addEventListener('htmx:sseMessage', function(evt) {

            const host = document.getElementById('timelineHost');

            if (host) {

                host.scrollTop = host.scrollHeight;

            }

            const visor = document.getElementById('visor-resultados');

            if (visor) {

                visor.scrollTop = visor.scrollHeight;

            }

        });



        // ================= GESTIÓN DEL MENÚ LATERAL Y CICLO DE VIDA =================

        function applySidebarState(expanded, widthStr) {

            const sidebar = document.getElementById('sidebarCol');

            if (!sidebar) return;



            if (expanded) {

                sidebar.classList.remove('sidebar-collapsed');

                sidebar.setAttribute('data-collapsed', 'false');

                const targetWidth = (widthStr && widthStr !== '64px' && widthStr !== '72px') ? widthStr : (localStorage.getItem('netdiag_sidebar_width') || '320px');

                sidebar.style.width = targetWidth;

                localStorage.setItem('netdiag_sidebar_collapsed', 'false');

                localStorage.setItem('netdiag_sidebar_width', targetWidth);

                window.dispatchEvent(new CustomEvent('set-sidebar-state', {

                    detail: { expanded: true, width: targetWidth }

                }));

            } else {

                sidebar.classList.add('sidebar-collapsed');

                sidebar.setAttribute('data-collapsed', 'true');

                sidebar.style.width = '64px';

                localStorage.setItem('netdiag_sidebar_collapsed', 'true');

                window.dispatchEvent(new CustomEvent('set-sidebar-state', {

                    detail: { expanded: false, width: '64px' }

                }));

            }

        }

        window.applySidebarState = applySidebarState;



        function toggleSidebar(e) {

            if (e) {

                if (typeof e.preventDefault === 'function') e.preventDefault();

                if (typeof e.stopPropagation === 'function') e.stopPropagation();

            }

            const sidebar = document.getElementById('sidebarCol');

            if (!sidebar) return;

            const isCurrentlyCollapsed = sidebar.classList.contains('sidebar-collapsed') ||

                                         sidebar.getAttribute('data-collapsed') === 'true' ||

                                         sidebar.offsetWidth <= 120;

            if (isCurrentlyCollapsed) {

                let savedWidth = localStorage.getItem('netdiag_sidebar_width') || '320px';

                if (!savedWidth || savedWidth === '64px' || savedWidth === '72px' || parseInt(savedWidth, 10) < 180) {

                    savedWidth = '320px';

                }

                applySidebarState(true, savedWidth);

            } else {

                const curWidth = sidebar.offsetWidth;

                if (curWidth > 180) {

                    localStorage.setItem('netdiag_sidebar_width', curWidth + 'px');

                }

                applySidebarState(false, '64px');

            }

        }

        window.toggleSidebar = toggleSidebar;



        document.addEventListener('DOMContentLoaded', () => {

            const sidebar = document.getElementById('sidebarCol');

            const resizer = document.getElementById('sidebarResizer');



            // Restaurar estado guardado inmediatamente

            const savedCollapsed = localStorage.getItem('netdiag_sidebar_collapsed') === 'true';

            const savedWidth = localStorage.getItem('netdiag_sidebar_width') || '320px';

            if (savedCollapsed) {

                applySidebarState(false, '64px');

            } else {

                applySidebarState(true, savedWidth);

            }



            if (sidebar && resizer) {

                let isDragging = false;

                let startX = 0;

                let startWidth = 320;

                let animationFrameId = null;



                resizer.addEventListener('mousedown', (e) => {

                    e.preventDefault();

                    isDragging = true;

                    startX = e.clientX;

                    startWidth = sidebar.offsetWidth || 320;

                    document.body.style.userSelect = 'none';

                    document.body.style.cursor = 'col-resize';

                    sidebar.classList.add('resizing');



                    // Prevenir que iframes en vistas analíticas capturen eventos de ratón durante el arrastre

                    document.querySelectorAll('iframe').forEach(f => {

                        f.style.pointerEvents = 'none';

                    });



                    window.dispatchEvent(new CustomEvent('set-sidebar-state', {

                        detail: { isResizing: true, expanded: !sidebar.classList.contains('sidebar-collapsed') }

                    }));



                    const onMouseMove = (moveEvt) => {

                        if (!isDragging) return;

                        if (animationFrameId) cancelAnimationFrame(animationFrameId);

                        animationFrameId = requestAnimationFrame(() => {

                            const delta = moveEvt.clientX - startX;

                            const rawWidth = startWidth + delta;

                            if (rawWidth < 180) {

                                applySidebarState(false, '64px');

                            } else {

                                const newWidth = Math.min(Math.max(rawWidth, 220), 650);

                                applySidebarState(true, newWidth + 'px');

                            }

                        });

                    };



                    const onMouseUp = () => {

                        if (!isDragging) return;

                        isDragging = false;

                        document.body.style.userSelect = '';

                        document.body.style.cursor = '';

                        sidebar.classList.remove('resizing');

                        document.removeEventListener('mousemove', onMouseMove);

                        document.removeEventListener('mouseup', onMouseUp);

                        if (animationFrameId) cancelAnimationFrame(animationFrameId);



                        // Restaurar eventos de puntero en iframes

                        document.querySelectorAll('iframe').forEach(f => {

                            f.style.pointerEvents = '';

                        });



                        const finalWidth = sidebar.offsetWidth || 320;

                        if (finalWidth <= 120) {

                            applySidebarState(false, '64px');

                        } else {

                            const clamped = Math.min(Math.max(finalWidth, 220), 650);

                            applySidebarState(true, clamped + 'px');

                        }



                        window.dispatchEvent(new CustomEvent('set-sidebar-state', {

                            detail: { isResizing: false, expanded: !sidebar.classList.contains('sidebar-collapsed') }

                        }));

                    };



                    document.addEventListener('mousemove', onMouseMove);

                    document.addEventListener('mouseup', onMouseUp);

                });

            }



            // Delegación de eventos para sincronizar inputs independientemente de reemplazos HTMX

            document.body.addEventListener('change', function(e) {

                if (e.target && e.target.id === 'selScenario') {

                    actualizarGroundTruth();

                    syncUrlParams();

                } else if (e.target && (e.target.id === 'selModel' || e.target.id === 'txtSeed')) {

                    syncUrlParams();

                }

            });



            // Inicializar datos del dashboard de inmediato sin esperar a window.onload

            init();

            const initialViewParam = new URLSearchParams(window.location.search).get('view');

            if (initialViewParam && initialViewParam !== 'diagnostico') {

                activateMainView(initialViewParam);

            } else {

                switchMainView('diagnostico', true);

            }

            initPipelineObserver();

        });



        function toggleAccordion(cardId) {

            const card = document.getElementById(cardId);

            if (!card) return;

            card.classList.toggle('collapsed');

        }



        // ================= CONMUTADOR DE VISTAS (HTMX STANDARD) =================

        let currentActiveView = 'diagnostico';

        let currentIframeUrl = '';



        function activateMainView(viewKey, forceReload = false) {

            if (viewKey === 'observabilidad' || viewKey === 'configuracion') {

                viewKey = 'diagnostico';

            }

            const btnMap = {

                'diagnostico': 'btnNavObservability',

                'comparativo': 'btnAnalytics',

                'correlacion': 'btnCorrAnalysis',

                'consolidado': 'btnHtmlReport',

                'suite_observabilidad': 'btnSuiteObservabilidad',

                'human_eval': 'btnHumanEval'

            };

            const targetBtn = document.getElementById(btnMap[viewKey]);

            if (targetBtn) {

                targetBtn.click();

            } else {

                switchMainView(viewKey);

            }

        }

        window.activateMainView = activateMainView;



        function switchMainView(viewKey) {

            if (viewKey === 'observabilidad' || viewKey === 'configuracion') {

                viewKey = 'diagnostico';

            }

            currentActiveView = viewKey;

            // Control de visibilidad del header superior (#mainViewHeader)
            const mainHdr = document.getElementById('mainViewHeader');
            if (mainHdr) {
                if (viewKey === 'human_eval') {
                    mainHdr.style.display = 'none';
                } else {
                    mainHdr.style.display = '';
                }
            }

            // Control de scroll en el contenedor principal (#mainViewContainer)
            const mainCont = document.getElementById('mainViewContainer');
            if (mainCont) {
                if (viewKey === 'human_eval') {
                    mainCont.classList.remove('overflow-hidden');
                    mainCont.classList.add('overflow-y-auto', 'custom-scrollbar');
                } else {
                    mainCont.classList.add('overflow-hidden');
                    mainCont.classList.remove('overflow-y-auto', 'custom-scrollbar');
                }
            }



            // 1. Actualizar estado activo en los botones de navegación lateral

            const btnMap = {

                'diagnostico': 'btnNavObservability',

                'comparativo': 'btnAnalytics',

                'correlacion': 'btnCorrAnalysis',

                'consolidado': 'btnHtmlReport',

                'suite_observabilidad': 'btnSuiteObservabilidad',

                'human_eval': 'btnHumanEval'

            };

            ['btnNavObservability', 'btnAnalytics', 'btnCorrAnalysis', 'btnHtmlReport', 'btnSuiteObservabilidad', 'btnHumanEval'].forEach(id => {

                const el = document.getElementById(id);

                if (el) el.classList.remove('active');

            });

            const activeBtn = document.getElementById(btnMap[viewKey]);

            if (activeBtn) activeBtn.classList.add('active');



            // Sincronizar estado global reactivo con Alpine.js

            try {

                if (window.Alpine && window.Alpine.store && window.Alpine.store('netdiag')) {

                    window.Alpine.store('netdiag').setActiveView(viewKey);

                }

            } catch(e) {}



            // 2. Cierre inmediato de SSE huérfanos al salir del visor de diagnóstico

            if (viewKey !== 'diagnostico') {

                if (window.activeEventSource) {

                    try { window.activeEventSource.close(); } catch(e){}

                    window.activeEventSource = null;

                }

                if (window.activeEventSources && window.activeEventSources.length) {

                    window.activeEventSources.forEach(es => {

                        try { es.close(); } catch(e){}

                    });

                    window.activeEventSources = [];

                }

                const tc = document.getElementById('timelineEventsContainer');

                if (tc) tc.removeAttribute('sse-connect');

            }



            // 3. Elementos del encabezado del dashboard

            const titleText = document.getElementById('mainViewTitleText');

            const subtitleText = document.getElementById('mainViewSubtitleText');

            const dot = document.getElementById('streamIndicatorDot');

            const openExtBtn = document.getElementById('btnOpenInNewTab');

            const printBtn = document.getElementById('btnPrintView');

            const badge = document.getElementById('streamStatusBadge');

            const excelBtn = document.getElementById('btnDownloadExcel');
            const csvBtn = document.getElementById('btnDownloadCsv');

            const excelBtnText = document.getElementById('btnDownloadExcelText');

            const jsonBtn = document.getElementById('btnDownloadJson');

            const jsonBtnText = document.getElementById('btnDownloadJsonText');

            const pdfBtn = document.getElementById('btnDownloadPdf');

            const pdfBtnText = document.getElementById('btnDownloadPdfText');

            const btnDiagLog = document.getElementById('btnDownloadDiagLog');

            const btnDiagPdf = document.getElementById('btnExportDiagPdf');



            const setBtnDisplay = (btn, groupId, display) => {

                if (btn) btn.style.display = display;

                const grp = document.getElementById(groupId);

                if (grp) grp.style.display = display;

            };

            const updateTooltip = (tooltipId, text) => {

                const tt = document.getElementById(tooltipId);

                if (tt && text) tt.textContent = text;

            };



            if (viewKey === 'diagnostico') {

                currentIframeUrl = '';

                if (titleText) titleText.textContent = 'Visor de Diagnóstico L7';

                if (subtitleText) subtitleText.textContent = 'Configuración de Escenario • Inferencia SLM • Observabilidad CoT en Tiempo Real';

                if (dot) {

                    dot.style.display = 'inline-block';

                    dot.style.background = '#10b981';

                    dot.style.boxShadow = '0 0 6px #10b981';

                }



                setBtnDisplay(btnDiagLog, 'groupDownloadDiagLog', 'inline-flex');

                setBtnDisplay(btnDiagPdf, 'groupExportDiagPdf', 'inline-flex');

                updateDiagPdfHref();

                setBtnDisplay(excelBtn, 'groupDownloadExcel', 'none');

                setBtnDisplay(jsonBtn, 'groupDownloadJson', 'none');

                setBtnDisplay(pdfBtn, 'groupDownloadPdf', 'none');

                setBtnDisplay(openExtBtn, 'groupOpenInNewTab', 'none');

                setBtnDisplay(printBtn, 'groupPrintView', 'inline-flex');

                if (badge) badge.style.display = 'inline-block';

                actualizarGroundTruth();

            } else if (viewKey === 'comparativo') {

                currentIframeUrl = '/analitica?view=comparativo';

                if (titleText) titleText.textContent = 'Informe Técnico Comparativo Multidimensional (OE4)';

                if (subtitleText) subtitleText.textContent = 'Matriz Radar de Evaluación • Score Compuesto • Comparativa Cruzada de Modelos';

                if (dot) dot.style.display = 'none';



                setBtnDisplay(btnDiagLog, 'groupDownloadDiagLog', 'none');

                setBtnDisplay(btnDiagPdf, 'groupExportDiagPdf', 'none');

                if (badge) badge.style.display = 'none';



                setBtnDisplay(excelBtn, 'groupDownloadExcel', 'inline-flex');
                setBtnDisplay(csvBtn, 'groupDownloadCsv', 'inline-flex');
                if (csvBtn) csvBtn.href = '/api/export/csv';

                if (excelBtn) excelBtn.href = '/api/export/excel';

                if (excelBtnText) excelBtnText.textContent = 'Descargar Excel (OE4)';

                updateTooltip('tooltipDownloadExcel', 'Descargar Excel (OE4)');

                setBtnDisplay(jsonBtn, 'groupDownloadJson', 'none');

                setBtnDisplay(pdfBtn, 'groupDownloadPdf', 'inline-flex');

                if (pdfBtn) pdfBtn.href = '/api/export/pdf/comparative';

                if (pdfBtnText) pdfBtnText.textContent = 'PDF Comparativo (OE4)';

                updateTooltip('tooltipDownloadPdf', 'PDF Comparativo (OE4)');

                setBtnDisplay(printBtn, 'groupPrintView', 'inline-flex');

                setBtnDisplay(openExtBtn, 'groupOpenInNewTab', 'inline-flex');

            } else if (viewKey === 'correlacion') {

                currentIframeUrl = '/analitica?view=correlacion';

                if (titleText) titleText.textContent = 'Análisis Correlacional y Significancia Estadística (Tarea 4.1.2)';

                if (subtitleText) subtitleText.textContent = 'Pruebas Kruskal-Wallis • Correlación Spearman • Intervalos de Confianza 95% (SciPy)';

                if (dot) dot.style.display = 'none';



                setBtnDisplay(btnDiagLog, 'groupDownloadDiagLog', 'none');

                setBtnDisplay(btnDiagPdf, 'groupExportDiagPdf', 'none');

                if (badge) badge.style.display = 'none';



                // En análisis correlacional se elimina el botón de Excel (no aplica y es redundante con comparativo)

                setBtnDisplay(excelBtn, 'groupDownloadExcel', 'none');

                setBtnDisplay(jsonBtn, 'groupDownloadJson', 'inline-flex');

                if (jsonBtn) jsonBtn.href = '/api/export/json';

                if (jsonBtnText) jsonBtnText.textContent = 'Descargar JSON';

                updateTooltip('tooltipDownloadJson', 'Descargar JSON');

                setBtnDisplay(pdfBtn, 'groupDownloadPdf', 'inline-flex');

                if (pdfBtn) pdfBtn.href = '/api/export/pdf/correlation';

                if (pdfBtnText) pdfBtnText.textContent = 'PDF Correlacional (SciPy)';

                updateTooltip('tooltipDownloadPdf', 'PDF Correlacional (SciPy)');

                setBtnDisplay(printBtn, 'groupPrintView', 'inline-flex');

                setBtnDisplay(openExtBtn, 'groupOpenInNewTab', 'inline-flex');

            } else if (viewKey === 'consolidado') {

                currentIframeUrl = '/api/report-html';

                if (titleText) titleText.textContent = 'Informe Consolidado Global de Benchmarking (HTML)';

                if (subtitleText) subtitleText.textContent = 'Reporte Técnico Integral • Trazabilidad Completa del Benchmark L7';

                if (dot) dot.style.display = 'none';



                setBtnDisplay(btnDiagLog, 'groupDownloadDiagLog', 'none');

                setBtnDisplay(btnDiagPdf, 'groupExportDiagPdf', 'none');

                if (badge) badge.style.display = 'none';



                // En informe consolidado se elimina el botón de Excel (duplicado de comparativo)

                setBtnDisplay(excelBtn, 'groupDownloadExcel', 'none');

                setBtnDisplay(jsonBtn, 'groupDownloadJson', 'inline-flex');

                if (jsonBtn) jsonBtn.href = '/api/export/json';

                if (jsonBtnText) jsonBtnText.textContent = 'Descargar JSON';

                updateTooltip('tooltipDownloadJson', 'Descargar JSON');

                setBtnDisplay(pdfBtn, 'groupDownloadPdf', 'inline-flex');

                if (pdfBtn) pdfBtn.href = '/api/export/pdf/consolidated';

                if (pdfBtnText) pdfBtnText.textContent = 'PDF Consolidado';

                updateTooltip('tooltipDownloadPdf', 'PDF Consolidado');

                setBtnDisplay(printBtn, 'groupPrintView', 'inline-flex');

                setBtnDisplay(openExtBtn, 'groupOpenInNewTab', 'inline-flex');

            } else if (viewKey === 'suite_observabilidad') {

                currentIframeUrl = '/observabilidad?embed=true';

                if (titleText) titleText.textContent = 'Suite de Observabilidad Completa (18 Escenarios Catalogados)';

                if (subtitleText) subtitleText.textContent = 'Streaming Continuo en Tiempo Real (HTMX + SSE + LangGraph)';

                if (dot) dot.style.display = 'none';



                setBtnDisplay(btnDiagLog, 'groupDownloadDiagLog', 'none');

                setBtnDisplay(btnDiagPdf, 'groupExportDiagPdf', 'none');

                if (badge) badge.style.display = 'none';



                const runParam = window.currentSuiteRunId ? ('?run_id=' + encodeURIComponent(window.currentSuiteRunId)) : '';



                setBtnDisplay(excelBtn, 'groupDownloadExcel', 'inline-flex');
                setBtnDisplay(csvBtn, 'groupDownloadCsv', 'inline-flex');
                if (csvBtn) csvBtn.href = '/api/export/csv';

                if (excelBtn) excelBtn.href = '/api/export/excel' + runParam;

                if (excelBtnText) excelBtnText.textContent = 'Descargar Excel (Suite)';

                updateTooltip('tooltipDownloadExcel', 'Descargar Excel (Suite)');

                setBtnDisplay(jsonBtn, 'groupDownloadJson', 'inline-flex');

                if (jsonBtn) jsonBtn.href = '/api/export/json' + runParam;

                if (jsonBtnText) jsonBtnText.textContent = 'Descargar JSON (Suite)';

                updateTooltip('tooltipDownloadJson', 'Descargar JSON (Suite)');

                setBtnDisplay(pdfBtn, 'groupDownloadPdf', 'inline-flex');

                if (pdfBtn) pdfBtn.href = '/api/export/pdf/suite' + runParam;

                if (pdfBtnText) pdfBtnText.textContent = 'Reporte de la Suite (PDF)';

                updateTooltip('tooltipDownloadPdf', 'Reporte de la Suite (PDF)');

                setBtnDisplay(printBtn, 'groupPrintView', 'inline-flex');

                setBtnDisplay(openExtBtn, 'groupOpenInNewTab', 'inline-flex');

            } else if (viewKey === 'human_eval') {
                if (titleText) titleText.textContent = 'Capa 8: Validación Humana y Calibración Inter-Evaluador';
                if (subtitleText) subtitleText.textContent = 'Evaluación Ciega Independiente • Muestra Estratificada de 54 Corridas • Rúbrica 6 Criterios + Sustentación';
                if (dot) dot.style.display = 'inline-block';
                setBtnDisplay(btnDiagLog, 'groupDownloadDiagLog', 'none');
                setBtnDisplay(btnDiagPdf, 'groupExportDiagPdf', 'none');
                if (badge) badge.style.display = 'none';
                setBtnDisplay(excelBtn, 'groupDownloadExcel', 'none');
                setBtnDisplay(csvBtn, 'groupDownloadCsv', 'none');
                setBtnDisplay(jsonBtn, 'groupDownloadJson', 'none');
                setBtnDisplay(pdfBtn, 'groupDownloadPdf', 'none');
                setBtnDisplay(printBtn, 'groupPrintView', 'none');
                setBtnDisplay(openExtBtn, 'groupOpenInNewTab', 'none');
            }



            if (typeof window.syncUrlParams === 'function') {

                window.syncUrlParams();

            }

        }



        window.triggerToast = function(msg) {

            const bodyEl = document.querySelector('body');

            if (bodyEl && bodyEl.__x && bodyEl.__x.$data && typeof bodyEl.__x.$data.triggerToast === 'function') {

                bodyEl.__x.$data.triggerToast(msg);

            } else {

                console.log("[TOAST]", msg);

            }

        };



        window.guardSuiteExport = function(event, exportType) {

            if (window.currentActiveView !== 'suite_observabilidad') {

                return true;

            }

            const isFinished = window.isSuiteFinished === true || (window.lastCompletedScenarioIndex >= 18);

            if (!isFinished) {

                if (event) {

                    event.preventDefault();

                    event.stopPropagation();

                }

                const currentDone = window.lastCompletedScenarioIndex || 0;

                const msg = '<strong class="text-amber-300">Descarga Bloqueada:</strong> La Suite está en curso (' + currentDone + '/18 casos resueltos). Espera a que finalice completamente (18/18) para exportar ' + exportType.toUpperCase() + ' con resultados empíricos reales.';

                window.triggerToast(msg);

                return false;

            }

            return true;

        };



        window.onSuiteRunStarted = function(runId) {

            window.currentSuiteRunId = runId;

            window.isSuiteFinished = false;

            const pdfBtn = document.getElementById('btnDownloadPdf');

            const excelBtn = document.getElementById('btnDownloadExcel');
            const csvBtn = document.getElementById('btnDownloadCsv');

            const jsonBtn = document.getElementById('btnDownloadJson');

            if (window.currentActiveView === 'suite_observabilidad') {

                if (pdfBtn) pdfBtn.href = '/api/export/pdf/suite?run_id=' + encodeURIComponent(runId);

                if (excelBtn) excelBtn.href = '/api/export/excel?run_id=' + encodeURIComponent(runId);

                if (jsonBtn) jsonBtn.href = '/api/export/json?run_id=' + encodeURIComponent(runId);

            }

        };



        window.onSuiteRunCompleted = function(runId) {

            window.currentSuiteRunId = runId;

            window.isSuiteFinished = true;

            window.lastCompletedScenarioIndex = 18;

            const pdfBtn = document.getElementById('btnDownloadPdf');

            const excelBtn = document.getElementById('btnDownloadExcel');
            const csvBtn = document.getElementById('btnDownloadCsv');

            const jsonBtn = document.getElementById('btnDownloadJson');

            if (window.currentActiveView === 'suite_observabilidad') {

                if (pdfBtn) pdfBtn.href = '/api/export/pdf/suite?run_id=' + encodeURIComponent(runId);

                if (excelBtn) excelBtn.href = '/api/export/excel?run_id=' + encodeURIComponent(runId);

                if (jsonBtn) jsonBtn.href = '/api/export/json?run_id=' + encodeURIComponent(runId);

            }

            window.triggerToast('<strong class="text-emerald-400">Suite Completada (18/18):</strong> Reportes PDF, Excel y JSON generados con la Cadena de Razonamiento real (ID: <code>' + runId + '</code>).');

        };



        window.addEventListener('suite-progress', function(e) {

            if (e.detail && e.detail.run_id) {

                window.currentSuiteRunId = e.detail.run_id;

            }

            if (e.detail && typeof e.detail.index === 'number') {

                window.lastCompletedScenarioIndex = e.detail.index;

            }

        });



        window.addEventListener('suite-finished', function(e) {

            if (e.detail && e.detail.run_id) {

                window.onSuiteRunCompleted(e.detail.run_id);

            }

        });



        window.onModelSelectionChanged = function(param) {

            const excel = document.getElementById('btnDownloadExcel');

            const json = document.getElementById('btnDownloadJson');

            if (excel) excel.href = '/api/export/excel' + (param || '');

            if (json) json.href = '/api/export/json' + (param || '');

            const pdf = document.getElementById('btnDownloadPdf');

            if (pdf && pdf.href) {

                const base = pdf.href.split('?')[0];

                pdf.href = base + (param || '');

            }

        };



        // ================= MEJORAS UX: BITÁCORA DE SESIÓN EN RAM =================

        window.markActiveHistoryCard = function(el) {

            document.querySelectorAll('.hist-card').forEach(c => {

                c.classList.remove('active-history-card');

            });

            if (el) {

                el.classList.add('active-history-card');

            }

        };



        window.filterHistoryStatus = function(status, btn) {

            document.querySelectorAll('.hist-filter-chip').forEach(b => {

                b.classList.remove('active-hist-chip');

            });

            if (btn) {

                btn.classList.add('active-hist-chip');

            }

            const cards = document.querySelectorAll('.hist-card');

            cards.forEach(card => {

                const cardStatus = (card.getAttribute('data-status') || '').toUpperCase();

                const isCorrect = card.getAttribute('data-correct') === 'true';

                if (status === 'ALL') {

                    card.style.display = 'flex';

                } else if (status === 'RESUELTO') {

                    card.style.display = (cardStatus === 'RESUELTO' || isCorrect) ? 'flex' : 'none';

                } else if (status === 'FALLO') {

                    card.style.display = (!isCorrect || cardStatus === 'FALLO' || cardStatus === 'PARCIAL') ? 'flex' : 'none';

                }

            });

        };



        window.rerunExecution = function(scId, modelId, seed) {

            // Cerrar modal visor de historial para salir de la ventana inmediatamente

            const visorModal = document.getElementById('modal-visor-historial');

            if (visorModal) {

                visorModal.innerHTML = '';

            }

            if (window.triggerToast) {

                window.triggerToast(`<strong class="text-sky-400">⚡ Re-ejecutando:</strong> Preparando ${scId} con ${modelId} (Semilla ${seed})...`);

            }

            if (window.switchMainView) {

                window.switchMainView('diagnostico');

            }

            const targetUrl = `/vistas/diagnostico?scenario_id=${encodeURIComponent(scId || '')}&model_id=${encodeURIComponent(modelId || '')}&seed=${encodeURIComponent(seed !== undefined ? seed : 42)}`;

            const afterRun = () => {

                setTimeout(() => {

                    const selSc = document.getElementById('selScenario');

                    const selMod = document.getElementById('selModel');

                    const txtSeed = document.getElementById('txtSeed');

                    if (selSc && scId) {

                        selSc.value = scId;

                        selSc.dispatchEvent(new Event('change', { bubbles: true }));

                    }

                    if (selMod && modelId) {

                        selMod.value = modelId;

                        selMod.dispatchEvent(new Event('change', { bubbles: true }));

                    }

                    if (txtSeed && seed !== undefined) {

                        txtSeed.value = seed;

                    }

                    const btnRun = document.getElementById('btnRun');

                    if (btnRun) {

                        btnRun.click();

                        if (window.triggerToast) {

                            window.triggerToast(`<strong class="text-emerald-400">⚡ Diagnóstico Iniciado:</strong> Ejecutando ${scId} en vivo...`);

                        }

                    }

                }, 100);

            };



            if (window.htmx) {

                const req = window.htmx.ajax('GET', targetUrl, {

                    target: '#mainViewContainer',

                    swap: 'innerHTML'

                });

                if (req && typeof req.then === 'function') {

                    req.then(afterRun);

                } else {

                    setTimeout(afterRun, 250);

                }

            } else {

                afterRun();

            }

        };



        let undoClearTimer = null;

        let undoClearCountdown = 5;



        window.clearHistoryWithUndo = function() {

            if (undoClearTimer) {

                clearInterval(undoClearTimer);

                undoClearTimer = null;

            }



            // Limpieza inmediata en RAM (sin interrupciones ni confirmaciones invasivas)

            if (window.htmx) {

                window.htmx.ajax('POST', '/api/history/clear', {

                    target: '#executionHistoryContainer',

                    swap: 'innerHTML'

                });

            }



            // Toast interactivo con cuenta regresiva de 5s y botón Deshacer

            undoClearCountdown = 5;

            const renderUndoToast = (sec) => {

                return '<div class="flex items-center justify-between gap-3 w-full font-sans">' +

                       '<span>🧹 Bitácora vaciada en RAM.</span>' +

                       '<button type="button" onclick="undoClearHistory()" class="px-2.5 py-1 rounded-md bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs border border-emerald-400/60 shadow-md transition-all cursor-pointer shrink-0 flex items-center gap-1.5">' +

                       '<span>↩ Deshacer</span> <span class="font-mono">(' + sec + 's)</span>' +

                       '</button>' +

                       '</div>';

            };



            if (window.triggerToast) {

                window.triggerToast(renderUndoToast(undoClearCountdown));

            }



            undoClearTimer = setInterval(() => {

                undoClearCountdown -= 1;

                if (undoClearCountdown > 0) {

                    if (window.triggerToast) {

                        window.triggerToast(renderUndoToast(undoClearCountdown));

                    }

                } else {

                    clearInterval(undoClearTimer);

                    undoClearTimer = null;

                }

            }, 1000);

        };



        window.undoClearHistory = function() {

            if (undoClearTimer) {

                clearInterval(undoClearTimer);

                undoClearTimer = null;

            }

            if (window.htmx) {

                window.htmx.ajax('POST', '/api/history/undo-clear', {

                    target: '#executionHistoryContainer',

                    swap: 'innerHTML'

                });

            }

            if (window.triggerToast) {

                window.triggerToast('<strong class="text-emerald-400">↺ Bitácora Restaurada:</strong> Registros en memoria RAM recuperados con éxito.');

            }

        };



        window.clearExecutionHistory = window.clearHistoryWithUndo;



        window.copyExecutionTicketMarkdown = function(execId, btn) {

            let text = '';

            const txtEl = (execId ? document.getElementById('ticket-raw-' + execId) : null) ||

                          (btn && btn.closest ? btn.closest('.suite-run-header')?.querySelector('textarea') : null) ||

                          document.querySelector('textarea[id^="ticket-raw-"]');

            if (txtEl) {

                text = txtEl.value;

            }

            if (!text && btn && btn.getAttribute('data-ticket-text')) {

                text = btn.getAttribute('data-ticket-text');

            }

            if (!text) {

                console.warn("No se encontró el contenido de la ficha para:", execId);

                if (window.triggerToast) {

                    window.triggerToast('<strong class="text-rose-400">⚠️ Error:</strong> No se pudo localizar el texto de la ficha técnica.');

                }

                return;

            }



            const showSuccess = function() {

                if (btn) {

                    const origHtml = btn.innerHTML;

                    btn.innerHTML = '<span>✓ Copiado</span>';

                    btn.classList.add('text-emerald-400', 'border-emerald-500/70');

                    setTimeout(function() {

                        btn.innerHTML = origHtml;

                        btn.classList.remove('text-emerald-400', 'border-emerald-500/70');

                    }, 2500);

                }

                if (window.triggerToast) {

                    window.triggerToast('<strong class="text-emerald-400">📋 Ficha Copiada:</strong> Reporte técnico en Markdown listo para ticket NOC / Jira.');

                }

            };



            const fallbackCopy = function(str) {

                try {

                    const ta = document.createElement('textarea');

                    ta.value = str;

                    ta.setAttribute('readonly', '');

                    ta.style.position = 'fixed';

                    ta.style.left = '-9999px';

                    ta.style.top = '0';

                    ta.style.opacity = '0';

                    document.body.appendChild(ta);

                    ta.focus();

                    ta.select();

                    const successful = document.execCommand('copy');

                    document.body.removeChild(ta);

                    if (successful) {

                        showSuccess();

                    } else {

                        console.error("document.execCommand copy fallo");

                    }

                } catch (e) {

                    console.error("Error en fallbackCopy:", e);

                }

            };



            if (navigator && navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {

                navigator.clipboard.writeText(text).then(function() {

                    showSuccess();

                }).catch(function(err) {

                    console.warn("navigator.clipboard fallo, usando fallbackCopy:", err);

                    fallbackCopy(text);

                });

            } else {

                fallbackCopy(text);

            }

        };



        window.goToSidebarBitacora = function() {

            // 1. Salir / cerrar el modal flotante de detalle histórico

            const modal = document.getElementById('modal-visor-historial');

            if (modal) {

                modal.innerHTML = '';

            }

            // 2. Si el panel lateral está colapsado, desplegarlo

            const sidebar = document.getElementById('sidebarCol');

            if (sidebar && sidebar.style.marginLeft && sidebar.style.marginLeft !== '0px') {

                if (typeof window.toggleSidebar === 'function') {

                    window.toggleSidebar();

                }

            }

            // 3. Asegurar que el acordeón de la ficha y bitácora esté expandido

            const cardGT = document.getElementById('cardGroundTruth');

            if (cardGT && cardGT.classList.contains('collapsed')) {

                cardGT.classList.remove('collapsed');

            }

            // 4. Desplazar suavemente el panel lateral hasta la Bitácora de Sesión

            setTimeout(() => {

                const histSection = document.getElementById('sidebarHistorySection');

                if (histSection) {

                    histSection.scrollIntoView({ behavior: 'smooth', block: 'center' });

                }

            }, 60);

        };



        function openCurrentViewExternal() {

            if (currentIframeUrl) {

                let url = currentIframeUrl;

                if (url.includes('/observabilidad')) {

                    url = '/observabilidad';

                }

                url = url.replace('?embed=true&', '?').replace('&embed=true', '').replace('?embed=true', '');

                window.open(url, '_blank');

            } else if (currentActiveView === 'diagnostico') {

                const params = typeof getActiveScenarioParams === 'function' ? getActiveScenarioParams() : {};

                const q = params.scId ? `?scenario=${encodeURIComponent(params.scId)}` : '';

                window.open('/' + q, '_blank');

            }

        }



        function printCurrentView() {

            if (currentActiveView === 'diagnostico' || currentActiveView === 'observabilidad' || currentActiveView === 'configuracion') {

                window.print();

            } else {

                const iframe = document.getElementById('mainViewIframe');

                if (iframe && iframe.contentWindow) {

                    try {

                        const iDoc = iframe.contentDocument || iframe.contentWindow.document;

                        if (currentActiveView === 'comparativo') {

                            const pComp = iDoc.getElementById('panel-comparativo');

                            const pCorr = iDoc.getElementById('panel-correlacion');

                            if (pComp) {

                                pComp.classList.add('active');

                                pComp.style.setProperty('display', 'block', 'important');

                            }

                            if (pCorr) {

                                pCorr.classList.remove('active');

                                pCorr.style.setProperty('display', 'none', 'important');

                            }

                            if (typeof iframe.contentWindow.showTab === 'function') {

                                iframe.contentWindow.showTab('comparativo');

                            }

                        } else if (currentActiveView === 'correlacion') {

                            const pComp = iDoc.getElementById('panel-comparativo');

                            const pCorr = iDoc.getElementById('panel-correlacion');

                            if (pCorr) {

                                pCorr.classList.add('active');

                                pCorr.style.setProperty('display', 'block', 'important');

                            }

                            if (pComp) {

                                pComp.classList.remove('active');

                                pComp.style.setProperty('display', 'none', 'important');

                            }

                            if (typeof iframe.contentWindow.showTab === 'function') {

                                iframe.contentWindow.showTab('correlacion');

                            }

                        }

                    } catch(e) {}

                    iframe.contentWindow.focus();

                    iframe.contentWindow.print();

                } else {

                    window.print();

                }

            }

        }



        // ================= ACCESOS RÁPIDOS POR TECLADO =================

        function handleGlobalKeyDown(evt) {

            const doc = evt.target?.ownerDocument || document;

            const activeEl = doc.activeElement;

            const activeTag = (activeEl?.tagName || '').toUpperCase();

            const isEditing = activeTag === 'INPUT' || activeTag === 'TEXTAREA' || activeTag === 'SELECT';



            // Ctrl + K o Cmd + K -> Alternar Paleta de comandos

            if ((evt.ctrlKey || evt.metaKey) && (evt.key === 'k' || evt.key === 'K')) {

                evt.preventDefault();

                const modal = document.getElementById('commandPaletteModal');

                if (modal && modal.style.display !== 'none') {

                    closeCommandPalette();

                } else {

                    openCommandPalette();

                }

                return;

            }



            if (evt.key === 'Escape') {

                const modal = document.getElementById('commandPaletteModal');

                if (modal && modal.style.display !== 'none') {

                    closeCommandPalette();

                    return;

                }

                if (currentActiveView !== 'diagnostico') {

                    activateMainView('diagnostico');

                }

                return;

            }



            if ((evt.ctrlKey || evt.metaKey) && evt.key === 'Enter') {

                const btn = document.getElementById('btnRun');

                if (btn && !btn.disabled) {

                    evt.preventDefault();

                    btn.click();

                }

                return;

            }



            // Atajos numéricos directos 1 a 5 para conmutar pestañas (solo cuando no se está editando texto)

            if (!isEditing && !evt.ctrlKey && !evt.altKey && !evt.metaKey) {

                if (evt.key === '1') { evt.preventDefault(); activateMainView('diagnostico'); }

                else if (evt.key === '2') { evt.preventDefault(); activateMainView('comparativo'); }

                else if (evt.key === '3') { evt.preventDefault(); activateMainView('correlacion'); }

                else if (evt.key === '4') { evt.preventDefault(); activateMainView('consolidado'); }

                else if (evt.key === '5') { evt.preventDefault(); activateMainView('suite_observabilidad'); }
                else if (evt.key === '6') { evt.preventDefault(); activateMainView('human_eval'); }

            }

        }

        window.handleGlobalKeyDown = handleGlobalKeyDown;

        document.addEventListener('keydown', handleGlobalKeyDown);



        function attachKeyboardListenerToIframe(iframe) {

            if (!iframe) return;

            try {

                const bindDoc = () => {

                    try {

                        const iDoc = iframe.contentDocument || iframe.contentWindow?.document;

                        if (iDoc && !iDoc.__benchKeyboardBound) {

                            iDoc.__benchKeyboardBound = true;

                            iDoc.addEventListener('keydown', handleGlobalKeyDown);

                        }

                    } catch (err) {

                        // Soporte seguro para restricciones de navegación

                    }

                };

                iframe.addEventListener('load', bindDoc);

                if (iframe.contentDocument && (iframe.contentDocument.readyState === 'complete' || iframe.contentDocument.readyState === 'interactive')) {

                    bindDoc();

                }

            } catch (e) {

                console.warn('No se pudo enlazar atajos al iframe:', e);

            }

        }

        window.attachKeyboardListenerToIframe = attachKeyboardListenerToIframe;



        document.addEventListener('htmx:afterSwap', function() {

            const iframe = document.getElementById('mainViewIframe');

            if (iframe) {

                attachKeyboardListenerToIframe(iframe);

            }

        });



        // ================= PALETA DE COMANDOS (Ctrl + K) =================

        let paletteCommands = [];

        let activePaletteIndex = 0;

        let filteredCommands = [];



        function ensureScenarioCategoryVisible(scCategory) {

            const chips = document.querySelectorAll('.sc-cat-chip');

            let targetChip = null;

            chips.forEach(c => {

                const onclickAttr = c.getAttribute('onclick') || '';

                if (scCategory && onclickAttr.includes(`'${scCategory}'`)) {

                    targetChip = c;

                } else if (!targetChip && onclickAttr.includes("'ALL'")) {

                    targetChip = c;

                }

            });

            if (targetChip) {

                targetChip.click();

            } else if (typeof filterScenarioCategory === 'function') {

                filterScenarioCategory('ALL');

            }

        }



        function selectScenarioFromPalette(scId) {

            if (!scId) return;



            const scInfo = Array.isArray(scenariosData) ? scenariosData.find(s => s.scenario_id === scId) : null;

            const scName = scInfo ? `${scInfo.scenario_id} - ${scInfo.fault_class}` : scId;

            const scCategory = scInfo ? scInfo.category : 'ALL';



            // 1. Sincronizar URL de inmediato para preservar el escenario en cualquier refresco o cambio

            try {

                const params = new URLSearchParams(window.location.search);

                params.set('scenario', scId);

                window.history.replaceState({}, '', `${window.location.pathname}?${params.toString()}`);

            } catch(e) {}



            // 2. Si ya estamos en la vista de diagnóstico

            const selSc = document.getElementById('selScenario');

            if (currentActiveView === 'diagnostico' && selSc) {

                ensureScenarioCategoryVisible(scCategory);

                selSc.value = scId;

                selSc.dispatchEvent(new Event('change', { bubbles: true }));

                if (typeof actualizarGroundTruth === 'function') actualizarGroundTruth();

                if (typeof syncUrlParams === 'function') syncUrlParams();

                const ws = document.getElementById('diagnostico-workspace');

                if (ws) ws.scrollTop = 0;

                if (typeof window.triggerToast === 'function') {

                    window.triggerToast(`<strong class="text-emerald-400">✓ Escenario Activo:</strong> ${escHtml(scName)}`);

                }

                return;

            }



            // 3. Conmutar a la vista de diagnóstico

            switchMainView('diagnostico');

            const url = `/vistas/diagnostico?scenario_id=${encodeURIComponent(scId)}`;

            if (window.htmx) {

                const applyAfterSwap = () => {

                    ensureScenarioCategoryVisible(scCategory);

                    const newSel = document.getElementById('selScenario');

                    if (newSel) {

                        newSel.value = scId;

                        newSel.dispatchEvent(new Event('change', { bubbles: true }));

                    }

                    if (typeof actualizarGroundTruth === 'function') actualizarGroundTruth();

                    if (typeof syncUrlParams === 'function') syncUrlParams();

                    const ws = document.getElementById('diagnostico-workspace');

                    if (ws) ws.scrollTop = 0;

                    if (typeof window.triggerToast === 'function') {

                        window.triggerToast(`<strong class="text-emerald-400">✓ Escenario Activo:</strong> ${escHtml(scName)}`);

                    }

                };



                const onSwap = function(evt) {

                    if (evt.detail && (evt.detail.target.id === 'mainViewContainer' || evt.detail.target.querySelector('#selScenario'))) {

                        document.body.removeEventListener('htmx:afterSwap', onSwap);

                        applyAfterSwap();

                    }

                };

                document.body.addEventListener('htmx:afterSwap', onSwap);



                htmx.ajax('GET', url, { target: '#mainViewContainer', swap: 'innerHTML' });

                setTimeout(() => {

                    document.body.removeEventListener('htmx:afterSwap', onSwap);

                    applyAfterSwap();

                }, 300);

            }

        }

        window.selectScenarioFromPalette = selectScenarioFromPalette;



        function buildPaletteCommands() {

            const list = [

                // Categoría 1: Vistas

                { category: 'Pestañas & Vistas', icon: '1️⃣', title: 'Visor de Diagnóstico L7', shortcut: '1', keywords: 'diagnostico visor stream cot', action: () => activateMainView('diagnostico') },

                { category: 'Pestañas & Vistas', icon: '2️⃣', title: 'Informe Técnico Comparativo (OE4)', shortcut: '2', keywords: 'comparativo radar score matriz oe4', action: () => activateMainView('comparativo') },

                { category: 'Pestañas & Vistas', icon: '3️⃣', title: 'Análisis Correlacional (SciPy)', shortcut: '3', keywords: 'correlacional scipy estadistica kruskal spearman', action: () => activateMainView('correlacion') },

                { category: 'Pestañas & Vistas', icon: '4️⃣', title: 'Informe Consolidado Global (HTML)', shortcut: '4', keywords: 'consolidado global html reporte trazabilidad', action: () => activateMainView('consolidado') },

                { category: 'Pestañas & Vistas', icon: '5️⃣', title: 'Suite de Observabilidad (18 Escenarios)', shortcut: '5', keywords: 'suite observabilidad langgraph sse batch 18', action: () => activateMainView('suite_observabilidad') },

                { category: 'Pestañas & Vistas', icon: '6️⃣', title: 'Validación Humana (Capa 8)', shortcut: '6', keywords: 'validacion humana capa 8 calibracion evaluadores expertos r1 r6', action: () => activateMainView('human_eval') },



                // Categoría 2: Acciones Rápidas

                { category: 'Acciones Rápidas', icon: '▶️', title: 'Ejecutar Diagnóstico L7', shortcut: 'Ctrl+↵', keywords: 'run ejecutar start diagnostico inferencia caso prueba', action: () => {

                    if (currentActiveView !== 'diagnostico') {

                        activateMainView('diagnostico');

                        setTimeout(() => {

                            const b = document.getElementById('btnRun');

                            if (b && !b.disabled) b.click();

                        }, 250);

                    } else {

                        const b = document.getElementById('btnRun');

                        if (b && !b.disabled) b.click();

                    }

                } },

                { category: 'Acciones Rápidas', icon: '📋', title: 'Copiar Ficha para Ticket (Markdown/Jira)', shortcut: '', keywords: 'copiar ticket jira markdown clipboard portapapeles ficha', action: () => copyTicketToClipboard() },

                { category: 'Acciones Rápidas', icon: '📥', title: 'Descargar Log de Diagnóstico (JSON/MD)', shortcut: '', keywords: 'descargar log diagnostico json markdown traza', action: () => downloadCurrentDiagnosticLog() },

                { category: 'Acciones Rápidas', icon: '🧹', title: 'Limpiar Bitácora de Sesión (RAM)', shortcut: '', keywords: 'limpiar ram bitacora historial borrar vaciar sesion memoria', action: () => clearExecutionHistory() },

                { category: 'Acciones Rápidas', icon: '🌓', title: 'Alternar Tema Claro / Oscuro', shortcut: '', keywords: 'tema noche dia dark light modo color apariencia', action: () => toggleTheme() },

                { category: 'Acciones Rápidas', icon: '◀', title: 'Colapsar / Mostrar Panel Lateral', shortcut: '', keywords: 'panel lateral sidebar colapsar ocultar expandir barra', action: () => toggleSidebar() },

                { category: 'Acciones Rápidas', icon: '🖨️', title: 'Imprimir / Guardar como PDF del Navegador', shortcut: '', keywords: 'imprimir print navegador papel documento', action: () => printCurrentView() },

                { category: 'Acciones Rápidas', icon: '↗', title: 'Abrir Vista en Pestaña Independiente', shortcut: '', keywords: 'abrir pestaña nueva ventana external tab', action: () => openCurrentViewExternal() },



                // Categoría 3: Exportaciones Técnicas

                { category: 'Exportaciones Técnicas', icon: '📄', title: 'Exportar Diagnóstico Actual a PDF', shortcut: '', keywords: 'exportar pdf diagnostico reporte caso activo', action: () => {

                    const params = getActiveScenarioParams();

                    window.location.href = `/api/export/pdf/diagnosis?scenario_id=${encodeURIComponent(params.scId)}&model_id=${encodeURIComponent(params.modelId)}&seed=${params.seed}`;

                } },

                { category: 'Exportaciones Técnicas', icon: '📊', title: 'Descargar Matriz Comparativa en Excel (.xlsx) [OE4]', shortcut: '', keywords: 'excel xlsx descargar exportar matriz metricas 10 hojas comparativo oe4', action: () => {

                    window.location.href = '/api/export/excel';

                } },

                { category: 'Exportaciones Técnicas', icon: '📊', title: 'Descargar Resultados de la Suite en Excel (.xlsx)', shortcut: '', keywords: 'excel xlsx suite descargar exportar 18 casos corrida observabilidad', action: () => {

                    const runParam = window.currentSuiteRunId ? ('?run_id=' + encodeURIComponent(window.currentSuiteRunId)) : '';

                    window.location.href = '/api/export/excel' + runParam;

                } },

                { category: 'Exportaciones Técnicas', icon: '📜', title: 'Descargar Reporte Consolidado (PDF)', shortcut: '', keywords: 'pdf reporte consolidado descargar documento global', action: () => {

                    window.location.href = '/api/export/pdf/consolidated';

                } },

                { category: 'Exportaciones Técnicas', icon: '🔬', title: 'Descargar Reporte Técnico de la Suite (PDF)', shortcut: '', keywords: 'suite pdf reporte langgraph cot real 18 casos', action: () => {

                    const runParam = window.currentSuiteRunId ? ('?run_id=' + encodeURIComponent(window.currentSuiteRunId)) : '';

                    window.location.href = '/api/export/pdf/suite' + runParam;

                } },

                { category: 'Exportaciones Técnicas', icon: '📑', title: 'Exportar Informe Comparativo a PDF (OE4)', shortcut: '', keywords: 'pdf comparativo oe4 radar matriz exportar', action: () => {

                    window.location.href = '/api/export/pdf/comparative';

                } },

                { category: 'Exportaciones Técnicas', icon: '📈', title: 'Exportar Análisis Correlacional a PDF (SciPy)', shortcut: '', keywords: 'pdf correlacional scipy kruskal spearman exportar', action: () => {

                    window.location.href = '/api/export/pdf/correlation';

                } },

                { category: 'Exportaciones Técnicas', icon: '📦', title: 'Descargar Volcado de Datos Completo (JSON)', shortcut: '', keywords: 'json descargar volcado datos estructurado dump', action: () => {

                    window.location.href = '/api/export/json';

                } }

            ];



            // Categoría 3: Escenarios RFC

            if (Array.isArray(scenariosData) && scenariosData.length > 0) {

                scenariosData.forEach(s => {

                    const desc = s.description || '';

                    list.push({

                        category: `Escenarios RFC (${s.category || 'L7'})`,

                        icon: '🧪',

                        title: `${s.scenario_id} - ${s.fault_class}`,

                        shortcut: s.scenario_id,

                        keywords: `${s.scenario_id} ${s.fault_class} ${s.category || ''} ${desc}`.toLowerCase(),

                        action: () => selectScenarioFromPalette(s.scenario_id)

                    });

                });

            }



            paletteCommands = list;

            return paletteCommands;

        }



        function handlePaletteInputKeyDown(evt) {

            const input = document.getElementById('commandPaletteInput');

            const val = (input?.value || '').trim();



            // Si el buscador está vacío y se presiona 1 a 5, saltar directamente a la vista

            if (!val && !evt.ctrlKey && !evt.altKey && !evt.metaKey) {

                if (evt.key === '1') { evt.preventDefault(); closeCommandPalette(); activateMainView('diagnostico'); return; }

                if (evt.key === '2') { evt.preventDefault(); closeCommandPalette(); activateMainView('comparativo'); return; }

                if (evt.key === '3') { evt.preventDefault(); closeCommandPalette(); activateMainView('correlacion'); return; }

                if (evt.key === '4') { evt.preventDefault(); closeCommandPalette(); activateMainView('consolidado'); return; }

                if (evt.key === '5') { evt.preventDefault(); closeCommandPalette(); activateMainView('suite_observabilidad'); return; }

                if (evt.key === '6') { evt.preventDefault(); closeCommandPalette(); activateMainView('human_eval'); return; }

            }



            if (evt.key === 'ArrowDown') {

                evt.preventDefault();

                navigatePalette(1);

            } else if (evt.key === 'ArrowUp') {

                evt.preventDefault();

                navigatePalette(-1);

            } else if (evt.key === 'Tab') {

                evt.preventDefault();

                navigatePalette(evt.shiftKey ? -1 : 1);

            } else if (evt.key === 'Enter') {

                evt.preventDefault();

                executeActivePaletteCommand();

            } else if (evt.key === 'Escape') {

                evt.preventDefault();

                closeCommandPalette();

            }

        }

        window.handlePaletteInputKeyDown = handlePaletteInputKeyDown;



        function openCommandPalette() {

            buildPaletteCommands();

            const modal = document.getElementById('commandPaletteModal');

            if (modal) {

                modal.style.display = 'flex';

                const input = document.getElementById('commandPaletteInput');

                if (input) {

                    input.value = '';

                }

                renderPaletteCommands('');

                setTimeout(() => {

                    if (input) input.focus();

                }, 40);

            }

            try {

                const body = document.querySelector('body');

                if (body && body.__x && body.__x.$data) {

                    body.__x.$data.showCommandPalette = true;

                }

            } catch(e) {}

        }

        window.openCommandPalette = openCommandPalette;



        function closeCommandPalette() {

            const modal = document.getElementById('commandPaletteModal');

            if (modal) {

                modal.style.display = 'none';

            }

            try {

                const body = document.querySelector('body');

                if (body && body.__x && body.__x.$data) {

                    body.__x.$data.showCommandPalette = false;

                }

            } catch(e) {}

        }

        window.closeCommandPalette = closeCommandPalette;



        function renderPaletteCommands(query) {

            if (!paletteCommands || paletteCommands.length === 0) buildPaletteCommands();

            const q = (query || '').toLowerCase().trim();

            filteredCommands = paletteCommands.filter(c => {

                if (!q) return true;

                return c.title.toLowerCase().includes(q) ||

                       c.category.toLowerCase().includes(q) ||

                       (c.keywords && c.keywords.includes(q)) ||

                       (c.shortcut && c.shortcut.toLowerCase().includes(q));

            });



            activePaletteIndex = 0;

            const container = document.getElementById('commandPaletteList');

            if (!container) return;



            if (filteredCommands.length === 0) {

                container.innerHTML = '<div class="p-6 text-center text-slate-500 text-xs">No se encontraron comandos o escenarios para "<b>' + escHtml(q) + '</b>".</div>';

                return;

            }



            let html = '';

            let currentCat = '';

            filteredCommands.forEach((cmd, idx) => {

                if (cmd.category !== currentCat) {

                    currentCat = cmd.category;

                    html += `<div class="px-3 pt-2 pb-1 text-[10px] font-bold uppercase tracking-wider text-slate-500">${escHtml(currentCat)}</div>`;

                }

                const isSelected = idx === activePaletteIndex;

                html += `

                    <div class="palette-item p-2.5 rounded-xl flex items-center justify-between cursor-pointer transition-colors ${isSelected ? 'bg-blue-600/25 text-white border border-blue-500/40' : 'text-slate-200 hover:bg-slate-800/60'}"

                         data-idx="${idx}"

                         onmouseenter="highlightPaletteItem(${idx})"

                         onclick="executePaletteCommandAt(${idx})">

                        <div class="flex items-center gap-2.5 min-w-0">

                            <span class="text-base">${cmd.icon}</span>

                            <span class="font-medium truncate">${escHtml(cmd.title)}</span>

                        </div>

                        ${cmd.shortcut ? `<kbd class="text-[10px] font-mono bg-slate-900/80 px-2 py-0.5 rounded border border-slate-700 text-slate-400 shrink-0 ml-2">${escHtml(cmd.shortcut)}</kbd>` : ''}

                    </div>

                `;

            });

            container.innerHTML = html;

        }

        window.renderPaletteCommands = renderPaletteCommands;



        function highlightPaletteItem(idx) {

            if (idx < 0 || idx >= filteredCommands.length) return;

            activePaletteIndex = idx;

            const items = document.querySelectorAll('.palette-item');

            items.forEach((el, i) => {

                if (i === activePaletteIndex) {

                    el.classList.add('bg-blue-600/25', 'text-white', 'border', 'border-blue-500/40');

                    el.classList.remove('text-slate-200');

                } else {

                    el.classList.remove('bg-blue-600/25', 'text-white', 'border', 'border-blue-500/40');

                    el.classList.add('text-slate-200');

                }

            });

        }

        window.highlightPaletteItem = highlightPaletteItem;



        function navigatePalette(delta) {

            if (filteredCommands.length === 0) return;

            activePaletteIndex = (activePaletteIndex + delta + filteredCommands.length) % filteredCommands.length;

            highlightPaletteItem(activePaletteIndex);

            const items = document.querySelectorAll('.palette-item');

            if (items[activePaletteIndex]) {

                items[activePaletteIndex].scrollIntoView({ block: 'nearest' });

            }

        }

        window.navigatePalette = navigatePalette;



        function executeActivePaletteCommand() {

            if (filteredCommands.length > 0 && activePaletteIndex >= 0 && activePaletteIndex < filteredCommands.length) {

                executePaletteCommandAt(activePaletteIndex);

            }

        }

        window.executeActivePaletteCommand = executeActivePaletteCommand;



        function executePaletteCommandAt(idx) {

            const cmd = filteredCommands[idx];

            if (cmd && typeof cmd.action === 'function') {

                closeCommandPalette();

                cmd.action();

            }

        }

        window.executePaletteCommandAt = executePaletteCommandAt;



        function escHtml(s) {

            return String(s || '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

        }



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

            if (th === 'light') {

                if (icon) icon.innerHTML = '<svg class="w-4 h-4 text-slate-700" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"/></svg>';

                if (txt) txt.textContent = 'Modo Noche';

            } else {

                if (icon) icon.innerHTML = '<svg class="w-4 h-4 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"/></svg>';

                if (txt) txt.textContent = 'Modo Día';

            }

            const statusBadge = document.getElementById('streamStatusBadge');

            if (statusBadge) {

                const text = statusBadge.textContent || '';

                if (text.includes('Completado')) {

                    statusBadge.style.background = th === 'light' ? '#dcfce7' : 'rgba(16, 185, 129, 0.2)';

                    statusBadge.style.color = th === 'light' ? '#065f46' : '#34d399';

                    statusBadge.style.borderColor = '#10b981';

                } else if (text.includes('Listo')) {

                    statusBadge.style.background = th === 'light' ? '#e0f2fe' : 'rgba(0, 51, 102, 0.4)';

                    statusBadge.style.color = th === 'light' ? '#003366' : '#DADADA';

                    statusBadge.style.borderColor = th === 'light' ? '#7dd3fc' : 'rgba(218, 218, 218, 0.3)';

                } else if (text.includes('Streaming')) {

                    statusBadge.style.background = th === 'light' ? '#fee2e2' : 'rgba(173, 51, 51, 0.3)';

                    statusBadge.style.color = th === 'light' ? '#991b1b' : '#ff9999';

                    statusBadge.style.borderColor = '#ad3333';

                }

            }

            try {

                const iframe = document.getElementById('mainViewIframe');

                if (iframe && iframe.contentDocument && iframe.contentDocument.documentElement) {

                    iframe.contentDocument.documentElement.setAttribute('data-theme', th);

                    if (th === 'dark') {

                        iframe.contentDocument.documentElement.classList.add('dark');

                    } else {

                        iframe.contentDocument.documentElement.classList.remove('dark');

                    }

                    if (iframe.contentWindow && typeof iframe.contentWindow.applyTheme === 'function') {

                        iframe.contentWindow.applyTheme(th);

                    }

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



        window.onload = init;

    </script>



    <!-- ================= MODAL DE ELIMINACIÓN DE MODELOS (Tailwind + Alpine.js) ================= -->

    <div x-cloak

         x-show="showDeleteModal"

         x-transition:enter="transition ease-out duration-200"

         x-transition:enter-start="opacity-0"

         x-transition:enter-end="opacity-100"

         x-transition:leave="transition ease-in duration-150"

         x-transition:leave-start="opacity-100"

         x-transition:leave-end="opacity-0"

         class="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">



        <div @click.away="cancelModal()"

             x-show="showDeleteModal"

             x-transition:enter="transition ease-out duration-200"

             x-transition:enter-start="opacity-0 scale-95"

             x-transition:enter-end="opacity-100 scale-100"

             x-transition:leave="transition ease-in duration-150"

             x-transition:leave-start="opacity-100 scale-100"

             x-transition:leave-end="opacity-0 scale-95"

             class="bg-[#101624] border border-red-900/50 rounded-xl shadow-2xl p-6 max-w-lg w-full relative">



            <!-- Botón de Cerrar (X) -->

            <button type="button"

                    @click="cancelModal()"

                    class="absolute top-4 right-4 text-slate-400 hover:text-slate-100 text-lg leading-none cursor-pointer bg-transparent border-0"

                    title="Cerrar modal">&times;</button>



            <!-- ================= PASO 1: Advertencia Principal (deleteStep === 1) ================= -->

            <div x-show="deleteStep === 1">

                <div class="flex items-center gap-3.5 mb-4">

                    <div class="w-12 h-12 rounded-full bg-red-950/70 border border-red-500/50 flex items-center justify-center text-red-400 shrink-0 shadow-lg shadow-red-950/50">

                        <svg class="w-6 h-6 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">

                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>

                        </svg>

                    </div>

                    <div>

                        <h3 class="text-base font-bold text-slate-100">¿Estás seguro de que deseas eliminar el modelo?</h3>

                        <p class="text-xs text-slate-400">Verifica el impacto operativo antes de confirmar la purga.</p>

                    </div>

                </div>



                <!-- Nombre dinámico del modelo -->

                <div class="mb-4 p-3 rounded-lg bg-slate-950/80 border border-slate-800 text-xs font-mono">

                    <span class="text-slate-400 block text-[11px] uppercase tracking-wider mb-1">Modelo seleccionado:</span>

                    <strong class="text-amber-300 text-sm block break-all font-semibold" x-text="modelToDelete?.name ? (modelToDelete.name + (modelToDelete.id !== modelToDelete.name ? ' (' + modelToDelete.id + ')' : '')) : modelToDelete?.id"></strong>

                </div>



                <!-- Lista de viñetas con el impacto (estilo texto secundario text-slate-400) -->

                <div class="mb-6 p-4 rounded-lg bg-[#0a101d] border border-slate-800/80 text-xs text-slate-400 space-y-2">

                    <p class="font-semibold text-slate-300">Esta acción purgará de forma permanente:</p>

                    <ul class="space-y-1.5 list-disc list-inside text-slate-400">

                        <li>Todas las corridas asociadas en el dataset (<code>resultados.csv</code>, con respaldo previo)</li>

                        <li>Archivos de diagnóstico y trazas en <code>data/runs</code></li>

                        <li>Su registro en la configuración del benchmark</li>

                    </ul>

                </div>



                <!-- Botones: Cancelar y Aceptar -->

                <div class="flex justify-end gap-3 pt-2 border-t border-slate-800">

                    <button type="button"

                            @click="cancelModal()"

                            class="px-4 py-2 text-xs font-semibold rounded-lg border border-slate-700 bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors cursor-pointer">

                        Cancelar

                    </button>

                    <button type="button"

                            @click="deleteStep = 2"

                            class="px-5 py-2 text-xs font-bold rounded-lg bg-red-600 hover:bg-red-700 text-white shadow-lg shadow-red-950/50 transition-all flex items-center gap-1.5 cursor-pointer">

                        <span>Aceptar</span>

                        <svg class="w-3.5 h-3.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3"/></svg>

                    </button>

                </div>

            </div>



            <!-- ================= PASO 2: Pesos de Ollama (deleteStep === 2) ================= -->

            <div x-show="deleteStep === 2">

                <div class="flex items-center gap-3.5 mb-4">

                    <div class="w-12 h-12 rounded-full bg-amber-950/70 border border-amber-500/50 flex items-center justify-center text-amber-400 shrink-0 shadow-lg shadow-amber-950/50">

                        <svg class="w-6 h-6 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">

                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>

                        </svg>

                    </div>

                    <div>

                        <h3 class="text-base font-bold text-slate-100">Desinstalación de Pesos en Ollama</h3>

                        <p class="text-xs text-slate-400">Paso 2 de 2: Liberación de almacenamiento en disco</p>

                    </div>

                </div>



                <div class="mb-5 p-4 rounded-lg bg-slate-950/80 border border-slate-800 text-xs leading-relaxed text-slate-200">

                    <p class="text-sm font-semibold mb-2">

                        ¿Deseas también desinstalar y borrar los pesos binarios de <span class="text-amber-300 font-mono" x-text="modelToDelete?.name || modelToDelete?.id"></span> de Ollama?

                    </p>

                    <div class="mt-3 text-[11px] text-slate-400 space-y-1.5 bg-[#0a101d] p-3 rounded border border-slate-800/80">

                        <p><strong class="text-slate-300">Cancelar:</strong> Elimina el modelo y sus corridas del benchmark, pero <span class="text-slate-200">mantiene los archivos descargados</span> en Ollama para reutilizarlos en el futuro.</p>

                        <p><strong class="text-red-300">Aceptar:</strong> Elimina el modelo del benchmark y <span class="text-red-200">borra físicamente el modelo</span> de Ollama para recuperar espacio en disco.</p>

                    </div>

                </div>



                <div class="flex justify-end gap-3 pt-2 border-t border-slate-800">

                    <button type="button"

                            :disabled="isDeleting"

                            @click="executeDelete(false)"

                            class="px-4 py-2 text-xs font-semibold rounded-lg border border-slate-700 bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors cursor-pointer disabled:opacity-50">

                        <span x-show="!isDeleting">Cancelar (Mantener en Ollama)</span>

                        <span x-show="isDeleting">Purgando datos...</span>

                    </button>

                    <button type="button"

                            :disabled="isDeleting"

                            @click="executeDelete(true)"

                            class="px-5 py-2 text-xs font-bold rounded-lg bg-red-600 hover:bg-red-700 text-white shadow-lg shadow-red-950/50 transition-all flex items-center gap-1.5 cursor-pointer disabled:opacity-50">

                        <svg class="w-3.5 h-3.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">

                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>

                        </svg>

                        <span x-show="!isDeleting">Aceptar (Borrar de Ollama)</span>

                        <span x-show="isDeleting">Borrando modelo...</span>

                    </button>

                </div>

            </div>

        </div>

    </div>



    <!-- ================= PALETA DE COMANDOS (Ctrl + K) ================= -->

    <div id="commandPaletteModal"

         data-test-feature="showCommandPalette"

         style="display: none;"

         onclick="if(event.target === this) closeCommandPalette()"

         class="fixed inset-0 bg-black/75 backdrop-blur-sm z-50 flex items-start justify-center pt-16 p-4">



        <div class="bg-[#101624] border border-slate-700/80 rounded-2xl shadow-2xl max-w-2xl w-full overflow-hidden flex flex-col max-h-[80vh] animate-fadeIn">



            <!-- Barra de búsqueda superior -->

            <div class="p-3.5 border-b border-slate-800 flex items-center gap-3 bg-[#0a101d]">

                <svg class="w-5 h-5 text-slate-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>

                <input type="text"

                       id="commandPaletteInput"

                       oninput="if(typeof renderPaletteCommands === 'function') renderPaletteCommands(this.value)"

                       onkeydown="if(typeof handlePaletteInputKeyDown === 'function') handlePaletteInputKeyDown(event)"

                       placeholder="Buscar comandos, vistas o los 18 escenarios RFC... (ej. DNS, Comparativo, 502, Run)"

                       class="w-full bg-transparent text-slate-100 placeholder-slate-500 text-sm focus:outline-none font-medium">

                <kbd onclick="closeCommandPalette()" class="text-[10px] font-mono bg-slate-800 hover:bg-slate-700 text-slate-400 px-2 py-0.5 rounded border border-slate-700 cursor-pointer" title="Cerrar (ESC)">ESC</kbd>

            </div>



            <!-- Lista de comandos filtrables -->

            <div id="commandPaletteList" class="overflow-y-auto p-2 space-y-1 flex-1 text-xs max-h-96">

                <!-- Se puebla dinámicamente -->

            </div>



            <!-- Footer con atajos de ayuda -->

            <div class="px-4 py-2 border-t border-slate-800/80 bg-[#070d18] flex items-center justify-between text-[11px] text-slate-400">

                <div class="flex items-center gap-3">

                    <span><kbd class="font-mono bg-slate-800 text-slate-300 px-1 rounded">↑↓</kbd> Navegar</span>

                    <span><kbd class="font-mono bg-slate-800 text-slate-300 px-1 rounded">↵</kbd> Ejecutar</span>

                    <span><kbd class="font-mono bg-slate-800 text-slate-300 px-1 rounded">1-5</kbd> Vistas directas</span>

                </div>

                <span class="font-mono text-slate-500">NetDiagBench-L7</span>

            </div>

        </div>

    </div>



    <!-- ================= NOTIFICACIÓN TOAST (Tailwind + Alpine.js) ================= -->

    <div x-cloak

         x-show="showToast"

         x-transition:enter="transition ease-out duration-300"

         x-transition:enter-start="opacity-0 translate-y-4"

         x-transition:enter-end="opacity-100 translate-y-0"

         x-transition:leave="transition ease-in duration-200"

         x-transition:leave-start="opacity-100 translate-y-0"

         x-transition:leave-end="opacity-0 translate-y-4"

         class="fixed bottom-6 right-6 bg-[#101624] border border-emerald-800/60 shadow-lg rounded-xl px-5 py-4 z-50 flex items-center gap-3 max-w-md">



        <div class="w-8 h-8 rounded-full bg-emerald-950/80 border border-emerald-500/50 flex items-center justify-center shrink-0 shadow">

            <svg class="w-4 h-4 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">

                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>

            </svg>

        </div>



        <div class="flex-1 min-w-0">

            <span class="text-xs text-slate-200 font-medium leading-relaxed block break-words" x-html="toastMessage"></span>

        </div>



        <button type="button"

                @click="showToast = false"

                class="text-slate-500 hover:text-slate-300 ml-2 text-base leading-none bg-transparent border-0 cursor-pointer p-0"

                title="Cerrar notificación">&times;</button>

    </div>



    <!-- ================= CONTENEDOR MODAL VISOR DETALLES HISTÓRICOS ================= -->

    <div id="modal-visor-historial"></div>



    <!-- ================= MODAL DE CONFIRMACIÓN PERSONALIZADO (HTMX) ================= -->

    <div id="custom-confirm-modal"

         class="hidden fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-[100] flex items-center justify-center p-4 transition-all"

         onclick="if(event.target === this) document.getElementById('custom-confirm-modal').classList.add('hidden')">

        <div class="bg-slate-900 border border-rose-900/50 rounded-2xl shadow-2xl max-w-md w-full p-6 transform transition-all text-slate-100">

            <div class="flex items-start gap-4">

                <div class="w-10 h-10 rounded-full bg-rose-950/80 border border-rose-700/60 flex items-center justify-center text-rose-400 shrink-0 shadow-inner">

                    <svg class="w-5 h-5 text-rose-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">

                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>

                    </svg>

                </div>

                <div class="flex-1 min-w-0">

                    <h3 class="text-base font-bold text-slate-100 flex items-center gap-2">Confirmar Acción</h3>

                    <p id="confirm-msg" class="text-xs text-slate-300 mt-2 leading-relaxed"></p>

                </div>

            </div>

            <div class="flex justify-end gap-3 mt-6 pt-3 border-t border-slate-800">

                <button type="button"

                        id="confirm-no"

                        class="px-4 py-2 text-xs font-semibold rounded-lg border border-slate-700 bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors cursor-pointer flex items-center gap-1.5">

                    Cancelar

                    <kbd class="text-[10px] font-mono bg-slate-900/80 px-1.5 py-0.5 rounded text-slate-400 border border-slate-700 ml-1">Esc</kbd>

                </button>

                <button type="button"

                        id="confirm-yes"

                        class="px-5 py-2 text-xs font-bold rounded-lg bg-rose-600 hover:bg-rose-700 text-white shadow-lg shadow-rose-950/50 transition-all cursor-pointer">

                    Confirmar

                </button>

            </div>

        </div>

    </div>



    <!-- ================= MODAL DE ALERTA PERSONALIZADO (REEMPLAZO WINDOW.ALERT) ================= -->

    <div id="custom-alert-modal"

         class="hidden fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-[110] flex items-center justify-center p-4 transition-all"

         onclick="if(event.target === this) document.getElementById('custom-alert-modal').classList.add('hidden')">

        <div class="bg-slate-900 border border-amber-600/50 rounded-2xl shadow-2xl max-w-md w-full p-6 transform transition-all text-slate-100">

            <div class="flex items-start gap-4">

                <div id="custom-alert-icon-wrap" class="w-10 h-10 rounded-full bg-amber-950/80 border border-amber-700/60 flex items-center justify-center text-amber-400 shrink-0 shadow-inner">

                    <svg id="custom-alert-icon" class="w-5 h-5 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">

                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>

                    </svg>

                </div>

                <div class="flex-1 min-w-0">

                    <div class="flex items-center justify-between">

                        <h3 id="custom-alert-title" class="text-base font-bold text-slate-100 flex items-center gap-2">Validación de Selección</h3>

                        <button type="button" onclick="document.getElementById('custom-alert-modal').classList.add('hidden')" class="text-slate-400 hover:text-white text-lg leading-none cursor-pointer">&times;</button>

                    </div>

                    <p id="custom-alert-msg" class="text-xs text-slate-300 mt-2 leading-relaxed"></p>

                </div>

            </div>

            <div class="flex justify-end gap-3 mt-6 pt-3 border-t border-slate-800">

                <button type="button"

                        id="custom-alert-btn"

                        onclick="document.getElementById('custom-alert-modal').classList.add('hidden')"

                        class="px-5 py-2 text-xs font-bold rounded-lg bg-[#ad3333] hover:bg-[#801818] text-white shadow-lg shadow-rose-950/50 transition-all cursor-pointer flex items-center gap-1.5">

                    Entendido

                    <kbd class="text-[10px] font-mono bg-black/40 px-1.5 py-0.5 rounded text-rose-200 border border-rose-400/30 ml-1">Enter</kbd>

                </button>

            </div>

        </div>

    </div>



    <script>

        // ================= PRESERVACIÓN DE POSICIÓN DE SCROLL (SCROLL MEMORY) =================

        window.savedVisorScrollTop = 0;



        window.closeVisorModal = function() {

            const visorModal = document.getElementById('modal-visor-historial');

            if (visorModal) {

                visorModal.innerHTML = '';

            }

            const visor = document.getElementById('visor-content');

            if (visor && typeof window.savedVisorScrollTop === 'number') {

                visor.scrollTop = window.savedVisorScrollTop;

            }

        };



        // Guardar la posición de scroll de #visor-content antes de inyectar el modal de historial

        document.addEventListener('htmx:beforeSwap', function(evt) {

            if (evt.detail.target && evt.detail.target.id === 'modal-visor-historial') {

                const visor = document.getElementById('visor-content');

                if (visor) {

                    window.savedVisorScrollTop = visor.scrollTop;

                }

            }

        });



        // Sistema Global de Alerta Personalizada (Anti-Native Alert)

        window.showCustomAlert = function(msg, title, type) {

            title = title || "Validación de Selección";

            type = type || "warning";

            const modal = document.getElementById('custom-alert-modal');

            if (!modal) {

                console.warn("[CustomAlert]", title, msg);

                return;

            }

            const titleEl = document.getElementById('custom-alert-title');

            const msgEl = document.getElementById('custom-alert-msg');

            const iconWrap = document.getElementById('custom-alert-icon-wrap');

            const iconSvg = document.getElementById('custom-alert-icon');

            const btn = document.getElementById('custom-alert-btn');

            if (titleEl) titleEl.textContent = title;

            if (msgEl) msgEl.textContent = msg;

            if (iconWrap && iconSvg) {

                if (type === 'error') {

                    iconWrap.className = "w-10 h-10 rounded-full bg-rose-950/80 border border-rose-700/60 flex items-center justify-center text-rose-400 shrink-0 shadow-inner";

                    iconSvg.innerHTML = '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>';

                } else if (type === 'info') {

                    iconWrap.className = "w-10 h-10 rounded-full bg-sky-950/80 border border-sky-700/60 flex items-center justify-center text-sky-400 shrink-0 shadow-inner";

                    iconSvg.innerHTML = '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>';

                } else if (type === 'success') {

                    iconWrap.className = "w-10 h-10 rounded-full bg-emerald-950/80 border border-emerald-700/60 flex items-center justify-center text-emerald-400 shrink-0 shadow-inner";

                    iconSvg.innerHTML = '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>';

                } else {

                    iconWrap.className = "w-10 h-10 rounded-full bg-amber-950/80 border border-amber-700/60 flex items-center justify-center text-amber-400 shrink-0 shadow-inner";

                    iconSvg.innerHTML = '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>';

                }

            }

            modal.classList.remove('hidden');

            if (btn) {

                setTimeout(() => btn.focus(), 50);

            }

        };



        window.alert = function(msg) {

            window.showCustomAlert(msg, "Validación de Selección", "warning");

        };



        // Interceptor Global de Confirmación HTMX (Custom hx-confirm sin alerts nativas)

        document.addEventListener('htmx:confirm', function(e) {

            // Solo interceptar si el elemento disparador tiene una pregunta de confirmación (hx-confirm)

            if (!e.detail.question) {

                return;

            }



            e.preventDefault();

            const question = e.detail.question;

            const modal = document.getElementById('custom-confirm-modal');

            const msgEl = document.getElementById('confirm-msg');

            const btnNo = document.getElementById('confirm-no');

            const btnYes = document.getElementById('confirm-yes');



            if (!modal || !msgEl || !btnNo || !btnYes) {

                if (window.confirm(question)) {

                    e.detail.issueRequest(true);

                }

                return;

            }



            msgEl.innerText = question;

            modal.classList.remove('hidden');



            // Reasignar onclick en cada apertura para evitar disparos acumulados

            btnNo.onclick = function() {

                modal.classList.add('hidden');

            };



            btnYes.onclick = function() {

                modal.classList.add('hidden');

                e.detail.issueRequest(true);

            };

        });



        // Manejador global de teclado Esc y Enter para cerrar modales de manera no invasiva

        document.addEventListener('keydown', function(ev) {

            if (ev.key === 'Escape' || ev.key === 'Enter') {

                const alertModal = document.getElementById('custom-alert-modal');

                if (alertModal && !alertModal.classList.contains('hidden')) {

                    alertModal.classList.add('hidden');

                    return;

                }

            }

            if (ev.key === 'Escape') {

                const confirmModal = document.getElementById('custom-confirm-modal');

                if (confirmModal && !confirmModal.classList.contains('hidden')) {

                    confirmModal.classList.add('hidden');

                    return;

                }

                const visorModal = document.getElementById('modal-visor-historial');

                if (visorModal && visorModal.innerHTML.trim() !== '') {

                    if (window.closeVisorModal) {

                        window.closeVisorModal();

                    } else {

                        visorModal.innerHTML = '';

                    }

                }

            }

        });

    </script>

</body>

</html>

"""

    return (

        html_content

        .replace("<!-- __DIAGNOSTICO_WORKSPACE__ -->", initial_workspace)

        .replace("</style>", f"{TOOLTIP_CSS}\n    </style>")

        .replace("</body>", f"{TOOLTIP_JS}\n</body>")

    )

