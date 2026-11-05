"""Tests de integración para el pipeline de visión y evaluación multi-persona de ErgoAI."""

import unittest
import sys
from pathlib import Path
import cv2

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

try:
    import rtmlib
    from ergoai.services.vision_pipeline import ErgoAIVisionPipeline
    from ergoai.config import SETTINGS
    from ergoai.domain.constants import JABIL_MIN_INTER_OPERATOR_DISTANCE_CM
    HAS_RTMLIB = True
except ImportError:
    HAS_RTMLIB = False

from ergoai.domain.models.simulation import EngineeringControlID


@unittest.skipUnless(HAS_RTMLIB, "Requiere rtmlib (disponible en venv con stack de visión)")
class TestVisionPipeline(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.pipeline = ErgoAIVisionPipeline()

    def test_pipeline_multi_person_scene(self):
        test_img_path = SETTINGS.dataset_dir / "01_sin_rostro" / "sr_01_recuadro_negro_operarioA.jpg"
        if not test_img_path.exists():
            self.skipTest("Dataset no encontrado en el entorno local.")

        img = cv2.imread(str(test_img_path))
        self.assertIsNotNone(img)

        result = self.pipeline.evaluate_multi_person_scene(
            lateral_img_bgr=img,
            frontal_img_bgr=img,
            load_kg=8.0,
            is_static=True,
        )

        # Debe detectar a las 2 personas en la imagen
        self.assertGreaterEqual(result.total_persons_detected, 2)
        self.assertGreaterEqual(len(result.persons), 2)

        for p in result.persons:
            # REBA 1 a 15
            self.assertTrue(1 <= p.reba["final_score"] <= 15)
            self.assertIn(p.reba["risk_level"], ("NEGLIGIBLE", "LOW", "MEDIUM", "HIGH", "VERY_HIGH"))
            # Ángulos calculados
            self.assertIn("trunk_angle", p.angles)
            self.assertIn("neck_angle", p.angles)
            self.assertIn("leg_knee_angle", p.angles)

        # Métrica F2 de distancia inter-operador
        self.assertGreaterEqual(result.multi_person_metrics["num_operators"], 2)
        f2 = result.multi_person_metrics["inter_operator_distance_f2"]
        self.assertIsNotNone(f2)
        self.assertGreater(f2["distance_cm"], 0)
        self.assertIn(f2["status"], ("CONFORME", f"NO CONFORME (< {JABIL_MIN_INTER_OPERATOR_DISTANCE_CM:.0f} cm)"))

    def test_pipeline_residual_risk_simulation(self):
        angles = {
            "active_side": "right",
            "trunk_angle": 35.0,
            "neck_angle": 25.0,
            "leg_knee_angle": 10.0,
            "upper_arm_angle": 55.0,
            "lower_arm_angle": 110.0,
            "wrist_angle": 20.0,
        }
        res = self.pipeline.simulate_residual_risk(
            original_angles=angles,
            original_load_kg=16.0,
            selected_controls=[
                EngineeringControlID.B1_LIFTER,
                EngineeringControlID.E1_RELOCATE_ZONE,
                EngineeringControlID.F1_HEIGHT_ADJUST,
            ],
            is_static=False,
        )

        self.assertLessEqual(res["residual_reba_score"], 3)
        self.assertIn(res["residual_risk_level"], ("NEGLIGIBLE", "LOW"))

    def test_vision_config_pydantic_schema_injection(self):
        """Valida que los esquemas de configuración se inyecten desde JSON mediante Pydantic sin hardcode."""
        from ergoai.config.vision_schema import VisionConfigSchema
        cfg = VisionConfigSchema.load_from_json()
        self.assertIsNotNone(cfg)
        self.assertTrue(0.0 < cfg.confidence_thresholds.yolox_score_thr < 1.0)
        self.assertTrue(0.0 < cfg.confidence_thresholds.yolox_nms_thr < 1.0)
        self.assertIn("VERDE", cfg.visualization_rules.reba_color_map)
        self.assertIn("ROJO", cfg.visualization_rules.reba_color_map)
        self.assertEqual(len(cfg.joint_mapping.left_chain), 8)
        self.assertEqual(len(cfg.joint_mapping.right_chain), 8)


if __name__ == "__main__":
    unittest.main()
