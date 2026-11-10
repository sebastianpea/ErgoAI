"""
Varios operadores en la misma foto, levantamiento entre 2 personas y hoja oficial 16-PE80-6500-00014-H.
El estimador de pose se sustituye por uno simulado (dos personas conocidas) para que las pruebas no
dependan de los modelos ONNX.
"""

import io
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

import openpyxl
from fastapi.testclient import TestClient

from backend.app.settings import PLANTILLA_14H
from backend.app.vision import estimador as mod_estimador
from backend.app.vision.estimador import PuntoDetectado, ResultadoFoto
from backend.main import create_app

ERGO = {"usuario": "Ing. Ergonomía", "rol": "ergonomia"}
IE = {"usuario": "Ing. Procesos", "rol": "ingenieria"}


def _persona(dx: float, flexion: bool) -> list:
    """Operador de perfil mirando a la derecha; `flexion` lo inclina hacia adelante."""
    hombro = (700 + dx, 330) if flexion else (590 + dx, 300)
    base = {0: (hombro[0] + 70, hombro[1] - 30), 3: (hombro[0] + 45, hombro[1] - 38), 5: hombro,
            7: (hombro[0] + 24, hombro[1] + 120), 9: (hombro[0] + 95, hombro[1] + 190), 11: (580 + dx, 440),
            13: (612 + dx, 560), 15: (600 + dx, 680), 17: (hombro[0] + 140, hombro[1] + 230)}
    pts = [PuntoDetectado(id=i, x=float(x), y=float(y), confianza=0.9) for i, (x, y) in base.items()]
    pts += [PuntoDetectado(id=i, x=0.0, y=0.0, confianza=0.05) for i in range(19) if i not in base]
    return sorted(pts, key=lambda p: p.id)


def _resultado(img, personas=2) -> ResultadoFoto:
    todas = [_persona(0, flexion=True), _persona(400, flexion=False)][:personas]
    return ResultadoFoto(imagen_bgr=img, personas=personas, puntos=todas[0], caja=(500, 250, 300, 450),
                         rostro_anonimizado=True, todas=todas,
                         cajas_todas=[(500 + 400 * i, 250, 300, 450) for i in range(personas)], indice_principal=0)


def _jpg() -> bytes:
    ok, buf = cv2.imencode(".jpg", np.full((720, 1280, 3), 180, np.uint8))
    return buf.tobytes()


@unittest.skipIf(cv2 is None, "Requiere opencv/numpy (backend/requirements-vision.txt)")
class TestMultipersona(unittest.TestCase):
    def setUp(self):
        self.ws = Path(tempfile.mkdtemp(prefix="ergoai_multi_"))
        self.c = TestClient(create_app(workspace_dir=self.ws))
        self.c.__enter__()
        mock.patch.object(mod_estimador.EstimadorPose, "estado", staticmethod(lambda: (True, "simulado"))).start()
        mock.patch.object(mod_estimador.estimador, "analizar", side_effect=lambda img: _resultado(img)).start()
        self.addCleanup(mock.patch.stopall)

    def tearDown(self):
        self.c.__exit__(None, None, None)
        shutil.rmtree(self.ws, ignore_errors=True)

    def crear(self, **extra):
        datos = {**ERGO, "estacion": "Línea 9 · Carga de bobinas", "tipo_tarea": "levantamiento",
                 "contexto": {"carga_kg": 22, "agarre": "regular", "personas_en_carga": 2},
                 "evaluar_todos": True, **extra}
        fotos = {"lateral": ("l.jpg", _jpg(), "image/jpeg"), "frontal": ("f.jpg", _jpg(), "image/jpeg")}
        r = self.c.post("/casos", data={"datos": json.dumps(datos)}, files=fotos)
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()["id"]

    def test_un_caso_por_operador(self):
        primero = self.crear()
        d1 = self.c.get(f"/casos/{primero}").json()
        g = d1["grupo"]
        self.assertEqual((g["indice"], g["total"]), (1, 2))
        self.assertEqual(len(g["casos"]), 2)
        d2 = self.c.get(f"/casos/{g['casos'][1]}").json()
        self.assertEqual(d2["grupo"]["indice"], 2)
        self.assertIn("Operador 2", d2["estacion"])
        # Cada operador tiene su propio esqueleto y su propio REBA
        hombro = lambda d: next(p for p in d["imagenes"][0]["puntos"] if p["id"] == 5)["x"]  # noqa: E731
        self.assertNotEqual(hombro(d1), hombro(d2))
        tronco = lambda d: next(a for a in d["angulos"] if a["segmento"] == "tronco")["puntaje_reba"]  # noqa: E731
        self.assertGreater(tronco(d1), tronco(d2))
        self.assertTrue(d1["recomendaciones"] and d2["recomendaciones"])

    def test_sin_evaluar_todos_crea_un_solo_caso(self):
        id_caso = self.crear(evaluar_todos=False)
        d = self.c.get(f"/casos/{id_caso}").json()
        self.assertIsNone(d["grupo"])
        self.assertTrue(any(h["id"] == "V-personas-lateral" for h in d["hallazgos"]))

    def test_reasignar_persona_en_una_vista(self):
        primero = self.crear()
        url = f"/casos/{primero}/asignacion-operador"
        self.assertEqual(self.c.put(url, json={**ERGO, "vista": "frontal", "indice": 5, "motivo": "x" * 4}).status_code, 422)
        self.assertEqual(self.c.put(url, json={**IE, "vista": "frontal", "indice": 1, "motivo": "xxxx"}).status_code, 403)
        r = self.c.put(url, json={**ERGO, "vista": "frontal", "indice": 1, "motivo": "En la frontal está a la derecha"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["grupo"]["asignacion"]["frontal"], 1)
        bit = self.c.get(f"/bitacora?id_caso={primero}").json()
        self.assertTrue(any(e["accion"] == "operador_reasignado" for e in bit))

    def test_levantamiento_entre_dos_personas(self):
        d = self.c.get(f"/casos/{self.crear()}").json()
        h = next(h for h in d["hallazgos"] if h["id"] == "JABIL-carga-equipo")
        self.assertEqual(h["severidad"], "advertencia")  # 22 kg entre 2: zona naranja (19–28)
        self.assertFalse(any(h["id"] == "JABIL-carga" for h in d["hallazgos"]))  # no se aplica el límite individual
        self.assertTrue(any("Peso en equipo" in f["etiqueta"] for f in d["nom036"]["factores"]))  # hoja Equipo (3)
        self.assertEqual(d["reba"]["carga"], 2)  # 11 kg por persona → > 10 kg
        titulos = [r["titulo"] for r in d["recomendaciones"]]
        self.assertIn("Asistencia mecánica para el levantamiento en equipo", titulos)

    def test_tipo_operacion_equipo_activa_dos_personas(self):
        datos = {**ERGO, "estacion": "Línea 9", "tipo_operacion": "Equipo (3)", "contexto": {"carga_kg": 15}}
        r = self.c.post("/casos", data={"datos": json.dumps(datos)}, files={"lateral": ("l.jpg", _jpg(), "image/jpeg")})
        d = self.c.get(f"/casos/{r.json()['id']}").json()
        self.assertEqual((d["tipo_tarea"], d["contexto"]["personas_en_carga"]), ("levantamiento", 2))
        self.assertFalse(any(h["id"].startswith("JABIL-carga") for h in d["hallazgos"]))  # 15 kg entre 2: verde

    def test_hoja_14h(self):
        primero = self.crear()
        hoja = {"negocio": "Healthcare", "linea": "L9", "zona_maxima": 4, "posicion": "Pie", "tipo_trabajo": "Ligero",
                "frecuencia": "2_20", "acceso_800mm": True, "evaluacion_operador": 3}
        r = self.c.put(f"/casos/{primero}/hoja-14h", json={**ERGO, "hoja_14h": hoja})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["hoja_14h"]["zona_maxima"], 4)
        malo = {**hoja, "zona_maxima": 9}
        self.assertEqual(self.c.put(f"/casos/{primero}/hoja-14h", json={**ERGO, "hoja_14h": malo}).status_code, 422)

    def _completar(self, id_caso):
        for r in self.c.get(f"/casos/{id_caso}").json()["recomendaciones"]:
            cuerpo = {**ERGO, "id_caso": id_caso, "id_recomendacion": r["id"], "accion": "aprobar"}
            self.c.post(f"/casos/{id_caso}/recomendaciones/{r['id']}/decision", json=cuerpo)
        for r in self.c.get(f"/casos/{id_caso}").json()["recomendaciones"]:
            if r["implementacion"] == "pendiente_autorizacion":
                self.c.post(f"/casos/{id_caso}/recomendaciones/{r['id']}/autorizacion", json={**IE, "accion": "autorizar"})
        for r in self.c.get(f"/casos/{id_caso}").json()["recomendaciones"]:
            if r["implementacion"] == "por_implementar":
                self.c.post(f"/casos/{id_caso}/recomendaciones/{r['id']}/implementacion", json={**ERGO})
        self.assertTrue(self.c.get(f"/casos/{id_caso}").json()["validacion"]["aprobado_e_implementado"])

    @unittest.skipUnless(PLANTILLA_14H.is_file(), "Plantilla oficial no disponible (no se versiona)")
    def test_excel_oficial_con_dos_operadores(self):
        primero = self.crear()
        ids = self.c.get(f"/casos/{primero}").json()["grupo"]["casos"]
        hoja = {"negocio": "Healthcare", "zona_maxima": 4, "posicion": "Pie", "tipo_trabajo": "Ligero"}
        self.c.put(f"/casos/{primero}/hoja-14h", json={**ERGO, "hoja_14h": hoja})
        # El grupo solo se exporta cuando ambos operadores están validados
        self._completar(primero)
        self.assertEqual(self.c.get(f"/casos/{primero}/exportar/excel").status_code, 422)
        self._completar(ids[1])

        r = self.c.get(f"/casos/{ids[1]}/exportar/excel")
        self.assertEqual(r.status_code, 200, r.text)
        wb = openpyxl.load_workbook(io.BytesIO(r.content), keep_vba=True)
        self.assertIn("Mov (2)", wb.sheetnames)
        d1, d2 = (self.c.get(f"/casos/{i}").json() for i in ids)
        mov, mov2 = wb["Mov"], wb["Mov (2)"]
        self.assertEqual((mov["L172"].value, mov2["L172"].value), (d1["reba"]["final"], d2["reba"]["final"]))
        self.assertEqual(mov["E2"].value, "Healthcare")
        self.assertEqual(mov["L43"].value, " Ligero")  # valor exacto de la lista de la plantilla
        self.assertIs(mov["V4"].value, True)  # zona 4
        self.assertIn("REBA", mov["B172"].value)
        marcas = [c.coordinate for fila in wb["Equipo (3)"].iter_rows(min_row=10, max_row=120, min_col=5, max_col=8)
                  for c in fila if c.value == "x"]
        # Una "x" por cada factor calculado (A, B, C, I): ni más ni menos. La plantilla trae una de ejemplo en F119.
        self.assertEqual(len(marcas), len(d1["nom036"]["factores"]), marcas)
        self.assertEqual(mov["K55"].value, 22)  # la plantilla trae 6 kg de ejemplo
        self.assertEqual(mov2["E2"].value, "Healthcare")  # el encabezado del operador 1 vale para el grupo
        otras_nom = [c.coordinate for h in ("Levantamiento (1)", "Transporte (2)", "con auxiliar (5)")
                     for fila in wb[h].iter_rows(min_col=5, max_col=8) for c in fila if str(c.value).lower() == "x"]
        self.assertEqual(otras_nom, [], "las hojas NOM-036 que no aplican quedan sin marcas de ejemplo")
        self.assertIn(wb["OBSERVACIONES Y MEJORAS"]["B3"].value, ("Mov", "Mov (2)"))
        self.assertEqual(len(wb["Fotos de la estacion"]._images), 4)  # 2 vistas × 2 operadores


if __name__ == "__main__":
    unittest.main()
