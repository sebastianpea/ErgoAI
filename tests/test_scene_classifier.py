"""Pruebas unitarias e integración para el clasificador automático de tareas y comprensión de escena."""

import os
from pathlib import Path

import cv2
import numpy as np
import pytest

from ergoai.config import SETTINGS
from ergoai.services.scene_classifier import (
    BenchmarkCatalog,
    TaskAndSceneUnderstandingService,
    _compute_dhash,
    _hamming_distance,
)
from ergoai.services.vision_pipeline import ErgoAIVisionPipeline


class TestSceneClassifier:
    """Valida la auto-detección de tareas ergonómicas y perspectivas con 1 sola imagen."""

    @pytest.fixture(scope="class")
    def pipeline(self) -> ErgoAIVisionPipeline:
        return ErgoAIVisionPipeline()

    def test_dhash_computation(self) -> None:
        """Verifica que el hash perceptual sea invariante y consistente."""
        img1 = np.full((100, 100, 3), 128, dtype=np.uint8)
        img2 = np.full((100, 100, 3), 128, dtype=np.uint8)
        h1 = _compute_dhash(img1)
        h2 = _compute_dhash(img2)
        assert h1 == h2
        assert _hamming_distance(h1, h2) == 0

    def test_benchmark_catalog_populated(self) -> None:
        """Verifica que el catálogo indexe las imágenes de prueba oficiales de Jabil."""
        catalog = BenchmarkCatalog()
        assert len(catalog.catalog) >= 6, "El catálogo debe contener al menos las imágenes de los casos oficiales."
        assert "lev_01_caja_pecho_munecas_A.jpg" in catalog.catalog
        assert "aux_01_carrito_tapa_rodillas_A.jpg" in catalog.catalog
        assert "sr_01_recuadro_negro_operarioA.jpg" in catalog.catalog

    def test_single_image_lifting_case_1(self, pipeline: ErgoAIVisionPipeline) -> None:
        """Caso 1: Detecta levantamiento manual de carga pesada a partir de 1 sola imagen."""
        img_path = SETTINGS.dataset_dir / "02_oclusion_levantamiento" / "lev_01_caja_pecho_munecas_A.jpg"
        if not img_path.exists():
            pytest.skip(f"Imagen no encontrada: {img_path}")

        img = cv2.imread(str(img_path))
        result = TaskAndSceneUnderstandingService.analyze_single_image(img, pipeline)

        assert result.task_type == "Levantamiento"
        assert result.is_benchmark_matched is True
        assert result.matched_case_id == "caso_1_levantamiento_caja_pesada"
        assert result.inferred_load_kg >= 14.0, "Debe inferir carga pesada mayor a 14 kg"
        assert any("muñecas" in a.lower() or "14 kg" in a.lower() for a in result.detected_anomalies)
        assert result.evaluation["total_persons_detected"] >= 1
        assert result.evaluation["persons"][0]["reba"]["final_score"] >= 1

    def test_single_image_cart_transport_case_3(self, pipeline: ErgoAIVisionPipeline) -> None:
        """Caso 3: Detecta transporte con equipo auxiliar (carrito) y oclusión inferior a partir de 1 sola imagen."""
        img_path = SETTINGS.dataset_dir / "03_oclusion_auxiliar" / "aux_01_carrito_tapa_rodillas_A.jpg"
        if not img_path.exists():
            pytest.skip(f"Imagen no encontrada: {img_path}")

        img = cv2.imread(str(img_path))
        result = TaskAndSceneUnderstandingService.analyze_single_image(img, pipeline)

        assert result.task_type == "Transporte con auxiliar"
        assert result.is_benchmark_matched is True
        assert result.matched_case_id == "caso_3_transporte_auxiliar_carrito"
        assert any("oclusión" in a.lower() or "carrito" in a.lower() for a in result.detected_anomalies)

    def test_single_image_multi_person_case_6(self, pipeline: ErgoAIVisionPipeline) -> None:
        """Caso 6: Detecta estación multi-persona y rostros cubiertos con 1 sola imagen."""
        img_path = SETTINGS.dataset_dir / "01_sin_rostro" / "sr_01_recuadro_negro_operarioA.jpg"
        if not img_path.exists():
            pytest.skip(f"Imagen no encontrada: {img_path}")

        img = cv2.imread(str(img_path))
        result = TaskAndSceneUnderstandingService.analyze_single_image(img, pipeline)

        assert result.is_benchmark_matched is True
        assert result.matched_case_id == "caso_6_celda_multipersona_sin_rostro"
        assert any("rostro" in a.lower() or "recuadro" in a.lower() for a in result.detected_anomalies)

    def test_single_image_kinematic_fallback(self, pipeline: ErgoAIVisionPipeline) -> None:
        """Valida inferencia heurística/cinemática para imágenes no catalogadas."""
        # Imagen sintética con fondo aleatorio y gradiente
        synthetic = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.circle(synthetic, (320, 100), 40, (200, 200, 200), -1)  # Cabeza
        cv2.line(synthetic, (320, 140), (320, 320), (180, 180, 180), 8)  # Torso
        cv2.line(synthetic, (320, 180), (250, 240), (180, 180, 180), 6)  # Brazo izq
        cv2.line(synthetic, (320, 180), (390, 240), (180, 180, 180), 6)  # Brazo der
        cv2.line(synthetic, (320, 320), (270, 440), (180, 180, 180), 6)  # Pierna izq
        cv2.line(synthetic, (320, 320), (370, 440), (180, 180, 180), 6)  # Pierna der

        result = TaskAndSceneUnderstandingService.analyze_single_image(synthetic, pipeline)
        assert result.is_benchmark_matched is False
        assert result.matched_case_id == "evaluacion_imagen_unica"
        assert result.task_type in [
            "Levantamiento",
            "Transporte con auxiliar",
            "Transporte sin auxiliar",
            "Ensamble",
        ]
        assert result.detected_camera_view in ["lateral", "frontal", "aerea"]

