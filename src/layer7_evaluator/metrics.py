"""
NetDiagBench-L7: Layer 7 - Evaluation Metrics & Official Technical Grounding
Implementa el cálculo de métricas de precisión diagnóstica (F1, acierto parcial),
estimación de huella energética (kWh/CO2e) y rúbrica de explicabilidad (0 a 5).
Evaluación formal basada en conceptos normativos de fuentes oficiales (RFC 1035/9110/8446,
manuales BIND9 ARM, SOPs IETF), versionada con hash criptográfico SHA-256 (Cero Golden Set / Cero Kappa).
"""

import hashlib
import os
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CONCEPTS_YAML_PATH = PROJECT_ROOT / "configs" / "evaluator_concepts.yaml"

OFFICIAL_TERNA_MODELS = {"qwen3-8b", "phi-4-mini-instruct", "glm-4-9b-chat"}

_RE_NON_ALPHANUM = re.compile(r"[^a-z0-9_\-\s]")
_RE_SPACES = re.compile(r"\s+")


def _remove_accents(text: str) -> str:
    """Elimina tildes y diacríticos manteniendo caracteres base."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if unicodedata.category(c) != "Mn")


def _clean_text(text: str) -> str:
    """Normaliza texto técnico a minúsculas, sin tildes ni caracteres especiales."""
    text = _remove_accents(str(text).lower())
    text = _RE_NON_ALPHANUM.sub(" ", text)
    return _RE_SPACES.sub(" ", text).strip()


def _match_term(term: str, text: str) -> bool:
    """
    Coincidencia determinista por palabra completa (\\b...\\b) o frase,
    soportando raíces y comodines mediante sufijo '*' (ej. 'rechaz*', 'intermedi*').
    """
    if not term or not text:
        return False

    term_raw = _remove_accents(str(term).lower().strip())
    clean_t = _clean_text(text)
    if not term_raw or not clean_t:
        return False

    if "*" in term_raw:
        parts = re.split(r"[\s\-_]+", term_raw)
        regex_parts = []
        for p in parts:
            p_clean = re.sub(r"[^a-z0-9*]", "", p)
            if p_clean.endswith("*"):
                stem = re.escape(p_clean[:-1])
                regex_parts.append(rf"{stem}[a-z0-9_\-]*")
            elif p_clean:
                regex_parts.append(re.escape(p_clean))
        if not regex_parts:
            return False
        pattern = rf"\b" + r"[\s\-_]+".join(regex_parts) + rf"\b"
        return bool(re.search(pattern, clean_t))

    clean_term = _clean_text(term_raw)
    if not clean_term:
        return False
    parts = clean_term.split()
    pattern = rf"\b" + r"[\s\-_]+".join(re.escape(p) for p in parts) + rf"\b"
    return bool(re.search(pattern, clean_t))


def _match_group(group: dict[str, Any], text: str) -> bool:
    """
    Verifica si un grupo de conceptos normativos (núcleo + modificadores opcionales)
    se cumple en el texto técnico analizado.
    """
    nucleus = group.get("nucleus", [])
    modifiers = group.get("modifiers", [])

    # 1. El núcleo es obligatorio (al menos uno de los términos/raíces debe coincidir)
    nucleus_match = any(_match_term(n, text) for n in nucleus)
    if not nucleus_match:
        return False

    # 2. Modificadores (si existen en el grupo, al menos uno debe coincidir)
    if modifiers:
        mod_match = any(_match_term(m, text) for m in modifiers)
        if not mod_match:
            return False

    return True


_NEGATION_TERMS = {
    "descartar", "descarta", "descartado", "descartada", "descartando",
    "no es", "no se trata de", "si persiste", "en caso de", "not", "rule out",
    "ruled out", "no corresponde", "sin ser", "a diferencia de", "diferente de",
    "en lugar de", "unlike"
}


def _extract_first_sentence_of_root_cause(text: str) -> str:
    """Extrae la primera oración del bloque de Causa Raíz emitido por el modelo."""
    if not text or not str(text).strip():
        return ""

    clean_t = str(text).strip()
    # Si contiene encabezado estructurado de Causa Raíz, extraer el contenido de ese bloque
    m = re.search(r"(?:causa\s+ra[íi]z|root\s+cause)\s*[:\-]\s*(.+)", clean_t, flags=re.IGNORECASE | re.DOTALL)
    target_text = m.group(1).strip() if m else clean_t

    # Cortar en el primer punto seguido de espacio/salto de línea o primer fin de línea
    sentences = re.split(r"(?<=[.!?])(?:\s+|\n+)", target_text)
    return sentences[0].strip() if sentences else target_text


def _is_negated_in_sentence(term: str, sentence: str) -> bool:
    """Verifica si la mención del término vecino en la primera oración está negada."""
    clean_s = _clean_text(sentence)
    for neg in _NEGATION_TERMS:
        clean_neg = _clean_text(neg)
        if clean_neg in clean_s:
            return True
    return False


@lru_cache(maxsize=1)
def load_evaluator_concepts() -> dict[str, Any]:
    """Carga y almacena en caché el catálogo normativo oficial de conceptos de evaluación."""
    if not CONCEPTS_YAML_PATH.exists():
        raise FileNotFoundError(f"Catálogo de conceptos no encontrado en: {CONCEPTS_YAML_PATH}")
    with open(CONCEPTS_YAML_PATH, "rb") as f:
        content = f.read()
    return yaml.safe_load(content)


@lru_cache(maxsize=1)
def get_evaluator_version() -> str:
    """Calcula y retorna el hash SHA-256 (12 caracteres) del archivo de conceptos oficial."""
    if not CONCEPTS_YAML_PATH.exists():
        return "desconocido"
    with open(CONCEPTS_YAML_PATH, "rb") as f:
        content = f.read()
    return hashlib.sha256(content).hexdigest()[:12]


def classify_model(
    model_id: str,
    parameters_raw: str = "",
    family_tag: str = "",
    reasoning_tokens: int = 0
) -> tuple[str, str]:
    """
    Clasifica deterministamente cualquier modelo agregado a la plataforma:
    Retorna (model_group, model_family).
      model_group: 'oficial' (para la terna acreditada) | 'adicional' (para cualquier otro modelo)
      model_family: 'ultraligero' (<=2B), 'razonamiento' (CoT con reasoning_tokens > 0),
                    'intermedio' (3B-4B), 'codigo' (tool-calling/code), 'completo' (7B-9B).
    """
    mid = model_id.lower().strip()
    mid_clean = mid.replace(":", "-").replace(".", "-").replace("_", "-")

    # 1. Determinación de model_group
    is_oficial = any(
        mid == off or mid_clean == off or off in mid
        for off in OFFICIAL_TERNA_MODELS
    )
    group = "oficial" if is_oficial else "adicional"

    # 2. Determinación de model_family
    combined = f"{mid} {parameters_raw} {family_tag}".lower()

    # Prioridad: Código / Tool-calling
    if any(k in combined for k in ("coder", "code", "sql", "starcoder", "codellama")):
        return group, "codigo"

    # Prioridad: Razonamiento CoT
    # Si tiene tokens de razonamiento (>0) o es modelo explícito de razonamiento profundo (r1, qwq)
    if any(k in combined for k in ("r1", "qwq")):
        return group, "razonamiento"
    if reasoning_tokens > 0 and any(k in combined for k in ("reasoning", "reason", "think", "qwen3")):
        return group, "razonamiento"

    # Extracción de tamaño de parámetros
    param_size = 0.0
    m_param = re.search(r"(\d+(?:\.\d+)?)\s*[bB]", combined)
    if m_param:
        try:
            param_size = float(m_param.group(1))
        except ValueError:
            param_size = 0.0

    if 0.0 < param_size <= 2.5:
        return group, "ultraligero"
    elif 2.5 < param_size <= 4.5:
        return group, "intermedio"
    elif param_size > 4.5:
        return group, "completo"

    # Inferencia por nombres comunes si no hay tamaño de parámetros explícito
    if any(k in mid for k in ("1b", "2b", "0.5b", "tiny", "smol", "nano")):
        return group, "ultraligero"
    if any(k in mid for k in ("3b", "4b", "mini")):
        return group, "intermedio"

    return group, "completo"


# Alias distintivos de componentes normativos (Ground Truth del catálogo - Auditoría A4)
# Sin palabras compartidas ambiguas ('api', 'nginx', 'backend', 'upstream', 'bind9', 'tls')
_COMPONENT_ALIASES: dict[str, set[str]] = {
    "bind9-authoritative": {
        "bind9-authoritative", "autoritativo", "authoritative",
        "servidor autoritativo", "authoritative server", "dns autoritativo"
    },
    "bind9-recursive-resolver": {
        "bind9-recursive-resolver", "recursivo", "recursive",
        "resolutor recursivo", "recursive resolver", "resolutor"
    },
    "bind9-zone-delegation": {
        "bind9-zone-delegation", "delegacion", "delegation",
        "lame delegation", "servidor delegado", "servidores delegados"
    },
    "bind9-resolver-firewall": {
        "bind9-resolver-firewall", "firewall", "edns-firewall",
        "resolver firewall", "firewall dns"
    },
    "upstream-backend-api": {
        "upstream-backend-api", "backend-api", "api-backend",
        "fastapi", "servicio api", "upstream api", "backend api"
    },
    "upstream-backend-database": {
        "upstream-backend-database", "database", "base de datos",
        "db backend", "upstream database", "backend database"
    },
    "upstream-cluster": {
        "upstream-cluster", "cluster upstream", "cluster de origen",
        "origin cluster", "servidores de origen", "origin servers"
    },
    "backend-application-code": {
        "backend-application-code", "codigo de aplicacion", "application code",
        "codigo backend", "app code", "source code"
    },
    "backend-application-pool": {
        "backend-application-pool", "pool de workers", "worker pool",
        "gunicorn", "uvicorn", "pool de procesos", "application pool"
    },
    "nginx-api-gateway": {
        "nginx-api-gateway", "api-gateway", "api gateway",
        "gateway", "reverse proxy gateway"
    },
    "nginx-rate-limiter": {
        "nginx-rate-limiter", "rate-limiter", "rate limiter",
        "limit_req", "limitador de tasa", "rate limiting"
    },
    "nginx-tls-crypto-engine": {
        "nginx-tls-crypto-engine", "crypto-engine", "crypto engine",
        "motor criptografico", "cipher engine", "motor de cifrado"
    },
    "nginx-tls-termination": {
        "nginx-tls-termination", "tls-termination", "terminacion tls",
        "terminacion ssl", "ssl termination", "certificado tls", "tls certificate", "certificado ssl"
    },
    "network-infrastructure": {
        "network-infrastructure", "infraestructura de red", "tc netem",
        "tc-netem", "qdisc", "enlace de red", "interfaz de red", "network infrastructure"
    },
}


def _normalize_tokens(text: str) -> set[str]:
    """Normaliza texto técnico a un conjunto de tokens en minúscula sin tildes."""
    clean = _clean_text(text)
    words = re.findall(r"[a-z0-9_\-\.]+", clean)
    stopwords = {
        "el", "la", "los", "las", "un", "una", "de", "en", "para", "por",
        "con", "que", "y", "o", "a", "del", "the", "is", "of", "to", "and",
        "an", "in", "on", "at", "by", "se", "su", "al", "es", "no",
    }
    return set(w for w in words if w not in stopwords and len(w) > 1)


def calculate_token_similarity(text_a: str, text_b: str) -> float:
    """Calcula la similitud de Jaccard basada en tokens normalizados (acierto parcial)."""
    toks_a = _normalize_tokens(text_a)
    toks_b = _normalize_tokens(text_b)
    if not toks_a or not toks_b:
        return 0.0
    intersection = toks_a.intersection(toks_b)
    union = toks_a.union(toks_b)
    return round(len(intersection) / len(union), 4)


def check_root_cause_correct(
    predicted_root_cause: str,
    ground_truth_root_cause: str,
    fault_class: str,
    predicted_component: str = "",
    ground_truth_component: str = "",
) -> tuple[bool, float]:
    """
    Evaluación formal de causa raíz basada exclusivamente en fuentes oficiales (evaluator_concepts.yaml).

    Regla única universal:
      is_correct = (cumple >= 1 cause_group) AND (NO concluye clase vecina no-negada en 1ra oración) AND (NO es solo síntoma)

    Retorna: (is_correct: bool, partial_score: float 0.0..1.0).
    """
    if not predicted_root_cause or not str(predicted_root_cause).strip():
        return False, 0.0

    cleaned = _clean_text(predicted_root_cause)
    concepts_catalog = load_evaluator_concepts().get("classes", {})
    class_def = concepts_catalog.get(fault_class, {})

    cause_groups = class_def.get("cause_groups", [])
    cause_concepts = class_def.get("cause_concepts", [])
    neighbor_concepts = class_def.get("neighbor_concepts", [])
    symptom_only_terms = class_def.get("symptom_only_terms", [])

    # 1. ¿Nombra al menos un grupo de conceptos de causa raíz de la clase?
    has_cause = False
    if cause_groups:
        has_cause = any(_match_group(g, cleaned) for g in cause_groups)
    if not has_cause and cause_concepts:
        has_cause = any(_match_term(c, cleaned) for c in cause_concepts)

    # 2. ¿Concluye erróneamente un concepto de una clase vecina en la 1ra oración sin estar negado?
    first_sentence = _extract_first_sentence_of_root_cause(predicted_root_cause)
    has_neighbor = False
    for n in neighbor_concepts:
        if _match_term(n, first_sentence):
            if not _is_negated_in_sentence(n, first_sentence):
                has_neighbor = True
                break

    # 3. ¿Es solo un síntoma genérico / salida cruda de herramienta sin causa raíz identificada?
    is_symptom_only = any(_match_term(s, cleaned) for s in symptom_only_terms) and not has_cause

    # Regla única normativa
    is_correct = bool(has_cause and not has_neighbor and not is_symptom_only)

    # Puntuación parcial continua (0.0 .. 1.0)
    jaccard = calculate_token_similarity(predicted_root_cause, ground_truth_root_cause)
    comp_match = check_component_correct(
        predicted_component,
        ground_truth_component,
        context_text=predicted_root_cause
    )

    partial = 0.0
    if is_correct:
        partial += 0.5
    partial += min(jaccard / 0.5, 0.3)
    if comp_match:
        partial += 0.2
    partial = round(min(partial, 1.0), 4)

    return is_correct, partial


def check_component_correct(
    predicted: str,
    expected: str,
    context_text: str = "",
    scenario_id: str = ""
) -> bool:
    """
    Verifica si el componente predicho coincide con el esperado según la topología normativa.
    Exige términos distintivos y rechaza términos genéricos compartidos (Auditoría A4).
    """
    p = _clean_text(predicted)
    e = _clean_text(expected)
    if not p or not e:
        return False

    # Caso especial normativo: BIND9 recursivo que consulta un autoritativo remoto
    if "bind9-recursive-resolver" in e or "dns-srv" in scenario_id.lower() or e == "bind9-recursive-resolver":
        if "bind9-authoritative" in p or "autoritativo" in p:
            ctx_clean = _clean_text(context_text)
            if "remoto" in ctx_clean or "remota" in ctx_clean or "remote" in ctx_clean:
                return True
            return False

    # Coincidencia exacta canónica
    if p == e:
        return True

    # Coincidencia exacta con normalización de guiones
    p_norm = p.replace("-", " ")
    e_norm = e.replace("-", " ")
    if p_norm == e_norm:
        return True

    # Verificación mediante alias distintivos exclusivos del componente esperado
    aliases = _COMPONENT_ALIASES.get(expected, set())
    clean_aliases = {_clean_text(a) for a in aliases}

    for alias in clean_aliases:
        if _match_term(alias, p):
            return True

    return False


def evaluate_explanation_rubric(
    explanation: str,
    root_cause_correct: bool,
    component_correct: bool,
    evidence_backed: bool,
    rubric_penalty: float = 0.0
) -> float:
    """
    Rúbrica de evaluación de calidad de explicación (0.0 a 5.0):
    - Fundamentación técnica y causa raíz: hasta 2.0 pts
    - Aislamiento de componente y mitigación: hasta 1.5 pts
    - Sustentación con evidencia empírica de red: hasta 1.0 pts
    - Claridad y concisión: hasta 0.5 pts
    Penalización: si un comando de herramienta fue bloqueado/rechazado y el reintento falló,
    se resta exactamente 1.0 punto a la rúbrica (mínimo 0.0).
    """
    if not explanation or not str(explanation).strip():
        return 0.0

    score = 0.0

    if root_cause_correct:
        score += 2.0
    else:
        score += 0.5

    if component_correct:
        score += 1.5
    else:
        score += 0.5

    if evidence_backed:
        score += 1.0

    exp_words = len(explanation.split())
    if 30 <= exp_words <= 400:
        score += 0.5
    elif exp_words > 10:
        score += 0.25

    if rubric_penalty > 0.0:
        score = max(0.0, score - rubric_penalty)

    return round(min(score, 5.0), 2)


def estimate_energy_and_carbon(
    total_time_ms: float,
    vram_peak_gb: float,
    cpu_percent_avg: float = 50.0,
    country_carbon_intensity_kg_per_kwh: float = 0.280
) -> tuple[float, float]:
    """
    Estima el consumo de energía (kWh) y emisiones de CO2 (kg) siguiendo el modelo
    dinámico de potencia multi-componente calibrado (Henríquez Miranda et al., 2026).
    """
    hours = total_time_ms / (1000.0 * 3600.0)

    p_base_watts = 35.0
    cpu_util = max(0.0, min(100.0, cpu_percent_avg)) / 100.0
    p_cpu_watts = 15.0 + (cpu_util * 45.0)

    vram_ratio = max(0.1, min(1.0, vram_peak_gb / 8.0))
    p_gpu_watts = 25.0 + (vram_ratio * 65.0)

    total_watts = p_base_watts + p_cpu_watts + p_gpu_watts
    kwh = (total_watts * hours) / 1000.0
    co2_kg = kwh * country_carbon_intensity_kg_per_kwh

    return round(kwh, 8), round(co2_kg, 8)
