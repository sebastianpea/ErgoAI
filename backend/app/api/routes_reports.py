from fastapi import APIRouter, Path as RutaParam, Query, Request
from fastapi.responses import StreamingResponse

from backend.app.api.schemas import (
    Alerta, EstadoVision, ID_PATRON, ResultadoIntegridad,
)
from backend.app.services.casos import ServicioCasos
from backend.app.session_store import EntradaBitacora
from backend.app.vision.estimador import estimador

router = APIRouter()


def svc(request: Request) -> ServicioCasos:
    return request.app.state.servicio


@router.get("/vision/estado", response_model=EstadoVision)
def estado_vision():
    disponible, detalle = estimador.estado()
    return EstadoVision(disponible=disponible, detalle=detalle)


@router.get("/catalogo/nom036")
def catalogo_nom036(request: Request) -> dict:
    return svc(request).config.get_nom036_tables()["metodos"]


# Alias de compatibilidad: usan los mismos exportadores que /exportar/pdf y /exportar/excel
# (servicio de casos + plantilla oficial), sin escribir archivos en el workspace.
@router.get("/casos/{id_caso}/informe")
def informe_caso(request: Request, id_caso: str = RutaParam(pattern=ID_PATRON)):
    contenido = svc(request).exportar_pdf(id_caso)
    return StreamingResponse(contenido, media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="Informe_Ergonomico_{id_caso}.pdf"'})


@router.get("/casos/{id_caso}/excel-jabil")
def excel_jabil(request: Request, id_caso: str = RutaParam(pattern=ID_PATRON)):
    contenido, nombre = svc(request).exportar_excel(id_caso)
    return StreamingResponse(contenido, media_type="application/vnd.ms-excel.sheet.macroEnabled.12",
                             headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


@router.get("/alertas", response_model=list[Alerta])
def listar_alertas(request: Request):
    return svc(request).listar_alertas()


@router.post("/alertas/{id_alerta}/atender")
def atender_alerta(request: Request, id_alerta: str = RutaParam(pattern=ID_PATRON),
                   cuerpo: dict | None = None):
    usuario = (cuerpo or {}).get("usuario", "sistema")
    svc(request).atender_alerta(id_alerta, usuario)
    return {"ok": True}


@router.get("/bitacora", response_model=list[EntradaBitacora])
def bitacora(request: Request, id_caso: str | None = Query(None, pattern=ID_PATRON)):
    return svc(request).bitacora(id_caso)


@router.get("/bitacora/verificar", response_model=ResultadoIntegridad)
def verificar(request: Request):
    return svc(request).verificar_integridad()
