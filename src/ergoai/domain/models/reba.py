"""Modelos tipados para la evaluación ergonómica según el Método REBA."""

from enum import IntEnum, Enum
try:
    from enum import StrEnum
except ImportError:
    class StrEnum(str, Enum):
        pass
from pydantic import BaseModel, Field


class REBARiskLevel(IntEnum):
    """Niveles de riesgo ergonómico estandarizados por el método REBA."""
    NEGLIGIBLE = 0  # Puntaje 1: Inapreciable
    LOW = 1         # Puntaje 2-3: Bajo
    MEDIUM = 2      # Puntaje 4-7: Medio
    HIGH = 3        # Puntaje 8-10: Alto
    VERY_HIGH = 4   # Puntaje 11-15: Muy Alto


class REBAGroupAScore(BaseModel):
    """Puntuaciones intermedias del Grupo A: Tronco, Cuello, Piernas y Carga/Fuerza."""
    trunk_raw_score: int = Field(..., ge=1, le=5, description="Puntaje de tronco ajustado")
    neck_raw_score: int = Field(..., ge=1, le=3, description="Puntaje de cuello ajustado")
    legs_raw_score: int = Field(..., ge=1, le=4, description="Puntaje de piernas ajustado")
    table_a_score: int = Field(..., ge=1, le=9, description="Puntaje cruzado obtenido en Tabla A")
    load_score: int = Field(..., ge=0, le=3, description="Ajuste por carga o fuerza (<5kg: 0, 5-10kg: +1, >10kg: +2, impacto: +1)")
    score_a: int = Field(..., ge=1, le=12, description="Puntuación total A = Tabla A + Carga")


class REBAGroupBScore(BaseModel):
    """Puntuaciones intermedias del Grupo B: Brazos, Antebrazos, Muñecas y Agarre."""
    upper_arm_raw_score: int = Field(..., ge=1, le=6, description="Puntaje de brazo/hombro ajustado")
    lower_arm_raw_score: int = Field(..., ge=1, le=2, description="Puntaje de antebrazo/codo ajustado")
    wrist_raw_score: int = Field(..., ge=1, le=3, description="Puntaje de muñeca ajustado")
    table_b_score: int = Field(..., ge=1, le=9, description="Puntaje cruzado obtenido en Tabla B")
    coupling_score: int = Field(..., ge=0, le=3, description="Puntuación por acoplamiento de agarre (0=Bueno, 1=Regular, 2=Malo, 3=Inaceptable)")
    score_b: int = Field(..., ge=1, le=12, description="Puntuación total B = Tabla B + Agarre")


class REBAActivityScore(BaseModel):
    """Puntuación por factores de actividad biomecánica repetitiva o estática."""
    is_static: bool = Field(default=False, description="+1 si una o más partes permanecen estáticas > 1 min")
    is_repetitive: bool = Field(default=False, description="+1 si hay movimientos repetitivos (> 4 veces/min)")
    is_rapid_change_or_unstable: bool = Field(default=False, description="+1 si hay cambios posturales importantes o base inestable")
    activity_score: int = Field(default=0, ge=0, le=3, description="Suma de puntos por actividad (0 a 3)")


class REBAAssessment(BaseModel):
    """Resultado integral de la auditoría ergonómica por el Método REBA."""
    group_a: REBAGroupAScore
    group_b: REBAGroupBScore
    table_c_score: int = Field(..., ge=1, le=12, description="Puntaje cruzado de Score A x Score B en Tabla C")
    activity: REBAActivityScore
    final_score: int = Field(..., ge=1, le=15, description="Puntaje final REBA (1 a 15)")
    risk_level: REBARiskLevel = Field(..., description="Nivel de riesgo asociado (0 a 4)")
    action_urgency: str = Field(..., description="Prioridad y urgencia de actuación ergonómica")
    color_code: str = Field(..., description="Código semafórico: VERDE, AMARILLO, NARANJA, ROJO o CRITICO")

