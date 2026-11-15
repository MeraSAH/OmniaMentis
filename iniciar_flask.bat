@echo off
:: ==========================================
:: UBICACIÓN: OmniaMentis/iniciar_flask.bat
:: PROPÓSITO: Iniciar la API de Omnia Mentis con Flask
:: FECHA: 2026-06-14 (actualizado 2026-10-10)
:: USO: doble clic o ejecutar desde cualquier carpeta; usa la carpeta donde
::      está este archivo (ya no depende de C:\Users\Usuario\OmniaMentis)
:: ==========================================

echo.
echo ================================================
echo   OMNIA MENTIS API Flask - INICIANDO
echo ================================================
echo.

cd /d "%~dp0"

if not exist "src\api\main_flask.py" (
    echo [ERROR] src\api\main_flask.py no encontrado
    echo         Copia el archivo main_flask.py a src\api\
    pause & exit /b 1
)

call .venv\Scripts\activate.bat
echo [OK] venv activado

python -c "import flask" 2>nul
if errorlevel 1 (
    echo [ERROR] Flask no instalado. Ejecuta: instalar_flask.bat
    pause & exit /b 1
)
echo [OK] Flask disponible

set PYTHONPATH=%CD%\src
echo [OK] PYTHONPATH=%PYTHONPATH%
echo.
echo   URL:    http://localhost:8000
echo   Chat:   POST http://localhost:8000/api/chat
echo   Estado: GET  http://localhost:8000/api/consciousness
echo   Health: GET  http://localhost:8000/health
echo.
echo   Ctrl+C para detener
echo.

python src\api\main_flask.py

pause