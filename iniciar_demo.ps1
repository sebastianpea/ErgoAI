# Arranque de ErgoAI para la demo: backend (8000) + frontend (5173) + navegador.
# Uso: doble clic en iniciar_demo.bat  (o: powershell -ExecutionPolicy Bypass -File iniciar_demo.ps1)
$ErrorActionPreference = "Stop"
$raiz = $PSScriptRoot
$python = Join-Path $raiz ".venv\Scripts\python.exe"

function Falta($mensaje) {
    Write-Host ""
    Write-Host "  [X] $mensaje" -ForegroundColor Red
    Write-Host ""
    Read-Host "Presiona Enter para salir"
    exit 1
}

Write-Host "ErgoAI - preparando la demo..." -ForegroundColor Cyan

if (-not (Test-Path $python)) {
    Falta "No existe .venv. Ejecuta una vez:  python -m venv .venv ; .venv\Scripts\python -m pip install -r backend/requirements.txt -r backend/requirements-vision.txt"
}
if (-not (Test-Path (Join-Path $raiz "frontend\node_modules"))) {
    Falta "Faltan dependencias del frontend. Ejecuta una vez:  cd frontend ; npm install"
}
$modelos = Get-ChildItem (Join-Path $raiz "models") -Filter *.onnx -ErrorAction SilentlyContinue
if (($modelos | Measure-Object).Count -lt 2) {
    Write-Host "  [!] Faltan los modelos de vision: 'Nuevo caso desde fotos' no estara disponible." -ForegroundColor Yellow
    Write-Host "      Para descargarlos (con internet):  .venv\Scripts\python -m backend.app.vision.modelos" -ForegroundColor Yellow
}

foreach ($puerto in 8000, 5173) {
    if (Get-NetTCPConnection -LocalPort $puerto -State Listen -ErrorAction SilentlyContinue) {
        Write-Host "  [!] El puerto $puerto ya esta en uso: se reutiliza lo que ya esta corriendo." -ForegroundColor Yellow
    }
}

if (-not (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue)) {
    Start-Process powershell -WorkingDirectory $raiz -ArgumentList "-NoExit", "-Command",
        "`$host.UI.RawUI.WindowTitle = 'ErgoAI - backend'; & '$python' -m uvicorn backend.main:app --port 8000"
}
if (-not (Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue)) {
    Start-Process powershell -WorkingDirectory (Join-Path $raiz "frontend") -ArgumentList "-NoExit", "-Command",
        "`$host.UI.RawUI.WindowTitle = 'ErgoAI - frontend'; npm run dev"
}

Write-Host "Esperando a que el sistema responda..." -NoNewline
$listo = $false
for ($i = 0; $i -lt 60 -and -not $listo; $i++) {
    try {
        Invoke-RestMethod http://localhost:8000/salud -TimeoutSec 2 | Out-Null
        Invoke-WebRequest http://localhost:5173/ -UseBasicParsing -TimeoutSec 2 | Out-Null
        $listo = $true
    } catch { Start-Sleep -Milliseconds 500; Write-Host "." -NoNewline }
}
Write-Host ""
if (-not $listo) { Falta "El sistema no respondio en 30 s. Revisa las ventanas 'ErgoAI - backend' y 'ErgoAI - frontend'." }

Start-Process "http://localhost:5173"
Write-Host "Listo: http://localhost:5173  (para detener, cierra las ventanas del backend y del frontend)" -ForegroundColor Green
Start-Sleep -Seconds 3
