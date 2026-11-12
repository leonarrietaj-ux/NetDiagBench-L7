"""
NetDiagBench-L7: Layer 6 - Command Line Interface (CLI)
Interfaz por línea de comandos desarrollada con Typer y Rich para la ejecución
individual y por lotes del benchmark de diagnóstico L7.
"""

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.core.config import SystemConfig
from src.layer1_lab.runner import ScenarioLabRunner
from src.layer2_pipeline.aggregator import DataPipelineAgent
from src.layer3_rag.retriever import RAGKnowledgeEngine
from src.layer4_inference.engine import LocalInferenceEngine
from src.layer5_orchestrator.agent import DiagnosticOrchestratorAgent
from src.layer8_human_eval.cli_handler import human_eval_app

app = typer.Typer(
    name="benchapp",
    help="NetDiagBench-L7: Herramienta de Diagnóstico y Benchmark para Servicios L7 sobre IP"
)
app.add_typer(human_eval_app, name="human-eval")
console = Console()


@app.command("list-scenarios")
def list_scenarios():
    """Lista todos los escenarios de falla disponibles en el catálogo."""
    runner = ScenarioLabRunner()
    scenarios = runner.list_scenarios()

    table = Table(title="Catálogo de Escenarios L7 (DNS & HTTP/Web/Gateway)", border_style="cyan")
    table.add_column("ID", style="bold green")
    table.add_column("Categoría", style="magenta")
    table.add_column("Clase de Falla", style="yellow")
    table.add_column("Componente Afectado", style="cyan")
    table.add_column("Descripción")

    for s in scenarios:
        table.add_row(
            s.scenario_id,
            s.category.value,
            s.fault_class.value,
            s.ground_truth.affected_component,
            s.description[:60] + "..." if len(s.description) > 60 else s.description
        )

    console.print(table)


@app.command("list-models")
def list_models():
    """Lista la terna de modelos SLM locales configurados para el benchmark."""
    sys_config = SystemConfig()
    table = Table(title="Terna de Modelos de Evaluación (GGUF Q4_K_M)", border_style="blue")
    table.add_column("ID", style="bold green")
    table.add_column("Nombre", style="bold")
    table.add_column("Proveedor", style="cyan")
    table.add_column("Parámetros", style="yellow")
    table.add_column("Licencia", style="magenta")
    table.add_column("VRAM Aprox.", style="red")
    table.add_column("Soporte Tools")

    for m in sys_config.models:
        table.add_row(
            m.id,
            m.name,
            m.provider,
            m.parameters_raw,
            m.license,
            f"{m.approx_vram_gb} GB",
            m.function_calling_support
        )

    console.print(table)


@app.command("rag-query")
def rag_query(
    query_text: str = typer.Argument(..., help="Texto de consulta técnica o síntoma"),
    top_k: int = typer.Option(3, "--top-k", "-k", help="Cantidad de fragmentos a recuperar")
):
    """Consulta la base documental normativa (RFCs 1035/9110 y SOPs) vía RAG."""
    rag = RAGKnowledgeEngine()
    result = rag.query(query_text, top_k=top_k)

    console.print(Panel(f"[bold cyan]Consulta:[/bold cyan] {query_text}\n[bold green]Huella RAM RAG:[/bold green] {result.memory_footprint_mb} MB (Límite: <= 450 MB)"))

    for idx, chunk in enumerate(result.chunks, 1):
        table = Table(title=f"Fragmento {idx}: [{chunk.source_document}] {chunk.section} (Score: {chunk.similarity_score})", border_style="dim")
        table.add_column("Contenido Normativo")
        table.add_row(chunk.content)
        console.print(table)


@app.command("run-scenario")
def run_scenario(
    scenario_id: str = typer.Argument(..., help="ID del escenario (ej: DNS-NXD-01, HTTP-502-01)"),
    model_id: str = typer.Option("qwen3-8b", "--model", "-m", help="ID del modelo (qwen3-8b, glm-4-9b-chat, phi-4-mini-instruct)"),
    seed: int = typer.Option(42, "--seed", "-s", help="Semilla determinista"),
    output_dir: str | None = typer.Option(None, "--output-dir", "-o", help="Directorio para guardar diagnostico.json y .md")
):
    """Ejecuta el pipeline de diagnóstico completo para un escenario y modelo específicos."""
    runner = ScenarioLabRunner()
    scenario = runner.get_scenario(scenario_id)
    if not scenario:
        console.print(f"[bold red]Error:[/bold red] Escenario '{scenario_id}' no encontrado.")
        raise typer.Exit(code=1)

    console.print(f"[bold green]=== Iniciando Diagnóstico: {scenario_id} con {model_id} (Seed {seed}) ===[/bold green]")

    with console.status("[bold blue]1. Generando traza de red y telemetría de laboratorio...[/bold blue]"):
        sc, raw_logs, raw_telemetry = runner.execute_scenario(scenario_id, seed=seed)

    with console.status("[bold blue]2. Normalizando logs con Drain3 y calculando ventana...[/bold blue]"):
        pipeline = DataPipelineAgent()
        ventana = pipeline.process_window(sc, raw_logs, raw_telemetry)

    with console.status("[bold blue]3. Recuperando documentación técnica con RAG congelado...[/bold blue]"):
        rag = RAGKnowledgeEngine()
        rag.freeze()
        observed_sample = " ".join(e.raw_message for e in ventana.parsed_logs[:3]) if ventana.parsed_logs else ""
        query_str = f"{sc.category.value} {observed_sample}".strip()
        contexto_rag = rag.query(query_str, top_k=2)

    with console.status("[bold blue]4. Orquestando diagnóstico con herramientas de red Read-Only...[/bold blue]"):
        engine = LocalInferenceEngine()
        orchestrator = DiagnosticOrchestratorAgent(inference_engine=engine)
        traza, diagnostico, inf_resp = orchestrator.run_diagnosis(
            scenario=sc,
            ventana=ventana,
            contexto_rag=contexto_rag,
            model_id=model_id,
            seed=seed
        )

    # Mostrar Resultados en Consola
    res_table = Table(title="Resultado del Diagnóstico Estructurado", border_style="green")
    res_table.add_column("Campo", style="bold cyan")
    res_table.add_column("Detalle")

    res_table.add_row("Escenario", diagnostico.scenario_id)
    res_table.add_row("Modelo", diagnostico.model_id)
    res_table.add_row("Causa Raíz", f"[bold yellow]{diagnostico.root_cause}[/bold yellow]")
    res_table.add_row("Componente Afectado", f"[bold red]{diagnostico.affected_component}[/bold red]")
    res_table.add_row("Acción Sugerida", diagnostico.suggested_action)
    res_table.add_row("Sustentado por Evidencia", f"[bold green]{diagnostico.is_evidence_backed}[/bold green]")
    res_table.add_row("Pasos de Verificación", str(len(traza.steps)))

    console.print(res_table)

    # Mostrar Telemetría
    t = inf_resp.telemetry
    tel_table = Table(title="Telemetría de Inferencia y Rendimiento", border_style="magenta")
    tel_table.add_column("TTFT (Prefill)")
    tel_table.add_column("Velocidad Decodificación")
    tel_table.add_column("Latencia Total")
    tel_table.add_column("Tokens Salida")
    tel_table.add_column("VRAM Pico")

    tel_table.add_row(
        f"{t.time_to_first_token_ms} ms",
        f"{t.decode_tokens_per_second} tok/s",
        f"{t.total_latency_ms} ms",
        str(t.completion_tokens),
        f"{t.vram_peak_gb} GB"
    )
    console.print(tel_table)

    # Guardar artefactos si se especificó directorio
    out_path = Path(output_dir) if output_dir else Path.cwd() / "data" / "runs"
    out_path.mkdir(parents=True, exist_ok=True)

    json_file = out_path / f"{scenario_id}_{model_id}_diagnostico.json"
    md_file = out_path / f"{scenario_id}_{model_id}_diagnostico.md"

    with open(json_file, "w", encoding="utf-8") as f:
        f.write(diagnostico.model_dump_json(indent=2))

    md_content = (
        f"# Diagnóstico de Red L7: {diagnostico.scenario_id}\n\n"
        f"- **Modelo:** {diagnostico.model_id}\n"
        f"- **Causa Raíz:** {diagnostico.root_cause}\n"
        f"- **Componente Afectado:** {diagnostico.affected_component}\n"
        f"- **Acción Sugerida:** {diagnostico.suggested_action}\n"
        f"- **Sustentado por Evidencia:** {diagnostico.is_evidence_backed}\n\n"
        f"## Evidencias Consultadas (Solo Lectura)\n"
    )
    for ev in diagnostico.supporting_evidence:
        md_content += f"- `{ev}`\n"
    md_content += f"\n## Explicación Detallada\n{diagnostico.natural_language_explanation}\n"

    with open(md_file, "w", encoding="utf-8") as f:
        f.write(md_content)

    console.print(f"[bold green]Artefactos generados exitosamente en:[/bold green] {out_path}")


@app.command("run-benchmark")
def run_benchmark_cmd(
    models: str | None = typer.Option(None, "--models", "-m", help="Modelos separados por coma (ej: qwen3-8b,phi-4-mini-instruct)"),
    scenarios: str | None = typer.Option(None, "--scenarios", "-s", help="Escenarios separados por coma"),
    seeds: str | None = typer.Option(None, "--seeds", help="Semillas separadas por coma (ej: 42,1337)"),
    repetitions: int = typer.Option(1, "--repetitions", "-r", help="Repeticiones por combinación"),
    output_csv: str = typer.Option("resultados.csv", "--output-csv", "-o", help="Nombre del archivo CSV de salida"),
    resume: bool = typer.Option(True, "--resume/--no-resume", help="Reanudar corridas previas si existen"),
    quick: bool = typer.Option(False, "--quick", "-q", help="Modo rápido de verificación (1 repetición, 1 semilla)"),
    simulate: bool = typer.Option(True, "--simulate/--live", help="Modo simulación determinista o inferencia en vivo con Ollama"),
    replace: bool = typer.Option(False, "--replace", help="Reemplazar filas existentes en el CSV en lugar de omitirlas preservando el resto del archivo"),
    solo_emulados: bool = typer.Option(False, "--solo-emulados", help="Ejecuta únicamente DNS-SRV-01, HTTP-502-01 y TLS-EXP-01 x 3 modelos x 3 semillas reemplazando las 27 filas en resultados.csv")
):
    """Ejecuta la batería automatizada de evaluación del benchmark (OE4)."""
    from src.layer7_evaluator.harness import BenchmarkEvaluatorHarness

    mod_list = [m.strip() for m in models.split(",")] if models else None
    sc_list = [s.strip() for s in scenarios.split(",")] if scenarios else None
    seed_list = [int(s.strip()) for s in seeds.split(",")] if seeds else None

    if solo_emulados:
        sc_list = ["DNS-SRV-01", "HTTP-502-01", "TLS-EXP-01"]
        if not mod_list:
            mod_list = ["qwen3-8b", "phi-4-mini-instruct", "glm-4-9b-chat"]
        if not seed_list:
            seed_list = [42, 1337, 2026]
        replace = True
        resume = False

    if quick:
        repetitions = 1
        if not seed_list:
            seed_list = [42]

    console.print("[bold cyan]=== Iniciando Benchmark NetDiagBench-L7 ===[/bold cyan]")
    harness = BenchmarkEvaluatorHarness()
    if simulate:
        harness.inference_engine.force_simulation = True

    results = harness.run_benchmark(
        model_ids=mod_list,
        scenario_ids=sc_list,
        seeds=seed_list,
        repetitions=repetitions,
        output_csv_filename=output_csv,
        resume=resume,
        replace_existing=replace
    )

    console.print(f"[bold green]Benchmark finalizado con {len(results)} corridas.[/bold green]")
    rep_file_name = "resultados_resumen.md" if output_csv == "resultados.csv" else f"resumen_{output_csv.replace('.csv', '')}.md"
    report_file = harness.output_dir / rep_file_name
    if report_file.exists():
        console.print(Panel(report_file.read_text(encoding="utf-8")[:1500] + "\n...", title="Resumen Ejecutivo (OE4)"))
    corr_file_name = "analisis_correlacional.md" if output_csv == "resultados.csv" else f"correlacion_{output_csv.replace('.csv', '')}.md"
    corr_file = harness.output_dir / corr_file_name
    if corr_file.exists():
        console.print(Panel(corr_file.read_text(encoding="utf-8")[:1200] + "\n...", title="Analisis Correlacional (Tarea 4.1.2)"))


@app.command("analyze-correlation")
def analyze_correlation_cmd(
    csv_file: str | None = typer.Option(None, "--csv", "-c", help="Ruta al CSV de resultados (por defecto: data/benchmark_results/resultados.csv)"),
    output_file: str | None = typer.Option(None, "--output", "-o", help="Ruta de salida del informe Markdown"),
):
    """Ejecuta el analisis correlacional de Spearman/Pearson sobre el dataset de benchmark (Tarea 4.1.2)."""
    from src.layer7_evaluator.statistical_analysis import (
        generate_correlation_report,
        load_benchmark_csv,
        run_correlation_analysis,
    )

    csv_path = Path(csv_file) if csv_file else None
    out_path = Path(output_file) if output_file else None

    console.print("[bold cyan]=== Analisis Correlacional y de Significancia (Tarea 4.1.2) ===[/bold cyan]")

    rows = load_benchmark_csv(csv_path)
    console.print(f"  Datos cargados: {len(rows)} corridas")

    analysis = run_correlation_analysis(rows=rows)

    _report = generate_correlation_report(analysis=analysis, output_path=out_path)

    # Mostrar resumen de correlaciones
    table = Table(title="Correlaciones: Parametros del Modelo vs Metricas", border_style="magenta")
    table.add_column("Metrica", style="bold cyan")
    table.add_column("Spearman rho", style="yellow")
    table.add_column("p-value", style="dim")
    table.add_column("Pearson r", style="green")
    table.add_column("p-value", style="dim")
    table.add_column("Significativo", style="bold red")

    for mk, corr in analysis["correlations"].items():
        sig = "[green]Si[/green]" if corr["significant_005"] else "[dim]No[/dim]"
        table.add_row(mk, str(corr["spearman_rho"]), str(corr["spearman_p"]),
                      str(corr["pearson_r"]), str(corr["pearson_p"]), sig)
    console.print(table)

    # Kruskal-Wallis
    kw_table = Table(title="Kruskal-Wallis: Diferencias entre Modelos", border_style="blue")
    kw_table.add_column("Metrica", style="bold cyan")
    kw_table.add_column("H Estadistico", style="yellow")
    kw_table.add_column("p-value", style="dim")
    kw_table.add_column("Significativo", style="bold red")

    for mk, kw in analysis["kruskal_wallis"].items():
        sig = "[green]Si[/green]" if kw["significant_005"] else "[dim]No[/dim]"
        kw_table.add_row(mk, str(kw["H_statistic"]), str(kw["p_value"]), sig)
    console.print(kw_table)

    console.print("[bold green]Informe completo generado exitosamente.[/bold green]")


@app.command("doctor")
def doctor_cmd():
    """Diagnóstico integral del entorno (hardware, Ollama, dependencias y modos operativos)."""
    import psutil

    from src.core.config import SystemConfig
    from src.layer4_inference.engine import LocalInferenceEngine

    cfg = SystemConfig()
    engine = LocalInferenceEngine(config=cfg)
    health = engine.check_health()

    table = Table(title="NetDiagBench-L7: Diagnóstico de Entorno (Doctor)", border_style="cyan")
    table.add_column("Componente / Verificación", style="bold")
    table.add_column("Estado", style="bold")
    table.add_column("Detalle")

    # CPU y RAM
    cpu_cores = psutil.cpu_count(logical=True)
    ram_gb = round(psutil.virtual_memory().total / (1024**3), 1)
    ram_ok = "[green][OK][/green]" if ram_gb >= 8.0 else "[yellow][!][/yellow]"
    table.add_row("Hardware Sistema", ram_ok, f"CPU: {cpu_cores} cores | RAM: {ram_gb} GB (Mínimo: 8 GB)")

    # Presupuesto VRAM
    vram_lim = cfg.hardware.vram_gb
    table.add_row("Presupuesto VRAM", "[green][OK][/green]", f"{vram_lim} GB configurados (Patrón de referencia)")

    # Motor Ollama
    if health["ollama_online"]:
        ollama_status = f"[green][ONLINE][/green] ({health['ping_latency_ms']} ms)"
        models_str = ", ".join(health["installed_models"]) if health["installed_models"] else "Ninguno descargado"
        table.add_row("Servidor Ollama", "[green][OK][/green]", f"{ollama_status} en {health['ollama_base_url']} | Modelos: {models_str}")
    else:
        table.add_row("Servidor Ollama", "[dim][OFFLINE][/dim]", f"No detectado en {health['ollama_base_url']} (Operando con simulador)")

    # Simulador determinista
    sim_ok = "[green][OK][/green]" if health["simulator_ready"] else "[red][ERROR][/red]"
    table.add_row("Simulador Determinista", sim_ok, "Listo (Fallback de 18 escenarios y 3 modelos calibrados)")

    # Base documental RAG
    from src.layer3_rag.retriever import RAGKnowledgeEngine
    try:
        rag = RAGKnowledgeEngine()
        mem_mb = rag.get_memory_footprint_mb()
        table.add_row("Base RAG Normativa", "[green][OK][/green]", f"{len(rag._chunks)} fragmentos indexados (RAM: {mem_mb} MB <= 450 MB)")
    except Exception as e:
        table.add_row("Base RAG Normativa", "[red][ERROR][/red]", f"Fallo al cargar: {e}")

    # Catálogo de escenarios
    from src.layer1_lab.runner import ScenarioLabRunner
    try:
        runner = ScenarioLabRunner()
        scs = runner.list_scenarios()
        table.add_row("Catálogo Escenarios", "[green][OK][/green]", f"{len(scs)} escenarios L7 válidos")
    except Exception as e:
        table.add_row("Catálogo Escenarios", "[red][ERROR][/red]", f"Fallo: {e}")

    console.print(table)


@app.command("validate-catalog")
def validate_catalog_cmd():
    """Valida la integridad de los 18 escenarios YAML contra contratos Pydantic y reglas técnicas."""
    from src.core.contracts import EscenarioLabContract
    from src.layer1_lab.runner import ScenarioLabRunner

    runner = ScenarioLabRunner()
    scenarios = runner.list_scenarios()

    table = Table(title=f"Validación de Integridad del Catálogo ({len(scenarios)} Escenarios)", border_style="green")
    table.add_column("Escenario ID", style="bold cyan")
    table.add_column("Categoría", style="magenta")
    table.add_column("Clase de Falla", style="yellow")
    table.add_column("Ground Truth", style="cyan")
    table.add_column("Herramienta Read-Only", style="dim")
    table.add_column("Estado Contrato", style="bold green")

    all_valid = True
    for s in scenarios:
        gt = s.ground_truth
        has_evidence = bool(gt.minimum_required_evidence)
        has_rc = bool(gt.root_cause)
        has_comp = bool(gt.affected_component)

        valid = has_evidence and has_rc and has_comp and isinstance(s, EscenarioLabContract)
        if not valid:
            all_valid = False

        ev_str = ", ".join(gt.minimum_required_evidence) if gt.minimum_required_evidence else "-"
        table.add_row(
            s.scenario_id,
            s.category.value,
            s.fault_class.value,
            f"Componente: {gt.affected_component}",
            ev_str[:35] + "..." if len(ev_str) > 35 else ev_str,
            "[green]VÁLIDO[/green]" if valid else "[red]INVÁLIDO[/red]"
        )

    console.print(table)
    if all_valid:
        console.print(f"[bold green]Catálogo 100% íntegro: {len(scenarios)}/{len(scenarios)} escenarios cumplen estrictamente con los contratos.[/bold green]")
    else:
        console.print("[bold red]Se encontraron inconsistencias en el catálogo de escenarios.[/bold red]")


@app.command("export-report")
def export_report_cmd(
    csv_file: str | None = typer.Option(None, "--csv", "-c", help="Ruta al archivo CSV de resultados"),
    output_html: str | None = typer.Option(None, "--output", "-o", help="Ruta de destino del archivo HTML"),
    open_browser: bool = typer.Option(False, "--open", help="Abrir automáticamente el reporte en el navegador predeterminado")
):
    """Compila y exporta el informe técnico consolidado en HTML con gráficos interactivos y SciPy."""
    import webbrowser

    from src.layer7_evaluator.report_generator import generate_html_benchmark_report

    csv_p = Path(csv_file) if csv_file else None
    out_p = Path(output_html) if output_html else None

    console.print("[bold cyan]Compilando informe técnico consolidado en formato HTML...[/bold cyan]")
    generated_path = generate_html_benchmark_report(csv_path=csv_p, output_path=out_p)
    console.print(f"[bold green]Informe HTML generado exitosamente en:[/bold green] {generated_path.resolve()}")

    if open_browser:
        webbrowser.open(generated_path.resolve().as_uri())


@app.command("export-excel")
def export_excel_cmd(
    csv_file: str | None = typer.Option(None, "--csv", "-c", help="Ruta al archivo CSV de resultados"),
    output_xlsx: str | None = typer.Option(None, "--output", "-o", help="Ruta de destino del archivo Excel (.xlsx)"),
):
    """Exporta el dataset completo y los análisis estadísticos a un libro Excel (.xlsx) multioja formateado."""
    from src.layer7_evaluator.excel_exporter import export_benchmark_to_excel

    csv_p = Path(csv_file) if csv_file else None
    out_p = Path(output_xlsx) if output_xlsx else None

    console.print("[bold cyan]Exportando datos y análisis de benchmark a libro Excel (.xlsx)...[/bold cyan]")
    generated_path = export_benchmark_to_excel(output_path=out_p, csv_path=csv_p)
    console.print(f"[bold green]Libro Excel generado exitosamente en:[/bold green] {generated_path.resolve()}")


@app.command("export-pdf")
def export_pdf_cmd(
    report_type: str = typer.Option("all", "--type", "-t", help="Tipo de reporte: 'all', 'comparative' o 'correlation'"),
    output_pdf: str | None = typer.Option(None, "--output", "-o", help="Ruta de destino del archivo PDF"),
    open_browser: bool = typer.Option(False, "--open", help="Abrir automáticamente el reporte PDF generado"),
):
    """Exporta los reportes técnicos en formato PDF con maquetación académica (ReportLab)."""
    import webbrowser

    from src.layer7_evaluator.pdf_exporter import (
        export_comparative_report_pdf,
        export_consolidated_report_pdf,
        export_correlation_report_pdf,
    )

    out_p = Path(output_pdf) if output_pdf else None
    console.print(f"[bold cyan]Compilando informe técnico a PDF (modo: {report_type})...[/bold cyan]")

    if report_type == "comparative":
        generated_path = export_comparative_report_pdf(output_path=out_p)
    elif report_type == "correlation":
        generated_path = export_correlation_report_pdf(output_path=out_p)
    else:
        generated_path = export_consolidated_report_pdf(output_path=out_p)

    console.print(f"[bold green]Reporte PDF generado exitosamente en:[/bold green] {generated_path.resolve()}")

    if open_browser:
        webbrowser.open(generated_path.resolve().as_uri())


@app.command("serve-dashboard")
def serve_dashboard(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host de enlace"),

    port: int = typer.Option(8000, "--port", "-p", help="Puerto HTTP")
):
    """Inicia el dashboard web interactivo para sustentación y pruebas visuales."""
    import uvicorn

    from src.layer6_interface.web import app as fastapi_app
    console.print(f"[bold green]Iniciando Dashboard Web en http://{host}:{port}...[/bold green]")
    uvicorn.run(fastapi_app, host=host, port=port)


if __name__ == "__main__":
    app()

