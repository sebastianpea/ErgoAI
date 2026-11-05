"""Operaciones matemáticas vectoriales puras en 2D y utilitarios geométricos con NumPy."""

from __future__ import annotations

import math
from typing import Tuple
import numpy as np

Point2D = Tuple[float, float]
Vector2D = Tuple[float, float]

# En imágenes digitales el eje Y crece hacia abajo (piso = Y máximo)
# Por tanto, el vector vertical contra la gravedad (plomada hacia arriba) es (0, -1)
V_UP: Vector2D = (0.0, -1.0)
V_DOWN: Vector2D = (0.0, 1.0)


def dot_product(u: Vector2D, v: Vector2D) -> float:
    """Calcula el producto punto entre dos vectores 2D."""
    return float(np.dot(np.asarray(u, dtype=np.float64), np.asarray(v, dtype=np.float64)))


def vector_norm(v: Vector2D) -> float:
    """Calcula la norma euclidiana (magnitud) de un vector 2D."""
    return float(np.linalg.norm(np.asarray(v, dtype=np.float64)))


def vector_from_points(p_start: Point2D, p_end: Point2D) -> Vector2D:
    """Crea un vector dirigido desde p_start hacia p_end."""
    return (float(p_end[0] - p_start[0]), float(p_end[1] - p_start[1]))


def distance_2d(p1: Point2D, p2: Point2D) -> float:
    """Calcula la distancia euclidiana en píxeles entre dos puntos 2D."""
    return float(np.hypot(p2[0] - p1[0], p2[1] - p1[1]))


def midpoint_2d(p1: Point2D, p2: Point2D) -> Point2D:
    """Calcula el punto medio entre dos puntos 2D."""
    return (float((p1[0] + p2[0]) / 2.0), float((p1[1] + p2[1]) / 2.0))


def angle_between_vectors(u: Vector2D, v: Vector2D) -> float:
    """Calcula el ángulo en grados sexagesimales [0°, 180°] entre dos vectores 2D con np.arctan2.
    
    Aprovecha la trigonometría vectorial de NumPy (np.arctan2) tomando arreglos de coordenadas
    (x, y) para garantizar estabilidad numérica absoluta sin riesgo de valores NaN derivados
    de desbordamientos en arccos.
    """
    u_arr = np.asarray(u, dtype=np.float64)
    v_arr = np.asarray(v, dtype=np.float64)

    norm_u = np.linalg.norm(u_arr)
    norm_v = np.linalg.norm(v_arr)

    if norm_u < 1e-7 or norm_v < 1e-7:
        return 0.0

    # Determinante (2D cross product z) y producto punto
    det = float(u_arr[0] * v_arr[1] - u_arr[1] * v_arr[0])
    dot = float(u_arr[0] * v_arr[0] + u_arr[1] * v_arr[1])

    # np.arctan2 entrega el ángulo con signo en (-pi, pi]; np.abs lo restringe a [0, pi]
    angle_rad = np.abs(np.arctan2(det, dot))
    return float(np.degrees(angle_rad))
