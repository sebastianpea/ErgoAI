"""Modelos tipados para el simulador de riesgo residual y controles de ingeniería NOM-036-1."""

from enum import Enum
try:
    from enum import StrEnum
except ImportError:
    class StrEnum(str, Enum):
        pass
from typing import Optional
from pydantic import BaseModel, Field


class EngineeringControlID(StrEnum):
    """Controles de ingeniería parametrizados según jerarquía NOM-036 y estándar Jabil."""
    B1_LIFTER = "B1_LIFTER"                            # Asistencia mecánica / lifter para carga > 14 kg
    B4_LOWER_PICKUP = "B4_LOWER_PICKUP"                # Bajar punto de toma en rack (<=1.7m) o tarima/carro (<=1.6m)
    E1_RELOCATE_ZONE = "E1_RELOCATE_ZONE"              # Mover material/herramienta a Zona 1 o 2 (<= 400 mm)
    F1_HEIGHT_ADJUST = "F1_HEIGHT_ADJUST"              # Ajuste de mesa a rango ergonómico 95-125 cm
    TOOL_CHANGE_ERGONOMIC = "TOOL_CHANGE_ERGONOMIC"    # Herramienta con empuñadura ergonómica / balanceador (muñeca neutra <= 15°)
    SIT_STAND_ALTERNATION = "SIT_STAND_ALTERNATION"    # Alternancia postural sentado-de pie y tapete antifatiga (NOM-036)
    C1_D3_ESD_CHAIR = "C1_D3_ESD_CHAIR"                # Dotar silla estándar ESD y pausas activas (Ley Silla)


class ActionStatus(StrEnum):
    """Ciclo de vida Human-in-the-Loop para acciones de mejora ergonómica."""
    PROPUESTA_PENDIENTE = "PROPUESTA_PENDIENTE"
    VALIDADA_POR_ESPECIALISTA = "VALIDADA_POR_ESPECIALISTA"
    APROBADA_PARA_PISO = "APROBADA_PARA_PISO"
    RECHAZADA_CON_JUSTIFICACION = "RECHAZADA_CON_JUSTIFICACION"


class EngineeringControlProposal(BaseModel):
    """Propuesta de ingeniería para mitigar el riesgo postural detectado."""
    control_id: EngineeringControlID
    priority: int = Field(default=1, description="1: Control de Ingeniería / Rediseño Físico, 2: Control Administrativo")
    title: str = Field(..., description="Título resumido de la intervención")
    description: str = Field(..., description="Detalle del rediseño biomecánico propuesto")
    nom036_clause: str = Field(default="NOM-036-1-STPS-2018", description="Referencia a la norma federal o corporativa")
    validated_by_specialist: bool = Field(default=False, description="True si fue revisado por el especialista")
    approved_by_specialist: bool = Field(default=False, description="True si fue aprobado para implementación")
    specialist_notes: Optional[str] = Field(default=None, description="Observaciones y directrices del especialista")


class ResidualRiskComparison(BaseModel):
    """Comparativa determinista antes vs después de la intervención de ingeniería."""
    initial_reba_score: int = Field(..., ge=1, le=15, description="Puntuación REBA previa a la intervención")
    initial_risk_level: str = Field(..., description="Nivel de riesgo inicial")
    applied_controls: list[EngineeringControlID] = Field(default_factory=list, description="Controles de ingeniería simulados")
    residual_reba_score: int = Field(..., ge=1, le=15, description="Puntuación REBA proyectada tras la mitigación")
    residual_risk_level: str = Field(..., description="Nivel de riesgo residual proyectado")
    score_delta: int = Field(..., description="Reducción neta de puntos REBA")
    risk_reduction_pct: float = Field(..., ge=0.0, le=100.0, description="Porcentaje de reducción de severidad ergonómica")
    validated_by_specialist: bool = Field(default=False, description="Invariante: True sólo si cuenta con firma del especialista")
    can_pass_to_floor: bool = Field(default=False, description="Invariante: Paso bloqueante a piso")

