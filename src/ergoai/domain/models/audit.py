"""Modelos de resultados de reglas, semáforo global y bitácora inmutable de trazabilidad (Audit Log)."""

from typing import Optional
from pydantic import BaseModel, Field
from ergoai.domain.models.workstation import RuleStatus, RuleOrigin


class RuleEvaluationResult(BaseModel):
    """Resultado individual de una regla evaluada sobre la estación."""
    id_estacion: str = Field(..., description="Identificador de la estación evaluada")
    regla: str = Field(..., description="Identificador de la regla (ej. B1, D2, F1)")
    estado: RuleStatus = Field(..., description="Resultado normativo: CONFORME, NO CONFORME, etc.")
    valor_medido: str = Field(..., description="Valor o condición observada")
    limite: str = Field(..., description="Límite o umbral normativo")
    referencia_doc: str = Field(..., description="Sección o párrafo de la instrucción oficial")
    origen: RuleOrigin = Field(..., description="DOC o SUPUESTO")
    accion: str = Field(..., description="Acción correctiva o preventiva recomendada")
    responsable: str = Field(..., description="Rol o departamento responsable de la mitigación")
    documentos_requeridos: list[str] = Field(default_factory=list, description="Formatos, checklists o MOC requeridos")
    fecha_deteccion: str = Field(..., description="Fecha de detección en formato ISO YYYY-MM-DD")
    dias_abierto: int = Field(default=0, ge=0, description="Días transcurridos desde la detección inicial")


class GlobalStationResult(BaseModel):
    """Dictamen consolidado de una estación con semáforo global y priorización de acciones."""
    id_estacion: str
    estado_global: RuleStatus = Field(..., description="VERDE, AMARILLO, ROJO o CRITICO")
    reglas_evaluadas: list[RuleEvaluationResult] = Field(default_factory=list)
    fallas: list[RuleEvaluationResult] = Field(default_factory=list)
    datos_faltantes: list[RuleEvaluationResult] = Field(default_factory=list)
    acciones_priorizadas: list[str] = Field(default_factory=list)


class AuditLogEntry(BaseModel):
    """Entrada inmutable en la bitácora de auditoría para trazabilidad estricta sin base de datos externa."""
    entry_id: str = Field(..., description="Identificador único del registro de auditoría")
    timestamp_iso: str = Field(..., description="Marca de tiempo ISO-8601 del evento")
    specialist_user_id: str = Field(..., description="Identificador del ergónomo o especialista que valida/modifica")
    id_estacion: str = Field(..., description="Identificador de la estación")
    action_type: str = Field(..., description="Tipo de acción: APROBACION, EDICION_ANGULO, RECHAZO, OVERRIDE")
    field_name: str = Field(..., description="Campo o parámetro afectado")
    previous_value: str = Field(..., description="Valor anterior a la intervención humana")
    new_value: str = Field(..., description="Nuevo valor fijado o confirmado")
    justification: str = Field(..., description="Justificación técnica de la decisión humana")
    is_blocking_approved: bool = Field(default=True, description="True si la aprobación desbloquea el pase a piso")

