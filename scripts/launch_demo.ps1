# ============================================================================
# NetDiagBench-L7: Lanzador Rápido PowerShell para Demostración y Sustentación
# Universidad de Pamplona - Facultad de Ingenierías y Arquitectura
# Autor: Juan David León Arrieta
# ============================================================================

$Host.UI.RawUI.WindowTitle = "NetDiagBench-L7 - Demostración en Vivo"

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "   Iniciando NetDiagBench-L7 Dashboard (Universidad de Pamplona)" -ForegroundColor White
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

$pythonExe = Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"

if (-not (Test-Path $pythonExe)) {
    Write-Host "[ERROR] No se detectó el entorno virtual .venv." -ForegroundColor Red
    Write-Host "Por favor ejecute: python -m venv .venv && pip install -e ." -ForegroundColor Yellow
    exit 1
}

Write-Host "[1/3] Ejecutando diagnóstico de pre-vuelo (Doctor)..." -ForegroundColor Green
& $pythonExe -m src.layer6_interface.cli doctor

Write-Host ""
Write-Host "[2/3] Abriendo navegador predeterminado en http://localhost:8000..." -ForegroundColor Green
Start-Process "http://localhost:8000"

Write-Host ""
Write-Host "[3/3] Iniciando servidor web interactivo FastAPI (Presione Ctrl+C para detener)..." -ForegroundColor Green
& $pythonExe -m src.layer6_interface.cli serve-dashboard --host 127.0.0.1 --port 8000
