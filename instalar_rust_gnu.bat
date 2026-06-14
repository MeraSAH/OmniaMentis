@echo off
:: ==========================================
:: UBICACIÓN: OmniaMentis/instalar_rust_gnu.bat
:: PROPÓSITO: Instalar Rust con toolchain GNU (sin Visual Studio)
::            y luego instalar FastAPI + pydantic-core
:: FECHA: 2026-06-14
:: USO: Ejecutar desde C:\Users\Usuario\OmniaMentis
::      DESPUÉS de elegir opción 3 en rustup-init.exe
:: ==========================================

echo.
echo ================================================
echo   OMNIA MENTIS - Configurar Rust GNU + FastAPI
echo ================================================
echo.

:: Verificar que rustup existe
where rustup >nul 2>&1
if errorlevel 1 (
    echo [ERROR] rustup no encontrado en PATH
    echo         Reinicia el cmd y vuelve a ejecutar este bat
    pause
    exit /b 1
)

echo [1/4] Instalando toolchain GNU para Windows...
rustup toolchain install stable-x86_64-pc-windows-gnu
rustup default stable-x86_64-pc-windows-gnu

echo.
echo [2/4] Verificando Rust...
rustc --version
cargo --version
echo [OK] Rust listo

echo.
echo [3/4] Activando venv e instalando pydantic-core + FastAPI...

if not exist ".venv\Scripts\activate.bat" (
    echo [ERROR] Ejecutar desde C:\Users\Usuario\OmniaMentis
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat
echo [OK] venv activado

python -m pip install --upgrade pip --quiet

pip install pydantic-core --no-binary pydantic-core
if errorlevel 1 (
    echo [WARN] Intentando con prefer-binary...
    pip install pydantic-core --prefer-binary
)

pip install "pydantic==2.7.4"
pip install "fastapi==0.110.3"
pip install "uvicorn==0.29.0"

echo.
echo [4/4] Verificando instalacion...
python -c "import pydantic; print('[OK] Pydantic', pydantic.__version__)"
python -c "import fastapi; print('[OK] FastAPI', fastapi.__version__)"
python -c "import uvicorn; print('[OK] Uvicorn', uvicorn.__version__)"

echo.
echo ================================================
echo   LISTO - Ejecuta: iniciar_api.bat
echo ================================================
pause