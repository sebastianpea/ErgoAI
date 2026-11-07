"""
Punto de entrada FastAPI de ErgoAI.

Ejecutar desde la raíz del repositorio:
    .venv\\Scripts\\python -m uvicorn backend.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, File, Form, Path as RutaParam, Query, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import ValidationError

from backend.app.api.schemas import (
    ID_PATRON, Alerta, AtenderAlerta, Autorizacion, CasoDetalle, CasoResumen, CorreccionContexto, CorreccionPuntos,
    Decision, EstadoVision, Implementacion, NuevaRecomendacion, NuevoCaso, Ok, ResultadoIntegridad, RevisionHallazgo,
    Vista,
)
from backend.app.vision.estimador import VisionNoDisponible, estimador
from backend.app.core_ergonomics.cambios import PARAMETROS
from backend.app.services.casos import Conflicto, DatosInvalidos, NoEncontrado, Prohibido, ServicioCasos
from backend.app.session_store import (
    AuditFileManager, AuditIntegrityError, EntradaBitacora, NormativeConfigLoader,
)
from backend.app.settings import CONFIG_DIR, CORS_ORIGINS, SEED_DIR, WORKSPACE_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("ergoai")


def create_app(workspace_dir: Optional[Path] = None, config_dir: Optional[Path] = None,
               sembrar: bool = True) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        config = NormativeConfigLoader(config_dir or CONFIG_DIR)
        config.validate_all()  # falla rápido si un catálogo normativo está mal
        servicio = ServicioCasos(AuditFileManager(workspace_dir or WORKSPACE_DIR), config)
        if sembrar:
            creados = servicio.sembrar_si_vacio(SEED_DIR / "casos_demo.json")
            if creados:
                log.info("Workspace inicializado con %d casos de demostración", creados)
        app.state.servicio = servicio
        yield

    app = FastAPI(title="ErgoAI API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["GET", "POST", "PUT"],
        allow_headers=["Content-Type"],
    )

    def svc(request: Request) -> ServicioCasos:
        return request.app.state.servicio

    @app.exception_handler(NoEncontrado)
    async def _404(_: Request, e: NoEncontrado):
        return JSONResponse(status_code=404, content={"detail": str(e)})

    @app.exception_handler(Conflicto)
    async def _409(_: Request, e: Conflicto):
        return JSONResponse(status_code=409, content={"detail": str(e)})

    @app.exception_handler(VisionNoDisponible)
    async def _503(_: Request, e: VisionNoDisponible):
        return JSONResponse(status_code=503, content={"detail": str(e)})

    @app.exception_handler(Prohibido)
    async def _403(_: Request, e: Prohibido):
        return JSONResponse(status_code=403, content={"detail": str(e)})

    @app.exception_handler(DatosInvalidos)
    async def _422(_: Request, e: DatosInvalidos):
        return JSONResponse(status_code=422, content={"detail": str(e)})

    @app.exception_handler(AuditIntegrityError)
    async def _integridad(_: Request, e: AuditIntegrityError):
        log.error("Integridad comprometida: %s", e)
        return JSONResponse(status_code=409, content={"detail": str(e)})

    IdCaso = RutaParam(pattern=ID_PATRON)

    @app.get("/salud")
    def salud() -> dict:
        return {"ok": True}

    @app.get("/catalogo/parametros")
    def catalogo_parametros() -> list:
        """Parámetros que una recomendación puede modificar (fuente única para los formularios)."""
        return [{"parametro": k, "etiqueta": p.etiqueta, "tipo": p.tipo, "unidad": p.unidad,
                 "minimo": p.minimo, "maximo": p.maximo, "opciones": list(p.opciones)}
                for k, p in PARAMETROS.items()]

    @app.get("/casos", response_model=List[CasoResumen])
    def listar_casos(request: Request):
        return svc(request).listar()

    @app.get("/vision/estado", response_model=EstadoVision)
    def estado_vision():
        disponible, detalle = estimador.estado()
        return EstadoVision(disponible=disponible, detalle=detalle)

    @app.post("/casos", response_model=dict)
    async def crear_caso(
        request: Request,
        datos: str = Form(..., description="JSON con estacion, tipo_tarea, contexto, usuario y rol"),
        lateral: UploadFile = File(...),
        frontal: Optional[UploadFile] = File(None),
        cenital: Optional[UploadFile] = File(None),
    ):
        try:
            nuevo = NuevoCaso.model_validate_json(datos)
        except ValidationError as e:
            raise DatosInvalidos("; ".join(err["msg"] for err in e.errors())) from e
        fotos = {"lateral": await lateral.read()}
        for vista, archivo in (("frontal", frontal), ("cenital", cenital)):
            if archivo is not None and archivo.filename:
                fotos[vista] = await archivo.read()
        # La inferencia es CPU-intensiva: fuera del event loop.
        id_caso = await run_in_threadpool(svc(request).crear_caso, nuevo, fotos)
        return {"ok": True, "id": id_caso}

    @app.get("/casos/{id_caso}", response_model=CasoDetalle)
    def obtener_caso(request: Request, id_caso: str = IdCaso):
        return svc(request).obtener(id_caso)

    IdRec = RutaParam(pattern=ID_PATRON)

    @app.put("/casos/{id_caso}/puntos/{vista}", response_model=CasoDetalle)
    def corregir_puntos(request: Request, cuerpo: CorreccionPuntos, vista: Vista, id_caso: str = IdCaso):
        return svc(request).corregir_puntos(id_caso, vista, cuerpo.puntos, cuerpo)

    @app.put("/casos/{id_caso}/contexto", response_model=CasoDetalle)
    def corregir_contexto(request: Request, cuerpo: CorreccionContexto, id_caso: str = IdCaso):
        return svc(request).corregir_contexto(id_caso, cuerpo)

    @app.post("/casos/{id_caso}/hallazgos/{id_hallazgo}/revision", response_model=CasoDetalle)
    def revisar_hallazgo(request: Request, cuerpo: RevisionHallazgo, id_caso: str = IdCaso,
                         id_hallazgo: str = RutaParam(pattern=ID_PATRON)):
        return svc(request).revisar_hallazgo(id_caso, id_hallazgo, cuerpo)

    @app.post("/casos/{id_caso}/recomendaciones", response_model=dict)
    def crear_recomendacion(request: Request, cuerpo: NuevaRecomendacion, id_caso: str = IdCaso):
        return {"ok": True, "id": svc(request).crear_recomendacion(id_caso, cuerpo)}

    @app.post("/casos/{id_caso}/recomendaciones/{id_recomendacion}/decision", response_model=Ok)
    def decidir(request: Request, d: Decision, id_caso: str = IdCaso, id_recomendacion: str = IdRec):
        svc(request).decidir(id_caso, id_recomendacion, d)
        return Ok()

    @app.post("/casos/{id_caso}/recomendaciones/{id_recomendacion}/autorizacion", response_model=Ok)
    def autorizar(request: Request, cuerpo: Autorizacion, id_caso: str = IdCaso, id_recomendacion: str = IdRec):
        svc(request).autorizar(id_caso, id_recomendacion, cuerpo)
        return Ok()

    @app.post("/casos/{id_caso}/recomendaciones/{id_recomendacion}/implementacion", response_model=Ok)
    def implementar(request: Request, cuerpo: Implementacion, id_caso: str = IdCaso, id_recomendacion: str = IdRec):
        svc(request).implementar(id_caso, id_recomendacion, cuerpo)
        return Ok()

    @app.get("/alertas", response_model=List[Alerta])
    def listar_alertas(request: Request):
        return svc(request).listar_alertas()

    @app.post("/alertas/{id_alerta}/atender", response_model=Ok)
    def atender_alerta(request: Request, cuerpo: Optional[AtenderAlerta] = None,
                       id_alerta: str = RutaParam(pattern=ID_PATRON)):
        svc(request).atender_alerta(id_alerta, (cuerpo or AtenderAlerta()).usuario)
        return Ok()

    @app.get("/bitacora", response_model=List[EntradaBitacora])
    def bitacora(request: Request, id_caso: Optional[str] = Query(None, pattern=ID_PATRON)):
        return svc(request).bitacora(id_caso)

    @app.get("/bitacora/verificar", response_model=ResultadoIntegridad)
    def verificar(request: Request):
        return svc(request).verificar_integridad()

    @app.get("/media/{id_caso}/{archivo}")
    def media(request: Request, id_caso: str = IdCaso,
              archivo: str = RutaParam(pattern=r"^[A-Za-z0-9_.-]{1,128}$")):
        return FileResponse(svc(request).ruta_media(id_caso, archivo))

    return app


app = create_app()
