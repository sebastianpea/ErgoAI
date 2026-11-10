"""
Llenado de la hoja oficial de Jabil 16-PE80-6500-00014-H (.xlsm) a partir de uno o varios casos.

- Hoja "Mov" (Evaluación de ergonomía): una por operador ("Mov", "Mov (2)", …). La sección D lleva los
  puntajes REBA del sistema (decisión del equipo), con las etiquetas de puntaje final y nivel ajustadas.
- Hoja NOM-036 que corresponde a la tarea: "x" en la columna del color de cada factor. Las filas y los
  puntajes por columna se leen de la propia plantilla (incisos a), b)… y sus fórmulas), no se copian aquí.
- "OBSERVACIONES Y MEJORAS": recomendaciones validadas por el especialista.
- "Fotos de la estacion": fotos anonimizadas con el esqueleto, una fila por operador.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

from backend.app.api.schemas import CasoDetalle, Hoja14H
from backend.app.services.plantilla_xlsx import LibroPlantilla, Valor, separar_ref

HOJA_PRINCIPAL = "Mov"
HOJA_OBSERVACIONES = "OBSERVACIONES Y MEJORAS"
HOJA_FOTOS = "Fotos de la estacion"

MESES_FECHA = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
# Lista desplegable de meses de la hoja de observaciones (tal cual está en la plantilla, incluido "Apr")
MESES_OBSERVACIONES = ["Ene", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

# A. Una casilla por zona: marcar cualquiera de la fila hace que la sección tome esa zona.
CASILLA_ZONA = {5: "AB2", 4: "V4", 3: "Z6", 2: "AB8", 1: "AD9"}
TIPO_TRABAJO = {"Precisión": "Precisión", "Ligero": " Ligero", "Esfuerzo": "Esfuerzo"}  # " Ligero": así viene
FRECUENCIA = {"0.2_o_menos": "L83", "0.2_2": "L84", "2_20": "L85", "mas_20": "L86"}
DURACION_TAREA = {"hasta_1h": "L89", "1_2h": "L90", "mas_2h": "L91"}
NIVEL_REBA_14H = {"inapreciable": 1, "bajo": 1, "medio": 2, "alto": 3, "muy_alto": 4}

HOJA_NOM036 = {
    "levantamiento": "Levantamiento (1)",
    "transporte": "Transporte (2)",
    "empuje_sin_auxiliar": "sin auxiliar (4)",
    "empuje_con_auxiliar": "con auxiliar (5)",
}
HOJA_EQUIPO = "Equipo (3)"


@dataclass
class OperadorExport:
    caso: CasoDetalle
    realizado_por: str
    fotos: List[Tuple[bytes, int, int, str]] = field(default_factory=list)  # (jpg, ancho, alto, descripción)


def _fecha_hoja(iso: str) -> str:
    try:
        d = datetime.fromisoformat(iso).date()
    except ValueError:
        d = date.today()
    return f"{d.day:02d}/{MESES_FECHA[d.month - 1]}/{d.year}"


def _altura_area(h: Hoja14H, caso: CasoDetalle) -> Optional[str]:
    if h.altura_area:
        return h.altura_area
    cm = caso.contexto.altura_trabajo_cm
    if cm is None:
        return None
    if 95 < cm < 120:
        return ">95<120"
    if 120 <= cm <= 130:
        return ">120<130"
    return "<95>130"


def _rango(col: str, desde: int, hasta: int) -> List[str]:
    return [f"{col}{f}" for f in range(desde, hasta + 1)]


# Celdas de captura de "Mov". La plantilla de Jabil trae datos de ejemplo en algunas (p. ej. 6 kg en K55):
# se vacían todas y solo se escribe lo que viene del caso. Nunca se tocan celdas con fórmula.
CAPTURA_MOV: List[str] = (
    _rango("E", 2, 7) + ["L37", "L38", "L39", "L40", "L41", "L42", "L43", "L44", "L47", "L48", "L49", "L50"]
    + ["K55", "K56"] + _rango("L", 60, 72) + ["L75", "L76", "L79", "L80"] + _rango("L", 83, 86) + _rango("L", 89, 91)
    + ["L99", "L107", "L116", "L125", "L130", "L134", "L140", "L148", "L157", "L164", "L169"]
    + _rango("G", 182, 185) + ["G193", "G194", "G195", "G196", "C199", "C200", "C201", "C208"]
)
ENCABEZADO = ("negocio", "linea", "area", "modelo")


def valores_mov(caso: CasoDetalle, realizado_por: str,
                encabezado_grupo: Optional[Hoja14H] = None) -> Tuple[Dict[str, Valor], Dict[str, bool]]:
    """Celdas de la hoja 'Mov' y casillas de zona para un operador."""
    h = caso.hoja_14h
    if encabezado_grupo is not None:  # en un grupo, el encabezado capturado en el operador 1 vale para todos
        h = h.model_copy(update={k: getattr(h, k) or getattr(encabezado_grupo, k) for k in ENCABEZADO})
    v: Dict[str, Valor] = {
        "E2": h.negocio or None,
        "E3": h.linea or caso.estacion,
        "E4": h.area or None,
        "E5": _fecha_hoja(caso.fecha),
        "E6": h.modelo or None,
        "E7": realizado_por,
    }
    # B. Área de trabajo
    v.update({
        "L37": h.posicion, "L38": h.espacio_pies_cm,
        "L39": None if h.tapete_antifatiga is None else ("Si" if h.tapete_antifatiga else "No"),
        "L40": h.reposapies_altura_cm, "L41": h.reposapies_profundidad_cm, "L42": _altura_area(h, caso),
        "L43": TIPO_TRABAJO.get(h.tipo_trabajo or ""), "L44": h.tiempo_posicion,
        "L47": h.piernas_profundidad_cm, "L48": h.piernas_ancho_cm, "L49": h.asiento_cm, "L50": h.espesor_mesa_cm,
    })
    # C. Fuerza
    kg = h.fuerza_kg if h.fuerza_kg is not None else (caso.contexto.carga_kg or None)
    v["K55"] = kg
    if h.tipo_accion is not None:
        v[f"L{60 + h.tipo_accion}"] = "X"
    if h.velocidad:
        v["L75" if h.velocidad == "inmovil" else "L76"] = "X"
    if h.duracion_accion:
        v["L79" if h.duracion_accion == "menos_3s" else "L80"] = "X"
    if h.frecuencia:
        v[FRECUENCIA[h.frecuencia]] = "X"
    if h.duracion_tarea:
        v[DURACION_TAREA[h.duracion_tarea]] = "X"

    # D. Puntajes REBA por segmento (el sistema evalúa con REBA)
    puntos = {a.segmento: a.puntaje_reba for a in caso.angulos}
    if caso.reba is not None:
        desviada = caso.contexto.modificadores.muneca_desviada_o_torcida
        actividad = 1 if caso.reba.actividad > 0 else 0
        v.update({
            "L99": puntos.get("brazo"), "L107": puntos.get("antebrazo"), "L116": puntos.get("muneca"),
            "L125": 2 if desviada else 1, "L130": actividad, "L134": caso.reba.carga,
            "L140": puntos.get("cuello"), "L148": puntos.get("tronco"), "L157": puntos.get("piernas"),
            "L164": actividad, "L169": caso.reba.carga,
            "B172": "Puntuación final REBA (1-15):", "L172": caso.reba.final,
            "B174": "Nivel de riesgo REBA (1-4):", "L174": NIVEL_REBA_14H[caso.reba.nivel],
        })

    # E. Accesibilidad ("Si" = cumple)
    for celda, valor in (("G182", h.acceso_800mm), ("G183", h.distancia_operadores_800mm),
                         ("G184", h.libertad_superiores), ("G185", h.libertad_inferiores)):
        if valor is not None:
            v[celda] = "Si" if valor else "No"
    # F. Visual
    if h.ayuda_visual_altura:
        v["G193" if h.ayuda_visual_altura == "1400_1600" else "G194"] = "X"
    v["G196"] = h.visualizacion
    # G. Iluminación y H. Evaluación del operador
    v.update({"C199": h.iluminacion_actividad, "C200": h.iluminacion_lux, "C201": h.reflexion_lux,
              "C208": h.evaluacion_operador})

    limpio: Dict[str, Valor] = {celda: None for celda in CAPTURA_MOV}  # borra los datos de ejemplo
    limpio.update({k: x for k, x in v.items() if x is not None})
    # Todas las casillas de zona se desmarcan y solo se marca la capturada.
    casillas = {celda: False for celda in CASILLA_ZONA.values()}
    if h.zona_maxima:
        casillas[CASILLA_ZONA[h.zona_maxima]] = True
    return limpio, casillas


def limpiar_marcas_nom036(libro: LibroPlantilla, hoja: str) -> Dict[str, Valor]:
    """Celdas con 'x' de ejemplo dentro de los rangos de captura de una hoja NOM-036 (se vacían)."""
    filas_columnas = set()
    for rango in libro.rangos_validacion(hoja):
        a, _, b = rango.partition(":")
        try:
            (c1, f1), (c2, f2) = separar_ref(a), separar_ref(b or a)
        except Exception:
            continue
        for f in range(f1, f2 + 1):
            for c in range(ord(c1), ord(c2) + 1):
                filas_columnas.add(f"{chr(c)}{f}")
    return {ref: None for ref, texto in libro.textos(hoja).items()
            if ref in filas_columnas and texto.strip().lower() == "x"}


def marcas_nom036(libro: LibroPlantilla, hoja: str, factores: List[Tuple[str, int]]) -> Dict[str, str]:
    """
    Celdas donde va la "x" para cada factor (letra del inciso, puntaje).
    Fila: primer rango con lista desplegable en columnas E–H debajo del inciso "a)", "b)"…
    Columna: la que la fórmula de la hoja puntúa igual al valor calculado.
    """
    textos = libro.textos(hoja)
    incisos: Dict[str, int] = {}
    for ref, texto in textos.items():
        col, fila = separar_ref(ref)
        m = re.fullmatch(r"\s*([a-kA-K])\)\s*", texto)
        if col == "A" and m:
            incisos.setdefault(m.group(1).upper(), fila)
    filas_captura = []
    for rango in libro.rangos_validacion(hoja):
        inicio = rango.split(":")[0]
        try:
            col, fila = separar_ref(inicio)
        except Exception:
            continue
        if col == "E":
            filas_captura.append(fila)
    filas_captura.sort()
    puntaje_por_celda: Dict[int, Dict[str, int]] = {}
    for formula in libro.formulas(hoja).values():
        for col, fila, pts in re.findall(r'IF\(\$?([E-H])\$?(\d+)="x",(\d+)', formula, re.I):
            puntaje_por_celda.setdefault(int(fila), {})[col.upper()] = int(pts)

    incisos_ordenados = sorted(incisos.items(), key=lambda kv: kv[1])
    marcas: Dict[str, str] = {}
    for letra, valor in factores:
        letra = letra.upper()
        if letra not in incisos:
            continue
        inicio = incisos[letra]
        siguiente = next((f for _, f in incisos_ordenados if f > inicio), 10**6)
        fila = next((f for f in filas_captura if inicio <= f < siguiente), None)
        if fila is None or fila not in puntaje_por_celda:
            continue
        columnas = puntaje_por_celda[fila]
        exactas = sorted(c for c, p in columnas.items() if p == valor)
        if exactas:
            col = exactas[0]  # si dos columnas valen igual, la de la izquierda (la que tiene encabezado)
        else:  # el valor no está en la hoja: la columna de puntaje inmediato inferior
            menores = [c for c, p in columnas.items() if p <= valor]
            col = max(menores, key=lambda c: columnas[c]) if menores else min(columnas, key=lambda c: columnas[c])
        marcas[f"{col}{fila}"] = "x"
    return marcas


def _inciso_observacion(rec) -> str:
    parametros = {c.parametro for c in rec.cambios}
    if "carga_kg" in parametros or "carga_brusca" in parametros:
        return "C"
    return "D"


def generar_hoja_14h(plantilla: bytes, operadores: List[OperadorExport], tablas_nom036: Dict) -> bytes:
    if not operadores:
        raise ValueError("No hay casos que exportar")
    libro = LibroPlantilla(plantilla)

    # Las copias de "Mov" se crean antes de llenar para que partan de la plantilla en blanco.
    hojas_mov = [HOJA_PRINCIPAL] + [f"{HOJA_PRINCIPAL} ({i})" for i in range(2, len(operadores) + 1)]
    for nombre in hojas_mov[1:]:
        libro.duplicar_hoja(HOJA_PRINCIPAL, nombre)

    encabezado = operadores[0].caso.hoja_14h if len(operadores) > 1 else None
    for hoja, op in zip(hojas_mov, operadores):
        valores, casillas = valores_mov(op.caso, op.realizado_por, encabezado)
        libro.escribir(hoja, valores)
        libro.marcar_casillas(hoja, casillas)

    # Las hojas NOM-036 de la plantilla traen "x" de ejemplo: se limpian todas antes de marcar.
    for hoja_nom in list(HOJA_NOM036.values()) + [HOJA_EQUIPO]:
        if hoja_nom in libro.nombres_hojas() and (limpiar := limpiar_marcas_nom036(libro, hoja_nom)):
            libro.escribir(hoja_nom, limpiar)

    # Hoja NOM-036 de la tarea (con varios operadores comparten la misma carga: se usa el primero)
    principal = operadores[0].caso
    if principal.nom036 is not None:
        en_equipo = principal.tipo_tarea == "levantamiento" and principal.contexto.personas_en_carga >= 2
        hoja_nom = HOJA_EQUIPO if en_equipo else HOJA_NOM036.get(principal.nom036.metodo)
        if hoja_nom and hoja_nom in libro.nombres_hojas():
            factores = [(f.codigo, f.valor) for f in principal.nom036.factores if re.fullmatch(r"[A-Ka-k]", f.codigo)]
            marcas = marcas_nom036(libro, hoja_nom, factores)
            if marcas:
                libro.escribir(hoja_nom, marcas)

    # Observaciones y mejoras: solo recomendaciones validadas por el especialista
    filas: Dict[str, Valor] = {}
    fila = 3
    for hoja, op in zip(hojas_mov, operadores):
        for r in op.caso.recomendaciones:
            if r.estado not in ("aprobada", "editada_aprobada") or r.implementacion == "denegada":
                continue
            filas[f"B{fila}"] = hoja
            filas[f"C{fila}"] = _inciso_observacion(r)
            filas[f"D{fila}"] = r.titulo
            filas[f"E{fila}"] = r.texto
            if r.responsable:
                filas[f"F{fila}"] = r.responsable
            if r.fecha_compromiso:
                d = date.fromisoformat(r.fecha_compromiso)
                filas[f"G{fila}"] = d.day
                filas[f"H{fila}"] = MESES_OBSERVACIONES[d.month - 1]
                filas[f"I{fila}"] = d.year
            fila += 1
            if fila > 50:  # la lista de la plantilla llega a la fila 50
                break
    if filas:
        libro.escribir(HOJA_OBSERVACIONES, filas)

    # Fotos de la estación: una fila por operador
    filas_fotos = [op.fotos for op in operadores if op.fotos]
    if filas_fotos and HOJA_FOTOS in libro.nombres_hojas():
        libro.agregar_imagenes(HOJA_FOTOS, filas_fotos)

    libro.preparar_recalculo()
    return libro.guardar()
