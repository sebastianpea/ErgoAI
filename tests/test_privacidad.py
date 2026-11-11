"""Privacy probes use synthetic pixels only; no confidential dataset copies."""
import hashlib
import json
import tempfile
from pathlib import Path
from unittest import mock

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.app.vision import privacidad
from backend.app.vision.estimador import EstimadorPose, estimador, ResultadoFoto
from backend.main import create_app

REVIEW = {"detail": "Imagen no disponible por privacidad: requiere revisión del rostro de todas las personas."}
HEADS = [(20, 15, 60, 55), (170, 15, 210, 55)]


@pytest.fixture
def tmp_path():
    with tempfile.TemporaryDirectory(prefix="ergoai_privacidad_") as directory:
        yield Path(directory)


def _image():
    image = np.full((200, 240, 3), 190, np.uint8)
    for x1, y1, x2, y2 in HEADS:
        image[y1:y2, x1:x2] = np.indices((y2-y1, x2-x1)).sum(axis=0)[:, :, None] % 2 * 180 + 40
    return image


def _snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def _assert_review(response):
    assert response.status_code == 422
    assert response.json() == REVIEW
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["content-type"] == "application/json"


def test_face_only_elliptical_gaussian_blur_for_every_face():
    image = _image()
    original = image.copy()
    with mock.patch.object(privacidad, "_detectar_caras", return_value=HEADS), \
         mock.patch.object(privacidad, "_detectar_personas", return_value=[]):
        protected = privacidad.proteger_imagen(image)
    assert protected.shape == image.shape
    mask = np.zeros(image.shape[:2], np.uint8)
    for x1, y1, x2, y2 in HEADS:
        roi = np.zeros((y2-y1, x2-x1), np.uint8)
        cv2.ellipse(roi, ((x2-x1)//2, (y2-y1)//2), ((x2-x1)//2, (y2-y1)//2), 0, 0, 360, 255, -1)
        mask[y1:y2, x1:x2] = roi
        center = protected[y1+10:y2-10, x1+10:x2-10]
        assert center.min() > 0
        assert center.std() < image[y1+10:y2-10, x1+10:x2-10].std() / 4
    assert np.array_equal(protected[mask == 0], image[mask == 0])
    assert np.array_equal(image, original)


@pytest.mark.parametrize("faces,boxes", [
    ([], []),
    ([HEADS[0]], [(10, 5, 100, 190), (140, 5, 230, 190)]),
    ([(20, 140, 60, 180)], [(10, 5, 100, 190)]),
    ([(float("nan"), 10, 60, 55)], []),
    ([(-10, 15, 60, 55)], []),
    ([(20, 15, 21, 16)], []),
    ([HEADS[0]], [(10, 5, 100, 190), (10, 5, 100, 190)]),
])
def test_unsupported_frame_is_withheld_without_changing_files(tmp_path, faces, boxes):
    with TestClient(create_app(workspace_dir=tmp_path, sembrar=False)) as client:
        path = tmp_path / "C-001" / "inputs" / "legacy.jpg"
        path.parent.mkdir(parents=True)
        path.write_bytes(cv2.imencode(".jpg", _image())[1].tobytes())
        before = _snapshot(tmp_path)
        with mock.patch.object(privacidad, "_detectar_caras", return_value=faces), \
             mock.patch.object(privacidad, "_detectar_personas", return_value=boxes):
            _assert_review(client.get("/media/C-001/legacy.jpg"))
        assert _snapshot(tmp_path) == before


def test_pose_points_alone_do_not_authorize_a_guessed_face():
    image = _image()
    boxes = np.array([[10, 5, 100, 190], [140, 5, 230, 190]])
    points = np.full((2, 133, 2), 30.)
    scores = np.ones((2, 133))
    with mock.patch.object(privacidad, "_detectar_caras", return_value=[HEADS[0]]):
        assert privacidad.localizar_cabezas(image, boxes, points, scores) is None


@pytest.mark.parametrize("failure", [RuntimeError("detector"), cv2.error("detector")])
def test_detector_failure_withholds_media(tmp_path, failure):
    with TestClient(create_app(workspace_dir=tmp_path, sembrar=False)) as client:
        path = tmp_path / "C-001" / "inputs" / "legacy.png"
        path.parent.mkdir(parents=True)
        cv2.imwrite(str(path), _image())
        before = _snapshot(tmp_path)
        with mock.patch.object(privacidad, "_detectar_caras", side_effect=failure):
            _assert_review(client.get("/media/C-001/legacy.png"))
        assert _snapshot(tmp_path) == before


@pytest.mark.parametrize("evidence", ["legacy", "stale", "empty", "invalid", "unknown", "unreadable"])
def test_sidecar_never_upgrades_rectangles_or_bad_evidence_to_blur(tmp_path, evidence):
    with TestClient(create_app(workspace_dir=tmp_path, sembrar=False)) as client:
        path = tmp_path / "C-001" / "inputs" / "photo.jpg"
        path.parent.mkdir(parents=True)
        cv2.imwrite(str(path), _image())
        data = {"politica": 3, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "regiones": HEADS}
        if evidence == "legacy":
            data["politica"] = 2
        elif evidence == "stale":
            data["sha256"] = "0" * 64
        elif evidence == "empty":
            data["regiones"] = []
        elif evidence == "invalid":
            data["regiones"] = [[-1, 0, 20, 20]]
        elif evidence == "unknown":
            data["politica"] = 99
        path.with_name(path.name + ".privacidad.json").write_text("broken" if evidence == "unreadable" else json.dumps(data))
        before = _snapshot(tmp_path)
        with mock.patch.object(privacidad, "_detectar_caras", return_value=HEADS), \
             mock.patch.object(privacidad, "_detectar_personas", return_value=[]):
            _assert_review(client.get("/media/C-001/photo.jpg"))
        assert before == _snapshot(tmp_path)


def test_upload_blur_evidence_survives_missing_detectors_and_preserves_source(tmp_path):
    from tests.test_vision import _resultado
    image = np.full((720, 1280, 3), 190, np.uint8)
    image[:200, :240] = _image()
    encoded = cv2.imencode(".jpg", image)[1].tobytes()
    with TestClient(create_app(workspace_dir=tmp_path, sembrar=False)) as client, \
         mock.patch.object(privacidad, "_detectar_caras", return_value=HEADS), \
         mock.patch.object(privacidad, "_detectar_personas", return_value=[]), \
         mock.patch.object(estimador, "estado", return_value=(True, "mock")), \
         mock.patch.object(estimador, "analizar", side_effect=_resultado):
        response = client.post("/casos", data={"datos": json.dumps({"usuario": "Ergonomia", "estacion": "Prueba"})},
                               files={"lateral": ("synthetic.jpg", encoded, "image/jpeg")})
        assert response.status_code == 200, response.text
        case_id = response.json()["id"]
        url = client.get("/casos/" + case_id).json()["imagenes"][0]["url"]
        path = tmp_path / case_id / "inputs" / "lateral.jpg"
        data = json.loads(path.with_name(path.name + ".privacidad.json").read_text())
        assert data["politica"] == 3
        assert data["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
        assert data["regiones"] == [list(h) for h in HEADS]
        before = _snapshot(tmp_path)
        with mock.patch.object(privacidad, "_detectar_caras", side_effect=RuntimeError("unavailable")):
            served = client.get(url)
        assert served.status_code == 200
        assert served.headers["cache-control"] == "no-store"
        decoded = cv2.imdecode(np.frombuffer(served.content, np.uint8), cv2.IMREAD_COLOR)
        assert decoded.shape == image.shape
        assert np.array_equal(decoded[300:], image[300:])
        assert decoded[25:45, 30:50].min() > 0
        assert before == _snapshot(tmp_path)
        assert cv2.imdecode(np.frombuffer(encoded, np.uint8), cv2.IMREAD_COLOR)[25:45, 30:50].std() > 50


def test_legacy_original_is_blurred_on_read_only(tmp_path):
    with TestClient(create_app(workspace_dir=tmp_path, sembrar=False)) as client:
        path = tmp_path / "C-001" / "inputs" / "legacy.png"
        path.parent.mkdir(parents=True)
        image = _image()
        cv2.imwrite(str(path), image)
        before = _snapshot(tmp_path)
        with mock.patch.object(privacidad, "_detectar_caras", return_value=HEADS), \
             mock.patch.object(privacidad, "_detectar_personas", return_value=[]):
            response = client.get("/media/C-001/legacy.png")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        decoded = cv2.imdecode(np.frombuffer(response.content, np.uint8), cv2.IMREAD_COLOR)
        assert decoded.shape == image.shape
        assert decoded[25:45, 30:50].std() < image[25:45, 30:50].std() / 4
        assert np.array_equal(decoded[100:], image[100:])
        assert before == _snapshot(tmp_path)


@pytest.mark.parametrize("mode", ["flat", "no_pose", "low_face", "multiple"])
def test_estimator_keeps_uncertain_pixels_closed_internally(mode):
    image = np.full((160, 240, 3), 180, np.uint8)
    if mode != "flat":
        image[::2] = 60
    original = image.copy()
    estimator = EstimadorPose()
    count = 2 if mode == "multiple" else 1
    estimator._detector = lambda image: np.array([[10, 10, 100, 150], [130, 10, 230, 150]][:count]) if mode != "no_pose" else []
    points = np.full((count, 133, 2), 30.)
    scores = np.full((count, 133), .9 if mode not in ("low_face", "no_pose") else 0.)
    estimator._pose = lambda image, bboxes: (points, scores)
    with mock.patch.object(privacidad, "_detectar_caras", return_value=[]):
        result = estimator.analizar(image)
    assert result.rostro_anonimizado
    assert not result.imagen_bgr.any()
    assert result.regiones_privacidad == []
    assert np.array_equal(image, original)
    if mode == "no_pose":
        assert result.personas == 0 and result.puntos == []
    if mode == "multiple":
        assert result.personas == 2


def test_estimator_reuses_all_person_boxes_and_keeps_geometry():
    image = _image()
    boxes = np.array([[10, 5, 100, 190], [140, 5, 230, 190]])
    points = np.full((2, 133, 2), 30.)
    for person, offset in enumerate((0, 140)):
        points[person, 5] = (50 + offset, 60)
        points[person, 7] = (60 + offset, 90)
        points[person, 9] = (70 + offset, 120)
    scores = np.ones((2, 133))
    estimator = EstimadorPose()
    estimator._detector = mock.Mock(return_value=boxes)
    estimator._pose = mock.Mock(return_value=(points, scores))
    with mock.patch.object(privacidad, "_detectar_caras", return_value=HEADS), \
         mock.patch.object(privacidad, "_detectar_personas", side_effect=AssertionError("Reuse boxes")):
        result = estimator.analizar(image)
    estimator._detector.assert_called_once()
    assert result.personas == 2
    assert result.imagen_bgr.shape == image.shape
    assert np.array_equal(result.imagen_bgr[100:], image[100:])
    assert result.puntos == []
    assert [pose.id for pose in result.poses] == ["persona-1", "persona-2"]
    assert [[p.id for p in pose.puntos] for pose in result.poses] == [[5, 7, 9], [5, 7, 9]]
    assert result.poses[1].puntos[0].x == 190
    assert result.imagen_bgr[25:45, 30:50].min() > 0


def test_optional_failure_is_withheld_and_bad_upload_is_atomic(tmp_path):
    from tests.test_vision import _resultado
    image = np.full((720, 1280, 3), 190, np.uint8)
    encoded = cv2.imencode(".jpg", image)[1].tobytes()
    payload = {"usuario": "Ergonomia", "rol": "ergonomia", "estacion": "Prueba"}
    with TestClient(create_app(workspace_dir=tmp_path, sembrar=False)) as client, \
         mock.patch.object(privacidad, "_detectar_caras", return_value=[]), \
         mock.patch.object(privacidad, "_detectar_personas", return_value=[]), \
         mock.patch.object(estimador, "estado", return_value=(True, "mock")), \
         mock.patch.object(estimador, "analizar", side_effect=[_resultado(image), ResultadoFoto(image.copy(), 0)]):
        response = client.post("/casos", data={"datos": json.dumps(payload)}, files={
            view: ("test.jpg", encoded, "image/jpeg") for view in ("lateral", "frontal")})
        assert response.status_code == 200, response.text
        detail = client.get("/casos/" + response.json()["id"]).json()
        before = _snapshot(tmp_path)
        for entry in detail["imagenes"]:
            _assert_review(client.get(entry["url"]))
        assert any("revisión" in h["mensaje"].lower() for h in detail["hallazgos"])
        bad = client.post("/casos", data={"datos": json.dumps(payload)}, files={"lateral": ("bad.jpg", b"bad", "image/jpeg")})
        assert bad.status_code == 422
        assert bad.json() == {"detail": "La foto lateral no es una imagen JPG o PNG válida"}
        assert before == _snapshot(tmp_path)
        inputs = tmp_path / response.json()["id"] / "inputs"
        (inputs / "unsafe.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
        assert client.get(f"/media/{response.json()['id']}/unsafe.svg").status_code == 422
        assert client.get(f"/media/{response.json()['id']}/missing.jpg").status_code == 404
