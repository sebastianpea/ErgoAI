<#
.SYNOPSIS
    Script de control interactivo para ErgoAI (Windows PowerShell).
    Menú permanente: se queda abierto hasta que el usuario elige salir.
#>

[CmdletBinding()]
param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173
)

$ErrorActionPreference = "Continue"
$root = Resolve-Path .
$venv = Join-Path $root ".venv"
$python = Join-Path $venv "Scripts\python.exe"
$pip = Join-Path $venv "Scripts\pip.exe"
$backendPidFile = Join-Path $env:TEMP "ergoai-backend.pid"
$frontendPidFile = Join-Path $env:TEMP "ergoai-frontend.pid"
$ollamaPidFile = Join-Path $env:TEMP "ergoai-ollama.pid"

function Log($msg) { Write-Host "[ergoai] $msg" -ForegroundColor Cyan }

function Show-Menu() {
    Clear-Host
    Write-Host "========================================" -ForegroundColor DarkCyan
    Write-Host "      ERGOAI - PANEL DE CONTROL         " -ForegroundColor Yellow
    Write-Host "========================================" -ForegroundColor DarkCyan
    Write-Host ""
    Write-Host "  1. Levantar sistema (backend + frontend)" -ForegroundColor Green
    Write-Host "  2. Bajar sistema (detener todo)"        -ForegroundColor Red
    Write-Host "  3. Reiniciar sistema"                    -ForegroundColor Yellow
    Write-Host "  4. Estado de puertos y servicios"        -ForegroundColor Cyan
    Write-Host "  5. Instalar dependencias"                -ForegroundColor Cyan
    Write-Host "  6. Ejecutar pruebas (pytest)"            -ForegroundColor Cyan
    Write-Host "  7. Build produccion frontend"            -ForegroundColor Cyan
    Write-Host "  8. Limpiar temporales"                   -ForegroundColor Cyan
    Write-Host "  9. Listar modelos Ollama"                -ForegroundColor Cyan
    Write-Host "  0. Salir del script"                     -ForegroundColor Red
    Write-Host ""
    Write-Host "Puertos: Backend=$BackendPort | Frontend=$FrontendPort" -ForegroundColor Gray
    Write-Host ""
}

function Test-PortFree($port) {
    try {
        Get-NetTCPConnection -LocalPort $port -ErrorAction Stop | Out-Null
        return $false
    } catch {
        return $true
    }
}

function Wait-Port($port, $timeoutSeconds = 30) {
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    while ($sw.Elapsed.TotalSeconds -lt $timeoutSeconds) {
        try {
            $req = [System.Net.WebRequest]::Create("http://localhost:$port/salud")
            $resp = $req.GetResponse()
            if ($resp.StatusCode -eq "OK") { $resp.Close(); return $true }
            $resp.Close()
        } catch {}
        Start-Sleep -Milliseconds 500
    }
    return $false
}

function Kill-PidFile($file) {
    if (Test-Path $file) {
        $pid = Get-Content $file -ErrorAction SilentlyContinue
        if ($pid) {
            try { Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue } catch {}
        }
        Remove-Item $file -Force -ErrorAction SilentlyContinue
    }
}

function Ensure-Python() {
    if (-not (Test-Path $python)) {
        Log "Creando entorno virtual Python..."
        python -m venv $venv | Out-Null
    }
    if (-not (Test-Path $python)) {
        throw "No se pudo crear el entorno virtual en $venv"
    }
    Log "Entorno virtual listo: $python"
}

function Ensure-PipDeps() {
    Log "Instalando dependencias de Python..."
    & $pip install --upgrade pip 2>$null | Out-Null
    if (Test-Path "requirements.txt") {
        & $pip install -r requirements.txt 2>$null | Out-Null
    }
    if (Test-Path "backend/requirements-vision.txt") {
        # onnxruntime==1.20.1 no existe en Python 3.14; usar versión disponible
        $content = Get-Content "backend/requirements-vision.txt" -Raw
        $content = $content -replace "onnxruntime==1\.20\.1", "onnxruntime>=1.24.0"
        $tmp = Join-Path $env:TEMP "requirements-vision-fixed.txt"
        $content | Out-File -FilePath $tmp -Encoding utf8
        & $pip install -r $tmp 2>$null | Out-Null
        Remove-Item $tmp -Force -ErrorAction SilentlyContinue
    }
    Log "Dependencias de Python instaladas."
}

function Ensure-Node() {
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
        throw "npm no esta instalado. Instale Node.js desde https://nodejs.org/"
    }
    if (Test-Path "frontend/package.json") {
        Log "Instalando dependencias de Node (frontend)..."
        & cmd /c "npm install --prefix frontend" | Out-Null
        Log "Dependencias de Node instaladas."
    }
}

function Ensure-Ollama() {
    if (Get-Command ollama -ErrorAction SilentlyContinue) {
        Log "Ollama detectado. Verificando modelo qwen2.5..."
        try {
            $models = ollama list | Out-String
            if ($models -notmatch "qwen2.5") {
                Log "Descargando modelo qwen2.5 (puede tardar)..."
                ollama pull qwen2.5 | Out-Null
            }
        } catch {
            Log "No se pudo consultar Ollama. Asegurate de que 'ollama serve' este corriendo."
        }
    } else {
        Log "Ollama no esta instalado. El agente IA usara fallback o fallara hasta que lo instale."
    }
}

function Start-OllamaService() {
    if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) { return }
    try {
        $status = ollama list 2>$null
        if ($LASTEXITCODE -ne 0) {
            Log "Iniciando ollama serve..."
            Start-Process ollama -ArgumentList "serve" -WindowStyle Hidden -PassThru | Select-Object -ExpandProperty Id > $ollamaPidFile
            Start-Sleep -Seconds 3
        }
    } catch {}
}

function Start-Backend() {
    if (-not (Test-PortFree $BackendPort)) {
        Log "Backend ya esta escuchando en puerto $BackendPort."
        return
    }
    Log "Iniciando backend en puerto $BackendPort..."
    $outLog = Join-Path $env:TEMP "ergoai-backend.out.log"
    $errLog = Join-Path $env:TEMP "ergoai-backend.err.log"
    Start-Process $python -ArgumentList "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", $BackendPort.ToString() -WorkingDirectory $root -RedirectStandardOutput $outLog -RedirectStandardError $errLog -PassThru | Select-Object -ExpandProperty Id > $backendPidFile
    if (Wait-Port $BackendPort) {
        Log "Backend listo en http://localhost:$BackendPort"
    } else {
        Log "ADVERTENCIA: Backend no respondio a tiempo. Revisar $outLog y $errLog"
    }
}

function Start-Frontend() {
    if (-not (Test-Path "frontend/package.json")) {
        Log "No hay frontend para levantar."
        return
    }
    if (-not (Test-PortFree $FrontendPort)) {
        Log "Frontend ya esta escuchando en puerto $FrontendPort."
        return
    }
    Log "Iniciando frontend en puerto $FrontendPort..."
    $outLog = Join-Path $env:TEMP "ergoai-frontend.out.log"
    $errLog = Join-Path $env:TEMP "ergoai-frontend.err.log"
    # En Windows, npm debe ejecutarse via cmd /c para evitar error Win32
    Start-Process cmd -ArgumentList "/c", "npm", "run", "dev" -WorkingDirectory (Join-Path $root "frontend") -RedirectStandardOutput $outLog -RedirectStandardError $errLog -PassThru | Select-Object -ExpandProperty Id > $frontendPidFile
    Start-Sleep -Seconds 5
    if (-not (Test-PortFree $FrontendPort)) {
        Log "Frontend listo en http://localhost:$FrontendPort"
    } else {
        Log "ADVERTENCIA: Frontend no respondio a tiempo. Revisar $outLog y $errLog"
    }
}

function Action-Up() {
    Ensure-Python
    Ensure-PipDeps
    Ensure-Node
    Ensure-Ollama
    Start-OllamaService

    if (Test-Path "backend/app/vision/modelos.py") {
        Log "Descargando modelos de vision ONNX (una sola vez)..."
        & $python -m backend.app.vision.modelos 2>$null | Out-Null
    }

    Start-Backend
    Start-Frontend
    Log "Sistema levantado. Backend: http://localhost:$BackendPort | Frontend: http://localhost:$FrontendPort"
}

function Action-Down() {
    Log "Deteniendo procesos de ErgoAI..."
    Kill-PidFile $backendPidFile
    Kill-PidFile $frontendPidFile
    Kill-PidFile $ollamaPidFile
    Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "*backend.main*" } | Stop-Process -Force -ErrorAction SilentlyContinue
    Get-Process -Name "node" -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "*vite*" } | Stop-Process -Force -ErrorAction SilentlyContinue
    Get-Process -Name "cmd" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*npm run dev*" } | Stop-Process -Force -ErrorAction SilentlyContinue
    Log "Procesos detenidos."
}

function Action-Status() {
    Log "Estado de puertos:"
    if (-not (Test-PortFree $BackendPort)) { Log "  Backend ($BackendPort): ACTIVO" } else { Log "  Backend ($BackendPort): APAGADO" }
    if (-not (Test-PortFree $FrontendPort)) { Log "  Frontend ($FrontendPort): ACTIVO" } else { Log "  Frontend ($FrontendPort): APAGADO" }
    if (Get-Command ollama -ErrorAction SilentlyContinue) {
        try { ollama list | Out-String } catch { Log "  Ollama: no responde" }
    }
}

function Action-Install() {
    Ensure-Python
    Ensure-PipDeps
    Ensure-Node
    Ensure-Ollama
    Log "Instalacion completa."
}

function Action-Test() {
    if (-not (Test-Path $python)) { throw "Entorno virtual no existe. Elija primero la opcion 5." }
    Log "Ejecutando suite de pruebas pytest..."
    & $python -m pytest
    if ($LASTEXITCODE -ne 0) {
        Log "Pruebas terminaron con codigo $LASTEXITCODE"
    } else {
        Log "Todas las pruebas pasaron."
    }
}

function Action-Build() {
    if (-not (Test-Path "frontend/package.json")) { throw "No hay frontend para build." }
    Log "Construyendo frontend para produccion..."
    & cmd /c "npm run build --prefix frontend" | Out-Null
    Log "Build listo en frontend/dist"
}

function Action-Clean() {
    Log "Limpiando archivos temporales..."
    Get-ChildItem $root -Recurse -Include "__pycache__", "*.pyc" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    Get-ChildItem $root -Recurse -Include ".pytest_cache" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    Kill-PidFile $backendPidFile
    Kill-PidFile $frontendPidFile
    Log "Limpieza completa."
}

function Action-Ollama() {
    if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
        Log "Ollama no esta instalado."
        return
    }
    ollama list
}

function Press-AnyKey() {
    Write-Host ""
    Write-Host "Presione cualquier tecla para volver al menu..." -ForegroundColor Gray -NoNewline
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    Write-Host ""
}

# Bucle principal interactivo
while ($true) {
    Show-Menu
    $opcion = Read-Host "Seleccione una opcion (0-9)"
    Write-Host ""

    switch ($opcion) {
        "1"  { Action-Up }
        "2"  { Action-Down }
        "3"  { Action-Down; Start-Sleep -Seconds 2; Action-Up }
        "4"  { Action-Status }
        "5"  { Action-Install }
        "6"  { Action-Test }
        "7"  { Action-Build }
        "8"  { Action-Clean }
        "9"  { Action-Ollama }
        "0"  { Log "Saliendo del script..."; break }
        default { Log "Opcion invalida: '$opcion'. Intente de nuevo." }
    }

    if ($opcion -ne "0") {
        Press-AnyKey
    }
}