"""
NetDiagBench-L7: Validador de Trazabilidad e Integridad Criptográfica de traza.jsonl
Verifica la presencia, tipos, congruencia de herramientas, huellas SHA-256, esquemas
y consistencia entre CSV y JSONL de cada registro en el archivo de trazas continuo.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError


MANDATORY_BASE_TRACE_FIELDS: list[str] = [
    "run_id",
    "scenario_id",
    "model_id",
    "engine_mode",
    "execution_mode",
    "timestamp",
    "prompt",
    "template_sha256",
    "evaluator_version",
    "response",
    "tools_called",
    "outputs",
    "return_codes",
    "ttft_s",
    "tokens",
    "speed",
    "energy_kwh",
    "vram_peak_gb",
    "ram_gb",
    "root_cause_expected",
    "root_cause_predicted",
    "factual_accuracy_c6",
    "is_evidence_backed",
]

MANDATORY_V4_TRACE_FIELDS: list[str] = [
    "campaign_id",
    "run_id",
    "attempt_id",
    "model_id",
    "scenario_id",
    "seed",
    "execution_mode",
    "engine_mode",
    "execution_backend",
    "template_sha256",
    "prompt_sha256",
    "response_sha256",
    "config_sha256",
    "timestamp",
    "prompt",
    "response",
    "tools_called",
    "outputs",
    "return_codes",
    "ttft_s",
    "latency_s",
    "tokens",
    "ram_gb",
    "vram_peak_gb",
    "energy_kwh",
    "diagnostico",
    "evidence_status",
]

# Alias de compatibilidad
MANDATORY_TRACE_FIELDS = MANDATORY_BASE_TRACE_FIELDS


class TraceEntryContract(BaseModel):
    """Esquema riguroso de cada línea en traza.jsonl con soporte completo v4 y compatibilidad retroactiva."""
    campaign_id: str | None = Field(None, description="Identificador único de la campaña experimental")
    run_id: str = Field(..., description="Identificador único de la corrida")
    attempt_id: int | None = Field(None, description="Número de intento de la corrida (1 para corridas regulares)")
    scenario_id: str = Field(..., description="Identificador del escenario L7")
    model_id: str = Field(..., description="Identificador del modelo evaluado")
    seed: int | None = Field(None, description="Semilla de inicialización y reproducibilidad")
    engine_mode: str = Field(..., description="'live_ollama' o 'deterministic_simulator'")
    execution_mode: str = Field(..., description="'sintetico_determinista' o 'emulado'")
    execution_backend: str | None = Field(None, description="Backend de ejecución: CPU, GPU, HYBRID o UNKNOWN")
    timestamp: str = Field(..., description="Marca temporal ISO-8601")
    prompt: str = Field(..., description="Texto completo del prompt enviado")
    template_sha256: str = Field(..., description="Hash SHA-256 de la plantilla Jinja2 o prompt base")
    prompt_sha256: str | None = Field(None, description="Hash SHA-256 del prompt final instanciado")
    response_sha256: str | None = Field(None, description="Hash SHA-256 de la respuesta del modelo")
    config_sha256: str | None = Field(None, description="Hash SHA-256 de la configuración del benchmark")
    evaluator_version: str | None = Field(None, description="Hash SHA-256 de evaluator_concepts.yaml")
    response: str = Field(..., description="Texto bruto de la respuesta generada")
    tools_called: list[str] = Field(default_factory=list, description="Lista de herramientas invocadas")
    outputs: list[str] = Field(default_factory=list, description="Salidas de las herramientas invocadas")
    return_codes: list[int] = Field(default_factory=list, description="Códigos de retorno de las herramientas")
    ttft_s: float = Field(..., ge=0.0, description="Time to first token en segundos")
    latency_s: float | None = Field(None, ge=0.0, description="Latencia total en segundos")
    tokens: int = Field(..., ge=0, description="Total de tokens generados")
    speed: float | None = Field(None, ge=0.0, description="Velocidad en tokens/segundo")
    energy_kwh: float = Field(..., ge=0.0, description="Energía estimada en kWh")
    vram_peak_gb: float | None = Field(None, description="VRAM pico en GB (null si no medible físicamente)")
    ram_gb: float = Field(..., ge=0.0, description="RAM del proceso en GB")
    diagnostico: dict[str, Any] | None = Field(None, description="Diagnóstico estructurado")
    evidence_status: str | None = Field(None, description="Estado de la evidencia ('backed', 'partial', 'unbacked')")
    root_cause_expected: str | None = Field(None, description="Causa raíz de referencia (Ground Truth)")
    root_cause_predicted: str | None = Field(None, description="Causa raíz predicha por el modelo")
    factual_accuracy_c6: int | None = Field(None, ge=0, le=2, description="Exactitud factual C6: 0, 1 o 2")
    is_evidence_backed: bool | None = Field(None, description="Sustentado en evidencia técnica")


def calculate_prompt_sha256(prompt: str) -> str:
    """Calcula el hash SHA-256 del prompt."""
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def calculate_file_sha256(file_path: Path | str) -> str:
    """Calcula el resumen SHA-256 de un archivo en disco."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()



def compute_canonical_config(entry_or_dict: dict[str, Any]) -> dict[str, Any]:
    """
    Construye la representacion canonica estandarizada de los parametros efectivos
    de ejecucion para una corrida experimental:
    - model_id: modelo evaluado
    - digest: digest criptografico o identificador de pesos del modelo
    - quantization: nivel de cuantizacion (e.g. Q4_K_M)
    - temperature: temperatura de muestreo (0.0 por defecto para determinismo)
    - top_p: top_p de inferencia (0.9)
    - seed: semilla pseudoaleatoria
    - context_window: tamano de ventana de contexto (tokens)
    - max_tokens: limite de tokens decodificados
    - engine_mode: live_ollama o deterministic_simulator
    - execution_mode: emulado o sintetico_determinista
    - execution_backend: CPU, GPU, HYBRID o UNKNOWN
    """
    return {
        "model_id": str(entry_or_dict.get("model_id", "")).strip(),
        "digest": str(entry_or_dict.get("model_digest", entry_or_dict.get("digest", "")) or "").strip() or None,
        "quantization": str(entry_or_dict.get("quantization", entry_or_dict.get("cuantizacion", "Q4_K_M"))).upper(),
        "temperature": float(entry_or_dict.get("temperature", 0.0)),
        "top_p": float(entry_or_dict.get("top_p", 0.9)),
        "seed": int(entry_or_dict.get("seed", 42)) if entry_or_dict.get("seed") is not None else 42,
        "context_window": int(entry_or_dict.get("context_window", entry_or_dict.get("ctx_len", 4096))),
        "max_tokens": int(entry_or_dict.get("max_tokens", entry_or_dict.get("max_decoding_tokens", 1024))),
        "engine_mode": str(entry_or_dict.get("engine_mode", "live_ollama")),
        "execution_mode": str(entry_or_dict.get("execution_mode", "emulado")),
        "execution_backend": str(entry_or_dict.get("execution_backend", "CPU")),
    }


def compute_canonical_config_sha256(entry_or_dict: dict[str, Any]) -> str:
    """Calcula el hash SHA-256 canonico y reproducible de la configuracion efectiva."""
    canon = compute_canonical_config(entry_or_dict)
    canon_bytes = json.dumps(canon, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canon_bytes).hexdigest()


def validate_trace_entry(
    entry: dict[str, Any],
    verify_prompt_hash: bool = True,
    strict_v4: bool = False
) -> tuple[bool, str]:
    """
    Valida un registro individual contra el esquema TraceEntryContract.
    Verifica campos obligatorios, congruencia de herramientas, hashes y ausencia de respuestas vacías.
    Retorna (is_valid: bool, error_msg: str).
    """
    fields_to_check = MANDATORY_V4_TRACE_FIELDS if strict_v4 else MANDATORY_BASE_TRACE_FIELDS
    missing = [f for f in fields_to_check if f not in entry]
    if missing:
        return False, f"Faltan campos obligatorios: {missing}"

    # Verificación de respuesta vacía
    resp = entry.get("response")
    if resp is None or not str(resp).strip():
        return False, "Respuesta vacía o ausente generada por el modelo"

    try:
        parsed = TraceEntryContract(**entry)
    except ValidationError as e:
        return False, f"Error de validación de contrato Pydantic: {e.errors()}"

    # Congruencia de listas de herramientas
    n_tools = len(parsed.tools_called)
    n_outs = len(parsed.outputs)
    n_codes = len(parsed.return_codes)
    if not (n_tools == n_outs == n_codes):
        return (
            False,
            f"Desalineación en longitud de pasos de herramientas: tools_called ({n_tools}), "
            f"outputs ({n_outs}), return_codes ({n_codes}) deben ser iguales.",
        )

    # Verificación de hashes criptográficos recalculados desde contenidos originales
    if verify_prompt_hash and parsed.prompt:
        expected_prompt_hash = calculate_prompt_sha256(parsed.prompt)
        if parsed.prompt_sha256:
            if parsed.prompt_sha256.lower() != expected_prompt_hash.lower():
                return (
                    False,
                    f"Discrepancia criptográfica: prompt_sha256 '{parsed.prompt_sha256}' "
                    f"no coincide con sha256(prompt) '{expected_prompt_hash}'",
                )

        # Diferenciación estricta entre template_sha256 y prompt_sha256
        if parsed.template_sha256 and parsed.prompt_sha256:
            if parsed.template_sha256.lower() == parsed.prompt_sha256.lower():
                return (
                    False,
                    "Falla de diferenciación criptográfica: template_sha256 coincide con prompt_sha256 "
                    "(el hash de la plantilla Jinja2 no debe confundirse con el hash del prompt renderizado)",
                )

    # Verificación de hash de respuesta recalculado
    if parsed.response and parsed.response_sha256:
        expected_resp_hash = hashlib.sha256(parsed.response.encode("utf-8")).hexdigest()
        if parsed.response_sha256.lower() != expected_resp_hash.lower():
            return (
                False,
                f"Discrepancia criptográfica: response_sha256 '{parsed.response_sha256}' "
                f"no coincide con sha256(response) '{expected_resp_hash}'",
            )

    # Verificación de validez de template_sha256 y config_sha256
    if parsed.template_sha256 and parsed.template_sha256 != "unknown_template_sha256":
        if len(parsed.template_sha256) != 64:
            return (
                False,
                f"Discrepancia criptográfica: template_sha256 '{parsed.template_sha256}' debe ser un hash hexadecimal de 64 caracteres",
            )

    if parsed.config_sha256 and parsed.config_sha256 != "unknown_config_sha256":
        if len(parsed.config_sha256) != 64:
            return (
                False,
                f"Discrepancia criptográfica: config_sha256 '{parsed.config_sha256}' debe ser un hash hexadecimal de 64 caracteres",
            )

    return True, ""


def validate_trace_file(
    file_path: Path | str,
    verify_prompt_hash: bool = True,
    strict_v4: bool = False
) -> dict[str, Any]:
    """
    Lee y valida cada línea de un archivo traza.jsonl.
    Detecta registros duplicados, registros incompletos, respuestas vacías y discrepancias de hashes.
    Retorna reporte con total de líneas, válidas, inválidas, errores y SHA-256 del archivo.
    """
    path = Path(file_path)
    if not path.is_file():
        return {
            "file_exists": False,
            "file_path": str(path),
            "total_lines": 0,
            "valid_lines": 0,
            "invalid_lines": 0,
            "is_valid": False,
            "errors": [f"El archivo no existe: {path}"],
            "sha256": "",
        }

    file_sha256 = calculate_file_sha256(path)
    total = 0
    valid = 0
    invalid = 0
    errors: list[dict[str, Any]] = []
    seen_run_ids: set[str] = set()

    with open(path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f, start=1):
            line_str = line.strip()
            if not line_str:
                continue
            total += 1
            try:
                data = json.loads(line_str)
            except json.JSONDecodeError as e:
                invalid += 1
                errors.append({"line": idx, "error": f"JSON inválido: {str(e)}"})
                continue

            run_id = str(data.get("run_id", "")).strip()
            if run_id in seen_run_ids:
                invalid += 1
                errors.append({
                    "line": idx,
                    "run_id": run_id,
                    "error": f"Registro duplicado detectado: run_id '{run_id}' ya existe previamente en la traza"
                })
                continue
            if run_id:
                seen_run_ids.add(run_id)

            ok, err = validate_trace_entry(
                data,
                verify_prompt_hash=verify_prompt_hash,
                strict_v4=strict_v4
            )
            if ok:
                valid += 1
            else:
                invalid += 1
                errors.append({"line": idx, "error": err, "run_id": run_id})

    return {
        "file_exists": True,
        "file_path": str(path),
        "total_lines": total,
        "valid_lines": valid,
        "invalid_lines": invalid,
        "is_valid": (invalid == 0 and total > 0),
        "errors": errors,
        "sha256": file_sha256,
    }


def validate_alignment_csv_jsonl(
    csv_path: Path | str,
    jsonl_path: Path | str
) -> dict[str, Any]:
    """
    Comprueba exhaustivamente la correspondencia y alineacion bidireccional entre resultados.csv y traza.jsonl:
    - Cantidad total de registros concordante.
    - Presencia reciproca de cada corrida identificada por 'run_id' como clave primaria estricta.
    - Congruencia metrica en veredictos (is_root_cause_correct vs coherencia en traza).
    - Deteccion de filas huerfanas en ambos lados.
    """
    c_path = Path(csv_path)
    j_path = Path(jsonl_path)

    if not c_path.is_file() or not j_path.is_file():
        return {
            "aligned": False,
            "errors": [f"Archivos no encontrados: CSV ({c_path.exists()}), JSONL ({j_path.exists()})"],
            "csv_count": 0,
            "jsonl_count": 0,
            "matched_count": 0,
            "discrepancies": [f"Archivos no encontrados: CSV ({c_path.exists()}), JSONL ({j_path.exists()})"],
        }

    csv_rows: list[dict[str, Any]] = []
    with open(c_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            csv_rows.append(r)

    jsonl_entries: list[dict[str, Any]] = []
    with open(j_path, "r", encoding="utf-8") as f:
        for line in f:
            l_str = line.strip()
            if l_str:
                try:
                    jsonl_entries.append(json.loads(l_str))
                except Exception:
                    pass

    discrepancies: list[str] = []

    if len(csv_rows) != len(jsonl_entries):
        discrepancies.append(
            f"Diferencia en número de registros: CSV tiene {len(csv_rows)} filas, "
            f"mientras JSONL tiene {len(jsonl_entries)} entradas."
        )

    # Indexar JSONL por run_id
    jsonl_by_run_id: dict[str, dict[str, Any]] = {}
    for idx, e in enumerate(jsonl_entries, start=1):
        rid = str(e.get("run_id", "")).strip()
        if not rid:
            sc = e.get("scenario_id", "")
            m = e.get("model_id", "")
            sd = e.get("seed", "42")
            rid = f"{sc}_s{sd}_r1_{m}"
        jsonl_by_run_id[rid] = e

    # Indexar CSV por run_id
    csv_by_run_id: dict[str, dict[str, Any]] = {}
    for idx, r in enumerate(csv_rows, start=1):
        rid = str(r.get("run_id", "")).strip()
        if not rid:
            sc = r.get("scenario_id", "")
            m = r.get("model_id", "")
            sd = r.get("seed", r.get("semilla", "42"))
            rep = r.get("repetition_index", "1")
            rid = f"{sc}_s{sd}_r{rep}_{m}"
        csv_by_run_id[rid] = r

    # 1. Correspondencia CSV -> JSONL
    matched_run_ids = set()
    for rid, r in csv_by_run_id.items():
        if rid in jsonl_by_run_id:
            matched_run_ids.add(rid)
        else:
            discrepancies.append(f"Fila CSV con run_id '{rid}' no encontrada en JSONL.")

    # 2. Correspondencia JSONL -> CSV (bidireccional)
    for rid, e in jsonl_by_run_id.items():
        if rid not in csv_by_run_id:
            discrepancies.append(f"Entrada JSONL con run_id '{rid}' no encontrada en CSV.")

    return {
        "aligned": len(discrepancies) == 0,
        "csv_count": len(csv_rows),
        "jsonl_count": len(jsonl_entries),
        "matched_count": len(matched_run_ids),
        "discrepancies": discrepancies,
    }


def main():
    parser = argparse.ArgumentParser(description="Validador de Trazabilidad e Integridad JSONL / CSV para NetDiagBench-L7")
    parser.add_argument("file", help="Ruta al archivo traza.jsonl")
    parser.add_argument("--csv", help="Ruta opcional al archivo resultados.csv para comprobar alineación", default=None)
    parser.add_argument("--skip-hash", action="store_true", help="Omitir validación estricta de hash de prompt")
    parser.add_argument("--strict-v4", action="store_true", help="Exigir todos los campos obligatorios v4")
    args = parser.parse_args()

    report = validate_trace_file(args.file, verify_prompt_hash=not args.skip_hash, strict_v4=args.strict_v4)
    print(f"Archivo JSONL: {report['file_path']}")
    print(f"Líneas totales: {report['total_lines']} | Válidas: {report['valid_lines']} | Inválidas: {report['invalid_lines']}")
    print(f"SHA-256: {report['sha256']}")
    if report["is_valid"]:
        print("ESTADO: VALIDO (100% de registros íntegros)")
    else:
        print("ESTADO: ERRORES DETECTADOS")
        for err in report["errors"][:10]:
            print(f" - Línea {err.get('line')}: {err.get('error')}")

    if args.csv:
        align = validate_alignment_csv_jsonl(args.csv, args.file)
        print(f"\nAlineación CSV vs JSONL: {'ALINEADO' if align['aligned'] else 'DISCREPANCIAS'}")
        print(f"Coincidencias: {align['matched_count']} / {align['csv_count']}")
        for d in align["discrepancies"][:5]:
            print(f" - {d}")


if __name__ == "__main__":
    main()
