"""Esquema de validación con Pydantic para la configuración del motor de visión.

Asegura que los umbrales de confianza, mapeo de articulaciones y reglas de
visualización se inyecten correctamente desde un archivo .json hacia el motor
de visión, eliminando el hardcode.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel, Field


class ConfidenceThresholdsSchema(BaseModel):
    """Umbrales de confianza para detección de personas y estimación de pose."""
    yolox_nms_thr: float = Field(0.45, ge=0.0, le=1.0)
    yolox_score_thr: float = Field(0.25, ge=0.0, le=1.0)
    min_keypoint_confidence: float = Field(0.30, ge=0.0, le=1.0)
    min_face_keypoint_confidence: float = Field(0.40, ge=0.0, le=1.0)
    min_face_points_present: int = Field(2, ge=1, le=10)
    joint_reliable_threshold: float = Field(0.50, ge=0.0, le=1.0)


class JointMappingSchema(BaseModel):
    """Mapeo de índices anatómicos para RTMPose WholeBody-133 (incluyendo nudillos MCP)."""
    left_chain: List[int] = Field(default_factory=lambda: [5, 7, 9, 96, 11, 13, 15, 17])
    right_chain: List[int] = Field(default_factory=lambda: [6, 8, 10, 117, 12, 14, 16, 18])
    face_landmarks: List[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4])
    chin_index: int = Field(32, ge=0, le=132)
    left_wrist: int = Field(9, ge=0, le=132)
    right_wrist: int = Field(10, ge=0, le=132)
    left_mcp: int = Field(96, ge=0, le=132)
    right_mcp: int = Field(117, ge=0, le=132)


class VisualizationRulesSchema(BaseModel):
    """Reglas y parámetros visuales para renderizado por excepción con OpenCV."""
    skeleton_kpt_thr: float = Field(0.30, ge=0.0, le=1.0)
    skeleton_radius: int = Field(3, ge=1, le=10)
    skeleton_line_width: int = Field(2, ge=1, le=10)
    card_opacity: float = Field(0.85, ge=0.0, le=1.0)
    f2_badge_opacity: float = Field(0.88, ge=0.0, le=1.0)
    reba_color_map: Dict[str, List[int]] = Field(
        default_factory=lambda: {
            "VERDE": [46, 204, 113],
            "AMARILLO": [0, 215, 255],
            "NARANJA": [0, 140, 255],
            "ROJO": [40, 40, 230],
            "CRITICO": [142, 36, 170],
        }
    )
    reach_zone_radii_mm: Dict[str, float] = Field(
        default_factory=lambda: {
            "zona_1": 300.0,
            "zona_2": 400.0,
            "zona_3": 500.0,
            "zona_4": 750.0,
        }
    )


class VisionConfigSchema(BaseModel):
    """Contenedor raíz del esquema de visión inyectado desde JSON."""
    title: str = "ErgoAI Vision Pipeline Configuration"
    description: Optional[str] = None
    confidence_thresholds: ConfidenceThresholdsSchema = Field(default_factory=ConfidenceThresholdsSchema)
    joint_mapping: JointMappingSchema = Field(default_factory=JointMappingSchema)
    visualization_rules: VisualizationRulesSchema = Field(default_factory=VisualizationRulesSchema)

    @classmethod
    def load_from_json(cls, json_path: Optional[Path] = None) -> VisionConfigSchema:
        """Carga y valida el archivo JSON de configuración mediante Pydantic."""
        if json_path is None:
            # Buscar en directorios estándar del proyecto
            base_dir = Path(__file__).resolve().parent.parent.parent.parent
            candidates = [
                base_dir / "configs" / "vision_config.json",
                base_dir / "src" / "ergoai" / "config" / "vision_config.json",
                Path("configs/vision_config.json"),
            ]
            for c in candidates:
                if c.exists():
                    json_path = c
                    break

        if json_path and json_path.exists():
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls.model_validate(data)

        # Si no existe archivo físico en disco, genera la configuración por defecto validada
        return cls()

