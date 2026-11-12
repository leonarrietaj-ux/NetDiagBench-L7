"""
NetDiagBench-L7: Layer 8 - Importador y Validador de Respuestas de Expertos (importer.py)
Importa libros Instrumento_Experto_<ID>_<sesion>.xlsx, valida credenciales contra la
etiqueta oficial, rangos de escala (C1-C6, S, U), observaciones obligatorias y completitud (54/54).
Guarda las respuestas validadas en data/human_eval/<sesion>/respuestas_<ID>.csv.
"""

import csv
from pathlib import Path
from typing import Any

import openpyxl

from src.core.logger import logger
from src.layer8_human_eval.agreement import round_rubric
from src.layer8_human_eval.labels import (
    load_etiquetas,
    verify_expert_submission,
)


def normalize_s_value(val: Any) -> str:
    """Normaliza respuestas de Sustentación a 'Sí' o 'No'."""
    if val is None:
        return ""
    v_str = str(val).strip().lower()
    if v_str in ("sí", "si", "s", "yes", "true", "1"):
        return "Sí"
    elif v_str in ("no", "n", "false", "0"):
        return "No"
    return str(val).strip()


def validate_response_row(row_dict: dict[str, Any], row_idx: int) -> dict[str, Any]:
    """
    Valida tipos, rangos y consistencia lógica de una fila de evaluación:
    - C1 a C6: enteros en {0, 1, 2}
    - S: 'Sí' o 'No'
    - U: entero en {1, 2, 3, 4, 5}
    - Observación: obligatoria si C1 = 0 o S = 'No'
    """
    codigo = str(row_dict.get("codigo", "")).strip()
    if not codigo:
        raise ValueError(f"Fila {row_idx}: Código de evaluación vacío")

    # Validar C1..C6
    int_fields = ["c1", "c2", "c3", "c4", "c5", "c6"]
    parsed_ints: dict[str, int] = {}
    for f in int_fields:
        val = row_dict.get(f)
        if val is None or str(val).strip() == "":
            raise ValueError(f"Fila {row_idx} ({codigo}): El campo {f.upper()} está vacío")
        try:
            val_int = int(float(str(val).strip()))
        except ValueError:
            raise ValueError(f"Fila {row_idx} ({codigo}): {f.upper()} debe ser numérico (0, 1 o 2), valor recibido: '{val}'")
        if val_int not in (0, 1, 2):
            raise ValueError(f"Fila {row_idx} ({codigo}): {f.upper()} fuera de rango ({val_int}). Debe ser 0, 1 o 2")
        parsed_ints[f] = val_int

    # Validar S
    raw_s = row_dict.get("s")
    s_norm = normalize_s_value(raw_s)
    if s_norm not in ("Sí", "No"):
        raise ValueError(f"Fila {row_idx} ({codigo}): S debe ser 'Sí' o 'No', valor recibido: '{raw_s}'")

    # Validar U
    raw_u = row_dict.get("u")
    if raw_u is None or str(raw_u).strip() == "":
        raise ValueError(f"Fila {row_idx} ({codigo}): U (Utilidad operativa) está vacío")
    try:
        u_int = int(float(str(raw_u).strip()))
    except ValueError:
        raise ValueError(f"Fila {row_idx} ({codigo}): U debe ser entero de 1 a 5, recibido: '{raw_u}'")
    if u_int not in (1, 2, 3, 4, 5):
        raise ValueError(f"Fila {row_idx} ({codigo}): U fuera de rango ({u_int}). Debe ser de 1 a 5")

    # Validar Observación obligatoria
    obs = str(row_dict.get("observacion", "") or "").strip()
    if parsed_ints["c1"] == 0 and not obs:
        raise ValueError(f"Fila {row_idx} ({codigo}): La columna 'Observación' es obligatoria cuando C1 = 0")
    if s_norm == "No" and not obs:
        raise ValueError(f"Fila {row_idx} ({codigo}): La columna 'Observación' es obligatoria cuando S = No")

    # Calcular rúbrica: suma(C2..C5) / 8 * 5
    suma_c2_c5 = parsed_ints["c2"] + parsed_ints["c3"] + parsed_ints["c4"] + parsed_ints["c5"]
    rubrica = round_rubric(suma_c2_c5)

    return {
        "codigo": codigo,
        "c1": parsed_ints["c1"],
        "c2": parsed_ints["c2"],
        "c3": parsed_ints["c3"],
        "c4": parsed_ints["c4"],
        "c5": parsed_ints["c5"],
        "c6": parsed_ints["c6"],
        "s": s_norm,
        "u": u_int,
        "observacion": obs,
        "rubrica": rubrica,
    }


def import_expert_responses(
    xlsx_path: Path,
    sesion_id: str,
    etiquetas_path: Path,
    version_evaluador: str | None = None,
    output_dir: Path | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """
    Importa y valida el libro Excel de respuestas entregado por un experto.
    Verifica credenciales, rangos y completitud de las 54 corridas (o corridas dirimentes para C).
    Guarda las respuestas en data/human_eval/<sesion>/respuestas_<ID>.csv.
    """
    if not xlsx_path.exists():
        raise FileNotFoundError(f"Archivo no encontrado: {xlsx_path}")

    wb = openpyxl.load_workbook(xlsx_path, data_only=True)

    # 1. Extraer credenciales de la hoja Instrucciones
    if "Instrucciones" not in wb.sheetnames:
        raise ValueError("El archivo Excel no contiene la hoja obligatoria 'Instrucciones'")

    ws_inst = wb["Instrucciones"]
    # Buscar celdas con Identificador, Código de acceso y Huella
    expert_id = ""
    codigo_acceso = ""
    huella_sha256 = ""

    for r in range(4, 15):
        lbl = str(ws_inst.cell(row=r, column=1).value or "").strip().lower()
        val = str(ws_inst.cell(row=r, column=2).value or "").strip()
        if "identificador del experto" in lbl or "experto" in lbl:
            expert_id = val
        elif "código de acceso" in lbl or "codigo de acceso" in lbl:
            codigo_acceso = val
        elif "huella" in lbl:
            huella_sha256 = val

    if not expert_id:
        raise ValueError("No se pudo identificar el 'Identificador del Experto' en la hoja Instrucciones")

    # 2. Validar credenciales contra la etiqueta oficial registrada
    ok, msg = verify_expert_submission(
        expert_id=expert_id,
        codigo_acceso=codigo_acceso,
        huella_sha256=huella_sha256,
        etiquetas_path=etiquetas_path,
        version_evaluador=version_evaluador,
    )
    if not ok:
        raise PermissionError(f"Validación de autenticidad fallida para el evaluador {expert_id}: {msg}")

    # Cargar etiqueta oficial para validar cantidad de corridas asignadas
    etiquetas = load_etiquetas(etiquetas_path)
    etiqueta_oficial = etiquetas[expert_id]
    expected_count = len(etiqueta_oficial.orden)

    # 3. Leer y validar respuestas de la hoja Evaluación
    if "Evaluación" not in wb.sheetnames:
        raise ValueError("El archivo Excel no contiene la hoja obligatoria 'Evaluación'")

    ws_eval = wb["Evaluación"]

    # Detectar mapeo de columnas dinámicamente desde la fila 4 de cabeceras
    col_map: dict[str, int] = {}
    for c_idx in range(1, 30):
        val = ws_eval.cell(row=4, column=c_idx).value
        if not val:
            continue
        h_lower = str(val).strip().lower()
        if h_lower in ("código", "codigo"):
            col_map["codigo"] = c_idx
        elif h_lower in ("c1", "causa raíz", "causa raiz"):
            col_map["c1"] = c_idx
        elif h_lower in ("c2", "coherencia técnica", "coherencia tecnica"):
            col_map["c2"] = c_idx
        elif h_lower in ("c3", "fundamentación normativa", "fundamentacion"):
            col_map["c3"] = c_idx
        elif h_lower in ("c4", "componente"):
            col_map["c4"] = c_idx
        elif h_lower in ("c5", "mitigación", "mitigacion"):
            col_map["c5"] = c_idx
        elif h_lower in ("c6", "exactitud factual"):
            col_map["c6"] = c_idx
        elif h_lower in ("s", "sustentado"):
            col_map["s"] = c_idx
        elif h_lower in ("u", "utilidad"):
            col_map["u"] = c_idx
        elif h_lower in ("observación", "observacion", "obs"):
            col_map["observacion"] = c_idx

    # Si no se detectaron todas las columnas, usar la disposición ciega estándar (C1 en col 5) o legado (C1 en col 7)
    if "c1" not in col_map:
        c1_in_5 = str(ws_eval.cell(row=4, column=5).value or "").strip().upper()
        if c1_in_5 == "C1":
            col_map = {"codigo": 2, "c1": 5, "c2": 6, "c3": 7, "c4": 8, "c5": 9, "c6": 10, "s": 11, "u": 12, "observacion": 13}
        else:
            col_map = {"codigo": 2, "c1": 7, "c2": 8, "c3": 9, "c4": 10, "c5": 11, "c6": 12, "s": 13, "u": 14, "observacion": 15}

    parsed_rows: list[dict[str, Any]] = []

    # Las corridas inician en fila 5
    for row_idx in range(5, 5 + expected_count):
        code_col = col_map.get("codigo", 2)
        code_val = ws_eval.cell(row=row_idx, column=code_col).value
        if code_val is None or str(code_val).strip() == "":
            break

        row_raw = {
            "codigo": str(code_val).strip(),
            "c1": ws_eval.cell(row=row_idx, column=col_map["c1"]).value,
            "c2": ws_eval.cell(row=row_idx, column=col_map["c2"]).value,
            "c3": ws_eval.cell(row=row_idx, column=col_map["c3"]).value,
            "c4": ws_eval.cell(row=row_idx, column=col_map["c4"]).value,
            "c5": ws_eval.cell(row=row_idx, column=col_map["c5"]).value,
            "c6": ws_eval.cell(row=row_idx, column=col_map["c6"]).value,
            "s": ws_eval.cell(row=row_idx, column=col_map["s"]).value,
            "u": ws_eval.cell(row=row_idx, column=col_map["u"]).value,
            "observacion": ws_eval.cell(row=row_idx, column=col_map["observacion"]).value,
        }

        validated = validate_response_row(row_raw, row_idx)
        parsed_rows.append(validated)

    # Verificar que haya exactamente el número de corridas esperadas completadas (54 de 54 para A/B)
    if len(parsed_rows) != expected_count:
        raise ValueError(
            f"Evaluación incompleta: Se esperaban {expected_count} corridas completas para experto {expert_id}, "
            f"pero se procesaron {len(parsed_rows)} filas."
        )

    # 4. Guardar CSV en data/human_eval/<sesion>/respuestas_<ID>.csv conservando historial
    if output_dir is None:
        output_dir = etiquetas_path.parent

    output_dir.mkdir(parents=True, exist_ok=True)
    csv_file = output_dir / f"respuestas_{expert_id}.csv"

    # Si ya existe un archivo previo, respaldar con marca temporal para trazabilidad histórica
    if csv_file.exists():
        import shutil
        import datetime
        ts_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
        hist_file = output_dir / f"respuestas_{expert_id}_{ts_str}.bak.csv"
        try:
            shutil.copy2(csv_file, hist_file)
            logger.info(f"Historial conservado: {csv_file.name} respaldado en {hist_file.name}")
        except Exception as e:
            logger.warning(f"No se pudo crear copia de historial para {csv_file}: {e}")

    fieldnames = ["codigo", "c1", "c2", "c3", "c4", "c5", "c6", "s", "u", "observacion", "rubrica"]
    with open(csv_file, "w", newline="", encoding="utf-8") as f_out:
        writer = csv.DictWriter(f_out, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(parsed_rows)

    logger.info(f"Respuestas del experto {expert_id} guardadas exitosamente en {csv_file}")
    return expert_id, parsed_rows


# Alias para conveniencia de CLI e interfaz
import_responses = import_expert_responses

