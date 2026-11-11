"""Optional real inference accuracy check; synthetic mocks do not establish accuracy."""
import json
from pathlib import Path

import cv2
import pytest

from backend.app.core_ergonomics.angle_geometry import extraer_angulos_laterales
from backend.app.vision.estimador import estimador

DATASET_DIR = Path(__file__).resolve().parents[1] / "backend/app/seed/dataset_jabil"
REFERENCE = DATASET_DIR / "angulos_referencia.json"
TOLERANCE_DEG = 5.0


def test_dataset_images_exist():
    assert DATASET_DIR.is_dir()
    assert any(DATASET_DIR.glob("*.jpg"))


def test_vision_precision_within_reba_range():
    # The former EXPECTED values had no annotated provenance and were never measured.
    # Reference format: {filename: {segment: degrees}}, validated by a specialist.
    if not REFERENCE.is_file():
        pytest.skip("Faltan ángulos de referencia anotados y validados; no se puede acreditar precisión >=90%")
    available, reason = estimador.estado()
    if not available:
        pytest.skip(reason)
    expected = json.loads(REFERENCE.read_text(encoding="utf-8"))
    assert expected, "La referencia validada no puede estar vacía"
    correct = total = 0
    for filename, angles in expected.items():
        image = cv2.imread(str(DATASET_DIR / filename))
        assert image is not None, f"Falta imagen de referencia: {filename}"
        result = estimador.analizar(image)
        measured = extraer_angulos_laterales(result.puntos)
        for segment, degrees in angles.items():
            total += 1
            angle = measured[segment]
            if angle.grados is not None and angle.confianza >= .5 and abs(angle.grados - degrees) <= TOLERANCE_DEG:
                correct += 1
    assert total > 0
    assert correct / total >= .90, f"Precisión real {correct}/{total} inferior a 90%"


def test_empty_workstation_has_no_detected_persons():
    image = cv2.imread(str(DATASET_DIR / "control_estacion_vacia.jpg"))
    assert image is not None
    result = estimador.analizar(image)
    assert result.personas == 0
    assert len(result.puntos) == 0
    assert result.rostro_anonimizado

