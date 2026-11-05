"""Tests unitarios para la capa geométrica, calibración y biomecánica con RTMPose WholeBody_133 y ByteTrack."""

import pytest
import math
from ergoai.domain.geometry.vectors import (
    dot_product,
    vector_norm,
    distance_2d,
    angle_between_vectors,
    V_UP,
    V_DOWN,
)
from ergoai.domain.geometry.calibration import ScaleCalibrator
from ergoai.domain.geometry.biomechanics import BiomechanicalGeometryCalculator
from ergoai.domain.models.keypoints import (
    Keypoint,
    BoundingBox,
    Pose2D,
    CameraView,
    WholeBodyKeypointIndex,
)
from ergoai.domain.models.angles import ActiveSide


def test_vector_operations():
    u = (3.0, 4.0)
    assert vector_norm(u) == pytest.approx(5.0)
    assert dot_product((1.0, 0.0), (0.0, 1.0)) == pytest.approx(0.0)
    assert dot_product((2.0, 3.0), (4.0, 5.0)) == pytest.approx(23.0)
    assert distance_2d((0.0, 0.0), (3.0, 4.0)) == pytest.approx(5.0)


def test_angle_between_vectors():
    assert angle_between_vectors((1.0, 0.0), (0.0, 1.0)) == pytest.approx(90.0)
    assert angle_between_vectors((0.0, -1.0), (0.0, -2.0)) == pytest.approx(0.0)
    assert angle_between_vectors((0.0, -1.0), (0.0, 1.0)) == pytest.approx(180.0)
    assert angle_between_vectors((0.0, 0.0), (1.0, 1.0)) == 0.0


def test_scale_calibrator():
    p1 = (100.0, 100.0)
    p2 = (100.0, 300.0)
    calibrator = ScaleCalibrator.from_reference(p1, p2, reference_real_mm=1000.0)
    assert calibrator.factor_mm_per_px == pytest.approx(5.0)
    assert calibrator.px_to_mm(50.0) == pytest.approx(250.0)
    assert calibrator.px_to_m(200.0) == pytest.approx(1.0)
    assert calibrator.mm_to_px(250.0) == pytest.approx(50.0)


def test_bytetrack_tracked_pose():
    # Verificación de tracking por ByteTrack
    bbox = BoundingBox(x1=50, y1=80, x2=250, y2=580, score=0.96)
    assert bbox.width == 200.0
    assert bbox.height == 500.0
    assert bbox.center == (150.0, 330.0)

    pose = Pose2D(
        view=CameraView.LATERAL,
        track_id=42,  # ID persistente asignado por ByteTrack
        bbox=bbox,
        keypoints={
            WholeBodyKeypointIndex.RIGHT_SHOULDER: Keypoint(x=150, y=100, confidence=0.9),
        }
    )
    assert pose.track_id == 42
    assert pose.bbox.score == 0.96


def test_inter_operator_distance_calculation():
    # Dos operarios en la misma escena frontal con 100 píxeles de separación
    # Factor de escala: 10 mm por píxel -> 1000 mm = 100 cm
    calibrator = ScaleCalibrator(factor_mm_per_px=10.0)
    pose1 = Pose2D(
        view=CameraView.FRONTAL,
        track_id=1,
        bbox=BoundingBox(x1=50, y1=100, x2=150, y2=500), # centro x=100, y=300
    )
    pose2 = Pose2D(
        view=CameraView.FRONTAL,
        track_id=2,
        bbox=BoundingBox(x1=150, y1=100, x2=250, y2=500), # centro x=200, y=300
    )
    dist_cm = BiomechanicalGeometryCalculator.calculate_inter_operator_distance_cm(pose1, pose2, calibrator)
    assert dist_cm == pytest.approx(100.0, abs=1.0)


def test_active_side_selection_wholebody():
    pose = Pose2D(
        view=CameraView.LATERAL,
        keypoints={
            WholeBodyKeypointIndex.LEFT_SHOULDER: Keypoint(x=100, y=100, confidence=0.2),
            WholeBodyKeypointIndex.LEFT_ELBOW: Keypoint(x=110, y=150, confidence=0.2),
            WholeBodyKeypointIndex.LEFT_WRIST: Keypoint(x=120, y=200, confidence=0.2),
            WholeBodyKeypointIndex.RIGHT_SHOULDER: Keypoint(x=105, y=100, confidence=0.9),
            WholeBodyKeypointIndex.RIGHT_ELBOW: Keypoint(x=115, y=150, confidence=0.95),
            WholeBodyKeypointIndex.RIGHT_WRIST: Keypoint(x=125, y=200, confidence=0.92),
            WholeBodyKeypointIndex.RIGHT_MIDDLE_MCP: Keypoint(x=130, y=220, confidence=0.91),
        }
    )
    side = BiomechanicalGeometryCalculator.select_active_side(pose)
    assert side == ActiveSide.RIGHT


def test_biomechanical_angles_with_wholebody_hands_and_feet():
    # Pose lateral vertical con 133 articulaciones completas
    calibrator = ScaleCalibrator(factor_mm_per_px=3.0)
    pose_lat = Pose2D(
        view=CameraView.LATERAL,
        track_id=1,
        keypoints={
            WholeBodyKeypointIndex.RIGHT_EAR: Keypoint(x=100, y=60, confidence=0.95),
            WholeBodyKeypointIndex.FACE_CHIN_BOTTOM: Keypoint(x=120, y=80, confidence=0.95),
            WholeBodyKeypointIndex.RIGHT_SHOULDER: Keypoint(x=100, y=100, confidence=0.95),
            WholeBodyKeypointIndex.RIGHT_ELBOW: Keypoint(x=100, y=180, confidence=0.95),
            WholeBodyKeypointIndex.RIGHT_WRIST: Keypoint(x=150, y=180, confidence=0.95),
            # Mano derecha: nudillo medio flexionado hacia abajo 30°
            # Antebrazo va horizontal hacia la derecha: codo (100, 180) -> muñeca (150, 180) -> vector (50, 0)
            # Nudillo medio en (170, 200) -> vector mano (20, 20) -> ángulo ~ 45° de flexión de muñeca
            WholeBodyKeypointIndex.RIGHT_MIDDLE_MCP: Keypoint(x=170, y=200, confidence=0.90),
            WholeBodyKeypointIndex.RIGHT_HIP: Keypoint(x=100, y=300, confidence=0.95),
            WholeBodyKeypointIndex.RIGHT_KNEE: Keypoint(x=100, y=420, confidence=0.95),
            WholeBodyKeypointIndex.RIGHT_ANKLE: Keypoint(x=100, y=550, confidence=0.95),
            # Pie derecho: talón y punta
            WholeBodyKeypointIndex.RIGHT_HEEL: Keypoint(x=90, y=570, confidence=0.95),
            WholeBodyKeypointIndex.RIGHT_BIG_TOE: Keypoint(x=130, y=570, confidence=0.95),
        }
    )

    angles = BiomechanicalGeometryCalculator.calculate_angles(
        lateral_pose=pose_lat,
        calibrator=calibrator,
        forced_side=ActiveSide.RIGHT,
    )

    # Tronco erguido
    assert angles.trunk_angle == pytest.approx(0.0, abs=1.0)
    # Cuello alineado
    assert angles.neck_angle == pytest.approx(0.0, abs=1.0)
    # Rodilla erguida
    assert angles.leg_knee_angle == pytest.approx(0.0, abs=2.0)
    # Codo a 90°
    assert angles.lower_arm_angle == pytest.approx(90.0, abs=2.0)
    # Muñeca calculada con vector de mano real de RTMPose (~45°)
    assert angles.wrist_angle == pytest.approx(45.0, abs=3.0)
    # Altura de toma al piso calculada con los talones (y=570):
    # dist_px = 570 - 200 = 370 px * 3 mm/px = 1110 mm = 1.11 m
    assert angles.pickup_height_m == pytest.approx(1.11, abs=0.05)


def test_faceless_photo_handling():
    # Pose sin rostro ni landmarks faciales
    pose_faceless = Pose2D(
        view=CameraView.LATERAL,
        keypoints={
            WholeBodyKeypointIndex.RIGHT_SHOULDER: Keypoint(x=100, y=100, confidence=0.9),
            WholeBodyKeypointIndex.RIGHT_HIP: Keypoint(x=100, y=300, confidence=0.9),
        }
    )
    angles = BiomechanicalGeometryCalculator.calculate_angles(
        lateral_pose=pose_faceless,
        forced_side=ActiveSide.RIGHT,
    )
    assert angles.neck_needs_human_review is True
    assert angles.neck_angle == 10.0
