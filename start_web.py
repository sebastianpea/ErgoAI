#!/usr/bin/env python3
"""Script de inicio para el servidor web de ErgoAI (Track 4 - Jabil).

Auto-detecta el entorno virtual con soporte para RTMPose/ONNX/GPU y previene
errores de importación, conflictos de puerto o dependencias faltantes.
"""

from __future__ import annotations

import os
import socket
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent

# 1. Asegurar auto-re-ejecución si el intérprete actual no cuenta con rtmlib
try:
    import rtmlib
    has_rtmlib = True
except ImportError:
    has_rtmlib = False

if not has_rtmlib:
    candidates = [
        ROOT_DIR / ".venv" / "bin" / "python",
        ROOT_DIR / "venv" / "bin" / "python",
        ROOT_DIR.parent / "pruebas_ergonomia" / "venv" / "bin" / "python",
        ROOT_DIR.parent.parent / "pruebas_ergonomia" / "venv" / "bin" / "python",
        Path.home() / "miniconda3" / "envs" / "vision_yolo" / "bin" / "python",
    ]
    for py_candidate in candidates:
        if py_candidate.exists() and py_candidate.resolve() != Path(sys.executable).resolve():
            print(f"🔄 Intérprete actual ({sys.executable}) no tiene rtmlib.")
            print(f"🚀 Conmutando automáticamente a entorno compatible: {py_candidate}")
            os.execv(str(py_candidate), [str(py_candidate), str(Path(__file__).resolve())] + sys.argv[1:])

# 2. Agregar directorios de código fuente al PYTHONPATH
sys.path.insert(0, str(ROOT_DIR / "src"))
for candidate_sibling in [
    ROOT_DIR.parent / "pruebas_ergonomia",
    ROOT_DIR.parent.parent / "pruebas_ergonomia",
]:
    if candidate_sibling.exists():
        sys.path.insert(0, str(candidate_sibling))


def find_available_port(default_port: int, host: str = "127.0.0.1") -> int:
    """Verifica si el puerto está disponible o busca el siguiente libre para evitar crash por [Errno 98]."""
    port = default_port
    while port < default_port + 50:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind((host, port))
                return port
            except OSError:
                port += 1
    return default_port


def main() -> None:
    requested_port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")

    actual_port = find_available_port(requested_port, host="127.0.0.1")
    if actual_port != requested_port:
        print(f"⚠️  Puerto {requested_port} ocupado. Seleccionado puerto libre {actual_port}.")

    print("=" * 80)
    print("ErgoAI — Copiloto Auditor de Ergonomía Industrial (Track 4 / Jabil)")
    print("Inferencia: RTMPose WholeBody-133 + ByteTrack + Evaluador REBA Oficial")
    print(f"URL de Acceso Local: http://127.0.0.1:{actual_port}")
    print(f"URL de Red:         http://{host}:{actual_port}")
    print("Presiona Ctrl+C para detener el servidor.")
    print("=" * 80)

    import uvicorn
    from ergoai.web.server import app

    try:
        uvicorn.run(app, host=host, port=actual_port, log_level="info")
    except KeyboardInterrupt:
        print("\n🛑 Servidor detenido ordenadamente por el usuario.")


if __name__ == "__main__":
    main()
