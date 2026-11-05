"""Motor de renderizado y anotaciones ergonómicas sobre imágenes con OpenCV y RTMPose.

Renderiza la capa visual por excepción:
  - Arcos de zonas de alcance ergonómicas (cv2.ellipse).
  - Colores de riesgo postural REBA (Verde, Amarillo, Naranja, Rojo, Púrpura).
  - Tarjetas y textos informativos con opacidad configurable (cv2.addWeighted).
  - Reglas multi-persona (Regla F2 de distancia inter-operador).
Configuración inyectada y validada mediante esquemas de Pydantic sin hardcode.
"""

from typing import Dict, List, Optional, Tuple
import cv2
import numpy as np
from rtmlib import draw_skeleton

from ergoai.config.vision_schema import VisionConfigSchema
from ergoai.domain.models.keypoints import WholeBodyKeypointIndex, Pose2D
from ergoai.domain.models.angles import BiomechanicalAngles
from ergoai.domain.constants import (
    REBA_NECK_SCORE_1_MAX_DEG,
    REBA_TRUNK_SCORE_2_MAX_DEG,
    REBA_ARM_SCORE_2_MAX_DEG,
    REBA_KNEE_SCORE_ADJ_1_MIN_DEG,
)

# Carga de reglas de visualización mediante Pydantic (elimina hardcode)
DEFAULT_CONFIG = VisionConfigSchema.load_from_json()


def get_reba_color_bgr(
    score: int,
    config: Optional[VisionConfigSchema] = None,
) -> Tuple[int, int, int]:
    """Retorna el color BGR correspondiente al nivel de riesgo REBA según esquema Pydantic."""
    cfg = config or DEFAULT_CONFIG
    cmap = cfg.visualization_rules.reba_color_map
    if score <= 1:
        c = cmap.get("VERDE", [46, 204, 113])
    elif score <= 3:
        c = cmap.get("AMARILLO", [0, 215, 255])
    elif score <= 7:
        c = cmap.get("NARANJA", [0, 140, 255])
    elif score <= 10:
        c = cmap.get("ROJO", [40, 40, 230])
    else:
        c = cmap.get("CRITICO", [142, 36, 170])
    return (int(c[0]), int(c[1]), int(c[2]))


def draw_operator_card(
    canvas: np.ndarray,
    bbox: Tuple[float, float, float, float],
    operator_id: str,
    reba_score: Optional[int] = None,
    risk_level_str: Optional[str] = None,
    color_bgr: Optional[Tuple[int, int, int]] = None,
    config: Optional[VisionConfigSchema] = None,
) -> None:
    """Dibuja un marco delimitador elegante y tarjeta con opacidad sobre el operador usando OpenCV."""
    cfg = config or DEFAULT_CONFIG
    if color_bgr is None:
        color_bgr = get_reba_color_bgr(reba_score or 1, cfg)

    x1, y1, x2, y2 = [int(v) for v in bbox]
    h_img, w_img = canvas.shape[:2]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w_img, x2), min(h_img, y2)

    # Esquinas estilizadas en lugar de un rectángulo plano
    corner_len = min(25, (x2 - x1) // 4, (y2 - y1) // 4)
    lw = cfg.visualization_rules.skeleton_line_width
    cv2.rectangle(canvas, (x1, y1), (x2, y2), color_bgr, 1, cv2.LINE_AA)

    # Esquinas gruesas destacadas
    if corner_len > 5:
        # Superior Izquierda
        cv2.line(canvas, (x1, y1), (x1 + corner_len, y1), color_bgr, lw + 1, cv2.LINE_AA)
        cv2.line(canvas, (x1, y1), (x1, y1 + corner_len), color_bgr, lw + 1, cv2.LINE_AA)
        # Superior Derecha
        cv2.line(canvas, (x2, y1), (x2 - corner_len, y1), color_bgr, lw + 1, cv2.LINE_AA)
        cv2.line(canvas, (x2, y1), (x2, y1 + corner_len), color_bgr, lw + 1, cv2.LINE_AA)
        # Inferior Izquierda
        cv2.line(canvas, (x1, y2), (x1 + corner_len, y2), color_bgr, lw + 1, cv2.LINE_AA)
        cv2.line(canvas, (x1, y2), (x1, y2 - corner_len), color_bgr, lw + 1, cv2.LINE_AA)
        # Inferior Derecha
        cv2.line(canvas, (x2, y2), (x2 - corner_len, y2), color_bgr, lw + 1, cv2.LINE_AA)
        cv2.line(canvas, (x2, y2), (x2, y2 - corner_len), color_bgr, lw + 1, cv2.LINE_AA)

    # Etiqueta superior informativa
    if reba_score is not None:
        label = f" {operator_id} | REBA: {reba_score} ({risk_level_str or ''}) "
    else:
        label = f" {operator_id} "

    (tw, th), tb = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.52, 1)
    tag_y1 = max(0, y1 - th - 10)
    tag_y2 = y1
    tag_x2 = min(w_img, x1 + tw + 8)

    # Fondo semitransparente para la tarjeta usando addWeighted
    alpha = cfg.visualization_rules.card_opacity
    overlay = canvas.copy()
    cv2.rectangle(overlay, (x1, tag_y1), (tag_x2, tag_y2), (20, 20, 25), -1)
    cv2.addWeighted(overlay, alpha, canvas, 1.0 - alpha, 0, canvas)
    cv2.rectangle(canvas, (x1, tag_y1), (tag_x2, tag_y2), color_bgr, 1)

    cv2.putText(
        canvas,
        label,
        (x1 + 4, tag_y2 - 5),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.52,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )


def draw_inter_operator_distance(
    canvas: np.ndarray,
    center_a: Tuple[float, float],
    center_b: Tuple[float, float],
    distance_cm: float,
    is_conforme: bool,
    config: Optional[VisionConfigSchema] = None,
) -> None:
    """Dibuja la línea de medición y etiqueta con opacidad de la Regla F2 (distancia >= 80 cm)."""
    cfg = config or DEFAULT_CONFIG
    color_verde = get_reba_color_bgr(1, cfg)
    color_rojo = get_reba_color_bgr(10, cfg)

    pt1 = (int(center_a[0]), int(center_a[1]))
    pt2 = (int(center_b[0]), int(center_b[1]))

    line_color = color_verde if is_conforme else color_rojo

    # Línea entre centroides
    cv2.line(canvas, pt1, pt2, line_color, 2, cv2.LINE_AA)
    cv2.circle(canvas, pt1, 5, line_color, -1, cv2.LINE_AA)
    cv2.circle(canvas, pt2, 5, line_color, -1, cv2.LINE_AA)

    # Punto medio para la etiqueta
    mid_x = (pt1[0] + pt2[0]) // 2
    mid_y = (pt1[1] + pt2[1]) // 2

    status_txt = "CONFORME" if is_conforme else "NO CONFORME (<80cm)"
    label = f" F2: {distance_cm:.1f} cm ({status_txt}) "
    (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)

    bg_x1 = max(5, mid_x - tw // 2 - 4)
    bg_y1 = max(5, mid_y - th - 8)
    bg_x2 = bg_x1 + tw + 8
    bg_y2 = bg_y1 + th + 12

    alpha = cfg.visualization_rules.f2_badge_opacity
    overlay = canvas.copy()
    cv2.rectangle(overlay, (bg_x1, bg_y1), (bg_x2, bg_y2), (15, 15, 20), -1)
    cv2.addWeighted(overlay, alpha, canvas, 1.0 - alpha, 0, canvas)
    cv2.rectangle(canvas, (bg_x1, bg_y1), (bg_x2, bg_y2), line_color, 1)

    cv2.putText(
        canvas,
        label,
        (bg_x1 + 4, bg_y2 - 6),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.52,
        line_color,
        2,
        cv2.LINE_AA,
    )


def draw_bad_posture_alerts(
    canvas: np.ndarray,
    pose: Pose2D,
    angles: BiomechanicalAngles,
    config: Optional[VisionConfigSchema] = None,
) -> None:
    """Dibuja indicadores discretos únicamente sobre las articulaciones del lado activo que exceden umbrales REBA."""
    cfg = config or DEFAULT_CONFIG
    color_rojo = get_reba_color_bgr(10, cfg)
    is_left = angles.active_side.value == "left"

    alert_joints: List[int] = []

    if angles.neck_angle > REBA_NECK_SCORE_1_MAX_DEG or angles.neck_needs_human_review:
        alert_joints.append(
            WholeBodyKeypointIndex.LEFT_EAR if is_left else WholeBodyKeypointIndex.RIGHT_EAR
        )

    if angles.trunk_angle > REBA_TRUNK_SCORE_2_MAX_DEG:
        alert_joints.append(
            WholeBodyKeypointIndex.LEFT_SHOULDER if is_left else WholeBodyKeypointIndex.RIGHT_SHOULDER
        )

    if angles.upper_arm_angle > REBA_ARM_SCORE_2_MAX_DEG or angles.upper_arm_abducted:
        alert_joints.append(
            WholeBodyKeypointIndex.LEFT_ELBOW if is_left else WholeBodyKeypointIndex.RIGHT_ELBOW
        )

    if angles.leg_knee_angle > REBA_KNEE_SCORE_ADJ_1_MIN_DEG:
        alert_joints.append(
            WholeBodyKeypointIndex.LEFT_KNEE if is_left else WholeBodyKeypointIndex.RIGHT_KNEE
        )

    min_conf = cfg.confidence_thresholds.min_keypoint_confidence
    for idx in alert_joints:
        kp = pose.get_keypoint(idx)
        if kp and kp.is_reliable(min_conf):
            px, py = int(kp.x), int(kp.y)
            cv2.circle(canvas, (px, py), 9, color_rojo, 2, cv2.LINE_AA)


def draw_reach_zones_aerial(
    canvas: np.ndarray,
    origin_px: Tuple[float, float],
    calibrator_factor_mm_per_px: float,
    hand_points_px: List[Tuple[float, float]],
    reach_zone_num: int,
    config: Optional[VisionConfigSchema] = None,
) -> None:
    """Dibuja las zonas de alcance concéntricas de Jabil (7.2.2.2) sobre la vista aérea usando OpenCV."""
    if calibrator_factor_mm_per_px <= 0:
        return

    cfg = config or DEFAULT_CONFIG
    color_verde = get_reba_color_bgr(1, cfg)
    color_amarillo = get_reba_color_bgr(3, cfg)
    color_naranja = get_reba_color_bgr(6, cfg)
    color_rojo = get_reba_color_bgr(10, cfg)

    ox, oy = int(origin_px[0]), int(origin_px[1])
    radii_dict = cfg.visualization_rules.reach_zone_radii_mm

    radii_mm = [
        (int(radii_dict.get("zona_1", 300.0)), "Zona 1 (Optima)", color_verde),
        (int(radii_dict.get("zona_2", 400.0)), "Zona 2 (Aceptable)", color_amarillo),
        (int(radii_dict.get("zona_3", 500.0)), "Zona 3 (Maxima)", color_naranja),
        (int(radii_dict.get("zona_4", 750.0)), "Zona 4/5 (Riesgo)", color_rojo),
    ]

    for r_mm, label, col in radii_mm:
        r_px = int(r_mm / calibrator_factor_mm_per_px)
        # Dibujar arco frontal (semicírculo hacia adelante de hombros) con cv2.ellipse
        cv2.ellipse(canvas, (ox, oy), (r_px, r_px), 0, 180, 360, col, 1, cv2.LINE_AA)
        cv2.putText(
            canvas,
            f"{r_mm}mm",
            (ox + r_px - 20, oy - 8),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            col,
            1,
            cv2.LINE_AA,
        )

    # Marcar posición de las manos
    for hx, hy in hand_points_px:
        ix, iy = int(hx), int(hy)
        cv2.circle(canvas, (ix, iy), 7, (255, 255, 0), -1, cv2.LINE_AA)
        cv2.circle(canvas, (ix, iy), 10, (0, 255, 255), 2, cv2.LINE_AA)
        cv2.line(canvas, (ox, oy), (ix, iy), (255, 255, 0), 1, cv2.LINE_AA)

    # Indicador de Zona Actual
    cv2.putText(
        canvas,
        f"Zona de Alcance Detectada: ZONA {reach_zone_num}",
        (15, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        color_verde if reach_zone_num <= 2 else color_rojo,
        2,
        cv2.LINE_AA,
    )
