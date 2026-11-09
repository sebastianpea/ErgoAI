"""
Paquete session_store: Persistencia Ligera y Trazabilidad sin Base de Datos.
Cumple con la restricción 'Cero Base de Datos' de la Rúbrica Track 4 X-RAIC / Jabil.
"""

from backend.app.session_store.models import (
    AuditActionEnum,
    ControlHierarchyEnum,
    SessionStatusEnum,
    RecommendationSnapshot,
    AuditEvent,
    AuditTrailDocument,
    SessionStateDocument,
)
from backend.app.session_store.audit_file_manager import (
    AuditFileManager,
    AuditIntegrityError,
)
from backend.app.session_store.bitacora_ledger import (
    BitacoraLedger,
    EntradaBitacora,
    ResultadoVerificacion,
)
from backend.app.session_store.config_loader import (
    NormativeConfigLoader,
    ConfigLoadError,
    default_config_loader,
)

__all__ = [
    "AuditActionEnum",
    "ControlHierarchyEnum",
    "SessionStatusEnum",
    "RecommendationSnapshot",
    "AuditEvent",
    "AuditTrailDocument",
    "SessionStateDocument",
    "AuditFileManager",
    "AuditIntegrityError",
    "BitacoraLedger",
    "EntradaBitacora",
    "ResultadoVerificacion",
    "NormativeConfigLoader",
    "ConfigLoadError",
    "default_config_loader",
]
