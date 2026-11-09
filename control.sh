#!/usr/bin/env bash
#
# control.sh — Menú interactivo para ErgoAI (Linux/macOS Bash)
# Se queda abierto hasta que el usuario elige salir (opción 0).
#

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
VENV="$ROOT/.venv"
PYTHON="$VENV/bin/python"
PIP="$VENV/bin/pip"
BACKEND_PID_FILE="/tmp/ergoai-backend.pid"
FRONTEND_PID_FILE="/tmp/ergoai-frontend.pid"
OLLAMA_PID_FILE="/tmp/ergoai-ollama.pid"

# Colores ANSI
C_CYAN='\033[1;36m'
C_YELLOW='\033[1;33m'
C_GREEN='\033[1;32m'
C_RED='\033[1;31m'
C_GRAY='\033[0;37m'
C_RESET='\033[0m'

log() { printf "${C_CYAN}[ergoai]${C_RESET} %s\n" "$*"; }

press_any_key() {
    printf "${C_GRAY}Presione cualquier tecla para volver al menu...${C_RESET}"
    read -r -n 1 -s
    printf "\n"
}

show_menu() {
    clear
    printf "${C_YELLOW}========================================${C_RESET}\n"
    printf "${C_YELLOW}      ERGOAI - PANEL DE CONTROL         ${C_RESET}\n"
    printf "${C_YELLOW}========================================${C_RESET}\n"
    printf "\n"
    printf "${C_GREEN}  1.${C_RESET} Levantar sistema (backend + frontend)\n"
    printf "${C_RED}  2.${C_RESET} Bajar sistema (detener todo)\n"
    printf "${C_YELLOW}  3.${C_RESET} Reiniciar sistema\n"
    printf "${C_CYAN}  4.${C_RESET} Estado de puertos y servicios\n"
    printf "${C_CYAN}  5.${C_RESET} Instalar dependencias\n"
    printf "${C_CYAN}  6.${C_RESET} Ejecutar pruebas (pytest)\n"
    printf "${C_CYAN}  7.${C_RESET} Build produccion frontend\n"
    printf "${C_CYAN}  8.${C_RESET} Limpiar temporales\n"
    printf "${C_CYAN}  9.${C_RESET} Listar modelos Ollama\n"
    printf "${C_RED}  0.${C_RESET} Salir del script\n"
    printf "\n"
    printf "${C_GRAY}Puertos: Backend=$BACKEND_PORT | Frontend=$FRONTENDPort${C_RESET}\n"
    printf "\n"
}

is_port_free() {
    local port="$1"
    if command -v ss >/dev/null 2>&1; then
        ss -ltn | grep -q ":$port " && return 1 || return 0
    elif command -v netstat >/dev/null 2>&1; then
        netstat -ltn 2>/dev/null | grep -q ":$port " && return 1 || return 0
    else
        return 0
    fi
}

wait_port() {
    local port="$1"
    local timeout="${2:-30}"
    local elapsed=0
    while [ "$elapsed" -lt "$timeout" ]; do
        if curl -sf "http://localhost:$port/salud" >/dev/null 2>&1; then
            return 0
        fi
        sleep 1
        elapsed=$((elapsed + 1))
    done
    return 1
}

kill_pid_file() {
    local file="$1"
    if [ -f "$file" ]; then
        local pid
        pid="$(cat "$file" 2>/dev/null || true)"
        if [ -n "${pid:-}" ] && kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
            sleep 1
            kill -9 "$pid" 2>/dev/null || true
        fi
        rm -f "$file"
    fi
}

ensure_python() {
    if [ ! -x "$PYTHON" ]; then
        log "Creando entorno virtual Python en $VENV..."
        python3 -m venv "$VENV"
    fi
    if [ ! -x "$PYTHON" ]; then
        echo "No se pudo crear el entorno virtual." >&2
        return 1
    fi
    log "Entorno virtual listo: $PYTHON"
}

ensure_pip_deps() {
    log "Instalando dependencias de Python..."
    "$PIP" install --upgrade pip >/dev/null 2>&1 || true
    if [ -f requirements.txt ]; then
        "$PIP" install -r requirements.txt >/dev/null 2>&1 || true
    fi
    if [ -f backend/requirements-vision.txt ]; then
        sed 's/onnxruntime==1\.20\.1/onnxruntime>=1.24.0/g' backend/requirements-vision.txt > /tmp/requirements-vision-fixed.txt
        "$PIP" install -r /tmp/requirements-vision-fixed.txt >/dev/null 2>&1 || true
        rm -f /tmp/requirements-vision-fixed.txt
    fi
    log "Dependencias de Python instaladas."
}

ensure_node() {
    if ! command -v node >/dev/null 2>&1; then
        echo "Node.js no esta instalado. Instalelo desde https://nodejs.org/" >&2
        return 1
    fi
    if [ -f frontend/package.json ]; then
        log "Instalando dependencias de Node (frontend)..."
        (cd frontend && npm install >/dev/null 2>&1 || true)
        log "Dependencias de Node instaladas."
    fi
}

ensure_ollama() {
    if command -v ollama >/dev/null 2>&1; then
        log "Ollama detectado. Verificando modelo qwen2.5..."
        if ! ollama list 2>/dev/null | grep -q "qwen2.5"; then
            log "Descargando modelo qwen2.5 (puede tardar)..."
            ollama pull qwen2.5 >/dev/null 2>&1 || true
        fi
    else
        log "Ollama no esta instalado. El agente IA usara fallback o fallara."
    fi
}

start_ollama_service() {
    command -v ollama >/dev/null 2>&1 || return 0
    if ! ollama list >/dev/null 2>&1; then
        log "Iniciando ollama serve..."
        nohup ollama serve >/dev/null 2>&1 &
        echo $! > "$OLLAMA_PID_FILE"
        sleep 3
    fi
}

start_backend() {
    if ! is_port_free "$BACKEND_PORT"; then
        log "Backend ya esta escuchando en puerto $BACKEND_PORT."
        return 0
    fi
    log "Iniciando backend en puerto $BACKEND_PORT..."
    nohup "$PYTHON" -m uvicorn backend.main:app --host 0.0.0.0 --port "$BACKEND_PORT" > /tmp/ergoai-backend.out.log 2> /tmp/ergoai-backend.err.log &
    echo $! > "$BACKEND_PID_FILE"
    if wait_port "$BACKEND_PORT"; then
        log "Backend listo en http://localhost:$BACKEND_PORT"
    else
        log "ADVERTENCIA: Backend no respondio a tiempo. Revisar /tmp/ergoai-backend.*.log"
    fi
}

start_frontend() {
    [ -f frontend/package.json ] || return 0
    if ! is_port_free "$FRONTEND_PORT"; then
        log "Frontend ya esta escuchando en puerto $FRONTEND_PORT."
        return 0
    fi
    log "Iniciando frontend en puerto $FRONTEND_PORT..."
    (cd frontend && nohup npm run dev > /tmp/ergoai-frontend.out.log 2> /tmp/ergoai-frontend.err.log &)
    echo $! > "$FRONTEND_PID_FILE"
    sleep 5
    if ! is_port_free "$FRONTEND_PORT"; then
        log "Frontend listo en http://localhost:$FRONTEND_PORT"
    else
        log "ADVERTENCIA: Frontend no respondio a tiempo. Revisar /tmp/ergoai-frontend.*.log"
    fi
}

action_up() {
    ensure_python || return 1
    ensure_pip_deps || return 1
    ensure_node || return 1
    ensure_ollama || return 1
    start_ollama_service

    if [ -f backend/app/vision/modelos.py ]; then
        log "Descargando modelos de vision ONNX (una sola vez)..."
        "$PYTHON" -m backend.app.vision.modelos >/dev/null 2>&1 || true
    fi

    start_backend
    start_frontend
    log "Sistema levantado. Backend: http://localhost:$BACKEND_PORT | Frontend: http://localhost:$FRONTEND_PORT"
}

action_down() {
    log "Deteniendo procesos de ErgoAI..."
    kill_pid_file "$BACKEND_PID_FILE"
    kill_pid_file "$FRONTEND_PID_FILE"
    kill_pid_file "$OLLAMA_PID_FILE"
    pkill -f "backend.main" 2>/dev/null || true
    pkill -f "vite" 2>/dev/null || true
    log "Procesos detenidos."
}

action_status() {
    log "Estado de puertos:"
    if is_port_free "$BACKEND_PORT"; then
        log "  Backend ($BACKEND_PORT): APAGADO"
    else
        log "  Backend ($BACKEND_PORT): ACTIVO"
    fi
    if is_port_free "$FRONTEND_PORT"; then
        log "  Frontend ($FRONTEND_PORT): APAGADO"
    else
        log "  Frontend ($FRONTEND_PORT): ACTIVO"
    fi
    if command -v ollama >/dev/null 2>&1; then
        ollama list 2>/dev/null || log "  Ollama: no responde"
    fi
}

action_install() {
    ensure_python || return 1
    ensure_pip_deps || return 1
    ensure_node || return 1
    ensure_ollama || return 1
    log "Instalacion completa."
}

action_test() {
    [ -x "$PYTHON" ] || { echo "Entorno virtual no existe. Elija primero la opcion 5." >&2; return 1; }
    log "Ejecutando suite de pruebas pytest..."
    "$PYTHON" -m pytest
}

action_build() {
    [ -f frontend/package.json ] || { echo "No hay frontend para build." >&2; return 1; }
    log "Construyendo frontend para produccion..."
    (cd frontend && npm run build)
    log "Build listo en frontend/dist"
}

action_clean() {
    log "Limpiando archivos temporales..."
    find "$ROOT" -type d -name "__pycache__" -prune -exec rm -rf {} + 2>/dev/null || true
    find "$ROOT" -name "*.pyc" -delete 2>/dev/null || true
    find "$ROOT" -type d -name ".pytest_cache" -prune -exec rm -rf {} + 2>/dev/null || true
    kill_pid_file "$BACKEND_PID_FILE"
    kill_pid_file "$FRONTEND_PID_FILE"
    log "Limpieza completa."
}

action_ollama() {
    command -v ollama >/dev/null 2>&1 || { echo "Ollama no esta instalado." >&2; return 1; }
    ollama list
}

# Bucle principal interactivo
while true; do
    show_menu
    printf "${C_YELLOW}Seleccione una opcion (0-9): ${C_RESET}"
    read -r opcion
    printf "\n"

    case "$opcion" in
        1)  action_up ;;
        2)  action_down ;;
        3)  action_down; sleep 2; action_up ;;
        4)  action_status ;;
        5)  action_install ;;
        6)  action_test ;;
        7)  action_build ;;
        8)  action_clean ;;
        9)  action_ollama ;;
        0)  log "Saliendo del script..."; break ;;
        *)  log "Opcion invalida: '$opcion'. Intente de nuevo." ;;
    esac

    if [ "$opcion" != "0" ]; then
        press_any_key
    fi
done