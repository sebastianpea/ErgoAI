"""Pruebas de integración de la API HTTP (FastAPI) sobre un workspace temporal."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import create_app

USUARIO = "Ing. Pruebas"


class TestApi(unittest.TestCase):
    def setUp(self):
        self.ws = Path(tempfile.mkdtemp(prefix="ergoai_api_"))
        self.cliente = TestClient(create_app(workspace_dir=self.ws))
        self.cliente.__enter__()

    def tearDown(self):
        self.cliente.__exit__(None, None, None)
        shutil.rmtree(self.ws, ignore_errors=True)

    def decidir(self, caso, rec, accion, **extra):
        cuerpo = {"id_caso": caso, "id_recomendacion": rec, "accion": accion, "usuario": USUARIO, **extra}
        return self.cliente.post(f"/casos/{caso}/recomendaciones/{rec}/decision", json=cuerpo)

    def test_listado_y_detalle(self):
        casos = self.cliente.get("/casos").json()
        self.assertEqual({c["id_caso"] for c in casos}, {f"C-{i:03d}" for i in range(1, 8)})
        d = self.cliente.get("/casos/C-001").json()
        self.assertEqual(len(d["angulos"]), 18)
        self.assertEqual({a["vista"] for a in d["angulos"]}, {"lateral", "frontal", "cenital"})
        self.assertEqual(d["nom036"]["total"], sum(f["valor"] for f in d["nom036"]["factores"]))
        self.assertTrue(any(h["origen"] == "reglas_jabil" for h in d["hallazgos"]))
        self.assertFalse(d["validacion"]["completa"])
        self.assertEqual(self.cliente.get(d["imagenes"][0]["url"]).status_code, 200)

    def test_caso_inexistente_y_traversal(self):
        self.assertEqual(self.cliente.get("/casos/NOPE").status_code, 404)
        self.assertEqual(self.cliente.get("/casos/..%2F..").status_code, 404)
        self.assertEqual(self.cliente.get("/media/C-001/caso.json").status_code, 404)

    def test_flujo_validacion_completo(self):
        self.assertEqual(self.decidir("C-001", "R1", "aprobar", responsable="IE L2", fecha_compromiso="2026-12-01").status_code, 200)
        self.assertEqual(self.decidir("C-001", "R1", "aprobar").status_code, 409)  # ya decidida
        self.assertEqual(self.decidir("C-001", "R2", "editar", texto_editado="Elevar a 105 cm con perfil Bosch",
                                      motivo="Ajuste existente").status_code, 200)
        self.assertEqual(self.decidir("C-001", "R3", "rechazar", motivo="No aplica").status_code, 200)
        self.assertEqual(self.decidir("C-001", "R4", "aprobar").status_code, 200)

        d = self.cliente.get("/casos/C-001").json()
        estados = {r["id"]: r["estado"] for r in d["recomendaciones"]}
        self.assertEqual(estados, {"R1": "aprobada", "R2": "editada_aprobada", "R3": "rechazada", "R4": "aprobada"})
        self.assertTrue(d["validacion"]["completa"])
        self.assertEqual(d["recomendaciones"][0]["responsable"], "IE L2")

        # Audit trail por caso con 3 eventos encadenados y session_state validado
        trail = json.loads((self.ws / "C-001" / "audit_trail.json").read_text(encoding="utf-8"))
        self.assertEqual([e["action"] for e in trail["events"]], ["APPROVED", "EDITED", "REJECTED", "APPROVED"])
        self.assertNotIn("GENESIS_HASH", trail)
        estado = json.loads((self.ws / "C-001" / "session_state.json").read_text(encoding="utf-8"))
        self.assertEqual(estado["status"], "VALIDATED")
        self.assertTrue(estado["is_validated_by_human"])

        # La alerta de riesgo alto pendiente se cierra sola
        alertas = {a["id_alerta"]: a for a in self.cliente.get("/alertas").json()}
        self.assertEqual(alertas["C-001-RIESGO_ALTO_PENDIENTE"]["estado"], "atendida")

        acciones = [e["accion"] for e in self.cliente.get("/bitacora?id_caso=C-001").json()]
        self.assertIn("recomendacion_editar", acciones)
        self.assertTrue(self.cliente.get("/bitacora/verificar").json()["ok"])

    def test_reglas_de_decision(self):
        self.assertEqual(self.decidir("C-001", "R3", "rechazar").status_code, 422)  # sin motivo
        self.assertEqual(self.decidir("C-001", "R2", "editar", texto_editado="", motivo="x").status_code, 422)
        self.assertEqual(self.decidir("C-001", "R9", "aprobar").status_code, 404)
        r = self.cliente.post("/casos/C-001/recomendaciones/R1/decision",
                              json={"id_caso": "C-002", "id_recomendacion": "R1", "accion": "aprobar", "usuario": USUARIO})
        self.assertEqual(r.status_code, 422)  # cuerpo no coincide con la ruta

    def test_alto_riesgo_requiere_ingenieria(self):
        for rec in ("R1", "R2"):
            self.decidir("C-001", rec, "rechazar", motivo="Prueba")
        self.decidir("C-001", "R3", "aprobar")
        self.decidir("C-001", "R4", "aprobar")
        v = self.cliente.get("/casos/C-001").json()["validacion"]
        self.assertEqual(v["pendientes"], 0)
        self.assertTrue(v["falta_ingenieria"])
        self.assertFalse(v["completa"])

    def test_correccion_de_puntos_recalcula(self):
        from unittest import mock
        from backend.app.vision.estimador import estimador
        from tests.test_vision import _foto_jpg, _resultado

        # Esta prueba mide edición y persistencia, no el resultado variable de ONNX.
        self.cliente.__exit__(None, None, None)
        self.cliente = TestClient(create_app(workspace_dir=self.ws / "correccion", sembrar=False))
        self.cliente.__enter__()
        with mock.patch.object(estimador, "estado", return_value=(True, "simulado")), \
             mock.patch.object(estimador, "analizar", side_effect=_resultado):
            creado = self.cliente.post("/casos", data={"datos": json.dumps({"usuario": USUARIO, "estacion": "Corrección"})},
                                       files={"lateral": ("lateral.jpg", _foto_jpg(), "image/jpeg")})
        self.assertEqual(creado.status_code, 200, creado.text)
        self.assertEqual(creado.json()["id"], "C-001")
        d = self.cliente.get("/casos/C-001").json()
        lateral = next(i for i in d["imagenes"] if i["vista"] == "lateral")
        puntos = lateral["puntos"]
        # Enderezar el tronco: hombro izquierdo (5) sobre la cadera (11)
        cadera = next(p for p in puntos if p["id"] == 11)
        for p in puntos:
            if p["id"] == 5:
                p["x"], p["y"] = cadera["x"], cadera["y"] - 200
        r = self.cliente.put("/casos/C-001/puntos/lateral", json={"puntos": puntos, "usuario": USUARIO})
        self.assertEqual(r.status_code, 200)
        nuevo = r.json()
        tronco = next(a for a in nuevo["angulos"] if a["segmento"] == "tronco")
        self.assertAlmostEqual(tronco["angulo_grados"], 0.0, places=1)
        previo = next(a for a in d["angulos"] if a["segmento"] == "tronco" and a["vista"] == "lateral")
        self.assertNotAlmostEqual(previo["angulo_grados"], tronco["angulo_grados"], places=1)
        # REBA es tabular: corregir un segmento no garantiza reducir el total.
        self.assertLessEqual(tronco["puntaje_reba"], previo["puntaje_reba"])
        persistido = self.cliente.get("/casos/C-001").json()
        self.assertEqual(persistido["angulos"], nuevo["angulos"])
        self.assertEqual(persistido["imagenes"], nuevo["imagenes"])
        p5 = next(p for p in next(i for i in nuevo["imagenes"] if i["vista"] == "lateral")["puntos"] if p["id"] == 5)
        self.assertTrue(p5["corregido"])
        entradas = self.cliente.get("/bitacora?id_caso=C-001").json()
        correccion = next(e for e in entradas if e["accion"] == "puntos_corregidos")
        self.assertEqual(correccion["usuario"], USUARIO)
        self.assertIn("1 punto(s) movido(s)", correccion["despues"])
        self.assertTrue(self.cliente.get("/bitacora/verificar").json()["ok"])

    def test_correccion_de_puntos_invalida(self):
        puntos = self.cliente.get("/casos/C-001").json()["imagenes"][0]["puntos"]
        self.assertEqual(self.cliente.put("/casos/C-001/puntos/lateral", json={"puntos": puntos[:-1]}).status_code, 422)
        puntos[0]["x"] = 99999
        self.assertEqual(self.cliente.put("/casos/C-001/puntos/lateral", json={"puntos": puntos}).status_code, 422)

    def test_confirmar_angulo_revisar(self):
        d = self.cliente.get("/casos/C-001").json()
        revisar = next(a for a in d["angulos"] if a["estado"] == "revisar")
        self.assertIsNotNone(revisar["motivo_estado"])
        r = self.cliente.post(
            f"/casos/C-001/angulos/{revisar['vista']}/{revisar['segmento']}/confirmar",
            json={"usuario": USUARIO, "rol": "ergonomia"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        actualizado = next(
            a for a in r.json()["angulos"]
            if a["vista"] == revisar["vista"] and a["segmento"] == revisar["segmento"]
        )
        self.assertEqual(actualizado["estado"], "ok")
        self.assertTrue(actualizado["confirmado"])
        self.assertEqual(actualizado["motivo_estado"], "Confirmado por especialista")
        entradas = self.cliente.get("/bitacora?id_caso=C-001").json()
        self.assertTrue(any(e["accion"] == "angulo_confirmado" for e in entradas))

    def test_alertas(self):
        alertas = self.cliente.get("/alertas").json()
        self.assertTrue(any(a["tipo_evento"] == "EMERGENCIA_CAIDA" for a in alertas))
        self.assertEqual(self.cliente.post("/alertas/DEMO-CAIDA-01/atender", json={"usuario": USUARIO}).status_code, 200)
        self.assertEqual(self.cliente.post("/alertas/DEMO-CAIDA-01/atender").status_code, 200)  # idempotente
        self.assertEqual(self.cliente.post("/alertas/NOPE/atender").status_code, 404)
        a = next(a for a in self.cliente.get("/alertas").json() if a["id_alerta"] == "DEMO-CAIDA-01")
        self.assertEqual(a["estado"], "atendida")

    def test_deteccion_de_alteracion_en_bitacora(self):
        ruta = self.ws / "bitacora.json"
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        datos[1]["usuario"] = "intruso"
        ruta.write_text(json.dumps(datos), encoding="utf-8")
        v = self.cliente.get("/bitacora/verificar").json()
        self.assertEqual((v["ok"], v["primera_falla"]), (False, 2))
        # No se permite encadenar nuevas decisiones sobre una bitácora alterada
        self.assertEqual(self.decidir("C-001", "R1", "aprobar").status_code, 409)

    def test_deteccion_de_alteracion_en_audit_trail(self):
        self.decidir("C-003", "R1", "aprobar")
        ruta = self.ws / "C-003" / "audit_trail.json"
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        datos["events"][0]["residual_risk_score"] = 1
        ruta.write_text(json.dumps(datos), encoding="utf-8")
        v = self.cliente.get("/bitacora/verificar").json()
        self.assertFalse(v["ok"])
        self.assertIn("C-003", v["detalle"])

    def test_persistencia_entre_reinicios(self):
        self.decidir("C-003", "R1", "aprobar")
        self.cliente.__exit__(None, None, None)
        self.cliente = TestClient(create_app(workspace_dir=self.ws))
        self.cliente.__enter__()
        d = self.cliente.get("/casos/C-003").json()
        self.assertEqual(d["recomendaciones"][0]["estado"], "aprobada")
        self.assertEqual(len(self.cliente.get("/casos").json()), 7)  # no se vuelve a sembrar


if __name__ == "__main__":
    unittest.main()
