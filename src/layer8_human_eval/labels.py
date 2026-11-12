"""
NetDiagBench-L7: Layer 8 - Etiquetas y Autenticación de Expertos (labels.py)
Genera y valida contratos EtiquetaExperto para evaluadores independientes (A, B)
y dirimente (C), gestionando códigos de acceso, semillas de barajado y huellas SHA-256.
"""

import hashlib
import json
import random
import secrets
from datetime import UTC, datetime
from pathlib import Path

from src.core.contracts import EtiquetaExperto
from src.core.logger import logger
from src.layer7_evaluator.metrics import get_evaluator_version

DEFAULT_SEEDS = {
    "A": 11,
    "B": 22,
    "C": 33,
}

DEFAULT_ROLES = {
    "A": "evaluador",
    "B": "evaluador",
    "C": "dirimente",
}

DEFAULT_ALIASES = {
    "A": "Evaluador Experto A",
    "B": "Evaluador Experto B",
    "C": "Evaluador Experto C (Dirimente)",
}


def compute_huella(sesion_id: str, expert_id: str, orden: list[str], version_evaluador: str) -> str:
    """
    Calcula el hash criptográfico SHA-256 que sella la etiqueta del experto.
    huella_sha256 = SHA-256 de (sesion_id, expert_id, orden, version_evaluador)
    """
    raw = f"{sesion_id}:{expert_id}:{','.join(orden)}:{version_evaluador}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def verify_etiqueta_integrity(etiqueta: EtiquetaExperto, version_evaluador: str | None = None) -> bool:
    """
    Verifica que la huella_sha256 de la etiqueta coincida exactamente con los datos contenidos.
    Si fue alterada o manipulada, retorna False.
    """
    if version_evaluador is None:
        version_evaluador = get_evaluator_version()
    expected = compute_huella(
        sesion_id=etiqueta.sesion_id,
        expert_id=etiqueta.expert_id,
        orden=etiqueta.orden,
        version_evaluador=version_evaluador,
    )
    return etiqueta.huella_sha256 == expected


def generate_expert_label(
    expert_id: str,
    sesion_id: str,
    codes: list[str],
    semilla_orden: int | None = None,
    alias: str | None = None,
    version_evaluador: str | None = None,
) -> EtiquetaExperto:
    """
    Emite una EtiquetaExperto formal con orden pseudoaleatorio barajado y código de acceso seguro.
    """
    if expert_id not in ("A", "B", "C"):
        raise ValueError(f"expert_id debe ser 'A', 'B' o 'C', recibido: {expert_id}")

    if semilla_orden is None:
        semilla_orden = DEFAULT_SEEDS[expert_id]

    if alias is None:
        alias = DEFAULT_ALIASES[expert_id]

    if version_evaluador is None:
        version_evaluador = get_evaluator_version()

    # Barajar el orden de los códigos con la semilla del experto
    shuffled_order = list(codes)
    rng = random.Random(semilla_orden)
    rng.shuffle(shuffled_order)

    # Código de acceso seguro de 8 caracteres alfanuméricos en mayúsculas
    codigo_acceso = secrets.token_hex(4).upper()

    # Huella criptográfica
    huella = compute_huella(
        sesion_id=sesion_id,
        expert_id=expert_id,
        orden=shuffled_order,
        version_evaluador=version_evaluador,
    )

    etiqueta = EtiquetaExperto(
        expert_id=expert_id,
        rol=DEFAULT_ROLES[expert_id],
        alias=alias,
        sesion_id=sesion_id,
        fecha_emision=datetime.now(UTC).isoformat(),
        semilla_orden=semilla_orden,
        orden=shuffled_order,
        codigo_acceso=codigo_acceso,
        huella_sha256=huella,
    )
    return etiqueta


def save_etiquetas(etiquetas: dict[str, EtiquetaExperto], output_dir: Path) -> Path:
    """
    Guarda el diccionario de etiquetas en data/human_eval/<sesion>/etiquetas.json.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    out_file = output_dir / "etiquetas.json"
    data = {k: v.model_dump() for k, v in etiquetas.items()}
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return out_file


def load_etiquetas(etiquetas_path: Path) -> dict[str, EtiquetaExperto]:
    """
    Carga las etiquetas emitidas desde su archivo JSON.
    """
    if not etiquetas_path.exists():
        raise FileNotFoundError(f"Archivo de etiquetas no encontrado: {etiquetas_path}")

    with open(etiquetas_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    result: dict[str, EtiquetaExperto] = {}
    for k, v in data.items():
        result[k] = EtiquetaExperto.model_validate(v)
    return result


def verify_expert_submission(
    expert_id: str,
    codigo_acceso: str,
    huella_sha256: str,
    etiquetas_path: Path,
    version_evaluador: str | None = None,
) -> tuple[bool, str]:
    """
    Valida las credenciales e integridad del libro entregado por un experto contra la etiqueta oficial.
    Retorna (True, 'OK') o (False, mensaje_error).
    """
    try:
        etiquetas = load_etiquetas(etiquetas_path)
    except Exception as e:
        return False, f"No se pudo cargar el archivo de etiquetas oficial: {e}"

    if expert_id not in etiquetas:
        return False, f"Experto '{expert_id}' no registrado en la sesión"

    etiqueta_oficial = etiquetas[expert_id]

    # 1. Validar código de acceso
    if etiqueta_oficial.codigo_acceso.strip().upper() != codigo_acceso.strip().upper():
        return False, f"Código de acceso inválido para experto {expert_id}"

    # 2. Validar huella SHA-256 del libro contra la oficial
    if etiqueta_oficial.huella_sha256.strip().lower() != huella_sha256.strip().lower():
        return False, f"Huella SHA-256 alterada o no coincide con la etiqueta emitida para experto {expert_id}"

    # 3. Validar integridad interna de la etiqueta oficial
    if not verify_etiqueta_integrity(etiqueta_oficial, version_evaluador):
        return False, f"La etiqueta oficial del experto {expert_id} presenta discrepancia de huella"

    return True, "Credenciales y huella verificadas satisfactoriamente"
