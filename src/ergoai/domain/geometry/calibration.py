"""Calibración geométrica y conversión dimensional píxeles <-> milímetros/metros."""

from typing import Tuple
from ergoai.domain.geometry.vectors import distance_2d, Point2D


class ScaleCalibrator:
    """Administra la conversión métrica sin valores mágicos ni rutas hardcodeadas."""

    def __init__(self, factor_mm_per_px: float) -> None:
        if factor_mm_per_px <= 0:
            raise ValueError(f"El factor de escala debe ser positivo. Recibido: {factor_mm_per_px}")
        self.factor_mm_per_px = factor_mm_per_px

    @classmethod
    def from_reference(cls, p1: Point2D, p2: Point2D, reference_real_mm: float) -> "ScaleCalibrator":
        """Calibra el factor a partir de dos puntos en píxeles y su distancia real conocida en mm.
        
        Ejemplos de referencias reales en manufactura:
          - Ancho biacromial de hombros del operario (~380-450 mm).
          - Altura conocida de la mesa o conveyor.
          - Estatura referencial del trabajador en vista lateral.
        """
        dist_px = distance_2d(p1, p2)
        if dist_px < 1e-4:
            raise ValueError("Los puntos de referencia no pueden ser coincidentes en píxeles.")
        if reference_real_mm <= 0:
            raise ValueError("La dimensión real de referencia debe ser mayor a cero.")
        
        factor = reference_real_mm / dist_px
        return cls(factor_mm_per_px=factor)

    def px_to_mm(self, dist_px: float) -> float:
        """Convierte una distancia en píxeles a milímetros reales."""
        return dist_px * self.factor_mm_per_px

    def px_to_m(self, dist_px: float) -> float:
        """Convierte una distancia en píxeles a metros reales."""
        return (dist_px * self.factor_mm_per_px) / 1000.0

    def mm_to_px(self, dist_mm: float) -> float:
        """Convierte milímetros reales a píxeles."""
        return dist_mm / self.factor_mm_per_px

