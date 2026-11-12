"""
NetDiagBench-L7: Layer 7 - Cálculo Normativo Unificado del Puntaje Compuesto Multicriterio
Implementa la ponderación estandarizada 40/20/20/20, el filtrado previo por umbral de exactitud (>= 70%),
y la gestión de estados normativos de evaluación:
- COMPLETE_MEASURED
- PROVISIONAL_ESTIMATED
- PENDING_HUMAN_EVALUATION
- PENDING_VRAM_MEASUREMENT
- INELIGIBLE_ACCURACY
"""

import math
from typing import Any

# Valores oficiales de VRAM declarada / estimada (configs/models.yaml)
OFFICIAL_DECLARED_VRAM_GB: dict[str, float] = {
    "glm-4-9b-chat": 5.9,
    "qwen3-8b": 5.5,
    "phi-4-mini-instruct": 2.8,
}

# Umbral normativo de viabilidad técnica (70.0%)
ACCURACY_THRESHOLD_PCT: float = 70.0

# Ponderaciones multicriterio normativas (Sección 2)
WEIGHTS: dict[str, float] = {
    "accuracy": 0.40,
    "rubric": 0.20,
    "speed": 0.20,
    "vram_efficiency": 0.20,
}

# Estados normativos de evaluación (Sección 2)
STATE_COMPLETE_MEASURED = "COMPLETE_MEASURED"
STATE_PROVISIONAL_ESTIMATED = "PROVISIONAL_ESTIMATED"
STATE_PENDING_HUMAN_EVAL = "PENDING_HUMAN_EVALUATION"
STATE_PENDING_VRAM = "PENDING_VRAM_MEASUREMENT"
STATE_INELIGIBLE_ACCURACY = "INELIGIBLE_ACCURACY"


def calculate_model_composite_scores(
    models_summary: dict[str, dict[str, Any]],
    threshold_pct: float = ACCURACY_THRESHOLD_PCT,
) -> dict[str, dict[str, Any]]:
    """
    Calcula el puntaje compuesto normalizado para cada modelo según la ponderación 40/20/20/20:
    - Precisión diagnóstica (40%): A = acc / 100.0
    - Rúbrica explicativa (20%): R = rub / 5.0
    - Velocidad de decodificación (20%): V = tok_s / max(tok_s)
    - Eficiencia de VRAM (20%): M = min(vram) / vram

    Fórmula:
    S = 0.40 * A + 0.20 * R + 0.20 * V + 0.20 * M

    Aplica primero el umbral de viabilidad técnica (accuracy >= 70.0%) ANTES
    de determinar la elegibilidad.

    Si falta medición real de VRAM:
    - Conserva la estimación separada.
    - NO redistribuye el 20%.
    - Clasifica el estado: COMPLETE_MEASURED, PROVISIONAL_ESTIMATED, PENDING_HUMAN_EVALUATION,
      PENDING_VRAM_MEASUREMENT o INELIGIBLE_ACCURACY.
    - Un puntaje estimado nunca se presenta como medido (puntaje_compuesto = null).
    """
    if not models_summary:
        return {}

    # 1. Normalizador de velocidad
    valid_speeds = [
        float(m.get("tokens_per_sec", 0.0) or 0.0)
        for m in models_summary.values()
        if m.get("tokens_per_sec") is not None and not math.isnan(float(m.get("tokens_per_sec", 0.0)))
    ]
    max_tok_s = max(valid_speeds) if valid_speeds and max(valid_speeds) > 0 else 1.0

    # 2. Normalizador de VRAM medida físicamente
    valid_vrams_measured = [
        float(m.get("vram_peak_gb") or m.get("vram_gb") or 0.0)
        for m in models_summary.values()
        if m.get("vram_measurement_valid") is True
        and (m.get("vram_peak_gb") or m.get("vram_gb")) is not None
        and float(m.get("vram_peak_gb") or m.get("vram_gb") or 0.0) > 0.0
    ]
    min_vram_measured = min(valid_vrams_measured) if valid_vrams_measured else 1.0

    # 3. Normalizador de VRAM estimada (provisional)
    valid_vrams_estimated = []
    for mid, m in models_summary.items():
        v = m.get("vram_estimated_gb")
        if v is None or (isinstance(v, float) and math.isnan(v)) or float(v or 0.0) <= 0.0:
            v = m.get("vram_declared_gb") or OFFICIAL_DECLARED_VRAM_GB.get(mid)
        if v is not None and not (isinstance(v, float) and math.isnan(v)) and float(v) > 0.0:
            valid_vrams_estimated.append(float(v))
    min_vram_estimated = min(valid_vrams_estimated) if valid_vrams_estimated else 1.0

    results: dict[str, dict[str, Any]] = {}

    for model_id, m in models_summary.items():
        acc_raw = m.get("accuracy_pct", m.get("acc"))
        rub_raw = m.get("rubric", m.get("rub", m.get("rubric_score")))
        spd_raw = m.get("tokens_per_sec", m.get("tok_s"))
        vrm_peak_raw = m.get("vram_peak_gb", m.get("vram_gb", m.get("vram")))
        vrm_valid = bool(m.get("vram_measurement_valid", False))

        # Prioridad de selección VRAM (Auditoría VRAM):
        # 1. Estimación específica del modelo, si dispone de procedencia verificable.
        # 2. VRAM declarada en configs/models.yaml, mediante approx_vram_gb / OFFICIAL_DECLARED_VRAM_GB.
        # 3. Si ninguno está disponible, registrar NA.
        vrm_est_raw = m.get("vram_estimated_gb")
        vram_origin = "estimated"
        if vrm_est_raw is None or (isinstance(vrm_est_raw, float) and math.isnan(vrm_est_raw)) or float(vrm_est_raw or 0.0) <= 0:
            vrm_est_raw = m.get("vram_declared_gb") or OFFICIAL_DECLARED_VRAM_GB.get(model_id)
            vram_origin = "declared" if vrm_est_raw is not None else "NA"

        missing_fields = []
        if acc_raw is None or math.isnan(float(acc_raw)):
            missing_fields.append("precisión")
        if spd_raw is None or math.isnan(float(spd_raw)):
            missing_fields.append("velocidad")

        if missing_fields:
            results[model_id] = {
                "model_id": model_id,
                "accuracy_pct": float(acc_raw) if acc_raw is not None else None,
                "rubric": float(rub_raw) if rub_raw is not None else None,
                "tokens_per_sec": float(spd_raw) if spd_raw is not None else None,
                "vram_gb": None,
                "vram_peak_gb": None,
                "vram_estimated_gb": None,
                "puntaje_precision": 0.0,
                "puntaje_rubrica": 0.0,
                "puntaje_velocidad": 0.0,
                "puntaje_vram": None,
                "puntaje_compuesto": None,
                "puntaje_compuesto_medido": None,
                "puntaje_compuesto_provisional": None,
                "subtotal_validado": 0.0,
                "subtotal_parcial_sin_vram": 0.0,
                "is_definitive_ranking": False,
                "elegibilidad": False,
                "motivo_exclusion": f"Medición requerida no disponible: {', '.join(missing_fields)}",
                "estado_evaluacion": STATE_INELIGIBLE_ACCURACY,
                "estado_mediciones": {
                    "precision": "no_disponible" if "precisión" in missing_fields else "valida",
                    "rubrica": "no_disponible",
                    "velocidad": "no_disponible" if "velocidad" in missing_fields else "valida",
                    "vram": "no_disponible",
                },
                "observacion_tecnica": "Datos insuficientes para evaluación diagnóstica.",
            }
            continue

        acc = float(acc_raw)
        spd = float(spd_raw)
        rub = float(rub_raw) if (rub_raw is not None and not math.isnan(float(rub_raw))) else None

        # 1. Regla obligatoria: Umbral estricto del 70.0% de exactitud
        if acc < threshold_pct:
            elegible = False
            motivo = f"Exactitud diagnóstica ({acc:.1f}%) inferior al umbral mínimo del {threshold_pct:.1f}%"
            estado_eval = STATE_INELIGIBLE_ACCURACY
        else:
            elegible = True
            motivo = ""
            estado_eval = STATE_COMPLETE_MEASURED

        # 2. Normalización de componentes A, R, V
        norm_acc = min(max(acc / 100.0, 0.0), 1.0)
        norm_spd = min(max(spd / max_tok_s, 0.0), 1.0) if max_tok_s > 0 else 0.0
        p_acc = round(WEIGHTS["accuracy"] * norm_acc, 4)
        p_spd = round(WEIGHTS["speed"] * norm_spd, 4)

        if rub is not None:
            norm_rub = min(max(rub / 5.0, 0.0), 1.0)
            p_rub = round(WEIGHTS["rubric"] * norm_rub, 4)
            estado_rub = "valida"
        else:
            p_rub = 0.0
            norm_rub = 0.0
            estado_rub = "pendiente"
            if elegible:
                estado_eval = STATE_PENDING_HUMAN_EVAL

        subtotal_validado = round(p_acc + p_rub + p_spd, 4)

        # 3. Tratamiento de VRAM medida vs. estimada (sin redistribución del 20%)
        p_vrm_medido = None
        p_vrm_estimado = None
        p_comp_medido = None
        p_comp_provisional = None
        vrm_val_reported = None

        has_valid_vram = (
            vrm_valid
            and vrm_peak_raw is not None
            and not math.isnan(float(vrm_peak_raw))
            and float(vrm_peak_raw) > 0
        )

        if has_valid_vram:
            vrm_val_reported = float(vrm_peak_raw)
            norm_vrm = min(max(min_vram_measured / max(vrm_val_reported, 0.1), 0.0), 1.0)
            p_vrm_medido = round(WEIGHTS["vram_efficiency"] * norm_vrm, 4)
            if rub is not None and elegible:
                p_comp_medido = round(p_acc + p_rub + p_spd + p_vrm_medido, 4)
                estado_eval = STATE_COMPLETE_MEASURED
            estado_vrm = "medida"
            obs_tecnica = ""
        else:
            # Medición real de VRAM no disponible (física)
            estado_vrm = vram_origin if vram_origin in ("declared", "estimated") else "no_disponible"
            if vrm_est_raw is not None and not math.isnan(float(vrm_est_raw)) and float(vrm_est_raw) > 0:
                vrm_est = float(vrm_est_raw)
                norm_vrm_est = min(max(min_vram_estimated / max(vrm_est, 0.1), 0.0), 1.0)
                p_vrm_estimado = round(WEIGHTS["vram_efficiency"] * norm_vrm_est, 4)
                p_comp_provisional = round(p_acc + p_rub + p_spd + p_vrm_estimado, 4)
                if elegible and rub is not None:
                    estado_eval = STATE_PROVISIONAL_ESTIMATED
                obs_tecnica = (
                    "Puntaje compuesto definitivo no calculable por ausencia de sensor físico de VRAM dedicada. "
                    "Se conserva estimación separada con estado PROVISIONAL_ESTIMATED. "
                    "El peso normativo del 20% no se redistribuye a otros componentes."
                )
            else:
                if elegible and rub is not None:
                    estado_eval = STATE_PENDING_VRAM
                obs_tecnica = (
                    "Puntaje compuesto no calculable por limitación de hardware: Ausencia de sensor físico de VRAM dedicada. "
                    "El peso normativo del 20% no se redistribuye a otros componentes."
                )

        # Un puntaje estimado NUNCA se presenta como medido
        puntaje_compuesto_publicable = p_comp_medido

        results[model_id] = {
            "model_id": model_id,
            "accuracy_pct": acc,
            "rubric": rub,
            "tokens_per_sec": spd,
            "vram_gb": vrm_val_reported,
            "vram_peak_gb": vrm_val_reported,
            "vram_estimated_gb": float(vrm_est_raw) if (vrm_est_raw is not None and not math.isnan(float(vrm_est_raw))) else None,
            "vram_status": estado_vrm,
            "vram_measurement_valid": has_valid_vram,
            "puntaje_precision": p_acc,
            "puntaje_rubrica": p_rub,
            "puntaje_velocidad": p_spd,
            "puntaje_vram": p_vrm_medido,
            "puntaje_vram_estimado": p_vrm_estimado,
            "puntaje_compuesto": puntaje_compuesto_publicable,
            "puntaje_compuesto_medido": p_comp_medido,
            "puntaje_compuesto_provisional": p_comp_provisional,
            "subtotal_validado": subtotal_validado,
            "subtotal_parcial_sin_vram": subtotal_validado,
            "is_definitive_ranking": bool(has_valid_vram and elegible and (rub is not None)),
            "elegibilidad": elegible,
            "motivo_exclusion": motivo,
            "estado_evaluacion": estado_eval,
            "estado_mediciones": {
                "precision": "valida",
                "rubrica": estado_rub,
                "velocidad": "valida",
                "vram": estado_vrm,
            },
            "observacion_tecnica": obs_tecnica,
        }

    return results


def rank_models_by_composite_score(
    scored_models: dict[str, dict[str, Any]]
) -> tuple[list[str], list[str]]:
    """
    Ordena los modelos según su estado y puntaje compuesto:
    1. ranking_elegibles: Modelos elegibles (exactitud >= 70%) ordenados por puntaje compuesto medido
       (o por subtotal validado si la medición física de VRAM está pendiente).
    2. ranking_excluidos: Modelos excluidos (< 70%) ordenados por exactitud descendente.
    """
    elegibles = []
    for mid, data in scored_models.items():
        if data.get("elegibilidad") is True:
            # Preferir puntaje compuesto medido; si no está disponible, ordenar por subtotal validado
            score = data.get("puntaje_compuesto")
            if score is None:
                score = data.get("subtotal_validado", 0.0)
            elegibles.append((mid, score, data.get("accuracy_pct", 0.0) or 0.0))

    elegibles.sort(key=lambda x: (x[1], x[2]), reverse=True)

    excluidos = [
        (mid, data.get("accuracy_pct", 0.0) or 0.0)
        for mid, data in scored_models.items()
        if not data.get("elegibilidad")
    ]
    excluidos.sort(key=lambda x: x[1], reverse=True)

    return [x[0] for x in elegibles], [x[0] for x in excluidos]
