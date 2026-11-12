@echo off
REM ============================================================================
REM NetDiagBench-L7: Lanzador Rápido para Demostración y Sustentación de Tesis
REM Universidad de Pamplona - Facultad de Ingenierías y Arquitectura
REM Autor: Juan David León Arrieta
REM ============================================================================

title NetDiagBench-L7 - Demostración en Vivo
echo ============================================================================
echo   Iniciando NetDiagBench-L7 Dashboard (Universidad de Pamplona)
echo ============================================================================
echo.

IF NOT EXIST ".venv\Scripts\python.exe" (
    echo [ERROR] No se detecto el entorno virtual .venv.
    echo Por favor ejecute: python -m venv .venv ^&^& pip install -e .
    pause
    exit /b 1
)

echo [1/3] Ejecutando diagnostico de pre-vuelo (Doctor)...
.venv\Scripts\python.exe -m src.layer6_interface.cli doctor

echo.
echo [2/3] Abriendo navegador predeterminado en http://localhost:8000...
start http://localhost:8000

echo.
echo [3/3] Iniciando servidor web interactivo FastAPI (Presione Ctrl+C para detener)...
.venv\Scripts\python.exe -m src.layer6_interface.cli serve-dashboard --host 127.0.0.1 --port 8000
