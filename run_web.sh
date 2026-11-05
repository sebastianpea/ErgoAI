#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Búsqueda dinámica de intérprete Python con soporte ML/RTMPose
if [ -n "$VIRTUAL_ENV" ] && [ -f "$VIRTUAL_ENV/bin/python" ]; then
    PYTHON_EXEC="$VIRTUAL_ENV/bin/python"
elif [ -f "$SCRIPT_DIR/../../pruebas_ergonomia/venv/bin/python" ]; then
    PYTHON_EXEC="$SCRIPT_DIR/../../pruebas_ergonomia/venv/bin/python"
elif [ -f "$SCRIPT_DIR/../pruebas_ergonomia/venv/bin/python" ]; then
    PYTHON_EXEC="$SCRIPT_DIR/../pruebas_ergonomia/venv/bin/python"
elif [ -f "$SCRIPT_DIR/.venv/bin/python" ]; then
    PYTHON_EXEC="$SCRIPT_DIR/.venv/bin/python"
elif [ -f "$SCRIPT_DIR/venv/bin/python" ]; then
    PYTHON_EXEC="$SCRIPT_DIR/venv/bin/python"
elif command -v python3 &>/dev/null; then
    PYTHON_EXEC="$(command -v python3)"
else
    PYTHON_EXEC="python"
fi

echo "================================================================================"
echo "Iniciando Servidor Web ErgoAI (Track 4 - Jabil)"
echo "RTMPose WholeBody_133 + ByteTrack + Evaluador REBA Multi-Persona"
echo "================================================================================"

exec "$PYTHON_EXEC" "$SCRIPT_DIR/start_web.py"

