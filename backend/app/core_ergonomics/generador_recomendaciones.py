"""
Generador determinista de recomendaciones para casos nuevos (sin LLM: cero alucinaciones).

Cada regla se dispara con umbrales del catálogo normativo y propone una acción con su
efecto esperado (entrada del simulador de riesgo residual). Respeta la jerarquía NOM-036:
primero controles de ingeniería, después métodos de trabajo y medidas administrativas.
El especialista revisa, edita, aprueba o rechaza cada una.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from backend.app.core_ergonomics.modelos import ContextoTarea, Segmento

TAREAS_CON_LEVANTAMIENTO = ("levantamiento", "transporte")


def _g(v: Optional[float]) -> str:
    return f"{v:.0f}°" if v is not None else "—"


def generar(
    angulos: Mapping[Segmento, Optional[float]],
    ctx: ContextoTarea,
    tipo_tarea: str,
    reba_final: int,
    reba_cfg: Mapping[str, Any],
    jabil: Mapping[str, Any],
) -> List[Dict[str, Any]]:
    seg = reba_cfg["segment_scoring_deg"]
    ref = jabil["references"]
    lim_tronco = seg["trunk"]["flexion_limits"][0]
    neutro_tronco = seg["trunk"]["upright_tolerance"]
    lim_brazo = seg["upper_arm"]["flexion_limits"]
    lim_cuello = seg["neck"]["flexion_limit"]
    lim_muneca = seg["wrist"]["limit"]
    lim_rodilla = seg["legs"]["knee_limits"][0]
    altura_min, altura_max = jabil["workstation_geometry"]["recommended_work_height_range_cm"]
    zona = jabil["reach_zones_mm"]["zone_1_2_regular_cycle"]
    limite_kg = jabil["load_limits"]["max_single_person_lift_kg"]
    reposapies = jabil["workstation_geometry"]["footrest_height_range_cm"]
    ley_silla = jabil["chair_law_stps"]

    tronco, brazo, cuello = angulos.get("tronco"), angulos.get("brazo"), angulos.get("cuello")
    muneca = angulos.get("muneca") if angulos.get("muneca") is not None else ctx.muneca_grados
    rodilla = angulos.get("piernas")
    m = ctx.modificadores
    recs: List[Dict[str, Any]] = []

    def agregar(nivel: str, tipo: str, titulo: str, texto: str, referencia: str, efecto: Dict[str, Any]) -> None:
        recs.append({"nivel_control": nivel, "tipo_cambio": tipo, "titulo": titulo, "texto": texto,
                     "referencia": referencia, "efecto": efecto})

    # ---------- Controles de ingeniería (cambios en planta) ----------
    if tipo_tarea in TAREAS_CON_LEVANTAMIENTO and ctx.carga_kg > limite_kg:
        agregar("ingenieria", "planta", "Asistencia mecánica para la carga",
                f"Instalar lifter, mesa elevadora o polipasto: la carga de {ctx.carga_kg:g} kg supera el límite "
                f"Jabil de {limite_kg:g} kg por persona.",
                f"{ref['load_limit']}; NOM-036-1-STPS-2018",
                {"carga_kg": 0, **({"carga_brusca": False} if ctx.carga_brusca else {})})

    if tronco is not None and tronco > lim_tronco:
        agregar("ingenieria", "planta", "Ajustar la altura de la superficie de trabajo",
                f"Colocar la pieza o superficie a la altura de codos ({altura_min:g}–{altura_max:g} cm) para eliminar "
                f"la flexión de tronco de {_g(tronco)}.",
                ref["work_height"],
                {"angulos": {"tronco": neutro_tronco}, "modificadores": {"tronco_torsion_o_inclinacion": False}})

    if (brazo is not None and brazo > lim_brazo[1]) or m.brazo_abducido_o_rotado or m.hombro_elevado:
        agregar("ingenieria", "planta", "Reubicar material a zonas de alcance 1–2",
                f"Acercar herramientas y material a {zona['radius_min_mm']:g}–{zona['radius_max_mm']:g} mm del "
                f"operador; el brazo trabaja a {_g(brazo)} de flexión.",
                ref["reach_zones"],
                {"angulos": {"brazo": lim_brazo[0]},
                 "modificadores": {"brazo_abducido_o_rotado": False, "hombro_elevado": False}})

    if cuello is not None and cuello > lim_cuello:
        agregar("ingenieria", "planta", "Elevar la pieza o el monitor a la línea de visión",
                f"Inclinar o elevar la pieza, plantilla o pantalla para reducir la flexión de cuello de {_g(cuello)}.",
                ref["work_height"], {"angulos": {"cuello": lim_cuello / 2}})

    if (muneca is not None and abs(muneca) > lim_muneca) or m.muneca_desviada_o_torcida:
        agregar("ingenieria", "planta", "Herramienta o sujeción con muñeca neutra",
                f"Usar herramienta de empuñadura en ángulo, balanceador o reorientar la pieza para mantener la "
                f"muñeca recta (actual: {_g(muneca)}).",
                "NOM-036-1-STPS-2018", {"angulos": {"muneca": 0}, "modificadores": {"muneca_desviada_o_torcida": False}})

    if (rodilla is not None and rodilla > lim_rodilla) or ctx.apoyo_unilateral:
        agregar("ingenieria", "planta", "Plataforma o reposapiés para postura estable",
                f"Nivelar la estación o instalar reposapiés de {reposapies[0]:g}–{reposapies[1]:g} cm para apoyar "
                f"ambos pies (flexión de rodilla actual: {_g(rodilla)}).",
                ref["footrest"], {"angulos": {"piernas": 0}, "apoyo_unilateral": False})

    # ---------- Método de trabajo y medidas administrativas ----------
    if tronco is not None and tronco > lim_tronco:
        objetivo = round(max(tronco - 15, neutro_tronco), 1)
        agregar("administrativo", "postura", "Corregir técnica de trabajo",
                f"Capacitar al operador para flexionar rodillas y reducir la flexión de tronco de {_g(tronco)} a "
                f"{_g(objetivo)} mientras se implementan los cambios en planta.",
                "NOM-036-1-STPS-2018 capacitación", {"angulos": {"tronco": objetivo}})

    if reba_final >= 4:
        agregar("administrativo", "administrativo", "Rotación de puesto y pausas",
                f"Rotar entre esta estación y una de bajo riesgo; no exceder {ley_silla['max_continuous_standing_hours']:g} h "
                f"de pie continuas con pausas de {ley_silla['mandatory_break_minutes']:g} min.",
                ref["chair_law"], {"actividad": max(ctx.actividad - 1, 0)} if ctx.actividad > 0 else {})

    for i, r in enumerate(recs, start=1):
        r["id"] = f"R{i}"
        r["efecto"] = _sin_cambios_nulos(r["efecto"], angulos, ctx)
    return recs


def _sin_cambios_nulos(efecto: Dict[str, Any], angulos: Mapping[Segmento, Optional[float]],
                       ctx: ContextoTarea) -> Dict[str, Any]:
    """Quita del efecto los modificadores que ya tienen el valor objetivo (no son un cambio real)."""
    mods = {k: v for k, v in efecto.get("modificadores", {}).items() if getattr(ctx.modificadores, k) != v}
    resultado = {k: v for k, v in efecto.items() if k != "modificadores"}
    if mods:
        resultado["modificadores"] = mods
    if resultado.get("apoyo_unilateral") is False and not ctx.apoyo_unilateral:
        del resultado["apoyo_unilateral"]
    return resultado
