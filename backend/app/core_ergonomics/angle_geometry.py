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


CONFIANZA_VOTO = 0.3


def direccion_frente(por_id: Mapping[int, PuntoLike], idx: Dict[str, int]) -> float:
    """
    Hacia dónde mira el operador en la foto lateral: +1 derecha, -1 izquierda.
    Si se equivoca, una flexión se lee como extensión y el REBA cambia, así que se vota con varias
    pistas anatómicas en lugar de depender solo de la nariz (que puede faltar o estar oculta):
      - nariz por delante de la oreja (la más fiable),
      - nariz por delante del hombro,
      - manos por delante de la cadera (al trabajar o cargar),
      - rodilla por delante del tobillo (las rodillas solo flexionan hacia el frente).
    """
    def p(i: Optional[int]) -> Optional[PuntoLike]:
        punto = por_id.get(i) if i is not None else None
        return punto if punto is not None and punto.confianza >= CONFIANZA_VOTO else None

    def signo(adelante: Optional[PuntoLike], atras: Optional[PuntoLike], minimo: float = 3.0) -> float:
        if adelante is None or atras is None or abs(adelante.x - atras.x) < minimo:
            return 0.0
        return 1.0 if adelante.x > atras.x else -1.0

    nariz = p(NARIZ)
    oreja = p(idx["oreja"])
    hombro, cadera, rodilla, tobillo = p(idx["hombro"]), p(idx["cadera"]), p(idx["rodilla"]), p(idx["tobillo"])
    mano = p(idx.get("mano")) or p(idx["muneca"])
    votos = (
        2.0 * signo(nariz, oreja)
        + 1.0 * signo(nariz, hombro, minimo=8.0)
        + 1.0 * signo(mano, cadera, minimo=15.0)
        + 0.5 * signo(rodilla, tobillo, minimo=10.0)
    )
    return -1.0 if votos < 0 else 1.0


def extraer_angulos_laterales(puntos: Iterable[PuntoLike]) -> Dict[Segmento, AnguloMedido]:
    por_id = {p.id: p for p in puntos}
    lado, idx = elegir_lado(por_id)

    def p(nombre: str) -> Optional[PuntoLike]:
        return por_id.get(idx[nombre])

    hombro, codo, muneca, mano = p("hombro"), p("codo"), p("muneca"), p("mano")
    cadera, rodilla, tobillo, oreja = p("cadera"), p("rodilla"), p("tobillo"), p("oreja")

    # Hacia dónde mira el operador: +1 derecha, -1 izquierda (votación de varias pistas)
    frente = direccion_frente(por_id, idx)

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


def medir_vista_frontal(puntos: Iterable[PuntoLike], lado: str, confianza_minima: float) -> Dict[str, Optional[float]]:
    """
    Vista frontal (plano coronal):
    - inclinación lateral de tronco: línea cadera-media → hombro-medio respecto a la vertical;
    - abducción del brazo del lado evaluado: hombro → codo respecto a la vertical, solo hacia afuera
      del cuerpo (un codo cruzado hacia la línea media no es abducción).
    """
    por_id = {p.id: p for p in puntos if p.confianza >= confianza_minima}
    res: Dict[str, Optional[float]] = {"inclinacion_tronco": None, "abduccion_brazo": None}
    hi, hd, ci, cd = por_id.get(5), por_id.get(6), por_id.get(11), por_id.get(12)
    if hi and hd and ci and cd:
        hombro_medio = ((hi.x + hd.x) / 2, (hi.y + hd.y) / 2)
        cadera_media = ((ci.x + cd.x) / 2, (ci.y + cd.y) / 2)
        tronco = (hombro_medio[0] - cadera_media[0], -(hombro_medio[1] - cadera_media[1]))
        res["inclinacion_tronco"] = round(abs(_rotacion_ccw((0.0, 1.0), tronco)), 1)

    idx = LADO_IZQ if lado == "izq" else LADO_DER
    otro = LADO_DER if lado == "izq" else LADO_IZQ
    hombro, codo, hombro_otro = por_id.get(idx["hombro"]), por_id.get(idx["codo"]), por_id.get(otro["hombro"])
    if hombro and codo and hombro_otro:
        afuera = 1.0 if hombro.x >= hombro_otro.x else -1.0  # dirección lateral hacia fuera del cuerpo
        brazo = (codo.x - hombro.x, -(codo.y - hombro.y))
        angulo = abs(_rotacion_ccw((0.0, -1.0), brazo))
        res["abduccion_brazo"] = round(angulo if brazo[0] * afuera > 0 else 0.0, 1)
    return res
