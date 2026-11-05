"""Módulo centralizado de configuración y descubrimiento dinámico de recursos (Settings).

Elimina rutas absolutas hardcodeadas, dependencias de usuario y valores mágicos
conforme a ARCHITECTURE.md (Secciones 4.1 y 4.3).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import List, Optional, Tuple
from pydantic import BaseModel, Field

from ergoai.domain.constants import (
    DEFAULT_OPERATOR_HEIGHT_MM,
    DEFAULT_BIACROMIAL_SHOULDER_WIDTH_MM,
)


class HardwareConfig(BaseModel):
    """Configuración de aceleración de hardware e inferencia ONNX Runtime."""
    backend: str = "onnxruntime"
    device: str = Field(default_factory=lambda: os.environ.get("ERGOAI_DEVICE", "cuda"))
    fallback_device: str = "cpu"
    vram_limit_mb: float = 3500.0


class VisionModelConfig(BaseModel):
    """Parámetros de modelos de visión por computadora."""
    yolox_input_size: Tuple[int, int] = (416, 416)
    yolox_nms_thr: float = 0.45
    yolox_score_thr: float = 0.25
    yolox_person_class_id: int = 0

    rtmpose_input_size: Tuple[int, int] = (192, 256)
    total_keypoints: int = 133
    min_keypoint_confidence: float = 0.50
    min_face_keypoint_confidence: float = 0.40
    min_face_points_present: int = 2

    bytetrack_activation_thr: float = 0.25
    bytetrack_fps: float = 30.0


class CalibrationConfig(BaseModel):
    """Parámetros de calibración métrica (píxeles a milímetros) sin hardcode."""
    default_person_height_mm: float = DEFAULT_OPERATOR_HEIGHT_MM
    default_shoulder_width_mm: float = DEFAULT_BIACROMIAL_SHOULDER_WIDTH_MM
    # Altura estándar de una persona en píxeles cuando ocupa el 80% de un encuadre HD (480px altura)
    fallback_scale_mm_per_px: float = 2.8


class ErgoAISettings:
    """Administrador centralizado de rutas, modelos y variables de entorno."""

    def __init__(self) -> None:
        self.workspace_dir: Path = Path(__file__).resolve().parent.parent.parent.parent
        self.outputs_dir: Path = self.workspace_dir / "outputs"
        self.audit_log_path: Path = self.outputs_dir / "audit_log.json"

        self.hardware: HardwareConfig = HardwareConfig()
        self.vision: VisionModelConfig = VisionModelConfig()
        self.calibration: CalibrationConfig = CalibrationConfig()

        self.default_specialist: str = os.environ.get("ERGOAI_SPECIALIST", "Ingeniero_EHS_Jabil")
        self.host: str = os.environ.get("HOST", "0.0.0.0")
        self.port: int = int(os.environ.get("PORT", "8000"))

    @property
    def dataset_dir(self) -> Path:
        """Descubre dinámicamente la carpeta de dataset sin rutas absolutas de usuario."""
        env_dataset = os.environ.get("ERGOAI_DATASET_DIR")
        if env_dataset and Path(env_dataset).exists():
            return Path(env_dataset)

        candidates = [
            self.workspace_dir / "dataset",
            self.workspace_dir.parent / "pruebas_ergonomia" / "dataset",
            self.workspace_dir.parent.parent / "pruebas_ergonomia" / "dataset",
        ]
        for c in candidates:
            if c.exists():
                return c

        return self.workspace_dir / "dataset"

    @property
    def checkpoints_dir(self) -> Path:
        """Descubre dinámicamente el directorio de checkpoints ONNX."""
        env_models = os.environ.get("ERGOAI_MODELS_DIR")
        if env_models and Path(env_models).exists():
            return Path(env_models)

        candidates = [
            Path.home() / ".cache" / "rtmlib" / "hub" / "checkpoints",
            self.workspace_dir / "models",
            self.workspace_dir.parent / "pruebas_ergonomia" / "models",
            self.workspace_dir.parent.parent / "pruebas_ergonomia" / "models",
        ]
        for c in candidates:
            if c.exists():
                return c

        return Path.home() / ".cache" / "rtmlib" / "hub" / "checkpoints"

    def get_yolox_checkpoint_path(self) -> str:
        """Retorna la ruta al modelo ONNX de YOLOX."""
        chk_dir = self.checkpoints_dir
        if chk_dir.exists():
            for f in chk_dir.glob("yolox_tiny*.onnx"):
                return str(f)
            for f in chk_dir.glob("yolox*.onnx"):
                return str(f)
        return str(chk_dir / "yolox_tiny_8xb8-300e_humanart-6f3252f9.onnx")

    def get_rtmpose_checkpoint_path(self) -> str:
        """Retorna la ruta al modelo ONNX de RTMPose WholeBody-133."""
        chk_dir = self.checkpoints_dir
        if chk_dir.exists():
            for f in chk_dir.glob("rtmw-dw*.onnx"):
                return str(f)
            for f in chk_dir.glob("rtmpose*wholebody*.onnx"):
                return str(f)
        return str(chk_dir / "rtmw-dw-l-m_simcc-cocktail14_270e-256x192_20231122.onnx")

    def discover_cuda_library_paths(self) -> List[str]:
        """Descubre dinámicamente las bibliotecas compartidas de CUDA/cuDNN en el entorno activo."""
        found_dirs: List[str] = []

        # 1. Rutas en LD_LIBRARY_PATH
        ld_path = os.environ.get("LD_LIBRARY_PATH", "")
        for p in ld_path.split(":"):
            if p and os.path.isdir(p):
                found_dirs.append(p)

        # 2. Rutas dentro del entorno Python activo (site-packages de nvidia / conda)
        py_ver = f"python{sys.version_info.major}.{sys.version_info.minor}"
        prefix = Path(sys.prefix)
        nvidia_cudnn = prefix / "lib" / py_ver / "site-packages" / "nvidia" / "cudnn" / "lib"
        if nvidia_cudnn.exists():
            found_dirs.append(str(nvidia_cudnn))

        # 3. Directorios Conda si existen
        conda_prefix = os.environ.get("CONDA_PREFIX")
        if conda_prefix:
            conda_lib = Path(conda_prefix) / "lib"
            if conda_lib.exists():
                found_dirs.append(str(conda_lib))

        # 4. Fallback a rutas estándar del sistema
        system_cuda = Path("/usr/local/cuda/lib64")
        if system_cuda.exists():
            found_dirs.append(str(system_cuda))

        return list(dict.fromkeys(found_dirs))


# Instancia singleton de configuración
SETTINGS = ErgoAISettings()
