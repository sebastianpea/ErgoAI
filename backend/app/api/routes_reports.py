from fastapi import APIRouter, Path as RutaParam, Query, Request
from fastapi.responses import FileResponse, StreamingResponse

from backend.app.api.schemas import (
    Alerta, EstadoVision, ID_PATRON, ResultadoIntegridad,
)
from backend.app.services.casos import ServicioCasos
from backend.app.session_store import EntradaBitacora
from backend.app.exporters.pdf_report_builder import PdfReportBuilder
from backend.app.exporters.jabil_xlsm_filler import JabilXlsmFiller
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


@router.get("/casos/{id_caso}/informe")
def informe_caso(id_caso: str = RutaParam(pattern=ID_PATRON)):
    builder = PdfReportBuilder()
    output_path = f"casos_jabil_workspace/{id_caso}/outputs/informe.pdf"
    pdf_path = builder.build(id_caso, output_path)
    return FileResponse(pdf_path, media_type="application/pdf", filename=f"informe_{id_caso}.pdf")


@router.get("/casos/{id_caso}/excel-jabil")
def excel_jabil(id_caso: str = RutaParam(pattern=ID_PATRON)):
    filler = JabilXlsmFiller()
    template_path = "casos_jabil_workspace/templates/16-PE80-6500-00014-H_base.xlsm"
    output_path = f"casos_jabil_workspace/{id_caso}/outputs/evaluacion_jabil.xlsx"
    xlsx_path = filler.fill(id_caso, template_path, output_path)
    return FileResponse(
        xlsx_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"evaluacion_jabil_{id_caso}.xlsx",
    )


@router.get("/casos/{id_caso}/exportar/excel")
def exportar_excel(request: Request, id_caso: str = RutaParam(pattern=ID_PATRON)):
    return StreamingResponse(
        svc(request).exportar_excel(id_caso),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=Informe_Ergonomico_{id_caso}.xlsx"},
    )


@router.get("/casos/{id_caso}/exportar/pdf")
def exportar_pdf(request: Request, id_caso: str = RutaParam(pattern=ID_PATRON)):
    return StreamingResponse(
        svc(request).exportar_pdf(id_caso), media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=Informe_Ergonomico_{id_caso}.pdf"},
    )


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
