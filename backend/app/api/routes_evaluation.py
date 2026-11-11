import time

from fastapi import APIRouter, File, Form, Path as RutaParam, Query, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from backend.app.api.schemas import (
    Actor, Alerta, AnalisisRapidoResponse, ResumenAnguloRapido, CasoDetalle, CasoResumen, CorreccionContexto, CorreccionPuntos,
    Decision, EstadoVision, ID_PATRON, Impacto, NuevaRecomendacion, NuevoCaso, Ok,
    MetricasDashboard, PaginaCasos, ResultadoIntegridad, RevisionHallazgo, SeleccionPersona, Segmento, TipoTarea, Vista,
)
from backend.app.core_ergonomics.cambios import PARAMETROS
from backend.app.services.casos import Conflicto, DatosInvalidos, NoEncontrado, Prohibido, ServicioCasos
from backend.app.session_store import AuditIntegrityError
from backend.app.vision.estimador import estimador
from backend.app.vision.annotador import codificar_imagen_b64
from backend.app.vision.privacidad import REVISION_PRIVACIDAD, validar_regiones

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


@router.post("/vision/analizar-rapido", response_model=AnalisisRapidoResponse)
async def analizar_rapido(
    foto: UploadFile = File(..., description="Foto capturada por cámara o subida por el usuario"),
    tipo_tarea: TipoTarea = Form("levantamiento"),
    carga_kg: float = Form(0.0, ge=0, allow_inf_nan=False, description="Carga finita no negativa en kg"),
):
    """Analiza una fotografía sin crear un expediente persistente."""
    t0 = time.perf_counter()
    contenido = await foto.read()
    if not contenido:
        raise DatosInvalidos("El archivo de fotografía está vacío.")

    import cv2
    import numpy as np
    from backend.app.core_ergonomics.angle_geometry import extraer_angulos_laterales
    img_bgr = cv2.imdecode(np.frombuffer(contenido, np.uint8), cv2.IMREAD_COLOR)
    if img_bgr is None:
        raise DatosInvalidos("Formato de imagen inválido. Se espera JPG o PNG.")
    resultado = await run_in_threadpool(estimador.analizar, img_bgr)
    if resultado.personas == 0:
        return AnalisisRapidoResponse(
            ok=False, personas=0, rostro_anonimizado=False,
            reba_final=None, reba_nivel="sin_dato", grupo_a=None, grupo_b=None, tabla_c=None,
            assessment_status="incomplete", risk_ready=False,
            missing_evidence=["tipo_tarea", "carga_kg", "agarre", "actividad", "modificadores", "altura_trabajo_cm"],
            angulos=[], imagen_anotada_b64=None,
            tiempo_ms=round((time.perf_counter() - t0) * 1000, 2),
            advertencia="No se detectó a ninguna persona con suficiente claridad en la toma.",
        )
    # Sin selección explícita no atribuir mediciones a la persona más grande ni a otra vista.
    poses = ServicioCasos._personas_foto(resultado)
    angulos_medidos = extraer_angulos_laterales([])
    privacidad_ok = (resultado.rostro_anonimizado and
                     validar_regiones(resultado.imagen_bgr, resultado.regiones_privacidad) is not None)
    falta = ["persona", "tipo_tarea", "agarre", "actividad", "carga_brusca", "apoyo_unilateral",
             "modificadores", "altura_trabajo_cm", "frecuencia_duracion"]
    if not privacidad_ok:
        falta.append("privacidad")
    falta.extend(f"angulo.{seg}" for seg, m in angulos_medidos.items()
                 if m.grados is None or m.confianza < 0.4)
    return AnalisisRapidoResponse(
        ok=True, personas=resultado.personas, rostro_anonimizado=resultado.rostro_anonimizado,
        reba_final=None, reba_nivel="sin_dato", grupo_a=None, grupo_b=None, tabla_c=None,
        assessment_status="incomplete", risk_ready=False, missing_evidence=falta,
        angulos=[ResumenAnguloRapido(
            segmento=seg, grados=m.grados, puntaje_reba=None,
            estado="sin_dato" if m.grados is None else ("revisar" if m.confianza < 0.4 else "ok"),
            confianza=m.confianza,
        ) for seg, m in angulos_medidos.items()],
        poses=poses,
        imagen_anotada_b64=codificar_imagen_b64(resultado.imagen_bgr) if privacidad_ok else None,
        tiempo_ms=round((time.perf_counter() - t0) * 1000, 2),
        advertencia=("Selecciona manualmente la persona en cada vista de un caso para medir su postura; no se asocian identidades entre imágenes. "
                     + (REVISION_PRIVACIDAD if not privacidad_ok else "Faltan datos operativos y revisión del especialista.")),
    )


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
    return svc(request).corregir_puntos(id_caso, vista, cuerpo.puntos, cuerpo, cuerpo.persona_id)


@router.put("/casos/{id_caso}/persona/{vista}", response_model=CasoDetalle)
def seleccionar_persona(request: Request, cuerpo: SeleccionPersona, vista: Vista,
                         id_caso: str = RutaParam(pattern=ID_PATRON)):
    return svc(request).seleccionar_persona(id_caso, vista, cuerpo.persona_id, cuerpo)


@router.post("/casos/{id_caso}/angulos/{vista}/{segmento}/confirmar", response_model=CasoDetalle)
def confirmar_angulo(request: Request, vista: Vista, segmento: Segmento,
                     cuerpo: Actor | None = None, id_caso: str = RutaParam(pattern=ID_PATRON)):
    return svc(request).confirmar_angulo(id_caso, vista, segmento, cuerpo or Actor())


@router.put("/casos/{id_caso}/contexto", response_model=CasoDetalle)
def corregir_contexto(request: Request, cuerpo: CorreccionContexto, id_caso: str = RutaParam(pattern=ID_PATRON)):
    return svc(request).corregir_contexto(id_caso, cuerpo)
