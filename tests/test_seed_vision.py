"""Seed geometry must belong to its actual image, never a different template."""
import json
import tempfile
from pathlib import Path
from unittest import mock

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.app.settings import SEED_DIR
from backend.app.vision.estimador import estimador, PuntoDetectado, ResultadoFoto, VisionNoDisponible
from backend.main import create_app


@pytest.fixture
def tmp_path():
    with tempfile.TemporaryDirectory(prefix="ergoai_seed_vision_") as directory:
        yield Path(directory)


@pytest.mark.parametrize("available", [False, True])
def test_seed_real_photo_dimensions_points_and_privacy(tmp_path, available):
    seed = tmp_path / "seed"
    seed.mkdir()
    data = json.loads((SEED_DIR / "casos_demo.json").read_text(encoding="utf-8"))
    data["casos"] = [data["casos"][0]]
    data["casos"][0]["fotos"] = {v: "synthetic.jpg" for v in ("lateral", "frontal", "cenital")}
    # A synthetic local stand-in with the reported portrait dimensions.
    cv2.imwrite(str(seed / "synthetic.jpg"), np.full((640, 480, 3), 190, np.uint8))
    (seed / "placeholder.svg").write_bytes((SEED_DIR / "placeholder.svg").read_bytes())
    path = seed / "casos_demo.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    points = [PuntoDetectado(5, 123., 234., .9)]
    with mock.patch.object(estimador, "analizar", side_effect=(lambda image: ResultadoFoto(image.copy(), 1, points)) if available else VisionNoDisponible("missing")), \
         TestClient(create_app(workspace_dir=tmp_path / "ws", sembrar=False)) as client:
        assert client.app.state.servicio.sembrar_si_vacio(path) == 1
        detail = client.get("/casos/C-001").json()
        for entry in detail["imagenes"]:
            assert (entry["ancho"], entry["alto"]) == (480, 640)
            assert entry["puntos"] == ([{"id": 5, "x": 123., "y": 234., "confianza": .9, "corregido": False}] if available else [])
            response = client.get(entry["url"])
            assert response.status_code == 200
            decoded = cv2.imdecode(np.frombuffer(response.content, np.uint8), cv2.IMREAD_COLOR)
            assert decoded.shape == (640, 480, 3)
            assert not decoded.any()
            stored = cv2.imread(str(tmp_path / "ws" / "C-001" / "inputs" / "synthetic.jpg"))
            assert not stored.any()
        if not available:
            assert any("revis" in h["mensaje"].lower() for h in detail["hallazgos"])
        assert client.app.state.servicio.sembrar_si_vacio(path) == 0
        assert client.get("/bitacora/verificar").json()["ok"]
        # Source photo is never rewritten by seeding or serving.
        assert cv2.imread(str(seed / "synthetic.jpg")).min() == 190


def test_missing_seed_photo_uses_only_its_own_generated_template(tmp_path):
    data = json.loads((SEED_DIR / "casos_demo.json").read_text(encoding="utf-8"))
    data["casos"] = [data["casos"][0]]
    data["casos"][0]["fotos"] = {}
    path = tmp_path / "seed.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with mock.patch.object(estimador, "analizar") as infer, \
         TestClient(create_app(workspace_dir=tmp_path / "ws", sembrar=False)) as client:
        assert client.app.state.servicio.sembrar_si_vacio(path) == 1
        infer.assert_not_called()
        detail = client.get("/casos/C-001").json()
        for entry in detail["imagenes"]:
            assert entry["url"].endswith(f"plantilla-{entry['vista']}.png")
            template = data["casos"][0]["esqueletos"][entry["vista"]]
            assert (entry["ancho"], entry["alto"]) == (template["ancho"], template["alto"])
            assert [(p["id"], p["x"], p["y"], p["confianza"]) for p in entry["puntos"]] == [tuple(p) for p in template["puntos"]]
            stored = cv2.imread(str(tmp_path / "ws" / "C-001" / "inputs" / f"plantilla-{entry['vista']}.png"))
            for point in entry["puntos"]:
                assert (stored[round(point["y"]), round(point["x"])] == 80).all()
        assert any("sintética" in h["mensaje"] for h in detail["hallazgos"])


@pytest.mark.parametrize("media_state", ["mismatch", "missing", "undecodable", "missing_decoder"])
def test_legacy_mismatched_geometry_is_untrusted_without_rewriting_records(tmp_path, media_state):
    from tests.test_vision import _resultado
    with mock.patch.object(estimador, "estado", return_value=(True, "mock")), \
         mock.patch.object(estimador, "analizar", side_effect=_resultado), \
         TestClient(create_app(workspace_dir=tmp_path, sembrar=False)) as client:
        encoded = cv2.imencode(".jpg", np.full((720, 1280, 3), 190, np.uint8))[1].tobytes()
        response = client.post("/casos", data={"datos": json.dumps({"usuario": "Ergonomia", "estacion": "Legacy"})},
                               files={"lateral": ("test.jpg", encoded, "image/jpeg")})
        assert response.status_code == 200, response.text
        case_id = response.json()["id"]
        image_path = tmp_path / case_id / "inputs" / "lateral.jpg"
        if media_state == "mismatch":
            cv2.imwrite(str(image_path), np.full((640, 480, 3), 190, np.uint8))
        elif media_state == "missing":
            # Move inside this disposable fixture to simulate unavailable legacy media.
            image_path.rename(image_path.with_suffix(".unavailable"))
        elif media_state == "undecodable":
            image_path.write_bytes(b"not an image")
        records = {str(p): p.read_bytes() for p in tmp_path.rglob("*.json")}
        with mock.patch.dict("sys.modules", {"cv2": None}) if media_state == "missing_decoder" else mock.patch.dict("sys.modules", {}):
            response = client.get("/casos/" + case_id)
        assert response.status_code == 200, response.text
        detail = response.json()
        entry = detail["imagenes"][0]
        assert (entry["ancho"], entry["alto"]) == ((480, 640) if media_state == "mismatch" else (1280, 720))
        assert entry["puntos"] == []
        assert any("geometría" in h["mensaje"].lower() for h in detail["hallazgos"])
        assert records == {str(p): p.read_bytes() for p in tmp_path.rglob("*.json")}
