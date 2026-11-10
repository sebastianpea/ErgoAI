"""
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
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import ValidationError

from backend.app.api.schemas import (
    ID_PATRON, ActualizacionHoja14H, AnalisisRapidoResponse, AsignacionOperador, CasoDetalle, ConsultaRAGRequest,
    FragmentoNormativo, Impacto, RespuestaRAG, ResumenAnguloRapido,
)
from backend.app.api.routes_evaluation import router as router_evaluation
from backend.app.api.routes_validation import router as router_validation
from backend.app.api.routes_reports import router as router_reports
from backend.app.vision.annotador import anotar_esqueleto, codificar_imagen_b64
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
        CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["GET", "POST", "PUT"],
        allow_headers=["Content-Type"],
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

    IdCaso = RutaParam(pattern=ID_PATRON)

    @app.post("/vision/analizar-rapido", response_model=AnalisisRapidoResponse)
    async def analizar_rapido(
        foto: UploadFile = File(..., description="Foto capturada por cámara o subida por el usuario"),
        tipo_tarea: str = Form("levantamiento"),
        carga_kg: float = Form(0.0),
    ):
        """Analiza instantáneamente una fotografía (desde cámara o archivo) y devuelve el esqueleto anotado y REBA."""
        t0 = time.perf_counter()
        contenido = await foto.read()
        if not contenido:
            raise DatosInvalidos("El archivo de fotografía está vacío.")

        import cv2
        import numpy as np
        from backend.app.core_ergonomics.angle_geometry import extraer_angulos_laterales
        from backend.app.core_ergonomics.modelos import ContextoTarea
        from backend.app.core_ergonomics.reba_calculator import RebaCalculator

        nparr = np.frombuffer(contenido, np.uint8)
        img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img_bgr is None:
            raise DatosInvalidos("Formato de imagen inválido. Se espera JPG o PNG.")

        # Inferencia de pose con el estimador (YOLOX + RTMPose)
        resultado = await run_in_threadpool(estimador.analizar, img_bgr)
        if resultado.personas == 0:
            return AnalisisRapidoResponse(
                ok=False,
                personas=0,
                rostro_anonimizado=False,
                reba_final=0,
                reba_nivel="sin_dato",
                grupo_a=0,
                grupo_b=0,
                tabla_c=0,
                angulos=[],
                imagen_anotada_b64=None,
                tiempo_ms=round((time.perf_counter() - t0) * 1000, 2),
                advertencia="No se detectó a ninguna persona con suficiente claridad en la toma.",
            )

        angulos_medidos = extraer_angulos_laterales(resultado.puntos)
        grados_map = {seg: m.grados for seg, m in angulos_medidos.items()}

        # Calcular REBA determinista
        config = NormativeConfigLoader(CONFIG_DIR)
        calc = RebaCalculator(config.get_reba_tables())
        ctx = ContextoTarea(carga_kg=carga_kg)
        res_reba = calc.calcular(grados_map, ctx)

        # Anotar imagen con esqueleto, banner REBA y etiquetas
        img_anotada = anotar_esqueleto(
            resultado.imagen_bgr,
            resultado.puntos,
            reba_final=res_reba.final,
            reba_nivel=res_reba.nivel,
            angulos=grados_map,
        )
        b64_str = codificar_imagen_b64(img_anotada)

        lista_angulos = [
            ResumenAnguloRapido(
                segmento=seg,
                grados=m.grados,
                puntaje_reba=res_reba.segmentos[seg].puntaje if seg in res_reba.segmentos else 1,
                estado="sin_dato" if m.grados is None else ("revisar" if m.confianza < 0.4 else "ok"),
                confianza=m.confianza,
            )
            for seg, m in angulos_medidos.items()
        ]

        t_ms = round((time.perf_counter() - t0) * 1000, 2)
        return AnalisisRapidoResponse(
            ok=True,
            personas=resultado.personas,
            rostro_anonimizado=resultado.rostro_anonimizado,
            reba_final=res_reba.final,
            reba_nivel=res_reba.nivel,
            grupo_a=res_reba.grupo_a,
            grupo_b=res_reba.grupo_b,
            tabla_c=res_reba.tabla_c,
            angulos=lista_angulos,
            imagen_anotada_b64=b64_str,
            tiempo_ms=t_ms,
        )

    @app.get("/casos/{id_caso}/exportar/excel")
    def exportar_excel(request: Request, id_caso: str = IdCaso):
        """Hoja oficial 16-PE80-6500-00014-H llena (una hoja de evaluación por operador)."""
        contenido, nombre = svc(request).exportar_excel(id_caso)
        return StreamingResponse(
            contenido,
            media_type="application/vnd.ms-excel.sheet.macroEnabled.12",
            headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
        )

    @app.put("/casos/{id_caso}/hoja-14h", response_model=CasoDetalle)
    def actualizar_hoja_14h(request: Request, cuerpo: ActualizacionHoja14H, id_caso: str = IdCaso):
        return svc(request).actualizar_hoja_14h(id_caso, cuerpo)

    @app.put("/casos/{id_caso}/asignacion-operador", response_model=CasoDetalle)
    def asignar_operador(request: Request, cuerpo: AsignacionOperador, id_caso: str = IdCaso):
        return svc(request).asignar_operador(id_caso, cuerpo)

    @app.get("/casos/{id_caso}/exportar/pdf")
    def exportar_pdf(request: Request, id_caso: str = IdCaso):
        contenido = svc(request).exportar_pdf(id_caso)
        nombre = f"Informe_Ergonomico_{id_caso}.pdf"
        return StreamingResponse(
            contenido,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={nombre}"},
        )

    @app.get("/metricas/impacto", response_model=Impacto)
    def impacto(request: Request):
        return svc(request).impacto()

    @app.get("/media/{id_caso}/{archivo}")
    def media(request: Request, id_caso: str = RutaParam(pattern=r"^[A-Za-z0-9_.-]{1,128}$"),
              archivo: str = RutaParam(pattern=r"^[A-Za-z0-9_.-]{1,128}$")):
        import cv2
        imagen = svc(request).imagen_media_protegida(id_caso, archivo)
        ok, contenido = cv2.imencode(".png", imagen)
        if not ok:
            raise DatosInvalidos("No se pudo proteger la imagen")
        return Response(contenido.tobytes(), media_type="image/png", headers={"Cache-Control": "no-store"})

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
