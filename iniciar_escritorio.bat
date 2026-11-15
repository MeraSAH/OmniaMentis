@echo off
:: UBICACIÓN: OmniaMentis/iniciar_escritorio.bat
:: PROPÓSITO: Abrir OmniaMentis como aplicación de escritorio (Windows). Doble clic.
cd /d "%~dp0"
if exist ".venv\Scripts\activate.bat" call ".venv\Scripts\activate.bat"
python scripts\omnia_desktop.py %*
if errorlevel 1 pause
