"""Tests unitarios para la evaluación ergonómica REBA (R1 a R4)."""

import pytest
from ergoai.domain.reba.tables import lookup_table_a, lookup_table_b, lookup_table_c
from ergoai.domain.reba.evaluator import REBAEvaluator
from ergoai.domain.models.angles import BiomechanicalAngles, ActiveSide
from ergoai.domain.models.reba import REBARiskLevel


def test_reba_tables_lookups():
    # Tabla A casos de control
    assert lookup_table_a(trunk=1, neck=1, legs=1) == 1
    assert lookup_table_a(trunk=4, neck=3, legs=4) == 9
    assert lookup_table_a(trunk=5, neck=3, legs=4) == 9

    # Tabla B casos de control
    assert lookup_table_b(upper_arm=1, lower_arm=1, wrist=1) == 1
    assert lookup_table_b(upper_arm=6, lower_arm=2, wrist=3) == 9

    # Tabla C casos de control
    assert lookup_table_c(score_a=1, score_b=1) == 1
    assert lookup_table_c(score_a=12, score_b=12) == 12


def test_reba_negligible_posture():
    # Postura neutra ideal
    angles = BiomechanicalAngles(
        active_side=ActiveSide.RIGHT,
        trunk_angle=2.0,      # Score 1
        neck_angle=10.0,      # Score 1
        leg_knee_angle=0.0,   # Score 1
        upper_arm_angle=15.0, # Score 1
        lower_arm_angle=90.0, # Score 1
        wrist_angle=5.0,      # Score 1
    )
    res = REBAEvaluator.evaluate(angles=angles, load_kg=0.0)
    assert res.final_score == 1
    assert res.risk_level == REBARiskLevel.NEGLIGIBLE
    assert res.color_code == "VERDE"


def test_reba_high_risk_posture():
    # Postura forzada: tronco muy flexionado (50°), cuello flexionado (30°),
    # brazo elevado (70°), carga de 12 kg
    angles = BiomechanicalAngles(
        active_side=ActiveSide.RIGHT,
        trunk_angle=50.0,      # Tronco 3
        trunk_twisted=True,    # Tronco +1 -> 4
        neck_angle=30.0,       # Cuello 2
        leg_knee_angle=45.0,   # Piernas rodilla flex -> 2
        upper_arm_angle=70.0,  # Brazo 3
        upper_arm_abducted=True, # +1 -> 4
        lower_arm_angle=40.0,  # Antebrazo 2 (<60°)
        wrist_angle=25.0,      # Muñeca 2 (>15°)
        wrist_twisted_or_deviated=True, # +1 -> 3
    )

    res = REBAEvaluator.evaluate(
        angles=angles,
        load_kg=12.0,       # +2 por carga
        is_repetitive=True, # +1 actividad
    )

    # Debe ser riesgo Alto o Muy Alto
    assert res.final_score >= 8
    assert res.risk_level in (REBARiskLevel.HIGH, REBARiskLevel.VERY_HIGH)
    assert res.color_code in ("ROJO", "CRITICO")

