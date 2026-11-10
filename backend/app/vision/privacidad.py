"""Conservative head masks; uncertainty closes the whole image, never returns raw pixels."""
from __future__ import annotations

import math


def _detectar_caras(imagen):
    import cv2
    gray = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
    regions = []
    # Both profile directions matter; these cascades ship with installed OpenCV.
    for filename, flipped in (("haarcascade_frontalface_default.xml", False),
                              ("haarcascade_profileface.xml", False),
                              ("haarcascade_profileface.xml", True)):
        classifier = cv2.CascadeClassifier(cv2.data.haarcascades + filename)
        if classifier.empty():
            raise RuntimeError("Detector facial OpenCV no disponible")
        source = cv2.flip(gray, 1) if flipped else gray
        for x, y, w, h in classifier.detectMultiScale(source, scaleFactor=1.1, minNeighbors=4, minSize=(20, 20)):
            if flipped:
                x = imagen.shape[1] - x - w
            regions.append((float(x), float(y), float(x + w), float(y + h)))
    return regions


def _detectar_personas(imagen):
    import cv2
    if imagen.shape[0] < 128 or imagen.shape[1] < 64:
        return []
    detector = cv2.HOGDescriptor()
    detector.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
    boxes, _ = detector.detectMultiScale(imagen, winStride=(8, 8), padding=(8, 8), scale=1.05)
    return [(float(x), float(y), float(x + w), float(y + h)) for x, y, w, h in boxes]


def _region_valida(region, ancho, alto):
    if len(region) != 4 or not all(math.isfinite(float(v)) for v in region):
        return None
    x1, y1, x2, y2 = region
    x1, y1 = max(0, math.floor(x1)), max(0, math.floor(y1))
    x2, y2 = min(ancho, math.ceil(x2)), min(alto, math.ceil(y2))
    return (x1, y1, x2, y2) if x2 > x1 and y2 > y1 else None


def localizar_cabezas(imagen, cajas=None, puntos=None, confianzas=None, umbral=.5):
    """Use every known person, not just the operator. None means insufficient evidence.

    Detector success is evidence, not proof that no other face exists. A known person
    without a plausible head forces the full-image fallback, even if other faces exist.
    """
    import cv2
    import numpy as np
    h, w = imagen.shape[:2]
    try:
        caras = _detectar_caras(imagen)
        personas = _detectar_personas(imagen) if cajas is None else cajas
        regiones = []
        for cara in caras:
            x1, y1, x2, y2 = cara
            margin = max(x2 - x1, y2 - y1) * .6 + 12
            regiones.append((x1 - margin, y1 - margin, x2 + margin, y2 + margin))
        for index, caja in enumerate(personas):
            valid = _region_valida(caja, w, h)
            if valid is None:
                return None
            x1, y1, x2, y2 = valid
            cabezas = [cara for cara in caras if x1 <= (cara[0] + cara[2]) / 2 <= x2
                       and y1 <= (cara[1] + cara[3]) / 2 <= y2]
            if puntos is not None and confianzas is not None:
                indices = [i for i in list(range(5)) + list(range(23, 91))
                           if i < len(confianzas[index]) and confianzas[index, i] >= umbral
                           and np.isfinite(puntos[index, i]).all()
                           and x1 <= puntos[index, i, 0] <= x2 and y1 <= puntos[index, i, 1] <= y2]
                if len(indices) >= 2:
                    head = puntos[index, indices]
                    lo, hi = head.min(axis=0), head.max(axis=0)
                    if min(hi - lo) >= 4:
                        margin = max(hi - lo) * .6 + 12
                        cabezas.append((lo[0] - margin, lo[1] - margin, hi[0] + margin, hi[1] + margin))
            if not cabezas:
                return None
            regiones.extend(cabezas)
            # Include hair/ears and the conservative upper person region, not facial landmarks alone.
            margin = (x2 - x1) * .15
            regiones.append((x1 - margin, y1 - margin, x2 + margin, y1 + (y2 - y1) * .45))
        validas = [_region_valida(r, w, h) for r in regiones]
        return validas if validas and all(validas) else None
    except (cv2.error, RuntimeError, ValueError, IndexError, TypeError):
        return None


def proteger_imagen(imagen, regiones=None):
    """Mask supported head regions on a copy, retaining exact dimensions and outside pixels."""
    protegida = imagen.copy()
    regiones = localizar_cabezas(imagen) if regiones is None else regiones
    h, w = imagen.shape[:2]
    try:
        validas = [_region_valida(r, w, h) for r in regiones] if regiones else []
    except (ValueError, TypeError, OverflowError):
        validas = []
    if not validas or not all(validas):
        protegida[:] = 0
    else:
        for x1, y1, x2, y2 in validas:
            protegida[y1:y2, x1:x2] = 0
    return protegida


AVISO_PRIVACIDAD = (
    "Privacidad: máscaras sólidas en las regiones de cabeza detectadas; si la evidencia es insuficiente, "
    "se cubre toda la fotografía. Los detectores pueden omitir personas: no garantizan anonimización "
    "completa. Revise la protección y los puntos antes de validar o compartir."
)
