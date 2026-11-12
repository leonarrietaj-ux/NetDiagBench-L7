@echo off
echo ========================================================
echo NetDiagBench-L7: Inicializando entorno virtual Python
echo ========================================================

python -m venv .venv
if %errorlevel% neq 0 (
    echo [ERROR] No se pudo crear el entorno virtual. Verifica la instalacion de Python.
    exit /b %errorlevel%
)

call .venv\Scripts\activate.bat
echo [INFO] Actualizando pip...
python -m pip install --upgrade pip

echo [INFO] Instalando dependencias de NetDiagBench-L7...
pip install -r requirements.txt

echo ========================================================
echo [OK] Entorno configurado correctamente en .venv
echo Ejecuta '.venv\Scripts\activate.bat' para activarlo.
echo ========================================================
