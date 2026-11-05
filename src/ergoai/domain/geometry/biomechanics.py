"""Módulo geométrico biomecánico (G_1 a G_7) optimizado para RTMPose WholeBody_133 y ByteTrack."""

import math
from typing import Optional, List, Tuple
from ergoai.domain.models.keypoints import (
    WholeBodyKeypointIndex,
    Pose2D,
    CameraView,
    MultiViewPose,
    Keypoint,
)
from ergoai.domain.models.angles import BiomechanicalAngles, ActiveSide
from ergoai.domain.geometry.vectors import (
    Point2D,
    Vector2D,
    V_UP,
    V_DOWN,
    angle_between_vectors,
    vector_from_points,
    distance_2d,
)
from ergoai.domain.geometry.calibration import ScaleCalibrator
from ergoai.domain.constants import (
    REBA_ARM_ABDUCTION_THRESHOLD_DEG,
    REBA_WRIST_DEVIATION_ANGLE_TOLERANCE_DEG,
)


class BiomechanicalGeometryCalculator:
    """Calcula ángulos biomecánicos con precisión sub-articular aprovechando RTMPose WholeBody (133 puntos)."""

    @staticmethod
    def select_active_side(lateral_pose: Pose2D) -> ActiveSide:
        """G_1: Selección de hemisferio activo considerando cuerpo, extremidades y manos completas."""
        # Cadena izquierda completa (hombro, codo, muñeca, mano, cadera, rodilla, tobillo, pie)
        left_indices = [
            WholeBodyKeypointIndex.LEFT_SHOULDER,
            WholeBodyKeypointIndex.LEFT_ELBOW,
            WholeBodyKeypointIndex.LEFT_WRIST,
            WholeBodyKeypointIndex.LEFT_MIDDLE_MCP,
            WholeBodyKeypointIndex.LEFT_HIP,
            WholeBodyKeypointIndex.LEFT_KNEE,
            WholeBodyKeypointIndex.LEFT_ANKLE,
            WholeBodyKeypointIndex.LEFT_HEEL,
        ]
        # Cadena derecha completa
        right_indices = [
            WholeBodyKeypointIndex.RIGHT_SHOULDER,
            WholeBodyKeypointIndex.RIGHT_ELBOW,
            WholeBodyKeypointIndex.RIGHT_WRIST,
            WholeBodyKeypointIndex.RIGHT_MIDDLE_MCP,
            WholeBodyKeypointIndex.RIGHT_HIP,
            WholeBodyKeypointIndex.RIGHT_KNEE,
            WholeBodyKeypointIndex.RIGHT_ANKLE,
            WholeBodyKeypointIndex.RIGHT_HEEL,
        ]

        conf_left = lateral_pose.average_confidence(left_indices)
        conf_right = lateral_pose.average_confidence(right_indices)

        return ActiveSide.LEFT if conf_left > conf_right else ActiveSide.RIGHT

    @staticmethod
    def calculate_inter_operator_distance_cm(
        pose_a: Pose2D,
        pose_b: Pose2D,
        calibrator: ScaleCalibrator,
    ) -> float:
        """F2: Calcula la distancia en cm entre dos operadores (punto medio a punto medio)."""
        # Priorizar punto medio de cadera/hombros si existen, o centro del bounding box
        def get_person_center(pose: Pose2D) -> Point2D:
            sh_l = pose.get_keypoint(WholeBodyKeypointIndex.LEFT_SHOULDER)
            sh_r = pose.get_keypoint(WholeBodyKeypointIndex.RIGHT_SHOULDER)
            if sh_l and sh_r and sh_l.is_reliable(0.3) and sh_r.is_reliable(0.3):
                return ((sh_l.x + sh_r.x) / 2.0, (sh_l.y + sh_r.y) / 2.0)
            if pose.bbox:
                return pose.bbox.center
            # Fallback a cadera
            hip_l = pose.get_keypoint(WholeBodyKeypointIndex.LEFT_HIP)
            hip_r = pose.get_keypoint(WholeBodyKeypointIndex.RIGHT_HIP)
            if hip_l and hip_r:
                return ((hip_l.x + hip_r.x) / 2.0, (hip_l.y + hip_r.y) / 2.0)
            return (0.0, 0.0)

        center_a = get_person_center(pose_a)
        center_b = get_person_center(pose_b)
        dist_px = distance_2d(center_a, center_b)
        dist_mm = calibrator.px_to_mm(dist_px)
        return round(dist_mm / 10.0, 1)  # Retorna en centímetros

    @classmethod
    def calculate_angles(
        cls,
        lateral_pose: Pose2D,
        frontal_pose: Optional[Pose2D] = None,
        calibrator: Optional[ScaleCalibrator] = None,
        forced_side: Optional[ActiveSide] = None,
        confidence_threshold: float = 0.25,
    ) -> BiomechanicalAngles:
        """Calcula el conjunto completo de ángulos articulares con RTMPose WholeBody 133."""
        if forced_side is not None:
            side = forced_side
        else:
            # Evaluar el hemisferio con mayor compromiso postural (REBA: evaluar lado más exigido)
            sh_l = lateral_pose.get_keypoint(WholeBodyKeypointIndex.LEFT_SHOULDER)
            el_l = lateral_pose.get_keypoint(WholeBodyKeypointIndex.LEFT_ELBOW)
            sh_r = lateral_pose.get_keypoint(WholeBodyKeypointIndex.RIGHT_SHOULDER)
            el_r = lateral_pose.get_keypoint(WholeBodyKeypointIndex.RIGHT_ELBOW)

            arm_disp_l = 0.0
            if sh_l and el_l and sh_l.is_reliable(confidence_threshold) and el_l.is_reliable(confidence_threshold):
                arm_disp_l = angle_between_vectors(vector_from_points((sh_l.x, sh_l.y), (el_l.x, el_l.y)), V_DOWN)

            arm_disp_r = 0.0
            if sh_r and el_r and sh_r.is_reliable(confidence_threshold) and el_r.is_reliable(confidence_threshold):
                arm_disp_r = angle_between_vectors(vector_from_points((sh_r.x, sh_r.y), (el_r.x, el_r.y)), V_DOWN)

            if abs(arm_disp_l - arm_disp_r) > 10.0:
                side = ActiveSide.LEFT if arm_disp_l > arm_disp_r else ActiveSide.RIGHT
            else:
                side = cls.select_active_side(lateral_pose)

        # Mapeo de articulaciones WholeBody según hemisferio activo
        if side == ActiveSide.LEFT:
            idx_ear = WholeBodyKeypointIndex.LEFT_EAR
            idx_shoulder = WholeBodyKeypointIndex.LEFT_SHOULDER
            idx_elbow = WholeBodyKeypointIndex.LEFT_ELBOW
            idx_wrist = WholeBodyKeypointIndex.LEFT_WRIST
            idx_hand_middle = WholeBodyKeypointIndex.LEFT_MIDDLE_MCP
            idx_hand_index = WholeBodyKeypointIndex.LEFT_INDEX_MCP
            idx_hand_pinky = WholeBodyKeypointIndex.LEFT_PINKY_MCP
            idx_hip = WholeBodyKeypointIndex.LEFT_HIP
            idx_knee = WholeBodyKeypointIndex.LEFT_KNEE
            idx_ankle = WholeBodyKeypointIndex.LEFT_ANKLE
            idx_heel = WholeBodyKeypointIndex.LEFT_HEEL
            idx_toe = WholeBodyKeypointIndex.LEFT_BIG_TOE
        else:
            idx_ear = WholeBodyKeypointIndex.RIGHT_EAR
            idx_shoulder = WholeBodyKeypointIndex.RIGHT_SHOULDER
            idx_elbow = WholeBodyKeypointIndex.RIGHT_ELBOW
            idx_wrist = WholeBodyKeypointIndex.RIGHT_WRIST
            idx_hand_middle = WholeBodyKeypointIndex.RIGHT_MIDDLE_MCP
            idx_hand_index = WholeBodyKeypointIndex.RIGHT_INDEX_MCP
            idx_hand_pinky = WholeBodyKeypointIndex.RIGHT_PINKY_MCP
            idx_hip = WholeBodyKeypointIndex.RIGHT_HIP
            idx_knee = WholeBodyKeypointIndex.RIGHT_KNEE
            idx_ankle = WholeBodyKeypointIndex.RIGHT_ANKLE
            idx_heel = WholeBodyKeypointIndex.RIGHT_HEEL
            idx_toe = WholeBodyKeypointIndex.RIGHT_BIG_TOE

        p_shoulder = lateral_pose.get_keypoint(idx_shoulder)
        p_hip = lateral_pose.get_keypoint(idx_hip)
        p_elbow = lateral_pose.get_keypoint(idx_elbow)
        p_wrist = lateral_pose.get_keypoint(idx_wrist)
        p_hand_mid = lateral_pose.get_keypoint(idx_hand_middle)
        p_knee = lateral_pose.get_keypoint(idx_knee)
        p_ankle = lateral_pose.get_keypoint(idx_ankle)
        p_ear = lateral_pose.get_keypoint(idx_ear)

        # G_2: Ángulo de Tronco (Hombro - Cadera vs Plomada Vertical V_UP)
        if p_shoulder and p_hip and p_shoulder.is_reliable(confidence_threshold) and p_hip.is_reliable(confidence_threshold):
            v_trunk = vector_from_points((p_hip.x, p_hip.y), (p_shoulder.x, p_shoulder.y))
            theta_trunk = angle_between_vectors(v_trunk, V_UP)
            # Detección de extensión de tronco
            is_facing_right = (p_knee and p_knee.x > p_hip.x) or (p_wrist and p_wrist.x > p_hip.x)
            if is_facing_right:
                trunk_is_ext = p_shoulder.x < (p_hip.x - 5.0)
            else:
                trunk_is_ext = p_shoulder.x > (p_hip.x + 5.0)
        else:
            v_trunk = V_UP
            theta_trunk = 0.0
            trunk_is_ext = False

        # G_3: Ángulo de Cuello (WholeBody: soporte de landmarks faciales 23-90 + oreja)
        neck_review_needed = False
        chin = lateral_pose.get_keypoint(WholeBodyKeypointIndex.FACE_CHIN_BOTTOM)
        nose = lateral_pose.get_keypoint(WholeBodyKeypointIndex.NOSE)

        # Si tenemos puntos faciales o de oreja confiables:
        head_ref_point = None
        if p_ear and p_ear.is_reliable(confidence_threshold):
            head_ref_point = p_ear
        elif chin and chin.is_reliable(confidence_threshold):
            head_ref_point = chin
        elif nose and nose.is_reliable(confidence_threshold):
            head_ref_point = nose

        if head_ref_point and p_shoulder and p_shoulder.is_reliable(confidence_threshold):
            v_neck = vector_from_points((p_shoulder.x, p_shoulder.y), (head_ref_point.x, head_ref_point.y))
            theta_neck = angle_between_vectors(v_neck, v_trunk)
            neck_is_ext = False
        else:
            # Foto sin rostro detectable (anonimizada, difuminada o sin confianza)
            neck_review_needed = True
            theta_neck = 10.0
            neck_is_ext = False

        # G_4: Piernas / Rodilla y Apoyo Plantar (utilizando talones y dedos 17-22 de WholeBody)
        if p_hip and p_knee and p_ankle and p_knee.is_reliable(confidence_threshold):
            v_thigh = vector_from_points((p_knee.x, p_knee.y), (p_hip.x, p_hip.y))
            v_shin = vector_from_points((p_knee.x, p_knee.y), (p_ankle.x, p_ankle.y))
            theta_inner_knee = angle_between_vectors(v_thigh, v_shin)
            theta_knee = max(0.0, 180.0 - theta_inner_knee)
        else:
            theta_knee = 0.0

        # Soporte unilateral o base inestable con precisión podométrica de WholeBody
        leg_unilateral = False
        if frontal_pose is not None and calibrator is not None:
            # Medición en talones o tobillos
            l_heel = frontal_pose.get_keypoint(WholeBodyKeypointIndex.LEFT_HEEL)
            r_heel = frontal_pose.get_keypoint(WholeBodyKeypointIndex.RIGHT_HEEL)
            l_ankle = frontal_pose.get_keypoint(WholeBodyKeypointIndex.LEFT_ANKLE)
            r_ankle = frontal_pose.get_keypoint(WholeBodyKeypointIndex.RIGHT_ANKLE)

            y_left = l_heel.y if (l_heel and l_heel.is_reliable(confidence_threshold)) else (l_ankle.y if l_ankle else None)
            y_right = r_heel.y if (r_heel and r_heel.is_reliable(confidence_threshold)) else (r_ankle.y if r_ankle else None)

            if y_left is not None and y_right is not None:
                diff_mm = abs(y_left - y_right) * calibrator.factor_mm_per_px
                if diff_mm > 40.0:  # Desnivel plantar > 40 mm indica apoyo unilateral
                    leg_unilateral = True

        # G_5: Brazo / Hombro
        if p_shoulder and p_elbow and p_shoulder.is_reliable(confidence_threshold) and p_elbow.is_reliable(confidence_threshold):
            v_arm = vector_from_points((p_shoulder.x, p_shoulder.y), (p_elbow.x, p_elbow.y))
            if p_hip and p_hip.is_reliable(confidence_threshold):
                v_trunk_down = vector_from_points((p_shoulder.x, p_shoulder.y), (p_hip.x, p_hip.y))
            else:
                v_trunk_down = V_DOWN
            theta_arm = angle_between_vectors(v_arm, v_trunk_down)
        else:
            theta_arm = 15.0

        # Abducción coronal desde vista frontal
        arm_abducted = False
        if frontal_pose is not None:
            f_shoulder = frontal_pose.get_keypoint(idx_shoulder)
            f_elbow = frontal_pose.get_keypoint(idx_elbow)
            if f_shoulder and f_elbow and f_shoulder.is_reliable(confidence_threshold) and f_elbow.is_reliable(confidence_threshold):
                v_frontal_arm = vector_from_points((f_shoulder.x, f_shoulder.y), (f_elbow.x, f_elbow.y))
                coronal_angle = angle_between_vectors(v_frontal_arm, V_DOWN)
                if coronal_angle > REBA_ARM_ABDUCTION_THRESHOLD_DEG:
                    arm_abducted = True

        # G_6: Antebrazo / Codo
        if p_shoulder and p_elbow and p_wrist and p_elbow.is_reliable(confidence_threshold) and p_wrist.is_reliable(confidence_threshold):
            v_arm_inv = vector_from_points((p_elbow.x, p_elbow.y), (p_shoulder.x, p_shoulder.y))
            v_forearm = vector_from_points((p_elbow.x, p_elbow.y), (p_wrist.x, p_wrist.y))
            theta_inner_elbow = angle_between_vectors(v_arm_inv, v_forearm)
            theta_forearm = max(0.0, 180.0 - theta_inner_elbow)
        else:
            theta_forearm = 90.0

        # G_6-BIS: Muñeca y Mano con precisión de 21 keypoints de mano (WholeBody)
        wrist_twisted_or_deviated = False
        if p_wrist and p_hand_mid and p_elbow and p_wrist.is_reliable(confidence_threshold) and p_hand_mid.is_reliable(confidence_threshold):
            # Vector antebrazo (codo -> muñeca) y vector palma (muñeca -> nudillo medio)
            v_forearm_dir = vector_from_points((p_elbow.x, p_elbow.y), (p_wrist.x, p_wrist.y))
            v_hand_dir = vector_from_points((p_wrist.x, p_wrist.y), (p_hand_mid.x, p_hand_mid.y))
            # Ángulo entre la línea del antebrazo y la mano (0° = alineada colineal)
            theta_wrist = angle_between_vectors(v_forearm_dir, v_hand_dir)

            # Desviación lateral radial/cubital utilizando nudillos índice y meñique si están visibles
            p_index = lateral_pose.get_keypoint(idx_hand_index)
            p_pinky = lateral_pose.get_keypoint(idx_hand_pinky)
            if p_index and p_pinky and p_index.is_reliable(confidence_threshold) and p_pinky.is_reliable(confidence_threshold):
                # Vector transversal de nudillos
                v_knuckles = vector_from_points((p_pinky.x, p_pinky.y), (p_index.x, p_index.y))
                # La perpendicular esperada respecto a v_hand_dir
                angle_knuckle = angle_between_vectors(v_knuckles, v_hand_dir)
                # Si se desvía de los 90° perpendiculares, hay torsión o desviación
                if abs(angle_knuckle - 90.0) > REBA_WRIST_DEVIATION_ANGLE_TOLERANCE_DEG:
                    wrist_twisted_or_deviated = True
        else:
            theta_wrist = 10.0

        # G_7: Altura física de toma desde el piso (utilizando talones/dedos exactos de WholeBody)
        pickup_height_m: Optional[float] = None
        if calibrator is not None:
            # La mano activa: preferir el nudillo medio o la muñeca
            ref_hand = p_hand_mid if (p_hand_mid and p_hand_mid.is_reliable(confidence_threshold)) else p_wrist

            if ref_hand:
                floor_points_y = []
                # Puntos plantares: talones (19, 22), dedos (17, 18, 20, 21), tobillos (15, 16)
                plantar_indices = [
                    WholeBodyKeypointIndex.LEFT_HEEL,
                    WholeBodyKeypointIndex.RIGHT_HEEL,
                    WholeBodyKeypointIndex.LEFT_BIG_TOE,
                    WholeBodyKeypointIndex.RIGHT_BIG_TOE,
                    WholeBodyKeypointIndex.LEFT_ANKLE,
                    WholeBodyKeypointIndex.RIGHT_ANKLE,
                ]
                for p_idx in plantar_indices:
                    kp = lateral_pose.get_keypoint(p_idx)
                    if kp and kp.is_reliable(confidence_threshold):
                        floor_points_y.append(kp.y)

                if floor_points_y:
                    y_piso = max(floor_points_y)
                    dist_px = y_piso - ref_hand.y
                    pickup_height_m = max(0.0, calibrator.px_to_m(dist_px))

        return BiomechanicalAngles(
            active_side=side,
            trunk_angle=round(theta_trunk, 1),
            trunk_is_extension=trunk_is_ext,
            trunk_twisted=False,
            trunk_side_bending=False,
            neck_angle=round(theta_neck, 1),
            neck_is_extension=neck_is_ext,
            neck_twisted=False,
            neck_side_bending=False,
            neck_needs_human_review=neck_review_needed,
            leg_knee_angle=round(theta_knee, 1),
            leg_bilateral_support=not leg_unilateral,
            leg_unilateral_or_unstable=leg_unilateral,
            upper_arm_angle=round(theta_arm, 1),
            upper_arm_is_extension=False,
            upper_arm_abducted=arm_abducted,
            shoulder_elevated=False,
            arm_supported_or_gravity_assisted=False,
            lower_arm_angle=round(theta_forearm, 1),
            wrist_angle=round(theta_wrist, 1),
            wrist_twisted_or_deviated=wrist_twisted_or_deviated,
            pickup_height_m=round(pickup_height_m, 2) if pickup_height_m is not None else None,
        )
