"""Modelos tipados para RTMPose + ByteTrack con topología WholeBody de 133 Keypoints."""

from enum import IntEnum, Enum
try:
    from enum import StrEnum
except ImportError:
    class StrEnum(str, Enum):
        pass
from typing import Optional, Tuple, List, Dict
from pydantic import BaseModel, Field


class WholeBodyKeypointIndex(IntEnum):
    """Índices canónicos de RTMPose WholeBody (133 puntos articulares)."""
    # --- CUERPO (0 a 16) ---
    NOSE = 0
    LEFT_EYE = 1
    RIGHT_EYE = 2
    LEFT_EAR = 3
    RIGHT_EAR = 4
    LEFT_SHOULDER = 5
    RIGHT_SHOULDER = 6
    LEFT_ELBOW = 7
    RIGHT_ELBOW = 8
    LEFT_WRIST = 9
    RIGHT_WRIST = 10
    LEFT_HIP = 11
    RIGHT_HIP = 12
    LEFT_KNEE = 13
    RIGHT_KNEE = 14
    LEFT_ANKLE = 15
    RIGHT_ANKLE = 16

    # --- PIES (17 a 22) ---
    LEFT_BIG_TOE = 17
    LEFT_SMALL_TOE = 18
    LEFT_HEEL = 19
    RIGHT_BIG_TOE = 20
    RIGHT_SMALL_TOE = 21
    RIGHT_HEEL = 22

    # --- ROSTRO (23 a 90: 68 Puntos Faciales) ---
    FACE_CHIN_START = 23
    FACE_CHIN_BOTTOM = 31      # Mentón / barbilla
    FACE_NOSE_BRIDGE = 51      # Puente de la nariz
    FACE_NOSE_TIP = 54         # Punta de la nariz
    FACE_END = 90

    # --- MANO IZQUIERDA (91 a 111: 21 Puntos) ---
    LEFT_HAND_WRIST = 91
    LEFT_THUMB_CMC = 92
    LEFT_THUMB_MCP = 93
    LEFT_THUMB_IP = 94
    LEFT_THUMB_TIP = 95
    LEFT_INDEX_MCP = 96
    LEFT_INDEX_PIP = 97
    LEFT_INDEX_DIP = 98
    LEFT_INDEX_TIP = 99
    LEFT_MIDDLE_MCP = 100
    LEFT_MIDDLE_PIP = 101
    LEFT_MIDDLE_DIP = 102
    LEFT_MIDDLE_TIP = 103
    LEFT_RING_MCP = 104
    LEFT_RING_PIP = 105
    LEFT_RING_DIP = 106
    LEFT_RING_TIP = 107
    LEFT_PINKY_MCP = 108
    LEFT_PINKY_PIP = 109
    LEFT_PINKY_DIP = 110
    LEFT_PINKY_TIP = 111

    # --- MANO DERECHA (112 a 132: 21 Puntos) ---
    RIGHT_HAND_WRIST = 112
    RIGHT_THUMB_CMC = 113
    RIGHT_THUMB_MCP = 114
    RIGHT_THUMB_IP = 115
    RIGHT_THUMB_TIP = 116
    RIGHT_INDEX_MCP = 117
    RIGHT_INDEX_PIP = 118
    RIGHT_INDEX_DIP = 119
    RIGHT_INDEX_TIP = 120
    RIGHT_MIDDLE_MCP = 121
    RIGHT_MIDDLE_PIP = 122
    RIGHT_MIDDLE_DIP = 123
    RIGHT_MIDDLE_TIP = 124
    RIGHT_RING_MCP = 125
    RIGHT_RING_PIP = 126
    RIGHT_RING_DIP = 127
    RIGHT_RING_TIP = 128
    RIGHT_PINKY_MCP = 129
    RIGHT_PINKY_PIP = 130
    RIGHT_PINKY_DIP = 131
    RIGHT_PINKY_TIP = 132


class CameraView(StrEnum):
    """Vistas de cámara estándar del sistema ErgoAI."""
    FRONTAL = "frontal"
    LATERAL = "lateral"
    AEREA = "aerea"


class Keypoint(BaseModel):
    """Representa una articulación detectada por RTMPose."""
    x: float = Field(..., description="Coordenada X en píxeles")
    y: float = Field(..., description="Coordenada Y en píxeles")
    confidence: float = Field(..., ge=0.0, le=2.0, description="Confianza de detección [0.0 - 1.0+]")

    def is_reliable(self, threshold: float = 0.5) -> bool:
        """Determina si el punto supera el umbral mínimo de confianza."""
        return self.confidence >= threshold


class BoundingBox(BaseModel):
    """Caja delimitadora 2D generada por el detector y refinada por ByteTrack."""
    x1: float
    y1: float
    x2: float
    y2: float
    score: float = Field(default=1.0, ge=0.0, le=1.0)

    @property
    def width(self) -> float:
        return max(0.0, self.x2 - self.x1)

    @property
    def height(self) -> float:
        return max(0.0, self.y2 - self.y1)

    @property
    def center(self) -> Tuple[float, float]:
        return ((self.x1 + self.x2) / 2.0, (self.y1 + self.y2) / 2.0)


class Pose2D(BaseModel):
    """Pose completa WholeBody_133 con soporte de seguimiento por ByteTrack."""
    view: CameraView
    track_id: Optional[int] = Field(default=None, description="ID de seguimiento persistente asignado por ByteTrack")
    bbox: Optional[BoundingBox] = Field(default=None, description="Bounding box de la persona trackeada")
    keypoints: Dict[int, Keypoint] = Field(default_factory=dict, description="Diccionario de 133 articulaciones")

    def get_keypoint(self, idx: int | WholeBodyKeypointIndex) -> Optional[Keypoint]:
        """Obtiene un keypoint por su índice WholeBody (0 a 132)."""
        return self.keypoints.get(int(idx))

    def is_confident(self, idx: int | WholeBodyKeypointIndex, threshold: float = 0.5) -> bool:
        """Verifica si un punto articular supera el umbral de confianza."""
        kp = self.get_keypoint(idx)
        return kp is not None and kp.is_reliable(threshold)

    def average_confidence(self, indices: List[int | WholeBodyKeypointIndex]) -> float:
        """Calcula la confianza promedio para un subconjunto de articulaciones."""
        if not indices:
            return 0.0
        scores = [self.get_keypoint(i).confidence if self.get_keypoint(i) else 0.0 for i in indices]
        return sum(scores) / len(scores)

    # Métodos utilitarios para regiones WholeBody
    def get_body_keypoints(self) -> Dict[int, Keypoint]:
        """Retorna las 17 articulaciones mayores del cuerpo (0 a 16)."""
        return {i: self.keypoints[i] for i in range(17) if i in self.keypoints}

    def get_feet_keypoints(self) -> Dict[int, Keypoint]:
        """Retorna los 6 puntos de apoyo plantar y talones (17 a 22)."""
        return {i: self.keypoints[i] for i in range(17, 23) if i in self.keypoints}

    def get_face_keypoints(self) -> Dict[int, Keypoint]:
        """Retorna los 68 puntos faciales (23 a 90)."""
        return {i: self.keypoints[i] for i in range(23, 91) if i in self.keypoints}

    def get_left_hand_keypoints(self) -> Dict[int, Keypoint]:
        """Retorna las 21 articulaciones de la mano izquierda (91 a 111)."""
        return {i: self.keypoints[i] for i in range(91, 112) if i in self.keypoints}

    def get_right_hand_keypoints(self) -> Dict[int, Keypoint]:
        """Retorna las 21 articulaciones de la mano derecha (112 a 132)."""
        return {i: self.keypoints[i] for i in range(112, 133) if i in self.keypoints}


class MultiViewPose(BaseModel):
    """Contenedor de poses multi-ángulo correlacionadas por ByteTrack (track_id compartido)."""
    target_track_id: Optional[int] = Field(default=None, description="ID del operario bajo auditoría")
    frontal: Optional[Pose2D] = None
    lateral: Optional[Pose2D] = None
    aerea: Optional[Pose2D] = None


class FrameDetections(BaseModel):
    """Colección de todas las personas detectadas y trackeadas por ByteTrack en un fotograma/vista."""
    view: CameraView
    poses: List[Pose2D] = Field(default_factory=list, description="Poses de personas presentes en la escena")

    def get_by_track_id(self, track_id: int) -> Optional[Pose2D]:
        """Busca la pose de un operario por su track_id."""
        for p in self.poses:
            if p.track_id == track_id:
                return p
        return None

    @property
    def track_ids(self) -> List[int]:
        """Lista de IDs de personas detectadas."""
        return [p.track_id for p in self.poses if p.track_id is not None]


class MultiPersonScene(BaseModel):
    """Representa la escena fabril completa con múltiples personas en las 3 vistas canónicas."""
    frontal: Optional[FrameDetections] = None
    lateral: Optional[FrameDetections] = None
    aerea: Optional[FrameDetections] = None

    def get_all_track_ids(self) -> List[int]:
        """Obtiene el conjunto ordenado de todos los IDs trackeados en cualquier vista."""
        ids = set()
        for frame in (self.frontal, self.lateral, self.aerea):
            if frame:
                ids.update(frame.track_ids)
        return sorted(list(ids))

    def get_multiview_for_track_id(self, track_id: int) -> MultiViewPose:
        """Extrae la pose correlacionada en las 3 vistas para un operario específico."""
        return MultiViewPose(
            target_track_id=track_id,
            frontal=self.frontal.get_by_track_id(track_id) if self.frontal else None,
            lateral=self.lateral.get_by_track_id(track_id) if self.lateral else None,
            aerea=self.aerea.get_by_track_id(track_id) if self.aerea else None,
        )
