"""
NetDiagBench-L7: Layer 8 - Gestor de Sesiones de Evaluación Humana (session.py)
Gestiona el ciclo de vida de las sesiones de evaluación ciega en data/human_eval/<sesion_id>.
Implementa las 10 fases formales de ciclo de vida y auditoría estricta de apertura de clave.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import secrets
from typing import Any

from src.core.config import PROJECT_ROOT
from src.core.logger import logger

HUMAN_EVAL_BASE_DIR = PROJECT_ROOT / "data" / "human_eval"
CURRENT_SESSION_FILE = HUMAN_EVAL_BASE_DIR / "CURRENT_SESSION.txt"

# Validación estricta de identificadores de sesión contra path traversal
SESSION_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")

# 10 Fases Formales del Ciclo de Vida de la Sesión
PHASES = [
    "NO_INICIALIZADA",
    "INICIALIZADA",
    "KITS_GENERADOS",
    "A_ENTREGADO",
    "B_ENTREGADO",
    "EVALUACIONES_IMPORTADAS",
    "ADJUDICACION_REQUERIDA",
    "ADJUDICACION_COMPLETADA",
    "CONCORDANCIA_CALCULADA",
    "CLAVE_ABIERTA",
]


def get_base_dir() -> Path:
    HUMAN_EVAL_BASE_DIR.mkdir(parents=True, exist_ok=True)
    return HUMAN_EVAL_BASE_DIR


def validate_session_id(sesion_id: str, base_dir: Path | None = None) -> tuple[str, Path]:
    """
    Valida rigurosamente un identificador de sesión y previene ataques de path traversal.

    Reglas de validación:
    1. Debe ser una cadena no vacía ni conformada exclusivamente por espacios.
    2. Prohibidos separadores de ruta ('/' o '\\') y rutas absolutas.
    3. Prohibidas referencias relativas parentales ('.' o '..').
    4. Debe coincidir estrictamente con ^[a-zA-Z0-9_-]+$.
    5. La ruta resuelta debe quedar contenida de forma estricta y directa dentro de base_dir.

    Retorna una tupla (clean_session_id, resolved_path).
    Lanza ValueError si alguna validación falla.
    """
    if not isinstance(sesion_id, str):
        raise ValueError("El identificador de sesión debe ser una cadena de texto.")

    clean_id = sesion_id.strip()
    if not clean_id:
        raise ValueError("El identificador de sesión no puede estar vacío.")

    if "/" in clean_id or "\\" in clean_id:
        raise ValueError(
            f"El identificador de sesión '{clean_id}' contiene separadores de ruta no permitidos."
        )

    if clean_id in (".", "..") or ".." in clean_id:
        raise ValueError(
            f"El identificador de sesión '{clean_id}' contiene secuencias relativas no permitidas."
        )

    if not SESSION_ID_PATTERN.match(clean_id):
        raise ValueError(
            f"El identificador de sesión '{clean_id}' contiene caracteres no permitidos. "
            f"Solo se admiten caracteres alfanuméricos, guiones y guiones bajos (^[a-zA-Z0-9_-]+$)."
        )

    base = (base_dir or get_base_dir()).resolve()
    target_path = (base / clean_id).resolve()

    # Comprobar contención estricta en el directorio base
    try:
        rel = target_path.relative_to(base)
        if len(rel.parts) != 1 or rel.parts[0] != clean_id:
            raise ValueError(
                f"Intento de path traversal detectado: '{sesion_id}' no resuelve como hijo directo de '{base}'."
            )
    except ValueError:
        raise ValueError(
            f"Intento de escape de directorio detectado: '{sesion_id}' resuelve fuera de '{base}'."
        )

    return clean_id, target_path


def generate_new_session_id(prefix: str = "SESION_") -> str:
    """
    Genera un identificador único, legible y criptográficamente seguro para una nueva sesión.
    Formato: SESION_YYYYMMDD_HHMMSS_<4 hex>
    """
    now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    rand_hex = secrets.token_hex(2)
    return f"{prefix}{now_str}_{rand_hex}"


def create_new_session_dir(
    sesion_id: str | None = None,
    base_dir: Path | None = None,
) -> tuple[str, Path]:
    """
    Crea de forma atómica y segura un nuevo directorio de sesión de evaluación humana.

    - Si sesion_id es None o vacío: genera un identificador único no colisionante.
    - Si sesion_id se proporciona: valida path traversal y verifica que NO exista previamente.
      Si ya existe, lanza FileExistsError para evitar sobrescritura accidental de datos.
    - No reemplaza ni altera claves, etiquetas, kits, respuestas ni auditorías de sesiones previas.

    Retorna (new_session_id, session_dir).
    """
    base = (base_dir or get_base_dir()).resolve()

    if sesion_id and str(sesion_id).strip():
        clean_id, s_dir = validate_session_id(sesion_id, base_dir=base)
        if s_dir.exists():
            raise FileExistsError(
                f"La sesión '{clean_id}' ya existe. La acción 'Nueva Sesión' rechaza identificadores "
                f"existentes para evitar la sobrescritura accidental de datos de sesiones previas."
            )
    else:
        # Generar identificador único garantizando ausencia de colisión
        while True:
            clean_id = generate_new_session_id()
            s_dir = (base / clean_id).resolve()
            if not s_dir.exists():
                break

    s_dir.mkdir(parents=True, exist_ok=False)
    return clean_id, s_dir


def set_active_session(sesion_id: str, base_dir: Path | None = None) -> None:
    """Registra la sesión activa en CURRENT_SESSION.txt tras validar su identificador."""
    clean_id, _ = validate_session_id(sesion_id, base_dir=base_dir)
    target_base = base_dir or get_base_dir()
    curr_file = target_base / "CURRENT_SESSION.txt" if base_dir else CURRENT_SESSION_FILE
    curr_file.write_text(clean_id, encoding="utf-8")


def get_active_session_id(fallback_create: bool = False, base_dir: Path | None = None) -> str:
    target_base = base_dir or HUMAN_EVAL_BASE_DIR
    curr_file = target_base / "CURRENT_SESSION.txt" if base_dir else CURRENT_SESSION_FILE

    if curr_file.exists():
        s_id = curr_file.read_text(encoding="utf-8").strip()
        if s_id:
            try:
                clean_id, s_dir = validate_session_id(s_id, base_dir=target_base)
                if s_dir.exists():
                    return clean_id
            except ValueError:
                pass

    # Buscar la sesión más reciente en el directorio (filtrando temporales de pruebas)
    sessions = list_sessions(base_dir=target_base)
    if sessions:
        latest = sessions[0]
        set_active_session(latest, base_dir=target_base)
        return latest

    if fallback_create:
        new_id, _ = create_new_session_dir(base_dir=target_base)
        set_active_session(new_id, base_dir=target_base)
        return new_id

    raise ValueError("No hay ninguna sesión de evaluación humana activa. Ejecute 'benchapp human-eval init' primero.")


def get_session_dir(
    sesion_id: str | None = None,
    fallback_create: bool = False,
    base_dir: Path | None = None,
) -> Path:
    target_base = base_dir or HUMAN_EVAL_BASE_DIR
    if not sesion_id or not str(sesion_id).strip():
        sesion_id = get_active_session_id(fallback_create=fallback_create, base_dir=target_base)

    clean_id, s_dir = validate_session_id(sesion_id, base_dir=target_base)
    if not s_dir.exists():
        if fallback_create:
            s_dir.mkdir(parents=True, exist_ok=True)
        else:
            raise FileNotFoundError(f"La sesión '{clean_id}' no existe en '{target_base}'.")
    return s_dir


def list_sessions(base_dir: Path | None = None) -> list[str]:
    base = base_dir or get_base_dir()
    if not base.exists():
        return []
    dirs = [
        d.name for d in base.iterdir()
        if d.is_dir() and not d.name.startswith(".") and not d.name.startswith("test_")
    ]
    return sorted(dirs, reverse=True)


def compute_session_phase(s_dir: Path, s_id: str) -> str:
    """Calcula deterministamente una de las 10 fases del ciclo de vida de la sesión."""
    clave_json = s_dir / "clave_RESTRINGIDA.json"
    etiquetas_json = s_dir / "etiquetas.json"
    audit_key_file = s_dir / "KEY_OPENED_AUDIT.json"

    # Si no tiene clave de cegamiento ni etiquetas, es una sesión no inicializada
    if not (clave_json.exists() and etiquetas_json.exists()):
        return "NO_INICIALIZADA"

    resp_a = s_dir / "respuestas_A.csv"
    resp_b = s_dir / "respuestas_B.csv"
    resp_c = s_dir / "respuestas_C.csv"

    count_a = _count_csv_rows(resp_a)
    count_b = _count_csv_rows(resp_b)
    count_c = _count_csv_rows(resp_c)

    has_agreement = (
        (s_dir / f"Analisis_Concordancia_{s_id}.xlsx").exists()
        or (s_dir / "concordancia.json").exists()
    )

    inst_a = s_dir / f"Instrumento_Experto_A_{s_id}.xlsx"
    inst_b = s_dir / f"Instrumento_Experto_B_{s_id}.xlsx"
    inst_c = s_dir / f"Instrumento_Experto_C_{s_id}.xlsx"

    # Fase 10: CLAVE_ABIERTA (solo válida si audit_key_file existe y se satisfacen las precondiciones formales)
    if audit_key_file.exists() and count_a >= 54 and count_b >= 54 and has_agreement:
        if not inst_c.exists() or count_c > 0:
            return "CLAVE_ABIERTA"

    # Fase 9: CONCORDANCIA_CALCULADA
    if has_agreement:
        return "CONCORDANCIA_CALCULADA"

    # Fase 8: ADJUDICACION_COMPLETADA (C entregado)
    if resp_c.exists() and count_c > 0:
        return "ADJUDICACION_COMPLETADA"

    # Fase 7: ADJUDICACION_REQUERIDA (C emitido y pendiente)
    if inst_c.exists():
        return "ADJUDICACION_REQUERIDA"

    # Fase 6: EVALUACIONES_IMPORTADAS (A y B entregados completos)
    if count_a >= 54 and count_b >= 54:
        return "EVALUACIONES_IMPORTADAS"

    # Fase 4 y 5: Solo uno de los evaluadores titulares ha entregado
    if count_a >= 54 and count_b == 0:
        return "A_ENTREGADO"
    if count_b >= 54 and count_a == 0:
        return "B_ENTREGADO"

    # Fase 3: KITS_GENERADOS
    if inst_a.exists() and inst_b.exists():
        return "KITS_GENERADOS"

    # Fase 2: INICIALIZADA
    return "INICIALIZADA"


def get_session_state(sesion_id: str | None = None) -> dict[str, Any]:
    """Retorna un resumen estructurado del estado de la sesión."""
    try:
        s_dir = get_session_dir(sesion_id)
        s_id = s_dir.name
    except ValueError:
        return {
            "active": False,
            "sesion_id": None,
            "phase": "NO_INICIALIZADA",
            "is_key_opened": False,
        }

    clave_json = s_dir / "clave_RESTRINGIDA.json"
    etiquetas_json = s_dir / "etiquetas.json"
    audit_key_file = s_dir / "KEY_OPENED_AUDIT.json"

    phase = compute_session_phase(s_dir, s_id)
    is_key_opened = (phase == "CLAVE_ABIERTA")

    resp_a = s_dir / "respuestas_A.csv"
    resp_b = s_dir / "respuestas_B.csv"
    resp_c = s_dir / "respuestas_C.csv"

    inst_a = s_dir / f"Instrumento_Experto_A_{s_id}.xlsx"
    inst_b = s_dir / f"Instrumento_Experto_B_{s_id}.xlsx"
    inst_c = s_dir / f"Instrumento_Experto_C_{s_id}.xlsx"

    paq_a = s_dir / f"Paquete_Experto_A_{s_id}.html"
    paq_b = s_dir / f"Paquete_Experto_B_{s_id}.html"
    paq_c = s_dir / f"Paquete_Experto_C_{s_id}.html"

    # Conteo de respuestas importadas
    count_a = _count_csv_rows(resp_a)
    count_b = _count_csv_rows(resp_b)
    count_c = _count_csv_rows(resp_c)

    has_key = clave_json.exists()
    has_agreement = (
        (s_dir / f"Analisis_Concordancia_{s_id}.xlsx").exists()
        or (s_dir / "concordancia.json").exists()
    )
    has_correlation = (s_dir / f"Informe_Correlacion_{s_id}.html").exists()

    key_audit = None
    if audit_key_file.exists() and has_key:
        try:
            key_audit = json.loads(audit_key_file.read_text(encoding="utf-8"))
        except Exception:
            key_audit = None

    return {
        "active": has_key and etiquetas_json.exists(),
        "sesion_id": s_id,
        "phase": phase,
        "session_dir": str(s_dir),
        "has_key": has_key,
        "is_key_opened": is_key_opened,
        "key_opened_audit": key_audit,
        "has_etiquetas": etiquetas_json.exists(),
        "experts": {
            "A": {
                "emitted": inst_a.exists() and paq_a.exists(),
                "imported": resp_a.exists(),
                "completed_count": count_a,
                "xlsx_path": str(inst_a) if inst_a.exists() else None,
                "html_path": str(paq_a) if paq_a.exists() else None,
            },
            "B": {
                "emitted": inst_b.exists() and paq_b.exists(),
                "imported": resp_b.exists(),
                "completed_count": count_b,
                "xlsx_path": str(inst_b) if inst_b.exists() else None,
                "html_path": str(paq_b) if paq_b.exists() else None,
            },
            "C": {
                "emitted": inst_c.exists() and paq_c.exists(),
                "imported": resp_c.exists(),
                "completed_count": count_c,
                "xlsx_path": str(inst_c) if inst_c.exists() else None,
                "html_path": str(paq_c) if paq_c.exists() else None,
            },
        },
        "has_agreement": has_agreement,
        "has_correlation": has_correlation,
    }


def open_key_audit(
    sesion_id: str | None = None,
    reason: str = "Apertura formal de clave para análisis desglosados",
    strict: bool = True,
    base_dir: Path | None = None,
) -> dict[str, Any]:
    """
    Registra en la sesión la apertura de la clave de cegamiento con trazabilidad de auditoría.
    Exige cumplimiento estricto y mandatorio de las precondiciones metodológicas:
    1. Motivo de auditoría válido, no vacío y explícito.
    2. Clave de cegamiento existente (clave_RESTRINGIDA.json).
    3. Al menos 54 evaluaciones válidas y completas importadas del Evaluador A.
    4. Al menos 54 evaluaciones válidas y completas importadas del Evaluador B.
    5. Concordancia inter-evaluador calculada (concordancia.json o Analisis_Concordancia_<id>.xlsx).
    6. Si se emitió instrumento dirimente para C, se exigen las respuestas importadas de C.

    Si cualquier requisito no se cumple:
    - Lanza ValueError con detalle explícito.
    - NO crea ni altera KEY_OPENED_AUDIT.json.
    - La vista web permanece en estado restringido.
    """
    # 1. Validar existencia y formato de sesión
    try:
        s_dir = get_session_dir(sesion_id, base_dir=base_dir)
    except (FileNotFoundError, ValueError) as err:
        raise ValueError(
            f"Requisito metodológico incumplido: La sesión '{sesion_id}' no existe o no ha sido inicializada."
        ) from err
    s_id = s_dir.name

    # 2. Validar motivo de auditoría
    if not reason or not isinstance(reason, str) or not reason.strip():
        raise ValueError(
            "Requisito metodológico incumplido: Se requiere un motivo de auditoría válido y explícito "
            "para autorizar la apertura de la clave de cegamiento."
        )
    clean_reason = reason.strip()
    if len(clean_reason) < 5:
        raise ValueError(
            "Requisito metodológico incumplido: El motivo de auditoría debe ser explicativo y contener al menos 5 caracteres."
        )

    # 2. Validar que la sesión tenga clave de cegamiento
    clave_json = s_dir / "clave_RESTRINGIDA.json"
    if not clave_json.exists():
        raise ValueError(
            "Requisito metodológico incumplido: La sesión no ha sido inicializada con clave de cegamiento (falta clave_RESTRINGIDA.json)."
        )

    # 3. Validar evaluaciones completas de A y B
    count_a = _count_csv_rows(s_dir / "respuestas_A.csv")
    count_b = _count_csv_rows(s_dir / "respuestas_B.csv")
    if count_a < 54 or count_b < 54:
        raise ValueError(
            f"Requisito metodológico incumplido: Se requieren 54 evaluaciones completas de los evaluadores A y B "
            f"antes de abrir la clave (actual: Experto A={count_a}/54, Experto B={count_b}/54)."
        )

    # 4. Validar concordancia calculada
    has_agreement = (
        (s_dir / f"Analisis_Concordancia_{s_id}.xlsx").exists()
        or (s_dir / "concordancia.json").exists()
    )
    if not has_agreement:
        raise ValueError(
            "Requisito metodológico incumplido: Debe calcular y verificar la concordancia inter-evaluador "
            "antes de abrir la clave de cegamiento."
        )

    # 5. Validar respuestas del árbitro C si fue convocado
    inst_c = s_dir / f"Instrumento_Experto_C_{s_id}.xlsx"
    count_c = _count_csv_rows(s_dir / "respuestas_C.csv")
    if inst_c.exists() and count_c == 0:
        raise ValueError(
            "Requisito metodológico incumplido: Se emitió convocatoria para el árbitro dirimente C pero aún no se han importado sus respuestas."
        )

    # Solo si todas las precondiciones se cumplen, se crea el registro de auditoría
    audit_file = s_dir / "KEY_OPENED_AUDIT.json"
    audit_data = {
        "sesion_id": s_id,
        "fecha_apertura": datetime.now(timezone.utc).isoformat(),
        "motivo": clean_reason,
        "estado": "clave_abierta_analisis_desbloqueados",
        "evaluaciones_verificadas": {
            "A": count_a,
            "B": count_b,
            "C": count_c if inst_c.exists() else None,
        },
        "concordancia_verificada": True,
    }

    audit_file.write_text(
        json.dumps(audit_data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    logger.info(f"Clave de cegamiento abierta y auditada exitosamente para sesión {s_id}")
    return audit_data


def _count_csv_rows(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]
            return max(0, len(lines) - 1)
    except Exception:
        return 0
