"""
Motor de Persistencia Atómica en Sistema de Archivos y Trazabilidad Criptográfica.
Implementa el patrón Write-Replace para garantizar integridad sin motor de base de datos.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.app.settings import WORKSPACE_DIR
from backend.app.session_store.models import (
    AuditActionEnum,
    AuditEvent,
    AuditTrailDocument,
    RecommendationSnapshot,
    SessionStateDocument,
)


CASE_ID_RE = re.compile(r"[A-Za-z0-9_-]{1,64}")


class AuditIntegrityError(Exception):
    """Excepción lanzada cuando se detecta corrupción o manipulación no autorizada en el historial."""
    pass


class AuditFileManager:
    """
    Gestor de archivos de sesión y auditoría inmutable basado en el sistema de archivos local.
    Satisface la restricción 'Cero Base de Datos' de la Rúbrica Track 4 X-RAIC.
    """

    DEFAULT_WORKSPACE_DIR = WORKSPACE_DIR

    def __init__(self, workspace_root: Optional[Path] = None):
        self.workspace_root = Path(workspace_root or self.DEFAULT_WORKSPACE_DIR)
        self._locks: Dict[str, threading.RLock] = {}
        self._global_lock = threading.Lock()

    def _get_case_lock(self, case_id: str) -> threading.RLock:
        """Obtiene o inicializa un RLock por caso para permitir reentrancia segura en el mismo hilo."""
        with self._global_lock:
            if case_id not in self._locks:
                self._locks[case_id] = threading.RLock()
            return self._locks[case_id]

    def get_case_dir(self, case_id: str) -> Path:
        """Retorna la ruta al directorio de un caso. Rechaza IDs que podrían salir del workspace."""
        if not CASE_ID_RE.fullmatch(case_id or ""):
            raise ValueError(f"case_id inválido: {case_id!r}")
        return self.workspace_root / case_id

    def init_case_workspace(self, case_id: str) -> Path:
        """
        Inicializa la estructura de directorios de un caso si no existe.
        Crea subdirectorios de inputs, outputs y archivos base de auditoría.
        """
        case_dir = self.get_case_dir(case_id)
        case_dir.mkdir(parents=True, exist_ok=True)
        (case_dir / "inputs").mkdir(exist_ok=True)
        (case_dir / "outputs").mkdir(exist_ok=True)

        audit_path = case_dir / "audit_trail.json"
        if not audit_path.exists():
            initial_doc = AuditTrailDocument(case_id=case_id)
            self._write_atomic(audit_path, initial_doc.model_dump(mode="json"))

        state_path = case_dir / "session_state.json"
        if not state_path.exists():
            initial_state = SessionStateDocument(case_id=case_id)
            self._write_atomic(state_path, initial_state.model_dump(mode="json"))

        return case_dir

    def write_json_atomic(self, target_path: Path, data: Any) -> None:
        """Escritura atómica pública para otros documentos del workspace (caso, bitácora, alertas)."""
        self._write_atomic(target_path, data)

    def _write_atomic(self, target_path: Path, data: Any) -> None:
        """
        Escribe un archivo JSON usando el patrón atómico Write-Replace.
        1. Escribe en archivo temporal en el mismo directorio.
        2. Fuerza flush y fsync del descriptor a disco.
        3. Realiza os.replace (operación atómica garantizada a nivel POSIX).
        """
        target_path.parent.mkdir(parents=True, exist_ok=True)
        temp_file = tempfile.NamedTemporaryFile(
            mode="w",
            dir=str(target_path.parent),
            prefix=f"{target_path.name}.tmp_",
            delete=False,
            encoding="utf-8"
        )
        try:
            with temp_file:
                json.dump(data, temp_file, indent=2, ensure_ascii=False)
                temp_file.flush()
                os.fsync(temp_file.fileno())
            os.replace(temp_file.name, target_path)
        except BaseException:
            # El archivo ya está cerrado (with); en Windows no se puede borrar uno abierto.
            Path(temp_file.name).unlink(missing_ok=True)
            raise

    def load_audit_trail(self, case_id: str, verify: bool = True) -> AuditTrailDocument:
        """
        Carga el documento de auditoría desde disco y opcionalmente verifica su integridad.
        """
        with self._get_case_lock(case_id):
            audit_path = self.get_case_dir(case_id) / "audit_trail.json"
            if not audit_path.exists():
                self.init_case_workspace(case_id)

            with open(audit_path, "r", encoding="utf-8") as f:
                content = json.load(f)

            doc = AuditTrailDocument.model_validate(content)
            if verify:
                is_valid, error_msg = doc.verify_integrity()
                if not is_valid:
                    raise AuditIntegrityError(
                        f"Integridad de auditoría comprometida en '{case_id}': {error_msg}"
                    )
            return doc

    def save_audit_trail(self, case_id: str, doc: AuditTrailDocument) -> None:
        """Guarda atómicamente el documento de auditoría en disco tras validar su integridad."""
        is_valid, error_msg = doc.verify_integrity()
        if not is_valid:
            raise AuditIntegrityError(
                f"No se puede persistir auditoría con integridad rota en '{case_id}': {error_msg}"
            )
        with self._get_case_lock(case_id):
            audit_path = self.get_case_dir(case_id) / "audit_trail.json"
            self._write_atomic(audit_path, doc.model_dump(mode="json"))

    def append_audit_event(
        self,
        case_id: str,
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
        """
        Agrega atómicamente un nuevo evento de auditoría al caso especificado.
        Calcula el hash SHA-256 encadenado y persiste inmediatamente a disco.
        """
        with self._get_case_lock(case_id):
            doc = self.load_audit_trail(case_id, verify=True)
            event = doc.append_event(
                event_id=event_id,
                specialist_id=specialist_id,
                action=action,
                target_recommendation_id=target_recommendation_id,
                original_ai_recommendation=original_ai_recommendation,
                human_edited_recommendation=human_edited_recommendation,
                initial_risk_score=initial_risk_score,
                residual_risk_score=residual_risk_score,
                timestamp_utc=timestamp_utc,
            )
            audit_path = self.get_case_dir(case_id) / "audit_trail.json"
            self._write_atomic(audit_path, doc.model_dump(mode="json"))
            return event

    def verify_case_audit_integrity(self, case_id: str) -> tuple[bool, Optional[str]]:
        """Verifica la cadena de custodia y los hashes de un caso sin arrojar excepción."""
        try:
            self.load_audit_trail(case_id, verify=True)
            return True, None
        except AuditIntegrityError as e:
            return False, str(e)
        except Exception as e:
            return False, f"Error de lectura o parseo: {e}"

    def load_session_state(self, case_id: str) -> SessionStateDocument:
        """Carga el snapshot del estado de sesión actual para el caso dado."""
        with self._get_case_lock(case_id):
            state_path = self.get_case_dir(case_id) / "session_state.json"
            if not state_path.exists():
                self.init_case_workspace(case_id)
            with open(state_path, "r", encoding="utf-8") as f:
                content = json.load(f)
            return SessionStateDocument.model_validate(content)

    def save_session_state(self, case_id: str, state: SessionStateDocument) -> None:
        """Guarda atómicamente el estado de sesión actual."""
        with self._get_case_lock(case_id):
            state_path = self.get_case_dir(case_id) / "session_state.json"
            self._write_atomic(state_path, state.model_dump(mode="json"))

    def list_cases(self) -> List[str]:
        """Lista todos los casos inicializados en el workspace actual."""
        if not self.workspace_root.exists():
            return []
        return sorted([
            d.name for d in self.workspace_root.iterdir()
            if d.is_dir() and (d / "audit_trail.json").exists()
        ])
