"""
Modelos de Datos y Esquemas Tipados para el Módulo de Persistencia y Auditoría.
Restricción: Cero dependencias de motores de Base de Datos (cumplimiento Rúbrica Track 4).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, ClassVar, Dict, List, Optional
from pydantic import BaseModel, Field


class AuditActionEnum(str, Enum):
    APPROVED = "APPROVED"
    EDITED = "EDITED"
    REJECTED = "REJECTED"
    CREATED = "CREATED"          # recomendación redactada por el especialista
    AUTHORIZED = "AUTHORIZED"    # ingeniería autoriza un cambio en planta
    DENIED = "DENIED"            # ingeniería deniega un cambio en planta
    IMPLEMENTED = "IMPLEMENTED"  # el cambio se ejecutó en piso


class ControlHierarchyEnum(str, Enum):
    INGENIERIA = "INGENIERIA"
    ADMINISTRATIVO = "ADMINISTRATIVO"


class SessionStatusEnum(str, Enum):
    PENDING_ANALYSIS = "PENDING_ANALYSIS"
    IN_REVIEW = "IN_REVIEW"
    VALIDATED = "VALIDATED"
    FINALIZED = "FINALIZED"


class RecommendationSnapshot(BaseModel):
    """Snapshot del contenido de una recomendación ergonómica."""
    recommendation_id: str = Field(..., description="Identificador único de la recomendación (ej. REC-01)")
    hierarchy: ControlHierarchyEnum = Field(..., description="Prioridad: INGENIERIA o ADMINISTRATIVO")
    description: str = Field(..., min_length=5, description="Descripción técnica de la acción ergonómica")
    projected_reba: Optional[int] = Field(None, ge=1, le=15, description="Puntaje REBA esperado tras la acción")
    justification: Optional[str] = Field(None, description="Justificación obligatoria en caso de edición o rechazo")


class AuditEvent(BaseModel):
    """
    Evento de auditoría individual inmutable con soporte de hash chaining (SHA-256).
    Registra toda interacción Human-in-the-Loop del especialista.
    """
    event_id: str = Field(..., description="Identificador único del evento")
    timestamp_utc: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Marca de tiempo UTC en formato ISO 8601"
    )
    specialist_id: str = Field(..., min_length=3, description="Identificador o nómina del especialista de EHS/IE")
    action: AuditActionEnum = Field(..., description="Acción realizada: APPROVED, EDITED o REJECTED")
    target_recommendation_id: str = Field(..., description="ID de la recomendación intervenida")
    original_ai_recommendation: RecommendationSnapshot = Field(
        ..., description="Propuesta original generada por la IA"
    )
    human_edited_recommendation: Optional[RecommendationSnapshot] = Field(
        None, description="Contenido final editado o aprobado por el especialista"
    )
    initial_risk_score: int = Field(..., ge=1, le=15, description="Puntuación REBA inicial del caso")
    residual_risk_score: int = Field(..., ge=1, le=15, description="Puntuación REBA residual recalculada")
    previous_event_hash: str = Field(
        ..., description="Hash SHA-256 del evento previo o GENESIS_BLOCK si es el primero"
    )
    event_hash: str = Field(
        default="", description="Digest SHA-256 del evento para garantizar inmutabilidad"
    )

    def canonical_payload_dict(self) -> Dict[str, Any]:
        """Genera el diccionario canónico excluyendo el campo event_hash para calcular la firma."""
        return {
            "event_id": self.event_id,
            "timestamp_utc": self.timestamp_utc,
            "specialist_id": self.specialist_id,
            "action": self.action.value,
            "target_recommendation_id": self.target_recommendation_id,
            "original_ai_recommendation": self.original_ai_recommendation.model_dump(mode="json"),
            "human_edited_recommendation": (
                self.human_edited_recommendation.model_dump(mode="json")
                if self.human_edited_recommendation else None
            ),
            "initial_risk_score": self.initial_risk_score,
            "residual_risk_score": self.residual_risk_score,
            "previous_event_hash": self.previous_event_hash,
        }

    def compute_hash(self) -> str:
        """Calcula el hash SHA-256 canónico determinista del evento."""
        payload_json = json.dumps(self.canonical_payload_dict(), sort_keys=True, ensure_ascii=True)
        return hashlib.sha256(payload_json.encode("utf-8")).hexdigest()

    def seal(self) -> AuditEvent:
        """Sella criptográficamente el evento calculando y asignando su event_hash."""
        self.event_hash = self.compute_hash()
        return self

    def verify_event_integrity(self) -> bool:
        """Valida que el hash registrado coincida con el contenido actual del evento."""
        return bool(self.event_hash and self.event_hash == self.compute_hash())


class AuditTrailDocument(BaseModel):
    """
    Documento completo de auditoría para un caso de estudio (audit_trail.json).
    Implementa un libro inmutable encadenado (Hash Chain).
    """
    # ClassVar: constante del esquema. Como campo Pydantic se serializaba al JSON y
    # un archivo alterado podía redefinir el bloque génesis contra el que se verifica.
    GENESIS_HASH: ClassVar[str] = "0" * 64

    case_id: str = Field(..., description="Identificador del caso Jabil (ej. caso_01_levantamiento)")
    created_at_utc: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Fecha y hora de creación del expediente"
    )
    audit_trail_version: str = Field("1.0.0", description="Versión del esquema de auditoría")
    events: List[AuditEvent] = Field(default_factory=list, description="Secuencia cronológica de eventos")

    def get_latest_hash(self) -> str:
        """Devuelve el hash del último evento registrado o el bloque génesis si está vacío."""
        if not self.events:
            return self.GENESIS_HASH
        return self.events[-1].event_hash

    def append_event(
        self,
        event_id: str,
        specialist_id: str,
        action: AuditActionEnum,
        target_recommendation_id: str,
        original_ai_recommendation: RecommendationSnapshot,
        initial_risk_score: int,
        residual_risk_score: int,
        human_edited_recommendation: Optional[RecommendationSnapshot] = None,
        timestamp_utc: Optional[str] = None,
    ) -> AuditEvent:
        """Agrega un nuevo evento al registro calculando automáticamente la cadena de hashes."""
        if any(e.event_id == event_id for e in self.events):
            raise ValueError(f"event_id duplicado en '{self.case_id}': {event_id}")
        prev_hash = self.get_latest_hash()
        event_data: Dict[str, Any] = {
            "event_id": event_id,
            "specialist_id": specialist_id,
            "action": action,
            "target_recommendation_id": target_recommendation_id,
            "original_ai_recommendation": original_ai_recommendation,
            "human_edited_recommendation": human_edited_recommendation,
            "initial_risk_score": initial_risk_score,
            "residual_risk_score": residual_risk_score,
            "previous_event_hash": prev_hash,
            "event_hash": "",
        }
        if timestamp_utc:
            event_data["timestamp_utc"] = timestamp_utc

        event = AuditEvent(**event_data)
        event.seal()
        self.events.append(event)
        return event

    def verify_integrity(self) -> tuple[bool, Optional[str]]:
        """
        Verifica exhaustivamente la integridad del documento y la cadena de hashes.
        Retorna (True, None) si es válido, o (False, detalle_error) si está comprometido.
        """
        expected_prev_hash = self.GENESIS_HASH
        for idx, event in enumerate(self.events):
            if event.previous_event_hash != expected_prev_hash:
                return False, (
                    f"Ruptura de cadena en evento índice {idx} ({event.event_id}): "
                    f"previous_event_hash esperado '{expected_prev_hash}', encontrado '{event.previous_event_hash}'"
                )
            if not event.verify_event_integrity():
                return False, (
                    f"Hash inválido o alteración detectada en evento índice {idx} ({event.event_id}): "
                    f"registrado '{event.event_hash}', calculado '{event.compute_hash()}'"
                )
            expected_prev_hash = event.event_hash
        return True, None


class SessionStateDocument(BaseModel):
    """
    Snapshot del estado actual de evaluación para un caso (session_state.json).
    Permite restaurar el estado en memoria sin depender de base de datos.
    """
    case_id: str = Field(..., description="ID del caso de estudio")
    updated_at_utc: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Marca de tiempo de la última actualización"
    )
    status: SessionStatusEnum = Field(
        default=SessionStatusEnum.PENDING_ANALYSIS,
        description="Estado del ciclo de vida del caso"
    )
    measured_angles: Dict[str, float] = Field(
        default_factory=dict,
        description="Ángulos articulares calculados por visión (cuello, tronco, brazos, etc.)"
    )
    reba_initial_score: Optional[int] = Field(None, ge=1, le=15)
    reba_initial_risk_level: Optional[str] = Field(None)
    reba_initial_action_level: Optional[str] = Field(None)
    nom036_alerts: List[str] = Field(default_factory=list)
    recommendations: List[Dict[str, Any]] = Field(default_factory=list)
    residual_risk_score: Optional[int] = Field(None, ge=1, le=15)
    specialist_id: Optional[str] = Field(None)
    is_validated_by_human: bool = Field(
        default=False,
        description="Bandera bloqueante: True únicamente cuando el especialista aprueba formalmente"
    )
