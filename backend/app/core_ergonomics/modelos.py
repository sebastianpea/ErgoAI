"""Contratos del dominio ergonómico, independientes de la API."""

from __future__ import annotations

from typing import Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

Segmento = Literal["tronco", "cuello", "piernas", "brazo", "antebrazo", "muneca"]
SEGMENTOS: tuple[Segmento, ...] = ("tronco", "cuello", "piernas", "brazo", "antebrazo", "muneca")
Agarre = Literal["bueno", "regular", "malo", "inaceptable"]
NivelReba = Literal["inapreciable", "bajo", "medio", "alto", "muy_alto"]


class Modificadores(BaseModel):
    """Ajustes REBA que no se miden en la vista lateral; los captura el especialista."""
    model_config = ConfigDict(extra="forbid")

    tronco_torsion_o_inclinacion: bool = False
    cuello_torsion_o_inclinacion: bool = False
    hombro_elevado: bool = False
    brazo_abducido_o_rotado: bool = False
    brazo_apoyado: bool = False
    muneca_desviada_o_torcida: bool = False


class ContextoTarea(BaseModel):
    """Parámetros operativos de la tarea (no se infieren de la foto)."""
    model_config = ConfigDict(extra="forbid")

    carga_kg: float = Field(0, ge=0)
    carga_brusca: bool = False
    agarre: Agarre = "bueno"
    actividad: int = Field(0, ge=0, le=3, description="Número de condiciones de actividad REBA presentes")
    apoyo_unilateral: bool = False
    muneca_grados: Optional[float] = Field(None, description="Flexión de muñeca medida manualmente (COCO-17 no tiene mano)")
    altura_trabajo_cm: Optional[float] = Field(None, gt=0)
    personas_en_carga: int = Field(
        1, ge=1, le=2,
        description="Personas que manipulan la misma carga. 2 = levantamiento en equipo (hoja NOM-036 Equipo (3))")
    modificadores: Modificadores = Field(default_factory=Modificadores)


class AnguloMedido(BaseModel):
    segmento: Segmento
    grados: Optional[float]
    confianza: float = Field(ge=0, le=1)
    lado: Optional[Literal["izq", "der"]] = None


class Efecto(BaseModel):
    """Cambio esperado al aplicar una recomendación (entrada del simulador de riesgo residual)."""
    model_config = ConfigDict(extra="forbid")

    angulos: Dict[Segmento, float] = Field(default_factory=dict)
    carga_kg: Optional[float] = Field(None, ge=0)
    carga_brusca: Optional[bool] = None
    agarre: Optional[Agarre] = None
    actividad: Optional[int] = Field(None, ge=0, le=3)
    apoyo_unilateral: Optional[bool] = None
    modificadores: Dict[str, bool] = Field(default_factory=dict)
