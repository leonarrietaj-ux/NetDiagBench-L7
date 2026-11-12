"""
Componente Global Reutilizable de Barra de Exportación para Vistas Standalone de NetDiagBench-L7.
Principio DRY: Centraliza los botones de descarga (Excel, PDF contextual, JSON, Imprimir)
y los inyecta en las vistas independientes eliminando botones innecesarios ('Ocultar Panel' y '↗ Pestaña').
"""
from pathlib import Path

PARTIAL_PATH = Path(__file__).parent / "partials" / "export_toolbar.html"

VIEW_CONFIGS = {
    "comparativo": {
        "title": "Informe Técnico Comparativo Multidimensional (OE4)",
        "pdf_url": "/api/export/comparativo/pdf",
        "pdf_label": "PDF Comparativo (OE4)",
        "back_url": "/?view=comparativo",
    },
    "correlacion": {
        "title": "Análisis Correlacional y Significancia Estadística (SciPy)",
        "pdf_url": "/api/export/correlacional/pdf",
        "pdf_label": "PDF Correlacional (SciPy)",
        "back_url": "/?view=correlacion",
    },
    "consolidado": {
        "title": "Informe Consolidado Global de Benchmarking (HTML)",
        "pdf_url": "/api/export/consolidado/pdf",
        "pdf_label": "PDF Consolidado",
        "back_url": "/?view=consolidado",
    },
    "suite_observabilidad": {
        "title": "Visor de Observabilidad • Suite Completa (18 Escenarios Catalogados)",
        "pdf_url": "/api/export/suite/pdf",
        "pdf_label": "Reporte de la Suite (PDF)",
        "back_url": "/?view=suite_observabilidad",
    },
}


def render_export_toolbar(
    view_key: str = "comparativo",
    models: str | None = None,
    run_id: str | None = None,
) -> str:
    """
    Genera el fragmento HTML del componente de barra de exportación para la vista solicitada.
    Utiliza rutas absolutas para garantizar funcionamiento en cualquier URL del navegador.
    """
    config = VIEW_CONFIGS.get(view_key, VIEW_CONFIGS["comparativo"])
    query_param = ""
    if run_id:
        query_param = f"?run_id={run_id}"
    elif models and models != "ALL":
        query_param = f"?models={models}"

    template = PARTIAL_PATH.read_text(encoding="utf-8")
    return (
        template
        .replace("{{ view_title }}", config["title"])
        .replace("{{ pdf_url }}", config["pdf_url"])
        .replace("{{ pdf_label }}", config["pdf_label"])
        .replace("{{ back_url }}", config["back_url"])
        .replace("{{ query_param }}", query_param)
        .replace("{{ view_key }}", view_key)
    )
