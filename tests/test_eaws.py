from backend.app.core_ergonomics.eaws_calculator import EawsCalculator


def test_eaws_low_risk():
    calc = EawsCalculator()
    result = calc.calculate(
        trunk_flexion_deg=10,
        torso_twist_deg=5,
        work_above_shoulder=False,
        work_below_knee=False,
        force_kg=3,
        frequency_actions_per_shift=50,
    )
    assert result["total_score"] <= 5
    assert result["risk_level"] == "Bajo"


def test_eaws_medium_risk():
    calc = EawsCalculator()
    result = calc.calculate(
        trunk_flexion_deg=30,
        torso_twist_deg=10,
        work_above_shoulder=False,
        work_below_knee=False,
        force_kg=7,
        frequency_actions_per_shift=300,
    )
    assert result["risk_level"] == "Medio"


def test_eaws_high_risk():
    calc = EawsCalculator()
    result = calc.calculate(
        trunk_flexion_deg=50,
        torso_twist_deg=30,
        work_above_shoulder=True,
        work_below_knee=True,
        force_kg=12,
        frequency_actions_per_shift=600,
    )
    assert result["total_score"] > 10
    assert result["risk_level"] == "Alto"
