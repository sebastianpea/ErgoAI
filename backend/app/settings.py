"""
Configuración centralizada (ARCHITECTURE.md §4.3).
Rutas y tolerancias se leen de variables de entorno con valores por defecto
resueltos respecto a la raíz del repositorio, no al directorio de trabajo.
"""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _ruta(var: str, defecto: Path) -> Path:
    valor = os.environ.get(var)
    return Path(valor).resolve() if valor else defecto


CONFIG_DIR = _ruta("ERGOAI_CONFIG_DIR", REPO_ROOT / "config_normativo")
WORKSPACE_DIR = _ruta("ERGOAI_WORKSPACE_DIR", REPO_ROOT / "casos_jabil_workspace")
SEED_DIR = Path(__file__).resolve().parent / "seed"
MODELS_DIR = _ruta("ERGOAI_MODELS_DIR", REPO_ROOT / "models")
# "cpu" funciona en cualquier laptop; "cuda" requiere onnxruntime-gpu.
VISION_DEVICE = os.environ.get("ERGOAI_DEVICE", "cpu")
# Umbral de confianza RTMPose para considerar un keypoint fiable en la detección automática.
VISION_CONFIANZA_KEYPOINT = float(os.environ.get("ERGOAI_VISION_CONFIANZA", "0.3"))
MAX_FOTO_MB = float(os.environ.get("ERGOAI_MAX_FOTO_MB", "15"))

CORS_ORIGINS = [
    o.strip()
    for o in os.environ.get("ERGOAI_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if o.strip()
]

# Un ángulo a menos de esta distancia de un umbral REBA se marca "revisar".
TOLERANCIA_UMBRAL_GRADOS = float(os.environ.get("ERGOAI_TOLERANCIA_GRADOS", "5"))
# Confianza mínima de un keypoint para considerarlo fiable.
CONFIANZA_MINIMA = float(os.environ.get("ERGOAI_CONFIANZA_MINIMA", "0.4"))
