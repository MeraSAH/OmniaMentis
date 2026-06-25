@echo off
:: ==========================================
:: UBICACIÓN: OmniaMentis/instalar_flask.bat
:: PROPÓSITO: Instalar Flask como alternativa a FastAPI
::            Flask no requiere compilación (sin pydantic-core)
:: FECHA: 2026-06-14
:: USO: Ejecutar desde C:\Users\Usuario\OmniaMentis
:: ==========================================

echo.
echo ================================================
echo   OMNIA MENTIS - Instalando Flask API
echo ================================================
echo.

cd /d C:\Users\Usuario\OmniaMentis

call .venv\Scripts\activate.bat
echo [OK] venv activado

echo.
echo [1/3] Instalando Flask y dependencias (sin compilacion)...
pip install flask flask-cors
if errorlevel 1 (
    echo [ERROR] pip install flask fallo
    pause & exit /b 1
)
echo [OK] Flask instalado

echo.
echo [2/3] Verificando...
python -c "import flask; print('[OK] Flask', flask.__version__)"
python -c "import flask_cors; print('[OK] Flask-CORS ok')"

echo.
echo [3/3] Verificando que uvicorn ya esta instalado...
python -c "import uvicorn; print('[OK] Uvicorn', uvicorn.__version__)"

echo.
echo ================================================
echo   Flask instalado correctamente
echo   Ejecuta: iniciar_flask.bat
echo ================================================
pause