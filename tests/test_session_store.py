"""
Suite de Pruebas Unitarias para el Módulo File-System Session & Audit Store.
Valida la integridad criptográfica, atomicidad y cumplimiento de la restricción Cero Base de Datos.
"""

import json
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

from backend.app.session_store import (
    AuditActionEnum,
    AuditEvent,
    AuditFileManager,
    AuditIntegrityError,
    AuditTrailDocument,
    ControlHierarchyEnum,
    NormativeConfigLoader,
    RecommendationSnapshot,
    SessionStateDocument,
    SessionStatusEnum,
)


class TestSessionStore(unittest.TestCase):

    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="ergoai_test_ws_"))
        self.mgr = AuditFileManager(workspace_root=self.test_dir)

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_zero_database_dependency(self):
        """Verifica que el módulo no importe ni dependa de drivers de base de datos."""
        forbidden_modules = ["sqlite3", "sqlalchemy", "psycopg2", "mysql", "pymongo", "redis"]
        for mod in forbidden_modules:
            self.assertNotIn(
                mod,
                sys.modules,
                f"Violación de regla: el módulo '{mod}' está cargado en el entorno de ejecución."
            )

    def test_init_case_workspace(self):
        """Valida que la inicialización del caso cree la jerarquía de carpetas y archivos base."""
        case_id = "caso_01_levantamiento"
        case_dir = self.mgr.init_case_workspace(case_id)

        self.assertTrue(case_dir.exists())
        self.assertTrue((case_dir / "inputs").exists())
        self.assertTrue((case_dir / "outputs").exists())
        self.assertTrue((case_dir / "audit_trail.json").exists())
        self.assertTrue((case_dir / "session_state.json").exists())

        doc = self.mgr.load_audit_trail(case_id)
        self.assertEqual(doc.case_id, case_id)
        self.assertEqual(len(doc.events), 0)

        state = self.mgr.load_session_state(case_id)
        self.assertEqual(state.case_id, case_id)
        self.assertEqual(state.status, SessionStatusEnum.PENDING_ANALYSIS)

    def test_audit_event_hash_chaining(self):
        """Valida que múltiples eventos encadenen correctamente sus hashes SHA-256."""
        case_id = "caso_02_transporte"
        self.mgr.init_case_workspace(case_id)

        rec_ai = RecommendationSnapshot(
            recommendation_id="REC-01",
            hierarchy=ControlHierarchyEnum.INGENIERIA,
            description="Reubicar materiales de Zona 4 a Zona 1 (250 mm)",
            projected_reba=3
        )

        event_1 = self.mgr.append_audit_event(
            case_id=case_id,
            event_id="EVT-001",
            specialist_id="ING_EHS_LUIS",
            action=AuditActionEnum.APPROVED,
            target_recommendation_id="REC-01",
            original_ai_recommendation=rec_ai,
            initial_risk_score=11,
            residual_risk_score=3,
        )

        self.assertEqual(event_1.previous_event_hash, "0" * 64)
        self.assertTrue(len(event_1.event_hash) == 64)

        rec_human_edit = RecommendationSnapshot(
            recommendation_id="REC-02",
            hierarchy=ControlHierarchyEnum.INGENIERIA,
            description="Añadir asistencia mecánica tipo lifter por superar 14 kg",
            projected_reba=2,
            justification="Límite corporativo Jabil Chihuahua 14 kg"
        )

        event_2 = self.mgr.append_audit_event(
            case_id=case_id,
            event_id="EVT-002",
            specialist_id="ING_EHS_LUIS",
            action=AuditActionEnum.EDITED,
            target_recommendation_id="REC-02",
            original_ai_recommendation=rec_ai,
            human_edited_recommendation=rec_human_edit,
            initial_risk_score=11,
            residual_risk_score=2,
        )

        self.assertEqual(event_2.previous_event_hash, event_1.event_hash)

        is_valid, err = self.mgr.verify_case_audit_integrity(case_id)
        self.assertTrue(is_valid, f"Fallo de integridad: {err}")

    def test_tampering_detection(self):
        """Simula una alteración manual maliciosa del archivo JSON y verifica que sea detectada."""
        case_id = "caso_03_tamper"
        self.mgr.init_case_workspace(case_id)

        rec_ai = RecommendationSnapshot(
            recommendation_id="REC-01",
            hierarchy=ControlHierarchyEnum.INGENIERIA,
            description="Instalar tapete antifatiga y reposapiés a 25 cm",
            projected_reba=4
        )

        self.mgr.append_audit_event(
            case_id=case_id,
            event_id="EVT-001",
            specialist_id="ING_JUAN",
            action=AuditActionEnum.APPROVED,
            target_recommendation_id="REC-01",
            original_ai_recommendation=rec_ai,
            initial_risk_score=8,
            residual_risk_score=4,
        )

        # Alteración directa en el archivo físico (cambiar un número en el score)
        audit_file = self.mgr.get_case_dir(case_id) / "audit_trail.json"
        with open(audit_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        data["events"][0]["residual_risk_score"] = 1  # Modificación no autorizada

        with open(audit_file, "w", encoding="utf-8") as f:
            json.dump(data, f)

        # La verificación debe fallar obligatoriamente
        is_valid, error_msg = self.mgr.verify_case_audit_integrity(case_id)
        self.assertFalse(is_valid)
        self.assertIn("Hash inválido o alteración detectada", str(error_msg))

        with self.assertRaises(AuditIntegrityError):
            self.mgr.load_audit_trail(case_id, verify=True)

    def test_session_state_lifecycle(self):
        """Verifica que el snapshot de sesión se persista y actualice correctamente."""
        case_id = "caso_04_state"
        self.mgr.init_case_workspace(case_id)

        state = self.mgr.load_session_state(case_id)
        state.status = SessionStatusEnum.IN_REVIEW
        state.measured_angles = {"cuello_flexion": 24.5, "tronco_flexion": 48.0}
        state.reba_initial_score = 11
        state.reba_initial_risk_level = "Muy Alto"
        state.nom036_alerts = ["Carga excede límite de 14 kg Jabil CUU"]
        state.specialist_id = "ING_CARLOS"
        state.is_validated_by_human = True

        self.mgr.save_session_state(case_id, state)

        reloaded = self.mgr.load_session_state(case_id)
        self.assertEqual(reloaded.status, SessionStatusEnum.IN_REVIEW)
        self.assertEqual(reloaded.measured_angles["cuello_flexion"], 24.5)
        self.assertEqual(reloaded.reba_initial_score, 11)
        self.assertTrue(reloaded.is_validated_by_human)

    def test_genesis_no_es_campo_serializado(self):
        """El bloque génesis es constante del esquema; un archivo no puede redefinirlo."""
        doc = AuditTrailDocument(case_id="x")
        self.assertNotIn("GENESIS_HASH", doc.model_dump())
        alterado = AuditTrailDocument.model_validate({"case_id": "x", "GENESIS_HASH": "f" * 64})
        self.assertEqual(alterado.get_latest_hash(), "0" * 64)

    def test_event_id_duplicado(self):
        case_id = "caso_dup"
        self.mgr.init_case_workspace(case_id)
        rec = RecommendationSnapshot(recommendation_id="R1", hierarchy=ControlHierarchyEnum.INGENIERIA,
                                     description="Ajuste de mesa")
        kwargs = dict(case_id=case_id, event_id="EVT-1", specialist_id="ING_X", action=AuditActionEnum.APPROVED,
                      target_recommendation_id="R1", original_ai_recommendation=rec,
                      initial_risk_score=8, residual_risk_score=3)
        self.mgr.append_audit_event(**kwargs)
        with self.assertRaises(ValueError):
            self.mgr.append_audit_event(**kwargs)

    def test_case_id_no_permite_salir_del_workspace(self):
        for malo in ("../fuera", "a/b", "..", "", "c:\\x"):
            with self.assertRaises(ValueError, msg=malo):
                self.mgr.get_case_dir(malo)

    def test_escritura_atomica_no_deja_temporales_si_falla(self):
        destino = self.test_dir / "x.json"
        with self.assertRaises(TypeError):
            self.mgr.write_json_atomic(destino, {"no_serializable": object()})
        self.assertEqual(list(self.test_dir.iterdir()), [])

    def test_performance_latency(self):
        """Mide la latencia de guardado de un evento (objetivo típico 1–3 ms; límite holgado por fsync)."""
        case_id = "caso_05_perf"
        self.mgr.init_case_workspace(case_id)

        rec = RecommendationSnapshot(
            recommendation_id="REC-01",
            hierarchy=ControlHierarchyEnum.INGENIERIA,
            description="Ajuste de mesa",
            projected_reba=3
        )

        start = time.perf_counter()
        self.mgr.append_audit_event(
            case_id=case_id,
            event_id="EVT-PERF",
            specialist_id="PERF_TESTER",
            action=AuditActionEnum.APPROVED,
            target_recommendation_id="REC-01",
            original_ai_recommendation=rec,
            initial_risk_score=8,
            residual_risk_score=3
        )
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        # Debe ser inferior a 15 ms en entorno local (típicamente 1-3 ms)
        self.assertLess(elapsed_ms, 15.0, f"Latencia excesiva: {elapsed_ms:.2f} ms")

    def test_normative_config_loader(self):
        """Valida la carga inmutable de catálogos normativos."""
        loader = NormativeConfigLoader()
        loader.validate_all()

        jabil = loader.get_jabil_standards()
        self.assertEqual(jabil["load_limits"]["max_single_person_lift_kg"], 14.0)

        reba = loader.get_reba_tables()
        self.assertEqual(len(reba["table_c_matrix"]), 12)

        nom = loader.get_nom036_tables()
        self.assertIn("VERDE", nom["risk_bands"])


if __name__ == "__main__":
    unittest.main()
