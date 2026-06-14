@echo off
:: ==========================================
:: UBICACIÓN: OmniaMentis/iniciar_api.bat
:: PROPÓSITO: Iniciar API web de Omnia Mentis
:: FECHA: 2026-06-14 (CORREGIDO)
:: USO: Ejecutar desde C:\Users\Usuario\OmniaMentis
:: ==========================================

echo.
echo ================================================
echo   OMNIA MENTIS API - INICIANDO
echo ================================================
echo.

if not exist "src\api\main_web.py" (
    echo [ERROR] Ejecutar desde la raiz de OmniaMentis
    echo         cd C:\Users\Usuario\OmniaMentis
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat
echo [OK] Virtual environment activado

python -c "import fastapi" 2>nul
if errorlevel 1 (
    echo [ERROR] FastAPI no instalado.
    echo         Ejecuta: python fix_fastapi.py
    pause
    exit /b 1
)
echo [OK] FastAPI disponible

set PYTHONPATH=%CD%\src
echo [OK] PYTHONPATH=%PYTHONPATH%
echo.
echo   URL:  http://localhost:8000
echo   Docs: http://localhost:8000/docs
echo.
echo   Ctrl+C para detener
echo.

python -m uvicorn src.api.main_web:app --host 0.0.0.0 --port 8000 --reload --reload-dir src

pause