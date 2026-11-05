"""Simulador de Riesgo Residual ergonómico y Jerarquía de Controles NOM-036-1 (Módulo 4.J)."""

import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from ergoai.domain.models.angles import BiomechanicalAngles
from ergoai.domain.models.reba import REBAAssessment, REBARiskLevel
from ergoai.domain.models.reach_zones import ReachPointEvaluation, ZoneClassification
from ergoai.domain.models.simulation import (
    EngineeringControlID,
    EngineeringControlProposal,
    ResidualRiskComparison,
)
from ergoai.domain.models.audit import AuditLogEntry
from ergoai.domain.reba.evaluator import REBAEvaluator
from ergoai.domain.constants import (
    JABIL_MAX_SINGLE_PERSON_LOAD_KG,
    REBA_ARM_SCORE_2_MAX_DEG,
    REBA_NECK_SCORE_1_MAX_DEG,
    REBA_ELBOW_OPTIMAL_MIN_DEG,
    REBA_ELBOW_OPTIMAL_MAX_DEG,
)


class ResidualRiskSimulator:
    """Calcula y proyecta el impacto ergonómico post-intervención de controles de ingeniería."""

    @classmethod
    def generate_proposals(
        cls,
        assessment: REBAAssessment,
        angles: BiomechanicalAngles,
        load_kg: float,
        reach_evaluations: Optional[List[ReachPointEvaluation]] = None,
    ) -> List[EngineeringControlProposal]:
        """Genera propuestas de control priorizando Controles de Ingeniería (Prioridad 1) sobre Administrativos."""
        proposals: List[EngineeringControlProposal] = []

        # 1. Carga > 14 kg -> Control B1 / NOM-036
        if load_kg > JABIL_MAX_SINGLE_PERSON_LOAD_KG:
            proposals.append(EngineeringControlProposal(
                control_id=EngineeringControlID.B1_LIFTER,
                priority=1,
                title="Instalación de Asistencia Mecánica (Lifter / Balancín)",
                description=f"La carga manipulada ({load_kg} kg) excede el estándar de {int(JABIL_MAX_SINGLE_PERSON_LOAD_KG)} kg. "
                            "Instalar equipo de levante para anular el esfuerzo lumbar y carga manual.",
                nom036_clause="NOM-036-1-STPS-2018 Numeral 7.1 / Jabil 6.4.1",
            ))

        # 2. Tomas forzadas de altura -> Control B4
        if angles.upper_arm_angle > REBA_ARM_SCORE_2_MAX_DEG or angles.shoulder_elevated:
            proposals.append(EngineeringControlProposal(
                control_id=EngineeringControlID.B4_LOWER_PICKUP,
                priority=1,
                title="Rediseño de Altura de Toma en Racks / Carros",
                description="Bajar el nivel de toma a cota <= 1.7 m (rack) o <= 1.6 m (carro) "
                            "para evitar flexión de hombros superior a 40°.",
                nom036_clause="NOM-036-1-STPS-2018 Numeral 7.2 / Jabil 6.4.4",
            ))

        # 3. Objetos fuera de alcance en Zonas 4 o 5 -> Control E1
        has_outer_reach = False
        if reach_evaluations:
            has_outer_reach = any(
                e.zone in (ZoneClassification.ZONE_4, ZoneClassification.ZONE_5)
                for e in reach_evaluations
            )
        if has_outer_reach or angles.upper_arm_abducted or angles.trunk_twisted:
            proposals.append(EngineeringControlProposal(
                control_id=EngineeringControlID.E1_RELOCATE_ZONE,
                priority=1,
                title="Reubicación de Materiales a Zonas 1 y 2 (< 400 mm)",
                description="Reubicar gavetas y herramientas de ensamble a la zona de alcance óptimo (< 400 mm) "
                            "para eliminar abducción coronal y torsión axial de tronco.",
                nom036_clause="NOM-036-1-STPS-2018 Numeral 7.2.2 / Jabil 7.2.2.2",
            ))

        # 4. Altura de mesa inadecuada / flexión cervical -> Control F1
        if angles.neck_angle > REBA_NECK_SCORE_1_MAX_DEG or angles.lower_arm_angle < REBA_ELBOW_OPTIMAL_MIN_DEG or angles.lower_arm_angle > REBA_ELBOW_OPTIMAL_MAX_DEG:
            proposals.append(EngineeringControlProposal(
                control_id=EngineeringControlID.F1_HEIGHT_ADJUST,
                priority=1,
                title="Ajuste Antropométrico de Altura de Mesa (95 - 125 cm)",
                description="Graduar la superficie de ensamble al plano de los codos (85°-90°) "
                            "para reducir la flexión cervical a <= 15° y optimizar antebrazos.",
                nom036_clause="NOM-036-1-STPS-2018 Numeral 7.3 / Jabil 7.2.3",
            ))

        # 5. Desviación de muñeca / herramienta inadecuada -> Control TOOL_CHANGE_ERGONOMIC
        if angles.wrist_angle > 15.0 or angles.wrist_twisted_or_deviated:
            proposals.append(EngineeringControlProposal(
                control_id=EngineeringControlID.TOOL_CHANGE_ERGONOMIC,
                priority=1,  # Control de ingeniería
                title="Sustitución por Herramienta Ergonómica con Balancín",
                description="Reemplazar la herramienta manual por modelo con empuñadura ergonómica axial y "
                            "brazo de reacción/balancín para eliminar la desviación ulnar/radial de muñeca (> 15°).",
                nom036_clause="NOM-036-1-STPS-2018 Numeral 7.2 / Jabil 6.4.3",
            ))

        # 6. Bipedestación estática / Alternancia postural -> Control SIT_STAND_ALTERNATION
        if assessment.activity.is_static or angles.leg_knee_angle > 25.0:
            proposals.append(EngineeringControlProposal(
                control_id=EngineeringControlID.SIT_STAND_ALTERNATION,
                priority=1,  # Rediseño de estación
                title="Estación Sit-Stand Regulable y Tapete Antifatiga",
                description="Habilitar sistema electro-mecánico de elevación de mesa para alternar la postura "
                            "entre sentado y de pie durante el turno, reduciendo la compresión discal.",
                nom036_clause="NOM-036-1-STPS-2018 Numeral 7.3 / Jabil 7.2.2",
            ))

        # 7. Bipedestación continua / Ley Silla -> Control C1 / D3
        if assessment.risk_level in (REBARiskLevel.HIGH, REBARiskLevel.VERY_HIGH) or angles.leg_unilateral_or_unstable:
            proposals.append(EngineeringControlProposal(
                control_id=EngineeringControlID.C1_D3_ESD_CHAIR,
                priority=2,  # Prioridad 2: Medida administrativa / relevo o silla de descanso
                title="Dotación de Silla Estándar ESD y Programa de Descanso Sit-Stand",
                description="Asignar silla ergonómica de 5 patas ESD y rol de alternancia para evitar "
                            "bipedestación continua mayor a 3 horas según Ley Silla.",
                nom036_clause="Ley Silla / Jabil 7.2.2.1",
            ))

        return proposals

    @classmethod
    def simulate(
        cls,
        initial_assessment: REBAAssessment,
        angles: BiomechanicalAngles,
        initial_load_kg: float,
        approved_controls: List[EngineeringControlID],
        validated_by_specialist: bool = False,
        specialist_user_id: str = "ESPECIALISTA_EHS",
        station_id: str = "STATION_01",
    ) -> Tuple[ResidualRiskComparison, List[AuditLogEntry]]:
        """Aplica los modificadores biomecánicos de los controles aprobados y recalcula el REBA residual."""
        audit_entries: List[AuditLogEntry] = []
        now_iso = datetime.now(timezone.utc).isoformat()

        # Clonar valores base
        sim_load_kg = initial_load_kg
        sim_trunk = angles.trunk_angle
        sim_trunk_twisted = angles.trunk_twisted
        sim_neck = angles.neck_angle
        sim_knee = angles.leg_knee_angle
        sim_leg_unilateral = angles.leg_unilateral_or_unstable
        sim_upper_arm = angles.upper_arm_angle
        sim_upper_arm_abducted = angles.upper_arm_abducted
        sim_shoulder_elevated = angles.shoulder_elevated
        sim_lower_arm = angles.lower_arm_angle
        sim_wrist = angles.wrist_angle
        sim_wrist_twisted = angles.wrist_twisted_or_deviated
        sim_static = initial_assessment.activity.is_static
        sim_repetitive = initial_assessment.activity.is_repetitive
        sim_shock = False

        # Aplicación estricta de modificadores (Sección 4.J):
        for ctrl in approved_controls:
            if ctrl == EngineeringControlID.B1_LIFTER:
                sim_load_kg = 0.0
                sim_trunk = min(sim_trunk, 15.0)
                sim_shock = False
            elif ctrl == EngineeringControlID.B4_LOWER_PICKUP:
                sim_upper_arm = min(sim_upper_arm, 40.0)
                sim_shoulder_elevated = False
            elif ctrl == EngineeringControlID.E1_RELOCATE_ZONE:
                sim_upper_arm = min(sim_upper_arm, 20.0)
                sim_trunk = min(sim_trunk, 10.0)
                sim_upper_arm_abducted = False
                sim_trunk_twisted = False
            elif ctrl == EngineeringControlID.F1_HEIGHT_ADJUST:
                sim_neck = min(sim_neck, 15.0)
                sim_lower_arm = 85.0  # Rango óptimo 60°-100°
                sim_trunk = min(sim_trunk, 10.0)
            elif ctrl == EngineeringControlID.TOOL_CHANGE_ERGONOMIC:
                sim_wrist = min(sim_wrist, 10.0)
                sim_wrist_twisted = False
                sim_lower_arm = 85.0
            elif ctrl == EngineeringControlID.SIT_STAND_ALTERNATION:
                sim_knee = 0.0
                sim_leg_unilateral = False
                sim_static = False
            elif ctrl == EngineeringControlID.C1_D3_ESD_CHAIR:
                sim_leg_unilateral = False
                sim_knee = 0.0
                sim_static = False

        # Crear nuevo modelo simulado
        sim_angles = BiomechanicalAngles(
            active_side=angles.active_side,
            trunk_angle=sim_trunk,
            trunk_is_extension=angles.trunk_is_extension if sim_trunk > 10.0 else False,
            trunk_twisted=sim_trunk_twisted,
            trunk_side_bending=False,
            neck_angle=sim_neck,
            neck_is_extension=False,
            neck_twisted=False,
            neck_side_bending=False,
            neck_needs_human_review=False,
            leg_knee_angle=sim_knee,
            leg_bilateral_support=not sim_leg_unilateral,
            leg_unilateral_or_unstable=sim_leg_unilateral,
            upper_arm_angle=sim_upper_arm,
            upper_arm_is_extension=False,
            upper_arm_abducted=sim_upper_arm_abducted,
            shoulder_elevated=sim_shoulder_elevated,
            arm_supported_or_gravity_assisted=angles.arm_supported_or_gravity_assisted,
            lower_arm_angle=sim_lower_arm,
            wrist_angle=sim_wrist,
            wrist_twisted_or_deviated=sim_wrist_twisted,
            pickup_height_m=angles.pickup_height_m,
        )

        residual_assessment = REBAEvaluator.evaluate(
            angles=sim_angles,
            load_kg=sim_load_kg,
            is_shock_load=sim_shock,
            coupling_score=initial_assessment.group_b.coupling_score,
            is_static=sim_static,
            is_repetitive=sim_repetitive,
            is_rapid_change_or_unstable=False,
        )

        delta = initial_assessment.final_score - residual_assessment.final_score
        reduction_pct = max(0.0, (delta / initial_assessment.final_score) * 100.0)

        # Invariante 1: El especialista decide; paso bloqueante a piso
        can_pass = validated_by_specialist and (len(approved_controls) > 0)

        # Registro inmutable en audit_log
        audit_entries.append(AuditLogEntry(
            entry_id=str(uuid.uuid4()),
            timestamp_iso=now_iso,
            specialist_user_id=specialist_user_id,
            id_estacion=station_id,
            action_type="SIMULACION_RIESGO_RESIDUAL",
            field_name="approved_controls",
            previous_value=f"REBA={initial_assessment.final_score} ({initial_assessment.color_code})",
            new_value=f"REBA_Residual={residual_assessment.final_score} ({residual_assessment.color_code})",
            justification=f"Controles aprobados: {[c.value for c in approved_controls]}",
            is_blocking_approved=can_pass,
        ))

        comparison = ResidualRiskComparison(
            initial_reba_score=initial_assessment.final_score,
            initial_risk_level=f"{initial_assessment.risk_level.name} ({initial_assessment.color_code})",
            applied_controls=approved_controls,
            residual_reba_score=residual_assessment.final_score,
            residual_risk_level=f"{residual_assessment.risk_level.name} ({residual_assessment.color_code})",
            score_delta=delta,
            risk_reduction_pct=round(reduction_pct, 1),
            validated_by_specialist=validated_by_specialist,
            can_pass_to_floor=can_pass,
        )

        return comparison, audit_entries

