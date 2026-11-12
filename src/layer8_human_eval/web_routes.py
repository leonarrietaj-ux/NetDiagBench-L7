"""

NetDiagBench-L7: Layer 8 - Rutas Web y Endpoints FastAPI para Validación Humana (web_routes.py)

Proporciona endpoints REST y vistas HTMX para:

- Inicialización de sesión y gestión de clave de cegamiento

- Descarga de kits de evaluación (ZIP con XLSX + HTML)

- Importación y validación de respuestas

- Análisis de concordancia inter-evaluador y validación automática

- Generación de informes de correlación y apertura auditada de clave

"""



import csv

import io

import json

from pathlib import Path

from typing import Any, Optional

import zipfile



from fastapi import APIRouter, HTTPException, Request, Response

from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

from pydantic import BaseModel



from src.core.config import PROJECT_ROOT

from src.core.contracts import ClaveCegamientoEntry

from src.core.logger import logger

from src.layer7_evaluator.metrics import get_evaluator_version

from src.layer8_human_eval.agreement import (

    calculate_agreement_summary,

    calculate_consensus,

    calculate_metrics_by_model,

    export_agreement_json,

    export_agreement_workbook,

    validate_auto_vs_human,

)

from src.layer8_human_eval.correlation_report import (

    append_correlation_sheets,

    build_correlation_dataset,

    export_correlation_report_html,

    export_correlation_report_pdf,

    run_correlation_report,

)

from src.layer8_human_eval.exporter_packet import export_expert_packet_html

from src.layer8_human_eval.exporter_xlsx import export_expert_instrument

from src.layer8_human_eval.importer import import_expert_responses

from src.layer8_human_eval.labels import (

    compute_huella,

    generate_expert_label,

    load_etiquetas,

    save_etiquetas,

)

from src.layer8_human_eval.sampler import (

    build_stratified_sample,

    load_anonymized_cards_from_sample,

    load_blind_cards_from_sample,

    save_blind_key,

)

from src.layer8_human_eval.session import (

    create_new_session_dir,

    generate_new_session_id,

    get_active_session_id,

    get_session_dir,

    get_session_state,

    open_key_audit,

    set_active_session,

    validate_session_id,

)



router = APIRouter(prefix="", tags=["human-eval"])







def get_kappa_dictamen(val: float | None) -> str:

    if val is None:

        return "Sin datos"

    if val >= 0.61:

        return "Sustancial"

    elif val >= 0.41:

        return "Moderado"

    else:

        return "Insuficiente"





def get_alpha_dictamen(val: float | None) -> str:

    if val is None:

        return "Sin datos"

    if val >= 0.80:

        return "Confiable"

    elif val >= 0.667:

        return "Tentativo"

    else:

        return "Insuficiente"





def get_icc_dictamen(val: float | None) -> str:

    if val is None:

        return "Sin datos"

    if val >= 0.75:

        return "Bueno"

    elif val >= 0.50:

        return "Moderado"

    else:

        return "Pobre"





class AlphaItemResponse(BaseModel):

    item: str

    alfa: Optional[float] = None

    ci_inferior: Optional[float] = None

    ci_superior: Optional[float] = None

    dictamen: str = "Sin datos"





class ConfusionMatrixResponse(BaseModel):

    TP: int = 0

    TN: int = 0

    FP: int = 0

    FN: int = 0





class AutoVsHumanDetails(BaseModel):

    n: int = 0

    kappa: Optional[float] = None

    dictamen_kappa: str = "Sin datos"

    spearman: dict[str, Any] = {}

    bland_altman: dict[str, Any] = {}

    confusion_matrix: ConfusionMatrixResponse = ConfusionMatrixResponse()





class AgreementResponse(BaseModel):

    ok: bool = True

    sesion_id: str

    has_data: bool = False

    acuerdo_exacto_c1: Optional[float] = None

    acuerdo_exacto_c1_ci: list[float] = []

    acuerdo_exacto_c1_dictamen: str = "Sin datos"

    kappa_ponderado_c1: Optional[float] = None

    kappa_ponderado_c1_ci: list[float] = []

    kappa_ponderado_c1_dictamen: str = "Sin datos"

    kappa_s: Optional[float] = None

    kappa_s_ci: list[float] = []

    kappa_s_dictamen: str = "Sin datos"

    icc_2_1: Optional[float] = None

    icc_2_1_ci: list[float] = []

    icc_2_1_dictamen: str = "Sin datos"

    alfas_ordinales: list[AlphaItemResponse] = []

    desacuerdos_c1: int = 0

    pendientes_count: int = 0

    agreement_summary: dict[str, Any] = {}

    auto_vs_human: AutoVsHumanDetails = AutoVsHumanDetails()

    models_breakdown: dict[str, Any] = {}



class InitSessionRequest(BaseModel):

    seed: int = 2026

    sesion_id: Optional[str] = None





class OpenKeyRequest(BaseModel):

    motivo: str = "Apertura formal de clave para análisis desglosados"





# ── Endpoints de la API REST ────────────────────────────────────────────────



@router.get("/api/human-eval/state")

def api_get_state(sesion_id: Optional[str] = None):

    """Devuelve el estado de la sesión activa o especificada."""

    if sesion_id and str(sesion_id).strip():

        try:

            validate_session_id(sesion_id)

        except ValueError as ve:

            return JSONResponse({"ok": False, "error": str(ve)}, status_code=400)

    state = get_session_state(sesion_id)

    return JSONResponse(state)





@router.post("/api/human-eval/init")

def api_init_session(req: InitSessionRequest):

    """Inicializa una sesión de evaluación humana: muestra estratificada, clave y etiquetas."""

    try:

        try:

            active_id, s_dir = create_new_session_dir(req.sesion_id)

        except FileExistsError as fee:

            return JSONResponse({"ok": False, "error": str(fee)}, status_code=409)

        except ValueError as ve:

            return JSONResponse({"ok": False, "error": str(ve)}, status_code=400)



        set_active_session(active_id)



        sample = build_stratified_sample(seed=req.seed)

        save_blind_key(sample, active_id, req.seed, s_dir)



        codes = [s.codigo for s in sample]

        etiqueta_a = generate_expert_label("A", active_id, codes, semilla_orden=11)

        etiqueta_b = generate_expert_label("B", active_id, codes, semilla_orden=22)

        etiqueta_c = generate_expert_label("C", active_id, codes, semilla_orden=33)



        etiquetas_map = {"A": etiqueta_a, "B": etiqueta_b, "C": etiqueta_c}

        save_etiquetas(etiquetas_map, s_dir)



        # Pre-generar kits ciegos completos para A y B

        cards_map = load_blind_cards_from_sample(sample)

        xlsx_a = s_dir / f"Instrumento_Experto_A_{active_id}.xlsx"

        paq_a = s_dir / f"Paquete_Experto_A_{active_id}.html"

        xlsx_b = s_dir / f"Instrumento_Experto_B_{active_id}.xlsx"

        paq_b = s_dir / f"Paquete_Experto_B_{active_id}.html"



        export_expert_instrument(etiqueta_a, cards_map, xlsx_a)

        export_expert_packet_html(etiqueta_a, cards_map, paq_a)

        export_expert_instrument(etiqueta_b, cards_map, xlsx_b)

        export_expert_packet_html(etiqueta_b, cards_map, paq_b)



        return JSONResponse({

            "ok": True,

            "sesion_id": active_id,

            "sample_size": len(sample),

            "state": get_session_state(active_id),

        })

    except Exception as e:

        logger.error(f"Error al inicializar sesión: {e}")

        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)





@router.get("/api/human-eval/labels")

def api_get_labels(sesion_id: Optional[str] = None):

    """Devuelve las etiquetas oficiales registradas."""

    try:

        s_dir = get_session_dir(sesion_id)

        etiquetas_path = s_dir / "etiquetas.json"

        if not etiquetas_path.exists():

            return JSONResponse({"ok": False, "error": "No hay etiquetas en la sesión"}, status_code=404)

        etiquetas = load_etiquetas(etiquetas_path)

        return JSONResponse({k: v.model_dump() for k, v in etiquetas.items()})

    except Exception as e:

        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)





def _is_valid_expert_kit(xlsx_path: Path, html_path: Path, expected_count: int) -> bool:

    """Verifica la integridad del instrumento Excel y el paquete HTML ciego."""

    if not xlsx_path.exists() or not html_path.exists():

        return False

    if xlsx_path.stat().st_size < 1024 or html_path.stat().st_size == 0:

        return False

    if not zipfile.is_zipfile(xlsx_path):

        return False

    try:

        import openpyxl

        wb = openpyxl.load_workbook(xlsx_path, data_only=True)

        sheet_name = "Evaluación" if "Evaluación" in wb.sheetnames else ("Evaluacion" if "Evaluacion" in wb.sheetnames else None)

        if not sheet_name:

            return False

        ws = wb[sheet_name]

        codes = [row[1] for row in ws.iter_rows(min_row=5, max_col=2, values_only=True) if row and row[1]]

        if len(codes) != expected_count:

            return False

    except Exception:

        return False

    return True





def load_session_auto_data(s_dir: Path, clave_entries: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:

    """

    Carga métricas automáticas para la sesión:

    1. Si existe s_dir / 'automatico.csv', lo lee directamente (codigo, is_correct, rubric_score, evidence_backed).

    2. Si no, lee los JSON de diagnóstico en data/runs/<modelo>/...

    """

    auto_csv_path = s_dir / "automatico.csv"

    auto_dict: dict[str, dict[str, Any]] = {}

    if auto_csv_path.exists():

        with open(auto_csv_path, "r", encoding="utf-8") as f:

            reader = csv.DictReader(f)

            for row in reader:

                code = row.get("codigo", "").strip()

                if not code:

                    continue

                corr_raw = row.get("is_correct", "")

                is_corr = bool(str(corr_raw).strip().lower() in ("1", "true", "si", "sí"))

                rub_score = float(row.get("rubric_score", 0.0))

                ev_backed_raw = row.get("evidence_backed", "")

                ev_backed = bool(str(ev_backed_raw).strip().lower() in ("1", "true", "si", "sí"))

                auto_dict[code] = {

                    "codigo": code,

                    "is_correct": is_corr,

                    "rubric_score": rub_score,

                    "evidence_backed": ev_backed,

                }

        for entry in clave_entries:

            c = entry.get("codigo")

            if c in auto_dict and "scenario_id" not in auto_dict[c]:

                auto_dict[c]["scenario_id"] = entry.get("scenario_id", "")

        return auto_dict



    for entry in clave_entries:

        code = entry.get("codigo")

        sc_id = entry.get("scenario_id", "")

        diag_rel = entry.get("ruta_diagnostico")

        if diag_rel:

            diag_p = PROJECT_ROOT / diag_rel

            if diag_p.exists():

                diag = json.loads(diag_p.read_text(encoding="utf-8"))

                ev = diag.get("evaluation", {})

                auto_dict[code] = {

                    "codigo": code,

                    "scenario_id": sc_id,

                    "is_correct": ev.get("is_correct", False),

                    "rubric_score": float(ev.get("rubric_score", 0.0)),

                    "evidence_backed": bool(ev.get("evidence_backed", False)),

                }

    # Fallback cientifico: consultar data/benchmark_results/resultados.csv si no existen archivos de corrida individuales
    csv_path = PROJECT_ROOT / "data" / "benchmark_results" / "resultados.csv"
    if csv_path.exists() and len(auto_dict) < len(clave_entries):
        with open(csv_path, "r", encoding="utf-8") as f_csv:
            csv_rows = list(csv.DictReader(f_csv))

        lookup = {}
        for r in csv_rows:
            m = r.get("model_id", "").strip().lower()
            s = r.get("scenario_id", "").strip()
            try:
                sd = int(r.get("seed", 0))
            except Exception:
                sd = 0
            is_corr = bool(str(r.get("is_full_diagnosis_correct") or r.get("is_root_cause_correct_full_text") or r.get("is_root_cause_correct", "")).strip().lower() in ("1", "true", "si"))
            rub = float(r.get("rubric_score") or 0.0)
            ev = bool(str(r.get("evidence_backed", "")).strip().lower() in ("1", "true", "si"))
            lookup[(m, s, sd)] = {
                "is_correct": is_corr,
                "rubric_score": rub,
                "evidence_backed": ev,
            }

        for entry in clave_entries:
            code = entry.get("codigo")
            if code and code not in auto_dict:
                m = str(entry.get("model_id", "")).strip().lower()
                s = str(entry.get("scenario_id", "")).strip()
                try:
                    sd = int(entry.get("seed", 0))
                except Exception:
                    sd = 0
                if (m, s, sd) in lookup:
                    matched = lookup[(m, s, sd)]
                    auto_dict[code] = {
                        "codigo": code,
                        "scenario_id": s,
                        "is_correct": matched["is_correct"],
                        "rubric_score": matched["rubric_score"],
                        "evidence_backed": matched["evidence_backed"],
                    }

    return auto_dict





@router.get("/api/human-eval/export/excel")
def api_download_agreement_excel(sesion_id: Optional[str] = None):
    """Descarga el libro Excel con la matriz de asignación, concordancia y correlación."""
    s_dir = get_session_dir(sesion_id)
    active_id = s_dir.name
    xlsx_path = s_dir / f"Analisis_Concordancia_{active_id}.xlsx"
    if not xlsx_path.exists():
        api_get_agreement(active_id)
    if not xlsx_path.exists():
        raise HTTPException(status_code=404, detail="Matriz de concordancia en Excel no encontrada")

    return Response(
        content=xlsx_path.read_bytes(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{xlsx_path.name}"'}
    )


@router.get("/api/human-eval/export/correlation")
@router.get("/api/human-eval/export/html")
def api_download_correlation_html(sesion_id: Optional[str] = None):
    """Descarga el informe técnico HTML de correlación."""
    s_dir = get_session_dir(sesion_id)
    active_id = s_dir.name
    html_path = s_dir / f"Informe_Correlacion_{active_id}.html"
    if not html_path.exists():
        api_get_correlation(active_id)
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Informe de correlación no encontrado")

    return Response(
        content=html_path.read_bytes(),
        media_type="text/html",
        headers={"Content-Disposition": f'attachment; filename="{html_path.name}"'}
    )


@router.get("/api/human-eval/export/correlation-pdf")
@router.get("/api/human-eval/export/pdf")
def api_download_correlation_pdf(sesion_id: Optional[str] = None):
    """Descarga el informe técnico PDF de correlación."""
    s_dir = get_session_dir(sesion_id)
    active_id = s_dir.name
    pdf_path = s_dir / f"Informe_Correlacion_{active_id}.pdf"
    if not pdf_path.exists():
        api_get_correlation(active_id)
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="Informe de correlación PDF no encontrado")

    return Response(
        content=pdf_path.read_bytes(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{pdf_path.name}"'}
    )


@router.get("/api/human-eval/export/{expert_id}")

def api_export_kit(expert_id: str, sesion_id: Optional[str] = None):

    """Descarga en un archivo ZIP el cuaderno Excel y el paquete HTML ciego de un evaluador."""

    expert_id = expert_id.upper().strip()

    if expert_id not in ("A", "B", "C"):

        raise HTTPException(status_code=400, detail="Identificador de experto inválido")



    s_dir = get_session_dir(sesion_id)

    active_id = s_dir.name



    xlsx_path = s_dir / f"Instrumento_Experto_{expert_id}_{active_id}.xlsx"

    html_path = s_dir / f"Paquete_Experto_{expert_id}_{active_id}.html"



    etiquetas_path = s_dir / "etiquetas.json"

    clave_json_path = s_dir / "clave_RESTRINGIDA.json"

    if not etiquetas_path.exists() or not clave_json_path.exists():

        raise HTTPException(status_code=400, detail="La sesión no ha sido inicializada")



    etiquetas = load_etiquetas(etiquetas_path)

    etiqueta = etiquetas.get(expert_id)

    if not etiqueta:

        raise HTTPException(status_code=404, detail="Etiqueta no encontrada")



    expected_count = len(etiqueta.orden) if etiqueta.orden else (54 if expert_id in ("A", "B") else 0)



    # Si los archivos no existen o no son válidos (ej. vacíos o corruptos), regenerarlos desde cero

    if not _is_valid_expert_kit(xlsx_path, html_path, expected_count):

        with open(clave_json_path, "r", encoding="utf-8") as f:

            clave_data = json.load(f)

        raw_entries = clave_data.get("entradas", clave_data) if isinstance(clave_data, dict) else clave_data

        sample_entries = [ClaveCegamientoEntry(**e) for e in raw_entries]

        cards_map = load_blind_cards_from_sample(sample_entries)



        if xlsx_path.exists():

            try:

                xlsx_path.unlink()

            except Exception:

                pass

        if html_path.exists():

            try:

                html_path.unlink()

            except Exception:

                pass



        export_expert_instrument(etiqueta, cards_map, xlsx_path)

        export_expert_packet_html(etiqueta, cards_map, html_path)



        if not _is_valid_expert_kit(xlsx_path, html_path, expected_count):

            raise HTTPException(

                status_code=500,

                detail=f"Fallo al generar instrumento válido para {expert_id}: tamaño o contenido inválido."

            )



    # Crear ZIP en memoria con formulario, visor interactivo, README y manifest.json

    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:

        # Incluir exactamente 1 cuaderno Excel y 1 visor HTML ciego (sin duplicados)
        zip_file.write(xlsx_path, arcname=xlsx_path.name)
        zip_file.write(html_path, arcname=html_path.name)



        manifest = {

            "session_id": active_id,

            "expert_id": expert_id,

            "alias": etiqueta.alias,

            "rol": etiqueta.rol,

            "codigo_acceso": etiqueta.codigo_acceso,

            "huella_sha256": etiqueta.huella_sha256,

            "total_corridas": expected_count,

            "evaluator_version": get_evaluator_version(),

        }

        zip_file.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))



        readme = f"""# NetDiagBench-L7 — Kit Ciego de Evaluación Humana

## Evaluador: {expert_id} ({etiqueta.alias})

- **Sesión**: `{active_id}`

- **Rol**: `{etiqueta.rol}`

- **Código de acceso**: `{etiqueta.codigo_acceso}`

- **Huella SHA-256**: `{etiqueta.huella_sha256}`

- **Total de corridas**: {expected_count}



### Instrucciones de Evaluación:

1. Abra `{html_path.name}` en su navegador web para consultar la telemetría, trazas y diagnósticos ciegos.

2. Complete `{xlsx_path.name}` conforme a la rúbrica aprobada (criterios C1-C6, Sustentación S y Utilidad U).

3. Guarde y cargue el archivo Excel completado en la plataforma NetDiagBench-L7 (Sección Capa 8 -> Importar Respuestas).

"""

        zip_file.writestr(f"README_EVALUADOR_{expert_id}.md", readme)



    zip_buffer.seek(0)



    filename = f"KIT_CIEGO_EVALUADOR_{expert_id}_{active_id}.zip"

    return Response(

        content=zip_buffer.getvalue(),

        media_type="application/zip",

        headers={"Content-Disposition": f'attachment; filename="{filename}"'}

    )





@router.post("/api/human-eval/import")

async def api_import_responses(

    request: Request,

    sesion_id: Optional[str] = None,

    filename: Optional[str] = None,

):

    """Importa y valida el cuaderno Excel con las respuestas de un experto."""

    s_dir = get_session_dir(sesion_id)

    active_id = s_dir.name

    etiquetas_path = s_dir / "etiquetas.json"



    if not etiquetas_path.exists():

        return JSONResponse({"ok": False, "error": "No se encontró etiquetas.json en la sesión"}, status_code=400)



    content = await request.body()

    if not content:

        return JSONResponse({"ok": False, "error": "El archivo recibido está vacío"}, status_code=400)



    fn = filename or "uploaded_responses.xlsx"

    temp_upload = s_dir / f"upload_{fn}"

    temp_upload.write_bytes(content)



    try:

        expert_id, rows = import_expert_responses(

            xlsx_path=temp_upload,

            sesion_id=active_id,

            etiquetas_path=etiquetas_path,

            output_dir=s_dir,

        )

        return JSONResponse({

            "ok": True,

            "expert_id": expert_id,

            "evaluated_count": len(rows),

            "state": get_session_state(active_id),

        })

    except Exception as e:

        logger.error(f"Error de importación: {e}")

        return JSONResponse({"ok": False, "error": str(e)}, status_code=400)





@router.post("/api/human-eval/emit-tiebreak")

def api_emit_tiebreak(sesion_id: Optional[str] = None):

    """Detecta desacuerdos entre A y B y emite el cuaderno dirimente para el Experto C."""

    s_dir = get_session_dir(sesion_id)

    active_id = s_dir.name



    resp_a = s_dir / "respuestas_A.csv"

    resp_b = s_dir / "respuestas_B.csv"

    if not resp_a.exists() or not resp_b.exists():

        return JSONResponse({"ok": False, "error": "Se requieren las respuestas de A y B importadas"}, status_code=400)



    def _read_csv(p: Path):

        with open(p, "r", encoding="utf-8") as f:

            return list(csv.DictReader(f))



    rows_a = _read_csv(resp_a)

    rows_b = _read_csv(resp_b)

    dict_b = {r["codigo"]: r for r in rows_b}



    disagreements = []

    for r_a in rows_a:

        code = r_a["codigo"]

        r_b = dict_b.get(code)

        if not r_b:

            continue

        # Verificar discrepancias en TODOS los criterios normativos (C1-C6 y variable S)
        has_disc = False
        for crit in ["c1", "c2", "c3", "c4", "c5", "c6"]:
            try:
                if int(r_a[crit]) != int(r_b[crit]):
                    has_disc = True
                    break
            except (ValueError, TypeError, KeyError):
                pass

        if not has_disc and r_a.get("s", "").strip().lower() != r_b.get("s", "").strip().lower():
            has_disc = True

        if has_disc:
            disagreements.append(code)



    if not disagreements:

        return JSONResponse({

            "ok": True,

            "disagreements_count": 0,

            "message": "Consenso unánime entre A y B; no se requiere dirimente C.",

        })



    # Actualizar etiqueta de C con solo las corridas en desacuerdo

    etiquetas_path = s_dir / "etiquetas.json"

    etiquetas = load_etiquetas(etiquetas_path)

    etiqueta_c = etiquetas["C"]

    etiqueta_c.orden = disagreements



    version = get_evaluator_version()

    etiqueta_c.huella_sha256 = compute_huella(active_id, "C", disagreements, version)

    save_etiquetas(etiquetas, s_dir)



    # Construir fichas para C

    clave_json_path = s_dir / "clave_RESTRINGIDA.json"

    with open(clave_json_path, "r", encoding="utf-8") as f:

        clave_data = json.load(f)

    raw_entries = clave_data.get("entradas", clave_data) if isinstance(clave_data, dict) else clave_data

    sample_entries = [ClaveCegamientoEntry(**e) for e in raw_entries]

    cards_map = load_blind_cards_from_sample(sample_entries)



    xlsx_c = s_dir / f"Instrumento_Experto_C_{active_id}.xlsx"

    export_expert_instrument(etiqueta_c, cards_map, xlsx_c)



    html_c = s_dir / f"Paquete_Experto_C_{active_id}.html"

    export_expert_packet_html(etiqueta_c, cards_map, html_c)



    return JSONResponse({

        "ok": True,

        "disagreements_count": len(disagreements),

        "disagreeing_codes": disagreements,

        "state": get_session_state(active_id),

    })





@router.get("/api/human-eval/agreement")

def api_get_agreement(sesion_id: Optional[str] = None):

    """Devuelve los cálculos de concordancia inter-evaluador y validación automática en formato JSON."""

    s_dir = get_session_dir(sesion_id)

    active_id = s_dir.name



    resp_a = s_dir / "respuestas_A.csv"

    resp_b = s_dir / "respuestas_B.csv"

    resp_c = s_dir / "respuestas_C.csv"



    if not resp_a.exists() or not resp_b.exists():

        return JSONResponse({"ok": False, "error": "Se requieren al menos las respuestas de A y B"}, status_code=400)



    def _read_csv(p: Path):

        with open(p, "r", encoding="utf-8") as f:

            return [{k: (int(v) if k in ("c1","c2","c3","c4","c5","c6","u") else (float(v) if k=="rubrica" else v)) for k, v in r.items()} for r in csv.DictReader(f)]



    rows_a = _read_csv(resp_a)

    rows_b = _read_csv(resp_b)

    rows_c = _read_csv(resp_c) if resp_c.exists() else None



    summary = calculate_agreement_summary(rows_a, rows_b)

    consensus = calculate_consensus(rows_a, rows_b, rows_c)



    clave_json_path = s_dir / "clave_RESTRINGIDA.json"

    auto_dict = {}

    code_to_model = {}

    if clave_json_path.exists():

        with open(clave_json_path, "r", encoding="utf-8") as f:

            clave_data = json.load(f)

        entries = clave_data.get("entradas", clave_data) if isinstance(clave_data, dict) else clave_data

        for entry in entries:

            code_to_model[entry["codigo"]] = entry["model_id"]

        auto_dict = load_session_auto_data(s_dir, entries)



    val_res = validate_auto_vs_human(consensus, auto_dict) if auto_dict else {}

    models_breakdown = calculate_metrics_by_model(consensus, code_to_model, auto_dict) if code_to_model else {}



    # Exportar JSON y XLSX de concordancia

    export_agreement_json(active_id, summary, val_res, models_breakdown, s_dir / "concordancia.json")

    export_agreement_workbook(active_id, rows_a, rows_b, consensus, summary, val_res, models_breakdown, s_dir / f"Analisis_Concordancia_{active_id}.xlsx")



    kw_c1_val = summary["kappa_ponderado_c1"]["valor"]

    kw_c1_ci = summary["kappa_ponderado_c1"]["ci_95"]

    kw_c1_dictamen = get_kappa_dictamen(kw_c1_val)



    ks_val = summary["kappa_s"]["valor"]

    ks_ci = summary["kappa_s"]["ci_95"]

    ks_dictamen = get_kappa_dictamen(ks_val)



    icc_val = summary["icc_2_1"]["valor"]

    icc_ci = summary["icc_2_1"]["ci_95"]

    icc_dictamen = get_icc_dictamen(icc_val)



    po_val = summary["acuerdo_exacto_c1"]["valor"]

    po_ci = summary["acuerdo_exacto_c1"]["ci_95"]

    po_dictamen = "Informativo" if po_val is not None else "Sin datos"



    alfas_list = []

    item_descs = {

        "C1": "Causa Raíz", "C2": "Coherencia Técnica", "C3": "Fundamentación Normativa",

        "C4": "Componente Afectado", "C5": "Mitigación", "C6": "Exactitud Factual"

    }

    for item_key in ["C1", "C2", "C3", "C4", "C5", "C6"]:

        d_a = summary.get("alfas_ordinales", {}).get(item_key, {})

        a_val = d_a.get("alfa")

        a_ci = d_a.get("ci_95", [0.0, 0.0])

        alfas_list.append({

            "item": item_key,

            "desc": item_descs.get(item_key, ""),

            "alfa": a_val,

            "ci_inferior": a_ci[0] if a_ci else None,

            "ci_superior": a_ci[1] if a_ci else None,

            "dictamen": get_alpha_dictamen(a_val),

        })



    response_obj = AgreementResponse(

        ok=True,

        sesion_id=active_id,

        has_data=True,

        acuerdo_exacto_c1=po_val,

        acuerdo_exacto_c1_ci=po_ci,

        acuerdo_exacto_c1_dictamen=po_dictamen,

        kappa_ponderado_c1=kw_c1_val,

        kappa_ponderado_c1_ci=kw_c1_ci,

        kappa_ponderado_c1_dictamen=kw_c1_dictamen,

        kappa_s=ks_val,

        kappa_s_ci=ks_ci,

        kappa_s_dictamen=ks_dictamen,

        icc_2_1=icc_val,

        icc_2_1_ci=icc_ci,

        icc_2_1_dictamen=icc_dictamen,

        alfas_ordinales=[AlphaItemResponse(**a) for a in alfas_list],

        desacuerdos_c1=summary.get("desacuerdos_c1", 0),

        pendientes_count=sum(1 for c in consensus if c["c1_consenso"] is None),

        agreement_summary=summary,

        auto_vs_human=AutoVsHumanDetails(

            n=val_res.get("n", 0),

            kappa=val_res.get("kappa"),

            dictamen_kappa=get_kappa_dictamen(val_res.get("kappa")),

            spearman=val_res.get("spearman", {}),

            bland_altman=val_res.get("bland_altman", {}),

            confusion_matrix=ConfusionMatrixResponse(**val_res.get("confusion_matrix", {})),

        ),

        models_breakdown=models_breakdown,

    )

    return JSONResponse(response_obj.model_dump())





@router.get("/api/human-eval/correlation")

def api_get_correlation(sesion_id: Optional[str] = None):

    """Devuelve los datos del informe de correlación en JSON."""

    s_dir = get_session_dir(sesion_id)

    active_id = s_dir.name

    try:
        state = get_session_state(active_id)
    except Exception:
        state = {}

    is_blind = not state.get("is_key_opened", False)



    resp_a = s_dir / "respuestas_A.csv"

    resp_b = s_dir / "respuestas_B.csv"

    resp_c = s_dir / "respuestas_C.csv"

    clave_json = s_dir / "clave_RESTRINGIDA.json"



    if not resp_a.exists() or not resp_b.exists() or not clave_json.exists():

        return JSONResponse({"ok": False, "error": "Faltan respuestas de A y B o clave restringida"}, status_code=400)



    def _read_csv(p: Path):

        with open(p, "r", encoding="utf-8") as f:

            return [{k: (int(v) if k in ("c1","c2","c3","c4","c5","c6","u") else (float(v) if k=="rubrica" else v)) for k, v in r.items()} for r in csv.DictReader(f)]



    rows_a = _read_csv(resp_a)

    rows_b = _read_csv(resp_b)

    rows_c = _read_csv(resp_c) if resp_c.exists() else None



    consensus = calculate_consensus(rows_a, rows_b, rows_c)



    with open(clave_json, "r", encoding="utf-8") as f:

        clave_data = json.load(f)

    entries = clave_data.get("entradas", clave_data) if isinstance(clave_data, dict) else clave_data

    key_by_code = {entry["codigo"]: entry for entry in entries}



    auto_dict = load_session_auto_data(s_dir, entries)



    results_csv_rows = []

    res_csv_p = PROJECT_ROOT / "data" / "benchmark_results" / "resultados.csv"

    if res_csv_p.exists():

        with open(res_csv_p, "r", encoding="utf-8") as f:

            results_csv_rows = list(csv.DictReader(f))



    summary = calculate_agreement_summary(rows_a, rows_b)

    try:

        unified_rows = build_correlation_dataset(consensus, key_by_code, results_csv_rows, auto_dict)

        report_data = run_correlation_report(unified_rows, agreement_summary=summary, is_blind=is_blind)

    except Exception as e:

        logger.error(f"Error calculando correlación: {e}")

        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)



    # Exportar HTML y PDF

    html_path = s_dir / f"Informe_Correlacion_{active_id}.html"

    export_correlation_report_html(report_data, unified_rows, html_path)

    pdf_path = s_dir / f"Informe_Correlacion_{active_id}.pdf"

    export_correlation_report_pdf(report_data, unified_rows, pdf_path)



    # Anexar hojas Correlación y Datos_correlación en Analisis_Concordancia_<sesion>.xlsx

    concordancia_xlsx = s_dir / f"Analisis_Concordancia_{active_id}.xlsx"

    import openpyxl

    if concordancia_xlsx.exists():

        wb = openpyxl.load_workbook(concordancia_xlsx)

    else:

        wb = openpyxl.Workbook()

        wb.remove(wb.active)

    for s_name in ["Correlación", "Datos_correlación"]:

        if s_name in wb.sheetnames:

            del wb[s_name]

    append_correlation_sheets(wb, report_data, unified_rows)

    wb.save(concordancia_xlsx)



    return JSONResponse(report_data)





@router.post("/api/human-eval/open-key")

def api_open_key(req: OpenKeyRequest, sesion_id: Optional[str] = None):

    """Registra en auditoría la apertura de la clave de cegamiento y desbloquea análisis 3 a 5."""

    try:

        s_dir = get_session_dir(sesion_id)

        audit_data = open_key_audit(s_dir.name, reason=req.motivo)

        return JSONResponse({"ok": True, "audit": audit_data, "state": get_session_state(s_dir.name)})

    except ValueError as e:

        return JSONResponse({"ok": False, "error": str(e)}, status_code=400)

    except Exception as e:

        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)











# ── Fragmento HTML de la 6ª Vista: Validación Humana (Capa 8) ───────────────



@router.get("/vistas/human_eval", response_class=HTMLResponse)

def vista_human_eval_fragment():

    """Genera el fragmento HTML reactivo e interactivo de la 6ª vista para la barra lateral."""

    try:

        active_id = get_active_session_id(fallback_create=False)

    except Exception:

        active_id = "default"



    state = get_session_state(active_id)

    is_blind = (state.get("phase") != "CLAVE_ABIERTA")



    html = """
<style>
  [data-theme="light"] label[class*="bg-rose"],
  [data-theme="light"] button[class*="bg-rose"],
  [data-theme="light"] a[class*="bg-rose"],
  [data-theme="light"] label[class*="bg-red"],
  [data-theme="light"] button[class*="bg-red"],
  [data-theme="light"] a[class*="bg-red"],
  [data-theme="light"] .bg-rose-600,
  [data-theme="light"] .bg-rose-700,
  [data-theme="light"] .bg-red-600,
  [data-theme="light"] .bg-red-700 {
    color: #ffffff !important;
  }
  [data-theme="light"] label[class*="bg-rose"] *,
  [data-theme="light"] button[class*="bg-rose"] *,
  [data-theme="light"] a[class*="bg-rose"] *,
  [data-theme="light"] label[class*="bg-red"] *,
  [data-theme="light"] button[class*="bg-red"] *,
  [data-theme="light"] a[class*="bg-red"] * {
    color: #ffffff !important;
  }
  [data-theme="light"] label[class*="bg-rose"] svg,
  [data-theme="light"] button[class*="bg-rose"] svg,
  [data-theme="light"] label[class*="bg-red"] svg,
  [data-theme="light"] button[class*="bg-red"] svg {
    color: #ffffff !important;
    stroke: #ffffff !important;
  }
</style>

    <div class="w-full flex-1 p-4 md:p-6 text-slate-800 dark:text-slate-100 flex flex-col gap-6 transition-colors pb-16 min-h-0"

         x-data="humanEvalView('__SESION_ID__', __IS_BLIND__)"

         x-init="initData()">



      <!-- Encabezado Institucional -->

      <div class="flex flex-col md:flex-row justify-between items-start md:items-center pb-4 border-b border-slate-200 dark:border-slate-700/80 gap-4">

        <div>

          <div class="flex items-center gap-3">

            <h1 class="text-xl md:text-2xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2">

              <span class="inline-block w-3 h-3 rounded-full bg-rose-500 shadow-lg shadow-rose-500/50"></span>

              Capa 8: Validación Humana y Calibración Inter-Evaluador

            </h1>

            <span class="px-2.5 py-0.5 text-xs font-mono font-bold rounded-full bg-slate-100 dark:bg-slate-800 text-rose-600 dark:text-rose-400 border border-rose-300 dark:border-rose-500/30">

              v1.0.0

            </span>

          </div>

          <p class="text-xs text-slate-600 dark:text-slate-400 mt-1">

            Evaluación ciega independiente por 3 expertos (A, B y C dirimente) • Muestra estratificada de 54 corridas • Rúbrica 6 criterios + Sustentación

          </p>

        </div>



        <div class="flex flex-wrap items-center gap-2.5">

          <!-- Badge de Sesión Activa -->

          <div class="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-xs shadow-sm">

            <span class="text-slate-500 dark:text-slate-400 font-medium">Sesión:</span>

            <span class="font-mono font-bold text-sky-600 dark:text-sky-400" x-text="sesionId"></span>

          </div>



          <!-- Botón Nueva Sesión -->

          <button @click="initNewSession()"

                  title="Inicializar nueva sesión con muestra estratificada"

                  class="px-2.5 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 border border-slate-300 dark:border-slate-700 text-xs font-medium transition-colors flex items-center gap-1.5 cursor-pointer shadow-sm">

            <svg class="w-3.5 h-3.5 text-sky-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/></svg>

            Nueva Sesión

          </button>





          <!-- Badges de Estado Formativo (10 Fases) -->

          <template x-if="state.phase === 'NO_INICIALIZADA'">

            <span class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-rose-50 dark:bg-rose-950/80 border border-rose-300 dark:border-rose-700 text-rose-700 dark:text-rose-300 text-xs font-semibold shadow-sm">

              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>

              Sesión No Inicializada

            </span>

          </template>

          <template x-if="state.phase === 'CLAVE_ABIERTA'">

            <span class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-50 dark:bg-emerald-950/80 border border-emerald-300 dark:border-emerald-600/50 text-emerald-800 dark:text-emerald-300 text-xs font-semibold shadow-sm">

              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 11V7a4 4 0 118 0m-4 8v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2z"/></svg>

              Clave Abierta (Desbloqueado)

            </span>

          </template>

          <template x-if="state.phase !== 'NO_INICIALIZADA' && state.phase !== 'CLAVE_ABIERTA'">

            <span class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-50 dark:bg-amber-950/80 border border-amber-300 dark:border-amber-600/50 text-amber-800 dark:text-amber-300 text-xs font-semibold shadow-sm">

              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"/></svg>

              Evaluación Ciega (Restringida)

            </span>

          </template>



          <!-- Botón Abrir Clave (solo si concordancia calculada) -->

          <template x-if="state.phase === 'CONCORDANCIA_CALCULADA'">

            <button @click="showOpenKeyModal = true"

                    class="px-3 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-700 text-white !text-white text-xs font-semibold transition-all flex items-center gap-1.5 cursor-pointer shadow-sm">

              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z"/></svg>

              Abrir Clave

            </button>

          </template>

        </div>

      </div>



      <!-- Banner de alerta si la sesión no ha sido inicializada -->

      <template x-if="state.phase === 'NO_INICIALIZADA'">

        <div class="p-4 rounded-xl bg-amber-50 dark:bg-amber-950/60 border border-amber-300 dark:border-amber-700/80 flex flex-col md:flex-row justify-between items-start md:items-center gap-3 shadow-sm">

          <div class="flex items-center gap-3">

            <div class="w-8 h-8 rounded-lg bg-amber-100 dark:bg-amber-900/60 border border-amber-300 dark:border-amber-700 flex items-center justify-center shrink-0">

              <svg class="w-4 h-4 text-amber-700 dark:text-amber-300" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>

            </div>

            <div>

              <h4 class="text-xs font-bold text-amber-900 dark:text-amber-200">Sesión no inicializada</h4>

              <p class="text-xs text-amber-800 dark:text-amber-300 mt-0.5">La sesión activa actual no contiene la muestra estratificada ni las claves de cegamiento. Inicialice la sesión para generar los kits de evaluación.</p>

            </div>

          </div>

          <button @click="initNewSession()"

                  class="px-4 py-2 rounded-lg bg-amber-600 hover:bg-amber-700 text-white text-xs font-bold transition-all shadow-sm shrink-0 cursor-pointer">

            Inicializar Sesión Ahora

          </button>

        </div>

      </template>



      <!-- Pestañas de Navegación de la Vista -->

      <div class="flex items-center gap-2 border-b border-slate-200 dark:border-slate-700/60">

        <button @click="activeTab = 'evaluadores'"

                :class="activeTab === 'evaluadores' ? 'border-rose-600 text-rose-600 dark:text-rose-400 font-bold bg-white dark:bg-slate-800/80 shadow-sm' : 'border-transparent text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800/40'"

                class="px-4 py-2.5 border-b-2 text-xs font-semibold rounded-t-lg transition-all flex items-center gap-2 cursor-pointer">

          <svg class="w-4 h-4 text-rose-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"/></svg>

          1. Instrumentos y Evaluadores

        </button>



        <button @click="activeTab = 'concordancia'; loadAgreement()"

                :class="activeTab === 'concordancia' ? 'border-rose-600 text-rose-600 dark:text-rose-400 font-bold bg-white dark:bg-slate-800/80 shadow-sm' : 'border-transparent text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800/40'"

                class="px-4 py-2.5 border-b-2 text-xs font-semibold rounded-t-lg transition-all flex items-center gap-2 cursor-pointer">

          <svg class="w-4 h-4 text-sky-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/></svg>

          2. Concordancia y Calibración

        </button>



        <button @click="activeTab = 'correlacion'; loadCorrelation()"

                :class="activeTab === 'correlacion' ? 'border-rose-600 text-rose-600 dark:text-rose-400 font-bold bg-white dark:bg-slate-800/80 shadow-sm' : 'border-transparent text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800/40'"

                class="px-4 py-2.5 border-b-2 text-xs font-semibold rounded-t-lg transition-all flex items-center gap-2 cursor-pointer">

          <svg class="w-4 h-4 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z"/></svg>

          3. Informe de Correlación Diagnóstica

        </button>

      </div>



      <!-- TAB 1: Instrumentos y Evaluadores (Cards A, B, C) -->

      <div x-show="activeTab === 'evaluadores'" class="flex flex-col gap-6">

        <div class="grid grid-cols-1 md:grid-cols-3 gap-5">



          <!-- Card Experto A -->

          <div class="rounded-xl bg-white dark:bg-slate-800/90 border border-slate-200 dark:border-slate-700/80 p-5 flex flex-col justify-between shadow-sm dark:shadow-md transition-all">

            <div>

              <div class="flex justify-between items-start mb-3">

                <div>

                  <span class="text-[11px] font-mono uppercase tracking-wider text-slate-500 dark:text-slate-400 font-bold">Evaluador Titular</span>

                  <h3 class="text-lg font-bold text-slate-900 dark:text-white flex items-center gap-2 mt-0.5">

                    Experto A

                    <span class="text-xs font-normal text-slate-500 dark:text-slate-400" x-text="'(Semilla ' + (labels.A?.semilla_orden || 11) + ')'"></span>

                  </h3>

                </div>

                <template x-if="state.experts?.A?.imported">

                  <span class="px-2.5 py-1 text-xs font-semibold rounded-full bg-emerald-50 dark:bg-emerald-950 border border-emerald-300 dark:border-emerald-500/50 text-emerald-800 dark:text-emerald-300 flex items-center gap-1 shadow-sm">

                    ✓ Importado (<span x-text="state.experts.A.completed_count"></span>/54)

                  </span>

                </template>

                <template x-if="!state.experts?.A?.imported">

                  <span class="px-2.5 py-1 text-xs font-semibold rounded-full bg-slate-100 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-600 dark:text-slate-400">

                    Pendiente Entrega

                  </span>

                </template>

              </div>



              <div class="space-y-2 text-xs bg-slate-50 dark:bg-slate-900/80 p-3.5 rounded-lg border border-slate-200 dark:border-slate-800 font-mono">

                <div class="flex justify-between items-center">

                  <span class="text-slate-600 dark:text-slate-400 font-semibold">Código Acceso:</span>

                  <span class="text-rose-600 dark:text-rose-400 font-bold text-sm tracking-wider" x-text="labels.A?.codigo_acceso || '—'"></span>

                </div>

                <div class="flex justify-between items-center">

                  <span class="text-slate-600 dark:text-slate-400 font-semibold">Huella SHA-256:</span>

                  <span class="text-slate-800 dark:text-slate-200 font-mono text-[11px] select-all" x-text="labels.A?.huella_sha256 ? labels.A.huella_sha256.substring(0, 16) + '...' : '—'">—</span>

                </div>

              </div>

            </div>



            <div class="mt-5 pt-4 border-t border-slate-200 dark:border-slate-700/60 flex flex-col gap-2.5">

              <a :href="'/api/human-eval/export/A?sesion_id=' + sesionId"

                 class="w-full py-2.5 px-3 rounded-lg bg-sky-600 hover:bg-sky-700 text-white text-xs font-semibold text-center transition-all shadow-sm flex items-center justify-center gap-2 cursor-pointer">

                <svg class="w-4 h-4 text-sky-100" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/></svg>

                Descargar Kit Ciego (ZIP: XLSX + HTML)

              </a>



              <label class="w-full py-2.5 px-3 rounded-lg bg-rose-600 hover:bg-rose-700 text-white !text-white text-xs font-semibold text-center cursor-pointer transition-all shadow-sm flex items-center justify-center gap-2">

                <svg class="w-4 h-4 text-rose-100" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"/></svg>

                Importar Respuestas (XLSX)

                <input type="file" accept=".xlsx" class="hidden" @change="uploadResponses($event, 'A')">

              </label>

            </div>

          </div>



          <!-- Card Experto B -->

          <div class="rounded-xl bg-white dark:bg-slate-800/90 border border-slate-200 dark:border-slate-700/80 p-5 flex flex-col justify-between shadow-sm dark:shadow-md transition-all">

            <div>

              <div class="flex justify-between items-start mb-3">

                <div>

                  <span class="text-[11px] font-mono uppercase tracking-wider text-slate-500 dark:text-slate-400 font-bold">Evaluador Titular</span>

                  <h3 class="text-lg font-bold text-slate-900 dark:text-white flex items-center gap-2 mt-0.5">

                    Experto B

                    <span class="text-xs font-normal text-slate-500 dark:text-slate-400" x-text="'(Semilla ' + (labels.B?.semilla_orden || 22) + ')'"></span>

                  </h3>

                </div>

                <template x-if="state.experts?.B?.imported">

                  <span class="px-2.5 py-1 text-xs font-semibold rounded-full bg-emerald-50 dark:bg-emerald-950 border border-emerald-300 dark:border-emerald-500/50 text-emerald-800 dark:text-emerald-300 flex items-center gap-1 shadow-sm">

                    ✓ Importado (<span x-text="state.experts.B.completed_count"></span>/54)

                  </span>

                </template>

                <template x-if="!state.experts?.B?.imported">

                  <span class="px-2.5 py-1 text-xs font-semibold rounded-full bg-slate-100 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-600 dark:text-slate-400">

                    Pendiente Entrega

                  </span>

                </template>

              </div>



              <div class="space-y-2 text-xs bg-slate-50 dark:bg-slate-900/80 p-3.5 rounded-lg border border-slate-200 dark:border-slate-800 font-mono">

                <div class="flex justify-between items-center">

                  <span class="text-slate-600 dark:text-slate-400 font-semibold">Código Acceso:</span>

                  <span class="text-sky-600 dark:text-sky-400 font-bold text-sm tracking-wider" x-text="labels.B?.codigo_acceso || '—'"></span>

                </div>

                <div class="flex justify-between items-center">

                  <span class="text-slate-600 dark:text-slate-400 font-semibold">Huella SHA-256:</span>

                  <span class="text-slate-800 dark:text-slate-200 font-mono text-[11px] select-all" x-text="labels.B?.huella_sha256 ? labels.B.huella_sha256.substring(0, 16) + '...' : '—'">—</span>

                </div>

              </div>

            </div>



            <div class="mt-5 pt-4 border-t border-slate-200 dark:border-slate-700/60 flex flex-col gap-2.5">

              <a :href="'/api/human-eval/export/B?sesion_id=' + sesionId"

                 class="w-full py-2.5 px-3 rounded-lg bg-sky-600 hover:bg-sky-700 text-white text-xs font-semibold text-center transition-all shadow-sm flex items-center justify-center gap-2 cursor-pointer">

                <svg class="w-4 h-4 text-sky-100" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/></svg>

                Descargar Kit Ciego (ZIP: XLSX + HTML)

              </a>



              <label class="w-full py-2.5 px-3 rounded-lg bg-rose-600 hover:bg-rose-700 text-white !text-white text-xs font-semibold text-center cursor-pointer transition-all shadow-sm flex items-center justify-center gap-2">

                <svg class="w-4 h-4 text-rose-100" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"/></svg>

                Importar Respuestas (XLSX)

                <input type="file" accept=".xlsx" class="hidden" @change="uploadResponses($event, 'B')">

              </label>

            </div>

          </div>



          <!-- Card Experto C (Dirimente) -->

          <div class="rounded-xl bg-white dark:bg-slate-800/90 border border-slate-200 dark:border-slate-700/80 p-5 flex flex-col justify-between shadow-sm dark:shadow-md transition-all">

            <div>

              <div class="flex justify-between items-start mb-3">

                <div>

                  <span class="text-[11px] font-mono uppercase tracking-wider text-slate-500 dark:text-slate-400 font-bold">Árbitro Dirimente</span>

                  <h3 class="text-lg font-bold text-slate-900 dark:text-white flex items-center gap-2 mt-0.5">

                    Experto C

                    <span class="text-xs font-normal text-slate-500 dark:text-slate-400" x-text="'(Semilla ' + (labels.C?.semilla_orden || 33) + ')'"></span>

                  </h3>

                </div>

                <template x-if="state.experts?.C?.imported">

                  <span class="px-2.5 py-1 text-xs font-semibold rounded-full bg-emerald-50 dark:bg-emerald-950 border border-emerald-300 dark:border-emerald-500/50 text-emerald-800 dark:text-emerald-300 flex items-center gap-1 shadow-sm">

                    ✓ Dirimido (<span x-text="state.experts.C.completed_count"></span>)

                  </span>

                </template>

                <template x-if="!state.experts?.C?.imported">

                  <span class="px-2.5 py-1 text-xs font-semibold rounded-full bg-purple-50 dark:bg-purple-950 border border-purple-300 dark:border-purple-500/50 text-purple-800 dark:text-purple-300 font-medium">

                    Condicional

                  </span>

                </template>

              </div>



              <div class="space-y-2 text-xs bg-slate-50 dark:bg-slate-900/80 p-3.5 rounded-lg border border-slate-200 dark:border-slate-800 font-mono">

                <div class="flex justify-between items-center">

                  <span class="text-slate-600 dark:text-slate-400 font-semibold">Código Acceso:</span>

                  <span class="text-purple-600 dark:text-purple-400 font-bold text-sm tracking-wider" x-text="labels.C?.codigo_acceso || '—'"></span>

                </div>

                <div class="flex justify-between items-center">

                  <span class="text-slate-600 dark:text-slate-400 font-semibold">Huella SHA-256:</span>

                  <span class="text-slate-800 dark:text-slate-200 font-mono text-[11px] select-all" x-text="labels.C?.huella_sha256 ? labels.C.huella_sha256.substring(0, 16) + '...' : '—'">—</span>

                </div>

              </div>

            </div>



            <div class="mt-5 pt-4 border-t border-slate-200 dark:border-slate-700/60 flex flex-col gap-2.5">

              <template x-if="state.experts?.A?.imported && state.experts?.B?.imported">

                <button @click="emitTiebreak()"

                        class="w-full py-2.5 px-3 rounded-lg bg-purple-600 hover:bg-purple-700 text-white text-xs font-semibold text-center transition-all shadow-sm flex items-center justify-center gap-2 cursor-pointer">

                  <svg class="w-4 h-4 text-purple-200" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>

                  Emitir Cuaderno Dirimente C

                </button>

              </template>

              <template x-if="!(state.experts?.A?.imported && state.experts?.B?.imported)">

                <div class="w-full py-2.5 px-3 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 border border-slate-200 dark:border-slate-700 text-xs font-medium text-center flex items-center justify-center">

                  Requiere importar A y B

                </div>

              </template>



              <template x-if="state.experts?.C?.emitted">

                <div class="flex gap-2">

                  <a :href="'/api/human-eval/export/C?sesion_id=' + sesionId"

                     class="flex-1 py-2.5 px-2 rounded-lg bg-sky-600 hover:bg-sky-700 text-white text-xs font-semibold text-center transition-all shadow-sm">

                    Descargar Kit C

                  </a>

                  <label class="flex-1 py-2.5 px-2 rounded-lg bg-rose-600 hover:bg-rose-700 text-white !text-white text-xs font-semibold text-center cursor-pointer transition-all shadow-sm">

                    Importar C

                    <input type="file" accept=".xlsx" class="hidden" @change="uploadResponses($event, 'C')">

                  </label>

                </div>

              </template>

            </div>

          </div>



        </div>

      </div>



      <!-- TAB 2: Concordancia y Calibración Inter-Evaluador -->

      <div x-show="activeTab === 'concordancia'" class="flex flex-col gap-6">

        <div class="space-y-6">



          <!-- Semáforo de Concordancia Inter-Evaluador -->

          <div class="rounded-xl bg-white dark:bg-slate-800/90 border border-slate-200 dark:border-slate-700/80 p-5 shadow-sm">

            <div class="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 mb-4">

              <h3 class="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">

                <span class="w-2.5 h-2.5 rounded-full bg-sky-500"></span>

                Matriz de Concordancia Inter-Evaluador (A vs B) • IC 95% Bootstrap (1000 remuestreos)

              </h3>

              <div class="flex items-center gap-2">

                <a :href="'/api/human-eval/export/excel?sesion_id=' + sesionId"

                   class="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white !text-white text-xs font-semibold transition-all shadow-sm flex items-center gap-1.5 cursor-pointer"

                   title="Descargar libro Excel con matriz completa de asignación, concordancia y correlación">

                  <svg width="15" height="15" class="w-3.5 h-3.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M3 14h18m-9-4v8m-7 4h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/></svg>

                  Descargar Excel

                </a>

                <a :href="'/api/human-eval/export/correlation-pdf?sesion_id=' + sesionId"

                   class="px-3 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-700 text-white !text-white text-xs font-semibold transition-all shadow-sm flex items-center gap-1.5 cursor-pointer"

                   title="Descargar reporte técnico de correlación en PDF">

                  <svg width="15" height="15" class="w-3.5 h-3.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"/></svg>

                  Descargar PDF

                </a>

              </div>

            </div>



            <div class="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-700 custom-scrollbar">

              <table class="w-full min-w-[620px] text-left text-xs border-collapse">

                <thead class="sticky top-0 bg-slate-50 dark:bg-slate-900/95 z-10 border-b border-slate-200 dark:border-slate-700 backdrop-blur-xs">

                  <tr class="text-slate-600 dark:text-slate-400 uppercase font-mono">

                    <th class="py-2.5 px-3">Criterio / Métrica</th>

                    <th class="py-2.5 px-3 text-center">Valor Estimado</th>

                    <th class="py-2.5 px-3 text-center">IC 95% Bootstrap</th>

                    <th class="py-2.5 px-3 text-center">Umbral Mínimo</th>

                    <th class="py-2.5 px-3 text-center">Dictamen</th>

                  </tr>

                </thead>

                <tbody class="divide-y divide-slate-100 dark:divide-slate-700/60 text-slate-800 dark:text-slate-200 font-mono">

                  <tr>

                    <td class="py-2.5 px-3 font-sans font-semibold">Acuerdo Exacto C1 (Causa Raíz)</td>

                    <td class="py-2.5 px-3 text-center font-bold text-slate-900 dark:text-white" x-text="formatVal(agreementData?.acuerdo_exacto_c1)">—</td>

                    <td class="py-2.5 px-3 text-center text-slate-600 dark:text-slate-400" x-text="formatCi(agreementData?.acuerdo_exacto_c1_ci)">—</td>

                    <td class="py-2.5 px-3 text-center text-slate-500">—</td>

                    <td class="py-2.5 px-3 text-center">

                      <span class="px-2 py-0.5 rounded text-[10px] font-bold" :class="getBadgeClass(agreementData?.acuerdo_exacto_c1_dictamen)" x-text="agreementData?.acuerdo_exacto_c1_dictamen || 'Sin datos'">Sin datos</span>

                    </td>

                  </tr>

                  <tr>

                    <td class="py-2.5 px-3 font-sans font-semibold">Kappa Cuadrático Ponderado C1</td>

                    <td class="py-2.5 px-3 text-center font-bold text-slate-900 dark:text-white" x-text="formatVal(agreementData?.kappa_ponderado_c1)">—</td>

                    <td class="py-2.5 px-3 text-center text-slate-600 dark:text-slate-400" x-text="formatCi(agreementData?.kappa_ponderado_c1_ci)">—</td>

                    <td class="py-2.5 px-3 text-center text-slate-500">≥ 0.610</td>

                    <td class="py-2.5 px-3 text-center">

                      <span class="px-2 py-0.5 rounded text-[10px] font-bold" :class="getBadgeClass(agreementData?.kappa_ponderado_c1_dictamen)" x-text="agreementData?.kappa_ponderado_c1_dictamen || 'Sin datos'">Sin datos</span>

                    </td>

                  </tr>

                  <tr>

                    <td class="py-2.5 px-3 font-sans font-semibold">Kappa de Cohen S (Sustentado)</td>

                    <td class="py-2.5 px-3 text-center font-bold text-slate-900 dark:text-white" x-text="formatVal(agreementData?.kappa_s)">—</td>

                    <td class="py-2.5 px-3 text-center text-slate-600 dark:text-slate-400" x-text="formatCi(agreementData?.kappa_s_ci)">—</td>

                    <td class="py-2.5 px-3 text-center text-slate-500">≥ 0.610</td>

                    <td class="py-2.5 px-3 text-center">

                      <span class="px-2 py-0.5 rounded text-[10px] font-bold" :class="getBadgeClass(agreementData?.kappa_s_dictamen)" x-text="agreementData?.kappa_s_dictamen || 'Sin datos'">Sin datos</span>

                    </td>

                  </tr>

                  <tr>

                    <td class="py-2.5 px-3 font-sans font-semibold">ICC(2,1) Rúbrica Continua 0–5</td>

                    <td class="py-2.5 px-3 text-center font-bold text-slate-900 dark:text-white" x-text="formatVal(agreementData?.icc_2_1)">—</td>

                    <td class="py-2.5 px-3 text-center text-slate-600 dark:text-slate-400" x-text="formatCi(agreementData?.icc_2_1_ci)">—</td>

                    <td class="py-2.5 px-3 text-center text-slate-500">≥ 0.750</td>

                    <td class="py-2.5 px-3 text-center">

                      <span class="px-2 py-0.5 rounded text-[10px] font-bold" :class="getBadgeClass(agreementData?.icc_2_1_dictamen)" x-text="agreementData?.icc_2_1_dictamen || 'Sin datos'">Sin datos</span>

                    </td>

                  </tr>



                  <!-- Filas dinámicas por ítem ordinal C1-C6 -->

                  <template x-for="alf in (agreementData?.alfas_ordinales || defaultAlfas)" :key="alf.item">

                    <tr>

                      <td class="py-2 px-3 font-sans" x-text="'Alfa Ordinal ' + alf.item + (alf.desc ? ' (' + alf.desc + ')' : '')"></td>

                      <td class="py-2 px-3 text-center font-bold text-slate-900 dark:text-white" x-text="formatVal(alf.alfa)">—</td>

                      <td class="py-2 px-3 text-center text-slate-600 dark:text-slate-400" x-text="alf.ci_inferior != null ? '[' + Number(alf.ci_inferior).toFixed(3) + ', ' + Number(alf.ci_superior).toFixed(3) + ']' : '—'">—</td>

                      <td class="py-2 px-3 text-center text-slate-500">≥ 0,800 / ≥ 0,667</td>

                      <td class="py-2 px-3 text-center">

                        <span class="px-2 py-0.5 rounded text-[10px] font-bold" :class="getBadgeClass(alf.dictamen)" x-text="alf.dictamen || 'Sin datos'">Sin datos</span>

                      </td>

                    </tr>

                  </template>

                </tbody>

              </table>

            </div>

          </div>



          <!-- Validación Frente al Evaluador Automático -->

          <div class="rounded-xl bg-white dark:bg-slate-800/90 border border-slate-200 dark:border-slate-700/80 p-5 shadow-sm">

            <h3 class="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2 mb-4">

              <span class="w-2.5 h-2.5 rounded-full bg-rose-500"></span>

              Validación Convergente: Evaluador Automático (Capa 7) frente a Consenso Humano

            </h3>



            <div class="grid grid-cols-1 md:grid-cols-4 gap-4">

              <div class="bg-slate-50 dark:bg-slate-900/60 p-4 rounded-xl border border-slate-200 dark:border-slate-700 text-center shadow-sm">

                <div class="text-xs text-slate-500 dark:text-slate-400 uppercase font-mono font-bold">Concordancia Kappa</div>

                <div class="text-2xl font-bold font-mono mt-1 text-slate-900 dark:text-rose-400" x-text="formatVal(agreementData?.auto_vs_human?.kappa)">—</div>

                <div class="text-[11px] text-slate-600 dark:text-slate-400 mt-1">Acuerdo de Veredicto</div>

              </div>



              <div class="bg-slate-50 dark:bg-slate-900/60 p-4 rounded-xl border border-slate-200 dark:border-slate-700 text-center shadow-sm">

                <div class="text-xs text-slate-500 dark:text-slate-400 uppercase font-mono font-bold">Spearman Rúbricas</div>

                <div class="text-2xl font-bold font-mono mt-1 text-slate-900 dark:text-sky-400" x-text="formatVal(agreementData?.auto_vs_human?.spearman?.rho)">—</div>

                <div class="text-[11px] text-slate-600 dark:text-slate-400 mt-1" x-text="agreementData?.auto_vs_human?.spearman?.p_value != null ? 'p = ' + Number(agreementData.auto_vs_human.spearman.p_value).toFixed(4) : 'p = —'">p = —</div>

              </div>



              <div class="bg-slate-50 dark:bg-slate-900/60 p-4 rounded-xl border border-slate-200 dark:border-slate-700 text-center shadow-sm">

                <div class="text-xs text-slate-500 dark:text-slate-400 uppercase font-mono font-bold">Bland-Altman Dif. Media</div>

                <div class="text-2xl font-bold font-mono mt-1 text-slate-900 dark:text-emerald-400" x-text="formatVal(agreementData?.auto_vs_human?.bland_altman?.mean_diff)">—</div>

                <div class="text-[11px] text-slate-600 dark:text-slate-400 mt-1" x-text="agreementData?.auto_vs_human?.bland_altman?.lower_limit != null ? 'IC: [' + Number(agreementData.auto_vs_human.bland_altman.lower_limit).toFixed(2) + ', ' + Number(agreementData.auto_vs_human.bland_altman.upper_limit).toFixed(2) + ']' : 'IC: [—, —]'">IC: [—, —]</div>

              </div>



              <div class="bg-slate-50 dark:bg-slate-900/60 p-4 rounded-xl border border-slate-200 dark:border-slate-700 text-center shadow-sm">

                <div class="text-xs text-slate-500 dark:text-slate-400 uppercase font-mono font-bold">Matriz de Confusión</div>

                <div class="text-sm font-mono text-slate-900 dark:text-slate-100 mt-2 font-bold">

                  <span class="text-emerald-600 dark:text-emerald-400" x-text="'TP=' + (agreementData?.auto_vs_human?.confusion_matrix?.TP ?? '—')">TP=—</span> •

                  <span class="text-blue-600 dark:text-blue-400" x-text="'TN=' + (agreementData?.auto_vs_human?.confusion_matrix?.TN ?? '—')">TN=—</span> •

                  <span class="text-amber-600 dark:text-amber-400" x-text="'FP=' + (agreementData?.auto_vs_human?.confusion_matrix?.FP ?? '—')">FP=—</span> •

                  <span class="text-rose-600 dark:text-rose-400" x-text="'FN=' + (agreementData?.auto_vs_human?.confusion_matrix?.FN ?? '—')">FN=—</span>

                </div>

                <div class="text-[11px] text-slate-600 dark:text-slate-400 mt-1">Veredictos Binarios</div>

              </div>

            </div>

          </div>



        </div>

      </div>



      <!-- TAB 3: Informe de Correlación Diagnóstica -->

      <div x-show="activeTab === 'correlacion'" class="flex flex-col gap-6">

        <div class="space-y-6">



          <!-- Aviso de Error si la llamada a la API falla -->

          <template x-if="correlationError">

            <div class="p-4 rounded-xl bg-rose-50 dark:bg-rose-950/80 border border-rose-300 dark:border-rose-700 text-rose-800 dark:text-rose-200 font-mono text-xs shadow-sm">

              <strong>Aviso de análisis:</strong> <span x-text="correlationError"></span>

            </div>

          </template>



          <div class="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">

            <h3 class="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">

              <span class="w-2.5 h-2.5 rounded-full bg-emerald-500"></span>

              Matriz de Correlación Interítem de Spearman (C1 a C6, S, U)

            </h3>

            <div class="flex items-center gap-2">

              <a :href="'/api/human-eval/export/excel?sesion_id=' + sesionId"

                 class="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white !text-white text-xs font-semibold transition-all shadow-sm flex items-center gap-1.5 cursor-pointer"

                 title="Descargar libro Excel con matriz completa de asignación, concordancia y correlación">

                <svg width="15" height="15" class="w-3.5 h-3.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M3 14h18m-9-4v8m-7 4h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/></svg>

                Descargar Excel

              </a>

              <a :href="'/api/human-eval/export/correlation-pdf?sesion_id=' + sesionId"

                 class="px-3 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-700 text-white !text-white text-xs font-semibold transition-all shadow-sm flex items-center gap-1.5 cursor-pointer"

                 title="Descargar reporte técnico de correlación en PDF">

                <svg width="15" height="15" class="w-3.5 h-3.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"/></svg>

                Descargar PDF

              </a>

              <a :href="'/api/human-eval/export/correlation?sesion_id=' + sesionId"

                 class="px-3 py-1.5 rounded-lg bg-sky-600 hover:bg-sky-700 text-white !text-white text-xs font-semibold transition-all shadow-sm flex items-center gap-1.5 cursor-pointer"

                 title="Descargar informe técnico de correlación en HTML">

                <svg width="15" height="15" class="w-3.5 h-3.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"/></svg>

                Descargar HTML

              </a>

            </div>

          </div>



          <!-- Mapa de Calor: Matriz Interítem -->

          <div class="rounded-xl bg-white dark:bg-slate-800/90 border border-slate-200 dark:border-slate-700/80 p-5 shadow-sm">

            <div class="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-700 custom-scrollbar">

              <table class="w-full min-w-[620px] text-center text-xs border-collapse">

                <thead class="sticky top-0 bg-slate-50 dark:bg-slate-900/95 z-10 border-b border-slate-200 dark:border-slate-700 backdrop-blur-xs">

                  <tr class="text-slate-700 dark:text-slate-300 font-mono font-bold">

                    <th class="py-2.5 px-3 text-left">Ítem</th>

                    <template x-for="col in interitemCols" :key="col">

                      <th class="py-2.5 px-3" x-text="col"></th>

                    </template>

                  </tr>

                </thead>

                <tbody class="divide-y divide-slate-100 dark:divide-slate-700/60 font-mono">

                  <template x-for="row in interitemCols" :key="row">

                    <tr>

                      <td class="py-2.5 px-3 text-left font-bold text-slate-800 dark:text-slate-200" x-text="row"></td>

                      <template x-for="col in interitemCols" :key="col">

                        <td class="py-2.5 px-3" :class="getHeatmapCellClass(correlationData?.analisis_1_interitem?.[row.toLowerCase()]?.[col.toLowerCase()]?.rho)"

                            x-text="formatRho(correlationData?.analisis_1_interitem?.[row.toLowerCase()]?.[col.toLowerCase()]?.rho)">—</td>

                      </template>

                    </tr>

                  </template>

                </tbody>

              </table>

            </div>

          </div>



          <!-- Hallazgos Principales -->

          <div class="bg-rose-50 dark:bg-rose-950/20 border border-rose-200 dark:border-rose-900/50 rounded-xl p-4 shadow-sm">

            <div class="text-xs font-bold text-rose-700 dark:text-rose-400 uppercase tracking-wider mb-2">Hallazgos Principales del Estudio:</div>

            <ul class="list-disc list-inside space-y-1 text-xs text-slate-700 dark:text-slate-300">

              <template x-for="h in (correlationData?.hallazgos_principales || ['Ejecución de validación inter-evaluador sin datos cargados'])" :key="h">

                <li x-text="h"></li>

              </template>

            </ul>

          </div>



          <!-- Bloque de restricción si es ciego -->

          <template x-if="isBlind">

            <div class="bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800/60 rounded-xl p-5 shadow-sm">

              <div class="flex items-center gap-2 text-amber-800 dark:text-amber-300 font-bold text-sm mb-1">

                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>

                Evaluación Ciega en Curso

              </div>

              <p class="text-xs text-slate-700 dark:text-slate-300">

                Los análisis de <strong>Calidad frente a Costo</strong> (TTFT, tok/s, latencia, energía) y <strong>Calidad frente a Tamaño de Modelo</strong> (Kruskal-Wallis y d de Cohen) se encuentran estrictamente restringidos conforme al protocolo de prueba ciega.

              </p>

              <div class="mt-3">

                <template x-if="state.phase === 'CONCORDANCIA_CALCULADA'">

                  <button @click="showOpenKeyModal = true"

                          class="px-3.5 py-2 rounded-lg bg-amber-600 hover:bg-amber-700 text-white text-xs font-semibold cursor-pointer shadow-sm">

                    Abrir Clave para Desbloquear Análisis

                  </button>

                </template>

                <template x-if="state.phase !== 'CONCORDANCIA_CALCULADA'">

                  <span class="text-xs text-amber-700 dark:text-amber-400 italic">

                    La clave podrá abrirse una vez importadas las respuestas de A y B y calculada la concordancia.

                  </span>

                </template>

              </div>

            </div>

          </template>

        </div>

      </div>



      <!-- Modal de Confirmación para Abrir Clave -->

      <div x-show="showOpenKeyModal"

           class="fixed inset-0 bg-slate-950/70 backdrop-blur-sm flex items-center justify-center p-4 z-50"

           x-cloak>

        <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-rose-700/60 rounded-xl max-w-md w-full p-6 shadow-2xl space-y-4">

          <div class="flex items-center gap-2 text-rose-600 dark:text-rose-400 font-bold text-base">

            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>

            Confirmación de Apertura de Clave Ciega

          </div>



          <p class="text-xs text-slate-700 dark:text-slate-300 leading-relaxed">

            La apertura de la clave de cegamiento es una acción <strong>irreversible</strong> conforme a las directrices de validación de tesis. Revelará la identidad de los modelos y registrará una marca de auditoría con fecha y hora.

          </p>



          <div>

            <label class="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">Motivo o justificación académica:</label>

            <input type="text" x-model="openKeyMotivo"

                   class="w-full bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-900 dark:text-white focus:outline-none focus:border-rose-500">

          </div>



          <div class="flex justify-end gap-2 pt-2">

            <button @click="showOpenKeyModal = false"

                    class="px-3.5 py-2 rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 text-xs font-medium cursor-pointer">

              Cancelar

            </button>

            <button @click="confirmOpenKey()"

                    class="px-3.5 py-2 rounded-lg bg-rose-600 hover:bg-rose-700 text-white !text-white text-xs font-semibold cursor-pointer shadow-sm">

              Confirmar y Abrir Clave

            </button>

          </div>

        </div>

      </div>



    </div>



    <script>

    function humanEvalView(initialSesionId, initialIsBlind) {

      return {

        sesionId: initialSesionId,

        isBlind: initialIsBlind,

        loading: false,

        activeTab: 'evaluadores',

        state: {},

        labels: {},

        agreementData: null,

        correlationData: null,

        correlationError: null,

        showOpenKeyModal: false,

        openKeyMotivo: 'Apertura formal de clave para análisis desglosados',

        interitemCols: ['C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'S', 'U'],

        defaultAlfas: [

          { item: 'C1', desc: 'Causa Raíz', alfa: null, ci_inferior: null, ci_superior: null, dictamen: 'Sin datos' },

          { item: 'C2', desc: 'Coherencia Técnica', alfa: null, ci_inferior: null, ci_superior: null, dictamen: 'Sin datos' },

          { item: 'C3', desc: 'Fundamentación Normativa', alfa: null, ci_inferior: null, ci_superior: null, dictamen: 'Sin datos' },

          { item: 'C4', desc: 'Componente Afectado', alfa: null, ci_inferior: null, ci_superior: null, dictamen: 'Sin datos' },

          { item: 'C5', desc: 'Mitigación', alfa: null, ci_inferior: null, ci_superior: null, dictamen: 'Sin datos' },

          { item: 'C6', desc: 'Exactitud Factual', alfa: null, ci_inferior: null, ci_superior: null, dictamen: 'Sin datos' },

        ],



        formatVal(val) {

          if (val == null) return '—';

          return Number(val).toFixed(3);

        },



        formatCi(ci) {

          if (!ci || !Array.isArray(ci) || ci.length < 2 || ci[0] == null) return '—';

          return '[' + Number(ci[0]).toFixed(3) + ', ' + Number(ci[1]).toFixed(3) + ']';

        },



        formatRho(val) {

          if (val == null) return '—';

          return Number(val).toFixed(2);

        },



        getBadgeClass(dictamen) {

          if (!dictamen) return 'bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 border border-slate-200 dark:border-slate-700';

          const d = dictamen.toLowerCase();

          if (d.includes('sust' + 'ancial') || d.includes('conf' + 'iable') || d.includes('bue' + 'no'))

            return 'bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-600 font-bold';

          if (d.includes('moderado') || d.includes('tentativo'))

            return 'bg-sky-100 dark:bg-sky-950 text-sky-800 dark:text-sky-300 border border-sky-300 dark:border-sky-600 font-bold';

          if (d.includes('informativo'))

            return 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-300 dark:border-slate-700';

          return 'bg-rose-100 dark:bg-rose-950 text-rose-800 dark:text-rose-300 border border-rose-300 dark:border-rose-600 font-bold';

        },



        getHeatmapCellClass(rho) {

          if (rho == null) return 'text-slate-400 dark:text-slate-500';

          if (rho >= 0.70) return 'bg-emerald-100 dark:bg-emerald-950/70 text-emerald-800 dark:text-emerald-300 font-bold';

          if (rho >= 0.40) return 'bg-sky-100 dark:bg-sky-950/70 text-sky-800 dark:text-sky-300 font-semibold';

          if (rho < -0.10) return 'bg-rose-100 dark:bg-rose-950/70 text-rose-800 dark:text-rose-300 font-semibold';

          return 'text-slate-700 dark:text-slate-300';

        },



        async refreshData() {
          this.loading = true;
          try {
            await this.loadState();
            await this.loadLabels();
            if (this.activeTab === 'concordancia' && typeof this.loadAgreement === 'function') {
              await this.loadAgreement();
            }
            if (this.activeTab === 'correlacion' && typeof this.loadCorrelation === 'function') {
              await this.loadCorrelation();
            }
            if (window.triggerToast) {
              window.triggerToast('<strong class="text-emerald-400">✓ Validación Humana:</strong> Datos y métricas actualizados.');
            }
          } catch(e) {
            console.error('Error al actualizar datos:', e);
          } finally {
            this.loading = false;
          }
        },

        async initData() {

          const mainHdr = document.getElementById('mainViewHeader');

          if (mainHdr) mainHdr.style.display = 'none';

          const mainCont = document.getElementById('mainViewContainer');

          if (mainCont) {

            mainCont.classList.remove('overflow-hidden');

            mainCont.classList.add('overflow-y-auto', 'custom-scrollbar');

          }

          await this.loadState();

          await this.loadLabels();

        },



        async loadState() {

          try {

            const r = await fetch('/api/human-eval/state?sesion_id=' + this.sesionId);

            this.state = await r.json();

            this.isBlind = (this.state.phase !== 'CLAVE_ABIERTA');

          } catch(e) {

            console.error('Error cargando estado:', e);

          }

        },



        async loadLabels() {

          try {

            const r = await fetch('/api/human-eval/labels?sesion_id=' + this.sesionId);

            this.labels = await r.json();

          } catch(e) {

            console.error('Error cargando etiquetas:', e);

          }

        },



        async loadAgreement() {

          try {

            const r = await fetch('/api/human-eval/agreement?sesion_id=' + this.sesionId);

            this.agreementData = await r.json();

          } catch(e) {

            console.error('Error cargando concordancia:', e);

          }

        },



        async loadCorrelation() {

          try {

            const r = await fetch('/api/human-eval/correlation?sesion_id=' + this.sesionId);

            const data = await r.json();

            if (!r.ok || data.ok === false) {

              this.correlationError = data.error || data.detail || 'Error al calcular correlación';

              this.correlationData = null;

            } else {

              this.correlationError = null;

              this.correlationData = data;

            }

          } catch(e) {

            this.correlationError = 'Error de conexión: ' + e;

            this.correlationData = null;

          }

        },



        async uploadResponses(event, expertId) {

          const file = event.target.files[0];

          if (!file) return;



          try {

            const url = '/api/human-eval/import?sesion_id=' + encodeURIComponent(this.sesionId) + '&filename=' + encodeURIComponent(file.name);

            const r = await fetch(url, {

              method: 'POST',

              headers: { 'Content-Type': 'application/octet-stream' },

              body: file

            });

            const res = await r.json();

            if (res.ok) {

              alert('✓ Respuestas de Experto ' + expertId + ' validadas e importadas exitosamente (' + res.evaluated_count + ' corridas).');

              await this.loadState();

            } else {

              alert('Error al importar: ' + (res.error || res.detail));

            }

          } catch(e) {

            alert('Error de conexión al importar: ' + e);

          }

        },



        async emitTiebreak() {

          try {

            const r = await fetch('/api/human-eval/emit-tiebreak?sesion_id=' + this.sesionId, {

              method: 'POST'

            });

            const res = await r.json();

            if (res.ok) {

              alert('✓ Paquete dirimente para Experto C emitido exitosamente (' + res.disagreements_count + ' discrepancias).');

              await this.loadState();

            } else {

              alert('Error: ' + (res.error || res.detail));

            }

          } catch(e) {

            alert('Error al emitir dirimente: ' + e);

          }

        },



        async confirmOpenKey() {

          try {

            const r = await fetch('/api/human-eval/open-key?sesion_id=' + this.sesionId, {

              method: 'POST',

              headers: { 'Content-Type': 'application/json' },

              body: JSON.stringify({ motivo: this.openKeyMotivo })

            });

            const res = await r.json();

            if (res.ok) {

              this.showOpenKeyModal = false;

              this.isBlind = false;

              await this.loadState();

              if (this.activeTab === 'correlacion') await this.loadCorrelation();

              alert('✓ Clave de cegamiento abierta exitosamente y registrada en auditoría.');

            } else {

              alert('Error al abrir clave: ' + (res.error || res.detail));

            }

          } catch(e) {

            alert('Error al abrir clave: ' + e);

          }

        },



        async initNewSession() {

          if (!confirm('¿Desea inicializar una nueva sesión de evaluación humana con muestra estratificada?')) return;

          try {

            const r = await fetch('/api/human-eval/init', {

              method: 'POST',

              headers: { 'Content-Type': 'application/json' },

              body: JSON.stringify({ seed: 2026 })

            });

            const data = await r.json();

            if (data.ok) {

              this.sesionId = data.sesion_id;

              await this.loadState();

              await this.loadLabels();

              alert('✓ Sesión ' + data.sesion_id + ' inicializada con 54 corridas.');

            } else {

              alert('Error al inicializar sesión: ' + (data.error || data.detail));

            }

          } catch(e) {

            alert('Error de conexión al inicializar sesión: ' + e);

          }

        }

      };

    }

    </script>

    """

    html = html.replace("__SESION_ID__", active_id).replace("__IS_BLIND__", str(is_blind).lower())

    return HTMLResponse(content=html, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})



