"""Modelos tipados para ángulos biomecánicos y discrepancias posturales."""

from enum import Enum
try:
    from enum import StrEnum
except ImportError:
    class StrEnum(str, Enum):
        pass
from typing import Optional
from pydantic import BaseModel, Field


class ActiveSide(StrEnum):
    """Hemisferio corporal evaluado en la vista lateral."""
    LEFT = "left"
    RIGHT = "right"
    BOTH = "both"


class BiomechanicalAngles(BaseModel):
    """Ángulos articulares calculados a partir de las coordenadas geométricas."""
    active_side: ActiveSide = Field(default=ActiveSide.RIGHT, description="Hemisferio activo seleccionado")
    
    # Tronco
    trunk_angle: float = Field(..., ge=0.0, le=180.0, description="Ángulo del tronco respecto a la vertical en grados")
    trunk_is_extension: bool = Field(default=False, description="True si la postura del tronco está en extensión")
    trunk_twisted: bool = Field(default=False, description="True si existe torsión axial del tronco")
    trunk_side_bending: bool = Field(default=False, description="True si existe flexión lateral del tronco")

    # Cuello
    neck_angle: float = Field(..., ge=0.0, le=180.0, description="Ángulo del cuello respecto al tronco en grados")
    neck_is_extension: bool = Field(default=False, description="True si el cuello está en extensión")
    neck_twisted: bool = Field(default=False, description="True si existe torsión del cuello")
    neck_side_bending: bool = Field(default=False, description="True si existe inclinación lateral del cuello")
    neck_needs_human_review: bool = Field(
        default=False,
        description="True si la imagen viene sin rostro y requiere confirmación o ajuste por especialista"
    )

    # Piernas
    leg_knee_angle: float = Field(default=0.0, ge=0.0, le=180.0, description="Ángulo de flexión de rodilla en grados")
    leg_bilateral_support: bool = Field(default=True, description="True si hay apoyo bilateral simétrico o sentado")
    leg_unilateral_or_unstable: bool = Field(default=False, description="True si el apoyo es unilateral o base inestable")

    # Brazo / Hombro
    upper_arm_angle: float = Field(..., ge=0.0, le=180.0, description="Ángulo del brazo respecto al torso en grados")
    upper_arm_is_extension: bool = Field(default=False, description="True si el brazo está en extensión posterior")
    upper_arm_abducted: bool = Field(default=False, description="True si existe abducción del hombro (>20° coronal)")
    shoulder_elevated: bool = Field(default=False, description="True si el hombro está encogido o elevado")
    arm_supported_or_gravity_assisted: bool = Field(
        default=False,
        description="True si el brazo cuenta con apoyo mecánico o gravedad a favor (-1 REBA)"
    )

    # Antebrazo / Codo
    lower_arm_angle: float = Field(..., ge=0.0, le=180.0, description="Ángulo de flexión del codo en grados")

    # Muñeca
    wrist_angle: float = Field(default=0.0, ge=0.0, le=180.0, description="Ángulo de flexión/extensión de muñeca")
    wrist_twisted_or_deviated: bool = Field(default=False, description="True si hay torsión o desviación cubital/radial")

    # Métrica derivada
    pickup_height_m: Optional[float] = Field(default=None, description="Altura estimada de la mano al piso en metros")


class AngularDiscrepancy(BaseModel):
    """Reporte de discrepancia entre una evaluación manual histórica y la medición objetiva."""
    joint_name: str = Field(..., description="Articulación evaluada (Tronco, Cuello, Brazo, Antebrazo, etc.)")
    recorded_angle: float = Field(..., description="Ángulo registrado manualmente en piso")
    estimated_angle: float = Field(..., description="Ángulo calculado objetivamente por visión/geometría")
    tolerance_deg: float = Field(default=5.0, description="Tolerancia aceptable en grados")
    discrepancy_deg: float = Field(..., description="Diferencia absoluta en grados")
    is_discrepant: bool = Field(..., description="True si la diferencia excede la tolerancia permitida")
    is_underestimated: bool = Field(..., description="True si la evaluación manual subestimó la postura real")

