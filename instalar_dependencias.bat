@echo off
:: ==========================================
:: UBICACIÓN: OmniaMentis/instalar_dependencias.bat
:: PROPÓSITO: Instalar todas las dependencias sin compilar desde source
:: FECHA: 2026-06-14
:: USO: Doble click o ejecutar desde cmd en la raíz del proyecto
:: ==========================================

echo.
echo ================================================
echo   OMNIA MENTIS - INSTALADOR DE DEPENDENCIAS
echo ================================================
echo.

:: Verificar que estamos en el directorio correcto
if not exist "src\api\main_web.py" (
    echo [ERROR] Ejecutar desde la raiz de OmniaMentis
    echo         cd C:\Users\Usuario\OmniaMentis
    pause
    exit /b 1
)

:: Activar venv
call .venv\Scripts\activate.bat
echo [OK] Virtual environment activado

echo.
echo [1/4] Actualizando pip...
python -m pip install --upgrade pip --quiet

echo.
echo [2/4] Instalando FastAPI y Uvicorn (wheels pre-compilados)...
pip install --only-binary=:all: "fastapi==0.115.12" "uvicorn==0.34.2" "pydantic==2.11.5"
if errorlevel 1 (
    echo [WARN] Intentando version alternativa...
    pip install --only-binary=:all: "fastapi==0.110.3" "uvicorn==0.29.0" "pydantic==2.7.4"
)

echo.
echo [3/4] Instalando dependencias de testing...
pip install --only-binary=:all: pytest pytest-cov pytest-asyncio httpx
echo [OK] Testing listo

echo.
echo [4/4] Instalando dependencias opcionales del proyecto...
pip install --only-binary=:all: python-dateutil requests
echo [OK] Dependencias base listas

echo.
echo Verificando instalacion...
python -c "import fastapi; print('[OK] FastAPI', fastapi.__version__)"
python -c "import uvicorn; print('[OK] Uvicorn', uvicorn.__version__)"
python -c "import pydantic; print('[OK] Pydantic', pydantic.__version__)"
python -c "import pytest; print('[OK] Pytest', pytest.__version__)"

echo.
echo ================================================
echo   INSTALACION COMPLETADA
echo ================================================
echo.
echo Proximos pasos:
echo   1. Iniciar API:  cd src\api ^& python main_web.py
echo   2. Abrir docs:   http://localhost:8000/docs
echo   3. Dashboard:    http://localhost:8000
echo.
pause