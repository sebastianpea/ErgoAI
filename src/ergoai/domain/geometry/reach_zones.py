"""Clasificador digitalizado de Zonas de Alcance en Vista Aérea (Sección 7.2.2.2 de Jabil)."""

import math
from typing import Tuple
from ergoai.domain.models.reach_zones import ZoneClassification, ReachPointEvaluation
from ergoai.domain.geometry.calibration import ScaleCalibrator
from ergoai.domain.geometry.vectors import Point2D
from ergoai.domain.constants import (
    REACH_ZONE_1_MAX_R_MM,
    REACH_ZONE_1_MAX_ALPHA_DEG,
    REACH_ZONE_1_CENTRAL_BOX_MM,
    REACH_ZONE_2_MAX_R_MM,
    REACH_ZONE_2_MAX_ALPHA_DEG,
    REACH_ZONE_2_MAX_DX_MM,
    REACH_ZONE_3_MAX_R_MM,
    REACH_ZONE_3_MAX_DX_MM,
    REACH_ZONE_3_MIN_ALPHA_DEG,
    REACH_ZONE_4_MAX_DX_MM,
    REACH_ZONE_LOWER_MAX_DEPTH_MM,
    REACH_ZONE_LOWER_MID_DEPTH_MM,
)


class ReachZoneClassifier:
    """Clasifica coordenadas en Vista Aérea dentro de las Zonas 1 a 5 de Jabil."""

    @staticmethod
    def classify_coordinates(dx_mm: float, dy_mm: float) -> ZoneClassification:
        """Determina la zona biomecánica a partir de las coordenadas radiales y polares."""
        r_mm = math.hypot(dx_mm, dy_mm)
        # alpha es el ángulo de apertura lateral respecto al frente (0° = directamente al frente)
        alpha_rad = math.atan2(dx_mm, max(1e-6, dy_mm))
        alpha_deg = math.degrees(alpha_rad)

        if dy_mm >= 0.0:
            # Cuadrantes superiores (Frente al plano de hombros)
            if (r_mm <= REACH_ZONE_1_MAX_R_MM and alpha_deg <= REACH_ZONE_1_MAX_ALPHA_DEG) or \
               (dx_mm <= REACH_ZONE_1_CENTRAL_BOX_MM and dy_mm <= REACH_ZONE_1_CENTRAL_BOX_MM):
                return ZoneClassification.ZONE_1

            if (REACH_ZONE_1_MAX_R_MM < r_mm <= REACH_ZONE_2_MAX_R_MM and alpha_deg <= REACH_ZONE_2_MAX_ALPHA_DEG) or \
               (r_mm <= REACH_ZONE_2_MAX_R_MM and alpha_deg > REACH_ZONE_2_MAX_ALPHA_DEG and dx_mm <= REACH_ZONE_2_MAX_DX_MM):
                return ZoneClassification.ZONE_2

            if (REACH_ZONE_2_MAX_R_MM < r_mm <= REACH_ZONE_3_MAX_R_MM and alpha_deg > REACH_ZONE_3_MIN_ALPHA_DEG and dx_mm <= REACH_ZONE_3_MAX_DX_MM):
                return ZoneClassification.ZONE_3

            # Zona 5 en el eje central superior o exceso lateral
            if (r_mm > REACH_ZONE_3_MAX_R_MM and alpha_deg <= REACH_ZONE_3_MIN_ALPHA_DEG) or (dx_mm > REACH_ZONE_4_MAX_DX_MM):
                return ZoneClassification.ZONE_5

            if (REACH_ZONE_2_MAX_R_MM < r_mm <= REACH_ZONE_3_MAX_R_MM and alpha_deg <= REACH_ZONE_3_MIN_ALPHA_DEG) or \
               (r_mm > REACH_ZONE_3_MAX_R_MM and dx_mm <= REACH_ZONE_4_MAX_DX_MM):
                return ZoneClassification.ZONE_4

            return ZoneClassification.ZONE_5

        else:
            # Cuadrantes inferiores laterales (Detrás del plano de hombros, dy_mm < 0)
            abs_dy = abs(dy_mm)
            if abs_dy <= REACH_ZONE_LOWER_MAX_DEPTH_MM:
                if (REACH_ZONE_1_MAX_R_MM <= dx_mm <= REACH_ZONE_2_MAX_DX_MM) and (abs_dy <= REACH_ZONE_LOWER_MID_DEPTH_MM):
                    return ZoneClassification.ZONE_3
                if ((REACH_ZONE_2_MAX_DX_MM < dx_mm <= REACH_ZONE_4_MAX_DX_MM) and (abs_dy <= REACH_ZONE_LOWER_MID_DEPTH_MM)) or \
                   ((REACH_ZONE_1_MAX_R_MM <= dx_mm <= REACH_ZONE_4_MAX_DX_MM) and (REACH_ZONE_LOWER_MID_DEPTH_MM < abs_dy <= REACH_ZONE_LOWER_MAX_DEPTH_MM)):
                    return ZoneClassification.ZONE_4

            return ZoneClassification.ZONE_5

    @classmethod
    def evaluate_point(
        cls,
        point_name: str,
        point_px: Point2D,
        origin_px: Point2D,
        calibrator: ScaleCalibrator,
        frequency_per_piece: float = 1.0,
    ) -> ReachPointEvaluation:
        """Evalúa un punto de material o herramental en vista aérea con sus reglas de conformidad."""
        x_obj, y_obj = point_px
        x_orig, y_orig = origin_px

        # Conversión a milímetros centrados en el operario
        dx_mm = abs(x_obj - x_orig) * calibrator.factor_mm_per_px
        # En imagen aérea estándar el operario mira hacia el frente (Y decrece hacia adelante)
        dy_mm = (y_orig - y_obj) * calibrator.factor_mm_per_px

        r_mm = math.hypot(dx_mm, dy_mm)
        alpha_rad = math.atan2(dx_mm, max(1e-6, dy_mm))
        alpha_deg = math.degrees(alpha_rad)

        zone = cls.classify_coordinates(dx_mm, dy_mm)

        # Reglas E1 - E4:
        # E3: Todo material usado en Zona 4 o 5 es NO CONFORME
        if zone in (ZoneClassification.ZONE_4, ZoneClassification.ZONE_5):
            is_compliant = False
            action = f"Reubicar material/herramienta a Zonas 1 o 2 (< {int(REACH_ZONE_2_MAX_R_MM)} mm)"
        elif frequency_per_piece >= 1.0:
            # Uso regular (>= 1 vez por pieza) debe estar en Zona 1 o 2
            is_compliant = zone in (ZoneClassification.ZONE_1, ZoneClassification.ZONE_2)
            action = None if is_compliant else f"Material frecuente en Zona 3: Reubicar a Zonas 1 o 2 (< {int(REACH_ZONE_2_MAX_R_MM)} mm)"
        else:
            # Uso ocasional (< 1 vez por pieza) permite Zona 3
            is_compliant = zone in (ZoneClassification.ZONE_1, ZoneClassification.ZONE_2, ZoneClassification.ZONE_3)
            action = None if is_compliant else "Reubicar objeto fuera de alcance a Zona 1, 2 o 3"

        return ReachPointEvaluation(
            point_name=point_name,
            x_px=x_obj,
            y_px=y_obj,
            dx_mm=dx_mm,
            dy_mm=dy_mm,
            r_mm=r_mm,
            alpha_deg=alpha_deg,
            zone=zone,
            frequency_per_piece=frequency_per_piece,
            is_compliant=is_compliant,
            action_required=action,
        )
