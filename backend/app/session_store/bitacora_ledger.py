"""
Bitácora global de solo inserción (workspace/bitacora.json) con encadenamiento SHA-256.
Registra todas las acciones del sistema y del especialista (puntos corregidos, decisiones,
alertas). Complementa el audit_trail.json por caso, que guarda el detalle de cada decisión.
"""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import ClassVar, List, Optional

from pydantic import BaseModel, Field

from backend.app.session_store.audit_file_manager import AuditFileManager, AuditIntegrityError


class EntradaBitacora(BaseModel):
    GENESIS_HASH: ClassVar[str] = "0" * 64

    secuencia: int = Field(ge=1)
    timestamp: str
    usuario: str
    accion: str
    objetivo: str
    id_caso: Optional[str] = None
    antes: Optional[str] = None
    despues: Optional[str] = None
    motivo: Optional[str] = None
    hash: str = ""
    hash_anterior: str

    def calcular_hash(self) -> str:
        datos = self.model_dump(mode="json", exclude={"hash"})
        return hashlib.sha256(
            json.dumps(datos, sort_keys=True, ensure_ascii=True).encode("utf-8")
        ).hexdigest()


class ResultadoVerificacion(BaseModel):
    ok: bool
    total: int
    primera_falla: Optional[int] = None
    detalle: Optional[str] = None


class BitacoraLedger:
    NOMBRE_ARCHIVO = "bitacora.json"

    def __init__(self, mgr: AuditFileManager):
        self.mgr = mgr
        self._lock = threading.RLock()

    @property
    def ruta(self) -> Path:
        return self.mgr.workspace_root / self.NOMBRE_ARCHIVO

    def _leer(self) -> List[EntradaBitacora]:
        if not self.ruta.exists():
            return []
        with open(self.ruta, "r", encoding="utf-8") as f:
            return [EntradaBitacora.model_validate(e) for e in json.load(f)]

    @staticmethod
    def _verificar_entradas(entradas: List[EntradaBitacora]) -> ResultadoVerificacion:
        anterior = EntradaBitacora.GENESIS_HASH
        for i, e in enumerate(entradas, start=1):
            if e.secuencia != i or e.hash_anterior != anterior or e.hash != e.calcular_hash():
                return ResultadoVerificacion(
                    ok=False, total=len(entradas), primera_falla=i,
                    detalle=f"Entrada {i} alterada o fuera de secuencia",
                )
            anterior = e.hash
        return ResultadoVerificacion(ok=True, total=len(entradas))

    def verificar(self) -> ResultadoVerificacion:
        with self._lock:
            try:
                entradas = self._leer()
            except (OSError, ValueError) as e:
                return ResultadoVerificacion(ok=False, total=0, detalle=f"Bitácora ilegible: {e}")
            return self._verificar_entradas(entradas)

    def listar(self, id_caso: Optional[str] = None) -> List[EntradaBitacora]:
        with self._lock:
            return [e for e in self._leer() if id_caso is None or e.id_caso == id_caso]

    def registrar(
        self,
        usuario: str,
        accion: str,
        objetivo: str,
        id_caso: Optional[str] = None,
        antes: Optional[str] = None,
        despues: Optional[str] = None,
        motivo: Optional[str] = None,
    ) -> EntradaBitacora:
        with self._lock:
            entradas = self._leer()
            resultado = self._verificar_entradas(entradas)
            if not resultado.ok:
                # No se encadena sobre una bitácora adulterada.
                raise AuditIntegrityError(f"Bitácora comprometida: {resultado.detalle}")
            entrada = EntradaBitacora(
                secuencia=len(entradas) + 1,
                timestamp=datetime.now(timezone.utc).isoformat(),
                usuario=usuario, accion=accion, objetivo=objetivo, id_caso=id_caso,
                antes=antes, despues=despues, motivo=motivo,
                hash_anterior=entradas[-1].hash if entradas else EntradaBitacora.GENESIS_HASH,
            )
            entrada.hash = entrada.calcular_hash()
            entradas.append(entrada)
            self.mgr.write_json_atomic(self.ruta, [e.model_dump(mode="json") for e in entradas])
            return entrada
