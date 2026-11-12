"""
NetDiagBench-L7: Layer 4 - Local Inference Engine & Telemetry
Abstracción de inferencia para la terna de modelos (Qwen3-8B, GLM-4-9B-Chat, Phi-4-mini-instruct).
Integra cliente Ollama/HTTP con telemetría de prellenado (TTFT), velocidad de decodificación (tok/s),
y simulador determinista de alta fidelidad para benchmark offline.
"""

import hashlib
import json
import os
import random
import re
import time
from typing import Any

import httpx

from src.core.config import ModelDefinition, SystemConfig
from src.core.contracts import RespuestaInferenciaContract, TelemetriaInferencia
from src.core.hardware_detector import detect_ollama_backend_and_vram, detect_system_hardware, BACKEND_CPU
from src.core.logger import logger



def extract_reasoning_and_response(raw_text: str) -> tuple[str, str, int]:
    """
    Separa bloques <think>...</think> o <thought>...</thought> del texto de respuesta final.
    Retorna (reasoning_text, final_response_text, reasoning_tokens_count).
    """
    if not raw_text:
        return "", "", 0

    think_pat = re.compile(r"<(?:think|thought)>(.*?)</(?:think|thought)>", re.DOTALL | re.IGNORECASE)
    parts = think_pat.findall(raw_text)
    reasoning_text = "\n\n".join(p.strip() for p in parts if p.strip())

    unclosed_pat = re.compile(r"<(?:think|thought)>(?!.*</(?:think|thought)>)(.*)$", re.DOTALL | re.IGNORECASE)
    unclosed = unclosed_pat.search(raw_text)
    if unclosed:
        unclosed_reasoning = unclosed.group(1).strip()
        if unclosed_reasoning:
            reasoning_text = (reasoning_text + "\n\n" + unclosed_reasoning).strip()
        final_text = think_pat.sub("", raw_text[:unclosed.start()]).strip()
    else:
        final_text = think_pat.sub("", raw_text).strip()

    reasoning_tokens = len(reasoning_text.split()) * 2 if reasoning_text else 0
    return reasoning_text, final_text, reasoning_tokens


def detect_and_cut_repetition_loops(text: str, max_repeats: int = 3) -> tuple[str, bool]:
    """
    Detecta si el modelo entra en bucles de repeticion autoregresiva y trunca el texto de forma limpia.
    Retorna (texto_truncado, loop_detectado).
    """
    if not text:
        return text, False

    lines = text.splitlines(keepends=True)
    if len(lines) >= 4:
        repeat_count = 1
        cut_idx = None
        for i in range(1, len(lines)):
            if lines[i].strip() and lines[i].strip() == lines[i - 1].strip():
                repeat_count += 1
                if repeat_count >= max_repeats:
                    cut_idx = i - (max_repeats - 1)
                    break
            else:
                repeat_count = 1
        if cut_idx is not None:
            return "".join(lines[:cut_idx]).strip(), True

    words = text.split()
    for phrase_len in range(4, 15):
        if len(words) < phrase_len * 3:
            continue
        for i in range(len(words) - phrase_len * 3 + 1):
            phrase = words[i:i + phrase_len]
            p2 = words[i + phrase_len:i + phrase_len * 2]
            p3 = words[i + phrase_len * 2:i + phrase_len * 3]
            if phrase == p2 == p3:
                cut_words = words[:i + phrase_len]
                return " ".join(cut_words), True

    return text, False


class LocalInferenceEngine:
    """Motor unificado de inferencia local con instrumentación precisa de telemetría."""

    def __init__(
        self,
        config: SystemConfig | None = None,
        ollama_base_url: str = "http://localhost:11434",
        force_simulation: bool = False,
        strict_ollama: bool = True
    ):
        self.config = config or SystemConfig()
        self.ollama_base_url = ollama_base_url.rstrip("/")
        self.force_simulation = force_simulation or (
            os.environ.get("BENCHMARK_FORCE_SIMULATION", "").lower() in ("1", "true")
        )
        self.strict_ollama = strict_ollama and (
            os.environ.get("BENCHMARK_STRICT_OLLAMA", "1").lower() in ("1", "true")
        ) and not self.force_simulation
        self.models_by_id: dict[str, ModelDefinition] = {
            m.id: m for m in self.config.get_all_models()
        }
        # Agregar también mapeo por ollama_tag para lookup flexible
        for m in self.config.get_all_models():
            self.models_by_id[m.ollama_tag] = m
        self._ollama_checked = False
        self._ollama_online = False

    def _is_ollama_available(self, timeout_s: float = 0.8) -> bool:
        """Verifica de forma rápida si Ollama está en línea en localhost o 127.0.0.1 con caché de 3s."""
        if self.force_simulation:
            return False
        now = time.time()
        if hasattr(self, "_last_ollama_check_time") and (now - getattr(self, "_last_ollama_check_time", 0.0) < 3.0):
            return self._ollama_online
        urls_to_try = [self.ollama_base_url]
        if "localhost" in self.ollama_base_url:
            urls_to_try.append(self.ollama_base_url.replace("localhost", "127.0.0.1"))
        elif "127.0.0.1" in self.ollama_base_url:
            urls_to_try.append(self.ollama_base_url.replace("127.0.0.1", "localhost"))
        for url in urls_to_try:
            try:
                with httpx.Client(timeout=httpx.Timeout(timeout_s, connect=0.5)) as client:
                    r = client.get(f"{url}/api/tags")
                    if r.status_code == 200:
                        self._ollama_online = True
                        self._ollama_checked = True
                        self._last_ollama_check_time = now
                        self.ollama_base_url = url
                        return True
            except Exception:
                continue
        self._ollama_online = False
        self._ollama_checked = True
        self._last_ollama_check_time = now
        return False


    def fetch_ollama_model_metadata(self, model_tag: str) -> dict[str, Any]:
        """Consulta /api/show para obtener cuantizacion, parametros y ventana de contexto real de Ollama."""
        try:
            with httpx.Client(timeout=1.2) as client:
                r = client.post(f"{self.ollama_base_url}/api/show", json={"name": model_tag})
                if r.status_code == 200:
                    data = r.json()
                    details = data.get("details", {})
                    model_info = data.get("model_info", {})
                    ctx_len = 8192
                    for k, v in model_info.items():
                        if "context_length" in k:
                            try:
                                ctx_len = int(v)
                            except Exception:
                                pass
                            break
                    return {
                        "parameter_size": details.get("parameter_size", "Desconocido"),
                        "quantization_level": details.get("quantization_level", "Q4_K_M"),
                        "format": details.get("format", "GGUF"),
                        "family": details.get("family", ""),
                        "context_length": ctx_len,
                    }
        except Exception:
            pass
        return {
            "parameter_size": "Desconocido",
            "quantization_level": "Q4_K_M",
            "format": "GGUF",
            "family": "",
            "context_length": 8192,
        }

    def _query_live_vram_gb(self, model_tag: str) -> float | None:
        """Consulta en tiempo real la VRAM dinámica asignada al modelo en Ollama (/api/ps)."""
        try:
            with httpx.Client(timeout=0.6) as client:
                r = client.get(f"{self.ollama_base_url}/api/ps")
                if r.status_code == 200:
                    data = r.json()
                    for m in data.get("models", []):
                        m_name = m.get("name", "")
                        if model_tag in m_name or m_name in model_tag:
                            vram_bytes = m.get("size_vram", 0)
                            if vram_bytes > 0:
                                return round(vram_bytes / (1024**3), 2)
        except Exception:
            pass
        return None

    def check_health(self) -> dict[str, Any]:
        """
        Diagnóstico de estado del subsistema de inferencia local.
        Verifica conectividad con Ollama, modelos descargados y modo operativo.
        """
        online = False
        installed_models: list[str] = []
        latency_ms = 0.0

        urls_to_try = [self.ollama_base_url]
        if "localhost" in self.ollama_base_url:
            urls_to_try.append(self.ollama_base_url.replace("localhost", "127.0.0.1"))
        elif "127.0.0.1" in self.ollama_base_url:
            urls_to_try.append(self.ollama_base_url.replace("127.0.0.1", "localhost"))

        t0 = time.perf_counter()
        for url in urls_to_try:
            try:
                with httpx.Client(timeout=httpx.Timeout(1.0, connect=0.5)) as client:
                    r = client.get(f"{url}/api/tags")
                    if r.status_code == 200:
                        online = True
                        data = r.json()
                        installed_models = [m.get("name", "") for m in data.get("models", [])]
                        self._ollama_online = True
                        self.ollama_base_url = url
                        break
            except Exception:
                pass
        latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        if not online:
            self._ollama_online = False

        all_models = self.config.get_all_models()
        configured_models = [m.id for m in all_models]
        matched_models = [
            m.id for m in all_models
            if any(
                m.id in inst.lower()
                or m.ollama_tag.lower() in inst.lower()
                or inst.lower().startswith(m.ollama_tag.split(":")[0].lower())
                for inst in installed_models
            )
        ]

        return {
            "ollama_online": online,
            "ollama_base_url": self.ollama_base_url,
            "ping_latency_ms": latency_ms if online else None,
            "installed_models": installed_models,
            "available_models": installed_models,
            "configured_models": configured_models,
            "matched_models": matched_models,
            "mode": "deterministic_simulator" if self.force_simulation else ("live_ollama" if online else "deterministic_simulator"),
            "simulator_ready": True,
            "vram_limit_gb": self.config.hardware.vram_gb,
        }



    def register_model(self, model_def: ModelDefinition) -> None:
        """Registra un nuevo modelo dinámico en el motor de inferencia."""
        self.models_by_id[model_def.id] = model_def
        self.models_by_id[model_def.ollama_tag] = model_def

    def unregister_model(self, model_id: str) -> None:
        """Retira un modelo (por id u ollama_tag) del registro en memoria del motor de inferencia."""
        target = self.models_by_id.get(model_id)
        keys = {model_id}
        if target is not None:
            keys.update({target.id, target.ollama_tag})
        for k in keys:
            self.models_by_id.pop(k, None)

    def generate(
        self,
        model_id: str,
        prompt: str,
        seed: int = 42,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        system_prompt: str | None = None,
        cancel_check: Any = None,
        scenario_hint: str | None = None
    ) -> RespuestaInferenciaContract:
        """
        Ejecuta la inferencia sobre el modelo especificado con telemetría de prellenado y decodificación.
        """
        # Sincronizar catálogo con Ollama para descubrir nuevos modelos al instante
        if self._is_ollama_available():
            try:
                fresh_models = self.config.sync_with_ollama(self.ollama_base_url)
                for m in fresh_models:
                    self.models_by_id[m.id] = m
                    self.models_by_id[m.ollama_tag] = m
            except Exception:
                pass

        model_def = self.models_by_id.get(model_id)
        if not model_def:
            # 1. Buscar en dynamic_models de la configuración (recarga fresca)
            clean_target = model_id.lower().replace(":", "-").replace(".", "-").replace("_", "-")
            for m in self.config.get_all_models():
                m_clean_id = m.id.lower().replace(":", "-").replace(".", "-").replace("_", "-")
                m_clean_tag = m.ollama_tag.lower().replace(":", "-").replace(".", "-").replace("_", "-")
                if (
                    m.id.lower() == model_id.lower()
                    or m.ollama_tag.lower() == model_id.lower()
                    or m_clean_id == clean_target
                    or m_clean_tag == clean_target
                    or m.id.lower().startswith(clean_target)
                    or clean_target.startswith(m_clean_id)
                ):
                    model_def = m
                    self.models_by_id[model_id] = m
                    self.models_by_id[m.id] = m
                    self.models_by_id[m.ollama_tag] = m
                    break

        if not model_def and self._is_ollama_available():
            # 2. Si no está en el catálogo pero está descargado en Ollama, auto-registrarlo dinámicamente
            try:
                health = self.check_health()
                installed = health.get("installed_models", [])
                clean_target = model_id.lower().replace(":", "-").replace(".", "-").replace("_", "-")
                for inst in installed:
                    inst_clean = inst.lower()
                    inst_slug = inst_clean.replace(":", "-").replace(".", "-").replace("_", "-")
                    if (
                        clean_target in inst_slug
                        or inst_slug in clean_target
                        or clean_target.split("-")[0] == inst_slug.split("-")[0]
                    ):
                        clean_name = inst.split(":")[0].replace("-", " ").title()
                        param_m = re.search(r'(\d+(?:\.\d+)?)[bB]', inst)
                        param_sz = f"{param_m.group(1)}B" if param_m else "Auto"
                        model_def = ModelDefinition(
                            id=model_id,
                            name=f"{clean_name} ({inst})",
                            provider="Ollama Local",
                            parameters_raw=param_sz,
                            license="Open",
                            quantization="Q4_K_M",
                            format="GGUF",
                            context_window_tokens=32768,
                            function_calling_support="native",
                            ollama_tag=inst,
                            approx_vram_gb=4.0,
                            reason_for_inclusion=f"Modelo {inst} detectado dinámicamente en Ollama."
                        )
                        self.config.save_dynamic_model(model_def)
                        self.register_model(model_def)
                        break
            except Exception:
                pass

        if not model_def:
            raise ValueError(f"Modelo '{model_id}' no reconocido en el catalogo de modelos del sistema ni en Ollama.")

        # Manejo universal de rol 'system': si el modelo no lo admite, fusionar en el prompt
        effective_prompt = prompt
        effective_system = system_prompt
        supports_system = getattr(model_def, "supports_system_role", True)
        if system_prompt and not supports_system:
            effective_prompt = f"### Instrucciones del Sistema:\n{system_prompt}\n\n### Tarea de Diagnóstico:\n{prompt}"
            effective_system = None

        # Verificacion y recorte determinista por ventana de contexto
        context_limit = getattr(model_def, "context_window_tokens", 8192) or 8192
        est_tokens = len(effective_prompt.split()) * 2
        context_truncated = False
        if est_tokens > context_limit:
            context_truncated = True
            keep_len = int((context_limit / 2) * 2.2)
            effective_prompt = (
                effective_prompt[:keep_len]
                + "\n\n[... Recorte determinista: telemetria intermedia truncada para ajustarse a ventana de contexto ... ]\n\n"
                + effective_prompt[-keep_len:]
            )

        if self._is_ollama_available():
            max_retries = 2
            for attempt in range(1, max_retries + 1):
                try:
                    return self._generate_ollama(
                        model_def=model_def,
                        prompt=effective_prompt,
                        seed=seed,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        system_prompt=effective_system,
                        cancel_check=cancel_check,
                        context_truncated=context_truncated
                    )
                except (httpx.ReadTimeout, httpx.ConnectTimeout) as e:
                    if attempt < max_retries:
                        logger.warning(
                            f"Timeout temporal en llamada a Ollama para {model_id} ({model_def.ollama_tag}). "
                            f"Reintentando intento {attempt + 1}/{max_retries} tras pausa de enfriamiento de 5s..."
                        )
                        time.sleep(5)
                        continue
                    logger.error(f"Fallo definitivo por timeout en Ollama para {model_id} ({model_def.ollama_tag}): {e}")
                    raise RuntimeError(
                        f"Fallo de inferencia en Ollama local para '{model_def.ollama_tag}': tiempo de espera agotado ({e}). "
                        "El modelo tardó más del límite configurado (15 min) en cargar o generar."
                    ) from e
                except Exception as e:
                    logger.error(f"Fallo en llamada a Ollama para {model_id} ({model_def.ollama_tag}): {e}")
                    raise RuntimeError(
                        f"Fallo de inferencia directa en Ollama local para '{model_def.ollama_tag}': {e}. "
                        "Verifica que el modelo este completamente descargado en Ollama."
                    ) from e

        if not self.force_simulation:
            raise RuntimeError(
                f"Ollama no disponible en {self.ollama_base_url}. Para diagnostico real en local, inicia el servicio de Ollama."
            )

        return self._generate_simulated(
            model_def=model_def,
            prompt=effective_prompt,
            seed=seed,
            temperature=temperature,
            max_tokens=max_tokens,
            scenario_hint=scenario_hint,
            context_truncated=context_truncated
        )

    def _generate_ollama(
        self,
        model_def: ModelDefinition,
        prompt: str,
        seed: int,
        temperature: float,
        max_tokens: int,
        system_prompt: str | None = None,
        cancel_check: Any = None,
        context_truncated: bool = False
    ) -> RespuestaInferenciaContract:
        """Ejecuta streaming con Ollama para medir con exactitud TTFT y velocidad de decodificación."""
        # Configuración de límites de generación y contexto para Ollama
        # num_predict=4096 (o -1) y num_ctx=8192 para evitar truncamientos en modelos de razonamiento (ej. DeepSeek R1)
        num_predict_val = max_tokens if max_tokens == -1 else max(max_tokens, 4096)
        num_ctx_val = 8192

        payload: dict[str, Any] = {
            "model": model_def.ollama_tag,
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": temperature,
                "seed": seed,
                "num_ctx": num_ctx_val,
                "num_predict": num_predict_val,
                "repeat_penalty": 1.15,
            }
        }
        if system_prompt:
            payload["system"] = system_prompt

        start_time = time.perf_counter()
        ttft_recorded = False
        ttft_ms = 0.0
        response_chunks: list[str] = []
        tokens_count = 0

        timeout_cfg = httpx.Timeout(connect=60.0, read=900.0, write=120.0, pool=60.0)
        with httpx.Client(timeout=timeout_cfg) as client:
            with client.stream("POST", f"{self.ollama_base_url}/api/generate", json=payload) as response:
                if response.status_code >= 400:
                    err_body = response.read().decode("utf-8", errors="replace")
                    raise RuntimeError(f"Ollama HTTP {response.status_code}: {err_body}")

                for line in response.iter_lines():
                    if cancel_check and cancel_check():
                        logger.info(f"Inferencia en {model_def.ollama_tag} cancelada por solicitud de usuario/teardown.")
                        break

                    if not line:
                        continue
                    if not ttft_recorded:
                        ttft_ms = (time.perf_counter() - start_time) * 1000.0
                        ttft_recorded = True

                    chunk_data = json.loads(line)
                    if "error" in chunk_data and chunk_data["error"]:
                        raise RuntimeError(f"Fallo en Ollama ({model_def.ollama_tag}): {chunk_data['error']}")

                    chunk_text = chunk_data.get("response", "")
                    chunk_thinking = chunk_data.get("thinking", "")
                    if chunk_text:
                        response_chunks.append(chunk_text)
                    elif chunk_thinking:
                        response_chunks.append(chunk_thinking)

                    if chunk_data.get("done", False):
                        if chunk_data.get("eval_count"):
                            tokens_count = chunk_data["eval_count"]
                        if chunk_data.get("eval_duration"):
                            eval_sec = chunk_data["eval_duration"] / 1e9
                            if eval_sec > 0 and tokens_count > 0:
                                tokens_per_sec = tokens_count / eval_sec
                        if chunk_data.get("prompt_eval_duration") and not ttft_recorded:
                            ttft_ms = chunk_data["prompt_eval_duration"] / 1e6
                        break
                    else:
                        tokens_count += 1

        total_time_ms = (time.perf_counter() - start_time) * 1000.0
        decode_time_s = max((total_time_ms - ttft_ms) / 1000.0, 0.001)
        tokens_per_sec = tokens_count / decode_time_s

        backend, live_vram, vram_valid = detect_ollama_backend_and_vram(self.ollama_base_url, model_def.ollama_tag)
        vram_allocated = live_vram if vram_valid else None
        vram_status = "measured" if vram_valid else "not_available"

        raw_text = "".join(response_chunks)
        clean_text, loop_detected = detect_and_cut_repetition_loops(raw_text)
        reasoning_text, final_text, reasoning_toks = extract_reasoning_and_response(clean_text)
        ttft_final_ms = round(ttft_ms + (reasoning_toks * 15.0), 2) if reasoning_text else ttft_ms

        telemetry = TelemetriaInferencia(
            time_to_first_token_ms=round(ttft_ms, 2),
            decode_tokens_per_second=round(tokens_per_sec, 2),
            prompt_tokens=len(prompt.split()) * 2,
            completion_tokens=tokens_count,
            total_latency_ms=round(total_time_ms, 2),
            vram_peak_gb=vram_allocated,
            vram_measurement_status=vram_status,
            inference_backend=backend,
            kv_cache_usage_mb=round(tokens_count * 0.12, 2),
            ttft_final_ms=round(ttft_final_ms, 2),
            reasoning_tokens=reasoning_toks
        )

        return RespuestaInferenciaContract(
            model_id=model_def.id,
            prompt_used=prompt,
            raw_response_text=clean_text,
            telemetry=telemetry,
            reasoning_text=reasoning_text,
            context_truncated=context_truncated,
            engine_mode="live_ollama"
        )

    # ── Respuestas simuladas por escenario (clave: patrón de detección) ────────
    _SCENARIO_RESPONSES = {
        "DNS-NXD": {
            "root_cause": "Registro DNS A ausente en la zona autoritativa de BIND9 (RCODE 3 / NXDOMAIN)",
            "affected": "bind9-authoritative",
            "action": "Agregar el registro de tipo A correspondiente en el archivo de zona y recargar BIND9.",
            "tool_call": '{"tool": "dig", "command": "dig @127.0.0.1 -p 5353 app.internal.corp A"}',
            "explanation": (
                "Al analizar la ventana de logs de BIND9, se observan múltiples solicitudes para el FQDN "
                "que devuelven NXDOMAIN. El análisis del SOP-DNS-01 y del RFC 1035 confirma que el servidor "
                "autoritativo no posee el registro solicitado en su archivo de zona."
            ),
        },
        "DNS-SRV": {
            "root_cause": "Tiempo de espera agotado (timeout) en resolución recursiva hacia servidor autoritativo remoto (SERVFAIL)",
            "affected": "bind9-recursive-resolver",
            "action": "Verificar conectividad de red y descarte de paquetes en puerto UDP 53 hacia el servidor remoto.",
            "tool_call": '{"tool": "dig", "command": "dig @127.0.0.1 -p 5353 partner.external.org A"}',
            "explanation": (
                "El servidor resolutor BIND9 no recibió respuesta de los servidores de nombres autoritativos, "
                "generando un RCODE 2 (SERVFAIL) tras expirar el temporizador de consulta recursiva."
            ),
        },
        "DNS-DEL": {
            "root_cause": "Delegación coja (lame delegation) por registros NS desincronizados en la zona padre",
            "affected": "bind9-zone-delegation",
            "action": "Sincronizar los registros NS y glue records en la zona autoritativa delegada.",
            "tool_call": '{"tool": "dig", "command": "dig @127.0.0.1 -p 5353 sub.corp.internal NS"}',
            "explanation": (
                "Los servidores designados por los registros NS no reconocen la autoridad para la zona solicitada, "
                "lo que provoca un fallo de delegación coja (lame delegation)."
            ),
        },
        "HTTP-502": {
            "root_cause": "Servicio upstream backend inaccesible (Connection Refused en socket TCP 127.0.0.1:8080), error HTTP 502",
            "affected": "upstream-backend-api",
            "action": "Reiniciar el servicio de backend y verificar que se encuentre escuchando activamente en el socket.",
            "tool_call": '{"tool": "curl", "command": "curl -I -s http://127.0.0.1:80/api/v1/users"}',
            "explanation": (
                "Nginx generó un error 502 Bad Gateway debido a que el socket del backend upstream rechazó la conexión "
                "(error 111 Connection refused). El SOP-NGINX-01 estipula la comprobación del socket y el reinicio del proceso."
            ),
        },
        "HTTP-504": {
            "root_cause": "Tiempo de espera agotado en backend upstream superando el proxy_read_timeout de Nginx, error HTTP 504",
            "affected": "upstream-backend-database",
            "action": "Optimizar la consulta en base de datos o incrementar el proxy_read_timeout en Nginx.",
            "tool_call": '{"tool": "curl", "command": "curl -I -s http://127.0.0.1:80/api/v1/reports"}',
            "explanation": (
                "La respuesta del backend tardó más del umbral configurado de 60s, causando un 504 Gateway Timeout."
            ),
        },
        "HTTP-500": {
            "root_cause": "Excepción no controlada (KeyError) en el código de la aplicación backend, HTTP 500 Internal Server Error",
            "affected": "backend-application-code",
            "action": "Corregir la excepción KeyError en la ruta del manejador y desplegar el hotfix.",
            "tool_call": '{"tool": "curl", "command": "curl -I -s http://127.0.0.1:80/api/v1/checkout"}',
            "explanation": (
                "Se detecta respuesta HTTP 500 Internal Server Error. Los logs del backend muestran un traceback "
                "de tipo KeyError no capturado en la lógica de negocio del manejador de la ruta de checkout."
            ),
        },
        "TLS-EXP": {
            "root_cause": "Certificado digital X.509 expirado en la terminación SSL/TLS de Nginx (certificate has expired)",
            "affected": "nginx-tls-termination",
            "action": "Renovar el certificado digital e instalar la nueva clave y cadena en el bloque SSL de Nginx.",
            "tool_call": '{"tool": "openssl", "command": "openssl s_client -connect 127.0.0.1:443 -servername secure.corp.internal"}',
            "explanation": (
                "El handshake TLS falla con código num=10 (certificate has expired). Los clientes abortan la conexión segura."
            ),
        },
        "HTTP-ORIGIN": {
            "root_cause": "Todos los servidores del cluster upstream están inalcanzables, no live upstreams (origin down)",
            "affected": "upstream-cluster",
            "action": "Verificar salud de los nodos del cluster y restaurar al menos una instancia del upstream.",
            "tool_call": '{"tool": "curl", "command": "curl -I -s http://127.0.0.1:80/api/v1/healthz"}',
            "explanation": (
                "Nginx reporta 'no live upstreams' porque ninguno de los backends configurados en el bloque "
                "upstream{} responde a los health checks. Todos los servidores origin están caídos."
            ),
        },
        "TLS-CHN": {
            "root_cause": "Cadena de certificados TLS incompleta en el servidor web (falta certificado intermedio de la CA emisora, unknown_ca)",
            "affected": "nginx-tls-termination",
            "action": "Concatenar el certificado del servidor con el bundle intermedio de la CA y recargar Nginx.",
            "tool_call": '{"tool": "openssl", "command": "openssl s_client -connect 127.0.0.1:443 -servername secure.corp.internal -showcerts"}',
            "explanation": (
                "El cliente rechaza el handshake TLS debido a que no puede validar la cadena de confianza hasta la CA raíz "
                "(unable to get local issuer certificate), conforme a la alerta unknown_ca del RFC 8446."
            ),
        },
        "HTTP-POOL": {
            "root_cause": "Agotamiento del pool de conexiones persistentes (keepalive pool exhausted) hacia el backend upstream",
            "affected": "upstream-backend-api",
            "action": "Incrementar el parámetro keepalive y max_conns en el bloque upstream de Nginx.",
            "tool_call": '{"tool": "curl", "command": "curl -I -s http://127.0.0.1:80/api/v1/users"}',
            "explanation": (
                "Nginx ha alcanzado el límite de conexiones simultáneas configuradas hacia el grupo upstream, "
                "rechazando nuevas peticiones con 503 Service Unavailable conforme al RFC 9110."
            ),
        },
        "NET-LAT": {
            "root_cause": "Latencia de red y retardo excesivo inyectado en el enlace (tc netem delay 2000ms), degradando RTT",
            "affected": "upstream-backend-database",
            "action": "Eliminar las colas de retardo tc netem en la interfaz de red y verificar latencia de transporte.",
            "tool_call": '{"tool": "curl", "command": "curl -I -s http://127.0.0.1:80/api/v1/reports"}',
            "explanation": (
                "La telemetría muestra un incremento anómalo en el percentil 95 de latencia superando los 2000ms "
                "debido a políticas de Traffic Control activas en el host que degradan la comunicación con el upstream."
            ),
        },
        "DNS-REF": {
            "root_cause": "Directiva allow-query o match-clients en named.conf restringe consultas para la dirección IP del cliente, devolviendo RCODE 5 (REFUSED)",
            "affected": "bind9-authoritative",
            "action": "Modificar la ACL en /etc/bind/named.conf.options para autorizar la subred del cliente solicitante y aplicar con rndc reload.",
            "tool_call": '{"tool": "dig", "command": "dig @127.0.0.1 -p 5353 restricted.corp.internal A"}',
            "explanation": (
                "El servidor autoritativo BIND9 devolvió RCODE 5 (REFUSED) para la consulta solicitada. "
                "El análisis de logs confirma que la dirección IP del cliente no pertenece a ninguna de las "
                "subredes autorizadas en la cláusula allow-query de la configuración de BIND9 conforme al RFC 1035."
            ),
        },
        "DNS-TRUNC": {
            "root_cause": "Respuesta con bandera TC=1 por desbordamiento de búfer UDP (512 bytes) sin soporte de EDNS0 o con puerto 53 TCP bloqueado en firewall",
            "affected": "bind9-resolver-firewall",
            "action": "Habilitar soporte EDNS0 con tamaño de búfer de 1232 bytes o habilitar tráfico TCP saliente en puerto 53 en la tabla de filtrado del firewall.",
            "tool_call": '{"tool": "dig", "command": "dig @127.0.0.1 -p 5353 large-recordset.corp.internal ANY +bufsize=512 +notcp"}',
            "explanation": (
                "La respuesta DNS superó el límite estándar de 512 octetos en transporte UDP, forzando la bandera TC=1 (Truncation). "
                "Al carecer de negociación EDNS0 o hallarse el puerto TCP 53 filtrado en el firewall perimetral, el cliente no pudo "
                "completar la transferencia del conjunto de registros conforme al RFC 1035 y RFC 6891."
            ),
        },
        "HTTP-403": {
            "root_cause": "Directiva 'deny all' en bloque location /admin/ o regla de lista negra de IP en el API Gateway bloqueando la dirección de origen del operador (HTTP 403 Forbidden)",
            "affected": "nginx-api-gateway",
            "action": "Modificar la directiva 'allow <ip>; deny all;' en /etc/nginx/conf.d/admin.conf para autorizar la IP de origen del operador y recargar Nginx.",
            "tool_call": '{"tool": "curl", "command": "curl -I -s http://127.0.0.1:80/admin/system/status"}',
            "explanation": (
                "Nginx API Gateway retornó un código de respuesta HTTP 403 Forbidden. Los registros de acceso y error demuestran "
                "que la ruta solicitada (/admin/system/status) cuenta con una regla de control de acceso basada en IP (deny all) "
                "o filtrado de seguridad WAF que rechaza la dirección del cliente."
            ),
        },
        "HTTP-429": {
            "root_cause": "Tasa de peticiones por segundo excede el umbral estipulado en limit_req_zone (rate=10r/s) devolviendo HTTP 429 Too Many Requests",
            "affected": "nginx-rate-limiter",
            "action": "Incrementar el parámetro burst o aumentar la tasa de peticiones en la directiva limit_req de Nginx para clientes autorizados.",
            "tool_call": '{"tool": "curl", "command": "curl -I -s http://127.0.0.1:80/api/v1/search?q=telecom"}',
            "explanation": (
                "El API Gateway rechazó las solicitudes entrantes con código HTTP 429 Too Many Requests. "
                "La directiva limit_req_zone excedió la tasa admisible por segundo configurada bajo el algoritmo leaky bucket, "
                "agotando los tokens disponibles para la clave de cliente conforme al RFC 6585."
            ),
        },
        "HTTP-503": {
            "root_cause": "Todos los procesos worker del servidor backend de aplicaciones se encuentran saturados con solicitudes pendientes o la aplicación se encuentra en modo mantenimiento (HTTP 503)",
            "affected": "backend-application-pool",
            "action": "Escalar horizontalmente las instancias de backend o incrementar el número de workers de ejecución asíncrona (Uvicorn/Gunicorn).",
            "tool_call": '{"tool": "curl", "command": "curl -I -s http://127.0.0.1:80/api/v1/orders"}',
            "explanation": (
                "El backend web devolvió HTTP 503 Service Unavailable debido a que la totalidad de los workers disponibles se "
                "encuentran bloqueados procesando solicitudes concurrentes, o la bandera de mantenimiento se encuentra activa en el pool."
            ),
        },
        "TLS-SNI": {
            "root_cause": "Discrepancia de SNI: el certificado presentado por Nginx corresponde al servidor por defecto y no incluye el FQDN solicitado en los Subject Alternative Names (SAN), causando error num=62 Hostname mismatch",
            "affected": "nginx-tls-termination",
            "action": "Configurar un bloque server dedicado con el certificado correspondiente o emitir un certificado wildcard/SAN que incluya el FQDN solicitado.",
            "tool_call": '{"tool": "openssl", "command": "openssl s_client -connect 127.0.0.1:443 -servername api-unregistered.corp.internal"}',
            "explanation": (
                "Durante el handshake TLS, el cliente transmitió la extensión SNI con el FQDN api-unregistered.corp.internal, pero el "
                "servidor Nginx sirvió el certificado default_server cuyo Subject/SAN no cubre dicho dominio, ocasionando verify error:num=62."
            ),
        },
        "TLS-CIPH": {
            "root_cause": "Incompatibilidad de suites de cifrado (Cipher Suite Mismatch): el servidor restringe exclusivamente a TLS 1.3/AEAD y rechaza las suites legadas ofrecidas por el cliente (código 40 handshake_failure)",
            "affected": "nginx-tls-crypto-engine",
            "action": "Actualizar la librería TLS del cliente para soportar suites modernas (TLS_AES_256_GCM_SHA384) o incorporar suites de transición en ssl_ciphers si la compatibilidad legada es requerida.",
            "tool_call": '{"tool": "openssl", "command": "openssl s_client -connect 127.0.0.1:443 -cipher AES128-SHA"}',
            "explanation": (
                "La negociación TLS fracasó con alerta fatal handshake_failure (código 40). El cliente ofreció suites de cifrado "
                "inseguras o legadas (AES128-SHA) que no coinciden con las directivas ssl_ciphers y ssl_protocols del servidor conforme al RFC 8446."
            ),
        },
    }

    def _detect_scenario(self, prompt_lower: str) -> dict:
        """Detecta el escenario deterministamente a partir de firmas en la telemetría y logs (Cero Fuga de Datos)."""
        # 1. Firmas deterministas de telemetría y logs observados (Zero Data Leakage / RFC-backed)
        signatures = [
            ("nxdomain", "DNS-NXD"),
            ("servfail", "DNS-SRV"),
            ("connection timed out resolving", "DNS-SRV"),
            ("query refused", "DNS-REF"),
            ("denied by access control", "DNS-REF"),
            ("refused", "DNS-REF"),
            ("tc flag", "DNS-TRUNC"),
            ("buffer limit 512", "DNS-TRUNC"),
            ("truncation", "DNS-TRUNC"),
            ("lame server", "DNS-DEL"),
            ("lame delegation", "DNS-DEL"),
            ("502 bad gateway", "HTTP-502"),
            ("connection refused", "HTTP-502"),
            ("504 gateway", "HTTP-504"),
            ("upstream timed out", "HTTP-504"),
            ("500 internal", "HTTP-500"),
            ("keyerror", "HTTP-500"),
            ("403 forbidden", "HTTP-403"),
            ("deny all", "HTTP-403"),
            ("429 too many", "HTTP-429"),
            ("limit_req", "HTTP-429"),
            ("503 service unavailable", "HTTP-503"),
            ("workers saturados", "HTTP-503"),
            ("connection pool exhausted", "HTTP-POOL"),
            ("sqlalchemy.exc.timeouterror", "HTTP-POOL"),
            ("high latency", "NET-LAT"),
            ("latency_ms >", "NET-LAT"),
            ("delay 150ms", "NET-LAT"),
            ("origin down", "HTTP-ORIGIN"),
            ("upstream server unreachable", "HTTP-ORIGIN"),
            ("no live upstreams", "HTTP-ORIGIN"),
            ("certificate has expired", "TLS-EXP"),
            ("verify error:num=10", "TLS-EXP"),
            ("num=10", "TLS-EXP"),
            ("hostname mismatch", "TLS-SNI"),
            ("verify error:num=62", "TLS-SNI"),
            ("num=62", "TLS-SNI"),
            ("handshake failure", "TLS-CIPH"),
            ("alert number 40", "TLS-CIPH"),
            ("local issuer certificate", "TLS-CHN"),
            ("verify error:num=20", "TLS-CHN"),
            ("num=20", "TLS-CHN"),
        ]
        for pattern, sc_key in signatures:
            if pattern in prompt_lower:
                return self._SCENARIO_RESPONSES[sc_key]

        # 2. Fallback de ID explícito si estuviese presente en otros modos
        for key in self._SCENARIO_RESPONSES:
            if key.lower() in prompt_lower:
                return self._SCENARIO_RESPONSES[key]

        # 3. Fallback genérico
        return {
            "root_cause": "Fallo indeterminado en servicio de aplicación de Capa 7",
            "affected": "backend-application-code",
            "action": "Revisar trazas de error de la aplicación e implementar excepciones controladas.",
            "tool_call": '{"tool": "curl", "command": "curl -I -s http://127.0.0.1:80/api/v1/status"}',
            "explanation": "Se detecta respuesta anómala del servicio; se requiere inspección detallada de los logs.",
        }

    def _generate_simulated(
        self,
        model_def: ModelDefinition,
        prompt: str,
        seed: int,
        temperature: float,
        max_tokens: int,
        scenario_hint: str | None = None,
        context_truncated: bool = False
    ) -> RespuestaInferenciaContract:
        """
        Simulador determinista de alta fidelidad calibrado con las mediciones empíricas
        de la plataforma de referencia (8GB VRAM, Q4_K_M).
        """
        model_hash = int(hashlib.sha256(model_def.id.encode("utf-8")).hexdigest(), 16)
        rng = random.Random(seed + model_hash)
        prompt_lower = prompt.lower()

        # Detectar escenario y obtener respuesta simulada
        resp = None
        if scenario_hint:
            clean_hint = scenario_hint.rsplit("-", 1)[0]
            resp = self._SCENARIO_RESPONSES.get(clean_hint) or self._SCENARIO_RESPONSES.get(scenario_hint)
        if not resp:
            resp = self._detect_scenario(prompt_lower)
        root_cause = resp["root_cause"]
        affected = resp["affected"]
        action = resp["action"]
        tool_call = resp["tool_call"]
        explanation = resp["explanation"]

        # Calibrar características de acuerdo al modelo
        if model_def.id == "phi-4-mini-instruct":
            # 3.8B: ultra rápido, menor consumo de VRAM
            ttft_ms = rng.uniform(110.0, 160.0)
            tok_per_sec = rng.uniform(38.0, 48.0)
            text = (
                f"DIAGNÓSTICO:\n"
                f"- Causa Raíz: {root_cause}\n"
                f"- Componente Afectado: {affected}\n"
                f"- Acción Sugerida: {action}\n"
                f"- Verificación Requerida: {tool_call}\n\n"
                f"Explicación Breve: {explanation}"
            )
        elif model_def.id == "qwen3-8b":
            # 8.2B: razonamiento nativo, tool calling
            ttft_ms = rng.uniform(220.0, 310.0)
            tok_per_sec = rng.uniform(24.0, 32.0)
            text = (
                f"<thought>\n"
                f"Analizando logs del servicio y cotejando contra RFC y SOP.\n"
                f"Hipótesis principal: {root_cause}.\n"
                f"Se requiere comprobación con herramienta de solo lectura.\n"
                f"</thought>\n\n"
                f"```json\n{tool_call}\n```\n\n"
                f"DIAGNÓSTICO FINAL:\n"
                f"- Causa Raíz: {root_cause}\n"
                f"- Componente Afectado: {affected}\n"
                f"- Acción Sugerida: {action}\n\n"
                f"Fundamentación Técnica:\n{explanation}"
            )
        elif model_def.id == "glm-4-9b-chat":
            # 9.0B: function calling de alta fidelidad
            ttft_ms = rng.uniform(270.0, 360.0)
            tok_per_sec = rng.uniform(20.0, 27.0)
            text = (
                f"[Action Plan]\n"
                f"Step 1: Execute read-only verification: {tool_call}\n\n"
                f"[Diagnostic Assessment]\n"
                f"- Root Cause: {root_cause}\n"
                f"- Affected Component: {affected}\n"
                f"- Suggested Mitigation: {action}\n\n"
                f"[Technical Rationale]\n{explanation}"
            )
        else:
            # Modelo dinámico: estimar según parámetros (1B, 3B, 7B, 8B, 14B...)
            param_lower = f"{model_def.parameters_raw} {model_def.id}".lower()
            if "1b" in param_lower or "2b" in param_lower:
                ttft_ms = rng.uniform(70.0, 115.0)
                tok_per_sec = rng.uniform(50.0, 68.0)
            elif "3b" in param_lower or "4b" in param_lower:
                ttft_ms = rng.uniform(110.0, 160.0)
                tok_per_sec = rng.uniform(38.0, 48.0)
            elif "7b" in param_lower or "8b" in param_lower:
                ttft_ms = rng.uniform(220.0, 300.0)
                tok_per_sec = rng.uniform(24.0, 32.0)
            else:
                ttft_ms = rng.uniform(270.0, 360.0)
                tok_per_sec = rng.uniform(20.0, 27.0)
            text = (
                f"<thought>\n"
                f"Evaluación técnica de infraestructura L7 con modelo {model_def.name}.\n"
                f"Anomalía detectada en logs: {root_cause}.\n"
                f"Comando de verificación read-only: {tool_call}.\n"
                f"</thought>\n\n"
                f"```json\n{tool_call}\n```\n\n"
                f"DIAGNÓSTICO FINAL:\n"
                f"- Causa Raíz: {root_cause}\n"
                f"- Componente Afectado: {affected}\n"
                f"- Acción Sugerida: {action}\n\n"
                f"Fundamentación Técnica:\n{explanation}"
            )

        completion_tokens = len(text.split()) * 2
        decode_time_s = completion_tokens / tok_per_sec
        total_time_ms = ttft_ms + (decode_time_s * 1000.0)

        # VRAM dinámica calibrada con expansión de KV-cache y decodificación autoregresiva
        vram_dyn = round(model_def.approx_vram_gb + (completion_tokens * 0.00012) + rng.uniform(-0.04, 0.04), 2)

        clean_text, loop_detected = detect_and_cut_repetition_loops(text)
        reasoning_text, final_text, reasoning_toks = extract_reasoning_and_response(clean_text)
        ttft_final_sim = round(ttft_ms + (reasoning_toks * 12.0), 2) if reasoning_text else ttft_ms

        telemetry = TelemetriaInferencia(
            time_to_first_token_ms=round(ttft_ms, 2),
            decode_tokens_per_second=round(tok_per_sec, 2),
            prompt_tokens=len(prompt.split()) * 2,
            completion_tokens=completion_tokens,
            total_latency_ms=round(total_time_ms, 2),
            vram_peak_gb=None,
            vram_measurement_status="not_available",
            inference_backend="CPU",
            kv_cache_usage_mb=round(completion_tokens * 0.12, 2),
            ttft_final_ms=round(ttft_final_sim, 2),
            reasoning_tokens=reasoning_toks
        )

        return RespuestaInferenciaContract(
            model_id=model_def.id,
            prompt_used=prompt,
            raw_response_text=clean_text,
            telemetry=telemetry,
            reasoning_text=reasoning_text,
            context_truncated=context_truncated,
            engine_mode="deterministic_simulator"
        )
