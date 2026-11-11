"""Face-only elliptical blur; unsupported evidence must never enable image display."""
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
    x1, y1, x2, y2 = map(float, region)
    # Do not clip unsupported/truncated evidence into a plausible face.
    if not (0 <= x1 < x2 <= ancho and 0 <= y1 < y2 <= alto):
        return None
    return math.floor(x1), math.floor(y1), math.ceil(x2), math.ceil(y2)


def validar_regiones(imagen, regiones):
    """Normalize face evidence identically for detection, persistence and media reads."""
    h, w = imagen.shape[:2]
    try:
        validas = [_region_valida(r, w, h) for r in regiones]
        if not validas or not all(validas):
            return None
        for x1, y1, x2, y2 in validas:
            ancho, alto = x2 - x1, y2 - y1
            if min(ancho, alto) < 20 or not .5 <= ancho / alto <= 2:
                return None
        return validas
    except (ValueError, TypeError, OverflowError):
        return None


def localizar_cabezas(imagen, cajas=None, puntos=None, confianzas=None, umbral=.5):
    """Require a detected face for every known person; landmarks alone cannot prove a face.

    The pose arguments remain accepted for estimator compatibility. Neither two points
    nor an upper-body rectangle supports a face-only blur.
    """
    import cv2
    h, w = imagen.shape[:2]
    try:
        caras = validar_regiones(imagen, _detectar_caras(imagen))
        personas = _detectar_personas(imagen) if cajas is None else cajas
        if caras is None:
            return None
        cajas_validas = [_region_valida(caja, w, h) for caja in personas]
        if not all(cajas_validas):
            return None
        cubiertas = set()
        for a, b, c, d in caras:
            candidatas = [i for i, (x1, y1, x2, y2) in enumerate(cajas_validas)
                          if x1 <= a < c <= x2 and y1 <= b < d <= y1 + (y2 - y1) * .5]
            # An ambiguous face cannot authorize two different people.
            if len(candidatas) > 1:
                return None
            cubiertas.update(candidatas)
        return caras if len(cubiertas) == len(cajas_validas) else None
    except (cv2.error, RuntimeError, ValueError, IndexError, TypeError, OverflowError):
        return None


def proteger_imagen(imagen, regiones=None):
    """Blur only face ellipses on a copy; black is an internal withheld-frame sentinel."""
    import cv2
    import numpy as np
    protegida = imagen.copy()
    regiones = localizar_cabezas(imagen) if regiones is None else regiones
    validas = validar_regiones(imagen, regiones)
    if validas is None:
        # Estimator compatibility only: the media service must refuse empty evidence.
        protegida[:] = 0
    else:
        for x1, y1, x2, y2 in validas:
            rostro = imagen[y1:y2, x1:x2]
            mascara = np.zeros(rostro.shape[:2], np.uint8)
            centro = ((x2 - x1) // 2, (y2 - y1) // 2)
            cv2.ellipse(mascara, centro, centro, 0, 0, 360, 255, -1)
            # shortcut: fixed relative blur is not certified anonymization; review before sharing.
            difuminada = cv2.GaussianBlur(rostro, (0, 0), max(x2 - x1, y2 - y1) / 4)
            protegida[y1:y2, x1:x2][mascara != 0] = difuminada[mascara != 0]
    return protegida


POLITICA_PRIVACIDAD = 3
REVISION_PRIVACIDAD = "Imagen no disponible por privacidad: requiere revisión del rostro de todas las personas."
AVISO_PRIVACIDAD = (
    "Privacidad: difuminado gaussiano elíptico únicamente sobre los rostros localizados; si falta "
    "evidencia de alguna persona, la imagen no se muestra y requiere revisión. Los detectores pueden "
    "omitir personas y el difuminado no garantiza anonimización completa. Revise antes de compartir."
)
