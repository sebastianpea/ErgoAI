"""Pipeline integral de visión artificial multi-persona y evaluación ergonómica REBA.

Integra:
  - YOLOX: Detección robusta de personas (incluyendo sin rostro y oclusión parcial).
  - ByteTrack: Seguimiento y asignación de identificadores persistentes.
  - RTMPose WholeBody_133: Extracción de 133 keypoints (cuerpo, manos de 21 puntos, pies).
  - Biomecánica Vectorial: Ángulos G_1 a G_7 (sin hardcode).
  - Método REBA Oficial: Tablas A, B, C y clasificación de riesgo (1 a 15).
  - Zonas de Alcance Jabil (7.2.2.2): Zonas 1 a 5.
  - Reglas Multi-Persona: Distancia entre operarios (F2 >= 80 cm) y levantamiento en equipo (B2).
  - Trazabilidad Human-in-the-Loop y Simulación de Riesgo Residual (NOM-036).
"""

from __future__ import annotations

import base64
import ctypes
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

import cv2
import numpy as np
from pydantic import BaseModel, Field

from ergoai.config import SETTINGS
from ergoai.config.vision_schema import VisionConfigSchema
from ergoai.domain.constants import (
    JABIL_MAX_SINGLE_PERSON_LOAD_KG,
    JABIL_MIN_INTER_OPERATOR_DISTANCE_CM,
    JABIL_TEAM_LIFT_2P_GREEN_MAX_KG,
    JABIL_TEAM_LIFT_2P_ORANGE_MAX_KG,
    JABIL_TEAM_LIFT_3P_GREEN_MAX_KG,
    JABIL_TEAM_LIFT_3P_ORANGE_MAX_KG,
    DEFAULT_OPERATOR_HEIGHT_MM,
    DEFAULT_BIACROMIAL_SHOULDER_WIDTH_MM,
)

# Preload dinámico de bibliotecas CUDA si están disponibles en el entorno
for lib_dir in SETTINGS.discover_cuda_library_paths():
    if os.path.isdir(lib_dir):
        for f in os.listdir(lib_dir):
            if f.endswith(".so") or ".so." in f:
                try:
                    ctypes.CDLL(os.path.join(lib_dir, f), mode=ctypes.RTLD_GLOBAL)
                except Exception:
                    pass

try:
    from rtmlib import RTMPose, YOLOX, draw_skeleton
    HAS_RTMLIB = True
except ImportError:
    RTMPose, YOLOX, draw_skeleton = None, None, None
    HAS_RTMLIB = False

from ergoai.domain.models.keypoints import (
    WholeBodyKeypointIndex,
    Pose2D,
    Keypoint,
    BoundingBox,
    CameraView,
)
from ergoai.domain.models.angles import BiomechanicalAngles, ActiveSide
from ergoai.domain.geometry.biomechanics import BiomechanicalGeometryCalculator
from ergoai.domain.geometry.calibration import ScaleCalibrator
from ergoai.domain.geometry.reach_zones import ReachZoneClassifier
from ergoai.domain.reba.evaluator import REBAEvaluator
from ergoai.domain.models.reba import REBAAssessment, REBARiskLevel
from ergoai.domain.models.simulation import EngineeringControlID
from ergoai.services.annotator import (
    draw_operator_card,
    draw_inter_operator_distance,
    draw_bad_posture_alerts,
    draw_reach_zones_aerial,
    get_reba_color_bgr,
)


class EvaluatedPersonDTO(BaseModel):
    """Resultados biomecánicos y ergonómicos de una persona detectada."""
    person_index: int
    track_id: int
    operator_label: str
    bbox_xyxy: List[float]
    active_side: str
    angles: Dict[str, Any]
    reba: Dict[str, Any]
    reach_zone: Optional[Dict[str, Any]] = None
    face_detected: bool
    neck_needs_review: bool


class MultiPersonSceneEvaluationDTO(BaseModel):
    """Reporte completo de la evaluación de la escena multi-persona."""
    timestamp: float
    total_persons_detected: int
    persons: List[EvaluatedPersonDTO]
    multi_person_metrics: Dict[str, Any]
    annotated_images_b64: Dict[str, str]
    execution_time_ms: float


class ErgoAIVisionPipeline:
    """Motor central de inferencia RTMPose WholeBody-133 y evaluación ergonómica."""

    def __init__(
        self,
        yolox_model_path: Optional[str] = None,
        rtmpose_model_path: Optional[str] = None,
        device: Optional[str] = None,
        config: Optional[VisionConfigSchema] = None,
    ) -> None:
        if not HAS_RTMLIB:
            raise RuntimeError(
                "Dependencia central de visión 'rtmlib' no encontrada en este intérprete Python.\n"
                "Ejecute con: python start_web.py (detectará automáticamente el venv compatible) o use .venv/bin/python"
            )

        self.device = device or SETTINGS.hardware.device
        self.backend = SETTINGS.hardware.backend
        # Inyección de configuración y reglas de visualización mediante Pydantic (elimina hardcode)
        self.config = config or VisionConfigSchema.load_from_json()

        yolox_path = yolox_model_path or SETTINGS.get_yolox_checkpoint_path()
        rtmpose_path = rtmpose_model_path or SETTINGS.get_rtmpose_checkpoint_path()

        # Inicialización del detector YOLOX (Top-Down) con ONNX Runtime
        self.detector = YOLOX(
            onnx_model=yolox_path,
            model_input_size=SETTINGS.vision.yolox_input_size,
            nms_thr=self.config.confidence_thresholds.yolox_nms_thr,
            score_thr=self.config.confidence_thresholds.yolox_score_thr,
            backend=self.backend,
            device=self.device,
        )

        # Inicialización de RTMPose WholeBody 133 con ONNX Runtime
        self.pose_estimator = RTMPose(
            onnx_model=rtmpose_path,
            model_input_size=SETTINGS.vision.rtmpose_input_size,
            to_openpose=False,
            backend=self.backend,
            device=self.device,
        )

    @staticmethod
    def compute_dynamic_scale_factor(
        poses: List[Pose2D],
        fallback_scale: Optional[float] = None,
        min_confidence: float = 0.30,
    ) -> float:
        """
        Calcula dinámicamente el factor de escala métrico (mm/px) basado en proporciones
        antropométricas (anchura biacromial de hombros o estatura del operador), eliminando
        factores fijos hardcodeados conforme a ARCHITECTURE.md 4.1 y 4.3.
        """
        default_scale = (
            fallback_scale
            if fallback_scale is not None and fallback_scale > 0
            else SETTINGS.calibration.fallback_scale_mm_per_px
        )
        if not poses:
            return default_scale

        for pose in poses:
            # 1. Distancia biacromial de hombros (400 mm estándar industrial)
            sh_l = pose.get_keypoint(WholeBodyKeypointIndex.LEFT_SHOULDER)
            sh_r = pose.get_keypoint(WholeBodyKeypointIndex.RIGHT_SHOULDER)
            if sh_l and sh_r and sh_l.is_reliable(min_confidence) and sh_r.is_reliable(min_confidence):
                dx = sh_l.x - sh_r.x
                dy = sh_l.y - sh_r.y
                dist_px = float(np.hypot(dx, dy))
                if dist_px > 25.0:
                    scale = DEFAULT_BIACROMIAL_SHOULDER_WIDTH_MM / dist_px
                    if 0.5 <= scale <= 10.0:
                        return float(round(scale, 3))

            # 2. Altura de bounding box si los tobillos están presentes
            if pose.bbox and pose.bbox.height > 150.0:
                ankle_l = pose.get_keypoint(WholeBodyKeypointIndex.LEFT_ANKLE)
                ankle_r = pose.get_keypoint(WholeBodyKeypointIndex.RIGHT_ANKLE)
                has_ankles = (ankle_l and ankle_l.is_reliable(min_confidence)) or (ankle_r and ankle_r.is_reliable(min_confidence))
                if has_ankles:
                    scale = DEFAULT_OPERATOR_HEIGHT_MM / pose.bbox.height
                    if 0.5 <= scale <= 10.0:
                        return float(round(scale, 3))

        return default_scale

    def _detect_operators(
        self,
        frame_bgr: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Ejecuta YOLOX para detectar la silueta de los operadores y ordena espacialmente de izq a der."""
        boxes = self.detector(frame_bgr)
        if boxes is None or len(boxes) == 0:
            # Fallback para tomas con oclusión severa (ej. carro o mesa que tapa miembros inferiores)
            h, w = frame_bgr.shape[:2]
            return (
                np.array([[0.0, 0.0, float(w), float(h)]], dtype=np.float32),
                np.array([0.50], dtype=np.float32),
                np.array([1], dtype=int),
            )

        boxes = np.atleast_2d(boxes).astype(np.float32)
        if boxes.shape[1] >= 5:
            scores = boxes[:, 4]
            boxes = boxes[:, :4]
        else:
            scores = np.ones(len(boxes), dtype=np.float32)

        # Ordenar operadores de izquierda a derecha (coordenada x1) para ID determinista
        order = np.argsort(boxes[:, 0])
        boxes = boxes[order]
        scores = scores[order]
        ids = np.arange(1, len(boxes) + 1, dtype=int)
        return boxes, scores, ids

    def _process_view(
        self,
        img_bgr: Optional[np.ndarray],
        view: CameraView,
    ) -> Tuple[Optional[np.ndarray], List[Pose2D]]:
        """Detecta operarios, estima 133 keypoints WholeBody y dibuja el esqueleto para una vista dada."""
        if img_bgr is None:
            return None, []

        canvas = img_bgr.copy()
        poses: List[Pose2D] = []
        boxes, scores, ids = self._detect_operators(img_bgr)
        if len(boxes) == 0:
            return canvas, poses

        kpts, scs = self.pose_estimator(img_bgr, bboxes=boxes)
        canvas = draw_skeleton(
            canvas,
            kpts,
            scs,
            kpt_thr=self.config.visualization_rules.skeleton_kpt_thr,
            radius=self.config.visualization_rules.skeleton_radius,
            line_width=self.config.visualization_rules.skeleton_line_width,
        )
        total_kp = SETTINGS.vision.total_keypoints
        for i in range(len(boxes)):
            kp_dict = {
                k: Keypoint(
                    x=float(kpts[i, k, 0]),
                    y=float(kpts[i, k, 1]),
                    confidence=float(np.clip(scs[i, k], 0.0, 1.0)),
                )
                for k in range(total_kp)
            }
            poses.append(
                Pose2D(
                    view=view,
                    track_id=int(ids[i]),
                    bbox=BoundingBox(
                        x1=float(boxes[i, 0]),
                        y1=float(boxes[i, 1]),
                        x2=float(boxes[i, 2]),
                        y2=float(boxes[i, 3]),
                        score=float(scores[i]),
                    ),
                    keypoints=kp_dict,
                )
            )
        return canvas, poses

    def evaluate_multi_person_scene(
        self,
        lateral_img_bgr: Optional[np.ndarray],
        frontal_img_bgr: Optional[np.ndarray] = None,
        aerea_img_bgr: Optional[np.ndarray] = None,
        load_kg: float = 0.0,
        coupling_score: int = 0,
        is_static: bool = False,
        is_repetitive: bool = False,
        is_shock_load: bool = False,
        reach_frequency_per_piece: float = 1.0,
        scale_mm_per_px: Optional[float] = None,
    ) -> MultiPersonSceneEvaluationDTO:
        """
        Ejecuta el pipeline completo sobre las 3 fotografías estáticas analizando a TODAS las personas presentes.
        """
        t0 = time.perf_counter()
        min_conf = self.config.confidence_thresholds.min_keypoint_confidence

        canvas_lateral, poses_lateral = self._process_view(lateral_img_bgr, CameraView.LATERAL)
        canvas_frontal, poses_frontal = self._process_view(frontal_img_bgr, CameraView.FRONTAL)
        canvas_aerea, poses_aerea = self._process_view(aerea_img_bgr, CameraView.AEREA)

        # Poses primarias para evaluar ergonomía (usar lateral si está disponible, sino frontal, sino aérea)
        primary_poses = poses_lateral if len(poses_lateral) > 0 else (poses_frontal if len(poses_frontal) > 0 else poses_aerea)
        target_canvas = canvas_lateral if len(poses_lateral) > 0 else (canvas_frontal if len(poses_frontal) > 0 else canvas_aerea)

        # Resolución dinámica del factor de escala mm/px eliminando magic number hardcodeado
        actual_scale = (
            scale_mm_per_px
            if scale_mm_per_px is not None and scale_mm_per_px > 0
            else self.compute_dynamic_scale_factor(primary_poses, min_confidence=min_conf)
        )
        calibrator = ScaleCalibrator(factor_mm_per_px=actual_scale)

        evaluated_persons: List[EvaluatedPersonDTO] = []

        for p_idx, pose in enumerate(primary_poses):
            # Posible pose frontal complementaria (por orden de índice)
            f_pose = poses_frontal[p_idx] if p_idx < len(poses_frontal) else None

            # Extracción de ángulos biomecánicos G_1 a G_7 (usando umbral calibrado desde schema)
            angles = BiomechanicalGeometryCalculator.calculate_angles(
                lateral_pose=pose,
                frontal_pose=f_pose,
                calibrator=calibrator,
                confidence_threshold=min_conf,
            )

            # Evaluación REBA (R1 a R4)
            reba_res = REBAEvaluator.evaluate(
                angles=angles,
                load_kg=load_kg,
                is_shock_load=is_shock_load,
                coupling_score=coupling_score,
                is_static=is_static,
                is_repetitive=is_repetitive,
            )

            # Zonas de Alcance si hay vista aérea
            reach_dto = None
            if len(poses_aerea) > p_idx:
                a_pose = poses_aerea[p_idx]
                mid_origin = a_pose.bbox.center if a_pose.bbox else (0.0, 0.0)
                sh_l = a_pose.get_keypoint(WholeBodyKeypointIndex.LEFT_SHOULDER)
                sh_r = a_pose.get_keypoint(WholeBodyKeypointIndex.RIGHT_SHOULDER)
                if sh_l and sh_r and sh_l.is_reliable(min_conf) and sh_r.is_reliable(min_conf):
                    mid_origin = ((sh_l.x + sh_r.x) / 2.0, (sh_l.y + sh_r.y) / 2.0)

                w_l = a_pose.get_keypoint(WholeBodyKeypointIndex.LEFT_WRIST)
                w_r = a_pose.get_keypoint(WholeBodyKeypointIndex.RIGHT_WRIST)
                active_wrist = w_r if (w_r and w_r.is_reliable(min_conf)) else w_l

                if active_wrist:
                    r_result = ReachZoneClassifier.evaluate_point(
                        point_name="muñeca_operador",
                        point_px=(active_wrist.x, active_wrist.y),
                        origin_px=mid_origin,
                        calibrator=calibrator,
                        frequency_per_piece=reach_frequency_per_piece,
                    )
                    zone_int = int(r_result.zone.value)
                    reach_dto = {
                        "zone_number": zone_int,
                        "radius_mm": round(r_result.r_mm, 1),
                        "angle_degrees": round(r_result.alpha_deg, 1),
                        "lateral_dx_mm": round(r_result.dx_mm, 1),
                        "frontal_dy_mm": round(r_result.dy_mm, 1),
                        "is_compliant": r_result.is_compliant,
                        "action_required": r_result.action_required,
                    }
                    if canvas_aerea is not None:
                        hpts = []
                        if w_l and w_l.is_reliable(min_conf):
                            hpts.append((w_l.x, w_l.y))
                        if w_r and w_r.is_reliable(min_conf):
                            hpts.append((w_r.x, w_r.y))
                        draw_reach_zones_aerial(
                            canvas_aerea,
                            origin_px=mid_origin,
                            calibrator_factor_mm_per_px=actual_scale,
                            hand_points_px=hpts,
                            reach_zone_num=zone_int,
                            config=self.config,
                        )

            # Anotaciones visuales sobre el operador
            if target_canvas is not None and pose.bbox:
                color_bgr = get_reba_color_bgr(reba_res.final_score, config=self.config)
                draw_operator_card(
                    target_canvas,
                    bbox=(pose.bbox.x1, pose.bbox.y1, pose.bbox.x2, pose.bbox.y2),
                    operator_id=f"Operador #{p_idx+1}",
                    reba_score=reba_res.final_score,
                    risk_level_str=reba_res.risk_level.name,
                    color_bgr=color_bgr,
                    config=self.config,
                )
                draw_bad_posture_alerts(target_canvas, pose, angles, config=self.config)

            # Detección de rostro
            face_kps = [
                pose.get_keypoint(WholeBodyKeypointIndex.NOSE),
                pose.get_keypoint(WholeBodyKeypointIndex.LEFT_EYE),
                pose.get_keypoint(WholeBodyKeypointIndex.RIGHT_EYE),
                pose.get_keypoint(WholeBodyKeypointIndex.LEFT_EAR),
                pose.get_keypoint(WholeBodyKeypointIndex.RIGHT_EAR),
            ]
            face_detected = (
                sum(1 for kp in face_kps if kp and kp.is_reliable(self.config.confidence_thresholds.min_face_keypoint_confidence))
                >= self.config.confidence_thresholds.min_face_points_present
            )

            person_dto = EvaluatedPersonDTO(
                person_index=p_idx + 1,
                track_id=pose.track_id or (p_idx + 1),
                operator_label=f"Operador #{p_idx+1}",
                bbox_xyxy=[
                    pose.bbox.x1 if pose.bbox else 0.0,
                    pose.bbox.y1 if pose.bbox else 0.0,
                    pose.bbox.x2 if pose.bbox else 0.0,
                    pose.bbox.y2 if pose.bbox else 0.0,
                ],
                active_side=angles.active_side.value,
                angles=angles.model_dump(),
                reba={
                    "final_score": reba_res.final_score,
                    "risk_level": reba_res.risk_level.name,
                    "color_code": reba_res.color_code,
                    "action_urgency": reba_res.action_urgency,
                    "score_a": reba_res.group_a.score_a,
                    "table_a_score": reba_res.group_a.table_a_score,
                    "load_score": reba_res.group_a.load_score,
                    "score_b": reba_res.group_b.score_b,
                    "table_b_score": reba_res.group_b.table_b_score,
                    "coupling_score": reba_res.group_b.coupling_score,
                    "table_c_score": reba_res.table_c_score,
                    "activity_score": reba_res.activity.activity_score,
                    "group_a": reba_res.group_a.model_dump(),
                    "group_b": reba_res.group_b.model_dump(),
                    "activity": reba_res.activity.model_dump(),
                },
                reach_zone=reach_dto,
                face_detected=face_detected,
                neck_needs_review=angles.neck_needs_human_review,
            )
            evaluated_persons.append(person_dto)

        # 4. Métricas Multi-Persona (Regla F2: Distancia Inter-Operador >= 80 cm y Regla B2)
        multi_person_metrics: Dict[str, Any] = {
            "num_operators": len(primary_poses),
            "inter_operator_distance_f2": None,
            "f2_status": "NO APLICA (1 OPERARIO)",
            "team_lifting_b2": None,
        }

        # Calcular F2 si hay 2 o más operadores en frontal o lateral
        ref_multi_poses = poses_frontal if len(poses_frontal) >= 2 else primary_poses
        if len(ref_multi_poses) >= 2:
            p_a, p_b = ref_multi_poses[0], ref_multi_poses[1]
            dist_cm = BiomechanicalGeometryCalculator.calculate_inter_operator_distance_cm(
                p_a, p_b, calibrator
            )
            is_f2_ok = dist_cm >= JABIL_MIN_INTER_OPERATOR_DISTANCE_CM
            multi_person_metrics["inter_operator_distance_f2"] = {
                "distance_cm": dist_cm,
                "threshold_cm": JABIL_MIN_INTER_OPERATOR_DISTANCE_CM,
                "is_compliant": is_f2_ok,
                "status": "CONFORME" if is_f2_ok else f"NO CONFORME (< {JABIL_MIN_INTER_OPERATOR_DISTANCE_CM:.0f} cm)",
                "action": (
                    "Distancia segura entre puestos adyacentes"
                    if is_f2_ok
                    else f"Separar puestos de trabajo a >= {JABIL_MIN_INTER_OPERATOR_DISTANCE_CM:.0f} cm o instalar mamparas divisorias"
                ),
            }
            multi_person_metrics["f2_status"] = "CONFORME" if is_f2_ok else "NO CONFORME"

            # Dibujar la línea de medición F2 en canvas frontal (o primario)
            f2_canvas = canvas_frontal if canvas_frontal is not None else target_canvas
            if f2_canvas is not None and p_a.bbox and p_b.bbox:
                draw_inter_operator_distance(
                    f2_canvas,
                    center_a=p_a.bbox.center,
                    center_b=p_b.bbox.center,
                    distance_cm=dist_cm,
                    is_conforme=is_f2_ok,
                    config=self.config,
                )

        # Evaluar B2 si carga > JABIL_MAX_SINGLE_PERSON_LOAD_KG y hay múltiples personas
        if load_kg > JABIL_MAX_SINGLE_PERSON_LOAD_KG:
            n_pers = len(primary_poses)
            if n_pers >= 2:
                # Criterios Jabil B2: 2 pers < 19 kg Verde, 19-28 kg Naranja; 3 pers < 23 kg Verde, 23-42 kg Naranja
                if n_pers == 2:
                    if load_kg < JABIL_TEAM_LIFT_2P_GREEN_MAX_KG:
                        b2_cat = f"CONFORME (Contención Verde: < {JABIL_TEAM_LIFT_2P_GREEN_MAX_KG:.0f} kg)"
                    elif load_kg < JABIL_TEAM_LIFT_2P_ORANGE_MAX_KG:
                        b2_cat = f"ADVERTENCIA (Contención Naranja: {JABIL_TEAM_LIFT_2P_GREEN_MAX_KG:.0f}-{JABIL_TEAM_LIFT_2P_ORANGE_MAX_KG:.0f} kg, requiere visto bueno médico y MOC)"
                    else:
                        b2_cat = f"CRÍTICO (Excede {JABIL_TEAM_LIFT_2P_ORANGE_MAX_KG:.0f} kg para 2 personas, requiere lifter obligatorio)"
                else:
                    if load_kg < JABIL_TEAM_LIFT_3P_GREEN_MAX_KG:
                        b2_cat = f"CONFORME (Contención Verde: < {JABIL_TEAM_LIFT_3P_GREEN_MAX_KG:.0f} kg)"
                    elif load_kg < JABIL_TEAM_LIFT_3P_ORANGE_MAX_KG:
                        b2_cat = f"ADVERTENCIA (Contención Naranja: {JABIL_TEAM_LIFT_3P_GREEN_MAX_KG:.0f}-{JABIL_TEAM_LIFT_3P_ORANGE_MAX_KG:.0f} kg, requiere visto bueno médico)"
                    else:
                        b2_cat = "CRÍTICO (Excede límite seguro de contención)"
                multi_person_metrics["team_lifting_b2"] = {
                    "load_kg": load_kg,
                    "num_people": n_pers,
                    "status": b2_cat,
                }

        # 5. Codificar imágenes resultantes a Base64
        def _to_b64(bgr_img: Optional[np.ndarray]) -> str:
            if bgr_img is None or bgr_img.size == 0:
                return ""
            ok, buf = cv2.imencode(".jpg", bgr_img, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
            if not ok:
                return ""
            return base64.b64encode(buf.tobytes()).decode("utf-8")

        annotated_b64 = {
            "lateral": _to_b64(canvas_lateral),
            "frontal": _to_b64(canvas_frontal),
            "aerea": _to_b64(canvas_aerea),
        }

        total_ms = (time.perf_counter() - t0) * 1000.0

        return MultiPersonSceneEvaluationDTO(
            timestamp=time.time(),
            total_persons_detected=len(evaluated_persons),
            persons=evaluated_persons,
            multi_person_metrics=multi_person_metrics,
            annotated_images_b64=annotated_b64,
            execution_time_ms=round(total_ms, 2),
        )

    def simulate_residual_risk(
        self,
        original_angles: Dict[str, Any],
        original_load_kg: float,
        selected_controls: List[str],
        user_adjusted_angles: Optional[Dict[str, float]] = None,
        is_static: bool = False,
        is_repetitive: bool = False,
    ) -> Dict[str, Any]:
        """
        Simulador de Riesgo Residual (4.J / NOM-036-1):
        Aplica los modificadores de ingeniería aprobados y recalcula el puntaje REBA resultante.
        """
        # Clonar ángulos
        angles_dict = original_angles.copy()
        if user_adjusted_angles:
            angles_dict.update(user_adjusted_angles)

        sim_load_kg = original_load_kg
        sim_is_static = is_static
        sim_is_repetitive = is_repetitive

        # 1. B1_LIFTER: Asistencia mecánica / lifter
        if EngineeringControlID.B1_LIFTER in selected_controls or "B1_LIFTER" in selected_controls:
            sim_load_kg = 0.0
            angles_dict["trunk_angle"] = min(angles_dict.get("trunk_angle", 20.0), 15.0)

        # 2. B4_LOWER_PICKUP: Reducir altura de toma en rack/carro
        if EngineeringControlID.B4_LOWER_PICKUP in selected_controls or "B4_LOWER_PICKUP" in selected_controls:
            angles_dict["upper_arm_angle"] = min(angles_dict.get("upper_arm_angle", 45.0), 40.0)
            angles_dict["shoulder_elevated"] = False

        # 3. E1_RELOCATE_ZONE: Mover piezas a Zona 1/2 (<= 400 mm)
        if EngineeringControlID.E1_RELOCATE_ZONE in selected_controls or "E1_RELOCATE_ZONE" in selected_controls:
            angles_dict["upper_arm_angle"] = min(angles_dict.get("upper_arm_angle", 40.0), 20.0)
            angles_dict["trunk_angle"] = min(angles_dict.get("trunk_angle", 20.0), 10.0)
            angles_dict["upper_arm_abducted"] = False
            angles_dict["trunk_twisted"] = False

        # 4. F1_HEIGHT_ADJUST: Ajuste de mesa a 95-125 cm
        if EngineeringControlID.F1_HEIGHT_ADJUST in selected_controls or "F1_HEIGHT_ADJUST" in selected_controls:
            angles_dict["neck_angle"] = min(angles_dict.get("neck_angle", 25.0), 15.0)
            angles_dict["lower_arm_angle"] = 85.0  # Rango óptimo 60-100
            angles_dict["trunk_angle"] = min(angles_dict.get("trunk_angle", 20.0), 10.0)

        # 5. TOOL_CHANGE_ERGONOMIC: Cambio de herramienta a empuñadura ergonómica / balanceador
        if EngineeringControlID.TOOL_CHANGE_ERGONOMIC in selected_controls or "TOOL_CHANGE_ERGONOMIC" in selected_controls:
            angles_dict["wrist_angle"] = min(angles_dict.get("wrist_angle", 20.0), 10.0)
            angles_dict["wrist_twisted_or_deviated"] = False
            angles_dict["lower_arm_angle"] = 85.0

        # 6. SIT_STAND_ALTERNATION: Estación sit-stand regulable y tapete antifatiga
        if EngineeringControlID.SIT_STAND_ALTERNATION in selected_controls or "SIT_STAND_ALTERNATION" in selected_controls:
            angles_dict["leg_knee_angle"] = 0.0
            angles_dict["leg_bilateral_support"] = True
            angles_dict["leg_unilateral_or_unstable"] = False
            sim_is_static = False

        # 7. C1_D3_ESD_CHAIR: Silla ergonómica ESD y pausas activas
        if EngineeringControlID.C1_D3_ESD_CHAIR in selected_controls or "C1_D3_ESD_CHAIR" in selected_controls:
            angles_dict["leg_knee_angle"] = 0.0
            angles_dict["leg_bilateral_support"] = True
            angles_dict["leg_unilateral_or_unstable"] = False
            sim_is_static = False

        # Construir objeto BiomechanicalAngles simulado
        sim_angles = BiomechanicalAngles(
            active_side=ActiveSide(angles_dict.get("active_side", "right")),
            trunk_angle=float(angles_dict.get("trunk_angle", 0.0)),
            trunk_is_extension=bool(angles_dict.get("trunk_is_extension", False)),
            trunk_twisted=bool(angles_dict.get("trunk_twisted", False)),
            trunk_side_bending=bool(angles_dict.get("trunk_side_bending", False)),
            neck_angle=float(angles_dict.get("neck_angle", 0.0)),
            neck_is_extension=bool(angles_dict.get("neck_is_extension", False)),
            neck_twisted=bool(angles_dict.get("neck_twisted", False)),
            neck_side_bending=bool(angles_dict.get("neck_side_bending", False)),
            neck_needs_human_review=False,
            leg_knee_angle=float(angles_dict.get("leg_knee_angle", 0.0)),
            leg_bilateral_support=bool(angles_dict.get("leg_bilateral_support", True)),
            leg_unilateral_or_unstable=bool(angles_dict.get("leg_unilateral_or_unstable", False)),
            upper_arm_angle=float(angles_dict.get("upper_arm_angle", 0.0)),
            upper_arm_is_extension=bool(angles_dict.get("upper_arm_is_extension", False)),
            upper_arm_abducted=bool(angles_dict.get("upper_arm_abducted", False)),
            shoulder_elevated=bool(angles_dict.get("shoulder_elevated", False)),
            arm_supported_or_gravity_assisted=bool(angles_dict.get("arm_supported_or_gravity_assisted", False)),
            lower_arm_angle=float(angles_dict.get("lower_arm_angle", 90.0)),
            wrist_angle=float(angles_dict.get("wrist_angle", 0.0)),
            wrist_twisted_or_deviated=bool(angles_dict.get("wrist_twisted_or_deviated", False)),
            pickup_height_m=angles_dict.get("pickup_height_m"),
        )

        # REBA Residual
        res_assessment = REBAEvaluator.evaluate(
            angles=sim_angles,
            load_kg=sim_load_kg,
            is_static=sim_is_static,
            is_repetitive=sim_is_repetitive,
        )

        return {
            "residual_reba_score": res_assessment.final_score,
            "residual_risk_level": res_assessment.risk_level.name,
            "residual_color_code": res_assessment.color_code,
            "residual_urgency": res_assessment.action_urgency,
            "is_goal_met": res_assessment.final_score <= 3,
            "simulated_angles": sim_angles.model_dump(),
            "applied_controls": selected_controls,
            "score_a": res_assessment.group_a.score_a,
            "score_b": res_assessment.group_b.score_b,
            "table_c_score": res_assessment.table_c_score,
        }
