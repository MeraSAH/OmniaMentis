@echo off
:: UBICACIÓN: OmniaMentis/construir_exe.bat
:: PROPÓSITO: Crea OmniaMentis.exe (lanzador de escritorio) en esta misma carpeta. Doble clic.
:: El .exe es SOLO el lanzador: usa el Python y las librerías de tu .venv, así que no pesa cientos de MB
:: y sigue usando tu código al día. Debe quedarse dentro de la carpeta de OmniaMentis.
cd /d "%~dp0"
if exist ".venv\Scripts\activate.bat" call ".venv\Scripts\activate.bat"
python -m pip install --quiet --upgrade pyinstaller
if errorlevel 1 ( echo [ERROR] No se pudo instalar PyInstaller & pause & exit /b 1 )
python -m PyInstaller --noconfirm --onefile --noconsole --name OmniaMentis --icon assets\omnia.ico scripts\omnia_desktop.py
if errorlevel 1 ( echo [ERROR] Fallo la construccion & pause & exit /b 1 )
copy /y dist\OmniaMentis.exe OmniaMentis.exe >nul
rmdir /s /q build 2>nul
del /q OmniaMentis.spec 2>nul
echo.
echo [OK] Creado OmniaMentis.exe en %CD%
echo      Doble clic para abrir OmniaMentis. Puedes crear un acceso directo en el escritorio.
pause
