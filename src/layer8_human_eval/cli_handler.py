"""
NetDiagBench-L7: Layer 8 - Interfaz CLI de Typer para Evaluación Humana (cli_handler.py)
Implementa los comandos:
- benchapp human-eval init --seed 2026
- benchapp human-eval emit --expert A|B
- benchapp human-eval import <xlsx>
- benchapp human-eval emit-tiebreak
- benchapp human-eval analyze
- benchapp human-eval export-agreement
- benchapp human-eval correlate [--open-key]
- benchapp human-eval status
"""

import csv
import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.core.config import PROJECT_ROOT
from src.core.contracts import ClaveCegamientoEntry
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
from src.layer8_human_eval.exporter_packet import export_expert_packet_html as export_blind_packet_html
from src.layer8_human_eval.exporter_xlsx import export_expert_instrument as export_expert_workbook
from src.layer8_human_eval.importer import import_expert_responses
from src.layer8_human_eval.labels import (
    generate_expert_label,
    load_etiquetas,
    save_etiquetas,
)
from src.layer8_human_eval.sampler import (
    build_anonymized_card,
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

human_eval_app = typer.Typer(
    name="human-eval",
    help="Capa 8: Módulo de Validación Humana, Prueba Ciega y Calibración Inter-Evaluador",
)
console = Console()


@human_eval_app.command("init")
def cmd_init(
    seed: int = typer.Option(2026, "--seed", "-s", help="Semilla generadora de la muestra estratificada y códigos ciegos"),
    sesion_id: Optional[str] = typer.Option(None, "--session-id", help="Identificador único de sesión (por defecto timestamp)"),
):
    """Inicializa una sesión de evaluación: muestra estratificada (54 corridas), clave de cegamiento y etiquetas."""
    try:
        active_id, s_dir = create_new_session_dir(sesion_id)
    except FileExistsError as fee:
        console.print(f"[bold red]Error al inicializar sesión:[/bold red] {fee}")
        raise typer.Exit(code=1)
    except ValueError as ve:
        console.print(f"[bold red]Error de validación:[/bold red] {ve}")
        raise typer.Exit(code=1)

    set_active_session(active_id)

    console.print(f"[bold cyan]Inicializando Sesión de Evaluación Humana:[/bold cyan] [yellow]{active_id}[/yellow]")
    console.print(f"Directorio de sesión: [dim]{s_dir}[/dim]")

    # 1. Generar muestra estratificada de 54 corridas
    console.print(f"Generando muestra estratificada con semilla {seed}...")
    sample = build_stratified_sample(seed=seed)
    console.print(f"[green][OK] Muestra estratificada generada ({len(sample)} corridas: 18 escenarios x 3 modelos).[/green]")

    # 2. Guardar clave restringida
    key_json, key_xlsx = save_blind_key(sample, active_id, seed, s_dir)
    console.print(f"[green][OK] Clave de cegamiento restringida guardada (JSON y Excel).[/green]")

    # 3. Generar etiquetas de los 3 expertos (A, B y C dirimente)
    codes = [s.codigo for s in sample]
    etiqueta_a = generate_expert_label("A", active_id, codes, semilla_orden=11)
    etiqueta_b = generate_expert_label("B", active_id, codes, semilla_orden=22)
    etiqueta_c = generate_expert_label("C", active_id, codes, semilla_orden=33)

    etiquetas_map = {"A": etiqueta_a, "B": etiqueta_b, "C": etiqueta_c}
    etiquetas_path = save_etiquetas(etiquetas_map, s_dir)
    console.print(f"[green][OK] Etiquetas criptográficas generadas y guardadas en {etiquetas_path.name}.[/green]")

    # 4. Mostrar tabla informativa con las credenciales
    table = Table(title=f"Etiquetas Oficiales de Expertos - Sesión {active_id}", border_style="cyan")
    table.add_column("Experto", style="bold yellow")
    table.add_column("Rol", style="magenta")
    table.add_column("Semilla", style="blue")
    table.add_column("Corridas", style="green")
    table.add_column("Código Acceso", style="bold red")
    table.add_column("Huella SHA-256 (prefijo)", style="dim")

    for et in [etiqueta_a, etiqueta_b, etiqueta_c]:
        table.add_row(
            et.expert_id,
            et.rol,
            str(et.semilla_orden),
            str(len(et.orden)),
            et.codigo_acceso,
            et.huella_sha256[:16] + "...",
        )
    console.print(table)
    console.print("[dim]Nota: Para generar los paquetes de los evaluadores A y B ejecute: 'benchapp human-eval emit --expert A'[/dim]")


@human_eval_app.command("emit")
def cmd_emit(
    expert: str = typer.Option(..., "--expert", "-e", help="Identificador del evaluador: 'A' o 'B'"),
    sesion_id: Optional[str] = typer.Option(None, "--session-id", help="Identificador de la sesión (por defecto activa)"),
):
    """Genera el instrumento Excel y el paquete ciego HTML para el evaluador A o B."""
    expert = expert.upper().strip()
    if expert not in ("A", "B"):
        console.print("[bold red]Error: Solo los evaluadores 'A' y 'B' pueden emitirse inicialmente. El experto 'C' se emite con 'emit-tiebreak'.[/bold red]")
        raise typer.Exit(code=1)

    s_dir = get_session_dir(sesion_id)
    active_id = s_dir.name
    etiquetas_path = s_dir / "etiquetas.json"
    clave_json_path = s_dir / "clave_RESTRINGIDA.json"

    if not etiquetas_path.exists() or not clave_json_path.exists():
        console.print("[bold red]Error: Faltan archivos de sesión. Ejecute 'benchapp human-eval init' primero.[/bold red]")
        raise typer.Exit(code=1)

    etiquetas = load_etiquetas(etiquetas_path)
    etiqueta = etiquetas[expert]

    with open(clave_json_path, "r", encoding="utf-8") as f:
        clave_data = json.load(f)
    raw_entries = clave_data.get("entradas", clave_data) if isinstance(clave_data, dict) else clave_data
    sample_entries = [ClaveCegamientoEntry(**e) for e in raw_entries]
    cards_map = load_blind_cards_from_sample(sample_entries)

    console.print(f"[bold cyan]Generando paquete de evaluación para Experto {expert} (Sesión {active_id})...[/bold cyan]")

    # Exportar cuaderno Excel
    xlsx_out = s_dir / f"Instrumento_Experto_{expert}_{active_id}.xlsx"
    export_expert_workbook(etiqueta, cards_map, xlsx_out)
    console.print(f"[green][OK] Cuaderno Excel generado:[/green] {xlsx_out}")

    # Exportar paquete HTML autocontenido
    html_out = s_dir / f"Paquete_Experto_{expert}_{active_id}.html"
    export_blind_packet_html(etiqueta, cards_map, html_out)
    console.print(f"[green][OK] Paquete ciego HTML generado:[/green] {html_out}")


@human_eval_app.command("import")
def cmd_import(
    file_path: Path = typer.Argument(..., help="Ruta al archivo Instrumento_Experto_<ID>_<sesion>.xlsx"),
    sesion_id: Optional[str] = typer.Option(None, "--session-id", help="Identificador de la sesión (opcional)"),
):
    """Importa y valida el cuaderno Excel con las respuestas de un experto."""
    s_dir = get_session_dir(sesion_id)
    active_id = s_dir.name
    etiquetas_path = s_dir / "etiquetas.json"

    if not etiquetas_path.exists():
        console.print("[bold red]Error: No se encontró etiquetas.json en la sesión.[/bold red]")
        raise typer.Exit(code=1)

    console.print(f"[bold cyan]Validando e importando respuestas de:[/bold cyan] {file_path.name}...")
    try:
        expert_id, rows = import_expert_responses(
            xlsx_path=file_path,
            sesion_id=active_id,
            etiquetas_path=etiquetas_path,
            output_dir=s_dir,
        )
        console.print(f"[bold green][OK] Respuestas del Experto {expert_id} validadas exitosamente![/bold green]")
        console.print(f"Total de corridas evaluadas y conformes: [bold cyan]{len(rows)}[/bold cyan]")
        console.print(f"Archivo generado: [dim]{s_dir / f'respuestas_{expert_id}.csv'}[/dim]")
    except Exception as e:
        console.print(f"[bold red]Error de validación/importación:[/bold red] {e}")
        raise typer.Exit(code=1)


@human_eval_app.command("emit-tiebreak")
def cmd_emit_tiebreak(
    sesion_id: Optional[str] = typer.Option(None, "--session-id", help="Identificador de la sesión (por defecto activa)"),
):
    """Genera el instrumento y paquete del experto dirimente C tras detectar desacuerdos entre A y B."""
    s_dir = get_session_dir(sesion_id)
    active_id = s_dir.name

    resp_a = s_dir / "respuestas_A.csv"
    resp_b = s_dir / "respuestas_B.csv"
    if not resp_a.exists() or not resp_b.exists():
        console.print("[bold red]Error: Se requiere haber importado las respuestas de A y B antes de generar el paquete dirimente.[/bold red]")
        raise typer.Exit(code=1)

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
        c1_a = int(r_a["c1"])
        c1_b = int(r_b["c1"])
        s_a = r_a["s"].strip().lower()
        s_b = r_b["s"].strip().lower()

        if abs(c1_a - c1_b) >= 1 or s_a != s_b:
            disagreements.append(code)

    console.print(f"[bold cyan]Análisis de discrepancias entre A y B (Sesión {active_id}):[/bold cyan]")
    console.print(f"Total de corridas en desacuerdo (|C1A - C1B| >= 1 o S difiere): [bold yellow]{len(disagreements)}[/bold yellow] de 54")

    if not disagreements:
        console.print("[green]No existen desacuerdos entre A y B. El consenso es unánime; no se requiere la intervención del dirimente C.[/green]")
        return

    # Actualizar etiqueta de C con solo las corridas en desacuerdo
    etiquetas_path = s_dir / "etiquetas.json"
    etiquetas = load_etiquetas(etiquetas_path)
    etiqueta_c = etiquetas["C"]
    etiqueta_c.orden = disagreements

    from src.layer8_human_eval.labels import compute_huella
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
    export_expert_workbook(etiqueta_c, cards_map, xlsx_c)

    html_c = s_dir / f"Paquete_Experto_C_{active_id}.html"
    export_blind_packet_html(etiqueta_c, cards_map, html_c)

    console.print(f"[bold green][OK] Paquete dirimente para Experto C generado exitosamente ({len(disagreements)} corridas):[/bold green]")
    console.print(f"Cuaderno Excel: {xlsx_c}")
    console.print(f"Paquete HTML:   {html_c}")


@human_eval_app.command("analyze")
def cmd_analyze(
    sesion_id: Optional[str] = typer.Option(None, "--session-id", help="Identificador de la sesión"),
):
    """Calcula concordancia inter-evaluador (A vs B), consenso y validación frente al evaluador automático."""
    s_dir = get_session_dir(sesion_id)
    active_id = s_dir.name

    resp_a = s_dir / "respuestas_A.csv"
    resp_b = s_dir / "respuestas_B.csv"
    resp_c = s_dir / "respuestas_C.csv"

    if not resp_a.exists() or not resp_b.exists():
        console.print("[bold red]Error: Se requieren al menos las respuestas de A y B importadas.[/bold red]")
        raise typer.Exit(code=1)

    def _read_csv(p: Path):
        with open(p, "r", encoding="utf-8") as f:
            rows = []
            for r in csv.DictReader(f):
                rows.append({
                    "codigo": r["codigo"],
                    "c1": int(r["c1"]),
                    "c2": int(r["c2"]),
                    "c3": int(r["c3"]),
                    "c4": int(r["c4"]),
                    "c5": int(r["c5"]),
                    "c6": int(r["c6"]),
                    "s": r["s"],
                    "u": int(r["u"]),
                    "observacion": r.get("observacion", ""),
                    "rubrica": float(r["rubrica"]),
                })
            return rows

    rows_a = _read_csv(resp_a)
    rows_b = _read_csv(resp_b)
    rows_c = _read_csv(resp_c) if resp_c.exists() else None

    # 1. Resumen de concordancia A vs B
    summary = calculate_agreement_summary(rows_a, rows_b)

    t_agree = Table(title=f"Concordancia Inter-Evaluador (A vs B) - Sesión {active_id}", border_style="cyan")
    t_agree.add_column("Métrica", style="bold")
    t_agree.add_column("Valor Estimado", style="bold green")
    t_agree.add_column("IC 95% Bootstrap", style="dim")
    t_agree.add_column("Criterio Aceptación", style="yellow")
    t_agree.add_column("Dictamen", style="magenta")

    def _dictamen(val, umbral):
        return "[bold green]CUMPLE[/bold green]" if val >= umbral else "[bold red]BAJO[/bold red]"

    t_agree.add_row("Acuerdo Exacto C1", f"{summary['c1_exact_agreement']:.3f}", str(summary['c1_exact_agreement_ci']), ">= 0.70", _dictamen(summary['c1_exact_agreement'], 0.70))
    t_agree.add_row("Kappa Cuadrático C1", f"{summary['c1_quadratic_weighted_kappa']:.3f}", str(summary['c1_quadratic_kappa_ci']), ">= 0.61", _dictamen(summary['c1_quadratic_weighted_kappa'], 0.61))
    t_agree.add_row("Kappa Cohen S", f"{summary['s_cohen_kappa']:.3f}", str(summary['s_cohen_kappa_ci']), ">= 0.40", _dictamen(summary['s_cohen_kappa'], 0.40))
    t_agree.add_row("ICC(2,1) Rúbrica 0-5", f"{summary['rubrica_icc_2_1']:.3f}", str(summary['rubrica_icc_ci']), ">= 0.75", _dictamen(summary['rubrica_icc_2_1'], 0.75))

    for item, d in summary["krippendorff_ordinal_c1_c6"].items():
        t_agree.add_row(f"Alfa Ordinal {item.upper()}", f"{d['alpha']:.3f}", str(d['ci_95']), ">= 0.667", _dictamen(d['alpha'], 0.667))

    console.print(t_agree)

    # 2. Consenso y validación auto vs humano
    consensus = calculate_consensus(rows_a, rows_b, rows_c)
    pendientes = sum(1 for c in consensus if c["c1_consenso"] is None)
    console.print(f"Consenso calculado: [bold cyan]{len(consensus)}[/bold cyan] corridas ([yellow]{pendientes} pendientes[/yellow] de dirimir).")

    # Obtener resultados automáticos de la clave de cegamiento
    clave_json_path = s_dir / "clave_RESTRINGIDA.json"
    auto_dict = {}
    if clave_json_path.exists():
        with open(clave_json_path, "r", encoding="utf-8") as f:
            clave_data = json.load(f)
        entries = clave_data.get("entradas", clave_data) if isinstance(clave_data, dict) else clave_data
        for entry in entries:
            diag_p = PROJECT_ROOT / entry["ruta_diagnostico"]
            if diag_p.exists():
                diag = json.loads(diag_p.read_text(encoding="utf-8"))
                ev = diag.get("evaluation", {})
                auto_dict[entry["codigo"]] = {
                    "scenario_id": entry["scenario_id"],
                    "is_correct": ev.get("is_correct", False),
                    "rubric_score": ev.get("rubric_score", 0.0),
                }

    if auto_dict:
        val_res = validate_auto_vs_human(consensus, auto_dict)
        t_val = Table(title="Validación Evaluador Automático frente a Consenso Humano", border_style="magenta")
        t_val.add_column("Métrica", style="bold")
        t_val.add_column("Valor", style="bold green")
        t_val.add_column("Detalle", style="dim")

        cm = val_res["confusion_matrix"]
        t_val.add_row("Corridas analizadas (n)", str(val_res["n"]), f"{pendientes} excluidas por pendientes")
        t_val.add_row("Matriz de Confusión", f"TP={cm['TP']}, TN={cm['TN']}, FP={cm['FP']}, FN={cm['FN']}", f"Exactitud: {((cm['TP']+cm['TN'])/val_res['n']):.3f}" if val_res['n']>0 else "")
        t_val.add_row("Kappa Auto vs Humano", f"{val_res['kappa']:.3f}", "Concordancia de veredicto binario")
        t_val.add_row("Spearman Rúbricas", f"{val_res['spearman']['rho']:.3f}", f"p-valor = {val_res['spearman']['p_value']}")
        t_val.add_row("Bland-Altman Diferencia Media", f"{val_res['bland_altman']['mean_diff']:.3f}", f"Límites: [{val_res['bland_altman']['lower_limit']:.2f}, {val_res['bland_altman']['upper_limit']:.2f}]")
        console.print(t_val)


@human_eval_app.command("export-agreement")
def cmd_export_agreement(
    sesion_id: Optional[str] = typer.Option(None, "--session-id", help="Identificador de la sesión"),
):
    """Exporta el libro Excel Analisis_Concordancia_<sesion>.xlsx y concordancia.json."""
    s_dir = get_session_dir(sesion_id)
    active_id = s_dir.name

    resp_a = s_dir / "respuestas_A.csv"
    resp_b = s_dir / "respuestas_B.csv"
    resp_c = s_dir / "respuestas_C.csv"

    if not resp_a.exists() or not resp_b.exists():
        console.print("[bold red]Error: Respuestas de A y B necesarias para exportar concordancia.[/bold red]")
        raise typer.Exit(code=1)

    def _read_csv(p: Path):
        with open(p, "r", encoding="utf-8") as f:
            return [{k: (int(v) if k in ("c1","c2","c3","c4","c5","c6","u") else (float(v) if k=="rubrica" else v)) for k, v in r.items()} for r in csv.DictReader(f)]

    rows_a = _read_csv(resp_a)
    rows_b = _read_csv(resp_b)
    rows_c = _read_csv(resp_c) if resp_c.exists() else None

    summary = calculate_agreement_summary(rows_a, rows_b)
    consensus = calculate_consensus(rows_a, rows_b, rows_c)

    # Cargar datos del benchmark si la clave está disponible
    clave_json_path = s_dir / "clave_RESTRINGIDA.json"
    # Cargar métricas automáticas y modelos
    auto_dict = {}
    code_to_model = {}
    if clave_json_path.exists():
        with open(clave_json_path, "r", encoding="utf-8") as f:
            clave_data = json.load(f)
        entries = clave_data.get("entradas", clave_data) if isinstance(clave_data, dict) else clave_data
        for entry in entries:
            code_to_model[entry["codigo"]] = entry["model_id"]
        from src.layer8_human_eval.web_routes import load_session_auto_data
        auto_dict = load_session_auto_data(s_dir, entries)

    val_res = validate_auto_vs_human(consensus, auto_dict) if auto_dict else {}
    models_breakdown = calculate_metrics_by_model(consensus, code_to_model, auto_dict) if code_to_model else {}

    xlsx_path = s_dir / f"Analisis_Concordancia_{active_id}.xlsx"
    export_agreement_workbook(active_id, rows_a, rows_b, consensus, summary, val_res, models_breakdown, xlsx_path)
    console.print(f"[bold green][OK] Libro Excel de Concordancia generado:[/bold green] {xlsx_path}")

    json_path = s_dir / "concordancia.json"
    export_agreement_json(active_id, summary, val_res, models_breakdown, json_path)
    console.print(f"[bold green][OK] Archivo JSON de Concordancia exportado:[/bold green] {json_path}")


@human_eval_app.command("correlate")
def cmd_correlate(
    sesion_id: Optional[str] = typer.Option(None, "--session-id", help="Identificador de la sesión"),
    open_key: bool = typer.Option(False, "--open-key", help="Abrir la clave de cegamiento para desbloquear análisis de costo y modelo"),
):
    """Genera el informe de correlación diagnóstica (HTML, Excel y JSON)."""
    s_dir = get_session_dir(sesion_id)
    active_id = s_dir.name

    if open_key:
        try:
            open_key_audit(active_id, reason="Apertura explícita desde CLI benchapp human-eval correlate")
            console.print("[bold yellow][!] CLAVE DE CEGAMIENTO ABIERTA. Análisis 3 a 5 desbloqueados.[/bold yellow]")
        except ValueError as ve:
            console.print(f"[bold red]Error al abrir clave de cegamiento:[/bold red] {ve}")
            raise typer.Exit(code=1)

    state = get_session_state(active_id)
    is_blind = not state.get("is_key_opened", False)

    resp_a = s_dir / "respuestas_A.csv"
    resp_b = s_dir / "respuestas_B.csv"
    resp_c = s_dir / "respuestas_C.csv"
    clave_json = s_dir / "clave_RESTRINGIDA.json"

    if not resp_a.exists() or not resp_b.exists() or not clave_json.exists():
        console.print("[bold red]Error: Se requieren respuestas de A y B y clave_RESTRINGIDA.json.[/bold red]")
        raise typer.Exit(code=1)

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

    from src.layer8_human_eval.web_routes import load_session_auto_data
    auto_runs_dict = load_session_auto_data(s_dir, entries)

    results_csv_rows = []
    res_csv_p = PROJECT_ROOT / "data" / "benchmark_results" / "resultados.csv"
    if res_csv_p.exists():
        with open(res_csv_p, "r", encoding="utf-8") as f:
            results_csv_rows = list(csv.DictReader(f))

    summary = calculate_agreement_summary(rows_a, rows_b)
    unified_rows = build_correlation_dataset(consensus, key_by_code, results_csv_rows, auto_runs_dict)
    report_data = run_correlation_report(unified_rows, agreement_summary=summary, is_blind=is_blind)

    # 1. Exportar HTML y PDF
    html_path = s_dir / f"Informe_Correlacion_{active_id}.html"
    export_correlation_report_html(report_data, unified_rows, html_path)
    console.print(f"[bold green][OK] Informe HTML generado:[/bold green] {html_path}")

    pdf_path = s_dir / f"Informe_Correlacion_{active_id}.pdf"
    export_correlation_report_pdf(report_data, unified_rows, pdf_path)
    console.print(f"[bold green][OK] Informe PDF generado:[/bold green] {pdf_path}")

    # 2. Anexar hojas Correlación y Datos_correlación en Analisis_Concordancia_<sesion>.xlsx
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
    console.print(f"[bold green][OK] Hojas de correlación anexadas a:[/bold green] {concordancia_xlsx}")

    # 3. Exportar JSON
    json_path = s_dir / "correlacion.json"
    json_path.write_text(json.dumps(report_data, indent=2, ensure_ascii=False), encoding="utf-8")
    console.print(f"[bold green][OK] Datos JSON de Correlación guardados:[/bold green] {json_path}")


@human_eval_app.command("status")
def cmd_status(
    sesion_id: Optional[str] = typer.Option(None, "--session-id", help="Identificador de la sesión"),
):
    """Muestra el estado actual del protocolo de evaluación humana."""
    try:
        s_id = sesion_id or get_active_session_id()
    except Exception as e:
        console.print(f"[bold red]{e}[/bold red]")
        return

    state = get_session_state(s_id)
    if not state.get("active"):
        console.print(f"[yellow]No hay sesión activa con ID: {s_id}[/yellow]")
        return

    table = Table(title=f"Estado de Sesión de Evaluación Humana: {s_id}", border_style="cyan")
    table.add_column("Componente / Evaluador", style="bold")
    table.add_column("Estado", style="bold green")
    table.add_column("Detalle / Archivos", style="dim")

    table.add_row("Clave de Cegamiento", "Generada" if state["has_key"] else "Falta", "clave_RESTRINGIDA.json / .xlsx")
    table.add_row("Estado de Cegamiento", "[bold yellow]ABIERTA (Desbloqueado)[/bold yellow]" if state["is_key_opened"] else "[bold cyan]CIEGA (Restringida)[/bold cyan]", "KEY_OPENED_AUDIT.json" if state["is_key_opened"] else "Análisis de costo restringidos")

    for exp_id in ("A", "B", "C"):
        exp = state["experts"][exp_id]
        if exp["imported"]:
            status_str = f"[bold green]Importado ({exp['completed_count']} corridas)[/bold green]"
        elif exp["emitted"]:
            status_str = "[yellow]Emitido (pendiente de entrega)[/yellow]"
        else:
            status_str = "[dim]No emitido[/dim]"
        detail = f"XLSX: {Path(exp['xlsx_path']).name if exp['xlsx_path'] else '-'}, HTML: {Path(exp['html_path']).name if exp['html_path'] else '-'}"
        table.add_row(f"Experto {exp_id}", status_str, detail)

    table.add_row("Informe de Concordancia", "Listo" if state["has_agreement"] else "Pendiente", f"Analisis_Concordancia_{s_id}.xlsx")
    table.add_row("Informe de Correlación", "Listo" if state["has_correlation"] else "Pendiente", f"Informe_Correlacion_{s_id}.html")

    console.print(table)
