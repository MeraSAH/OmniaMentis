
@echo off
:: ==========================================
:: UBICACIÓN: OmniaMentis/recrear_venv.bat
:: PROPÓSITO: Detectar Python correcto del sistema y recrear venv
::            El venv actual usa Python de Inkscape (GNU) que no puede compilar
:: FECHA: 2026-06-14
:: USO: Ejecutar desde C:\Users\Usuario\OmniaMentis
::      SIN activar ningún venv primero
:: ==========================================

echo.
echo ================================================
echo   OMNIA MENTIS - Recrear venv con Python correcto
echo ================================================
echo.

cd /d C:\Users\Usuario\OmniaMentis

:: Detectar Python del sistema (no de Inkscape)
echo [1/5] Buscando Python correcto del sistema...
echo.

:: Buscar en ubicaciones estándar de Python para Windows
set PYTHON_OK=

:: Probar py launcher primero (instalador oficial de Python)
py -3.12 --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON_OK=py -3.12
    echo [OK] Encontrado: py launcher -3.12
    py -3.12 -c "import sys; print('   Ejecutable:', sys.executable)"
    goto :found
)

py -3.11 --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON_OK=py -3.11
    echo [OK] Encontrado: py launcher -3.11
    py -3.11 -c "import sys; print('   Ejecutable:', sys.executable)"
    goto :found
)

py -3 --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON_OK=py -3
    echo [OK] Encontrado: py launcher
    py -3 -c "import sys; print('   Ejecutable:', sys.executable)"
    goto :found
)

:: Buscar en rutas estándar de instalación de Python
for %%P in (
    "C:\Python312\python.exe"
    "C:\Python311\python.exe"
    "C:\Python310\python.exe"
    "C:\Users\Usuario\AppData\Local\Programs\Python\Python312\python.exe"
    "C:\Users\Usuario\AppData\Local\Programs\Python\Python311\python.exe"
    "C:\Users\Usuario\AppData\Local\Programs\Python\Python310\python.exe"
) do (
    if exist %%P (
        set PYTHON_OK=%%P
        echo [OK] Encontrado: %%P
        goto :found
    )
)

echo [ERROR] No se encontro Python de Microsoft instalado
echo.
echo SOLUCION: Descarga Python oficial desde:
echo   https://www.python.org/downloads/
echo   - Descarga Python 3.11 o 3.12
echo   - Durante instalacion marca: "Add Python to PATH"
echo   - Reinicia este bat despues de instalar
echo.
pause
exit /b 1

:found
echo.
echo [2/5] Eliminando venv anterior (basado en Python de Inkscape)...
if exist .venv (
    rmdir /s /q .venv
    echo [OK] venv anterior eliminado
) else (
    echo [OK] No habia venv anterior
)

echo.
echo [3/5] Creando nuevo venv con Python correcto...
%PYTHON_OK% -m venv .venv
if errorlevel 1 (
    echo [ERROR] No se pudo crear venv
    pause & exit /b 1
)
echo [OK] Nuevo venv creado

echo.
echo [4/5] Activando nuevo venv e instalando dependencias...
call .venv\Scripts\activate.bat

:: Verificar que es el Python correcto (no Inkscape)
python -c "import sys; print('Python:', sys.executable)"

python -m pip install --upgrade pip --quiet

echo Instalando Flask (wheels puros, sin compilacion C)...
pip install --only-binary=:all: flask flask-cors
if errorlevel 1 (
    echo Intentando sin restriccion binaria...
    pip install flask flask-cors
)

pip install --only-binary=:all: pytest pytest-cov pytest-asyncio httpx
pip install --only-binary=:all: python-dateutil requests uvicorn

echo.
echo [5/5] Verificando instalacion...
python -c "import flask; print('[OK] Flask', flask.__version__)"
if errorlevel 1 (
    echo [FAIL] Flask no instalado
    goto :error
)

python -c "import uvicorn; print('[OK] Uvicorn', uvicorn.__version__)"
python -c "import pytest; print('[OK] Pytest', pytest.__version__)"

echo.
echo ================================================
echo   VENV RECREADO CORRECTAMENTE
echo   Ejecuta: iniciar_flask.bat
echo ================================================
pause
exit /b 0

:error
echo.
echo [ERROR] La instalacion fallo incluso con el Python correcto
echo Ejecuta manualmente:
echo   python -c "import sys; print(sys.executable)"
echo Y verifica que NO diga C:\Program Files\Inkscape\
pause
exit /b 1
ENDOFFILE
echo "recrear_venv.bat creado"