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
from backend.app.settings import UMBRAL_ANCHO_TORSO_FRONTAL

Vec = Tuple[float, float]

# Índices COCO-17
NARIZ = 0
# "mano" = nudillo medio (17/18), presente cuando los puntos vienen de RTMPose WholeBody-133.
LADO_IZQ = {"oreja": 3, "hombro": 5, "codo": 7, "muneca": 9, "cadera": 11, "rodilla": 13, "tobillo": 15, "mano": 17}
LADO_DER = {"oreja": 4, "hombro": 6, "codo": 8, "muneca": 10, "cadera": 12, "rodilla": 14, "tobillo": 16, "mano": 18}

# Articulaciones que intervienen en el cálculo de cada segmento REBA.
ARTICULACIONES_SEGMENTO: Dict[Segmento, Tuple[str, ...]] = {
    "tronco": ("hombro", "cadera"),
    "cuello": ("oreja", "hombro", "cadera"),
    "brazo": ("hombro", "codo", "cadera"),
    "antebrazo": ("hombro", "codo", "muneca"),
    "muneca": ("codo", "muneca", "mano"),
    "piernas": ("cadera", "rodilla", "tobillo"),
}


class PuntoLike(Protocol):
    id: int
    x: float
    y: float
    confianza: float


def _confianza_punto(p: PuntoLike) -> float:
    """Un punto ajustado manualmente por el especialista tiene confianza plena (1.0)."""
    return 1.0 if getattr(p, "corregido", False) else p.confianza


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
    return min(_confianza_punto(p) for p in puntos)


def segmentos_de_punto(id_punto: int) -> Tuple[Segmento, ...]:
    """Devuelve los segmentos REBA cuyo ángulo depende del keypoint `id_punto`."""
    if id_punto == NARIZ:
        return ("cuello",)
    nombre = next((k for lado in (LADO_IZQ, LADO_DER) for k, idx in lado.items() if idx == id_punto), None)
    if nombre is None:
        return ()
    return tuple(seg for seg, arts in ARTICULACIONES_SEGMENTO.items() if nombre in arts)


def elegir_lado(por_id: Mapping[int, PuntoLike]) -> Tuple[str, Dict[str, int]]:
    """El lado más visible en la vista es el de mayor confianza media."""
    def media(lado: Dict[str, int]) -> float:
        vals = [_confianza_punto(por_id[i]) for k, i in lado.items() if i in por_id and k != "mano"]
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


class _PuntoMedio:
    def __init__(self, a: PuntoLike, b: PuntoLike):
        self.id = -1
        self.x = (a.x + b.x) / 2.0
        self.y = (a.y + b.y) / 2.0
        self.confianza = min(_confianza_punto(a), _confianza_punto(b))
        self.corregido = bool(getattr(a, "corregido", False) and getattr(b, "corregido", False))


def _extraer_frontal(
    por_id: Mapping[int, PuntoLike],
    base: Dict[Segmento, AnguloMedido],
    m_hom: _PuntoMedio,
    m_cad: _PuntoMedio,
) -> None:
    lado, idx = elegir_lado(por_id)
    hombro, codo, cadera = por_id.get(idx["hombro"]), por_id.get(idx["codo"]), por_id.get(idx["cadera"])
    o_izq, o_der = por_id.get(LADO_IZQ["oreja"]), por_id.get(LADO_DER["oreja"])
    nariz = por_id.get(NARIZ)

    v_tronco = _vec(m_cad, m_hom)
    base["tronco"] = AnguloMedido(
        segmento="tronco",
        grados=round(abs(_rotacion_ccw((0.0, 1.0), v_tronco)), 1),
        confianza=_confianza([m_hom, m_cad]),
    )
    cabeza = _PuntoMedio(o_izq, o_der) if (o_izq and o_der) else (nariz or o_izq or o_der)
    if cabeza:
        base["cuello"] = AnguloMedido(
            segmento="cuello",
            grados=round(abs(_rotacion_ccw(v_tronco, _vec(m_hom, cabeza))), 1),
            confianza=_confianza([m_hom, m_cad, cabeza]),
        )
    if hombro and codo and cadera:
        base["brazo"] = AnguloMedido(
            segmento="brazo", lado=lado,
            grados=round(abs(_rotacion_ccw(_vec(hombro, cadera), _vec(hombro, codo))), 1),
            confianza=_confianza([hombro, codo, cadera]),
        )


def _extraer_cenital(
    por_id: Mapping[int, PuntoLike],
    base: Dict[Segmento, AnguloMedido],
    h_izq: PuntoLike,
    h_der: PuntoLike,
    c_izq: PuntoLike,
    c_der: PuntoLike,
    m_hom: _PuntoMedio,
    m_cad: _PuntoMedio,
) -> None:
    lado, idx = elegir_lado(por_id)
    hombro, codo = por_id.get(idx["hombro"]), por_id.get(idx["codo"])
    o_izq, o_der = por_id.get(LADO_IZQ["oreja"]), por_id.get(LADO_DER["oreja"])

    v_hom = _vec(h_der, h_izq)
    v_cad = _vec(c_der, c_izq)
    base["tronco"] = AnguloMedido(
        segmento="tronco",
        grados=round(abs(_rotacion_ccw(v_cad, v_hom)), 1),
        confianza=_confianza([m_hom, m_cad]),
    )
    if o_izq and o_der:
        v_ore = _vec(o_der, o_izq)
        base["cuello"] = AnguloMedido(
            segmento="cuello",
            grados=round(abs(_rotacion_ccw(v_hom, v_ore)), 1),
            confianza=_confianza([h_izq, h_der, o_izq, o_der]),
        )
    if hombro and codo:
        base["brazo"] = AnguloMedido(
            segmento="brazo", lado=lado,
            grados=round(abs(_rotacion_ccw(_vec(m_hom, m_cad), _vec(hombro, codo))), 1),
            confianza=_confianza([m_hom, m_cad, hombro, codo]),
        )


def extraer_angulos_vista(puntos: Iterable[PuntoLike], vista: str = "lateral") -> Dict[Segmento, AnguloMedido]:
    """
    Extrae los 6 ángulos por segmento para cualquier vista (`lateral`, `frontal`, `cenital`).
    - En `lateral` (o si en otra vista el operador aparece de perfil), usa la proyección sagital.
    - En `frontal`, mide inclinación lateral de tronco/cuello con el eje medio y abducción de brazo.
    - En `cenital`, mide torsión/rotación entre líneas de hombros, caderas y cabeza, y apertura de brazo.
    """
    pts_lista = list(puntos)
    base = extraer_angulos_laterales(pts_lista)
    if vista == "lateral":
        return base

    por_id = {p.id: p for p in pts_lista}
    h_izq, h_der = por_id.get(LADO_IZQ["hombro"]), por_id.get(LADO_DER["hombro"])
    c_izq, c_der = por_id.get(LADO_IZQ["cadera"]), por_id.get(LADO_DER["cadera"])
    if not (h_izq and h_der and c_izq and c_der):
        return base

    m_hom = _PuntoMedio(h_izq, h_der)
    m_cad = _PuntoMedio(c_izq, c_der)
    ancho_hombros = abs(h_izq.x - h_der.x)
    largo_tronco = math.hypot(m_hom.x - m_cad.x, m_hom.y - m_cad.y)
    # Si los hombros están casi superpuestos respecto al largo del tronco, la foto es de perfil.
    if largo_tronco == 0 or (ancho_hombros / largo_tronco) < UMBRAL_ANCHO_TORSO_FRONTAL:
        return base

    if vista == "frontal":
        _extraer_frontal(por_id, base, m_hom, m_cad)
    elif vista == "cenital":
        _extraer_cenital(por_id, base, h_izq, h_der, c_izq, c_der, m_hom, m_cad)

    return base
