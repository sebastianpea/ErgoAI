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


def test_manual_person_selection_is_local_and_edits_are_scoped(tmp_path):
    from backend.app.vision.estimador import PersonaDetectada
    actor = Actor(usuario='Ergonomía').model_dump()
    def multiple(image):
        result = _pose(image)
        result.personas = 2
        result.poses = [PersonaDetectada('persona-1', result.puntos),
                        PersonaDetectada('persona-2', [PuntoDetectado(5, 100, 100, .9)])]
        result.puntos = []
        return result
    client = TestClient(create_app(workspace_dir=tmp_path, sembrar=False))
    with mock.patch.object(mod_estimador.EstimadorPose, 'estado', return_value=(True, 'fixture')), \
         mock.patch.object(mod_estimador.estimador, 'analizar', side_effect=multiple), client:
        case_id = _create_evidence_case(client, 'frontal')
        url = f'/casos/{case_id}'
        before = client.get(url).json()
        assert all(i['persona_seleccionada'] is None and i['puntos'] == [] for i in before['imagenes'])
        assert all(len(i['personas']) == 2 for i in before['imagenes'])
        assert before['reba'] is None
        selection = f'{url}/persona/lateral'
        response = client.put(selection, json={**actor, 'persona_id': 'persona-2'})
        assert response.status_code == 200, response.text
        detail = response.json()
        assert detail['imagenes'][0]['puntos'][0]['x'] == 100
        assert detail['imagenes'][1]['puntos'] == [], 'no identity matching across views'
        points = detail['imagenes'][0]['puntos']
        points[0]['x'] = 110
        response = client.put(f'{url}/puntos/lateral', json={**actor, 'persona_id': 'persona-2', 'puntos': points})
        assert response.status_code == 200, response.text
        people = response.json()['imagenes'][0]['personas']
        assert people[0]['puntos'] == before['imagenes'][0]['personas'][0]['puntos']
        assert people[1]['puntos'][0]['x'] == 110
        snapshot = client.get(url).json()
        events = client.get('/bitacora').json()
        for body in [{**actor, 'persona_id': 'missing'}, {**actor, 'rol': 'ingenieria', 'persona_id': 'persona-1'}]:
            rejected = client.put(selection, json=body)
            assert rejected.status_code in (403, 422)
            assert client.get(url).json() == snapshot
            assert client.get('/bitacora').json() == events
        rejected = client.put(f'{url}/puntos/lateral', json={**actor, 'persona_id': 'persona-1', 'puntos': points})
        assert rejected.status_code == 422
        assert client.get(url).json() == snapshot
        assert client.get('/bitacora').json() == events
        for body in [{**actor, 'puntos': points},
                     {**actor, 'persona_id': 'persona-2', 'puntos': points + points},
                     {**actor, 'persona_id': 'persona-2', 'puntos': [{**points[0], 'x': -1}]}]:
            rejected = client.put(f'{url}/puntos/lateral', json=body)
            assert rejected.status_code == 422
            assert client.get(url).json() == snapshot
            assert client.get('/bitacora').json() == events
        response = client.put(selection, json={**actor, 'persona_id': None})
        assert response.status_code == 200
        assert response.json()['imagenes'][0]['puntos'] == []
        assert response.json()['imagenes'][0]['personas'] == people


def test_quick_analysis_delivers_all_poses_without_implicit_target_or_unprotected_photo(tmp_path):
    from backend.app.vision.estimador import PersonaDetectada
    client = TestClient(create_app(workspace_dir=tmp_path, sembrar=False))
    def multiple(image):
        result = _pose(image)
        result.personas = 2
        result.poses = [PersonaDetectada('persona-1', result.puntos),
                        PersonaDetectada('persona-2', [PuntoDetectado(5, 100, 100, .9)])]
        result.regiones_privacidad = []
        return result
    with mock.patch.object(mod_estimador.estimador, 'analizar', side_effect=multiple), client:
        response = client.post('/vision/analizar-rapido', files={'foto': ('x.jpg', _photo(), 'image/jpeg')})
        assert response.status_code == 200, response.text
        body = response.json()
        assert body['imagen_anotada_b64'] is None
        assert [p['id'] for p in body['poses']] == ['persona-1', 'persona-2']
        assert all(a['grados'] is None for a in body['angulos'])
        assert body['reba_final'] is None
        assert 'persona' in body['missing_evidence']
        assert 'privacidad' in body['missing_evidence']
        assert client.get('/casos').json() == []
        assert client.get('/bitacora').json() == []


def test_quick_single_person_keeps_photo_protected_and_requires_manual_target(tmp_path):
    from backend.app.vision.privacidad import proteger_imagen
    client = TestClient(create_app(workspace_dir=tmp_path, sembrar=False))
    def single(image):
        result = _pose(image)
        result.regiones_privacidad = [(700, 250, 800, 350)]
        result.imagen_bgr = proteger_imagen(image, result.regiones_privacidad)
        return result
    with mock.patch.object(mod_estimador.estimador, 'analizar', side_effect=single), client:
        response = client.post('/vision/analizar-rapido', files={'foto': ('x.jpg', _photo(), 'image/jpeg')})
        assert response.status_code == 200, response.text
        body = response.json()
        assert body['poses'][0]['id'] == 'persona-1'
        assert body['poses'][0]['puntos'][0]['x'] == 790
        assert body['imagen_anotada_b64'].startswith('data:image/jpeg;base64,')
        assert all(a['grados'] is None for a in body['angulos'])
        assert not body['risk_ready']
        assert 'persona' in body['missing_evidence']
        assert 'privacidad' not in body['missing_evidence']
        assert client.get('/casos').json() == []
        assert client.get('/bitacora').json() == []


def test_legacy_image_contract_remains_readable_without_a_migration():
    from backend.app.api.schemas import Imagen
    original = {'vista': 'lateral', 'url': 'fixture.jpg', 'ancho': 1280, 'alto': 720,
                'puntos': [{'id': 5, 'x': 700, 'y': 330, 'confianza': .9}]}
    image = Imagen.model_validate(original)
    assert image.persona_seleccionada == 'legacy'
    assert image.puntos == image.personas[0].puntos
    assert 'personas' not in original
    empty = Imagen.model_validate({**original, 'puntos': []})
    assert empty.personas == []
    assert empty.persona_seleccionada is None


def test_new_case_without_operational_evidence_has_no_final_risk_score():
    workspace = Path(tempfile.mkdtemp(prefix="ergoai_evidence_"))
    client = TestClient(create_app(workspace_dir=workspace, sembrar=False))
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
    client = TestClient(create_app(workspace_dir=tmp_path, sembrar=False))
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


def test_frontal_evidence_does_not_match_identity_or_change_context_automatically(tmp_path):
    client = TestClient(create_app(workspace_dir=tmp_path, sembrar=False))
    with mock.patch.object(mod_estimador.EstimadorPose, "estado", staticmethod(lambda: (True, "simulated"))), \
         mock.patch.object(mod_estimador.estimador, "analizar", side_effect=_pose), \
         mock.patch("backend.app.services.casos.medir_vista_frontal", return_value={
             "inclinacion_tronco": 30, "abduccion_brazo": 60,
         }), client:
        case_id = _create_evidence_case(client, "frontal")
        detail = client.get(f"/casos/{case_id}").json()
    modifiers = detail["contexto"]["modificadores"]
    assert modifiers["tronco_torsion_o_inclinacion"] is False
    assert modifiers["brazo_abducido_o_rotado"] is False
    assert "modificadores.tronco_torsion_o_inclinacion" in detail["contexto_faltante"]
    assert "modificadores.brazo_abducido_o_rotado" in detail["contexto_faltante"]
    assert all(i['persona_seleccionada'] is None for i in detail['imagenes'])


def test_unknown_context_modifier_is_rejected_not_ignored(tmp_path):
    client = TestClient(create_app(workspace_dir=tmp_path, sembrar=False))
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
        url = f"/casos/{case_id}"
        assert client.put(f"{url}/contexto", json={
            **actor, "contexto": context, "motivo": "Verificado en piso",
        }).status_code == 200
        selected = client.put(f'{url}/persona/lateral', json={**actor, 'persona_id': 'persona-1'})
        assert selected.status_code == 200, selected.text
        angles = selected.json()["angulos"]
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
