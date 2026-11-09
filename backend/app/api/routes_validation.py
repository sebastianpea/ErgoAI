from fastapi import APIRouter, Path as RutaParam, Request
from fastapi.responses import JSONResponse

from backend.app.api.schemas import (
    Actor, Alerta, Autorizacion, CasoDetalle, CorreccionNom036, CorreccionReferencia,
    Decision, Implementacion, ID_PATRON, NuevaRecomendacion, Ok, ResultadoIntegridad,
    RevisionHallazgo, Vista,
)
from backend.app.services.casos import ServicioCasos

router = APIRouter()


def svc(request: Request) -> ServicioCasos:
    return request.app.state.servicio


@router.put("/casos/{id_caso}/nom036", response_model=CasoDetalle)
def corregir_nom036(request: Request, cuerpo: CorreccionNom036, id_caso: str = RutaParam(pattern=ID_PATRON)):
    return svc(request).corregir_nom036(id_caso, cuerpo)


@router.put("/casos/{id_caso}/referencia", response_model=CasoDetalle)
def corregir_referencia(request: Request, cuerpo: CorreccionReferencia, id_caso: str = RutaParam(pattern=ID_PATRON)):
    return svc(request).corregir_referencia(id_caso, cuerpo)


@router.post("/casos/{id_caso}/hallazgos/{id_hallazgo}/revision", response_model=CasoDetalle)
def revisar_hallazgo(request: Request, cuerpo: RevisionHallazgo, id_caso: str = RutaParam(pattern=ID_PATRON),
                     id_hallazgo: str = RutaParam(pattern=ID_PATRON)):
    return svc(request).revisar_hallazgo(id_caso, id_hallazgo, cuerpo)


@router.post("/casos/{id_caso}/recomendaciones", response_model=dict)
def crear_recomendacion(request: Request, cuerpo: NuevaRecomendacion, id_caso: str = RutaParam(pattern=ID_PATRON)):
    return {"ok": True, "id": svc(request).crear_recomendacion(id_caso, cuerpo)}


@router.post("/casos/{id_caso}/generar-plan-ia", response_model=CasoDetalle)
async def generar_plan_ia(request: Request, cuerpo: Actor | None = None, id_caso: str = RutaParam(pattern=ID_PATRON)):
    actor = cuerpo or Actor()
    import asyncio
    return await asyncio.to_thread(svc(request).generar_plan_ergoai, id_caso, actor.usuario)


@router.post("/casos/{id_caso}/recomendaciones/{id_recomendacion}/decision", response_model=Ok)
def decidir(request: Request, d: Decision, id_caso: str = RutaParam(pattern=ID_PATRON),
            id_recomendacion: str = RutaParam(pattern=ID_PATRON)):
    svc(request).decidir(id_caso, id_recomendacion, d)
    return Ok()


@router.post("/casos/{id_caso}/recomendaciones/{id_recomendacion}/autorizacion", response_model=Ok)
def autorizar(request: Request, cuerpo: Autorizacion, id_caso: str = RutaParam(pattern=ID_PATRON),
              id_recomendacion: str = RutaParam(pattern=ID_PATRON)):
    svc(request).autorizar(id_caso, id_recomendacion, cuerpo)
    return Ok()


@router.post("/casos/{id_caso}/recomendaciones/{id_recomendacion}/implementacion", response_model=Ok)
def implementar(request: Request, cuerpo: Implementacion, id_caso: str = RutaParam(pattern=ID_PATRON),
                id_recomendacion: str = RutaParam(pattern=ID_PATRON)):
    svc(request).implementar(id_caso, id_recomendacion, cuerpo)
    return Ok()
