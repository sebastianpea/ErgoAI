from fastapi import APIRouter, File, Form, Path as RutaParam, Query, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from backend.app.api.schemas import (
    Actor, Alerta, CasoDetalle, CasoResumen, CorreccionContexto, CorreccionPuntos,
    Decision, EstadoVision, ID_PATRON, Impacto, NuevaRecomendacion, NuevoCaso, Ok,
    MetricasDashboard, PaginaCasos, ResultadoIntegridad, RevisionHallazgo, Segmento, Vista,
)
from backend.app.core_ergonomics.cambios import PARAMETROS
from backend.app.services.casos import Conflicto, DatosInvalidos, NoEncontrado, Prohibido, ServicioCasos
from backend.app.session_store import AuditIntegrityError

router = APIRouter()


def svc(request: Request) -> ServicioCasos:
    return request.app.state.servicio


@router.get("/salud")
def salud() -> dict:
    return {"ok": True}


@router.get("/catalogo/parametros")
def catalogo_parametros() -> list:
    return [{"parametro": k, "etiqueta": p.etiqueta, "tipo": p.tipo, "unidad": p.unidad,
             "minimo": p.minimo, "maximo": p.maximo, "opciones": list(p.opciones)}
            for k, p in PARAMETROS.items()]


@router.get("/casos", response_model=list[CasoResumen])
def listar_casos(request: Request):
    return svc(request).listar()


@router.get("/casos/pagina", response_model=PaginaCasos)
def pagina_casos(request: Request, page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=100)):
    return svc(request).pagina(page, page_size)


@router.get("/metricas/dashboard", response_model=MetricasDashboard)
def metricas_dashboard(request: Request):
    return svc(request).dashboard()


@router.get("/casos/{id_caso}", response_model=CasoDetalle)
def obtener_caso(request: Request, id_caso: str = RutaParam(pattern=ID_PATRON)):
    return svc(request).obtener(id_caso)


@router.post("/casos", response_model=dict)
async def crear_caso(
    request: Request,
    datos: str = Form(..., description="JSON con estacion, tipo_tarea, contexto, usuario y rol"),
    lateral: UploadFile = File(...),
    frontal: UploadFile | None = File(None),
    cenital: UploadFile | None = File(None),
):
    try:
        nuevo = NuevoCaso.model_validate_json(datos)
    except ValidationError as e:
        raise DatosInvalidos("; ".join(err["msg"] for err in e.errors())) from e
    fotos = {"lateral": await lateral.read()}
    for vista, archivo in (("frontal", frontal), ("cenital", cenital)):
        if archivo is not None and archivo.filename:
            fotos[vista] = await archivo.read()
    id_caso = await run_in_threadpool(svc(request).crear_caso, nuevo, fotos)
    return {"ok": True, "id": id_caso}


@router.put("/casos/{id_caso}/puntos/{vista}", response_model=CasoDetalle)
def corregir_puntos(request: Request, cuerpo: CorreccionPuntos, vista: Vista, id_caso: str = RutaParam(pattern=ID_PATRON)):
    return svc(request).corregir_puntos(id_caso, vista, cuerpo.puntos, cuerpo)


@router.post("/casos/{id_caso}/angulos/{vista}/{segmento}/confirmar", response_model=CasoDetalle)
def confirmar_angulo(request: Request, vista: Vista, segmento: Segmento,
                     cuerpo: Actor | None = None, id_caso: str = RutaParam(pattern=ID_PATRON)):
    return svc(request).confirmar_angulo(id_caso, vista, segmento, cuerpo or Actor())


@router.put("/casos/{id_caso}/contexto", response_model=CasoDetalle)
def corregir_contexto(request: Request, cuerpo: CorreccionContexto, id_caso: str = RutaParam(pattern=ID_PATRON)):
    return svc(request).corregir_contexto(id_caso, cuerpo)
