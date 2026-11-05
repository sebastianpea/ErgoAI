"""Motor de Auditoría y Orquestador de Reglas de Ergonomía ErgoAI."""

from typing import Optional, List
from ergoai.domain.models.workstation import (
    WorkstationInputData,
    RuleStatus,
)
from ergoai.domain.models.audit import (
    RuleEvaluationResult,
    GlobalStationResult,
)
from ergoai.domain.models.reach_zones import ReachPointEvaluation
from ergoai.domain.rules.rules_jabil import JabilRulesEvaluator


class ErgonomicRulesEngine:
    """Orquesta la ejecución de las reglas normativas, consolidando el semáforo y plan de acción."""

    def __init__(self, detection_date: Optional[str] = None) -> None:
        self.evaluator = JabilRulesEvaluator(detection_date=detection_date)

    def evaluate_station(
        self,
        data: WorkstationInputData,
        reach_evaluations: Optional[List[ReachPointEvaluation]] = None,
    ) -> GlobalStationResult:
        """Ejecuta el pipeline normativo completo sobre la estación y sus zonas de alcance."""
        results: list[RuleEvaluationResult] = []

        # Modulo A - Alcance
        res_a1 = self.evaluator.eval_a1_scope(data)
        results.append(res_a1)
        if res_a1.estado == RuleStatus.NO_APLICA:
            return GlobalStationResult(
                id_estacion=data.id_estacion,
                estado_global=RuleStatus.NO_APLICA,
                reglas_evaluadas=results,
                fallas=[],
                datos_faltantes=[],
                acciones_priorizadas=["Área no productiva. No requiere acciones de piso."],
            )

        # Modulo B - Cargas
        results.append(self.evaluator.eval_b1_single_person_weight(data))
        results.append(self.evaluator.eval_b2_team_containment(data))
        results.append(self.evaluator.eval_b3_free_space(data))
        results.append(self.evaluator.eval_b4_pickup_height(data))
        results.append(self.evaluator.eval_b5_new_business(data))
        results.append(self.evaluator.eval_b6_annual_coverage(data))

        # Modulo C - Postura
        results.append(self.evaluator.eval_c_posture(data))

        # Modulo D - Ley Silla
        results.append(self.evaluator.eval_d1_chair_law_score(data))
        results.append(self.evaluator.eval_d2_standing_time_limit(data))
        results.extend(self.evaluator.eval_d4_chair_specs(data))

        # Modulo E - Zonas de Alcance (si se proporcionaron evaluaciones de vista aérea)
        if reach_evaluations:
            for idx, re in enumerate(reach_evaluations, 1):
                rule_status = RuleStatus.CONFORME if re.is_compliant else RuleStatus.NO_CONFORME
                action_text = re.action_required or "Ubicación en zona de alcance conforme."
                results.append(RuleEvaluationResult(
                    id_estacion=data.id_estacion,
                    regla=f"E{idx}_{re.point_name}",
                    estado=rule_status,
                    valor_medido=f"Zona {re.zone.value} (r={round(re.r_mm, 1)}mm, dx={round(re.dx_mm, 1)}mm)",
                    limite="Zona 1 o 2 para uso frecuente, Zona 3 para ocasional",
                    referencia_doc="7.2.2.2",
                    origen=self.evaluator.eval_a1_scope(data).origen,
                    accion=action_text,
                    responsable="IE de Célula",
                    documentos_requeridos=[],
                    fecha_deteccion=self.evaluator.detection_date,
                    dias_abierto=0,
                ))

        # Modulo F - Dimensiones
        results.append(self.evaluator.eval_f1_work_surface_height(data))
        results.append(self.evaluator.eval_f2_operator_distance(data))
        results.append(self.evaluator.eval_f3_leg_room_sitting(data))
        results.append(self.evaluator.eval_f5_table_thickness(data))

        # Modulo G - Conveyors
        results.extend(self.evaluator.eval_g_conveyor(data))

        # Modulo H - Pasillos y Seguridad
        results.append(self.evaluator.eval_h4_electrical_and_emergency_clearance(data))
        results.append(self.evaluator.eval_h5_mrb_cage_and_esd(data))

        # Cálculo de resultado global (Sección 5)
        has_critico = any(r.estado == RuleStatus.CRITICO for r in results)
        has_no_conforme = any(r.estado == RuleStatus.NO_CONFORME for r in results)
        has_warning_or_missing = any(
            r.estado in (RuleStatus.ADVERTENCIA, RuleStatus.REVISION_HUMANA, RuleStatus.DATO_FALTANTE)
            for r in results
        )

        if has_critico:
            global_status = RuleStatus.CRITICO
        elif has_no_conforme:
            global_status = RuleStatus.NO_CONFORME
        elif has_warning_or_missing:
            global_status = RuleStatus.ADVERTENCIA
        else:
            global_status = RuleStatus.CONFORME

        fallas = [r for r in results if r.estado in (RuleStatus.CRITICO, RuleStatus.NO_CONFORME)]
        datos_faltantes = [r for r in results if r.estado == RuleStatus.DATO_FALTANTE]

        # Priorización de acciones: CRITICO primero, luego NO CONFORME, luego REVISION_HUMANA/ADVERTENCIA
        prioritized_actions: list[str] = []
        for r in results:
            if r.estado == RuleStatus.CRITICO:
                prioritized_actions.append(f"[CRÍTICO {r.regla}] {r.accion} (Resp: {r.responsable})")
        for r in results:
            if r.estado == RuleStatus.NO_CONFORME:
                prioritized_actions.append(f"[NO CONFORME {r.regla}] {r.accion} (Resp: {r.responsable})")
        for r in results:
            if r.estado in (RuleStatus.REVISION_HUMANA, RuleStatus.ADVERTENCIA):
                prioritized_actions.append(f"[{r.estado.value} {r.regla}] {r.accion} (Resp: {r.responsable})")

        return GlobalStationResult(
            id_estacion=data.id_estacion,
            estado_global=global_status,
            reglas_evaluadas=results,
            fallas=fallas,
            datos_faltantes=datos_faltantes,
            acciones_priorizadas=prioritized_actions,
        )

