"""Pruebas de integración para la API REST de ErgoAI y análisis de imagen única."""

import io
from pathlib import Path

import cv2
import pytest
from fastapi.testclient import TestClient

from ergoai.config import SETTINGS
from ergoai.web.server import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def test_api_health(client: TestClient) -> None:
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "online"
    assert "RTMPose" in data["models"]["pose"]


def test_api_sample_cases(client: TestClient) -> None:
    """Valida que los casos de benchmark se devuelvan dinámicamente con todos sus metadatos."""
    resp = client.get("/api/sample_cases")
    assert resp.status_code == 200
    cases = resp.json()
    assert len(cases) == 6
    for c in cases:
        assert "id" in c
        assert "case_number" in c
        assert "title" in c
        assert "task_type" in c
        assert "description" in c


def test_api_load_sample(client: TestClient) -> None:
    """Valida la ejecución del análisis de un caso oficial tri-vista con formato unificado."""
    resp = client.post(
        "/api/load_sample",
        data={"case_id": "caso_1_levantamiento_caja_pesada"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["task_type"] == "Levantamiento"
    assert "evaluation" in data
    assert "residual_risk" in data
    assert "report_url" in data
    assert len(data["evaluation"]["persons"]) >= 1
    assert "annotated_images_b64" in data["evaluation"]


def test_api_single_image_samples(client: TestClient) -> None:
    resp = client.get("/api/single_image_samples")
    assert resp.status_code == 200
    samples = resp.json()
    assert len(samples) == 6
    case_ids = [s["case_id"] for s in samples]
    assert "caso_1_levantamiento_caja_pesada" in case_ids
    assert "caso_3_transporte_auxiliar_carrito" in case_ids
    assert "caso_6_celda_multipersona_sin_rostro" in case_ids


def test_api_analyze_sample_image(client: TestClient) -> None:
    """Valida la auto-clasificación de una imagen individual del dataset vía endpoint REST."""
    resp = client.post(
        "/api/analyze_sample_image",
        data={"filename": "lev_01_caja_pecho_munecas_A.jpg"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["task_type"] == "Levantamiento"
    assert data["is_benchmark_matched"] is True
    assert data["matched_case_id"] == "caso_1_levantamiento_caja_pesada"
    assert data["inferred_load_kg"] == 16.5
    assert len(data["evaluation"]["persons"]) >= 1


def test_api_analyze_single_image_upload(client: TestClient) -> None:
    """Valida la subida multipart de UNA SOLA IMAGEN y su clasificación automática."""
    img_path = SETTINGS.dataset_dir / "03_oclusion_auxiliar" / "aux_01_carrito_tapa_rodillas_A.jpg"
    if not img_path.exists():
        pytest.skip(f"No se encontró: {img_path}")

    with open(img_path, "rb") as f:
        file_bytes = f.read()

    resp = client.post(
        "/api/analyze_single_image",
        files={"image_file": ("aux_01_carrito_tapa_rodillas_A.jpg", file_bytes, "image/jpeg")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["task_type"] == "Transporte con auxiliar"
    assert data["detected_camera_view"] == "lateral"
    assert data["matched_case_id"] == "caso_3_transporte_auxiliar_carrito"
    assert any("carrito" in a.lower() or "oclusión" in a.lower() for a in data["detected_anomalies"])


def test_api_evaluate_triple_files(client: TestClient) -> None:
    """Valida la capacidad de enviar los 3 archivos (Lateral, Frontal, Aérea) simultáneamente."""
    lat_path = SETTINGS.dataset_dir / "02_oclusion_levantamiento" / "lev_03_caja_lateral_perfil_C.jpg"
    fro_path = SETTINGS.dataset_dir / "02_oclusion_levantamiento" / "lev_01_caja_pecho_munecas_A.jpg"
    aer_path = SETTINGS.dataset_dir / "04_perspectiva_cenital" / "cen_02_vista_cenital_oblicua_25deg.jpg"

    if not (lat_path.exists() and fro_path.exists() and aer_path.exists()):
        pytest.skip("No se encontraron las imágenes del dataset para prueba tri-vista")

    with open(lat_path, "rb") as f_lat, open(fro_path, "rb") as f_fro, open(aer_path, "rb") as f_aer:
        resp = client.post(
            "/api/evaluate",
            files={
                "lateral_file": ("lateral.jpg", f_lat.read(), "image/jpeg"),
                "frontal_file": ("frontal.jpg", f_fro.read(), "image/jpeg"),
                "aerea_file": ("aerea.jpg", f_aer.read(), "image/jpeg"),
            },
            data={"load_kg": 16.5},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["task_type"] in ["Levantamiento", "Transporte con auxiliar", "Transporte sin auxiliar"]
    assert "evaluation" in data
    assert "residual_risk" in data
    assert "report_url" in data
    # Comprobar que contiene las anotaciones de las 3 vistas
    b64 = data["evaluation"]["annotated_images_b64"]
    assert "lateral" in b64 and b64["lateral"] is not None
    assert "frontal" in b64 and b64["frontal"] is not None
    assert "aerea" in b64 and b64["aerea"] is not None


def test_api_evaluate_custom_unmatched_photo(client: TestClient) -> None:
    """Valida que subir una fotografía propia no catalogada se analice correctamente sin errores 500."""
    from unittest.mock import patch
    lat_path = SETTINGS.dataset_dir / "02_oclusion_levantamiento" / "lev_03_caja_lateral_perfil_C.jpg"
    if not lat_path.exists():
        pytest.skip(f"No se encontró: {lat_path}")

    with open(lat_path, "rb") as f_lat:
        file_bytes = f_lat.read()

    # Forzar match=None para simular una fotografía tomada en otra planta/celda
    with patch("ergoai.web.server.CATALOG.match_image", return_value=None):
        resp = client.post(
            "/api/evaluate",
            files={"lateral_file": ("custom_floor_operator.jpg", file_bytes, "image/jpeg")},
            data={"load_kg": 15.0},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["task_type"] in ["Levantamiento", "Transporte con auxiliar", "Transporte sin auxiliar"]
    assert "evaluation" in data
    assert "residual_risk" in data
    assert len(data["evaluation"]["persons"]) >= 1
    assert data["residual_risk"]["residual_reba_score"] is not None
