"""
Calculadora REBA 100% determinista. Todas las tablas y umbrales salen de
config_normativo/reba_lookup_tables.json (SSOT); aquí no hay números normativos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional

from backend.app.core_ergonomics.modelos import ContextoTarea, NivelReba, Segmento

NIVELES_POR_CLAVE: Dict[str, NivelReba] = {
    "1": "inapreciable", "2": "bajo", "3": "medio", "4": "alto", "5": "muy_alto",
}


@dataclass
class PuntajeSegmento:
    segmento: Segmento
    puntaje: int
    modificadores: List[str] = field(default_factory=list)
    umbrales: List[float] = field(default_factory=list)  # límites angulares relevantes (para "revisar")


@dataclass
class ResultadoRebaCalculado:
    segmentos: Dict[Segmento, PuntajeSegmento]
    grupo_a: int
    grupo_b: int
    tabla_c: int
    carga: int
    agarre: int
    actividad: int
    final: int
    nivel: NivelReba


def _limitar(v: int, minimo: int, maximo: int) -> int:
    return max(minimo, min(maximo, v))


class RebaCalculator:
    def __init__(self, tablas: Mapping[str, Any]):
        self.t = tablas
        self.cfg = tablas["segment_scoring_deg"]

    # ---------- Puntajes por segmento ----------

    def tronco(self, grados: Optional[float], ctx: ContextoTarea) -> PuntajeSegmento:
        c = self.cfg["trunk"]
        lim_flex, lim_ext, tol = c["flexion_limits"], c["extension_limit"], c["upright_tolerance"]
        if grados is None or abs(grados) <= tol:
            base = 1
        elif grados < 0:
            base = 2 if -grados <= lim_ext else 3
        elif grados <= lim_flex[0]:
            base = 2
        elif grados <= lim_flex[1]:
            base = 3
        else:
            base = 4
        mods = ["torsión/inclinación"] if ctx.modificadores.tronco_torsion_o_inclinacion else []
        return PuntajeSegmento("tronco", base + len(mods), mods, [-lim_ext, -tol, tol, *lim_flex])

    def cuello(self, grados: Optional[float], ctx: ContextoTarea) -> PuntajeSegmento:
        c = self.cfg["neck"]
        if grados is None:
            base = 1
        elif grados < -c["extension_tolerance"] or grados > c["flexion_limit"]:
            base = 2
        else:
            base = 1
        mods = ["torsión/inclinación"] if ctx.modificadores.cuello_torsion_o_inclinacion else []
        return PuntajeSegmento("cuello", base + len(mods), mods, [-c["extension_tolerance"], c["flexion_limit"]])

    def piernas(self, flexion_rodilla: Optional[float], ctx: ContextoTarea) -> PuntajeSegmento:
        lim = self.cfg["legs"]["knee_limits"]
        base = 2 if ctx.apoyo_unilateral else 1
        mods = ["apoyo unilateral"] if ctx.apoyo_unilateral else []
        if flexion_rodilla is not None and flexion_rodilla > lim[1]:
            base += 2
            mods.append(f"rodilla > {lim[1]}°")
        elif flexion_rodilla is not None and flexion_rodilla > lim[0]:
            base += 1
            mods.append(f"rodilla {lim[0]}–{lim[1]}°")
        return PuntajeSegmento("piernas", base, mods, list(lim))

    def brazo(self, grados: Optional[float], ctx: ContextoTarea) -> PuntajeSegmento:
        c = self.cfg["upper_arm"]
        lim, lim_ext = c["flexion_limits"], c["extension_limit"]
        if grados is None or -lim_ext <= grados <= lim[0]:
            base = 1
        elif grados < -lim_ext or grados <= lim[1]:
            base = 2
        elif grados <= lim[2]:
            base = 3
        else:
            base = 4
        m = ctx.modificadores
        mods: List[str] = []
        ajuste = 0
        if m.brazo_abducido_o_rotado:
            mods.append("abducido/rotado"); ajuste += 1
        if m.hombro_elevado:
            mods.append("hombro elevado"); ajuste += 1
        if m.brazo_apoyado:
            mods.append("apoyado"); ajuste -= 1
        return PuntajeSegmento("brazo", _limitar(base + ajuste, 1, 6), mods, [-lim_ext, *lim])

    def antebrazo(self, flexion: Optional[float]) -> PuntajeSegmento:
        rango = self.cfg["lower_arm"]["flexion_range"]
        puntaje = 1 if flexion is None or rango[0] <= flexion <= rango[1] else 2
        return PuntajeSegmento("antebrazo", puntaje, [], list(rango))

    def muneca(self, grados: Optional[float], ctx: ContextoTarea) -> PuntajeSegmento:
        lim = self.cfg["wrist"]["limit"]
        base = 1 if grados is None or abs(grados) <= lim else 2
        mods = ["desviación/torsión"] if ctx.modificadores.muneca_desviada_o_torcida else []
        return PuntajeSegmento("muneca", base + len(mods), mods, [-lim, lim])

    # ---------- Factores ----------

    def puntaje_carga(self, ctx: ContextoTarea) -> int:
        c = self.t["load_force_kg"]
        lim_bajo, lim_medio = c.get("thresholds", [5.0, 10.0])
        if ctx.carga_kg < lim_bajo:
            v = c["lt_5"]
        elif ctx.carga_kg <= lim_medio:
            v = c["5_to_10"]
        else:
            v = c["gt_10"]
        return v + (c["shock_add"] if ctx.carga_brusca else 0)

    def nivel(self, final: int) -> NivelReba:
        for clave, banda in self.t["risk_levels"].items():
            lo, hi = banda["score_range"]
            if lo <= final <= hi:
                return NIVELES_POR_CLAVE[clave]
        raise ValueError(f"Puntaje REBA fuera de rango: {final}")

    # ---------- Cálculo completo ----------

    def calcular(self, angulos: Mapping[Segmento, Optional[float]], ctx: ContextoTarea) -> ResultadoRebaCalculado:
        # La vista lateral no mide muñeca: se usa el valor del simulador o el capturado a mano.
        muneca_grados = angulos.get("muneca")
        if muneca_grados is None:
            muneca_grados = ctx.muneca_grados
        segs: Dict[Segmento, PuntajeSegmento] = {
            "tronco": self.tronco(angulos.get("tronco"), ctx),
            "cuello": self.cuello(angulos.get("cuello"), ctx),
            "piernas": self.piernas(angulos.get("piernas"), ctx),
            "brazo": self.brazo(angulos.get("brazo"), ctx),
            "antebrazo": self.antebrazo(angulos.get("antebrazo")),
            "muneca": self.muneca(muneca_grados, ctx),
        }

        ta = self.t["table_a_matrix"]["values"]
        tb = self.t["table_b_matrix"]["values"]
        tc = self.t["table_c_matrix"]
        grupo_a = ta[_limitar(segs["tronco"].puntaje, 1, 5) - 1][_limitar(segs["cuello"].puntaje, 1, 3) - 1][
            _limitar(segs["piernas"].puntaje, 1, 4) - 1]
        grupo_b = tb[_limitar(segs["brazo"].puntaje, 1, 6) - 1][_limitar(segs["antebrazo"].puntaje, 1, 2) - 1][
            _limitar(segs["muneca"].puntaje, 1, 3) - 1]

        carga = self.puntaje_carga(ctx)
        agarre = self.t["coupling_scores"][ctx.agarre]
        puntaje_a = _limitar(grupo_a + carga, 1, 12)
        puntaje_b = _limitar(grupo_b + agarre, 1, 12)
        tabla_c = tc[puntaje_a - 1][puntaje_b - 1]
        final = _limitar(tabla_c + ctx.actividad, 1, 15)

        return ResultadoRebaCalculado(
            segmentos=segs, grupo_a=grupo_a, grupo_b=grupo_b, tabla_c=tabla_c,
            carga=carga, agarre=agarre, actividad=ctx.actividad, final=final, nivel=self.nivel(final),
        )
