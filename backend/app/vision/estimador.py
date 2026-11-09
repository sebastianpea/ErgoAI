"""
Estimación de pose top-down: YOLOX detecta personas y RTMPose WholeBody-133 extrae sus articulaciones.
Mismo stack que el pipeline del equipo (github.com/sebastianpea/ErgoAI, rama develop), reducido a lo que
este backend necesita: puntos por foto. Ángulos, REBA y reglas los calcula core_ergonomics.

Puntos que se guardan por foto (formato del sistema):
    0–16  cuerpo COCO-17 (idénticos a los índices 0–16 de WholeBody-133)
    17    nudillo medio izquierdo  (WholeBody 100)  → permite medir la muñeca
    18    nudillo medio derecho    (WholeBody 121)
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

try:  # el stack de visión es opcional: sin él, el resto del backend funciona igual
    import numpy as np
except ImportError:  # pragma: no cover
    np = None  # type: ignore[assignment]

from backend.app.settings import (
    VISION_CONFIANZA_KEYPOINT,
    VISION_CONFIANZA_RESPALDO,
    VISION_DEVICE,
    VISION_LADO_MAXIMO_PX,
    VISION_MIN_PUNTOS_RESPALDO,
    VISION_STD_MINIMA_IMAGEN,
)
from backend.app.vision.modelos import MODELOS, faltantes, ruta_modelo

log = logging.getLogger("ergoai.vision")

MAPA_PUNTOS: dict[int, int] = {i: i for i in range(17)} | {17: 100, 18: 121}
ROSTRO_WHOLEBODY = list(range(0, 5)) + list(range(23, 91))  # nariz, ojos, orejas + 68 puntos faciales
LADO_MAXIMO_PX = VISION_LADO_MAXIMO_PX  # se reduce la foto antes de inferir y guardar (coordenadas en ese tamaño)
MIN_PUNTOS_RESPALDO = VISION_MIN_PUNTOS_RESPALDO  # de los 17 del cuerpo, detectables en oclusión severa


class VisionNoDisponible(RuntimeError):
    pass


@dataclass
class PuntoDetectado:
    id: int
    x: float
    y: float
    confianza: float


@dataclass
class ResultadoFoto:
    imagen_bgr: np.ndarray          # ya reducida y con el rostro difuminado
    personas: int
    puntos: List[PuntoDetectado] = field(default_factory=list)
    caja: Optional[Tuple[float, float, float, float]] = None
    rostro_anonimizado: bool = False
    por_respaldo: bool = False  # el detector no vio a la persona; se estimó sobre la imagen completa


def reducir(img: np.ndarray) -> np.ndarray:
    import cv2
    h, w = img.shape[:2]
    lado = max(h, w)
    if lado <= LADO_MAXIMO_PX:
        return img
    f = LADO_MAXIMO_PX / lado
    return cv2.resize(img, (round(w * f), round(h * f)), interpolation=cv2.INTER_AREA)


def anonimizar_rostro(img: np.ndarray, kpts: np.ndarray, scores: np.ndarray, umbral: float) -> bool:
    """Difumina la región del rostro de cada persona. Devuelve True si difuminó algo."""
    import cv2
    h, w = img.shape[:2]
    hecho = False
    for persona in range(kpts.shape[0]):
        sel = [i for i in ROSTRO_WHOLEBODY if scores[persona, i] >= umbral]
        if len(sel) < 2:
            continue
        xs, ys = kpts[persona, sel, 0], kpts[persona, sel, 1]
        x1, x2, y1, y2 = xs.min(), xs.max(), ys.min(), ys.max()
        margen = max(x2 - x1, y2 - y1) * 0.6 + 12
        x1, y1 = int(max(0, x1 - margen)), int(max(0, y1 - margen))
        x2, y2 = int(min(w, x2 + margen)), int(min(h, y2 + margen))
        if x2 - x1 < 4 or y2 - y1 < 4:
            continue
        roi = img[y1:y2, x1:x2]
        k = max(15, (min(roi.shape[:2]) // 2) | 1)  # kernel impar proporcional
        img[y1:y2, x1:x2] = cv2.GaussianBlur(roi, (k, k), 0)
        hecho = True
    return hecho


class EstimadorPose:
    """Carga perezosa de los modelos (la primera foto tarda unos segundos más)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._detector = None
        self._pose = None

    @staticmethod
    def estado() -> Tuple[bool, str]:
        try:
            import rtmlib  # noqa: F401
            import cv2  # noqa: F401
        except ImportError as e:
            return False, f"Dependencias de visión no instaladas ({e.name}). Ver README: pip install -r backend/requirements-vision.txt"
        if faltan := faltantes():
            return False, ("Faltan modelos ONNX: " + ", ".join(MODELOS[k].archivo for k in faltan)
                           + ". Ejecuta: .venv\\Scripts\\python -m backend.app.vision.modelos")
        return True, f"{MODELOS['detector'].nombre} + {MODELOS['pose'].nombre} en {VISION_DEVICE.upper()}"

    def _cargar(self) -> None:
        if self._pose is not None:
            return
        ok, detalle = self.estado()
        if not ok:
            raise VisionNoDisponible(detalle)
        import onnxruntime
        from rtmlib import RTMPose, YOLOX
        onnxruntime.set_default_logger_severity(3)  # solo errores: los avisos de grafo del modelo son ruido
        log.info("Cargando modelos de visión (%s)", detalle)
        self._detector = YOLOX(onnx_model=str(ruta_modelo("detector")), model_input_size=MODELOS["detector"].entrada,
                               backend="onnxruntime", device=VISION_DEVICE)
        self._pose = RTMPose(onnx_model=str(ruta_modelo("pose")), model_input_size=MODELOS["pose"].entrada,
                             to_openpose=False, backend="onnxruntime", device=VISION_DEVICE)

    def analizar(self, img_bgr: np.ndarray) -> ResultadoFoto:
        """Detecta personas, elige al operador (la de mayor tamaño) y anonimiza rostros."""
        with self._lock:  # ONNX Runtime admite concurrencia, pero en CPU no gana nada y duplica memoria
            self._cargar()
            img = reducir(img_bgr).copy()
            if float(img.std()) < VISION_STD_MINIMA_IMAGEN:
                return ResultadoFoto(imagen_bgr=img, personas=0)
            cajas = self._detector(img)
            cajas = np.atleast_2d(np.asarray(cajas, dtype=np.float32)) if cajas is not None else np.zeros((0, 4))
            respaldo = cajas.size == 0
            if respaldo:
                # Oclusión severa (p. ej. una caja tapa el torso): se estima sobre la imagen completa,
                # igual que el pipeline original, y solo se acepta si el cuerpo se ve con claridad.
                h, w = img.shape[:2]
                cajas = np.array([[0, 0, w, h]], dtype=np.float32)
            cajas = cajas[:, :4]
            kpts, scores = self._pose(img, bboxes=cajas.tolist())
            if respaldo and int((scores[0, :17] >= VISION_CONFIANZA_RESPALDO).sum()) < MIN_PUNTOS_RESPALDO:
                return ResultadoFoto(imagen_bgr=img, personas=0)

        anonimo = anonimizar_rostro(img, kpts, scores, VISION_CONFIANZA_KEYPOINT)
        areas = (cajas[:, 2] - cajas[:, 0]) * (cajas[:, 3] - cajas[:, 1])
        p = int(np.argmax(areas))
        h, w = img.shape[:2]
        puntos = [
            PuntoDetectado(
                id=nuestro,
                x=float(np.clip(kpts[p, wb, 0], 0, w)), y=float(np.clip(kpts[p, wb, 1], 0, h)),
                confianza=round(float(np.clip(scores[p, wb], 0.0, 1.0)), 3),
            )
            for nuestro, wb in MAPA_PUNTOS.items()
        ]
        x1, y1, x2, y2 = (float(v) for v in cajas[p])
        return ResultadoFoto(imagen_bgr=img, personas=len(cajas), puntos=puntos,
                             caja=None if respaldo else (x1, y1, x2 - x1, y2 - y1),
                             rostro_anonimizado=anonimo, por_respaldo=respaldo)


estimador = EstimadorPose()
