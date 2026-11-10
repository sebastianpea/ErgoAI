"""
Punto de entrada FastAPI de ErgoAI.

Ejecutar desde la raíz del repositorio:
    .venv\\Scripts\\python -m uvicorn backend.main:app --reload --port 8000
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
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import ValidationError

from backend.app.api.schemas import (
    ID_PATRON, Actor, Alerta, AnalisisRapidoResponse, AtenderAlerta, Autorizacion, CasoDetalle, CasoResumen,
    ConsultaRAGRequest, CorreccionContexto, CorreccionPuntos, Decision, EstadoVision, FragmentoNormativo,
    Implementacion, NuevaRecomendacion, NuevoCaso, Ok, RespuestaRAG, ResultadoIntegridad, ResumenAnguloRapido,
    RevisionHallazgo, Segmento, Vista,
)
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

    @app.post("/casos/{id_caso}/angulos/{vista}/{segmento}/confirmar", response_model=CasoDetalle)
    def confirmar_angulo(request: Request, vista: Vista, segmento: Segmento,
                         cuerpo: Optional[Actor] = None, id_caso: str = IdCaso):
        return svc(request).confirmar_angulo(id_caso, vista, segmento, cuerpo or Actor())

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

    @app.post("/casos/{id_caso}/generar-plan-ia", response_model=CasoDetalle)
    async def generar_plan_ia(request: Request, cuerpo: Optional[Actor] = None, id_caso: str = IdCaso):
        actor = cuerpo or Actor()
        return await run_in_threadpool(svc(request).generar_plan_ergoai, id_caso, actor.usuario)

    @app.get("/casos/{id_caso}/exportar/excel")
    def exportar_excel(request: Request, id_caso: str = IdCaso):
        contenido = svc(request).exportar_excel(id_caso)
        nombre = f"Informe_Ergonomico_{id_caso}.xlsx"
        return StreamingResponse(
            contenido,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={nombre}"},
        )

    @app.get("/casos/{id_caso}/exportar/pdf")
    def exportar_pdf(request: Request, id_caso: str = IdCaso):
        contenido = svc(request).exportar_pdf(id_caso)
        nombre = f"Informe_Ergonomico_{id_caso}.pdf"
        return StreamingResponse(
            contenido,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={nombre}"},
        )

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

