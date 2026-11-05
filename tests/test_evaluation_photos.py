"""Pruebas exhaustivas para verificar que se puedan hacer los cálculos ergonómicos
a cada una de las fotografías de evaluación del dataset oficial de Jabil (12 fotos)
y a cada uno de los 6 casos oficiales de benchmark (Criterios 1, 2, 3 y 7).
"""

import glob
import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from ergoai.config import SETTINGS
from ergoai.web.server import app
from ergoai.services.vision_pipeline import ErgoAIVisionPipeline
from ergoai.domain.benchmarks import get_official_jabil_cases
from ergoai.services.scene_classifier import TaskAndSceneUnderstandingService


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def pipeline():
    return ErgoAIVisionPipeline()


def test_all_12_evaluation_photos_exist_and_calculate_successfully(pipeline):
    """Verifica que cada una de las 12 fotos del dataset oficial se analice correctamente con RTMPose WholeBody-133."""
    all_jpgs = sorted(glob.glob(str(SETTINGS.dataset_dir / "**" / "*.jpg"), recursive=True))
    assert len(all_jpgs) == 12, f"Se esperaban 12 fotografías en el dataset oficial, encontradas {len(all_jpgs)}"

    for path_str in all_jpgs:
        p = Path(path_str)
        import cv2
        img = cv2.imread(path_str)
        assert img is not None, f"No se pudo leer la imagen {p.name}"

        # Analizar con el servicio de entendimiento de escena
        analysis = TaskAndSceneUnderstandingService.analyze_single_image(
            image_bgr=img,
            pipeline=pipeline,
        )

        assert analysis is not None
        assert analysis.evaluation is not None
        persons = analysis.evaluation.get("persons", [])
        assert len(persons) >= 1, f"Fallo al detectar operario en {p.name}"

        p0 = persons[0]
        # Verificar extracción de 133 puntos y ángulos
        assert "angles" in p0
        angles = p0["angles"]
        assert "trunk_angle" in angles
        assert "upper_arm_angle" in angles
        assert "neck_angle" in angles
        assert "wrist_angle" in angles

        # Verificar cálculo REBA
        assert "reba" in p0
        reba = p0["reba"]
        assert 1 <= reba["final_score"] <= 15
        assert reba["risk_level"] in ["NEGLIGIBLE", "LOW", "MEDIUM", "HIGH", "VERY_HIGH"]

        # Verificar riesgo residual
        assert "residual_risk" in analysis.model_dump()
        assert analysis.residual_risk.get("residual_reba_score") is not None


def test_api_analyze_sample_image_endpoint_for_all_photos(client):
    """Verifica que el endpoint /api/analyze_sample_image procese con HTTP 200 cada una de las fotos."""
    all_jpgs = sorted(glob.glob(str(SETTINGS.dataset_dir / "**" / "*.jpg"), recursive=True))

    for path_str in all_jpgs:
        fname = Path(path_str).name
        response = client.post("/api/analyze_sample_image", data={"filename": fname})
        assert response.status_code == 200, f"Error en endpoint para {fname}: {response.text}"
        data = response.json()
        assert data.get("status") == "success"
        assert "evaluation" in data
        assert len(data["evaluation"].get("persons", [])) >= 1
        assert "annotated_images_b64" in data["evaluation"]


def test_api_load_sample_case_for_all_6_cases(client):
    """Verifica que el endpoint /api/load_sample procese con HTTP 200 los 6 casos oficiales de benchmark."""
    cases = get_official_jabil_cases()
    assert len(cases) == 6

    for c in cases:
        response = client.post("/api/load_sample", data={"case_id": c.case_id})
        assert response.status_code == 200, f"Error al cargar caso {c.case_id}: {response.text}"
        data = response.json()
        assert data.get("status") == "success"
        assert data.get("matched_case_id") == c.case_id
        assert len(data["evaluation"].get("persons", [])) >= 1
        assert data["evaluation"]["persons"][0]["reba"]["final_score"] >= 1


def test_analyze_correct_posture_evaluation(client):
    """Verifica la capacidad del sistema de reconocer, evaluar y certificar posturas ergonómicamente correctas."""
    # 1. Probar carga de caso de referencia de postura correcta
    response = client.post("/api/load_sample", data={"case_id": "caso_postura_correcta_conforme"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "Correcta" in data["task_type"] or "Conforme" in data["task_type"]

    p0 = data["evaluation"]["persons"][0]
    # REBA debe ser 1 (NEGLIGIBLE) o bajo (<= 2)
    assert p0["reba"]["final_score"] <= 2
    assert p0["reba"]["risk_level"] in ["NEGLIGIBLE", "LOW"]
    assert p0["reba"]["color_code"] in ["VERDE", "AMARILLO"]

    # Ángulos deben estar en rangos neutros de confort
    angles = p0["angles"]
    assert angles["trunk_angle"] <= 20.0
    assert angles["upper_arm_angle"] <= 30.0

    # Riesgo residual debe reflejar condición óptima
    res_risk = data["residual_risk"]
    assert res_risk["residual_reba_score"] == 1
    assert res_risk["is_goal_met"] is True

    # 2. Probar imagen individual de postura correcta
    resp_img = client.post("/api/analyze_sample_image", data={"filename": "sr_03_recorte_hombros_operarioC.jpg"})
    assert resp_img.status_code == 200
    d_img = resp_img.json()
    assert d_img["evaluation"]["persons"][0]["reba"]["final_score"] <= 2
    assert any("✅" in anom or "Conforme" in anom for anom in d_img["detected_anomalies"])

