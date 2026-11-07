"""
Catálogo de parámetros que una recomendación puede modificar y conversión entre el
`Efecto` interno (entrada del simulador) y la lista de cambios concretos que ve el especialista
(p. ej. "Ángulo de tronco: 47.5° → 32.5°").
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Union

from pydantic import BaseModel

from backend.app.core_ergonomics.modelos import SEGMENTOS, ContextoTarea, Efecto, Modificadores, Segmento

Valor = Union[bool, float, str, None]

NOMBRE_SEGMENTO: Dict[str, str] = {
    "tronco": "tronco", "cuello": "cuello", "piernas": "rodilla", "brazo": "brazo",
    "antebrazo": "codo", "muneca": "muñeca",
}
ETIQUETA_MODIFICADOR: Dict[str, str] = {
    "tronco_torsion_o_inclinacion": "Torsión o inclinación de tronco",
    "cuello_torsion_o_inclinacion": "Torsión o inclinación de cuello",
    "hombro_elevado": "Hombro elevado",
    "brazo_abducido_o_rotado": "Brazo abducido o rotado",
    "brazo_apoyado": "Brazo apoyado",
    "muneca_desviada_o_torcida": "Muñeca desviada o torcida",
}
AGARRES = ("bueno", "regular", "malo", "inaceptable")


@dataclass(frozen=True)
class Parametro:
    etiqueta: str
    tipo: str  # "numero" | "booleano" | "opcion"
    unidad: Optional[str] = None
    minimo: Optional[float] = None
    maximo: Optional[float] = None
    opciones: tuple[str, ...] = ()


def _catalogo() -> Dict[str, Parametro]:
    cat: Dict[str, Parametro] = {}
    for seg in SEGMENTOS:
        etiqueta = "Flexión de rodilla" if seg == "piernas" else f"Ángulo de {NOMBRE_SEGMENTO[seg]}"
        cat[f"angulo.{seg}"] = Parametro(etiqueta, "numero", "°", -90, 180)
    cat["carga_kg"] = Parametro("Carga manipulada", "numero", "kg", 0, 200)
    cat["carga_brusca"] = Parametro("Carga brusca o repentina", "booleano")
    cat["agarre"] = Parametro("Calidad del agarre", "opcion", opciones=AGARRES)
    cat["actividad"] = Parametro("Condiciones de actividad REBA", "numero", None, 0, 3)
    cat["apoyo_unilateral"] = Parametro("Apoyo en una sola pierna", "booleano")
    for mod, etiqueta in ETIQUETA_MODIFICADOR.items():
        cat[f"mod.{mod}"] = Parametro(etiqueta, "booleano")
    return cat


PARAMETROS: Dict[str, Parametro] = _catalogo()


class CambioPropuesto(BaseModel):
    parametro: str
    etiqueta: str
    tipo: str
    unidad: Optional[str] = None
    actual: Valor = None
    objetivo: Valor = None
    minimo: Optional[float] = None
    maximo: Optional[float] = None
    opciones: List[str] = []


def _valor_actual(clave: str, angulos: Mapping[Segmento, Optional[float]], ctx: ContextoTarea) -> Valor:
    if clave.startswith("angulo."):
        seg = clave.split(".", 1)[1]
        if seg == "muneca" and angulos.get("muneca") is None:
            return ctx.muneca_grados
        return angulos.get(seg)  # type: ignore[arg-type]
    if clave.startswith("mod."):
        return getattr(ctx.modificadores, clave.split(".", 1)[1])
    return getattr(ctx, clave)


def efecto_a_dict(e: Efecto) -> Dict[str, Valor]:
    d: Dict[str, Valor] = {f"angulo.{s}": v for s, v in e.angulos.items()}
    for campo in ("carga_kg", "carga_brusca", "agarre", "actividad", "apoyo_unilateral"):
        v = getattr(e, campo)
        if v is not None:
            d[campo] = v
    d.update({f"mod.{k}": v for k, v in e.modificadores.items()})
    return d


def efecto_a_cambios(e: Efecto, angulos: Mapping[Segmento, Optional[float]], ctx: ContextoTarea) -> List[CambioPropuesto]:
    res = []
    for clave, objetivo in efecto_a_dict(e).items():
        p = PARAMETROS[clave]
        res.append(CambioPropuesto(
            parametro=clave, etiqueta=p.etiqueta, tipo=p.tipo, unidad=p.unidad,
            actual=_valor_actual(clave, angulos, ctx), objetivo=objetivo,
            minimo=p.minimo, maximo=p.maximo, opciones=list(p.opciones),
        ))
    return res


def validar_valor(clave: str, valor: Valor) -> Valor:
    p = PARAMETROS.get(clave)
    if p is None:
        raise ValueError(f"Parámetro desconocido: {clave}")
    if p.tipo == "booleano":
        if not isinstance(valor, bool):
            raise ValueError(f"{p.etiqueta}: se esperaba sí/no")
        return valor
    if p.tipo == "opcion":
        if valor not in p.opciones:
            raise ValueError(f"{p.etiqueta}: valor no válido ({valor})")
        return valor
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ValueError(f"{p.etiqueta}: se esperaba un número")
    if (p.minimo is not None and valor < p.minimo) or (p.maximo is not None and valor > p.maximo):
        raise ValueError(f"{p.etiqueta}: debe estar entre {p.minimo:g} y {p.maximo:g}")
    return int(valor) if clave == "actividad" else round(float(valor), 1)


def dict_a_efecto(d: Mapping[str, Valor]) -> Efecto:
    """Construye un Efecto validando cada parámetro contra el catálogo."""
    datos: Dict[str, object] = {"angulos": {}, "modificadores": {}}
    for clave, valor in d.items():
        v = validar_valor(clave, valor)
        if clave.startswith("angulo."):
            datos["angulos"][clave.split(".", 1)[1]] = v  # type: ignore[index]
        elif clave.startswith("mod."):
            datos["modificadores"][clave.split(".", 1)[1]] = v  # type: ignore[index]
        else:
            datos[clave] = v
    return Efecto.model_validate(datos)


def describir_contexto(ctx: ContextoTarea) -> Dict[str, str]:
    """Representación legible de cada campo del contexto (para la bitácora)."""
    d = {
        "carga_kg": f"{ctx.carga_kg:g} kg", "carga_brusca": "sí" if ctx.carga_brusca else "no",
        "agarre": ctx.agarre, "actividad": str(ctx.actividad),
        "apoyo_unilateral": "sí" if ctx.apoyo_unilateral else "no",
        "muneca_grados": "—" if ctx.muneca_grados is None else f"{ctx.muneca_grados:g}°",
        "altura_trabajo_cm": "—" if ctx.altura_trabajo_cm is None else f"{ctx.altura_trabajo_cm:g} cm",
    }
    for campo in Modificadores.model_fields:
        d[f"mod.{campo}"] = "sí" if getattr(ctx.modificadores, campo) else "no"
    return d
