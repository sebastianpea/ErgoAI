from backend.app.core_ergonomics.chair_law_evaluator import ChairLawEvaluator


def test_chair_law_tres_horas_continua_es_no_cumple():
    evaluator = ChairLawEvaluator()
    context = {
        "tiempo_pie_continuo_horas": 3.5,
        "espacio_pies_profundidad_cm": 20,
        "tapete_antifatiga": True,
        "reposapiés_altura_cm": 25,
        "espacio_piernas_profundidad_cm": 60,
        "espacio_piernas_ancho_cm": 70,
        "superficie": "concreto",
    }
    result = evaluator.evaluate(context)

    assert result["cumple_ley_silla"] is False
    assert result["alerta_bipedestacion_3h"] is True
    assert len(result["factores"]) == 7


def test_chair_law_menos_de_tres_horas_es_cumple():
    evaluator = ChairLawEvaluator()
    context = {
        "tiempo_pie_continuo_horas": 2.0,
        "espacio_pies_profundidad_cm": 15,
        "tapete_antifatiga": True,
        "reposapiés_altura_cm": 30,
        "espacio_piernas_profundidad_cm": 55,
        "espacio_piernas_ancho_cm": 60,
        "superficie": "tapete",
    }
    result = evaluator.evaluate(context)

    assert result["cumple_ley_silla"] is True
    assert result["alerta_bipedestacion_3h"] is False
    assert len(result["factores"]) == 7


def test_chair_law_siete_factores_retornados():
    evaluator = ChairLawEvaluator()
    context = {
        "tiempo_pie_continuo_horas": 1.0,
        "espacio_pies_profundidad_cm": 15,
        "tapete_antifatiga": True,
        "reposapiés_altura_cm": 30,
        "espacio_piernas_profundidad_cm": 55,
        "espacio_piernas_ancho_cm": 60,
        "superficie": "tapete",
    }
    result = evaluator.evaluate(context)

    factor_codes = {f["codigo"] for f in result["factores"]}
    expected = {
        "tiempo_pie_continuo",
        "cambio_postura",
        "espacio_moverse",
        "malestares_reportados",
        "superficie_tapete",
        "pausas_tareas_alterna",
        "calzado",
    }
    assert factor_codes == expected
