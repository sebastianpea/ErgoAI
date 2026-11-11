"""Evidence-aware intake contract tests through the public case API."""

import json
import shutil
import tempfile
from pathlib import Path
from unittest import mock

import cv2
import numpy as np
from fastapi.testclient import TestClient

from backend.app.api.schemas import Actor
from backend.app.vision import estimador as mod_estimador
from backend.app.vision.estimador import PuntoDetectado, ResultadoFoto
from backend.main import create_app


def _photo() -> bytes:
    ok, encoded = cv2.imencode(".jpg", np.full((720, 1280, 3), 200, np.uint8))
    assert ok
    return encoded.tobytes()


def _pose(image) -> ResultadoFoto:
    coordinates = {
        0: (790, 300), 3: (745, 292), 5: (700, 330), 7: (724, 450), 9: (795, 520),
        11: (580, 440), 13: (612, 560), 15: (600, 680), 17: (840, 560),
    }
    points = [PuntoDetectado(i, float(x), float(y), 0.95) for i, (x, y) in coordinates.items()]
    return ResultadoFoto(image, 1, points, (500, 250, 400, 450), True)


def test_new_case_without_operational_evidence_has_no_final_risk_score():
    workspace = Path(tempfile.mkdtemp(prefix="ergoai_evidence_"))
    client = TestClient(create_app(workspace_dir=workspace))
    with mock.patch.object(mod_estimador.EstimadorPose, "estado", staticmethod(lambda: (True, "simulated"))), \
         mock.patch.object(mod_estimador.estimador, "analizar", side_effect=_pose):
        with client:
            response = client.post("/casos", data={
                "datos": json.dumps({
                    **Actor(usuario="Ergonomía", rol="ergonomia").model_dump(),
                    "estacion": "Línea 4 · Empaque",
                    "tipo_tarea": "levantamiento",
                }),
            }, files={"lateral": ("lateral.jpg", _photo(), "image/jpeg")})
            assert response.status_code == 200, response.text
            case = client.get(f"/casos/{response.json()['id']}")

    assert case.status_code == 200, case.text
    detail = case.json()
    assert detail["assessment_status"] == "incomplete"
    assert detail["reba"] is None
    assert detail["nom036"] is None
    assert {"carga_kg", "agarre", "actividad"}.issubset(set(detail["missing_evidence"]))
    shutil.rmtree(workspace, ignore_errors=True)


def _create_evidence_case(client, extra_view=None):
    files = {"lateral": ("lateral.jpg", _photo(), "image/jpeg")}
    if extra_view:
        files[extra_view] = (f"{extra_view}.jpg", _photo(), "image/jpeg")
    response = client.post("/casos", data={"datos": json.dumps({
        **Actor(usuario="Ergonomía", rol="ergonomia").model_dump(),
        "estacion": "Línea 4 · Empaque", "tipo_tarea": "empuje_con_auxiliar",
    })}, files=files)
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_unknown_context_audit_does_not_call_unknown_zero(tmp_path):
    client = TestClient(create_app(workspace_dir=tmp_path))
    actor = Actor(usuario="Ergonomía", rol="ergonomia").model_dump()
    with mock.patch.object(mod_estimador.EstimadorPose, "estado", staticmethod(lambda: (True, "simulated"))), \
         mock.patch.object(mod_estimador.estimador, "analizar", side_effect=_pose), client:
        case_id = _create_evidence_case(client)
        url = f"/casos/{case_id}/contexto"
        context = {"carga_kg": 8, "carga_brusca": False, "agarre": "regular", "actividad": 1,
                   "apoyo_unilateral": False, "altura_trabajo_cm": 100,
                   "modificadores": {k: False for k in (
                       "tronco_torsion_o_inclinacion", "cuello_torsion_o_inclinacion", "hombro_elevado",
                       "brazo_abducido_o_rotado", "brazo_apoyado", "muneca_desviada_o_torcida")}}
        assert client.put(url, json={**actor, "contexto": context, "motivo": "Medido en piso"}).status_code == 200
        response = client.put(url, json={**actor, "contexto": {**context, "carga_kg": None}, "motivo": "Medición pendiente"})
        assert response.status_code == 200, response.text
        entries = client.get("/bitacora", params={"id_caso": case_id}).json()
        event = [e for e in entries if e["accion"] == "contexto_corregido"][-1]
        assert "desconocido" in event["despues"]
        assert "0 kg" not in event["despues"]


def test_supported_frontal_positive_evidence_survives_input_normalization(tmp_path):
    client = TestClient(create_app(workspace_dir=tmp_path))
    with mock.patch.object(mod_estimador.EstimadorPose, "estado", staticmethod(lambda: (True, "simulated"))), \
         mock.patch.object(mod_estimador.estimador, "analizar", side_effect=_pose), \
         mock.patch("backend.app.services.casos.medir_vista_frontal", return_value={
             "inclinacion_tronco": 30, "abduccion_brazo": 60,
         }), client:
        case_id = _create_evidence_case(client, "frontal")
        detail = client.get(f"/casos/{case_id}").json()
    modifiers = detail["contexto"]["modificadores"]
    assert modifiers["tronco_torsion_o_inclinacion"] is True
    assert modifiers["brazo_abducido_o_rotado"] is True
    assert "modificadores.tronco_torsion_o_inclinacion" not in detail["contexto_faltante"]
    assert "modificadores.brazo_abducido_o_rotado" not in detail["contexto_faltante"]


def test_unknown_context_modifier_is_rejected_not_ignored(tmp_path):
    client = TestClient(create_app(workspace_dir=tmp_path))
    with mock.patch.object(mod_estimador.EstimadorPose, "estado", staticmethod(lambda: (True, "simulated"))), \
         mock.patch.object(mod_estimador.estimador, "analizar", side_effect=_pose), client:
        case_id = _create_evidence_case(client)
        before = client.get(f"/casos/{case_id}").json()
        context = {"modificadores": {"hombros_elevados": True}}
        response = client.put(f"/casos/{case_id}/contexto", json={
            **Actor(usuario="Ergonomía", rol="ergonomia").model_dump(),
            "contexto": context, "motivo": "Corrijo dato",
        })
        after = client.get(f"/casos/{case_id}").json()
    assert response.status_code == 422
    assert after["contexto_faltante"] == before["contexto_faltante"]


def test_unknown_modifier_audit_does_not_substitute_task_name(tmp_path):
    client = TestClient(create_app(workspace_dir=tmp_path, sembrar=False))
    actor = Actor(usuario="Ergonomía", rol="ergonomia").model_dump()
    context = {"carga_kg": 8, "carga_brusca": False, "agarre": "regular", "actividad": 1,
               "apoyo_unilateral": False, "altura_trabajo_cm": 100,
               "modificadores": {k: False for k in (
                   "tronco_torsion_o_inclinacion", "cuello_torsion_o_inclinacion", "hombro_elevado",
                   "brazo_abducido_o_rotado", "brazo_apoyado", "muneca_desviada_o_torcida")}}
    with mock.patch.object(mod_estimador.EstimadorPose, "estado", staticmethod(lambda: (True, "simulated"))), \
         mock.patch.object(mod_estimador.estimador, "analizar", side_effect=_pose), client:
        case_id = _create_evidence_case(client)
        url = f"/casos/{case_id}/contexto"
        assert client.put(url, json={**actor, "contexto": context, "motivo": "Revisión en piso"}).status_code == 200
        context["modificadores"]["hombro_elevado"] = None
        assert client.put(url, json={**actor, "contexto": context, "motivo": "Dato desconocido"}).status_code == 200
        entries = client.get("/bitacora", params={"id_caso": case_id}).json()
        event = [e for e in entries if e["accion"] == "contexto_corregido"][-1]
    assert "hombro_elevado: desconocido" in event["despues"]
    for text in (event["antes"], event["despues"]):
        assert "hombro_elevado: empuje_con_auxiliar" not in text


def test_confirmed_reba_context_does_not_make_automatic_nom036_final(tmp_path):
    client = TestClient(create_app(workspace_dir=tmp_path))
    actor = Actor(usuario="Ergonomía", rol="ergonomia").model_dump()
    context = {"carga_kg": 8, "carga_brusca": False, "agarre": "regular", "actividad": 1,
               "apoyo_unilateral": False, "altura_trabajo_cm": 100,
               "modificadores": {k: False for k in (
                   "tronco_torsion_o_inclinacion", "cuello_torsion_o_inclinacion", "hombro_elevado",
                   "brazo_abducido_o_rotado", "brazo_apoyado", "muneca_desviada_o_torcida")}}
    with mock.patch.object(mod_estimador.EstimadorPose, "estado", staticmethod(lambda: (True, "simulated"))), \
         mock.patch.object(mod_estimador.estimador, "analizar", side_effect=_pose), client:
        case_id = _create_evidence_case(client)
        url = f"/casos/{case_id}"
        assert client.put(f"{url}/contexto", json={
            **actor, "contexto": context, "motivo": "Verificado en piso",
        }).status_code == 200
        angles = client.get(url).json()["angulos"]
        for angle in angles:
            if angle["angulo_grados"] is not None:
                response = client.post(
                    f"{url}/angulos/{angle['vista']}/{angle['segmento']}/confirmar", json=actor,
                )
                assert response.status_code == 200, response.text
        detail = client.get(url).json()
    assert detail["risk_ready"]
    assert detail["reba"] is not None
    assert detail["nom036"] is None
