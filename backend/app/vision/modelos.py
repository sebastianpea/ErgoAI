"""
Catálogo de modelos ONNX (los mismos que usa el pipeline del equipo en github.com/sebastianpea/ErgoAI,
rama develop) y su descarga a la carpeta local `models/` para que la demo funcione sin internet.

Uso (una sola vez, con internet):
    .venv\\Scripts\\python -m backend.app.vision.modelos
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple

from backend.app.settings import MODELS_DIR


@dataclass(frozen=True)
class ModeloOnnx:
    nombre: str
    archivo: str
    url: str
    entrada: Tuple[int, int]  # (ancho, alto) que espera la red


MODELOS: Dict[str, ModeloOnnx] = {
    "detector": ModeloOnnx(
        nombre="YOLOX-tiny (detección de personas, HumanArt)",
        archivo="yolox_tiny_8xb8-300e_humanart-6f3252f9.onnx",
        url="https://download.openmmlab.com/mmpose/v1/projects/rtmposev1/onnx_sdk/"
            "yolox_tiny_8xb8-300e_humanart-6f3252f9.zip",
        entrada=(416, 416),
    ),
    "pose": ModeloOnnx(
        nombre="RTMW-L WholeBody-133 (cuerpo, pies, rostro y manos)",
        archivo="rtmw-dw-l-m_simcc-cocktail14_270e-256x192_20231122.onnx",
        url="https://download.openmmlab.com/mmpose/v1/projects/rtmw/onnx_sdk/"
            "rtmw-dw-l-m_simcc-cocktail14_270e-256x192_20231122.zip",
        entrada=(192, 256),
    ),
}


def ruta_modelo(clave: str) -> Path:
    return MODELS_DIR / MODELOS[clave].archivo


def faltantes() -> list[str]:
    return [k for k in MODELOS if not ruta_modelo(k).is_file()]


def descargar(clave: str) -> Path:
    """Descarga el .zip oficial de OpenMMLab y deja solo el .onnx en models/."""
    m = MODELOS[clave]
    destino = ruta_modelo(clave)
    if destino.is_file():
        return destino
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        zip_path = Path(tmp) / "modelo.zip"
        print(f"Descargando {m.nombre}…")
        peticion = urllib.request.Request(m.url, headers={"User-Agent": "ergoai-model-fetch"})
        with urllib.request.urlopen(peticion, timeout=120) as resp, open(zip_path, "wb") as f:
            shutil.copyfileobj(resp, f)
        with zipfile.ZipFile(zip_path) as z:
            onnx = [n for n in z.namelist() if n.endswith(".onnx")]
            if len(onnx) != 1:
                raise RuntimeError(f"Se esperaba un .onnx en {m.url}, se encontraron: {onnx}")
            with z.open(onnx[0]) as origen, open(destino.with_suffix(".tmp"), "wb") as f:
                shutil.copyfileobj(origen, f)
    destino.with_suffix(".tmp").replace(destino)
    print(f"  → {destino} ({destino.stat().st_size / 1e6:.1f} MB)")
    return destino


if __name__ == "__main__":
    for clave in MODELOS:
        descargar(clave)
    sys.exit(0 if not faltantes() else 1)
