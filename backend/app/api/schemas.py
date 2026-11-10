"""
Contrato HTTP. Debe coincidir 1:1 con frontend/src/types/caso.ts y alerta.ts.
"""

from __future__ import annotations

from typing import Dict, List, Literal, Optional, Tuple, Union

from pydantic import BaseModel, Field, model_validator

from backend.app.core_ergonomics.cambios import CambioPropuesto
from backend.app.core_ergonomics.modelos import ContextoTarea, Efecto, NivelReba, Segmento
from backend.app.settings import USUARIO_POR_DEFECTO

Vista = Literal["lateral", "frontal", "cenital"]
VISTAS: Tuple[Vista, ...] = ("lateral", "frontal", "cenital")
TipoTarea = Literal["postura", "levantamiento", "transporte", "empuje_sin_auxiliar", "empuje_con_auxiliar"]
ColorNom = Literal["verde", "amarillo", "naranja", "rojo", "morado"]
NivelControl = Literal["ingenieria", "administrativo"]
EstadoRecomendacion = Literal["propuesta", "aprobada", "editada_aprobada", "rechazada"]
ID_PATRON = r"^[A-Za-z0-9_-]{1,64}$"


class Punto(BaseModel):
    id: int = Field(ge=0, le=18)  # 0-16 COCO-17; 17/18 nudillo medio izq/der (WholeBody)
    x: float
    y: float
    confianza: float = Field(ge=0, le=1)
    corregido: bool = False


class Imagen(BaseModel):
    vista: Vista
    url: str
    ancho: int = Field(gt=0)
    alto: int = Field(gt=0)
    puntos: List[Punto]


class Angulo(BaseModel):
    segmento: Segmento
    lado: Optional[Literal["izq", "der"]]
    vista: Vista
    angulo_grados: Optional[float]
    puntaje_reba: int
    modificadores: List[str]
    estado: Literal["ok", "revisar", "sin_dato"]
    motivo_estado: Optional[str] = None
    confirmado: bool = False
    puntaje_previo: Optional[int] = None


class ResultadoReba(BaseModel):
    grupo_a: int
    grupo_b: int
    tabla_c: int
    carga: int
    agarre: int
    actividad: int
    final: int
    nivel: NivelReba


class FactorNom(BaseModel):
    codigo: str
    etiqueta: str
    color: ColorNom
    valor: int = Field(ge=0)


class ResultadoNom036(BaseModel):
    metodo: Literal["levantamiento", "transporte", "empuje_sin_auxiliar", "empuje_con_auxiliar"]
    total: int
    nivel: ColorNom
    factores: List[FactorNom]


class Hallazgo(BaseModel):
    id: str
    origen: Literal["vision", "reglas_jabil", "auditoria"]
    severidad: Literal["info", "advertencia", "critico"]
    mensaje: str
    referencia: Optional[str] = None
    vista: Optional[Vista] = None
    caja: Optional[Tuple[float, float, float, float]] = None
    descartado: Optional["Descarte"] = None


class Descarte(BaseModel):
    """El especialista marcó el hallazgo como falso positivo o no aplicable."""
    motivo: str
    usuario: str
    timestamp: str


Hallazgo.model_rebuild()


Rol = Literal["ergonomia", "ingenieria"]
TipoCambio = Literal["planta", "postura", "administrativo"]
EstadoImplementacion = Literal["pendiente_autorizacion", "por_implementar", "implementada", "denegada"]


class RecomendacionBase(BaseModel):
    id: str
    nivel_control: NivelControl
    tipo_cambio: TipoCambio
    titulo: str
    texto: str
    referencia: str
    origen: Literal["ia", "especialista"] = "ia"
    estado: EstadoRecomendacion = "propuesta"
    implementacion: Optional[EstadoImplementacion] = None
    responsable: Optional[str] = None
    fecha_compromiso: Optional[str] = None
    aprobado_por: Optional[str] = None
    autorizado_por: Optional[str] = None
    nota_autorizacion: Optional[str] = None
    implementado_por: Optional[str] = None
    nota_implementacion: Optional[str] = None
    justificacion_rag: Optional[str] = None
    norma_vinculada: Optional[str] = None
    codigo_jabil: Optional[str] = None
    hoja_excel_jabil: Optional[str] = None
    layer_autocad: Optional[str] = None
    tramite_moc: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _tipo_por_defecto(cls, datos):
        # Casos guardados antes de existir tipo_cambio: ingeniería = cambio en planta.
        if isinstance(datos, dict) and "tipo_cambio" not in datos:
            datos = {**datos, "tipo_cambio": "planta" if datos.get("nivel_control") == "ingenieria" else "administrativo"}
        return datos


class Recomendacion(RecomendacionBase):
    """Salida: incluye los cambios concretos y el REBA proyectado (calculados)."""
    cambios: List[CambioPropuesto] = Field(default_factory=list)
    reba_proyectado: Optional[int] = None
    requiere_autorizacion: bool = False


class SegmentoResidual(BaseModel):
    segmento: Segmento
    antes: int
    despues: int


class Residual(BaseModel):
    antes_final: int
    antes_nivel: NivelReba
    despues_final: int
    despues_nivel: NivelReba
    segmentos: List[SegmentoResidual]
    recomendaciones_aplicadas: List[str]


class Validacion(BaseModel):
    pendientes: int
    falta_ingenieria: bool
    completa: bool
    por_autorizar: int = 0
    por_implementar: int = 0
    implementadas: int = 0
    aprobado_e_implementado: bool = False


class CasoResumen(BaseModel):
    id_caso: str
    estacion: str
    tipo_tarea: TipoTarea
    fecha: str
    reba_final: Optional[int]
    nivel: Optional[NivelReba]
    decisiones_pendientes: int
    por_autorizar: int = 0


class CasoDetalle(BaseModel):
    id_caso: str
    estacion: str
    tipo_tarea: TipoTarea
    fecha: str
    imagenes: List[Imagen]
    contexto: ContextoTarea
    angulos: List[Angulo]
    reba: Optional[ResultadoReba]
    nom036: Optional[ResultadoNom036]
    hallazgos: List[Hallazgo]
    recomendaciones: List[Recomendacion]
    residual: Optional[Residual]
    validacion: Validacion


# ---------- Persistencia del caso (caso.json) ----------

class RecomendacionAlmacenada(RecomendacionBase):
    texto_ia: str = Field(..., description="Texto original propuesto (IA o especialista); nunca se sobrescribe")
    efecto: Efecto = Field(default_factory=Efecto)
    efecto_ia: Optional[Efecto] = Field(None, description="Efecto original antes de que el especialista lo editara")


class Nom036Captura(BaseModel):
    metodo: Literal["levantamiento", "transporte", "empuje_sin_auxiliar", "empuje_con_auxiliar"]
    factores: List[FactorNom]


class EvaluacionPrevia(BaseModel):
    """Evaluación capturada manualmente en piso, contra la que se audita."""
    segmentos: Dict[Segmento, int] = Field(default_factory=dict)
    reba_final: Optional[int] = Field(None, ge=1, le=15)


class CasoAlmacenado(BaseModel):
    id_caso: str = Field(pattern=ID_PATRON)
    estacion: str
    tipo_tarea: TipoTarea
    fecha: str
    imagenes: List[Imagen]
    contexto: ContextoTarea = Field(default_factory=ContextoTarea)
    evaluacion_previa: EvaluacionPrevia = Field(default_factory=EvaluacionPrevia)
    nom036: Optional[Nom036Captura] = None
    hallazgos_vision: List[Hallazgo] = Field(default_factory=list)
    hallazgos_descartados: Dict[str, Descarte] = Field(default_factory=dict)
    angulos_confirmados: List[str] = Field(default_factory=list)
    recomendaciones: List[RecomendacionAlmacenada] = Field(default_factory=list)

    @model_validator(mode="after")
    def _ids_unicos(self) -> "CasoAlmacenado":
        ids = [r.id for r in self.recomendaciones]
        if len(ids) != len(set(ids)):
            raise ValueError(f"IDs de recomendación duplicados en {self.id_caso}")
        vistas = [i.vista for i in self.imagenes]
        if len(vistas) != len(set(vistas)):
            raise ValueError(f"Vistas duplicadas en {self.id_caso}")
        return self


# ---------- Peticiones ----------

Usuario = Field(USUARIO_POR_DEFECTO, min_length=3, max_length=120)
ValorCambio = Union[bool, float, str]


def _texto(v: Optional[str]) -> str:
    return (v or "").strip()


class Actor(BaseModel):
    usuario: str = Usuario
    rol: Rol = "ergonomia"


class CorreccionPuntos(Actor):
    puntos: List[Punto] = Field(max_length=19)


class Decision(Actor):
    id_caso: str
    id_recomendacion: str
    accion: Literal["aprobar", "editar", "rechazar"]
    texto_editado: Optional[str] = Field(None, max_length=4000)
    cambios: Dict[str, ValorCambio] = Field(default_factory=dict, description="parametro → nuevo objetivo")
    motivo: Optional[str] = Field(None, max_length=2000)
    responsable: Optional[str] = Field(None, max_length=120)
    fecha_compromiso: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")

    @model_validator(mode="after")
    def _reglas(self) -> "Decision":
        if self.accion == "editar":
            if self.texto_editado is not None and len(_texto(self.texto_editado)) < 5:
                raise ValueError("El texto editado debe tener al menos 5 caracteres")
            if self.texto_editado is None and not self.cambios:
                raise ValueError("La edición requiere cambiar el texto o los valores propuestos")
        elif self.cambios:
            raise ValueError("Solo se pueden modificar los valores al editar")
        if self.accion in ("editar", "rechazar") and not _texto(self.motivo):
            raise ValueError("Editar o rechazar requiere una justificación (motivo)")
        return self


class Autorizacion(Actor):
    accion: Literal["autorizar", "denegar"]
    motivo: Optional[str] = Field(None, max_length=2000)

    @model_validator(mode="after")
    def _motivo(self) -> "Autorizacion":
        if self.accion == "denegar" and not _texto(self.motivo):
            raise ValueError("Denegar requiere una justificación (motivo)")
        return self


class Implementacion(Actor):
    nota: Optional[str] = Field(None, max_length=2000)


class NuevaRecomendacion(Actor):
    nivel_control: NivelControl
    tipo_cambio: TipoCambio
    titulo: str = Field(min_length=3, max_length=200)
    texto: str = Field(min_length=5, max_length=4000)
    referencia: str = Field("Criterio del especialista", min_length=3, max_length=300)
    cambios: Dict[str, ValorCambio] = Field(default_factory=dict)
    motivo: str = Field(min_length=3, max_length=2000)
    responsable: Optional[str] = Field(None, max_length=120)
    fecha_compromiso: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")

    @model_validator(mode="after")
    def _coherencia(self) -> "NuevaRecomendacion":
        if self.tipo_cambio == "administrativo" and self.nivel_control != "administrativo":
            raise ValueError("Una medida administrativa debe tener nivel de control administrativo")
        if self.tipo_cambio == "planta" and self.nivel_control != "ingenieria":
            raise ValueError("Un cambio en planta es un control de ingeniería")
        return self


class CorreccionContexto(Actor):
    contexto: ContextoTarea
    motivo: str = Field(min_length=3, max_length=2000)


class RevisionHallazgo(Actor):
    accion: Literal["descartar", "restaurar"]
    motivo: str = Field(min_length=3, max_length=2000)


class AtenderAlerta(Actor):
    pass


class NuevoCaso(Actor):
    """Datos que acompañan a las fotos al crear un caso (campo `datos` del formulario multipart)."""
    estacion: str = Field(min_length=3, max_length=120)
    tipo_tarea: TipoTarea = "postura"
    tipo_operacion: Optional[str] = None
    contexto: ContextoTarea = Field(default_factory=ContextoTarea)
    evaluacion_previa: EvaluacionPrevia = Field(default_factory=EvaluacionPrevia)

    @model_validator(mode="before")
    @classmethod
    def _normalizar_tipo_operacion(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        op = data.get("tipo_operacion")
        if op and not data.get("tipo_tarea"):
            mapa = {
                "levantamiento (1)": "levantamiento",
                "levantamiento_1": "levantamiento",
                "levantamiento": "levantamiento",
                "transporte (2)": "transporte",
                "transporte_2": "transporte",
                "transporte": "transporte",
                "equipo (3)": "levantamiento",
                "equipo_3": "levantamiento",
                "equipo": "levantamiento",
                "sin auxiliar (4)": "empuje_sin_auxiliar",
                "sin_auxiliar_4": "empuje_sin_auxiliar",
                "sin_auxiliar": "empuje_sin_auxiliar",
                "empuje_sin_auxiliar": "empuje_sin_auxiliar",
                "con auxiliar (5)": "empuje_con_auxiliar",
                "con_auxiliar_5": "empuje_con_auxiliar",
                "con_auxiliar": "empuje_con_auxiliar",
                "empuje_con_auxiliar": "empuje_con_auxiliar",
                "postura": "postura",
            }
            normalizado = mapa.get(str(op).strip().lower())
            if normalizado:
                data = {**data, "tipo_tarea": normalizado}
        return data


class EstadoVision(BaseModel):
    disponible: bool
    detalle: str


class Ok(BaseModel):
    ok: Literal[True] = True


# ---------- Alertas ----------

TipoEvento = Literal[
    "RIESGO_ALTO_PENDIENTE", "DISCREPANCIA_EVALUACION", "ANGULO_POR_REVISAR",
    "OBJETO_DESCONOCIDO", "EMERGENCIA_CAIDA", "AUTORIZACION_PENDIENTE",
]


class Alerta(BaseModel):
    id_alerta: str
    id_operario: Optional[str] = None
    estacion: str
    tipo_evento: TipoEvento
    nivel_urgencia: Literal["BAJO", "MEDIO", "ALTO", "CRITICO"]
    detalles: str
    timestamp: str
    id_caso: Optional[str] = None
    estado: Literal["nueva", "vista", "atendida"] = "nueva"


# ---------- Bitácora ----------

class ResultadoIntegridad(BaseModel):
    ok: bool
    total: int
    primera_falla: Optional[int]
    detalle: Optional[str] = None


# ---------- RAG Normativo en Memoria ----------

class ConsultaRAGRequest(BaseModel):
    consulta: str = Field(..., min_length=2, description="Texto de búsqueda o palabra clave normativa")
    top_k: int = Field(default=3, ge=1, le=10)


class FragmentoNormativo(BaseModel):
    id: str
    condicion: str
    titulo: str
    documento: str
    seccion: str
    pagina: int
    norma_vinculada: str
    hoja_excel_jabil: str
    layer_autocad: str
    tramite_moc: str
    texto_oficial: str
    control_ingenieria: str
    score: float
    terminos_coincidentes: List[str] = Field(default_factory=list)


class RespuestaRAG(BaseModel):
    consulta: str
    total_coincidencias: int
    resultados: List[FragmentoNormativo]
    tiempo_ms: float


# ---------- Análisis Rápido con Cámara / Foto Instantánea ----------

class ResumenAnguloRapido(BaseModel):
    segmento: str
    grados: Optional[float] = None
    puntaje_reba: int
    estado: Literal["ok", "revisar", "sin_dato"]
    confianza: float


class AnalisisRapidoResponse(BaseModel):
    ok: bool
    personas: int
    rostro_anonimizado: bool
    reba_final: int
    reba_nivel: str
    grupo_a: int
    grupo_b: int
    tabla_c: int
    angulos: List[ResumenAnguloRapido]
    imagen_anotada_b64: Optional[str] = None
    tiempo_ms: float
    advertencia: Optional[str] = None


