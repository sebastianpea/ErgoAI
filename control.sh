#!/usr/bin/env bash
#
# control.sh — Menú interactivo para ErgoAI (Linux/macOS Bash)
# Se queda abierto hasta que el usuario elige salir (opción 0).
#

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

BACKEND_PORT="${BACKEND_PORT:-8080}"
FRONTEND_PORT="${FRONTEND_PORT:-5180}"
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
    printf "${C_YELLOW} 10.${C_RESET} Recrear todo desde 0 (reset workspace + levantar)\n"
    printf "${C_RED}  0.${C_RESET} Salir del script\n"
    printf "\n"
    printf "${C_GRAY}Puertos: Backend=$BACKEND_PORT | Frontend=$FRONTEND_PORT${C_RESET}\n"
    printf "\n"
}

is_port_free() {
    local port="$1"
    if command -v ss >/dev/null 2>&1; then
        ss -ltn | grep -qE ":${port}[[:space:]]" && return 1 || return 0
    elif command -v netstat >/dev/null 2>&1; then
        netstat -ltn 2>/dev/null | grep -qE ":${port}[[:space:]]" && return 1 || return 0
    else
        return 0
    fi
}

wait_port() {
    local port="$1"
    local timeout="${2:-30}"
    local elapsed=0
    while [ "$elapsed" -lt "$timeout" ]; do
        if ! is_port_free "$port"; then
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

deps_python_installed() {
    [ -x "$PYTHON" ] && "$PYTHON" -c "import uvicorn, fastapi, pydantic, openpyxl, httpx, pytest" >/dev/null 2>&1
}

ensure_pip_deps() {
    local force="${1:-0}"
    if [ "$force" != "1" ] && deps_python_installed; then
        log "Dependencias principales ya instaladas (uvicorn, fastapi, pydantic, openpyxl)."
        return 0
    fi

    log "Instalando dependencias de Python..."
    "$PIP" install --upgrade pip >/dev/null 2>&1 || true

    # 1) Dependencias principales (uvicorn, fastapi, pydantic, openpyxl, etc.)
    if [ -f backend/requirements.txt ]; then
        if ! "$PIP" install -r backend/requirements.txt >/dev/null 2>&1; then
            log "Adaptando pines de backend/requirements.txt para Python $(python3 --version | cut -d' ' -f2)..."
            sed 's/^pydantic==/pydantic>=/g' backend/requirements.txt > /tmp/requirements-backend-compat.txt
            if ! "$PIP" install --only-binary :all: -r /tmp/requirements-backend-compat.txt >/dev/null 2>&1; then
                log "Reintentando con PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1..."
                PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1 "$PIP" install -r /tmp/requirements-backend-compat.txt >/dev/null 2>&1 || true
            fi
            rm -f /tmp/requirements-backend-compat.txt
        fi
    fi

    # 2) openpyxl es necesario para los reportes de Excel
    if ! "$PYTHON" -c "import openpyxl" >/dev/null 2>&1; then
        log "Instalando openpyxl (requerido para reportes Excel)..."
        "$PIP" install openpyxl >/dev/null 2>&1 || log "AVISO: no se pudo instalar openpyxl"
    fi

    # 3) Verificacion final de que uvicorn este disponible
    if ! "$PYTHON" -c "import uvicorn" >/dev/null 2>&1; then
        echo "Fallo al instalar dependencias principales (backend/requirements.txt)." >&2
        echo "  Python $(python3 --version) no tiene wheels precompilados para pydantic-core/uvicorn." >&2
        echo "  Soluciones: use Docker (docker-compose up) o Python 3.11/3.12." >&2
        return 1
    fi
    log "Dependencias principales instaladas (uvicorn, fastapi, pydantic, openpyxl)."

    # 4) Requisitos adicionales del requirements.txt raiz (ignorando delegaciones -r backend/...)
    if [ -f requirements.txt ]; then
        grep -vE '^[[:space:]]*(#|$|-r[[:space:]]+backend/)' requirements.txt > /tmp/requirements-root-extra.txt 2>/dev/null || true
        if [ -s /tmp/requirements-root-extra.txt ]; then
            if ! "$PIP" install -r /tmp/requirements-root-extra.txt >/dev/null 2>&1; then
                log "AVISO: No se pudieron instalar algunos requisitos adicionales del requirements.txt raiz (continuando)."
            fi
        fi
        rm -f /tmp/requirements-root-extra.txt
    fi

    # 5) Visión artificial (opcional)
    if [ -f backend/requirements-vision.txt ]; then
        sed 's/onnxruntime==1\.20\.1/onnxruntime>=1.20.1/g' backend/requirements-vision.txt > /tmp/requirements-vision-fixed.txt
        "$PIP" install -r /tmp/requirements-vision-fixed.txt >/dev/null 2>&1 || true
        rm -f /tmp/requirements-vision-fixed.txt
    fi
    log "Dependencias de Python instaladas."
}

ensure_node() {
    local force="${1:-0}"
    if ! command -v node >/dev/null 2>&1; then
        echo "Node.js no esta instalado. Instalelo desde https://nodejs.org/" >&2
        return 1
    fi
    if [ -f frontend/package.json ]; then
        if [ "$force" != "1" ] && [ -d frontend/node_modules ]; then
            log "Dependencias de Node (frontend) listas."
            return 0
        fi
        log "Instalando dependencias de Node (frontend)..."
        if ! (cd frontend && npm install >/dev/null 2>&1); then
            echo "Error al instalar dependencias de Node en frontend/." >&2
            return 1
        fi
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
        log "Ollama no esta instalado. El agente IA usara fallback normativo o proveedor cloud."
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
        if command -v curl >/dev/null 2>&1 && ! curl -sf -i -H "Origin: http://localhost:$FRONTEND_PORT" "http://localhost:$BACKEND_PORT/salud" 2>/dev/null | grep -qi "access-control-allow-origin"; then
            log "Reiniciando backend en puerto $BACKEND_PORT para actualizar configuracion CORS..."
            kill_pid_file "$BACKEND_PID_FILE"
            command -v fuser >/dev/null 2>&1 && fuser -k "${BACKEND_PORT}/tcp" >/dev/null 2>&1 || true
            sleep 1
        else
            log "Backend ya esta escuchando en puerto $BACKEND_PORT."
            return 0
        fi
    fi
    if ! "$PYTHON" -c "import uvicorn" >/dev/null 2>&1; then
        log "uvicorn no esta instalado. Ejecute primero la opcion 5 (Instalar dependencias)."
        return 1
    fi
    log "Iniciando backend en puerto $BACKEND_PORT..."
    export BACKEND_PORT FRONTEND_PORT
    export CORS_ORIGINS="${CORS_ORIGINS:-http://localhost:${FRONTEND_PORT},http://127.0.0.1:${FRONTEND_PORT},http://localhost:5173,http://127.0.0.1:5173,http://localhost:80,http://localhost}"
    nohup "$PYTHON" -m uvicorn backend.main:app --host 0.0.0.0 --port "$BACKEND_PORT" > /tmp/ergoai-backend.out.log 2> /tmp/ergoai-backend.err.log &
    echo $! > "$BACKEND_PID_FILE"
    if wait_port "$BACKEND_PORT"; then
        log "Backend listo en http://localhost:$BACKEND_PORT"
        return 0
    else
        log "ADVERTENCIA: Backend no respondio a tiempo. Revisar /tmp/ergoai-backend.*.log"
        return 1
    fi
}

start_frontend() {
    [ -f frontend/package.json ] || return 0
    if ! is_port_free "$FRONTEND_PORT"; then
        log "Frontend ya esta escuchando en puerto $FRONTEND_PORT."
        return 0
    fi
    log "Iniciando frontend en puerto $FRONTEND_PORT..."
    export BACKEND_PORT FRONTEND_PORT
    export VITE_PORT="$FRONTEND_PORT"
    export VITE_BACKEND_PORT="$BACKEND_PORT"
    if [ -x frontend/node_modules/.bin/vite ]; then
        (cd frontend && nohup npm run dev -- --port "$FRONTEND_PORT" --host 0.0.0.0 > /tmp/ergoai-frontend.out.log 2> /tmp/ergoai-frontend.err.log & echo $! > "$FRONTEND_PID_FILE")
    else
        if [ ! -d frontend/dist ]; then
            log "Construyendo frontend/dist..."
            action_build || return 1
        fi
        (cd frontend && nohup "$PYTHON" -m http.server "$FRONTEND_PORT" --directory dist > /tmp/ergoai-frontend.out.log 2> /tmp/ergoai-frontend.err.log & echo $! > "$FRONTEND_PID_FILE")
    fi
    if wait_port "$FRONTEND_PORT" 15; then
        log "Frontend listo en http://localhost:$FRONTEND_PORT"
        return 0
    else
        log "ADVERTENCIA: Frontend no respondio a tiempo. Revisar /tmp/ergoai-frontend.*.log"
        return 1
    fi
}

ensure_vision_models() {
    if [ -f backend/app/vision/modelos.py ]; then
        if ! "$PYTHON" -c "from backend.app.vision.modelos import faltantes; raise SystemExit(0 if not faltantes() else 1)" >/dev/null 2>&1; then
            log "Descargando modelos de vision ONNX (una sola vez)..."
            "$PYTHON" -m backend.app.vision.modelos >/dev/null 2>&1 || log "AVISO: No se pudieron descargar los modelos ONNX."
        else
            log "Modelos de vision ONNX listos."
        fi
    fi
}

action_up() {
    ensure_python || return 1
    ensure_pip_deps 0 || return 1
    ensure_node 0 || return 1
    ensure_ollama || return 1
    start_ollama_service
    ensure_vision_models

    start_backend || return 1
    start_frontend || return 1
    log "Sistema levantado. Backend: http://localhost:$BACKEND_PORT | Frontend: http://localhost:$FRONTEND_PORT"
}

action_down() {
    log "Deteniendo procesos de ErgoAI..."
    kill_pid_file "$BACKEND_PID_FILE"
    kill_pid_file "$FRONTEND_PID_FILE"
    kill_pid_file "/tmp/ergoai-frontend-static.pid"
    kill_pid_file "$OLLAMA_PID_FILE"
    pkill -f "uvicorn backend.main:app" 2>/dev/null || true
    pkill -f "vite.*--port $FRONTEND_PORT" 2>/dev/null || true
    pkill -f "http.server $FRONTEND_PORT" 2>/dev/null || true
    if command -v fuser >/dev/null 2>&1; then
        fuser -k "${BACKEND_PORT}/tcp" >/dev/null 2>&1 || true
        fuser -k "${FRONTEND_PORT}/tcp" >/dev/null 2>&1 || true
    fi
    log "Procesos detenidos."
}

action_status() {
    log "Estado de puertos y servicios:"
    if is_port_free "$BACKEND_PORT"; then
        log "  Backend ($BACKEND_PORT): APAGADO"
    else
        if command -v curl >/dev/null 2>&1 && curl -sf "http://localhost:$BACKEND_PORT/salud" >/dev/null 2>&1; then
            log "  Backend ($BACKEND_PORT): ACTIVO (salud OK)"
        else
            log "  Backend ($BACKEND_PORT): ACTIVO"
        fi
    fi
    if is_port_free "$FRONTEND_PORT"; then
        log "  Frontend ($FRONTEND_PORT): APAGADO"
    else
        log "  Frontend ($FRONTEND_PORT): ACTIVO"
    fi
    if command -v ollama >/dev/null 2>&1; then
        if ollama list >/dev/null 2>&1; then
            log "  Ollama: ACTIVO"
            ollama list 2>/dev/null || true
        else
            log "  Ollama: INSTALADO (servicio detenido)"
        fi
    else
        log "  Ollama: NO INSTALADO (usando fallback normativo / cloud)"
    fi
}

action_install() {
    local py_ver
    py_ver="$(python3 --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+' || true)"
    if [ -n "${py_ver:-}" ] && [ "$(printf '%s\n' "3.14" "$py_ver" | sort -V | head -n1)" = "3.14" ]; then
        log "NOTA: Python ${py_ver} detectado. Se usaran wheels compatibles para pydantic/onnxruntime."
    fi
    ensure_python || return 1
    ensure_pip_deps 1 || return 1
    ensure_node 1 || return 1
    ensure_ollama || return 1
    ensure_vision_models
    log "Instalacion completa."
}

action_test() {
    [ -x "$PYTHON" ] || { echo "Entorno virtual no existe. Elija primero la opcion 5." >&2; return 1; }
    log "Ejecutando suite de pruebas pytest..."
    "$PYTHON" -m pytest
}

action_build() {
    [ -f frontend/package.json ] || { echo "No hay frontend para build." >&2; return 1; }
    ensure_node 0 || return 1
    log "Construyendo frontend para produccion..."
    if (cd frontend && npm run build); then
        log "Build listo en frontend/dist"
    else
        echo "Error al construir el frontend." >&2
        return 1
    fi
}

action_clean() {
    log "Limpiando archivos temporales..."
    find "$ROOT" -type d -name "__pycache__" -prune -exec rm -rf {} + 2>/dev/null || true
    find "$ROOT" -name "*.pyc" -delete 2>/dev/null || true
    find "$ROOT" -type d -name ".pytest_cache" -prune -exec rm -rf {} + 2>/dev/null || true
    rm -f /tmp/requirements-backend-*.txt /tmp/requirements-vision-fixed.txt /tmp/requirements-root-extra.txt 2>/dev/null || true
    for pid_file in "$BACKEND_PID_FILE" "$FRONTEND_PID_FILE" "$OLLAMA_PID_FILE"; do
        if [ -f "$pid_file" ]; then
            local pid
            pid="$(cat "$pid_file" 2>/dev/null || true)"
            if [ -z "${pid:-}" ] || ! kill -0 "$pid" 2>/dev/null; then
                rm -f "$pid_file"
            fi
        fi
    done
    log "Limpieza completa."
}

action_reset_all() {
    log "Recreando todo el sistema desde cero..."
    action_down
    sleep 2

    log "Limpiando workspace de datos y runtime (casos_jabil_workspace)..."
    rm -rf "$ROOT/casos_jabil_workspace"
    mkdir -p "$ROOT/casos_jabil_workspace"

    log "Limpiando temporales y cache de frontend..."
    action_clean
    rm -rf "$ROOT/frontend/dist" "$ROOT/frontend/node_modules/.vite"

    log "Reconstruyendo bundle del frontend..."
    action_build || log "AVISO: no se pudo compilar frontend/dist (se usara dev server si esta disponible)"

    log "Levantando backend y frontend desde cero (re-sembrando datos)..."
    action_up
    log "¡Sistema recreado y levantado desde cero con exito!"
}

action_ollama() {
    if ! command -v ollama >/dev/null 2>&1; then
        log "Ollama no esta instalado. El agente IA opera con fallback normativo o proveedor cloud (LLM_PROVIDER en .env)."
        return 1
    fi
    if ! ollama list 2>/dev/null; then
        log "El servicio de Ollama no esta respondiendo. Inicielo con 'ollama serve' o la opcion 1."
        return 1
    fi
}

# Bucle principal interactivo
while true; do
    show_menu
    printf "${C_YELLOW}Seleccione una opcion (0-10): ${C_RESET}"
    read -r opcion || break
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
        10|r|R) action_reset_all ;;
        0)  log "Saliendo del script..."; break ;;
        *)  log "Opcion invalida: '$opcion'. Intente de nuevo." ;;
    esac

    if [ "$opcion" != "0" ]; then
        press_any_key
    fi
done
