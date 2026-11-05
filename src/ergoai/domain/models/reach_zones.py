"""Modelos tipados para Zonas de Alcance digitalizadas según estándar Jabil (16-PE30-6500-00023)."""

from enum import IntEnum
from typing import Optional
from pydantic import BaseModel, Field


class ZoneClassification(IntEnum):
    """Clasificación de Zonas de Alcance (1 a 5)."""
    ZONE_1 = 1
    ZONE_2 = 2
    ZONE_3 = 3
    ZONE_4 = 4
    ZONE_5 = 5


class ReachPointEvaluation(BaseModel):
    """Evaluación de un punto de toma o liberación de material en el plano horizontal (Vista Aérea)."""
    point_name: str = Field(..., description="Nombre del objeto, herramienta o componente")
    x_px: float = Field(..., description="Coordenada X en píxeles")
    y_px: float = Field(..., description="Coordenada Y en píxeles")
    dx_mm: float = Field(..., description="Distancia lateral absoluta respecto al eje central en mm")
    dy_mm: float = Field(..., description="Distancia frontal hacia adelante respecto a los hombros en mm")
    r_mm: float = Field(..., description="Distancia radial polar desde el punto medio del torso en mm")
    alpha_deg: float = Field(..., description="Ángulo de apertura polar respecto al frente en grados (0° = al frente)")
    zone: ZoneClassification = Field(..., description="Zona asignada (1 a 5)")
    frequency_per_piece: float = Field(default=1.0, description="Frecuencia de manipulación por pieza terminada")
    is_compliant: bool = Field(..., description="True si la ubicación cumple con las reglas ergonómicas de uso")
    action_required: Optional[str] = Field(
        default=None,
        description="Acción correctiva requerida si la ubicación es no conforme (ej. mover a Zona 1 o 2)"
    )

