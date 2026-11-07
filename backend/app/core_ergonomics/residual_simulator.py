"""Simulador de riesgo residual: aplica los efectos esperados de las recomendaciones y recalcula REBA."""

from __future__ import annotations

from typing import Dict, Iterable, Optional

from backend.app.core_ergonomics.modelos import ContextoTarea, Efecto, Segmento
from backend.app.core_ergonomics.reba_calculator import RebaCalculator, ResultadoRebaCalculado


def aplicar_efectos(
    angulos: Dict[Segmento, Optional[float]], ctx: ContextoTarea, efectos: Iterable[Efecto]
) -> tuple[Dict[Segmento, Optional[float]], ContextoTarea]:
    nuevos = dict(angulos)
    datos = ctx.model_dump()
    for ef in efectos:
        nuevos.update(ef.angulos)
        for campo in ("carga_kg", "carga_brusca", "agarre", "actividad", "apoyo_unilateral"):
            valor = getattr(ef, campo)
            if valor is not None:
                datos[campo] = valor
        for nombre, valor in ef.modificadores.items():
            if nombre not in datos["modificadores"]:
                raise ValueError(f"Modificador desconocido en efecto: {nombre}")
            datos["modificadores"][nombre] = valor
    return nuevos, ContextoTarea.model_validate(datos)


def simular(
    calc: RebaCalculator,
    angulos: Dict[Segmento, Optional[float]],
    ctx: ContextoTarea,
    efectos: Iterable[Efecto],
) -> ResultadoRebaCalculado:
    """
    Aplica varias acciones juntas. Si dos ajustan el mismo parámetro, prevalece la de mayor
    reducción individual: se aplican de menor a mayor efecto, así la más efectiva queda al final.
    """
    lista = list(efectos)
    if len(lista) > 1:
        def impacto(e: Efecto) -> tuple[int, int]:
            r = calc.calcular(*aplicar_efectos(angulos, ctx, [e]))
            # Desempate por puntajes de segmento: a igual REBA final, gana la que más reduce la postura.
            return (-r.final, -sum(s.puntaje for s in r.segmentos.values()))
        lista.sort(key=impacto)
    nuevos_angulos, nuevo_ctx = aplicar_efectos(angulos, ctx, lista)
    return calc.calcular(nuevos_angulos, nuevo_ctx)
