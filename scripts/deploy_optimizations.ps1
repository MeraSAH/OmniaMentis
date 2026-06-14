# ==========================================
# OMNIA MENTIS - Deploy Script v1.2.0
# UBICACION: OmniaMentis/scripts/deploy_optimizations_fixed.ps1
# PROPOSITO: Script automatizado para deploy de optimizaciones
# DEPENDENCIAS: PowerShell 5.1+, Python 3.10+
# CREADO: 2025-12-08
# USO: .\scripts\deploy_optimizations_fixed.ps1
# ==========================================

$ErrorActionPreference = "Stop"
$PROJECT_ROOT = $PSScriptRoot | Split-Path -Parent
$TIMESTAMP = Get-Date -Format "yyyyMMdd_HHmmss"
$BACKUP_DIR = Join-Path $PROJECT_ROOT "backups\$TIMESTAMP"

# Colores
$COLOR_SUCCESS = "Green"
$COLOR_ERROR = "Red"
$COLOR_WARNING = "Yellow"
$COLOR_INFO = "Cyan"

# ==================== FUNCIONES ====================
function Write-Step {
    param([string]$Message, [string]$Color = $COLOR_INFO )
    Write-Host "`n$Message" -ForegroundColor $Color
}

function Write-Success {
    param([string]$Message)
    Write-Host "[OK] $Message" -ForegroundColor $COLOR_SUCCESS
}

function Write-Error-Custom {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor $COLOR_ERROR
}

function Write-Warning-Custom {
    param([string]$Message)
    Write-Host "[WARN] $Message" -ForegroundColor $COLOR_WARNING
}

function Test-PythonVersion {
    try {
        $version = python --version 2>&1
        if ($version -match "Python 3\.(1[0-9]|[2-9][0-9])") {
            Write-Success "Python version valida: $version"
            return $true
        }
        else {
            Write-Error-Custom "Python 3.10+ requerido. Version actual: $version"
            return $false
        }
    }
    catch {
        Write-Error-Custom "Python no encontrado en PATH"
        return $false
    }
}

function Test-VirtualEnv {
    $venvPath = Join-Path $PROJECT_ROOT ".venv\Scripts\python.exe"
    if (Test-Path $venvPath) {
        Write-Success "Virtual environment encontrado"
        return $true
    }
    else {
        Write-Warning-Custom "Virtual environment no encontrado"
        return $false
    }
}

function Stop-ExistingServer {
    Write-Step "Deteniendo servidor existente..."
    
    $processes = Get-Process python -ErrorAction SilentlyContinue | 
    Where-Object { $_.Path -like "*OmniaMentis*" }
    
    if ($processes) {
        $processes | Stop-Process -Force
        Write-Success "Servidor anterior detenido"
        Start-Sleep -Seconds 2
    }
    else {
        Write-Success "No hay servidor corriendo"
    }
}

function New-Backup {
    Write-Step "Creando backup de archivos criticos..."
    
    New-Item -ItemType Directory -Path $BACKUP_DIR -Force | Out-Null
    
    $filesToBackup = @(
        "src\api\main_web.py",
        "web\dashboard.html",
        "scripts\test_production_web.py"
    )
    
    foreach ($file in $filesToBackup) {
        $sourcePath = Join-Path $PROJECT_ROOT $file
        if (Test-Path $sourcePath) {
            $fileName = Split-Path $file -Leaf
            $destPath = Join-Path $BACKUP_DIR $fileName
            Copy-Item $sourcePath $destPath -Force
            Write-Success "Backup: $file"
        }
    }
    
    Write-Success "Backup completado en: $BACKUP_DIR"
}

function Test-OptimizedBackend {
    Write-Step "Verificando backend optimizado..."
    
    $backendPath = Join-Path $PROJECT_ROOT "src\api\main_web.py"
    
    if (-not (Test-Path $backendPath)) {
        Write-Error-Custom "Backend no encontrado en: $backendPath"
        return $false
    }
    
    # Verificar que tiene las optimizaciones
    $content = Get-Content $backendPath -Raw
    
    if ($content -match "Performance Optimizado" -or $content -match "@asynccontextmanager") {
        Write-Success "Backend optimizado detectado"
        return $true
    }
    else {
        Write-Warning-Custom "Backend NO optimizado"
        Write-Host "`nINSTRUCCIONES:" -ForegroundColor Yellow
        Write-Host "1. Abre: $backendPath"
        Write-Host "2. Reemplaza TODO el contenido con el codigo del Artifact optimizado"
        Write-Host "3. Guarda y vuelve a ejecutar este script"
        return $false
    }
}

function Test-OptimizedDashboard {
    Write-Step "Verificando dashboard optimizado..."
    
    $dashboardPath = Join-Path $PROJECT_ROOT "web\dashboard.html"
    
    if (-not (Test-Path $dashboardPath)) {
        Write-Error-Custom "Dashboard no encontrado en: $dashboardPath"
        return $false
    }
    
    # Verificar que tiene las correcciones
    $content = Get-Content $dashboardPath -Raw
    
    if ($content -match "http://localhost:8000[^/]" -and $content -notmatch "/docs/api") {
        Write-Success "Dashboard optimizado detectado"
        return $true
    }
    else {
        Write-Warning-Custom "Dashboard NO optimizado"
        Write-Host "`nINSTRUCCIONES:" -ForegroundColor Yellow
        Write-Host "1. Abre: $dashboardPath"
        Write-Host "2. Busca: const API_URL = 'http://localhost:8000/docs';"
        Write-Host "3. Cambia a: const API_URL = 'http://localhost:8000';"
        Write-Host "4. Guarda y vuelve a ejecutar este script"
        return $false
    }
}

function Test-ServerStartup {
    Write-Step "Probando inicio del servidor..."
    
    # Activar virtual environment si existe
    $activateScript = Join-Path $PROJECT_ROOT ".venv\Scripts\Activate.ps1"
    if (Test-Path $activateScript) {
        & $activateScript
    }
    
    # Iniciar servidor en background
    $backendPath = Join-Path $PROJECT_ROOT "src\api\main_web.py"
    $job = Start-Job -ScriptBlock {
        param($path, $root)
        Set-Location $root
        $env:PYTHONPATH = Join-Path $root "src"
        & python $path
    } -ArgumentList $backendPath, $PROJECT_ROOT
    
    Write-Host "Esperando inicio del servidor (15 segundos)..."
    Start-Sleep -Seconds 15
    
    # Verificar health check
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 5
        if ($response.StatusCode -eq 200) {
            Write-Success "Servidor iniciado correctamente"
            $healthData = $response.Content | ConvertFrom-Json
            Write-Host "   Consciencia: $($healthData.consciousness)" -ForegroundColor Cyan
            Write-Host "   API Version: $($healthData.api_version)" -ForegroundColor Cyan
            
            # Detener job
            Stop-Job $job
            Remove-Job $job
            return $true
        }
    }
    catch {
        Write-Error-Custom "Servidor no respondio: $_"
        Stop-Job $job -ErrorAction SilentlyContinue
        Remove-Job $job -ErrorAction SilentlyContinue
        return $false
    }
}

function Show-Summary {
    param([hashtable]$Results)
    
    Write-Host "`n" + ("=" * 70) -ForegroundColor Cyan
    Write-Host "RESUMEN DE DEPLOY" -ForegroundColor Cyan
    Write-Host ("=" * 70) -ForegroundColor Cyan
    
    foreach ($key in $Results.Keys) {
        $status = if ($Results[$key]) { "[OK]" } else { "[FAIL]" }
        $color = if ($Results[$key]) { $COLOR_SUCCESS } else { $COLOR_ERROR }
        Write-Host "   $status $key" -ForegroundColor $color
    }
    
    Write-Host ("=" * 70) -ForegroundColor Cyan
    
    $successCount = ($Results.Values | Where-Object { $_ -eq $true }).Count
    $totalCount = $Results.Count
    $percentage = [math]::Round(($successCount / $totalCount) * 100, 1)
    
    Write-Host "`nRESULTADO: $successCount/$totalCount ($percentage%)" -ForegroundColor Cyan
    
    if ($percentage -eq 100) {
        Write-Host "DEPLOY EXITOSO - Sistema 100% funcional" -ForegroundColor $COLOR_SUCCESS
        Write-Host "`nProximos pasos:" -ForegroundColor Cyan
        Write-Host "  1. Abrir dashboard: http://localhost:8000/dashboard.html"
        Write-Host "  2. Verificar docs API: http://localhost:8000/docs"
        Write-Host "  3. Monitorear logs: Get-Content logs\omnia.log -Wait"
    }
    elseif ($percentage -ge 80) {
        Write-Host "DEPLOY PARCIAL - Revisar errores arriba" -ForegroundColor $COLOR_WARNING
    }
    else {
        Write-Host "DEPLOY FALLIDO - Revisar guia de troubleshooting" -ForegroundColor $COLOR_ERROR
    }
    
    Write-Host "`nBackup disponible en: $BACKUP_DIR" -ForegroundColor Cyan
}

# ==================== SCRIPT PRINCIPAL ====================
function Main {
    Write-Host @"

================================================================
        OMNIA MENTIS - DEPLOY DE OPTIMIZACIONES v1.2.0
================================================================

"@ -ForegroundColor Cyan

    # Navegar a raiz del proyecto
    Set-Location $PROJECT_ROOT
    Write-Host "Proyecto: $PROJECT_ROOT`n" -ForegroundColor Cyan
    
    # Resultados
    $results = @{}
    
    # 1. Verificar Python
    $results["Python 3.10+"] = Test-PythonVersion
    if (-not $results["Python 3.10+"]) {
        Write-Error-Custom "Python 3.10+ es requerido. Abortando."
        return
    }
    
    # 2. Verificar Virtual Environment
    $results["Virtual Environment"] = Test-VirtualEnv
    
    # 3. Detener servidor existente
    Stop-ExistingServer
    $results["Detener Servidor"] = $true
    
    # 4. Crear backup
    try {
        New-Backup
        $results["Backup"] = $true
    }
    catch {
        Write-Error-Custom "Error creando backup: $_"
        $results["Backup"] = $false
    }
    
    # 5. Verificar backend
    $results["Backend Optimizado"] = Test-OptimizedBackend
    if (-not $results["Backend Optimizado"]) {
        Write-Host "`nDeploy pausado. Completa las instrucciones arriba." -ForegroundColor $COLOR_WARNING
        Show-Summary -Results $results
        return
    }
    
    # 6. Verificar dashboard
    $results["Dashboard Optimizado"] = Test-OptimizedDashboard
    if (-not $results["Dashboard Optimizado"]) {
        Write-Host "`nDeploy pausado. Completa las instrucciones arriba." -ForegroundColor $COLOR_WARNING
        Show-Summary -Results $results
        return
    }
    
    # 7. Test servidor
    Write-Host "`nDeseas probar el servidor ahora? (Y/N): " -NoNewline
    $response = Read-Host
    if ($response -eq "Y" -or $response -eq "y") {
        $results["Servidor Funcional"] = Test-ServerStartup
    }
    else {
        Write-Warning-Custom "Saltando pruebas del servidor"
        $results["Servidor Funcional"] = $null
    }
    
    # 8. Resumen final
    Show-Summary -Results $results
    
    # 9. Mensaje final
    Write-Host "`nDocumentacion completa en: GUIA_IMPLEMENTACION_OPTIMIZACION.md" -ForegroundColor Cyan
    Write-Host "Troubleshooting: Ver seccion en la guia`n" -ForegroundColor Cyan
}

# ==================== EJECUCION ====================
try {
    Main
}
catch {
    Write-Error-Custom "Error critico durante el deploy: $_"
    Write-Host "`nStack trace:" -ForegroundColor Red
    Write-Host $_.ScriptStackTrace -ForegroundColor Red
    exit 1
}