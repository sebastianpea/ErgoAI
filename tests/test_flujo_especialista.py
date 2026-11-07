"""
Flujo de revisión del especialista: corrección de datos, descarte de hallazgos, edición de valores
propuestos, autorización de ingeniería para cambios en planta e implementación.
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import create_app

ERGO = {"usuario": "Ing. Ergonomía", "rol": "ergonomia"}
IE = {"usuario": "Ing. Procesos", "rol": "ingenieria"}


class TestFlujoEspecialista(unittest.TestCase):
    def setUp(self):
        self.ws = Path(tempfile.mkdtemp(prefix="ergoai_flujo_"))
        self.c = TestClient(create_app(workspace_dir=self.ws))
        self.c.__enter__()

    def tearDown(self):
        self.c.__exit__(None, None, None)
        shutil.rmtree(self.ws, ignore_errors=True)

    # ---------- utilidades ----------

    def caso(self, id_caso="C-001"):
        return self.c.get(f"/casos/{id_caso}").json()

    def rec(self, id_rec, id_caso="C-001"):
        return next(r for r in self.caso(id_caso)["recomendaciones"] if r["id"] == id_rec)

    def decidir(self, rec, accion, caso="C-001", actor=ERGO, **extra):
        cuerpo = {"id_caso": caso, "id_recomendacion": rec, "accion": accion, **actor, **extra}
        return self.c.post(f"/casos/{caso}/recomendaciones/{rec}/decision", json=cuerpo)

    def autorizar(self, rec, accion="autorizar", caso="C-001", actor=IE, **extra):
        return self.c.post(f"/casos/{caso}/recomendaciones/{rec}/autorizacion", json={"accion": accion, **actor, **extra})

    def implementar(self, rec, caso="C-001", actor=ERGO, **extra):
        return self.c.post(f"/casos/{caso}/recomendaciones/{rec}/implementacion", json={**actor, **extra})

    def acciones_trail(self, caso="C-001"):
        trail = json.loads((self.ws / caso / "audit_trail.json").read_text(encoding="utf-8"))
        return [e["action"] for e in trail["events"]]

    # ---------- recomendaciones con cambios concretos ----------

    def test_recomendacion_expone_cambios_y_reba_proyectado(self):
        r4 = self.rec("R4")
        self.assertEqual(r4["tipo_cambio"], "postura")
        cambio = r4["cambios"][0]
        self.assertEqual((cambio["parametro"], cambio["unidad"]), ("angulo.tronco", "°"))
        self.assertAlmostEqual(cambio["actual"] - cambio["objetivo"], 15.0, places=1)
        self.assertIsNotNone(r4["reba_proyectado"])
        self.assertFalse(r4["requiere_autorizacion"])
        self.assertTrue(self.rec("R1")["requiere_autorizacion"])

    def test_editar_valores_propuestos(self):
        r = self.decidir("R4", "editar", cambios={"angulo.tronco": 20}, motivo="El operador puede bajar más")
        self.assertEqual(r.status_code, 200, r.text)
        r4 = self.rec("R4")
        self.assertEqual(r4["estado"], "editada_aprobada")
        self.assertEqual(r4["cambios"][0]["objetivo"], 20.0)
        self.assertEqual(r4["implementacion"], "por_implementar")  # postura: sin autorización
        ultima = self.c.get("/bitacora?id_caso=C-001").json()
        self.assertTrue(any("valores:" in (e.get("despues") or "") for e in ultima))

    def test_editar_valores_invalidos(self):
        self.assertEqual(self.decidir("R4", "editar", cambios={"carga_kg": 0}, motivo="x").status_code, 422)
        self.assertEqual(self.decidir("R4", "editar", cambios={"angulo.tronco": 500}, motivo="x").status_code, 422)
        self.assertEqual(self.decidir("R4", "aprobar", cambios={"angulo.tronco": 10}).status_code, 422)

    # ---------- cambio en planta: requiere ingeniería ----------

    def test_cambio_en_planta_requiere_autorizacion_de_ingenieria(self):
        self.assertEqual(self.decidir("R1", "aprobar").status_code, 200)
        self.assertEqual(self.rec("R1")["implementacion"], "pendiente_autorizacion")
        self.assertEqual(self.caso()["validacion"]["por_autorizar"], 1)

        alertas = {a["id_alerta"]: a for a in self.c.get("/alertas").json()}
        self.assertEqual(alertas["C-001-AUTORIZACION_PENDIENTE"]["estado"], "nueva")

        # No se puede implementar sin autorización
        self.assertEqual(self.implementar("R1").status_code, 409)
        # Ergonomía no puede autorizar
        self.assertEqual(self.autorizar("R1", actor=ERGO).status_code, 403)
        # Quien aprobó no puede autorizar, aunque cambie de rol
        self.assertEqual(self.autorizar("R1", actor={**IE, "usuario": ERGO["usuario"]}).status_code, 409)

        self.assertEqual(self.autorizar("R1", motivo="MOC 16-HS80 firmado").status_code, 200)
        r1 = self.rec("R1")
        self.assertEqual((r1["implementacion"], r1["autorizado_por"]), ("por_implementar", IE["usuario"]))
        self.assertEqual(self.autorizar("R1").status_code, 409)  # ya autorizada

        # Ingeniería no marca la implementación; ergonomía sí
        self.assertEqual(self.implementar("R1", actor=IE).status_code, 403)
        self.assertEqual(self.implementar("R1", nota="Lifter instalado").status_code, 200)
        self.assertEqual(self.rec("R1")["implementacion"], "implementada")
        self.assertEqual(self.acciones_trail(), ["APPROVED", "AUTHORIZED", "IMPLEMENTED"])

        alertas = {a["id_alerta"]: a for a in self.c.get("/alertas").json()}
        self.assertEqual(alertas["C-001-AUTORIZACION_PENDIENTE"]["estado"], "atendida")
        self.assertTrue(self.c.get("/bitacora/verificar").json()["ok"])

    def test_denegacion_saca_la_recomendacion_del_residual(self):
        self.decidir("R1", "aprobar")
        antes = self.caso()["residual"]["recomendaciones_aplicadas"]
        self.assertEqual(self.autorizar("R1", "denegar").status_code, 422)  # sin motivo
        self.assertEqual(self.autorizar("R1", "denegar", motivo="Sin presupuesto este trimestre").status_code, 200)
        d = self.caso()
        self.assertIn("R1", antes)
        self.assertNotIn("R1", d["residual"]["recomendaciones_aplicadas"])
        self.assertEqual(self.rec("R1")["implementacion"], "denegada")

    def test_ingenieria_no_decide_recomendaciones(self):
        self.assertEqual(self.decidir("R1", "aprobar", actor=IE).status_code, 403)

    # ---------- recomendación nueva del especialista ----------

    def test_crear_recomendacion(self):
        cuerpo = {**ERGO, "nivel_control": "ingenieria", "tipo_cambio": "planta", "titulo": "Mesa elevadora",
                  "texto": "Instalar mesa elevadora de tijera a 105 cm.", "cambios": {"carga_kg": 0, "angulo.tronco": 10},
                  "motivo": "Alternativa más barata que el lifter"}
        r = self.c.post("/casos/C-001/recomendaciones", json=cuerpo)
        self.assertEqual(r.status_code, 200, r.text)
        e1 = self.rec(r.json()["id"])
        self.assertEqual((e1["origen"], e1["estado"], e1["implementacion"]), ("especialista", "aprobada", "pendiente_autorizacion"))
        self.assertEqual(len(e1["cambios"]), 2)
        self.assertEqual(self.acciones_trail(), ["CREATED"])

        incoherente = {**cuerpo, "tipo_cambio": "administrativo"}
        self.assertEqual(self.c.post("/casos/C-001/recomendaciones", json=incoherente).status_code, 422)
        self.assertEqual(self.c.post("/casos/C-001/recomendaciones", json={**cuerpo, **IE}).status_code, 403)

    # ---------- corrección de datos y hallazgos ----------

    def test_corregir_contexto(self):
        d = self.caso()
        ctx = {**d["contexto"], "carga_kg": 8}
        sin_motivo = self.c.put("/casos/C-001/contexto", json={**ERGO, "contexto": ctx})
        self.assertEqual(sin_motivo.status_code, 422)
        self.assertEqual(self.c.put("/casos/C-001/contexto", json={**IE, "contexto": ctx, "motivo": "x" * 5}).status_code, 403)

        r = self.c.put("/casos/C-001/contexto", json={**ERGO, "contexto": ctx, "motivo": "Se pesó la pieza: 8 kg"})
        self.assertEqual(r.status_code, 200, r.text)
        nuevo = r.json()
        self.assertEqual(nuevo["contexto"]["carga_kg"], 8)
        self.assertLess(nuevo["reba"]["final"], d["reba"]["final"])
        self.assertFalse(any(h["id"] == "JABIL-carga" for h in nuevo["hallazgos"]))
        entrada = next(e for e in self.c.get("/bitacora?id_caso=C-001").json() if e["accion"] == "contexto_corregido")
        self.assertIn("carga_kg: 16 kg", entrada["antes"])
        self.assertEqual(entrada["motivo"], "Se pesó la pieza: 8 kg")

    def test_descartar_y_restaurar_hallazgo(self):
        url = "/casos/C-001/hallazgos/V1/revision"
        r = self.c.post(url, json={**ERGO, "accion": "descartar", "motivo": "Es el termo del supervisor, no está en la estación"})
        self.assertEqual(r.status_code, 200, r.text)
        v1 = next(h for h in r.json()["hallazgos"] if h["id"] == "V1")
        self.assertEqual(v1["descartado"]["usuario"], ERGO["usuario"])
        alertas = {a["id_alerta"]: a for a in self.c.get("/alertas").json()}
        self.assertEqual(alertas["C-001-OBJETO_DESCONOCIDO"]["estado"], "atendida")

        self.assertEqual(self.c.post(url, json={**ERGO, "accion": "descartar", "motivo": "otra vez"}).status_code, 409)
        r = self.c.post(url, json={**ERGO, "accion": "restaurar", "motivo": "Sí estaba en la mesa"})
        self.assertIsNone(next(h for h in r.json()["hallazgos"] if h["id"] == "V1")["descartado"])
        self.assertEqual(self.c.post("/casos/C-001/hallazgos/NOPE/revision",
                                     json={**ERGO, "accion": "descartar", "motivo": "xxx"}).status_code, 404)


if __name__ == "__main__":
    unittest.main()
