"""
Integración de visión: creación de casos desde fotos.
El estimador se sustituye por uno simulado con puntos conocidos para que las pruebas sean
deterministas y no requieran los modelos ONNX; una prueba adicional usa los modelos reales si están.
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

try:
    import cv2
    import numpy as np
except ImportError:  # pragma: no cover
    cv2 = None

from fastapi.testclient import TestClient

from backend.app.core_ergonomics.angle_geometry import extraer_angulos_laterales, medir_vista_frontal
from backend.app.vision import estimador as mod_estimador
from backend.app.vision.estimador import PuntoDetectado, ResultadoFoto
from backend.main import create_app

ERGO = {"usuario": "Ing. Ergonomía", "rol": "ergonomia"}

# Operador de perfil mirando a la derecha, tronco flexionado ~45°, con nudillo medio (17) para la muñeca.
ESQUELETO = {
    0: (790, 300), 3: (745, 292), 5: (700, 330), 7: (724, 450), 9: (795, 520), 11: (580, 440),
    13: (612, 560), 15: (600, 680), 17: (840, 560),
}


def _contexto_confirmado(**cambios):
    """Captura manual de la fixture; no son inferencias de la fotografía."""
    return {
        "carga_kg": 18, "carga_brusca": False, "agarre": "regular", "actividad": 1,
        "apoyo_unilateral": False, "altura_trabajo_cm": 95,
        "modificadores": {
            "tronco_torsion_o_inclinacion": False, "cuello_torsion_o_inclinacion": False,
            "hombro_elevado": False, "brazo_abducido_o_rotado": False,
            "brazo_apoyado": False, "muneca_desviada_o_torcida": False,
        },
        **cambios,
    }


def _confirmar_angulos(cliente, id_caso):
    respuesta = cliente.get(f"/casos/{id_caso}")
    assert respuesta.status_code == 200, respuesta.text
    detalle = respuesta.json()
    for angulo in detalle["angulos"]:
        if angulo["angulo_grados"] is not None:
            respuesta = cliente.post(
                f"/casos/{id_caso}/angulos/{angulo['vista']}/{angulo['segmento']}/confirmar",
                json=ERGO,
            )
            assert respuesta.status_code == 200, respuesta.text
    respuesta = cliente.get(f"/casos/{id_caso}")
    assert respuesta.status_code == 200, respuesta.text
    detalle = respuesta.json()
    assert detalle["assessment_status"] == "ready", detalle["missing_evidence"]
    assert detalle["risk_ready"]
    assert detalle["missing_evidence"] == []
    assert detalle["reba"] is not None
    assert all(a["confirmado"] for a in detalle["angulos"] if a["angulo_grados"] is not None)
    return detalle


def _foto_jpg() -> bytes:
    ok, buf = cv2.imencode(".jpg", np.full((720, 1280, 3), 200, np.uint8))
    return buf.tobytes()


def _resultado(img, personas=1) -> ResultadoFoto:
    puntos = [PuntoDetectado(id=i, x=float(x), y=float(y), confianza=0.9) for i, (x, y) in ESQUELETO.items()]
    puntos += [PuntoDetectado(id=i, x=0.0, y=0.0, confianza=0.05) for i in range(19) if i not in ESQUELETO]
    return ResultadoFoto(imagen_bgr=img, personas=personas, puntos=sorted(puntos, key=lambda p: p.id),
                         caja=(500, 250, 400, 450), rostro_anonimizado=True)


@unittest.skipIf(cv2 is None, "Requiere opencv/numpy (backend/requirements-vision.txt)")
class TestCrearCasoDesdeFotos(unittest.TestCase):
    def setUp(self):
        self.ws = Path(tempfile.mkdtemp(prefix="ergoai_vision_"))
        self.c = TestClient(create_app(workspace_dir=self.ws))
        self.c.__enter__()
        estado = mock.patch.object(mod_estimador.EstimadorPose, "estado", staticmethod(lambda: (True, "simulado")))
        analizar = mock.patch.object(mod_estimador.estimador, "analizar", side_effect=lambda img: _resultado(img))
        estado.start(); analizar.start()
        self.addCleanup(mock.patch.stopall)

    def tearDown(self):
        self.c.__exit__(None, None, None)
        shutil.rmtree(self.ws, ignore_errors=True)

    def crear(self, datos=None, fotos=None):
        datos = datos or {**ERGO, "estacion": "Línea 7 · Prensa", "tipo_tarea": "levantamiento",
                          "contexto": _contexto_confirmado()}
        fotos = fotos if fotos is not None else {"lateral": ("lateral.jpg", _foto_jpg(), "image/jpeg")}
        return self.c.post("/casos", data={"datos": json.dumps(datos)}, files=fotos)

    def test_crea_caso_con_angulos_reba_y_recomendaciones(self):
        r = self.crear()
        self.assertEqual(r.status_code, 200, r.text)
        id_caso = r.json()["id"]
        self.assertEqual(id_caso, "C-008")  # después de los 7 casos de ejemplo
        d = _confirmar_angulos(self.c, id_caso)
        self.assertEqual(d["estacion"], "Línea 7 · Prensa")
        self.assertEqual(d["contexto"]["altura_trabajo_cm"], 95)

        muneca = next(a for a in d["angulos"] if a["segmento"] == "muneca")
        self.assertIsNotNone(muneca["angulo_grados"], "la muñeca se mide con el punto de la mano")
        self.assertIsNotNone(d["reba"])
        titulos = [rec["titulo"] for rec in d["recomendaciones"]]
        self.assertIn("Asistencia mecánica para la carga", titulos)  # 18 kg > 14 kg Jabil
        self.assertIn("Ajustar la altura de la superficie de trabajo", titulos)  # tronco ~45°
        primeras = [rec["nivel_control"] for rec in d["recomendaciones"]]
        self.assertEqual(primeras, sorted(primeras, key=lambda n: n != "ingenieria"))  # ingeniería primero
        self.assertTrue((self.ws / id_caso / "inputs" / "lateral.jpg").is_file())
        self.assertEqual(self.c.get(d["imagenes"][0]["url"]).status_code, 200)
        acciones = [e["accion"] for e in self.c.get(f"/bitacora?id_caso={id_caso}").json()]
        self.assertEqual(acciones[:2], ["caso_creado", "analisis_ejecutado"])

    def test_varias_personas_genera_hallazgo(self):
        with mock.patch.object(mod_estimador.estimador, "analizar", side_effect=lambda img: _resultado(img, 3)):
            id_caso = self.crear().json()["id"]
        hallazgos = self.c.get(f"/casos/{id_caso}").json()["hallazgos"]
        self.assertTrue(any(h["id"] == "V-personas-lateral" for h in hallazgos))

    def test_validaciones(self):
        self.assertEqual(self.crear(fotos={}).status_code, 422)  # falta lateral
        malo = {"lateral": ("x.jpg", b"no soy una imagen", "image/jpeg")}
        self.assertEqual(self.crear(fotos=malo).status_code, 422)
        self.assertEqual(self.crear(datos={**ERGO, "estacion": "x", "tipo_tarea": "levantamiento"}).status_code, 422)
        ie = {"usuario": "Ing. IE", "rol": "ingenieria", "estacion": "Línea 7", "tipo_tarea": "postura"}
        self.assertEqual(self.crear(datos=ie).status_code, 403)
        with mock.patch.object(mod_estimador.estimador, "analizar", side_effect=lambda img: _resultado(img, 0)):
            self.assertEqual(self.crear().status_code, 422)  # nadie en la foto lateral

    def test_impacto_medido(self):
        id_caso = self.crear().json()["id"]
        _confirmar_angulos(self.c, id_caso)
        imp = self.c.get("/metricas/impacto").json()
        self.assertEqual([c["id_caso"] for c in imp["casos"]], [id_caso])  # los casos de ejemplo no cuentan
        self.assertIsNotNone(imp["analisis_promedio_s"])
        self.assertIsNone(imp["casos"][0]["validacion_min"])  # aún sin validar
        for r in self.c.get(f"/casos/{id_caso}").json()["recomendaciones"]:
            cuerpo = {**ERGO, "id_caso": id_caso, "id_recomendacion": r["id"], "accion": "aprobar"}
            respuesta = self.c.post(f"/casos/{id_caso}/recomendaciones/{r['id']}/decision", json=cuerpo)
            self.assertEqual(respuesta.status_code, 200, respuesta.text)
        d = self.c.get(f"/casos/{id_caso}").json()
        self.assertTrue(d["validacion"]["completa"])
        self.assertIsNotNone(d["metricas"]["validado_en"])
        imp = self.c.get("/metricas/impacto").json()
        self.assertIsNotNone(imp["casos"][0]["validacion_min"])
        self.assertGreater(imp["ahorro_porcentaje"], 0)

    def test_recomendaciones_por_tipo_de_transporte(self):
        base = {**ERGO, "estacion": "Línea 3 · Almacén", "contexto": _contexto_confirmado(carga_kg=8)}
        acarreo = self.crear(datos={**base, "tipo_tarea": "transporte"}).json()["id"]
        carro = self.crear(datos={**base, "tipo_tarea": "empuje_con_auxiliar"}).json()["id"]
        t1 = [r["titulo"] for r in _confirmar_angulos(self.c, acarreo)["recomendaciones"]]
        t2 = [r["titulo"] for r in _confirmar_angulos(self.c, carro)["recomendaciones"]]
        self.assertIn("Sustituir el acarreo manual por un auxiliar de transporte", t1)
        self.assertNotIn("Asistencia mecánica para la carga", t1)
        self.assertIn("Adecuar el carro o auxiliar de transporte", t2)

    def test_sin_modelos_responde_503(self):
        with mock.patch.object(mod_estimador.EstimadorPose, "estado", staticmethod(lambda: (False, "faltan modelos"))):
            r = self.crear()
            self.assertEqual(r.status_code, 503)
            self.assertFalse(self.c.get("/vision/estado").json()["disponible"])

    def test_analizar_rapido_foto(self):
        archivos = {"foto": ("operador.jpg", _foto_jpg(), "image/jpeg")}
        r = self.c.post("/vision/analizar-rapido", files=archivos, data={"tipo_tarea": "levantamiento", "carga_kg": 10.0})
        self.assertEqual(r.status_code, 200, r.text)
        datos = r.json()
        self.assertTrue(datos["ok"])
        # Esta captura rápida prueba la imagen/pose, no valida riesgo sin contexto confirmado.
        self.assertIsNone(datos["reba_final"])
        self.assertFalse(datos["risk_ready"])
        self.assertEqual(datos["assessment_status"], "incomplete")
        self.assertIn("imagen_anotada_b64", datos)
        self.assertTrue(datos["imagen_anotada_b64"].startswith("data:image/jpeg;base64,"))
        self.assertGreater(len(datos["angulos"]), 0)


class TestMunecaDesdeMano(unittest.TestCase):
    def test_muneca_alineada_y_flexionada(self):
        class P:
            def __init__(self, i, x, y):
                self.id, self.x, self.y, self.confianza = i, x, y, 0.9
        base = [P(0, 300, 90), P(3, 260, 95), P(5, 200, 100), P(7, 200, 200), P(11, 200, 300),
                P(13, 200, 400), P(15, 200, 500)]
        recta = extraer_angulos_laterales(base + [P(9, 300, 200), P(17, 350, 200)])
        flexionada = extraer_angulos_laterales(base + [P(9, 300, 200), P(17, 335, 235)])
        self.assertAlmostEqual(recta["muneca"].grados, 0.0, places=1)
        self.assertAlmostEqual(flexionada["muneca"].grados, 45.0, places=1)


class TestVistaFrontal(unittest.TestCase):
    class P:
        def __init__(self, i, x, y):
            self.id, self.x, self.y, self.confianza = i, x, y, 0.9

    def puntos(self, codo_izq, hombros=((560, 300), (720, 300))):
        # Vista frontal: el hombro izquierdo (5) aparece a la DERECHA de la imagen.
        (xd, yd), (xi, yi) = hombros
        P = self.P
        return [P(6, xd, yd), P(5, xi, yi), P(12, 590, 450), P(11, 690, 450), P(7, *codo_izq)]

    def test_brazo_pegado_al_cuerpo(self):
        m = medir_vista_frontal(self.puntos((725, 420)), "izq", 0.3)
        self.assertLess(m["abduccion_brazo"], 5)
        self.assertLess(m["inclinacion_tronco"], 5)

    def test_brazo_abducido_hacia_afuera(self):
        m = medir_vista_frontal(self.puntos((800, 380)), "izq", 0.3)
        self.assertGreater(m["abduccion_brazo"], 40)

    def test_codo_cruzado_no_es_abduccion(self):
        m = medir_vista_frontal(self.puntos((640, 400)), "izq", 0.3)
        self.assertEqual(m["abduccion_brazo"], 0.0)

    def test_inclinacion_lateral_de_tronco(self):
        m = medir_vista_frontal(self.puntos((780, 400), hombros=((620, 300), (780, 300))), "izq", 0.3)
        self.assertGreater(m["inclinacion_tronco"], 15)


@unittest.skipUnless(cv2 is not None and mod_estimador.EstimadorPose.estado()[0], "Modelos ONNX no descargados")
class TestModelosReales(unittest.TestCase):
    def test_imagen_sin_personas(self):
        r = mod_estimador.estimador.analizar(np.full((480, 640, 3), 127, np.uint8))
        self.assertEqual(r.personas, 0)


if __name__ == "__main__":
    unittest.main()
