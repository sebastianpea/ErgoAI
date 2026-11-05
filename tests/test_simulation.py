"""Tests unitarios para el Simulador de Riesgo Residual y Jerarquía NOM-036 (Módulo 4.J)."""

import pytest
from ergoai.domain.models.angles import BiomechanicalAngles, ActiveSide
from ergoai.domain.models.reach_zones import ReachPointEvaluation, ZoneClassification
from ergoai.domain.models.simulation import EngineeringControlID
from ergoai.domain.reba.evaluator import REBAEvaluator
from ergoai.domain.simulation.residual_risk import ResidualRiskSimulator


def test_residual_risk_proposals_hierarchy():
    # Postura de riesgo alto: carga 18 kg (> 14 kg), hombro flexionado a 60°, cuello a 30°
    angles = BiomechanicalAngles(
        active_side=ActiveSide.RIGHT,
        trunk_angle=40.0,
        neck_angle=30.0,
        leg_knee_angle=20.0,
        upper_arm_angle=60.0,
        lower_arm_angle=50.0,
        wrist_angle=20.0,
    )
    assessment = REBAEvaluator.evaluate(angles=angles, load_kg=18.0)

    # Objeto en Zona 4
    reach_eval = ReachPointEvaluation(
        point_name="Componente Pesado",
        x_px=100, y_px=100, dx_mm=450, dy_mm=450, r_mm=636, alpha_deg=45,
        zone=ZoneClassification.ZONE_4,
        frequency_per_piece=1.0,
        is_compliant=False,
    )

    proposals = ResidualRiskSimulator.generate_proposals(
        assessment=assessment,
        angles=angles,
        load_kg=18.0,
        reach_evaluations=[reach_eval],
    )

    # Debe haber propuestas de ingeniería
    assert len(proposals) > 0
    # La primera propuesta debe ser Prioridad 1 (Ingeniería) antes que administrativa
    assert proposals[0].priority == 1
    # Debe recomendar B1_LIFTER por carga > 14 kg
    assert any(p.control_id == EngineeringControlID.B1_LIFTER for p in proposals)


def test_residual_risk_simulation_modifiers():
    # Condición inicial de alto riesgo
    angles = BiomechanicalAngles(
        active_side=ActiveSide.RIGHT,
        trunk_angle=50.0,
        trunk_twisted=True,
        neck_angle=35.0,
        leg_knee_angle=45.0,
        upper_arm_angle=75.0,
        upper_arm_abducted=True,
        lower_arm_angle=40.0,
        wrist_angle=25.0,
    )
    initial_assessment = REBAEvaluator.evaluate(
        angles=angles,
        load_kg=18.0,
        is_repetitive=True,
    )
    assert initial_assessment.final_score >= 9

    # Aprobación de controles de ingeniería: Lifter (B1), Reubicación a Zona 1/2 (E1), Ajuste de altura (F1)
    controls = [
        EngineeringControlID.B1_LIFTER,
        EngineeringControlID.E1_RELOCATE_ZONE,
        EngineeringControlID.F1_HEIGHT_ADJUST,
    ]

    # Simulación sin aprobación del especialista: el pase a piso debe estar bloqueado (Invariante 1)
    comparison_unapproved, _ = ResidualRiskSimulator.simulate(
        initial_assessment=initial_assessment,
        angles=angles,
        initial_load_kg=18.0,
        approved_controls=controls,
        validated_by_specialist=False,
    )
    assert comparison_unapproved.residual_reba_score < comparison_unapproved.initial_reba_score
    assert comparison_unapproved.score_delta > 0
    assert comparison_unapproved.can_pass_to_floor is False  # Invariante 1 bloqueante

    # Simulación con validación del especialista
    comparison_approved, audit_log = ResidualRiskSimulator.simulate(
        initial_assessment=initial_assessment,
        angles=angles,
        initial_load_kg=18.0,
        approved_controls=controls,
        validated_by_specialist=True,
        specialist_user_id="ING_ERGONOMIA_01",
    )
    assert comparison_approved.can_pass_to_floor is True
    assert comparison_approved.risk_reduction_pct > 40.0
    assert len(audit_log) == 1
    assert audit_log[0].specialist_user_id == "ING_ERGONOMIA_01"

