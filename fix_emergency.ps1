# ==========================================
# COMANDOS DE EMERGENCIA - OMNIA MENTIS
# Ejecutar directamente en PowerShell
# ==========================================

Write-Host @"

========================================
  OMNIA MENTIS - COMANDOS EMERGENCIA
========================================

"@ -ForegroundColor Cyan

# Navegar al proyecto
Set-Location C:\Users\Usuario\OmniaMentis

Write-Host "[1/5] Activando virtual environment..." -ForegroundColor Yellow
& .\.venv\Scripts\Activate.ps1

Write-Host "[2/5] Configurando PYTHONPATH..." -ForegroundColor Yellow
$env:PYTHONPATH = "$PWD\src"

Write-Host "[3/5] Verificando archivo main_web.py..." -ForegroundColor Yellow
if (Test-Path "src\api\main_web.py") {
    Write-Host "   [OK] Archivo encontrado" -ForegroundColor Green
    
    # Verificar contenido
    $content = Get-Content "src\api\main_web.py" -Raw
    
    if ($content -match 'uvicorn\.run\(\s*["\']main_web_optimized:app["\']\s*,') {
        Write-Host "   [ERROR] Nombre incorrecto detectado: 'main_web_optimized:app'" -ForegroundColor Red
        Write-Host "   [FIX] Aplicando corrección automática..." -ForegroundColor Yellow
        
        # Backup
        Copy-Item "src\api\main_web.py" "src\api\main_web.py.backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
        
        # Corregir
        $content = $content -replace 'uvicorn\.run\(\s*["\']main_web_optimized:app["\']\s*, ', 'uvicorn.run("main_web:app", '
        Set-Content "src\api\main_web.py" -Value $content
        
        Write-Host "   [OK] Corregido automaticamente" -ForegroundColor Green
    } elseif ($content -match 'uvicorn\.run\(\s*["\']main_web:app["\']\s*,') {
                Write-Host "   [OK] Configuracion correcta" -ForegroundColor Green
            } else {
                Write-Host "   [WARN] No se pudo verificar uvicorn.run()" -ForegroundColor Yellow
            }
        }
        else {
            Write-Host "   [ERROR] Archivo no encontrado: src\api\main_web.py" -ForegroundColor Red
            exit 1
        }

        Write-Host "[4/5] Deteniendo procesos Python existentes..." -ForegroundColor Yellow
        Get-Process python -ErrorAction SilentlyContinue | 
        Where-Object { $_.Path -like "*OmniaMentis*" } | 
        Stop-Process -Force -ErrorAction SilentlyContinue

        Start-Sleep -Seconds 2

        Write-Host "[5/5] Iniciando servidor..." -ForegroundColor Yellow
        Write-Host @"

========================================
  SERVIDOR INICIANDO...
  
  Si ves errores, presiona Ctrl+C y 
  reporta el mensaje exacto
========================================

"@ -ForegroundColor Cyan

        # Iniciar servidor
        python src\api\main_web.py