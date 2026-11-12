"""
NetDiagBench-L7: Layer 8 - Muestreo Estratificado y Anonimización Ciega (sampler.py)
Selecciona una muestra estratificada de 54 corridas (18 escenarios x 3 modelos),
asigna códigos ciegos EV-001..EV-054 y anonimiza exhaustivamente diagnósticos y trazas.
"""

import json
import random
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from src.core.config import PROJECT_ROOT
from src.core.contracts import (
    ClaveCegamientoEntry,
    CorridaAnonimizada,
    EscenarioLabContract,
    FichaCiegaEvaluador,
)
from src.core.logger import logger
from src.layer1_lab.runner import ScenarioLabRunner

# Modelos oficiales de la terna del benchmark
OFFICIAL_MODELS = ["glm-4-9b-chat", "qwen3-8b", "phi-4-mini-instruct"]
AVAILABLE_SEEDS = [42, 1337, 2026]

# Palabras prohibidas que no deben fugarse a la vista de los evaluadores
FORBIDDEN_TERMS = [
    "qwen",
    "glm",
    "phi",
    "alibaba",
    "zhipu",
    "microsoft",
    "<think>",
    "</think>",
    "<thought>",
    "</thought>",
    "ttft",
    "tok/s",
    "vram",
    "is_correct",
]

# Expresiones regulares para anonimización
RE_THINK = re.compile(r"<(think|thought)>.*?</\1>", re.DOTALL | re.IGNORECASE)
RE_THINK_DANGLING = re.compile(r"<\/?(think|thought)>", re.IGNORECASE)
RE_MODELS = re.compile(r"\b(qwen\d*(-[a-z0-9]+)*|glm\d*(-[a-z0-9]+)*|phi\d*(-[a-z0-9]+)*|alibaba|zhipu|microsoft)\b", re.IGNORECASE)
RE_METRICS_LEAKS = re.compile(r"\b(ttft|tokens?\/s|tok\/s|vram|is_correct|rubric_score|partial_match_score)\b", re.IGNORECASE)


def anonymize_text(text: str) -> str:
    """
    Anonimiza exhaustivamente texto libre eliminando:
    1. Bloques de pensamiento CoT (<think>...</think>, <thought>...</thought>).
    2. Nombres de modelo o proveedores de la terna.
    3. Menciones a métricas internas del benchmark (TTFT, VRAM, is_correct, etc.).
    """
    if not text:
        return ""
    # 1. Eliminar bloques de pensamiento CoT
    cleaned = RE_THINK.sub("", text)
    cleaned = RE_THINK_DANGLING.sub("", cleaned)
    
    # 2. Reemplazar nombres de modelos por [MODELO]
    cleaned = RE_MODELS.sub("[MODELO]", cleaned)

    # 3. Eliminar posibles fugas residuales de tokens métricos
    cleaned = RE_METRICS_LEAKS.sub("[METRICA]", cleaned)

    # 4. Asegurar reemplazo estricto de cualquier subcadena prohibida remanente
    for term in ["qwen", "glm", "phi", "alibaba", "zhipu", "microsoft"]:
        pattern = re.compile(re.escape(term), re.IGNORECASE)
        cleaned = pattern.sub("[MODELO]", cleaned)

    for metric_term in ["ttft", "tok/s", "vram", "is_correct"]:
        pattern = re.compile(re.escape(metric_term), re.IGNORECASE)
        cleaned = pattern.sub("[METRICA]", cleaned)

    return cleaned.strip()


def check_forbidden_terms(content: str) -> list[str]:
    """
    Verifica si una cadena contiene alguna de las cadenas prohibidas
    del conjunto {'qwen', 'glm', 'phi', 'alibaba', 'zhipu', 'microsoft', '<think>', 'ttft', 'tok/s', 'vram', 'is_correct'}.
    Retorna la lista de términos encontrados (vacía si es completamente ciego).
    """
    if not content:
        return []
    content_lower = content.lower()
    found = []
    for term in FORBIDDEN_TERMS:
        if term in content_lower:
            found.append(term)
    return found


def extract_tool_steps(diagnostico: dict[str, Any], traza_path: Path | None = None) -> list[dict[str, str]]:
    """
    Extrae los pasos de ejecución de herramientas para la ficha del evaluador.
    Busca primero en traza.jsonl si existe; de lo contrario, extrae de supporting_evidence.
    """
    steps: list[dict[str, str]] = []

    if traza_path and traza_path.exists():
        try:
            with open(traza_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        raw_steps = data.get("steps", [])
                        for s in raw_steps:
                            cmd = anonymize_text(s.get("command_executed", s.get("command", "")))
                            out = anonymize_text(s.get("output_received", s.get("output", "")))
                            hyp = anonymize_text(s.get("hypothesis_tested", s.get("reasoning", "Verificación de comportamiento en red")))
                            steps.append({
                                "herramienta": s.get("tool_name", "network_tool"),
                                "comando": cmd,
                                "salida": out,
                                "hipotesis": hyp,
                            })
            if steps:
                return steps
        except Exception as e:
            logger.warning(f"No se pudo leer traza {traza_path}: {e}")

    # Fallback: extraer de supporting_evidence
    evidence_list = diagnostico.get("supporting_evidence", [])
    for idx, ev in enumerate(evidence_list, start=1):
        ev_str = str(ev)
        if " -> " in ev_str:
            cmd_part, out_part = ev_str.split(" -> ", 1)
        else:
            cmd_part = ev_str
            out_part = "Salida capturada en ejecución determinista"

        steps.append({
            "herramienta": "network_tool",
            "comando": anonymize_text(cmd_part),
            "salida": anonymize_text(out_part),
            "hipotesis": f"Verificación empírica {idx}",
        })

    if not steps:
        steps.append({
            "herramienta": "diagnostico",
            "comando": "Inspección pasiva de telemetría y logs del escenario",
            "salida": "Logs preprocesados del servicio analizados en contexto",
            "hipotesis": "Análisis inicial de logs y telemetría",
        })

    return steps


def build_stratified_sample(seed: int = 2026) -> list[ClaveCegamientoEntry]:
    """
    Selecciona la muestra estratificada: 18 escenarios x 3 modelos = 54 corridas.
    Una semilla elegida por combinación usando random.Random(seed).
    Genera códigos ciegos únicos EV-001..EV-054 barajados por el mismo generador.
    """
    rng = random.Random(seed)
    lab_runner = ScenarioLabRunner()
    scenarios = lab_runner.list_scenarios()
    scenario_ids = sorted([s.scenario_id for s in scenarios])
    model_ids = sorted(OFFICIAL_MODELS)

    # 54 combinaciones ordenadas canónicamente
    combinations: list[tuple[str, str]] = []
    for sc_id in scenario_ids:
        for m_id in model_ids:
            combinations.append((sc_id, m_id))

    # Seleccionar una semilla por combinación con rng
    sampled_combos: list[dict[str, Any]] = []
    for sc_id, m_id in combinations:
        chosen_seed = rng.choice(AVAILABLE_SEEDS)
        runs_dir = PROJECT_ROOT / "data" / "runs" / m_id
        diag_file = runs_dir / f"{sc_id}_s{chosen_seed}_r1_diagnostico.json"
        
        # En caso de que la ruta relativa sea usada:
        rel_diag_path = f"data/runs/{m_id}/{sc_id}_s{chosen_seed}_r1_diagnostico.json"

        sampled_combos.append({
            "scenario_id": sc_id,
            "model_id": m_id,
            "seed": chosen_seed,
            "diag_path": str(rel_diag_path),
            "abs_path": diag_file,
        })

    # Barajar la muestra estratificada primero para romper cualquier correlación de orden
    rng.shuffle(sampled_combos)

    # Generar 54 números aleatorios únicos de 3 dígitos (100-999) extraídos con rng
    random_nums = rng.sample(range(100, 1000), len(sampled_combos))
    blind_codes = [f"EV-{num:03d}" for num in random_nums]

    entries: list[ClaveCegamientoEntry] = []
    for i, item in enumerate(sampled_combos):
        entry = ClaveCegamientoEntry(
            codigo=blind_codes[i],
            model_id=item["model_id"],
            scenario_id=item["scenario_id"],
            seed=item["seed"],
            ruta_diagnostico=item["diag_path"],
        )
        entries.append(entry)

    # Ordenar la clave por código para consistencia documental
    entries.sort(key=lambda x: x.codigo)
    return entries


def build_anonymized_card(
    entry: ClaveCegamientoEntry,
    scenario: EscenarioLabContract,
    diag_data: dict[str, Any],
    traza_path: Path | None = None
) -> CorridaAnonimizada:
    """
    Construye la ficha anonimizada de una corrida para ser calificada a ciegas por expertos.
    """
    steps = extract_tool_steps(diag_data, traza_path)

    raw_rc = diag_data.get("root_cause", "")
    raw_comp = diag_data.get("affected_component", "")
    raw_act = diag_data.get("suggested_action", "")
    raw_exp = diag_data.get("natural_language_explanation", diag_data.get("model_diagnosis_text", ""))

    veredicto = {
        "causa_raiz": anonymize_text(raw_rc),
        "componente": anonymize_text(raw_comp),
        "mitigacion": anonymize_text(raw_act),
        "fundamentacion": anonymize_text(raw_exp),
    }

    gt = scenario.ground_truth
    card = CorridaAnonimizada(
        codigo=entry.codigo,
        scenario_id=scenario.scenario_id,
        sintoma=anonymize_text(scenario.description),
        causa_raiz_esperada=anonymize_text(gt.root_cause),
        componente_esperado=anonymize_text(gt.affected_component),
        evidencia_minima=[anonymize_text(e) for e in gt.minimum_required_evidence],
        pasos_herramienta=steps,
        veredicto=veredicto,
    )
    return card


def save_blind_key(
    entries: list[ClaveCegamientoEntry],
    sesion_id: str,
    seed: int,
    output_dir: Path
) -> tuple[Path, Path]:
    """
    Guarda la clave de cegamiento en data/human_eval/<sesion>/clave_RESTRINGIDA.json y .xlsx.
    Nunca se incluye en lo que reciben los expertos.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "clave_RESTRINGIDA.json"
    xlsx_path = output_dir / "clave_RESTRINGIDA.xlsx"

    # 1. Guardar JSON
    payload = {
        "sesion_id": sesion_id,
        "seed": seed,
        "fecha_creacion": datetime.now(UTC).isoformat(),
        "total_corridas": len(entries),
        "advertencia": "DOCUMENTO RESTRINGIDO - CLAVE DE CEGAMIENTO. PROHIBIDO SU ENVIO A EVALUADORES.",
        "entradas": [e.model_dump() for e in entries],
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    # 2. Guardar XLSX
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Clave_Cegamiento"

    # Estilos institucionales
    header_fill = PatternFill(start_color="B03535", end_color="B03535", fill_type="solid")
    header_font = Font(name="Arial", size=11, bold=True, color="FFFFFF")
    regular_font = Font(name="Arial", size=10, color="000000")
    thin_border = Border(
        left=Side(style="thin", color="CCCCCC"),
        right=Side(style="thin", color="CCCCCC"),
        top=Side(style="thin", color="CCCCCC"),
        bottom=Side(style="thin", color="CCCCCC"),
    )

    headers = ["Código Ciego", "Modelo", "Escenario", "Semilla", "Ruta Diagnóstico"]
    ws.append(headers)

    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = thin_border

    for e in entries:
        row = [e.codigo, e.model_id, e.scenario_id, e.seed, e.ruta_diagnostico]
        ws.append(row)

    for row in ws.iter_rows(min_row=2, max_row=len(entries)+1, min_col=1, max_col=5):
        for cell in row:
            cell.font = regular_font
            cell.border = thin_border
            if cell.column in (1, 3, 4):
                cell.alignment = Alignment(horizontal="center", vertical="center")
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center")

    for col in ws.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 4, 14)

    # Metadatos del documento
    wb.properties.creator = "NetDiagBench-L7"
    wb.properties.title = "Clave Restringida de Cegamiento"
    wb.save(xlsx_path)

    return json_path, xlsx_path


def load_anonymized_cards_from_sample(entries: list[ClaveCegamientoEntry]) -> dict[str, CorridaAnonimizada]:
    """
    Carga los archivos diagnostico.json correspondientes a cada corrida
    de la clave de cegamiento y genera el diccionario {codigo: CorridaAnonimizada}.
    """
    lab = ScenarioLabRunner()
    scenarios_map = {s.scenario_id: s for s in lab.list_scenarios()}
    cards: dict[str, CorridaAnonimizada] = {}

    for entry in entries:
        sc = scenarios_map.get(entry.scenario_id)
        if not sc:
            sc = lab.get_scenario(entry.scenario_id)

        diag_path = PROJECT_ROOT / entry.ruta_diagnostico
        diag_data: dict[str, Any] = {}
        if diag_path.exists():
            try:
                with open(diag_path, "r", encoding="utf-8") as f:
                    diag_data = json.load(f)
            except Exception as e:
                logger.warning(f"No se pudo cargar {diag_path}: {e}")

        traza_path = diag_path.with_name(diag_path.name.replace("_diagnostico.json", "_traza.jsonl"))
        if not traza_path.exists():
            traza_path = None

        card = build_anonymized_card(entry, sc, diag_data, traza_path)
        cards[entry.codigo] = card

    return cards


def load_blind_cards_from_sample(entries: list[ClaveCegamientoEntry]) -> dict[str, FichaCiegaEvaluador]:
    """
    Carga y retorna las fichas estrictamente ciegas (sin verdad fundamental) para los evaluadores.
    Separa los datos de referencia internos de los objetos que alimentan los exportadores ciegos.
    """
    cards = load_anonymized_cards_from_sample(entries)
    return {codigo: card.to_blind_card() for codigo, card in cards.items()}


