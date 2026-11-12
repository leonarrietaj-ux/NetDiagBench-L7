"""
NetDiagBench-L7: Layer 7 - Benchmark Evaluation & Metrics
"""
from src.layer7_evaluator.metrics import (
    calculate_token_similarity,
    check_component_correct,
    check_root_cause_correct,
    classify_model,
    estimate_energy_and_carbon,
    evaluate_explanation_rubric,
    get_evaluator_version,
    load_evaluator_concepts,
)

__all__ = [
    "BenchmarkEvaluatorHarness",
    # Metrics & Official Concepts
    "calculate_token_similarity",
    "check_component_correct",
    "check_root_cause_correct",
    "classify_model",
    "estimate_energy_and_carbon",
    "evaluate_explanation_rubric",
    "get_evaluator_version",
    "load_evaluator_concepts",
    # Statistical Analysis (Lazy loaded)
    "bootstrap_ci",
    "build_comparative_summary",
    "descriptive_stats",
    "effect_size_cohens_d",
    "generate_correlation_report",
    "interpret_effect_size",
    "kruskal_wallis_test",
    "load_benchmark_csv",
    "pearson_correlation",
    "run_correlation_analysis",
    "spearman_correlation",
    # Reporting & Exporters (Lazy loaded)
    "generate_html_benchmark_report",
    "export_benchmark_to_excel",
    "export_comparative_report_pdf",
    "export_correlation_report_pdf",
    "export_consolidated_report_pdf",
    "markdown_to_pdf",
]


def __getattr__(name: str):
    if name == "BenchmarkEvaluatorHarness":
        from src.layer7_evaluator.harness import BenchmarkEvaluatorHarness
        return BenchmarkEvaluatorHarness

    # Lazy import para submodulos de análisis estadístico
    stat_exports = {
        "bootstrap_ci", "build_comparative_summary", "descriptive_stats",
        "effect_size_cohens_d", "generate_correlation_report", "interpret_effect_size",
        "kruskal_wallis_test", "load_benchmark_csv", "pearson_correlation",
        "run_correlation_analysis", "spearman_correlation"
    }
    if name in stat_exports:
        import src.layer7_evaluator.statistical_analysis as sa
        return getattr(sa, name)

    # Lazy import para reportes y exportadores
    rep_exports = {
        "generate_html_benchmark_report", "export_benchmark_to_excel",
        "export_comparative_report_pdf", "export_correlation_report_pdf",
        "export_consolidated_report_pdf", "markdown_to_pdf"
    }
    if name in rep_exports:
        import src.layer7_evaluator.report_generator as rg
        if hasattr(rg, name):
            return getattr(rg, name)
        import src.layer7_evaluator.excel_exporter as ee
        if hasattr(ee, name):
            return getattr(ee, name)
        import src.layer7_evaluator.pdf_exporter as pe
        if hasattr(pe, name):
            return getattr(pe, name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
