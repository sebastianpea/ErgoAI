from types import SimpleNamespace
from unittest.mock import patch

import cv2
import numpy as np

from backend.app.vision.annotador import anotar_esqueleto


def test_draw_filters_low_confidence_points_and_connections():
    points = [
        SimpleNamespace(id=5, x=10, y=10, confianza=0.9),
        SimpleNamespace(id=7, x=20, y=20, confianza=0.9),
        SimpleNamespace(id=9, x=30, y=30, confianza=0.39),
    ]
    lines = []
    circles = []
    with patch.object(cv2, "line", side_effect=lambda image, a, b, color, thickness, *_: lines.append((a, b, thickness))), \
         patch.object(cv2, "circle", side_effect=lambda image, center, radius, *_: circles.append((center, radius))):
        anotar_esqueleto(np.zeros((200, 200, 3), dtype=np.uint8), points)

    assert ((10, 10), (20, 20)) in [(a, b) for a, b, _ in lines]
    assert ((20, 20), (30, 30)) not in [(a, b) for a, b, _ in lines]
    assert (30, 30) not in [center for center, _ in circles]


def test_draw_uses_thinner_hand_link_than_body_link():
    points = [
        SimpleNamespace(id=5, x=10, y=10, confianza=0.9),
        SimpleNamespace(id=7, x=20, y=20, confianza=0.9),
        SimpleNamespace(id=9, x=30, y=30, confianza=0.9),
        SimpleNamespace(id=17, x=40, y=40, confianza=0.9),
    ]
    lines = []
    with patch.object(cv2, "line", side_effect=lambda image, a, b, color, thickness, *_: lines.append((a, b, thickness))):
        anotar_esqueleto(np.zeros((1000, 1000, 3), dtype=np.uint8), points)

    body_width = next(width for a, b, width in lines if a == (10, 10) and b == (20, 20) and width < 10)
    hand_width = next(width for a, b, width in lines if a == (30, 30) and b == (40, 40) and width < 10)
    assert hand_width < body_width
