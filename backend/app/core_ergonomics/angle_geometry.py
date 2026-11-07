"""
Geometría vectorial pura para extraer ángulos articulares de keypoints COCO-17 en vista lateral.

Convenciones:
- Coordenadas de imagen (y hacia abajo) se convierten a coordenadas matemáticas (y hacia arriba).
- Flexión positiva = segmento rotado hacia donde mira el operador; extensión negativa.
- La muñeca solo se mide si hay punto de mano (17/18, de WholeBody-133); con COCO-17 puro queda sin dato.
"""

from __future__ import annotations

import math
from typing import Dict, Iterable, Mapping, Optional, Protocol, Tuple

from backend.app.core_ergonomics.modelos import AnguloMedido, Segmento

Vec = Tuple[float, float]

# Índices COCO-17
NARIZ = 0
# "mano" = nudillo medio (17/18), presente cuando los puntos vienen de RTMPose WholeBody-133.
LADO_IZQ = {"oreja": 3, "hombro": 5, "codo": 7, "muneca": 9, "cadera": 11, "rodilla": 13, "tobillo": 15, "mano": 17}
LADO_DER = {"oreja": 4, "hombro": 6, "codo": 8, "muneca": 10, "cadera": 12, "rodilla": 14, "tobillo": 16, "mano": 18}


class PuntoLike(Protocol):
    id: int
    x: float
    y: float
    confianza: float


def _vec(desde: PuntoLike, hasta: PuntoLike) -> Vec:
    return (hasta.x - desde.x, -(hasta.y - desde.y))


def _rotacion_ccw(ref: Vec, v: Vec) -> float:
    """Ángulo con signo (grados, antihorario positivo) para llevar `ref` a `v`."""
    cruz = ref[0] * v[1] - ref[1] * v[0]
    punto = ref[0] * v[0] + ref[1] * v[1]
    return math.degrees(math.atan2(cruz, punto))


def _angulo_interior(a: PuntoLike, vertice: PuntoLike, b: PuntoLike) -> float:
    """Ángulo interior en `vertice` (0–180°)."""
    return abs(_rotacion_ccw(_vec(vertice, a), _vec(vertice, b)))


def _confianza(puntos: Iterable[PuntoLike]) -> float:
    return min(p.confianza for p in puntos)


def elegir_lado(por_id: Mapping[int, PuntoLike]) -> Tuple[str, Dict[str, int]]:
    """El lado más visible en la vista lateral es el de mayor confianza media."""
    def media(lado: Dict[str, int]) -> float:
        vals = [por_id[i].confianza for k, i in lado.items() if i in por_id and k != "mano"]
        return sum(vals) / len(vals) if vals else 0.0
    return ("izq", LADO_IZQ) if media(LADO_IZQ) >= media(LADO_DER) else ("der", LADO_DER)


def extraer_angulos_laterales(puntos: Iterable[PuntoLike]) -> Dict[Segmento, AnguloMedido]:
    por_id = {p.id: p for p in puntos}
    lado, idx = elegir_lado(por_id)

    def p(nombre: str) -> Optional[PuntoLike]:
        return por_id.get(idx[nombre])

    hombro, codo, muneca, mano = p("hombro"), p("codo"), p("muneca"), p("mano")
    cadera, rodilla, tobillo, oreja = p("cadera"), p("rodilla"), p("tobillo"), p("oreja")
    nariz = por_id.get(NARIZ)

    # Hacia dónde mira el operador: +1 derecha, -1 izquierda
    frente = 1.0
    if nariz and hombro and nariz.x != hombro.x:
        frente = 1.0 if nariz.x > hombro.x else -1.0

    def flexion(ref: Vec, v: Vec, cadena_inferior: bool = False) -> float:
        rot = _rotacion_ccw(ref, v)
        # Con referencia hacia arriba, inclinarse hacia el frente es giro horario; hacia abajo, antihorario.
        return round((rot if cadena_inferior else -rot) * frente, 1)

    res: Dict[Segmento, AnguloMedido] = {}

    def sin_dato(seg: Segmento, con_lado: bool = False) -> AnguloMedido:
        return AnguloMedido(segmento=seg, grados=None, confianza=0.0, lado=lado if con_lado else None)

    if hombro and cadera:
        tronco = _vec(cadera, hombro)
        res["tronco"] = AnguloMedido(segmento="tronco", grados=flexion((0.0, 1.0), tronco),
                                     confianza=_confianza([hombro, cadera]))
        if oreja:
            res["cuello"] = AnguloMedido(segmento="cuello", grados=flexion(tronco, _vec(hombro, oreja)),
                                         confianza=_confianza([oreja, hombro, cadera]))
        if codo:
            res["brazo"] = AnguloMedido(
                segmento="brazo", lado=lado,
                grados=flexion(_vec(hombro, cadera), _vec(hombro, codo), cadena_inferior=True),
                confianza=_confianza([hombro, codo, cadera]))
    if hombro and codo and muneca:
        res["antebrazo"] = AnguloMedido(
            segmento="antebrazo", lado=lado,
            grados=round(180.0 - _angulo_interior(hombro, codo, muneca), 1),
            confianza=_confianza([hombro, codo, muneca]))
    if codo and muneca and mano:
        # Muñeca: desviación entre la línea del antebrazo y la de la mano (0° = alineadas).
        res["muneca"] = AnguloMedido(
            segmento="muneca", lado=lado,
            grados=round(abs(_rotacion_ccw(_vec(codo, muneca), _vec(muneca, mano))), 1),
            confianza=_confianza([codo, muneca, mano]))
    if cadera and rodilla and tobillo:
        res["piernas"] = AnguloMedido(
            segmento="piernas",
            grados=round(180.0 - _angulo_interior(cadera, rodilla, tobillo), 1),
            confianza=_confianza([cadera, rodilla, tobillo]))

    for seg in ("tronco", "cuello", "piernas"):
        res.setdefault(seg, sin_dato(seg))
    for seg in ("brazo", "antebrazo", "muneca"):
        res.setdefault(seg, sin_dato(seg, con_lado=True))
    return res
