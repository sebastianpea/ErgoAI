"""
Motor determinista NOM-036-1-STPS-2018 y formato Jabil 16-PE80-6500-00014-H.xlsm.
Implementa el Patrón Strategy para aislar el cálculo matemático de las 5 hojas:
  1. Levantamiento (1)
  2. Transporte (2)
  3. Equipo (3)
  4. sin auxiliar (4)
  5. con auxiliar (5)

El Agente IA (LLM) tiene prohibido calcular puntajes; este módulo produce el
dictamen matemático inmutable consultando el catálogo estático en RAM.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Type


def total_factores(valores: Iterable[int]) -> int:
    """Suma determinista de los factores evaluados en la hoja activa."""
    return sum(valores)


def color_total(total: int, tablas: Mapping[str, Any]) -> str:
    """Determina el color de banda (verde, amarillo, rojo, morado) según nom036_mac_rapp_tables.json."""
    for banda in tablas["total_score_bands"]:
        if banda["min"] <= total <= banda["max"]:
            return banda["color"]
    raise ValueError(f"Total NOM-036 fuera de las bandas configuradas: {total}")


def nivel_riesgo_texto(color: str, tablas: Mapping[str, Any] | None = None) -> str:
    """Convierte el color de banda NOM-036 en la etiqueta de nivel de riesgo inmutable."""
    c_norm = color.lower()
    if tablas:
        for banda in tablas.get("total_score_bands", []):
            if str(banda.get("color", "")).lower() == c_norm and "nivel" in banda:
                return str(banda["nivel"])
        banda_rb = tablas.get("risk_bands", {}).get(color.upper())
        if isinstance(banda_rb, Mapping) and "level" in banda_rb:
            return str(banda_rb["level"])
    mapa = {
        "verde": "Bajo",
        "amarillo": "Medio",
        "naranja": "Medio",
        "rojo": "Alto",
        "morado": "Muy Alto",
    }
    return mapa.get(c_norm, "Medio")


def _color_factor(valor: int, tablas: Mapping[str, Any] | None = None) -> str:
    if tablas and "factor_color_bands" in tablas:
        for b in tablas["factor_color_bands"]:
            if valor <= int(b["max"]):
                return str(b["color"])
    if valor <= 0:
        return "verde"
    if valor <= 2:
        return "amarillo"
    if valor <= 5:
        return "naranja"
    if valor <= 10:
        return "rojo"
    return "morado"


def _umbrales_postura(tablas: Mapping[str, Any]) -> tuple[float, float, float, float]:
    ang = tablas.get("posture_angle_thresholds_deg", {})
    return (
        float(ang.get("trunk_moderate", 20.0)),
        float(ang.get("trunk_severe", 45.0)),
        float(ang.get("arm_moderate", 25.0)),
        float(ang.get("arm_severe", 45.0)),
    )


def _puntaje_por_umbrales(valor: float, umbrales: List[float], puntajes: List[int]) -> int:
    for idx, lim in enumerate(umbrales):
        if valor <= float(lim):
            return int(puntajes[idx])
    return int(puntajes[-1])


@dataclass(frozen=True)
class FactorEvaluado:
    codigo: str
    etiqueta: str
    color: str
    valor: int


@dataclass(frozen=True)
class ResultadoCalculoNom036:
    tipo_operacion: str
    hoja_excel: str
    metodo_api: str
    total: int
    color: str
    nivel_riesgo: str
    resumen_inmutable: str
    factores: List[FactorEvaluado]


class EstrategiaEvaluacionNom036(ABC):
    """Interfaz base del Patrón Strategy para cada prueba de 16-PE80-6500-00014-H.xlsm."""

    hoja_excel: str
    metodo_api: str

    @abstractmethod
    def calcular_factores(
        self, datos: Mapping[str, Any], tablas: Mapping[str, Any]
    ) -> List[FactorEvaluado]:
        """Calcula de forma aislada los factores exclusivos de esta prueba."""

    def evaluar(
        self, datos: Mapping[str, Any], tablas: Mapping[str, Any]
    ) -> ResultadoCalculoNom036:
        factores = self.calcular_factores(datos, tablas)
        puntaje_total = total_factores(f.valor for f in factores)
        color = color_total(puntaje_total, tablas)
        nivel = nivel_riesgo_texto(color, tablas)
        resumen = f"Riesgo {nivel}, {puntaje_total} puntos (Hoja: {self.hoja_excel})"
        return ResultadoCalculoNom036(
            tipo_operacion=self.hoja_excel,
            hoja_excel=self.hoja_excel,
            metodo_api=self.metodo_api,
            total=puntaje_total,
            color=color,
            nivel_riesgo=nivel,
            resumen_inmutable=resumen,
            factores=factores,
        )


class EstrategiaLevantamiento(EstrategiaEvaluacionNom036):
    """Hoja 1: Levantamiento (1) - Método MAC de levantamiento individual."""

    hoja_excel = "Levantamiento (1)"
    metodo_api = "levantamiento"

    def calcular_factores(
        self, datos: Mapping[str, Any], tablas: Mapping[str, Any]
    ) -> List[FactorEvaluado]:
        cfg = tablas.get("sheets_mapping", {}).get("levantamiento_1", {})
        comunes = tablas.get("common_factor_scores", {})
        tronco_mod, tronco_sev, brazo_mod, brazo_sev = _umbrales_postura(tablas)

        lim_seguro = float(cfg.get("safe_weight_kg", 7.0))
        lim_jabil = float(cfg.get("jabil_restrictive_weight_kg", 14.0))
        lim_nom = float(cfg.get("max_acceptable_weight_kg", 25.0))
        pesos_pts = cfg.get("weight_scores", [0, 4, 6, 10])
        umb_dist_cm = cfg.get("horizontal_distance_thresholds_cm", [25.0, 45.0])
        def_dist_cm = cfg.get("default_horizontal_distances_cm", [20.0, 30.0, 46.0])
        dist_pts = comunes.get("horizontal_distance_scores", [0, 3, 6])
        vert_pts = comunes.get("vertical_region_scores", [0, 1, 3])
        torsion_pto = int(comunes.get("torsion_score", 2))
        agarre_mapa = comunes.get("coupling_scores", {"bueno": 0, "regular": 1, "malo": 2, "inaceptable": 2})

        carga_kg = float(datos.get("carga_kg", 0.0))
        tronco = float(datos.get("tronco_grados") or 0.0)
        brazo = float(datos.get("brazo_grados") or 0.0)
        torsion = bool(datos.get("torsion_tronco", False))
        agarre = str(datos.get("agarre", "bueno")).lower()

        # a) Peso vs Frecuencia
        pts_peso = _puntaje_por_umbrales(carga_kg, [lim_seguro, lim_jabil, lim_nom], pesos_pts)

        # b) Distancia horizontal manos-espalda baja
        dist_inferida = def_dist_cm[2] if brazo > brazo_sev else (def_dist_cm[1] if brazo > brazo_mod else def_dist_cm[0])
        dist_cm = float(datos.get("distancia_horizontal_cm", dist_inferida))
        pts_dist = _puntaje_por_umbrales(dist_cm, umb_dist_cm, dist_pts)

        # c) Región de levantamiento vertical
        pts_vert = _puntaje_por_umbrales(tronco, [tronco_mod, tronco_sev], vert_pts)

        # d) Torsión y flexión lateral del torso
        pts_torsion = torsion_pto if torsion else 0

        # f) Acoplamiento mano-carga
        pts_agarre = int(agarre_mapa.get(agarre, 2))

        return [
            FactorEvaluado("A", "Peso y frecuencia de la carga", _color_factor(pts_peso, tablas), pts_peso),
            FactorEvaluado("B", "Distancia horizontal manos-espalda baja", _color_factor(pts_dist, tablas), pts_dist),
            FactorEvaluado("C", "Región de levantamiento vertical", _color_factor(pts_vert, tablas), pts_vert),
            FactorEvaluado("D", "Torsión y flexión lateral del torso", _color_factor(pts_torsion, tablas), pts_torsion),
            FactorEvaluado("F", "Acoplamiento mano-carga", _color_factor(pts_agarre, tablas), pts_agarre),
        ]


class EstrategiaTransporte(EstrategiaEvaluacionNom036):
    """
    Hoja 2: Transporte (2) - Cálculo aislado para transporte manual.
    Aplica exclusivamente carga asimétrica sobre el torso y distancia de transporte (sin región vertical ni ruedas).
    """

    hoja_excel = "Transporte (2)"
    metodo_api = "transporte"

    def calcular_factores(
        self, datos: Mapping[str, Any], tablas: Mapping[str, Any]
    ) -> List[FactorEvaluado]:
        cfg = tablas.get("sheets_mapping", {}).get("transporte_2", {})
        comunes = tablas.get("common_factor_scores", {})
        _, _, brazo_mod, brazo_sev = _umbrales_postura(tablas)

        lim_seguro = float(cfg.get("safe_weight_kg", 7.0))
        lim_jabil = float(cfg.get("jabil_restrictive_weight_kg", 14.0))
        lim_nom = float(cfg.get("max_acceptable_weight_kg", 25.0))
        pesos_pts = cfg.get("weight_scores", [0, 4, 6, 10])
        umb_dist_m = cfg.get("distance_thresholds_m", [4.0, 10.0])
        def_dist_m = cfg.get("default_distances_m", [4.0, 12.0])
        mapa_asim = cfg.get("asymmetry_scores", {"simetrica": 0, "leve": 1, "lateral": 2, "un_hombro": 3, "severa": 3})
        dist_manos_pts = comunes.get("horizontal_distance_scores", [0, 3, 6])
        viaje_pts = comunes.get("travel_distance_scores", [0, 1, 3])
        obst_pts = comunes.get("route_obstacles_scores", [0, 1, 3])
        agarre_mapa = comunes.get("coupling_scores", {"bueno": 0, "regular": 1, "malo": 2, "inaceptable": 2})

        carga_kg = float(datos.get("carga_kg", 0.0))
        brazo = float(datos.get("brazo_grados") or 0.0)
        asimetria = datos.get("asimetria_torso", "lateral" if datos.get("apoyo_unilateral") or datos.get("torsion_tronco") else "simetrica")
        distancia_m = float(datos.get("distancia_transporte_m", def_dist_m[1] if datos.get("actividad", 0) >= 2 else def_dist_m[0]))
        obstaculos = int(datos.get("obstaculos_ruta", 0))
        agarre = str(datos.get("agarre", "bueno")).lower()

        # a) Peso vs Frecuencia
        pts_peso = _puntaje_por_umbrales(carga_kg, [lim_seguro, lim_jabil, lim_nom], pesos_pts)

        # b) Distancia horizontal manos-espalda baja
        pts_dist_manos = _puntaje_por_umbrales(brazo, [brazo_mod, brazo_sev], dist_manos_pts)

        # c) Carga asimétrica sobre el torso - EXCLUSIVO DE TRANSPORTE (2)
        if isinstance(asimetria, (int, float)):
            pts_asimetria = max(0, min(max(mapa_asim.values()), int(asimetria)))
        else:
            pts_asimetria = int(mapa_asim.get(str(asimetria).lower(), mapa_asim.get("lateral", 2)))

        # h) Distancia de transporte - EXCLUSIVO DE TRANSPORTE (2)
        pts_distancia = _puntaje_por_umbrales(distancia_m, umb_dist_m, viaje_pts)

        # j) Obstáculos en la ruta / escaleras
        pts_obstaculos = _puntaje_por_umbrales(float(obstaculos), [0.0, 1.0], obst_pts)

        # e) Acoplamiento mano-carga
        pts_agarre = int(agarre_mapa.get(agarre, 2))

        return [
            FactorEvaluado("A", "Peso y frecuencia de transporte", _color_factor(pts_peso, tablas), pts_peso),
            FactorEvaluado("B", "Distancia horizontal manos-espalda", _color_factor(pts_dist_manos, tablas), pts_dist_manos),
            FactorEvaluado("C", "Carga asimétrica sobre el torso", _color_factor(pts_asimetria, tablas), pts_asimetria),
            FactorEvaluado("E", "Acoplamiento mano-carga", _color_factor(pts_agarre, tablas), pts_agarre),
            FactorEvaluado("H", "Distancia de transporte", _color_factor(pts_distancia, tablas), pts_distancia),
            FactorEvaluado("J", "Obstáculos en la ruta", _color_factor(pts_obstaculos, tablas), pts_obstaculos),
        ]


class EstrategiaEquipo(EstrategiaEvaluacionNom036):
    """
    Hoja 3: Equipo (3) - Levantamiento en equipo (2 a 4 personas).
    Evalúa peso por número de operadores y comunicación, coordinación y control.
    """

    hoja_excel = "Equipo (3)"
    metodo_api = "levantamiento"

    def calcular_factores(
        self, datos: Mapping[str, Any], tablas: Mapping[str, Any]
    ) -> List[FactorEvaluado]:
        cfg = tablas.get("sheets_mapping", {}).get("equipo_3", {})
        comunes = tablas.get("common_factor_scores", {})
        tronco_mod, tronco_sev, brazo_mod, brazo_sev = _umbrales_postura(tablas)

        lim_eq = cfg.get("team_limits_kg", {})
        pesos_pts = cfg.get("weight_scores", [0, 4, 6, 10])
        mapa_coord = cfg.get("coordination_scores", {"buena": 0, "regular": 1, "deficiente": 3, "mala": 3})
        dist_pts = comunes.get("horizontal_distance_scores", [0, 3, 6])
        vert_pts = comunes.get("vertical_region_scores", [0, 1, 3])

        carga_kg = float(datos.get("carga_kg", 0.0))
        operadores = max(2, min(4, int(datos.get("num_operadores", 2))))
        coordinacion = str(datos.get("coordinacion", "buena")).lower()
        tronco = float(datos.get("tronco_grados") or 0.0)
        brazo = float(datos.get("brazo_grados") or 0.0)

        # a) Peso según número de operadores (Estándar Jabil 6.4.2)
        if operadores == 2:
            v_lim = float(lim_eq.get("2_personas_verde", 19.0))
            n_lim = float(lim_eq.get("2_personas_naranja", 28.0))
            r_lim = float(lim_eq.get("2_personas_rojo", 40.0))
            pts_peso = pesos_pts[0] if carga_kg < v_lim else (pesos_pts[1] if carga_kg < n_lim else (pesos_pts[2] if carga_kg <= r_lim else pesos_pts[3]))
        elif operadores == 3:
            v_lim = float(lim_eq.get("3_personas_verde", 23.0))
            n_lim = float(lim_eq.get("3_personas_naranja", 42.0))
            r_lim = float(lim_eq.get("3_personas_rojo", 56.0))
            pts_peso = pesos_pts[0] if carga_kg < v_lim else (pesos_pts[1] if carga_kg < n_lim else (pesos_pts[2] if carga_kg <= r_lim else pesos_pts[3]))
        else:
            v_lim = float(lim_eq.get("4_personas_verde", 23.0))
            n_lim = float(lim_eq.get("4_personas_naranja", 56.0))
            pts_peso = pesos_pts[0] if carga_kg < v_lim else (pesos_pts[1] if carga_kg < n_lim else pesos_pts[3])

        pts_dist = _puntaje_por_umbrales(brazo, [brazo_mod, brazo_sev], dist_pts)
        pts_vert = _puntaje_por_umbrales(tronco, [tronco_mod, tronco_sev], vert_pts)

        # i) Comunicación, coordinación y control
        pts_coord = int(mapa_coord.get(coordinacion, 1))

        return [
            FactorEvaluado("A", f"Peso en equipo ({operadores} operadores)", _color_factor(pts_peso, tablas), pts_peso),
            FactorEvaluado("B", "Distancia horizontal manos-espalda", _color_factor(pts_dist, tablas), pts_dist),
            FactorEvaluado("C", "Región de levantamiento vertical", _color_factor(pts_vert, tablas), pts_vert),
            FactorEvaluado("I", "Comunicación, coordinación y control", _color_factor(pts_coord, tablas), pts_coord),
        ]


class EstrategiaSinAuxiliar(EstrategiaEvaluacionNom036):
    """
    Hoja 4: sin auxiliar (4) - Empuje y arrastre sin equipo rodante (rodando, girando, arrastrando).
    """

    hoja_excel = "sin auxiliar (4)"
    metodo_api = "empuje_sin_auxiliar"

    def calcular_factores(
        self, datos: Mapping[str, Any], tablas: Mapping[str, Any]
    ) -> List[FactorEvaluado]:
        cfg = tablas.get("sheets_mapping", {}).get("sin_auxiliar_4", {})
        comunes = tablas.get("common_factor_scores", {})
        tronco_mod, tronco_sev, _, _ = _umbrales_postura(tablas)

        umb_peso = cfg.get("weight_thresholds_kg", [10.0, 14.0, 25.0])
        pesos_pts = cfg.get("weight_scores", [0, 2, 4, 8])
        umb_dist = cfg.get("distance_thresholds_m", [2.0, 10.0])
        def_dist = float(cfg.get("default_distance_m", 5.0))
        postura_pts = comunes.get("push_pull_posture_scores", [0, 3, 6])
        viaje_pts = comunes.get("travel_distance_scores", [0, 1, 3])
        agarre_mapa = comunes.get("coupling_scores", {"bueno": 0, "regular": 1, "malo": 2, "inaceptable": 2})
        sup_mapa = comunes.get("surface_condition_scores", {"buena": 0, "regular": 1, "mala": 4})

        carga_kg = float(datos.get("carga_kg", 0.0))
        tronco = float(datos.get("tronco_grados") or 0.0)
        agarre = str(datos.get("agarre", "bueno")).lower()
        distancia_m = float(datos.get("distancia_transporte_m", def_dist))
        superficie = str(datos.get("condicion_superficie", "buena")).lower()

        # a) Actividad y peso sin auxiliar
        pts_peso = _puntaje_por_umbrales(carga_kg, umb_peso, pesos_pts)

        # b) Postura
        pts_postura = _puntaje_por_umbrales(tronco, [tronco_mod, tronco_sev], postura_pts)

        # c) Agarre de la mano
        pts_agarre = int(agarre_mapa.get(agarre, 2))

        # e) Distancia por viaje
        pts_dist = _puntaje_por_umbrales(distancia_m, umb_dist, viaje_pts)

        # f) Superficie
        pts_sup = int(sup_mapa.get(superficie, 4))

        return [
            FactorEvaluado("A", "Actividad y peso (sin equipo auxiliar)", _color_factor(pts_peso, tablas), pts_peso),
            FactorEvaluado("B", "Postura durante empuje/arrastre", _color_factor(pts_postura, tablas), pts_postura),
            FactorEvaluado("C", "Agarre de la mano", _color_factor(pts_agarre, tablas), pts_agarre),
            FactorEvaluado("E", "Distancia por viaje", _color_factor(pts_dist, tablas), pts_dist),
            FactorEvaluado("F", "Condición de la superficie", _color_factor(pts_sup, tablas), pts_sup),
        ]


class EstrategiaConAuxiliar(EstrategiaEvaluacionNom036):
    """
    Hoja 5: con auxiliar (5) - Empuje y arrastre con equipo auxiliar rodante.
    Exige y evalúa de forma aislada:
      - Tipo de equipo ('1_2_ruedas', '3_mas_ruedas', 'grande_rieles')
      - Peso (hasta puntaje_inaceptable si supera límite nominal)
      - Condición de mantenimiento del equipo auxiliar (0, 2, 4 pts)
    """

    hoja_excel = "con auxiliar (5)"
    metodo_api = "empuje_con_auxiliar"

    def calcular_factores(
        self, datos: Mapping[str, Any], tablas: Mapping[str, Any]
    ) -> List[FactorEvaluado]:
        cfg = tablas.get("sheets_mapping", {}).get("con_auxiliar_5", {})
        comunes = tablas.get("common_factor_scores", {})
        tronco_mod, tronco_sev, _, _ = _umbrales_postura(tablas)

        puntaje_inaceptable = int(cfg.get("unacceptable_weight_score", 21))
        pesos_base_pts = list(cfg.get("weight_scores", [0, 2, 4, 8])) + [puntaje_inaceptable]
        umb_equipos = cfg.get(
            "equipment_weight_thresholds_kg",
            {
                "1_2_ruedas": [25.0, 50.0, 75.0, 100.0],
                "3_mas_ruedas": [50.0, 100.0, 180.0, 250.0],
                "grande_rieles": [150.0, 300.0, 450.0, 600.0],
            },
        )
        umb_dist = cfg.get("distance_thresholds_m", [10.0, 30.0])
        def_dist = float(cfg.get("default_distance_m", 10.0))
        mapa_mant = cfg.get("maintenance_scores", {"bueno": 0, "regular": 2, "malo": 4})
        postura_pts = comunes.get("push_pull_posture_scores", [0, 3, 6])
        viaje_pts = comunes.get("travel_distance_scores", [0, 1, 3])
        agarre_mapa = comunes.get("coupling_scores", {"bueno": 0, "regular": 1, "malo": 2, "inaceptable": 2})

        tipo_equipo = str(datos.get("tipo_equipo", "3_mas_ruedas")).lower()
        carga_kg = float(datos.get("carga_kg", 0.0))
        mantenimiento = str(datos.get("condicion_mantenimiento", "bueno")).lower()
        tronco = float(datos.get("tronco_grados") or 0.0)
        agarre = str(datos.get("agarre", "bueno")).lower()
        distancia_m = float(datos.get("distancia_transporte_m", def_dist))

        # a) Tipo de equipo y peso desde catálogo normativo
        umbrales_equipo = umb_equipos.get(tipo_equipo, umb_equipos.get("3_mas_ruedas", [50.0, 100.0, 180.0, 250.0]))
        pts_equipo_peso = _puntaje_por_umbrales(carga_kg, umbrales_equipo, pesos_base_pts)

        # b) Postura
        pts_postura = _puntaje_por_umbrales(tronco, [tronco_mod, tronco_sev], postura_pts)

        # c) Acoplamiento mano-maneral
        pts_agarre = int(agarre_mapa.get(agarre, 2))

        # e) Distancia por viaje
        pts_dist = _puntaje_por_umbrales(distancia_m, umb_dist, viaje_pts)

        # f) Condición de mantenimiento del equipo auxiliar - EXCLUSIVO DE CON AUXILIAR (5)
        pts_mant = int(mapa_mant.get(mantenimiento, 2))

        return [
            FactorEvaluado("A", f"Tipo de equipo ({tipo_equipo}) y peso", _color_factor(pts_equipo_peso, tablas), pts_equipo_peso),
            FactorEvaluado("B", "Postura de empuje/arrastre", _color_factor(pts_postura, tablas), pts_postura),
            FactorEvaluado("C", "Acoplamiento en manerales", _color_factor(pts_agarre, tablas), pts_agarre),
            FactorEvaluado("E", "Distancia de traslado", _color_factor(pts_dist, tablas), pts_dist),
            FactorEvaluado("F", "Condición de mantenimiento del equipo auxiliar", _color_factor(pts_mant, tablas), pts_mant),
        ]


class EnrutadorNom036:
    """
    Enrutador dinámico (Contexto del Patrón Strategy) que selecciona la calculadora
    exacta según `tipo_operacion` sin condicionales if/else acoplados.
    """

    _REGISTRO: Dict[str, Type[EstrategiaEvaluacionNom036]] = {
        "levantamiento": EstrategiaLevantamiento,
        "levantamiento_1": EstrategiaLevantamiento,
        "levantamiento (1)": EstrategiaLevantamiento,
        "postura": EstrategiaLevantamiento,
        "transporte": EstrategiaTransporte,
        "transporte_2": EstrategiaTransporte,
        "transporte (2)": EstrategiaTransporte,
        "equipo": EstrategiaEquipo,
        "equipo_3": EstrategiaEquipo,
        "equipo (3)": EstrategiaEquipo,
        "sin_auxiliar": EstrategiaSinAuxiliar,
        "sin_auxiliar_4": EstrategiaSinAuxiliar,
        "sin auxiliar (4)": EstrategiaSinAuxiliar,
        "empuje_sin_auxiliar": EstrategiaSinAuxiliar,
        "con_auxiliar": EstrategiaConAuxiliar,
        "con_auxiliar_5": EstrategiaConAuxiliar,
        "con auxiliar (5)": EstrategiaConAuxiliar,
        "empuje_con_auxiliar": EstrategiaConAuxiliar,
    }

    @classmethod
    def obtener_estrategia(cls, tipo_operacion: str) -> EstrategiaEvaluacionNom036:
        clave = (tipo_operacion or "").strip().lower()
        clase_estrategia = cls._REGISTRO.get(clave)
        if clase_estrategia is None:
            raise ValueError(
                f"Tipo de operación no soportado: '{tipo_operacion}'. "
                f"Operaciones válidas: {sorted(set(cls._REGISTRO.keys()))}"
            )
        return clase_estrategia()

    @classmethod
    def evaluar(
        cls, tipo_operacion: str, datos: Mapping[str, Any], tablas: Mapping[str, Any]
    ) -> ResultadoCalculoNom036:
        estrategia = cls.obtener_estrategia(tipo_operacion)
        return estrategia.evaluar(datos, tablas)
