"""Tests unitarios para las Zonas de Alcance digitalizadas (4.E / Sección 7.2.2.2)."""

import pytest
from ergoai.domain.geometry.reach_zones import ReachZoneClassifier
from ergoai.domain.models.reach_zones import ZoneClassification
from ergoai.domain.geometry.calibration import ScaleCalibrator


def test_classify_coordinates_upper_arcs():
    # Zona 1: muy cerca del centro al frente
    z1 = ReachZoneClassifier.classify_coordinates(dx_mm=50.0, dy_mm=200.0)
    assert z1 == ZoneClassification.ZONE_1

    # Zona 2: radio 350 mm al frente (alpha pequeño)
    z2 = ReachZoneClassifier.classify_coordinates(dx_mm=100.0, dy_mm=330.0)
    assert z2 == ZoneClassification.ZONE_2

    # Zona 3: radio 450 mm lateral
    z3 = ReachZoneClassifier.classify_coordinates(dx_mm=300.0, dy_mm=350.0)
    assert z3 == ZoneClassification.ZONE_3

    # Zona 4: radio 450 mm directamente al frente (alpha <= 20°)
    z4 = ReachZoneClassifier.classify_coordinates(dx_mm=50.0, dy_mm=450.0)
    assert z4 == ZoneClassification.ZONE_4

    # Zona 5: radio > 500 mm directamente al frente
    z5 = ReachZoneClassifier.classify_coordinates(dx_mm=50.0, dy_mm=600.0)
    assert z5 == ZoneClassification.ZONE_5

    # Zona 5: lateral extremo dx > 750 mm
    z5_lat = ReachZoneClassifier.classify_coordinates(dx_mm=800.0, dy_mm=200.0)
    assert z5_lat == ZoneClassification.ZONE_5


def test_classify_coordinates_lower_quadrants():
    # Zona 3 cuadrante inferior (detrás de hombros, dy < 0)
    z3_low = ReachZoneClassifier.classify_coordinates(dx_mm=400.0, dy_mm=-100.0)
    assert z3_low == ZoneClassification.ZONE_3

    # Zona 4 cuadrante inferior
    z4_low = ReachZoneClassifier.classify_coordinates(dx_mm=600.0, dy_mm=-100.0)
    assert z4_low == ZoneClassification.ZONE_4

    # Zona 5 fuera de cuadrante inferior
    z5_low = ReachZoneClassifier.classify_coordinates(dx_mm=800.0, dy_mm=-200.0)
    assert z5_low == ZoneClassification.ZONE_5


def test_evaluate_point_compliance_rules():
    calibrator = ScaleCalibrator(factor_mm_per_px=2.0)
    origin_px = (500.0, 500.0)

    # 1. Punto en Zona 1 usado con alta frecuencia -> Conforme
    p_z1 = (520.0, 420.0)  # dx=40mm, dy=160mm
    eval_z1 = ReachZoneClassifier.evaluate_point(
        point_name="Tornillos",
        point_px=p_z1,
        origin_px=origin_px,
        calibrator=calibrator,
        frequency_per_piece=2.0,
    )
    assert eval_z1.zone == ZoneClassification.ZONE_1
    assert eval_z1.is_compliant is True
    assert eval_z1.action_required is None

    # 2. Objeto en Zona 4 o 5 -> NO CONFORME sin importar frecuencia
    p_z5 = (500.0, 100.0)  # dy=800mm -> Zona 5
    eval_z5 = ReachZoneClassifier.evaluate_point(
        point_name="Caja de empaque",
        point_px=p_z5,
        origin_px=origin_px,
        calibrator=calibrator,
        frequency_per_piece=0.2,
    )
    assert eval_z5.zone == ZoneClassification.ZONE_5
    assert eval_z5.is_compliant is False
    assert "Reubicar" in eval_z5.action_required

    # 3. Objeto en Zona 3 con frecuencia >= 1 vez/pieza -> NO CONFORME (debe estar en 1 o 2)
    # dx=300mm (150px), dy=350mm (175px) -> r ~ 460mm, alpha ~ 40° -> Zona 3
    p_z3 = (650.0, 325.0)
    eval_z3_freq = ReachZoneClassifier.evaluate_point(
        point_name="Herramienta neumática",
        point_px=p_z3,
        origin_px=origin_px,
        calibrator=calibrator,
        frequency_per_piece=1.0,
    )
    assert eval_z3_freq.zone == ZoneClassification.ZONE_3
    assert eval_z3_freq.is_compliant is False

