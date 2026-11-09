r"""
Punto de entrada FastAPI de ErgoAI.

Ejecutar desde la raíz del repositorio:
    .venv\Scripts\python -m uvicorn backend.main:app --reload --port 8000
"""


from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, File, Form, Path as RutaParam, Query, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import ValidationError

from backend.app.api.schemas import (
    ID_PATRON, Actor, Alerta, AtenderAlerta, Autorizacion, CasoDetalle, CasoResumen, ConsultaRAGRequest,
    CorreccionContexto, CorreccionNom036, CorreccionPuntos, CorreccionReferencia, Decision, EstadoVision,
    FragmentoNormativo, Impacto, Implementacion, NuevaRecomendacion, NuevoCaso, Ok, RespuestaRAG,
    ResultadoIntegridad, RevisionHallazgo, Segmento, Vista,
)
from backend.app.api.routes_evaluation import router as router_evaluation
from backend.app.api.routes_validation import router as router_validation
from backend.app.api.routes_reports import router as router_reports
from backend.app.vision.estimador import VisionNoDisponible, estimador
from backend.app.core_ergonomics.cambios import PARAMETROS
from backend.app.services.casos import Conflicto, DatosInvalidos, NoEncontrado, Prohibido, ServicioCasos
from backend.app.session_store import (
    AuditFileManager, AuditIntegrityError, EntradaBitacora, NormativeConfigLoader,
)
from backend.app.settings import (
    BACKEND_HOST, BACKEND_PORT, CONFIG_DIR, CORS_ORIGINS, SEED_DIR, WORKSPACE_DIR,
)

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
        CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers separados por dominio (Fase 6)
    app.include_router(router_evaluation)
    app.include_router(router_validation)
    app.include_router(router_reports)

    def svc(request: Request) -> ServicioCasos:
        return request.app.state.servicio

    CodigosError = {
        NoEncontrado: 404,
        Conflicto: 409,
        VisionNoDisponible: 503,
        Prohibido: 403,
        DatosInvalidos: 422,
    }
    for exc_cls, status_code in CodigosError.items():
        def _crear_manejador(codigo: int):
            async def _manejador(_: Request, e: Exception):
                return JSONResponse(status_code=codigo, content={"detail": str(e)})
            return _manejador
        app.add_exception_handler(exc_cls, _crear_manejador(status_code))

    @app.exception_handler(AuditIntegrityError)
    async def _integridad(_: Request, e: AuditIntegrityError):
        log.error("Integridad comprometida: %s", e)
        return JSONResponse(status_code=409, content={"detail": str(e)})

    @app.get("/metricas/impacto", response_model=Impacto)
    def impacto(request: Request):
        return svc(request).impacto()

    @app.get("/media/{id_caso}/{archivo}")
    def media(request: Request, id_caso: str = RutaParam(pattern=r"^[A-Za-z0-9_.-]{1,128}$"),
              archivo: str = RutaParam(pattern=r"^[A-Za-z0-9_.-]{1,128}$")):
        return FileResponse(svc(request).ruta_media(id_caso, archivo))

    @app.post("/rag/consultar", response_model=RespuestaRAG)
    def consultar_rag(request: Request, cuerpo: ConsultaRAGRequest):
        t0 = time.perf_counter()
        resultados = svc(request).consultar_rag(cuerpo.consulta, top_k=cuerpo.top_k)
        t_ms = round((time.perf_counter() - t0) * 1000, 2)
        return RespuestaRAG(
            consulta=cuerpo.consulta,
            total_coincidencias=len(resultados),
            resultados=[
                FragmentoNormativo(
                    id=r.clausula.id,
                    condicion=r.clausula.condicion,
                    titulo=r.clausula.titulo,
                    documento=r.clausula.documento,
                    seccion=r.clausula.seccion,
                    pagina=r.clausula.pagina,
                    norma_vinculada=r.clausula.norma_vinculada,
                    hoja_excel_jabil=r.clausula.hoja_excel_jabil,
                    layer_autocad=r.clausula.layer_autocad,
                    tramite_moc=r.clausula.tramite_moc,
                    texto_oficial=r.clausula.texto_oficial,
                    control_ingenieria=r.clausula.control_ingenieria,
                    score=r.score,
                    terminos_coincidentes=r.terminos_coincidentes,
                )
                for r in resultados
            ],
            tiempo_ms=t_ms,
        )

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host=BACKEND_HOST, port=BACKEND_PORT, reload=True)
