"""
Pruebas Unitarias para Exportadores de Benchmark: Excel (.xlsx) y Reportes PDF
Capa 7 y Capa 6 (NetDiagBench-L7)
"""

from pathlib import Path

import openpyxl
import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from src.layer6_interface.cli import app as cli_app
from src.layer6_interface.web import app as fastapi_app
from src.layer7_evaluator.excel_exporter import export_benchmark_to_excel
from src.layer7_evaluator.pdf_exporter import (
    export_comparative_report_pdf,
    export_consolidated_report_pdf,
    export_correlation_report_pdf,
    markdown_to_pdf,
)


@pytest.fixture
def client():
    return TestClient(fastapi_app)


@pytest.fixture
def runner():
    return CliRunner()


class TestExcelExporter:
    """Validación del exportador de libro de cálculo OpenPyXL."""

    def test_export_benchmark_to_excel_creates_file(self, tmp_path: Path):
        out_file = tmp_path / "test_benchmark.xlsx"
        result_path = export_benchmark_to_excel(output_path=out_file)

        assert result_path.exists()
        assert result_path.stat().st_size > 15_000

    def test_excel_sheets_structure(self, tmp_path: Path):
        out_file = tmp_path / "test_benchmark.xlsx"
        export_benchmark_to_excel(output_path=out_file)

        wb = openpyxl.load_workbook(out_file)
        expected_sheets = [
            "Resumen Ejecutivo",
            "Matriz Multidimensional (OE4)",
            "Desglose por Escenario",
            "Huella Energética y CO2",
            "Correlaciones (4.1.2)",
            "Kruskal-Wallis (Significancia)",
            "IC 95% Bootstrap",
            "Tamaño del Efecto (Cohen d)",
            "Estadísticos Descriptivos",
            "Dataset Raw (162 Corridas)",
        ]

        for s_name in expected_sheets:
            assert s_name in wb.sheetnames, f"Falta la hoja: {s_name}"
        assert any(s.startswith("Dataset Raw") for s in wb.sheetnames)

    def test_excel_data_integrity(self, tmp_path: Path):
        out_file = tmp_path / "test_benchmark.xlsx"
        export_benchmark_to_excel(output_path=out_file)

        wb = openpyxl.load_workbook(out_file)

        # Hoja Matriz Multidimensional tiene los 3 modelos
        ws_matriz = wb["Matriz Multidimensional (OE4)"]
        models_in_sheet = [ws_matriz.cell(row=r, column=1).value for r in range(4, 7)]
        assert "qwen3-8b" in models_in_sheet
        assert "glm-4-9b-chat" in models_in_sheet
        assert "phi-4-mini-instruct" in models_in_sheet

        # Hoja Desglose por Escenario tiene los 18 escenarios
        ws_esc = wb["Desglose por Escenario"]
        assert ws_esc.max_row == 21  # Título (1) + espacio (2) + cabecera (3) + 18 escenarios (4..21) = 21

        # Hoja Raw tiene 162 filas de datos + 1 cabecera = 163 filas
        raw_sheet = [s for s in wb.sheetnames if s.startswith("Dataset Raw")][0]
        ws_raw = wb[raw_sheet]
        assert ws_raw.max_row == 163
        assert ws_raw.max_column in (41, 42, 67)


class TestPDFExporter:
    """Validación del generador de reportes PDF con ReportLab."""

    def test_markdown_to_pdf_basic(self, tmp_path: Path):
        sample_md = """# Título de Prueba
Texto de introducción con **negrita** y *cursiva*.

## Sección 1
- Elemento 1
- Elemento 2

| Columna A | Columna B |
|---|---|
| Valor 1 | Valor 2 |

> Conclusión importante de prueba.
"""
        out_pdf = tmp_path / "sample.pdf"
        result_path = markdown_to_pdf(
            markdown_text=sample_md,
            output_path=out_pdf,
            document_title="Documento de Prueba",
        )

        assert result_path.exists()
        assert result_path.stat().st_size > 1_000
        # Validar firma PDF
        header_bytes = result_path.read_bytes()[:5]
        assert header_bytes == b"%PDF-"

    def test_export_comparative_report_pdf(self, tmp_path: Path):
        out_pdf = tmp_path / "comp.pdf"
        res = export_comparative_report_pdf(output_path=out_pdf)

        assert res.exists()
        assert res.stat().st_size > 4_000
        assert res.read_bytes()[:5] == b"%PDF-"

    def test_export_correlation_report_pdf(self, tmp_path: Path):
        out_pdf = tmp_path / "corr.pdf"
        res = export_correlation_report_pdf(output_path=out_pdf)

        assert res.exists()
        assert res.stat().st_size > 6_000
        assert res.read_bytes()[:5] == b"%PDF-"

    def test_export_consolidated_report_pdf(self, tmp_path: Path):
        out_pdf = tmp_path / "cons.pdf"
        res = export_consolidated_report_pdf(output_path=out_pdf)

        assert res.exists()
        assert res.stat().st_size > 10_000
        assert res.read_bytes()[:5] == b"%PDF-"


class TestExportEndpoints:
    """Validación de los endpoints HTTP FastAPI de descarga."""

    def test_download_excel_endpoint(self, client: TestClient):
        response = client.get("/api/export/excel")
        assert response.status_code == 200
        assert "spreadsheetml.sheet" in response.headers.get("content-type", "")
        assert len(response.content) > 15_000

    def test_download_pdf_comparative_endpoint(self, client: TestClient):
        response = client.get("/api/export/pdf/comparative")
        assert response.status_code == 200
        assert response.headers.get("content-type") == "application/pdf"
        assert response.content[:5] == b"%PDF-"

    def test_download_pdf_correlation_endpoint(self, client: TestClient):
        response = client.get("/api/export/pdf/correlation")
        assert response.status_code == 200
        assert response.headers.get("content-type") == "application/pdf"
        assert response.content[:5] == b"%PDF-"

    def test_download_pdf_consolidated_endpoint(self, client: TestClient):
        response = client.get("/api/export/pdf/consolidated")
        assert response.status_code == 200
        assert response.headers.get("content-type") == "application/pdf"
        assert response.content[:5] == b"%PDF-"


class TestCLIExportCommands:
    """Validación de los comandos CLI benchapp export-excel y export-pdf."""

    def test_cli_export_excel(self, runner: CliRunner, tmp_path: Path):
        out_file = tmp_path / "cli_test.xlsx"
        result = runner.invoke(cli_app, ["export-excel", "--output", str(out_file)])
        assert result.exit_code == 0
        assert out_file.exists()
        assert out_file.stat().st_size > 15_000

    def test_cli_export_pdf_all(self, runner: CliRunner, tmp_path: Path):
        out_file = tmp_path / "cli_all.pdf"
        result = runner.invoke(cli_app, ["export-pdf", "--type", "all", "--output", str(out_file)])
        assert result.exit_code == 0
        assert out_file.exists()
        assert out_file.stat().st_size > 10_000

    def test_cli_export_pdf_comparative(self, runner: CliRunner, tmp_path: Path):
        out_file = tmp_path / "cli_comp.pdf"
        result = runner.invoke(cli_app, ["export-pdf", "--type", "comparative", "--output", str(out_file)])
        assert result.exit_code == 0
        assert out_file.exists()
        assert out_file.stat().st_size > 4_000

    def test_cli_export_pdf_correlation(self, runner: CliRunner, tmp_path: Path):
        out_file = tmp_path / "cli_corr.pdf"
        result = runner.invoke(cli_app, ["export-pdf", "--type", "correlation", "--output", str(out_file)])
        assert result.exit_code == 0
        assert out_file.exists()
        assert out_file.stat().st_size > 6_000
