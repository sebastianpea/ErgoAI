"""Módulo geométrico y biomecánico de ErgoAI."""

from ergoai.domain.geometry.vectors import (
    Point2D,
    Vector2D,
    V_UP,
    V_DOWN,
    dot_product,
    vector_norm,
    vector_from_points,
    distance_2d,
    midpoint_2d,
    angle_between_vectors,
)
from ergoai.domain.geometry.calibration import ScaleCalibrator
from ergoai.domain.geometry.reach_zones import ReachZoneClassifier
from ergoai.domain.geometry.biomechanics import BiomechanicalGeometryCalculator

__all__ = [
    "Point2D",
    "Vector2D",
    "V_UP",
    "V_DOWN",
    "dot_product",
    "vector_norm",
    "vector_from_points",
    "distance_2d",
    "midpoint_2d",
    "angle_between_vectors",
    "ScaleCalibrator",
    "ReachZoneClassifier",
    "BiomechanicalGeometryCalculator",
]

