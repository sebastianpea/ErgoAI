"""Motor de Reglas Ergonómicas y de Layout - Jabil Chihuahua (16-PE30-6500-00023 Rev O).

SSOT para todos los módulos A a I y reglas de tiempo T1 a T8.
"""

from datetime import date
from typing import Optional
from ergoai.domain.models.workstation import (
    WorkstationInputData,
    WorkstationType,
    RuleStatus,
    RuleOrigin,
)
from ergoai.domain.models.audit import RuleEvaluationResult
from ergoai.domain.constants import (
    JABIL_MAX_SINGLE_PERSON_LOAD_KG,
    JABIL_TEAM_LIFT_2_PERSONS_GREEN_MAX_KG,
    JABIL_TEAM_LIFT_2_PERSONS_ORANGE_MAX_KG,
    JABIL_TEAM_LIFT_3_PERSONS_GREEN_MAX_KG,
    JABIL_TEAM_LIFT_3_PERSONS_ORANGE_MAX_KG,
    JABIL_TEAM_LIFT_4_PERSONS_ORANGE_MAX_KG,
    JABIL_MIN_LIFTING_FREE_SPACE_CM,
    JABIL_MAX_PICKUP_HEIGHT_RACK_M,
    JABIL_MAX_PICKUP_HEIGHT_CART_PALLET_M,
    JABIL_WORKSTATION_SURFACE_HEIGHT_MIN_CM,
    JABIL_WORKSTATION_SURFACE_HEIGHT_MAX_CM,
    JABIL_MIN_INTER_OPERATOR_DISTANCE_CM,
    JABIL_MIN_LEGROOM_DEPTH_CM,
    JABIL_MIN_LEGROOM_WIDTH_CM,
    JABIL_MAX_TABLE_THICKNESS_CM,
    JABIL_CONVEYOR_HEIGHT_MIN_M,
    JABIL_CONVEYOR_HEIGHT_MAX_M,
    JABIL_CONVEYOR_MAX_GRAVITY_LENGTH_M,
    JABIL_MIN_ELECTRICAL_PANEL_CLEARANCE_CM,
    JABIL_MRB_CAGE_MIN_HEIGHT_M,
)


class JabilRulesEvaluator:
    """Implementa las reglas ergonómicas de la Instrucción de Trabajo 16-PE30-6500-00023."""

    def __init__(self, detection_date: Optional[str] = None) -> None:
        self.detection_date = detection_date or date.today().isoformat()

    def _result(
        self,
        station_id: str,
        rule_id: str,
        status: RuleStatus,
        measured: str,
        limit: str,
        doc_ref: str,
        origin: RuleOrigin,
        action: str,
        responsible: str,
        required_docs: Optional[list[str]] = None,
        days_open: int = 0,
    ) -> RuleEvaluationResult:
        return RuleEvaluationResult(
            id_estacion=station_id,
            regla=rule_id,
            estado=status,
            valor_medido=measured,
            limite=limit,
            referencia_doc=doc_ref,
            origen=origin,
            accion=action,
            responsable=responsible,
            documentos_requeridos=required_docs or [],
            fecha_deteccion=self.detection_date,
            dias_abierto=days_open,
        )

    # --------------------------------------------------------------------------
    # MODULO A - ALCANCE
    # --------------------------------------------------------------------------
    def eval_a1_scope(self, data: WorkstationInputData) -> RuleEvaluationResult:
        """A1 [DOC 2.1, 2.2, 10.7]: Valida si el área es productiva."""
        if data.tipo == WorkstationType.NON_PRODUCTIVE:
            return self._result(
                station_id=data.id_estacion,
                rule_id="A1",
                status=RuleStatus.NO_APLICA,
                measured=str(data.tipo.value),
                limit="Áreas productivas, empaque o almacén",
                doc_ref="2.1, 2.2, 10.7",
                origin=RuleOrigin.DOC,
                action="No requiere evaluación ergonómica de piso de manufactura.",
                responsible="IE de Célula",
            )
        return self._result(
            station_id=data.id_estacion,
            rule_id="A1",
            status=RuleStatus.CONFORME,
            measured=f"Área productiva tipo {data.tipo.value}",
            limit="Áreas productivas, empaque o almacén",
            doc_ref="2.1, 2.2, 10.7",
            origin=RuleOrigin.DOC,
            action="Continuar con el pipeline de evaluación.",
            responsible="IE de Célula",
        )

    # --------------------------------------------------------------------------
    # MODULO B - LEVANTAMIENTO MANUAL DE CARGAS
    # --------------------------------------------------------------------------
    def eval_b1_single_person_weight(self, data: WorkstationInputData) -> RuleEvaluationResult:
        """B1 [DOC 6.4.1]: Límite absoluto de 14 kg por persona."""
        weight = data.lifting.weight_kg
        if weight is None:
            return self._result(
                data.id_estacion, "B1", RuleStatus.DATO_FALTANTE, "No especificado",
                "<= 14 kg (1 persona)", "6.4.1", RuleOrigin.DOC,
                "Capturar peso manipulado en estación.", "IE de Célula"
            )

        if data.lifting.num_people == 1:
            if weight <= JABIL_MAX_SINGLE_PERSON_LOAD_KG or data.lifting.has_mechanical_assist:
                return self._result(
                    data.id_estacion, "B1", RuleStatus.CONFORME, f"{weight} kg",
                    f"<= {int(JABIL_MAX_SINGLE_PERSON_LOAD_KG)} kg", "6.4.1", RuleOrigin.DOC,
                    "Mantener método actual.", "IE de Célula"
                )
            return self._result(
                data.id_estacion, "B1", RuleStatus.NO_CONFORME, f"{weight} kg",
                f"<= {int(JABIL_MAX_SINGLE_PERSON_LOAD_KG)} kg", "6.4.1", RuleOrigin.DOC,
                "Considerar asistencia mecánica (lifter/grúa) o rediseño de carga.",
                "IE de Célula + EHS", ["16-HS80-8000-00021 (MOC)"]
            )
        return self._result(
            data.id_estacion, "B1", RuleStatus.NO_APLICA, f"Levantamiento en equipo ({data.lifting.num_people} pers.)",
            "Aplica regla B2", "6.4.1", RuleOrigin.DOC,
            "Evaluar mediante regla B2 de levantamiento en equipo.", "IE de Célula"
        )

    def eval_b2_team_containment(self, data: WorkstationInputData) -> RuleEvaluationResult:
        """B2 [DOC 6.4.2]: Levantamiento en equipo > 14 kg como contención."""
        weight = data.lifting.weight_kg
        num = data.lifting.num_people

        if weight is None or weight <= JABIL_MAX_SINGLE_PERSON_LOAD_KG or num <= 1:
            return self._result(
                data.id_estacion, "B2", RuleStatus.NO_APLICA,
                f"{weight} kg / {num} pers.", f"Solo aplica para cargas > {int(JABIL_MAX_SINGLE_PERSON_LOAD_KG)} kg en equipo",
                "6.4.2", RuleOrigin.DOC, "No aplica.", "IE de Célula"
            )

        # Tablas Verde y Naranja
        is_green = False
        is_orange = False

        if num == 2:
            is_green = weight < JABIL_TEAM_LIFT_2_PERSONS_GREEN_MAX_KG
            is_orange = JABIL_TEAM_LIFT_2_PERSONS_GREEN_MAX_KG <= weight < JABIL_TEAM_LIFT_2_PERSONS_ORANGE_MAX_KG
        elif num == 3:
            is_green = weight < JABIL_TEAM_LIFT_3_PERSONS_GREEN_MAX_KG
            is_orange = JABIL_TEAM_LIFT_3_PERSONS_GREEN_MAX_KG <= weight < JABIL_TEAM_LIFT_3_PERSONS_ORANGE_MAX_KG
        elif num == 4:
            is_green = False
            is_orange = JABIL_TEAM_LIFT_3_PERSONS_GREEN_MAX_KG <= weight < JABIL_TEAM_LIFT_4_PERSONS_ORANGE_MAX_KG

        if is_green:
            if data.lifting.has_form_00014 and data.lifting.has_moc:
                return self._result(
                    data.id_estacion, "B2", RuleStatus.CONFORME, f"{weight} kg entre {num} pers. (Tabla Verde)",
                    "Tabla Verde con MOC y formato 00014", "6.4.2", RuleOrigin.DOC,
                    "Contención conforme. Mantener vigencia de MOC.", "IE de Célula + EHS",
                    ["16-PE80-6500-00014", "16-HS80-8000-00021"]
                )
            return self._result(
                data.id_estacion, "B2", RuleStatus.ADVERTENCIA, f"{weight} kg entre {num} pers. (Faltan documentos)",
                "Requiere formato 16-PE80-6500-00014 y MOC", "6.4.2", RuleOrigin.DOC,
                "Formalizar evaluación ergonómica y tramitar MOC de contención.",
                "IE de Célula + EHS", ["16-PE80-6500-00014", "16-HS80-8000-00021"]
            )

        if is_orange:
            if data.lifting.medical_clearance and data.lifting.has_form_00014 and data.lifting.has_moc:
                return self._result(
                    data.id_estacion, "B2", RuleStatus.ADVERTENCIA,
                    f"{weight} kg entre {num} pers. (Tabla Naranja validada médicamente)",
                    "Tabla Naranja con visto bueno médico y MOC", "6.4.2", RuleOrigin.DOC,
                    "Contención bajo estricto monitoreo médico. Migrar a asistencia mecánica prioritaria.",
                    "Departamento Médico + EHS", ["16-PE80-6500-00014", "16-HS80-8000-00021"]
                )
            return self._result(
                data.id_estacion, "B2", RuleStatus.NO_CONFORME,
                f"{weight} kg entre {num} pers. (Sin visto bueno médico)",
                "Requiere revisión del Departamento Médico obligatoria", "6.4.2", RuleOrigin.DOC,
                "Detener levantamiento manual; requiere valoración médica inmediata y MOC.",
                "Departamento Médico + EHS", ["16-PE80-6500-00014", "16-HS80-8000-00021"]
            )

        # Cargas fuera de tabla (exceden los máximos absolutos permitidos)
        return self._result(
            data.id_estacion, "B2", RuleStatus.CRITICO, f"{weight} kg entre {num} pers. (Fuera de tablas)",
            "Límites máximos de contención excedidos", "6.4.2", RuleOrigin.SUPUESTO,
            "Riesgo inminente de lesión severa. Prohibido levantamiento manual sin grúa o lifter.",
            "Gerente EHS + Gerente PE", ["16-HS80-8000-00021"]
        )

    def eval_b3_free_space(self, data: WorkstationInputData) -> RuleEvaluationResult:
        """B3 [DOC 6.4.3]: Espacio libre para levantamiento >= 60 cm."""
        space = data.lifting.free_space_around_cm
        if space is None:
            return self._result(
                data.id_estacion, "B3", RuleStatus.DATO_FALTANTE, "No medido",
                ">= 60 cm libre", "6.4.3", RuleOrigin.DOC,
                "Medir espacio perimetral libre en la estación.", "IE de Célula"
            )
        if space >= JABIL_MIN_LIFTING_FREE_SPACE_CM:
            return self._result(
                data.id_estacion, "B3", RuleStatus.CONFORME, f"{space} cm",
                f">= {int(JABIL_MIN_LIFTING_FREE_SPACE_CM)} cm", "6.4.3", RuleOrigin.DOC, "Espacio adecuado.", "IE de Célula"
            )
        return self._result(
            data.id_estacion, "B3", RuleStatus.NO_CONFORME, f"{space} cm",
            f">= {int(JABIL_MIN_LIFTING_FREE_SPACE_CM)} cm", "6.4.3", RuleOrigin.DOC,
            "Reubicar obstáculos que restrinjan movimientos o fuercen posturas forzadas.",
            "IE de Célula"
        )

    def eval_b4_pickup_height(self, data: WorkstationInputData) -> RuleEvaluationResult:
        """B4 [DOC 6.4.4]: Alturas de toma (Rack <= 1.7 m, Tarima/Carro <= 1.6 m, Evitar piso/sobre cabeza)."""
        height = data.lifting.pickup_height_m
        origin = (data.lifting.pickup_origin or "").lower()

        if height is None and not origin:
            return self._result(
                data.id_estacion, "B4", RuleStatus.DATO_FALTANTE, "No medido",
                f"Rack <= {JABIL_MAX_PICKUP_HEIGHT_RACK_M}m | Tarima <= {JABIL_MAX_PICKUP_HEIGHT_CART_PALLET_M}m | No piso ni sobre cabeza", "6.4.4", RuleOrigin.DOC,
                "Capturar altura y origen de toma de materiales.", "IE de Célula"
            )

        is_floor_or_overhead = origin in ("piso", "sobre_cabeza")
        limit_m = JABIL_MAX_PICKUP_HEIGHT_RACK_M if origin == "rack_estatico" else JABIL_MAX_PICKUP_HEIGHT_CART_PALLET_M
        is_exceeded = (height is not None and height > limit_m) or is_floor_or_overhead

        if not is_exceeded:
            return self._result(
                data.id_estacion, "B4", RuleStatus.CONFORME, f"{height or 'N/A'} m ({origin})",
                f"<= {limit_m} m", "6.4.4", RuleOrigin.DOC, "Altura de toma ergonómica.", "IE de Célula"
            )

        if data.lifting.has_moc:
            return self._result(
                data.id_estacion, "B4", RuleStatus.ADVERTENCIA, f"{height} m ({origin}) con MOC",
                f"<= {limit_m} m", "6.4.4", RuleOrigin.DOC,
                "Excepción liberada con MOC por requerimiento de cliente o producto.",
                "IE de Célula + EHS", ["16-HS80-8000-00021"]
            )

        return self._result(
            data.id_estacion, "B4", RuleStatus.NO_CONFORME, f"{height} m ({origin}) sin MOC",
            f"<= {limit_m} m", "6.4.4", RuleOrigin.DOC,
            "Bajar punto de toma en rack o tarima a cota admisible, o tramitar MOC de excepción.",
            "IE de Célula + EHS", ["16-HS80-8000-00021"]
        )

    def eval_b5_new_business(self, data: WorkstationInputData) -> RuleEvaluationResult:
        """B5 [DOC 6.4.5]: Negocio nuevo requiere formato 16-PE80-6500-00091."""
        if not data.lifting.is_new_business:
            return self._result(
                data.id_estacion, "B5", RuleStatus.NO_APLICA, "Negocio existente",
                "Solo aplica para negocios nuevos", "6.4.5", RuleOrigin.DOC, "No aplica.", "IE de Célula"
            )
        if data.lifting.has_form_00091:
            return self._result(
                data.id_estacion, "B5", RuleStatus.CONFORME, "Formato 00091 liberado",
                "Evaluación de cargas para negocio nuevo", "6.4.5", RuleOrigin.DOC, "Conforme.", "IE de Célula"
            )
        return self._result(
            data.id_estacion, "B5", RuleStatus.NO_CONFORME, "Falta formato 00091",
            "Evaluación de cargas obligatoria", "6.4.5", RuleOrigin.DOC,
            "Generar formato 16-PE80-6500-00091 para nuevo negocio.",
            "IE de Célula", ["16-PE80-6500-00091"]
        )

    def eval_b6_annual_coverage(self, data: WorkstationInputData) -> RuleEvaluationResult:
        """B6 [DOC 6.4.6 / T3]: Cobertura de evaluación anual en el año fiscal."""
        last_fy = data.last_ergonomic_evaluation_fiscal_year
        curr_fy = data.current_fiscal_year

        if last_fy is None:
            return self._result(
                data.id_estacion, "B6", RuleStatus.DATO_FALTANTE, "Sin registro de año fiscal",
                f"Año fiscal {curr_fy}", "6.4.6", RuleOrigin.DOC,
                "Verificar fecha de última evaluación ergonómica.", "IE de Célula"
            )
        if last_fy >= curr_fy:
            return self._result(
                data.id_estacion, "B6", RuleStatus.CONFORME, f"Evaluada en FY{last_fy}",
                f"FY{curr_fy}", "6.4.6", RuleOrigin.DOC, "Evaluación anual vigente.", "IE de Célula"
            )
        return self._result(
            data.id_estacion, "B6", RuleStatus.NO_CONFORME, f"Última evaluación FY{last_fy} (Vencida)",
            f"FY{curr_fy}", "6.4.6", RuleOrigin.DOC,
            "Re-evaluar estación en año fiscal vigente con formato 16-PE80-6500-00014.",
            "IE de Célula", ["16-PE80-6500-00014"]
        )

    # --------------------------------------------------------------------------
    # MODULO C - POSTURA SENTADO VS DE PIE
    # --------------------------------------------------------------------------
    def eval_c_posture(self, data: WorkstationInputData) -> RuleEvaluationResult:
        """C1, C2, C3 [DOC 7.2.1]: Criterios para postura sentado vs de pie."""
        weight = data.lifting.weight_kg or 0.0
        prop = data.posture_proposed.lower()

        wants_sitting = (weight < 3.0) or data.has_fine_assembly or data.requires_pedals
        wants_standing = (weight > 3.0) or data.frequent_travel_required

        if wants_sitting and not wants_standing:
            recommended = "sentado"
        elif wants_standing and not wants_sitting:
            recommended = "de_pie"
        else:
            # Conflicto o criterios mixtos
            return self._result(
                data.id_estacion, "C3", RuleStatus.REVISION_HUMANA, f"Propuesta: {prop} (Criterios mixtos)",
                "Criterios de sentado y de pie presentes simultáneamente", "7.2.1", RuleOrigin.SUPUESTO,
                "Revisión humana por especialista para determinar postura o alternancia sit-stand.",
                "Especialista Ergonómico"
            )

        if prop == recommended:
            return self._result(
                data.id_estacion, "C3", RuleStatus.CONFORME, f"Propuesta: {prop} | Recomendada: {recommended}",
                f"Postura coincidente ({recommended})", "7.2.1", RuleOrigin.DOC,
                "Postura asignada correctamente.", "IE de Célula"
            )

        return self._result(
            data.id_estacion, "C3", RuleStatus.ADVERTENCIA, f"Propuesta: {prop} | Recomendada: {recommended}",
            f"Se recomienda {recommended}", "7.2.1", RuleOrigin.DOC,
            f"Considerar cambiar postura de trabajo a {recommended} para optimizar ergonomía.",
            "IE de Célula + Ergonomía"
        )

    # --------------------------------------------------------------------------
    # MODULO D - LEY SILLA (BIPEDESTACIÓN)
    # --------------------------------------------------------------------------
    def eval_d1_chair_law_score(self, data: WorkstationInputData) -> RuleEvaluationResult:
        """D1 [DOC 7.2.2.1]: Cuestionario de 7 preguntas de Ley Silla (7 a 21 pts)."""
        if data.posture_proposed.lower() == "sentado":
            return self._result(
                data.id_estacion, "D1", RuleStatus.NO_APLICA, "Estación sentado",
                "Aplica a estaciones de pie", "7.2.2.1", RuleOrigin.DOC, "No aplica.", "IE de Célula"
            )

        if data.chair_law is None:
            return self._result(
                data.id_estacion, "D1", RuleStatus.DATO_FALTANTE, "Cuestionario incompleto",
                "7 respuestas obligatorias", "7.2.2.1", RuleOrigin.DOC,
                "Capturar las 7 respuestas de la Ley Silla.", "IE de Célula"
            )

        total = data.chair_law.total_score
        if total == 7:
            return self._result(
                data.id_estacion, "D1", RuleStatus.CONFORME, f"Puntaje {total} (VERDE)",
                "Puntaje 7: Ley Silla NO aplica", "7.2.2.1", RuleOrigin.DOC,
                "Condiciones de bipedestación seguras. No requiere intervención de Ley Silla.", "IE de Célula"
            )
        elif 8 <= total <= 14:
            return self._result(
                data.id_estacion, "D1", RuleStatus.ADVERTENCIA, f"Puntaje {total} (AMARILLO)",
                "8-14 pts: Ley Silla SI aplica", "7.2.2.1", RuleOrigin.DOC,
                "Implementar estrategia de descanso de Ley Silla (Silla de descanso o rotación).",
                "IE + Producción + WCM"
            )
        else:
            return self._result(
                data.id_estacion, "D1", RuleStatus.NO_CONFORME, f"Puntaje {total} (ROJO)",
                "15-21 pts: Ley Silla SI aplica con alta criticidad", "7.2.2.1", RuleOrigin.DOC,
                "Alto estrés por bipedestación. Implementar de inmediato rotación o silla de relevo.",
                "IE + Producción + WCM"
            )

    def eval_d2_standing_time_limit(self, data: WorkstationInputData) -> RuleEvaluationResult:
        """D2 [DOC 7.2.2.1 / T1]: Máximo 3 horas (180 min) continuas de bipedestación y pausa mín. 5 min."""
        if data.posture_proposed.lower() == "sentado":
            return self._result(
                data.id_estacion, "D2", RuleStatus.NO_APLICA, "Estación sentado",
                "<= 180 min de pie continuo", "7.2.2.1", RuleOrigin.DOC, "No aplica.", "IE de Célula"
            )

        t_stand = data.standing_continuous_time_min
        t_pause = data.seated_pause_min

        if t_stand > 180.0:
            return self._result(
                data.id_estacion, "D2", RuleStatus.NO_CONFORME, f"{t_stand} min continuos de pie",
                "<= 180 min (3 horas)", "7.2.2.1", RuleOrigin.DOC,
                "Infracción a Ley Silla. Romper bipedestación continua con descansos sentados de mín. 5 min.",
                "Supervisor de Producción + IE"
            )

        if t_stand >= 150.0:
            return self._result(
                data.id_estacion, "D2", RuleStatus.ADVERTENCIA, f"{t_stand} min continuos de pie",
                "Alerta preventiva (>= 150 min)", "7.2.2.1", RuleOrigin.SUPUESTO,
                "Próximo al límite legal de 180 min. Programar pausa sentada.",
                "Supervisor de Producción"
            )

        if t_pause < 5.0 and t_stand > 60.0:
            return self._result(
                data.id_estacion, "D2", RuleStatus.NO_CONFORME, f"Pausa sentado: {t_pause} min",
                ">= 5 min de descanso sentado", "7.2.2.1", RuleOrigin.DOC,
                "Garantizar pausa mínima de 5 minutos sentado.", "Supervisor de Producción"
            )

        return self._result(
            data.id_estacion, "D2", RuleStatus.CONFORME, f"{t_stand} min de pie / pausa {t_pause} min",
            "<= 180 min continuo y pausa >= 5 min", "7.2.2.1", RuleOrigin.DOC,
            "Tiempos de bipedestación conformes.", "Supervisor de Producción"
        )

    def eval_d4_chair_specs(self, data: WorkstationInputData) -> list[RuleEvaluationResult]:
        """D4 [DOC 7.2.2.1, 7.3.3.1]: Especificaciones técnicas obligatorias de la silla estándar."""
        results: list[RuleEvaluationResult] = []
        cs = data.chair_spec

        checks = [
            ("D4_LEGS", cs.chair_has_5_legs, "Silla cuenta con 5 patas", "5 patas obligatorias"),
            ("D4_FOOTREST", cs.chair_has_footrest, "Cuenta con área de reposapiés", "Reposapiés integrado obligatorio"),
            ("D4_ADJ", cs.chair_height_adjustable, "Altura ajustable", "Altura ajustable obligatoria"),
            ("D4_BACKREST", cs.chair_non_rigid_backrest, "Respaldo no rígido", "Respaldo flexible/ergonómico"),
            ("D4_MATERIAL", cs.chair_polyurethane, "Material poliuretano", "Poliuretano estandarizado"),
            ("D4_FLOOR", cs.marked_on_floor, "Ubicación marcada en piso 'SILLA'", "Marcado en piso 'SILLA'"),
            ("D4_LAYOUT", cs.documented_in_layout, "Documentada en layout", "Documentada en dibujo de layout"),
            ("D4_SIGNAGE", cs.visual_factory_signage, "Fábrica visual de uso", "Señalización de fábrica visual"),
        ]

        # Validación ESD en áreas EPA
        if data.is_epa_area:
            checks.append(("D4_ESD", cs.is_esd_chair, "Silla con certificación ESD", "Obligatoria en área EPA"))

        for code, val, desc_ok, desc_req in checks:
            if val is None:
                results.append(self._result(
                    data.id_estacion, code, RuleStatus.DATO_FALTANTE, "No verificado",
                    desc_req, "7.3.3.1", RuleOrigin.DOC, f"Inspeccionar {desc_req}.", "IE de Célula"
                ))
            elif val:
                results.append(self._result(
                    data.id_estacion, code, RuleStatus.CONFORME, desc_ok,
                    desc_req, "7.3.3.1", RuleOrigin.DOC, "Conforme.", "IE de Célula"
                ))
            else:
                results.append(self._result(
                    data.id_estacion, code, RuleStatus.NO_CONFORME, f"Incumple: {desc_req}",
                    desc_req, "7.3.3.1", RuleOrigin.DOC,
                    f"Adecuar o reemplazar silla para cumplir con {desc_req}.", "IE de Célula + EHS"
                ))

        return results

    # --------------------------------------------------------------------------
    # MODULO F - DIMENSIONES DE LA ESTACIÓN
    # --------------------------------------------------------------------------
    def eval_f1_work_surface_height(self, data: WorkstationInputData) -> RuleEvaluationResult:
        """F1 [DOC 7.2.3]: Altura de área de trabajo en CUU (95 a 125 cm)."""
        h = data.dimensions.surface_height_cm
        if h is None:
            return self._result(
                data.id_estacion, "F1", RuleStatus.DATO_FALTANTE, "No medido",
                f"{int(JABIL_WORKSTATION_SURFACE_HEIGHT_MIN_CM)} cm a {int(JABIL_WORKSTATION_SURFACE_HEIGHT_MAX_CM)} cm (CUU)", "7.2.3", RuleOrigin.DOC,
                "Medir altura de superficie de trabajo.", "IE de Célula"
            )
        if JABIL_WORKSTATION_SURFACE_HEIGHT_MIN_CM <= h <= JABIL_WORKSTATION_SURFACE_HEIGHT_MAX_CM:
            return self._result(
                data.id_estacion, "F1", RuleStatus.CONFORME, f"{h} cm",
                f"{int(JABIL_WORKSTATION_SURFACE_HEIGHT_MIN_CM)} cm a {int(JABIL_WORKSTATION_SURFACE_HEIGHT_MAX_CM)} cm", "7.2.3", RuleOrigin.DOC, "Altura conforme.", "IE de Célula"
            )
        return self._result(
            data.id_estacion, "F1", RuleStatus.REVISION_HUMANA, f"{h} cm",
            f"{int(JABIL_WORKSTATION_SURFACE_HEIGHT_MIN_CM)} cm a {int(JABIL_WORKSTATION_SURFACE_HEIGHT_MAX_CM)} cm", "7.2.3", RuleOrigin.DOC,
            "Revisar estación fuera de rango estándar; validar con especialista o ajustar altura.",
            "IE de Célula + Ergonomía"
        )

    def eval_f2_operator_distance(self, data: WorkstationInputData) -> RuleEvaluationResult:
        """F2 [DOC 7.3.3]: Distancia entre operadores >= 80 cm."""
        dist = data.dimensions.operator_distance_cm
        if dist is None:
            return self._result(
                data.id_estacion, "F2", RuleStatus.DATO_FALTANTE, "No medido",
                f">= {int(JABIL_MIN_INTER_OPERATOR_DISTANCE_CM)} cm punto medio a punto medio", "7.3.3", RuleOrigin.DOC,
                "Medir separación entre puestos de trabajo adyacentes.", "IE de Célula"
            )
        if dist >= JABIL_MIN_INTER_OPERATOR_DISTANCE_CM:
            return self._result(
                data.id_estacion, "F2", RuleStatus.CONFORME, f"{dist} cm",
                f">= {int(JABIL_MIN_INTER_OPERATOR_DISTANCE_CM)} cm", "7.3.3", RuleOrigin.DOC, "Espacio entre operadores conforme.", "IE de Célula"
            )
        return self._result(
            data.id_estacion, "F2", RuleStatus.NO_CONFORME, f"{dist} cm",
            f">= {int(JABIL_MIN_INTER_OPERATOR_DISTANCE_CM)} cm", "7.3.3", RuleOrigin.DOC,
            f"Aumentar separación entre operadores a mínimo {int(JABIL_MIN_INTER_OPERATOR_DISTANCE_CM)} cm para evitar interferencias.",
            "IE de Célula"
        )

    def eval_f3_leg_room_sitting(self, data: WorkstationInputData) -> RuleEvaluationResult:
        """F3 [DOC 7.3.3]: Espacio libre para piernas en estación sentado (profundidad >= 55cm, ancho >= 60cm)."""
        if data.posture_proposed.lower() != "sentado":
            return self._result(
                data.id_estacion, "F3", RuleStatus.NO_APLICA, "Estación de pie",
                f"Profundidad >= {int(JABIL_MIN_LEGROOM_DEPTH_CM)} cm, Ancho >= {int(JABIL_MIN_LEGROOM_WIDTH_CM)} cm (Sentado)", "7.3.3", RuleOrigin.DOC, "No aplica.", "IE de Célula"
            )

        depth = data.dimensions.leg_room_depth_cm
        width = data.dimensions.leg_room_width_cm

        if depth is None or width is None:
            return self._result(
                data.id_estacion, "F3", RuleStatus.DATO_FALTANTE, "Dimensiones de hueco no medidas",
                f"Profundidad >= {int(JABIL_MIN_LEGROOM_DEPTH_CM)} cm, Ancho >= {int(JABIL_MIN_LEGROOM_WIDTH_CM)} cm", "7.3.3", RuleOrigin.DOC,
                "Medir profundidad y ancho del hueco inferior de la mesa.", "IE de Célula"
            )

        if depth >= JABIL_MIN_LEGROOM_DEPTH_CM and width >= JABIL_MIN_LEGROOM_WIDTH_CM:
            return self._result(
                data.id_estacion, "F3", RuleStatus.CONFORME, f"Prof: {depth} cm, Ancho: {width} cm",
                f">= {int(JABIL_MIN_LEGROOM_DEPTH_CM)} x {int(JABIL_MIN_LEGROOM_WIDTH_CM)} cm", "7.3.3", RuleOrigin.DOC, "Hueco de piernas conforme.", "IE de Célula"
            )

        return self._result(
            data.id_estacion, "F3", RuleStatus.NO_CONFORME, f"Prof: {depth} cm, Ancho: {width} cm",
            f">= {int(JABIL_MIN_LEGROOM_DEPTH_CM)} x {int(JABIL_MIN_LEGROOM_WIDTH_CM)} cm", "7.3.3", RuleOrigin.DOC,
            f"Retirar travesaños u obstáculos inferiores para asegurar mínimo {int(JABIL_MIN_LEGROOM_DEPTH_CM)} cm profundidad y {int(JABIL_MIN_LEGROOM_WIDTH_CM)} cm ancho.",
            "IE de Célula + Mobiliario"
        )

    def eval_f5_table_thickness(self, data: WorkstationInputData) -> RuleEvaluationResult:
        """F5 [DOC 7.3.3]: Espesor de mesa <= 10 cm."""
        thick = data.dimensions.table_thickness_cm
        if thick is None:
            return self._result(
                data.id_estacion, "F5", RuleStatus.DATO_FALTANTE, "No medido",
                "<= 10 cm", "7.3.3", RuleOrigin.DOC, "Medir grosor del canto de mesa.", "IE de Célula"
            )
        if thick <= JABIL_MAX_TABLE_THICKNESS_CM:
            return self._result(
                data.id_estacion, "F5", RuleStatus.CONFORME, f"{thick} cm",
                f"<= {int(JABIL_MAX_TABLE_THICKNESS_CM)} cm", "7.3.3", RuleOrigin.DOC, "Espesor de mesa adecuado.", "IE de Célula"
            )
        return self._result(
            data.id_estacion, "F5", RuleStatus.REVISION_HUMANA, f"{thick} cm",
            f"<= {int(JABIL_MAX_TABLE_THICKNESS_CM)} cm", "7.3.3", RuleOrigin.DOC,
            f"Espesor mayor a {int(JABIL_MAX_TABLE_THICKNESS_CM)} cm: Validar con especialista que no exista estrés por contacto en muslos.",
            "Especialista Ergonómico"
        )

    # --------------------------------------------------------------------------
    # MODULO G - CONVEYORS
    # --------------------------------------------------------------------------
    def eval_g_conveyor(self, data: WorkstationInputData) -> list[RuleEvaluationResult]:
        """G1 a G7 [DOC 7.3.3.2, 10.3]: Reglas técnicas para transportadores."""
        cv = data.conveyor
        if not cv.has_conveyor:
            return [self._result(
                data.id_estacion, "G", RuleStatus.NO_APLICA, "Sin conveyor",
                "Aplica solo con conveyor", "7.3.3.2", RuleOrigin.DOC, "No aplica.", "IE de Célula"
            )]

        results: list[RuleEvaluationResult] = []

        # G1: Altura (0.5 a 1.4 m)
        if cv.height_m is None:
            results.append(self._result(data.id_estacion, "G1", RuleStatus.DATO_FALTANTE, "No medido", "0.5 a 1.4 m", "7.3.3.2", RuleOrigin.DOC, "Medir altura de conveyor.", "IE de Célula"))
        elif 0.5 <= cv.height_m <= 1.4:
            results.append(self._result(data.id_estacion, "G1", RuleStatus.CONFORME, f"{cv.height_m} m", "0.5 a 1.4 m", "7.3.3.2", RuleOrigin.DOC, "Altura conforme.", "IE de Célula"))
        else:
            results.append(self._result(data.id_estacion, "G1", RuleStatus.NO_CONFORME, f"{cv.height_m} m", "0.5 a 1.4 m", "7.3.3.2", RuleOrigin.DOC, "Ajustar altura de conveyor al rango 0.5m - 1.4m.", "IE de Célula"))

        # G2: Longitud conveyor de gravedad (<= 3 m)
        if cv.conveyor_type == "gravedad":
            if cv.length_m is None:
                results.append(self._result(data.id_estacion, "G2", RuleStatus.DATO_FALTANTE, "No medido", "<= 3 m", "7.3.3.2", RuleOrigin.DOC, "Medir longitud de gravedad.", "IE de Célula"))
            elif cv.length_m <= 3.0:
                results.append(self._result(data.id_estacion, "G2", RuleStatus.CONFORME, f"{cv.length_m} m", "<= 3 m", "7.3.3.2", RuleOrigin.DOC, "Longitud conforme.", "IE de Célula"))
            else:
                results.append(self._result(data.id_estacion, "G2", RuleStatus.NO_CONFORME, f"{cv.length_m} m", "<= 3 m", "7.3.3.2", RuleOrigin.DOC, "Reducir tramo de gravedad a máximo 3 metros.", "IE de Célula"))

        # G3: Guardas en partes móviles (engranes, motores, poleas) -> CRITICO
        if cv.conveyor_type == "electrico":
            if cv.moving_parts_guards is None:
                results.append(self._result(data.id_estacion, "G3", RuleStatus.DATO_FALTANTE, "No inspeccionado", "Guardas físicas completas", "7.3.3.2", RuleOrigin.DOC, "Inspeccionar guardas en conveyor eléctrico.", "Seguridad EHS"))
            elif cv.moving_parts_guards:
                results.append(self._result(data.id_estacion, "G3", RuleStatus.CONFORME, "Guardas instaladas", "Cubrir engranes, motores y poleas", "7.3.3.2", RuleOrigin.DOC, "Protección mecánica conforme.", "Seguridad EHS"))
            else:
                results.append(self._result(data.id_estacion, "G3", RuleStatus.CRITICO, "Sin guardas en partes móviles", "Guardas físicas obligatorias", "7.3.3.2", RuleOrigin.DOC, "Riesgo de atrapamiento. Detener y colocar guardas de inmediato.", "Seguridad EHS + Mantenimiento"))

        # G5: Análisis de ergonomía obligatorio
        if cv.has_ergonomic_analysis is None or not cv.has_ergonomic_analysis:
            results.append(self._result(data.id_estacion, "G5", RuleStatus.NO_CONFORME, "Sin análisis ergonómico de conveyor", "Análisis ergonómico obligatorio", "7.3.3.2", RuleOrigin.DOC, "Elaborar y documentar análisis de ergonomía para el conveyor.", "IE de Célula"))
        else:
            results.append(self._result(data.id_estacion, "G5", RuleStatus.CONFORME, "Análisis de ergonomía validado", "Análisis ergonómico obligatorio", "7.3.3.2", RuleOrigin.DOC, "Conforme.", "IE de Célula"))

        return results

    # --------------------------------------------------------------------------
    # MODULO H - PASILLOS, AMRs, EMERGENCIAS Y MRB
    # --------------------------------------------------------------------------
    def eval_h4_electrical_and_emergency_clearance(self, data: WorkstationInputData) -> RuleEvaluationResult:
        """H4 [DOC 6.3.14]: Área libre de 90 cm en tableros eléctricos y salidas despejadas."""
        clearance = data.aisles.electrical_panel_clearance_cm
        unblocked = data.aisles.emergency_exits_unblocked

        if clearance is None and unblocked is None:
            return self._result(
                data.id_estacion, "H4", RuleStatus.DATO_FALTANTE, "No medido",
                ">= 90 cm libre frente a tablero y rutas no bloqueadas", "6.3.14", RuleOrigin.DOC,
                "Inspeccionar despeje de tableros eléctricos y extintores.", "Seguridad EHS"
            )

        is_blocked = (clearance is not None and clearance < 90.0) or (unblocked is False)
        if is_blocked:
            return self._result(
                data.id_estacion, "H4", RuleStatus.CRITICO,
                f"Despeje: {clearance} cm, Desbloqueado: {unblocked}",
                ">= 90 cm y rutas 100% libres", "6.3.14", RuleOrigin.DOC,
                "Bloqueo de seguridad crítica en tablero/salidas. Despejar área de inmediato.",
                "Seguridad EHS + Supervisor"
            )

        return self._result(
            data.id_estacion, "H4", RuleStatus.CONFORME,
            f"Despeje: {clearance or '>=90'} cm, Desbloqueado: True",
            ">= 90 cm y rutas despejadas", "6.3.14", RuleOrigin.DOC,
            "Despeje de seguridad conforme.", "Seguridad EHS"
        )

    def eval_h5_mrb_cage_and_esd(self, data: WorkstationInputData) -> RuleEvaluationResult:
        """H5 [DOC 10.6]: Jaula MRB >= 1.60m con cerradura y lupa validada ESD."""
        if not data.aisles.is_mrb_area:
            return self._result(
                data.id_estacion, "H5", RuleStatus.NO_APLICA, "No es área MRB",
                "Aplica únicamente a jaulas de MRB", "10.6", RuleOrigin.DOC, "No aplica.", "IE de Célula"
            )

        h_cage = data.aisles.mrb_cage_height_m
        has_lock = data.aisles.mrb_has_lock
        has_esd = data.aisles.mrb_has_esd_magnifier

        if h_cage is None or has_lock is None or has_esd is None:
            return self._result(
                data.id_estacion, "H5", RuleStatus.DATO_FALTANTE, "Datos MRB incompletos",
                "Altura >= 1.60m, candado y lupa ESD", "10.6", RuleOrigin.DOC,
                "Completar checklist de inspección MRB.", "Calidad / IE"
            )

        if h_cage >= 1.60 and has_lock and has_esd:
            return self._result(
                data.id_estacion, "H5", RuleStatus.CONFORME,
                f"Altura {h_cage}m, con cerradura y lupa ESD",
                ">= 1.60m, cerradura y lupa ESD", "10.6", RuleOrigin.DOC,
                "Instalación MRB conforme.", "Calidad / IE"
            )

        return self._result(
            data.id_estacion, "H5", RuleStatus.NO_CONFORME,
            f"Altura: {h_cage}m, Cerradura: {has_lock}, Lupa ESD: {has_esd}",
            ">= 1.60m, cerradura y lupa ESD", "10.6", RuleOrigin.DOC,
            "Adecuar cerramiento MRB: asegurar jaula >= 1.60 m, cerradura y equipamiento ESD.",
            "Calidad / IE + Facilities"
        )
