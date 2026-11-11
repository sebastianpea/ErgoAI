"""
Anotador visual de esqueleto biomecánico y dictamen REBA con OpenCV.
Genera imágenes anotadas listas para visualización en frontend o guardado en disco,
compatible al 100% con Windows y Linux (CPU o GPU).
"""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional, Tuple

from backend.app.settings import VISION_UMBRAL_DIBUJO

if TYPE_CHECKING:
    import numpy as np

# Pares de índices (COCO-17 + Nudillos WholeBody 17/18) que forman los huesos del esqueleto
HUESOS: List[Tuple[int, int, str]] = [
    # Torso
    (5, 6, "tronco"),
    (5, 11, "tronco"),
    (6, 12, "tronco"),
    (11, 12, "tronco"),
    # Brazo izquierdo
    (5, 7, "brazo"),
    (7, 9, "antebrazo"),
    (9, 17, "muneca"),
    # Brazo derecho
    (6, 8, "brazo"),
    (8, 10, "antebrazo"),
    (10, 18, "muneca"),
    # Pierna izquierda
    (11, 13, "piernas"),
    (13, 15, "piernas"),
    # Pierna derecha
    (12, 14, "piernas"),
    (14, 16, "piernas"),
    # Cabeza y cuello
    (3, 5, "cuello"),
    (4, 6, "cuello"),
]

# Paleta de colores BGR según nivel de riesgo REBA
COLORES_REBA_BGR: Dict[str, Tuple[int, int, int]] = {
    "inapreciable": (200, 180, 40),  # Azul verdoso
    "bajo": (70, 180, 40),          # Verde
    "medio": (30, 180, 240),        # Amarillo/Ámbar
    "alto": (30, 80, 230),          # Naranja/Rojo
    "muy_alto": (180, 40, 180),     # Púrpura/Magenta
}

COLOR_POR_DEFECTO = (229, 180, 60)  # Cian Jabil (#3CB4E5 en BGR: (229, 180, 60))


def anotar_esqueleto(
    imagen_bgr: np.ndarray,
    puntos: List[Any],
    reba_final: Optional[int] = None,
    reba_nivel: Optional[str] = None,
    angulos: Optional[Mapping[str, Optional[float]]] = None,
    confianza_minima: float = VISION_UMBRAL_DIBUJO,
) -> np.ndarray:
    """
    Dibuja el esqueleto biomecánico, banner informativo superior y etiquetas angulares.
    """
    import cv2

    canvas = imagen_bgr.copy()
    h, w = canvas.shape[:2]

    # Diccionario de puntos válidos por id
    pts_dict: Dict[int, Tuple[int, int, float]] = {}
    for p in puntos:
        pid = getattr(p, "id", None)
        px = getattr(p, "x", None)
        py = getattr(p, "y", None)
        pconf = getattr(p, "confianza", 1.0)
        if pid is not None and px is not None and py is not None:
            if pconf >= confianza_minima and 0 <= px <= w and 0 <= py <= h:
                pts_dict[int(pid)] = (int(round(px)), int(round(py)), float(pconf))

    nivel_str = (reba_nivel or "medio").lower()
    color_nivel = COLORES_REBA_BGR.get(nivel_str, (70, 180, 40))

    # Tamaños relativos: torso/extremidades dominan; manos y rasgos faciales quedan discretos.
    escala = min(h, w) / 1000.0
    grosor_cuerpo = max(2, int(round(2 * escala)))
    grosor_distal = max(1, int(round(escala)))
    radio_cuerpo = max(3, int(round(4 * escala)))
    radio_mano = max(2, int(round(2.5 * escala)))
    radio_cara = max(1, int(round(1.5 * escala)))
    puntos_cara = {0, 1, 2, 3, 4}
    puntos_mano = {17, 18}

    # 1. Dibujar conexiones sólo cuando ambos landmarks superan el umbral.
    for a, b, _ in HUESOS:
        if a in pts_dict and b in pts_dict:
            pt1 = (pts_dict[a][0], pts_dict[a][1])
            pt2 = (pts_dict[b][0], pts_dict[b][1])
            grosor = grosor_distal if a in puntos_mano or b in puntos_mano else grosor_cuerpo
            cv2.line(canvas, pt1, pt2, (20, 20, 20), grosor + 2, cv2.LINE_AA)
            cv2.line(canvas, pt1, pt2, color_nivel, grosor, cv2.LINE_AA)

    # 2. Articulaciones en capas: cara (puntos), cuerpo y manos (nodos pequeños).
    for pid, (x, y, conf) in pts_dict.items():
        radio = radio_cara if pid in puntos_cara else radio_mano if pid in puntos_mano else radio_cuerpo
        cv2.circle(canvas, (x, y), radio + 1, (20, 20, 20), -1, cv2.LINE_AA)
        cv2.circle(canvas, (x, y), radio, (255, 255, 255), -1, cv2.LINE_AA)
        cv2.circle(canvas, (x, y), max(1, radio - 2), color_nivel, -1, cv2.LINE_AA)

    # 3. Banner superior con dictamen REBA
    banner_h = max(46, int(round(h * 0.075)))
    cv2.rectangle(canvas, (0, 0), (w, banner_h), (22, 42, 60), -1)  # Azul oscuro Jabil
    # Línea divisoria cian
    cv2.line(canvas, (0, banner_h), (w, banner_h), (229, 180, 60), 2)

    texto_reba = f"ErgoAI · REBA {reba_final if reba_final is not None else '-'} [{nivel_str.upper()}]"
    escala_fuente = max(0.55, min(w, h) / 1200.0)
    cv2.putText(
        canvas,
        texto_reba,
        (16, int(banner_h * 0.65)),
        cv2.FONT_HERSHEY_DUPLEX,
        escala_fuente,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )

    # 4. Etiquetas de ángulos si están disponibles
    if angulos:
        partes_angulos = []
        for seg, val in angulos.items():
            if val is not None:
                partes_angulos.append(f"{seg[:4].capitalize()}: {val:.0f}°")
        texto_angulos = " | ".join(partes_angulos[:4])
        if texto_angulos:
            tam_txt, _ = cv2.getTextSize(texto_angulos, cv2.FONT_HERSHEY_SIMPLEX, escala_fuente * 0.8, 1)
            cv2.putText(
                canvas,
                texto_angulos,
                (max(16, w - tam_txt[0] - 16), int(banner_h * 0.65)),
                cv2.FONT_HERSHEY_SIMPLEX,
                escala_fuente * 0.8,
                (200, 220, 240),
                1,
                cv2.LINE_AA,
            )

    return canvas


def codificar_imagen_b64(imagen_bgr: np.ndarray, calidad: int = 85) -> str:
    """Codifica una imagen OpenCV en una cadena data URL base64 JPEG."""
    import cv2

    ok, buf = cv2.imencode(".jpg", imagen_bgr, [cv2.IMWRITE_JPEG_QUALITY, calidad])
    if not ok:
        raise RuntimeError("Error al codificar imagen a JPEG")
    b64_str = base64.b64encode(buf.tobytes()).decode("utf-8")
    return f"data:image/jpeg;base64,{b64_str}"
