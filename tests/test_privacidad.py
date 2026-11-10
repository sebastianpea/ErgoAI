"""Privacy probes use synthetic pixels only; no confidential dataset copies."""
import json
import tempfile
from pathlib import Path
from unittest import mock

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.app.vision.estimador import EstimadorPose
from backend.app.vision import privacidad
from backend.main import create_app


@pytest.fixture
def tmp_path():
    with tempfile.TemporaryDirectory(prefix="ergoai_privacidad_") as directory:
        yield Path(directory)


@pytest.mark.parametrize("mode", ["flat", "no_pose", "low_face", "multiple"])
def test_estimator_masks_even_when_pose_is_unreliable(mode):
    img = np.full((160, 240, 3), 180, np.uint8)
    if mode != "flat":
        img[::2] = 60
    estimator = EstimadorPose()
    count = 2 if mode == "multiple" else 1
    estimator._detector = lambda image: np.array([[10, 10, 100, 150], [130, 10, 230, 150]][:count]) if mode != "no_pose" else []
    points = np.full((count, 133, 2), 30., dtype=float)
    scores = np.full((count, 133), .9)
    if mode in ("low_face", "no_pose"):
        scores[:] = 0
    estimator._pose = lambda image, bboxes: (points, scores)
    result = estimator.analizar(img)
    assert result.rostro_anonimizado
    assert not result.imagen_bgr.any(), "Uncertain regions must never contain original facial pixels"
    assert np.array_equal(img[0, 0], [180]*3 if mode == "flat" else [60]*3)
    if mode == "no_pose":
        assert result.personas == 0 and result.puntos == []
    if mode == "multiple":
        assert result.personas == 2


@pytest.mark.parametrize("uncertain_person", [False, True])
def test_estimator_reuses_all_person_boxes_and_pose_heads(uncertain_person):
    image = np.full((200, 240, 3), 190, np.uint8)
    image[::2] = 90
    boxes = np.array([[10, 10, 100, 190], [140, 10, 230, 190]], dtype=float)
    points = np.zeros((2, 133, 2), dtype=float)
    scores = np.zeros((2, 133), dtype=float)
    for person, x in enumerate((30, 170)):
        points[person, :2] = [(x, 20), (x + 20, 40)]
        scores[person, :2] = .9
    if uncertain_person:
        scores[1] = 0
    estimator = EstimadorPose()
    estimator._detector = mock.Mock(return_value=boxes)
    estimator._pose = mock.Mock(return_value=(points, scores))
    with mock.patch.object(privacidad, "_detectar_caras", return_value=[]), \
         mock.patch.object(privacidad, "_detectar_personas", side_effect=AssertionError("Reuse analysis boxes")):
        result = estimator.analizar(image)
    estimator._detector.assert_called_once()
    assert result.personas == 2
    assert result.imagen_bgr.shape == image.shape
    assert not result.imagen_bgr[20:40, 30:50].any()
    assert not result.imagen_bgr[20:40, 170:190].any()
    if uncertain_person:
        assert not result.imagen_bgr.any()
        assert result.regiones_privacidad == []
    else:
        assert np.array_equal(result.imagen_bgr[130:], image[130:])
        assert result.regiones_privacidad
        assert result.puntos[0].x == 30 and result.puntos[0].y == 20


def _known_heads():
    return [(20, 15, 50, 45), (170, 15, 200, 45)]


def test_localized_masks_keep_torso_and_background_for_all_known_heads():
    image = np.full((200, 240, 3), 190, np.uint8)
    with mock.patch.object(privacidad, "_detectar_caras", return_value=_known_heads(), create=True), \
         mock.patch.object(privacidad, "_detectar_personas", return_value=[], create=True):
        protected = privacidad.proteger_imagen(image)
    assert protected.shape == image.shape
    for x1, y1, x2, y2 in _known_heads():
        assert not protected[y1:y2, x1:x2].any()
    assert np.array_equal(protected[120:, :], image[120:, :])
    assert np.array_equal(protected[80:100, 100:130], image[80:100, 100:130])
    assert image.min() == 190


@pytest.mark.parametrize("origin", ["upload", "legacy"])
def test_public_media_localizes_all_heads_and_keeps_originals(tmp_path, origin):
    from backend.app.vision.estimador import estimador
    from tests.test_vision import _resultado
    image = np.full((720, 1280, 3), 190, np.uint8)
    heads = [(100, 30, 160, 90), (1000, 30, 1060, 90)]
    encoded = cv2.imencode(".jpg", image)[1].tobytes()
    with TestClient(create_app(workspace_dir=tmp_path, sembrar=False)) as client, \
         mock.patch.object(privacidad, "_detectar_caras", return_value=heads, create=True), \
         mock.patch.object(privacidad, "_detectar_personas", return_value=[], create=True), \
         mock.patch.object(estimador, "estado", return_value=(True, "mock")), \
         mock.patch.object(estimador, "analizar", side_effect=_resultado):
        if origin == "upload":
            response = client.post("/casos", data={"datos": json.dumps({"usuario": "Ergonomia", "estacion": "Prueba"})},
                                   files={"lateral": ("synthetic.jpg", encoded, "image/jpeg")})
            assert response.status_code == 200, response.text
            url = client.get("/casos/" + response.json()["id"]).json()["imagenes"][0]["url"]
            path = tmp_path / response.json()["id"] / "inputs" / "lateral.jpg"
            saved = cv2.imread(str(path))
            for x1, y1, x2, y2 in heads:
                assert saved[y1:y2, x1:x2].max() <= 2
            assert np.array_equal(saved[300:, :], image[300:, :])
        else:
            path = tmp_path / "C-001" / "inputs" / "legacy.jpg"
            path.parent.mkdir(parents=True)
            path.write_bytes(encoded)
            url = "/media/C-001/legacy.jpg"
        before = {str(p): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
        response = client.get(url)
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        protected = cv2.imdecode(np.frombuffer(response.content, np.uint8), cv2.IMREAD_COLOR)
        assert protected.shape == image.shape
        for x1, y1, x2, y2 in heads:
            assert not protected[y1:y2, x1:x2].any()
        assert np.array_equal(protected[300:, :], image[300:, :])
        assert before == {str(p): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
        if origin == "upload":
            # Saved masks must remain usable even when masked faces are no longer detectable.
            with mock.patch.object(privacidad, "_detectar_caras", return_value=[]):
                served = client.get(url)
            decoded = cv2.imdecode(np.frombuffer(served.content, np.uint8), cv2.IMREAD_COLOR)
            assert np.array_equal(decoded[300:, :], image[300:, :])
            # A replaced original must not inherit trusted regions from different saved bytes.
            path.write_bytes(encoded)
            with mock.patch.object(privacidad, "_detectar_caras", return_value=[]):
                stale = client.get(url)
            assert stale.status_code == 200
            assert not cv2.imdecode(np.frombuffer(stale.content, np.uint8), cv2.IMREAD_COLOR).any()
            assert path.read_bytes() == encoded


def test_legacy_media_is_safe_without_mutating_originals(tmp_path):
    with TestClient(create_app(workspace_dir=tmp_path, sembrar=False)) as client:
        inputs = tmp_path / "C-001" / "inputs"
        inputs.mkdir(parents=True)
        original = inputs / "legacy.jpg"
        cv2.imwrite(str(original), np.full((160, 240, 3), 190, np.uint8))
        before = original.read_bytes()
        response = client.get("/media/C-001/legacy.jpg")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        image = cv2.imdecode(np.frombuffer(response.content, np.uint8), cv2.IMREAD_COLOR)
        assert image.shape == (160, 240, 3)
        assert not image.any()
        assert original.read_bytes() == before
        (inputs / "unsafe.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"><image href="private.jpg"/></svg>')
        assert client.get("/media/C-001/unsafe.svg").status_code == 422
        assert client.get("/media/C-001/missing.jpg").status_code == 404


def test_upload_optional_failure_saved_and_served_safely_and_rejection_is_atomic(tmp_path):
    from tests.test_vision import _resultado
    from backend.app.vision.estimador import estimador, ResultadoFoto
    image = np.full((720, 1280, 3), 190, np.uint8)
    encoded = cv2.imencode(".jpg", image)[1].tobytes()
    payload = {"usuario": "Ergonomia", "rol": "ergonomia", "estacion": "Prueba"}
    with TestClient(create_app(workspace_dir=tmp_path, sembrar=False)) as client, \
         mock.patch.object(estimador, "estado", return_value=(True, "mock")), \
         mock.patch.object(estimador, "analizar", side_effect=[_resultado(image), ResultadoFoto(image.copy(), 0)]):
        response = client.post("/casos", data={"datos": json.dumps(payload)}, files={
            view: ("test.jpg", encoded, "image/jpeg") for view in ("lateral", "frontal")})
        assert response.status_code == 200, response.text
        detail = client.get("/casos/" + response.json()["id"]).json()
        for entry in detail["imagenes"]:
            saved = cv2.imread(str(tmp_path / response.json()["id"] / "inputs" / (entry["vista"] + ".jpg")))
            assert not saved.any()
            media = client.get(entry["url"])
            assert media.status_code == 200
            assert not cv2.imdecode(np.frombuffer(media.content, np.uint8), cv2.IMREAD_COLOR).any()
        assert any("privacidad" in h["mensaje"].lower() for h in detail["hallazgos"])
        before = {str(p.relative_to(tmp_path)): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
        bad = client.post("/casos", data={"datos": json.dumps(payload)}, files={"lateral": ("bad.jpg", b"bad", "image/jpeg")})
        assert bad.status_code == 422
        assert bad.json() == {"detail": "La foto lateral no es una imagen JPG o PNG válida"}
        assert before == {str(p.relative_to(tmp_path)): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
