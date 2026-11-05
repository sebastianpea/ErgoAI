"""Tests unitarios para las Reglas de Negocio Ergonómicas de Jabil (Módulos A a I y Motor)."""

import pytest
from ergoai.domain.models.workstation import (
    WorkstationInputData,
    WorkstationType,
    RuleStatus,
    ChairLawAnswers,
    WorkstationDimensions,
    WorkstationLiftingData,
    WorkstationConveyorData,
    WorkstationAislesData,
)
from ergoai.domain.rules.engine import ErgonomicRulesEngine


def test_scope_non_productive():
    engine = ErgonomicRulesEngine()
    data = WorkstationInputData(
        id_estacion="OFICINA_01",
        tipo=WorkstationType.NON_PRODUCTIVE,
    )
    result = engine.evaluate_station(data)
    assert result.estado_global == RuleStatus.NO_APLICA


def test_b1_weight_limit_14kg():
    engine = ErgonomicRulesEngine()
    # 1. Conforme: 12 kg por 1 persona
    data_ok = WorkstationInputData(
        id_estacion="BE_01",
        lifting=WorkstationLiftingData(weight_kg=12.0, num_people=1),
    )
    res_b1_ok = engine.evaluator.eval_b1_single_person_weight(data_ok)
    assert res_b1_ok.estado == RuleStatus.CONFORME

    # 2. No conforme: 16 kg por 1 persona sin lifter
    data_fail = WorkstationInputData(
        id_estacion="BE_02",
        lifting=WorkstationLiftingData(weight_kg=16.0, num_people=1, has_mechanical_assist=False),
    )
    res_b1_fail = engine.evaluator.eval_b1_single_person_weight(data_fail)
    assert res_b1_fail.estado == RuleStatus.NO_CONFORME
    assert "asistencia mecánica" in res_b1_fail.accion


def test_b2_containment_tables():
    engine = ErgonomicRulesEngine()
    # 2 personas 20 kg (Tabla Naranja) sin visto bueno médico -> NO CONFORME
    data_orange_no_med = WorkstationInputData(
        id_estacion="BE_03",
        lifting=WorkstationLiftingData(
            weight_kg=20.0, num_people=2, medical_clearance=False, has_form_00014=True, has_moc=True
        ),
    )
    res_orange = engine.evaluator.eval_b2_team_containment(data_orange_no_med)
    assert res_orange.estado == RuleStatus.NO_CONFORME

    # Carga fuera de tablas: 2 personas 35 kg -> CRITICO
    data_crit = WorkstationInputData(
        id_estacion="BE_04",
        lifting=WorkstationLiftingData(weight_kg=35.0, num_people=2),
    )
    res_crit = engine.evaluator.eval_b2_team_containment(data_crit)
    assert res_crit.estado == RuleStatus.CRITICO


def test_ley_silla_and_continuous_standing():
    engine = ErgonomicRulesEngine()
    # Preguntas Ley Silla: todas respuestas 1 -> total 7 -> VERDE (no aplica)
    answers_green = ChairLawAnswers(
        p1_standing_time=1, p2_posture_change=1, p3_surface_type=1,
        p4_footwear=1, p5_space=1, p6_discomfort=1, p7_breaks=1
    )
    data_green = WorkstationInputData(
        id_estacion="BE_05",
        posture_proposed="de_pie",
        chair_law=answers_green,
    )
    res_d1 = engine.evaluator.eval_d1_chair_law_score(data_green)
    assert res_d1.estado == RuleStatus.CONFORME

    # Bipedestación continua > 180 min -> NO CONFORME
    data_time_exceeded = WorkstationInputData(
        id_estacion="BE_06",
        posture_proposed="de_pie",
        standing_continuous_time_min=200.0,
        seated_pause_min=0.0,
    )
    res_d2 = engine.evaluator.eval_d2_standing_time_limit(data_time_exceeded)
    assert res_d2.estado == RuleStatus.NO_CONFORME


def test_safety_critical_rules():
    engine = ErgonomicRulesEngine()
    # Conveyor eléctrico sin guardas móviles -> CRITICO
    data_conveyor_no_guards = WorkstationInputData(
        id_estacion="SMT_01",
        conveyor=WorkstationConveyorData(
            has_conveyor=True,
            conveyor_type="electrico",
            moving_parts_guards=False,
        ),
    )
    res_g3 = engine.evaluator.eval_g_conveyor(data_conveyor_no_guards)
    crit_guards = [r for r in res_g3 if r.regla == "G3"]
    assert len(crit_guards) == 1
    assert crit_guards[0].estado == RuleStatus.CRITICO

    # Tablero eléctrico con despeje < 90 cm -> CRITICO
    data_panel_blocked = WorkstationInputData(
        id_estacion="SMT_02",
        aisles=WorkstationAislesData(electrical_panel_clearance_cm=50.0),
    )
    res_h4 = engine.evaluator.eval_h4_electrical_and_emergency_clearance(data_panel_blocked)
    assert res_h4.estado == RuleStatus.CRITICO


def test_global_station_result_priority():
    engine = ErgonomicRulesEngine()
    # Estación con regla crítica: estado global debe ser CRITICO
    data = WorkstationInputData(
        id_estacion="EST_TEST",
        tipo=WorkstationType.BE,
        conveyor=WorkstationConveyorData(
            has_conveyor=True,
            conveyor_type="electrico",
            moving_parts_guards=False,
        ),
    )
    global_res = engine.evaluate_station(data)
    assert global_res.estado_global == RuleStatus.CRITICO
    assert any("[CRÍTICO" in act for act in global_res.acciones_priorizadas)

