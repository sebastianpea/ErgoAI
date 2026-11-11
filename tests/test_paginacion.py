"""Query contracts through HTTP; all fixtures live outside the repository."""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.app.api.schemas import CasoAlmacenado, RecomendacionAlmacenada
from backend.app.session_store import AuditFileManager


@pytest.fixture
def tmp_path():
    with tempfile.TemporaryDirectory(prefix="ergoai_paginacion_") as directory:
        yield Path(directory)


@pytest.fixture
def workspace(tmp_path):
    mgr = AuditFileManager(tmp_path)
    # Reverse creation order and identical dates exercise the deterministic ID tie-break.
    for n in reversed(range(1, 106)):
        case_id = f"C-{n:03d}"
        mgr.init_case_workspace(case_id)
        caso = CasoAlmacenado(
            id_caso=case_id, estacion="Estación prueba", fecha="2026-01-01", imagenes=[],
            tipo_tarea="postura" if n % 2 else "transporte",
            recomendaciones=[RecomendacionAlmacenada(
                id="R1", nivel_control="ingenieria", tipo_cambio="planta", titulo="Ajuste",
                texto="Ajustar estación", texto_ia="Ajustar estación", referencia="Prueba")],
        )
        mgr.write_json_atomic(mgr.get_case_dir(case_id) / "caso.json", caso.model_dump(mode="json"))
    return tmp_path


@pytest.fixture
def client(workspace):
    with TestClient(create_app(workspace_dir=workspace, sembrar=False)) as client:
        yield client


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def get_ok(client, path):
    response = client.get(path)
    assert response.status_code == 200, response.text
    return response.json()


def test_page_bounds_order_and_payload_budget(client):
    svc = client.app.state.servicio
    with patch.object(svc, "_cargar", wraps=svc._cargar) as loads, \
         patch.object(svc, "_evaluar", wraps=svc._evaluar) as evaluations:
        originals = snapshot(client.app.state.servicio.mgr.workspace_root)
        first = get_ok(client, "/casos/pagina")
        assert all(snapshot(client.app.state.servicio.mgr.workspace_root)[k] == v for k, v in originals.items())
        assert loads.call_count == evaluations.call_count == 10  # only the cold requested page
        get_ok(client, "/metricas/dashboard")  # explicitly warm the remaining legacy entries
        assert loads.call_count == evaluations.call_count == 105
        assert (first["total"], first["page"], first["page_size"], first["total_pages"]) == (105, 1, 10, 11)
        assert [c["id_caso"] for c in first["items"]] == [f"C-{n:03d}" for n in range(1, 11)]
        loads.reset_mock()
        evaluations.reset_mock()
        for size in (1, 100):
            page = get_ok(client, f"/casos/pagina?page=2&page_size={size}")
            assert [c["id_caso"] for c in page["items"]] == [
                f"C-{n:03d}" for n in range(size + 1, min(2 * size, 105) + 1)]
            assert page["total_pages"] == (105 + size - 1) // size
        beyond = get_ok(client, "/casos/pagina?page=999&page_size=100")
        assert beyond == {"items": [], "total": 105, "page": 999, "page_size": 100, "total_pages": 2}
        assert loads.call_count == evaluations.call_count == 0


@pytest.mark.parametrize("warm", [False, True], ids=["cold", "warm"])
def test_page_reads_only_selected_summary_files(client, workspace, warm):
    expected_dashboard = {
        "total_casos": 105,
        "niveles": {"sin_evaluar": 105, "inapreciable": 0, "bajo": 0, "medio": 0, "alto": 0, "muy_alto": 0},
        "tipos_tarea": {"postura": 53, "transporte": 52},
        "decisiones_pendientes": 105, "por_autorizar": 0,
    }
    if warm:
        assert get_ok(client, "/metricas/dashboard") == expected_dashboard
    before = snapshot(workspace)
    summary_reads = []
    original_open = Path.open

    def counted_open(path, mode="r", *args, **kwargs):
        if path.name == "resumen_consulta.json" and "r" in mode:
            summary_reads.append(path.parent.name)
        return original_open(path, mode, *args, **kwargs)

    svc = client.app.state.servicio
    with patch.object(Path, "open", counted_open), \
         patch.object(svc, "_cargar", wraps=svc._cargar) as loads, \
         patch.object(svc, "_evaluar", wraps=svc._evaluar) as evaluations:
        page = get_ok(client, "/casos/pagina?page=2&page_size=2")
        assert summary_reads == ["C-003", "C-004"]
        assert loads.call_count == evaluations.call_count == (0 if warm else 2)
        assert [item["id_caso"] for item in page["items"]] == ["C-003", "C-004"]
        assert (page["total"], page["page"], page["page_size"], page["total_pages"]) == (105, 2, 2, 53)
        summary_reads.clear()
        loads.reset_mock()
        evaluations.reset_mock()
        beyond = get_ok(client, "/casos/pagina?page=999&page_size=2")
        assert beyond == {"items": [], "total": 105, "page": 999, "page_size": 2, "total_pages": 53}
        assert summary_reads == []
        assert loads.call_count == evaluations.call_count == 0
        assert get_ok(client, "/metricas/dashboard") == expected_dashboard
        assert len(summary_reads) == 105
        assert loads.call_count == evaluations.call_count == (0 if warm else 103)
        summary_reads.clear()
        loads.reset_mock()
        evaluations.reset_mock()
        assert get_ok(client, "/metricas/dashboard") == expected_dashboard
        assert len(summary_reads) == 105
        assert loads.call_count == evaluations.call_count == 0
    after = snapshot(workspace)
    assert all(after[name] == data for name, data in before.items() if not name.endswith("resumen_consulta.json"))


def test_global_dashboard_no_warm_payload_or_geometry_reads(client):
    all_cases = get_ok(client, "/casos")  # preserved legacy consumer
    get_ok(client, "/metricas/dashboard")  # warm the entire aggregate, not just one page
    svc = client.app.state.servicio
    with patch.object(svc, "_cargar", wraps=svc._cargar) as loads, \
         patch.object(svc, "_evaluar", wraps=svc._evaluar) as evaluations, \
         patch("cv2.imread", side_effect=AssertionError("warm query read image")):
        expected = {
            "total_casos": 105,
            "niveles": {"sin_evaluar": 105, "inapreciable": 0, "bajo": 0, "medio": 0, "alto": 0, "muy_alto": 0},
            "tipos_tarea": {"postura": 53, "transporte": 52},
            "decisiones_pendientes": 105, "por_autorizar": 0,
        }
        assert get_ok(client, "/metricas/dashboard") == expected
        for page in (1, 2, 999):
            get_ok(client, f"/casos/pagina?page={page}")
            assert get_ok(client, "/metricas/dashboard") == expected
        assert loads.call_count == evaluations.call_count == 0
    assert get_ok(client, "/casos/pagina?page_size=100")["items"] == all_cases[:100]
    assert get_ok(client, "/casos/C-001")["id_caso"] == "C-001"
    assert get_ok(client, "/metricas/impacto")["casos"] == []
    assert get_ok(client, "/bitacora/verificar")["ok"]


@pytest.mark.parametrize("query,field,kind", [
    ("page=0", "page", "greater_than_equal"),
    ("page=-1", "page", "greater_than_equal"),
    ("page_size=0", "page_size", "greater_than_equal"),
    ("page_size=101", "page_size", "less_than_equal"),
    ("page=1.5", "page", "int_parsing"),
])
def test_invalid_bounds_do_not_mutate(client, workspace, query, field, kind):
    before = snapshot(workspace)
    response = client.get("/casos/pagina?" + query)
    assert response.status_code == 422, response.text
    error = response.json()["detail"]
    assert len(error) == 1
    assert error[0]["loc"] == ["query", field]
    assert error[0]["type"] == kind
    assert snapshot(workspace) == before
    assert get_ok(client, "/casos")[0]["decisiones_pendientes"] == 1


def test_empty(tmp_path):
    with TestClient(create_app(workspace_dir=tmp_path, sembrar=False)) as client:
        assert get_ok(client, "/casos/pagina") == {
            "items": [], "total": 0, "page": 1, "page_size": 10, "total_pages": 0}
        dashboard = get_ok(client, "/metricas/dashboard")
        assert dashboard["total_casos"] == dashboard["decisiones_pendientes"] == dashboard["por_autorizar"] == 0
        assert dashboard["tipos_tarea"] == {}
        assert sum(dashboard["niveles"].values()) == 0


def test_mutation_and_restart(client, workspace):
    get_ok(client, "/metricas/dashboard")
    response = client.post("/casos/C-001/recomendaciones/R1/decision", json={
        "id_caso": "C-001", "id_recomendacion": "R1", "accion": "aprobar", "usuario": "Ergonomía"})
    assert response.status_code == 200 and response.json() == {"ok": True}
    dashboard = get_ok(client, "/metricas/dashboard")
    assert dashboard["decisiones_pendientes"] == 104
    assert dashboard["por_autorizar"] == 1
    assert get_ok(client, "/casos/pagina?page_size=1")["items"][0]["por_autorizar"] == 1
    # Same segregation-of-duties contract, and rejected mutations leave derived data untouched.
    before = snapshot(workspace)
    rejected = client.post("/casos/C-001/recomendaciones/R1/autorizacion", json={
        "accion": "autorizar", "usuario": "Ergonomía", "rol": "ingenieria"})
    assert rejected.status_code == 409
    assert snapshot(workspace) == before
    response = client.post("/casos/C-001/recomendaciones/R1/autorizacion", json={
        "accion": "autorizar", "usuario": "Ingeniería", "rol": "ingenieria"})
    assert response.status_code == 200 and response.json() == {"ok": True}
    response = client.post("/casos/C-001/recomendaciones/R1/implementacion", json={"usuario": "Ergonomía"})
    assert response.status_code == 200 and response.json() == {"ok": True}
    expected = get_ok(client, "/metricas/dashboard")
    assert expected["por_autorizar"] == 0
    with TestClient(create_app(workspace_dir=workspace, sembrar=False)) as restarted:
        svc = restarted.app.state.servicio
        with patch.object(svc, "_cargar", wraps=svc._cargar) as loads, \
             patch.object(svc, "_evaluar", wraps=svc._evaluar) as evaluations:
            assert get_ok(restarted, "/metricas/dashboard") == expected
            assert loads.call_count == evaluations.call_count == 0


@pytest.mark.parametrize("damage", ["missing", "corrupt", "stale", "invalid_schema"])
def test_summary_rebuild_only_stale_case(client, workspace, damage):
    get_ok(client, "/metricas/dashboard")
    original = snapshot(workspace)
    summary = workspace / "C-001" / "resumen_consulta.json"
    if damage == "missing":
        summary.unlink()
    elif damage == "corrupt":
        summary.write_text("{", encoding="utf-8")
    elif damage == "invalid_schema":
        summary.write_text('{"version": 1}', encoding="utf-8")
    else:
        path = workspace / "C-001" / "caso.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["estacion"] = "Estación actualizada"
        AuditFileManager(workspace).write_json_atomic(path, data)
    before = snapshot(workspace)
    svc = client.app.state.servicio
    with patch.object(svc, "_cargar", wraps=svc._cargar) as loads, \
         patch.object(svc, "_evaluar", wraps=svc._evaluar) as evaluations:
        page = get_ok(client, "/casos/pagina?page_size=1")
        assert loads.call_count == evaluations.call_count == 1
        assert page["items"][0]["estacion"] == ("Estación actualizada" if damage == "stale" else "Estación prueba")
        get_ok(client, "/metricas/dashboard")
        assert loads.call_count == evaluations.call_count == 1
    after = snapshot(workspace)
    assert {k: v for k, v in before.items() if not k.endswith("resumen_consulta.json")} == {
        k: v for k, v in after.items() if not k.endswith("resumen_consulta.json")}
    assert original.keys() == after.keys()


@pytest.mark.parametrize("mutation", ["points", "context", "reference", "nom036", "finding", "recommendation", "plan", "confirm"])
def test_all_mutation_consumers_refresh_and_preserve_contracts(tmp_path, mutation):
    from tests.test_vision import ERGO, _confirmar_angulos, _contexto_confirmado, _foto_jpg, _resultado
    from backend.app.vision.estimador import estimador

    with TestClient(create_app(workspace_dir=tmp_path, sembrar=False)) as client:
        with patch.object(estimador, "estado", return_value=(True, "simulado")), \
             patch.object(estimador, "analizar", side_effect=_resultado):
            response = client.post("/casos", data={"datos": json.dumps({
                **ERGO, "estacion": "Estación real", "tipo_tarea": "levantamiento",
                "contexto": _contexto_confirmado()})},
                files={"lateral": ("foto.jpg", _foto_jpg(), "image/jpeg")})
        assert response.status_code == 200 and response.json() == {"ok": True, "id": "C-001"}
        detail = _confirmar_angulos(client, "C-001")
        get_ok(client, "/metricas/dashboard")
        if mutation == "points":
            points = detail["imagenes"][0]["puntos"]
            points[5]["x"] -= 20
            response = client.put("/casos/C-001/puntos/lateral", json={
                "persona_id": detail["imagenes"][0]["persona_seleccionada"], "puntos": points,
            })
            assert response.json()["imagenes"][0]["puntos"][5]["corregido"]
        elif mutation == "context":
            context = {**detail["contexto"], "carga_kg": 0, "actividad": 0}
            response = client.put("/casos/C-001/contexto", json={"contexto": context, "motivo": "Corregir carga"})
            assert response.json()["contexto"] == context
        elif mutation == "reference":
            response = client.put("/casos/C-001/referencia", json={
                "evaluacion_previa": {"reba_final": 1}, "motivo": "Captura referencia"})
            assert response.json()["evaluacion_previa"]["reba_final"] == 1
        elif mutation == "nom036":
            factors = get_ok(client, "/catalogo/nom036")["levantamiento"]["factores"]
            capture = {"metodo": "levantamiento", "factores": [
                {"codigo": f["codigo"], "etiqueta": f["etiqueta"], "color": "verde", "valor": f["opciones"]["verde"]}
                for f in factors]}
            response = client.put("/casos/C-001/nom036", json={"nom036": capture, "motivo": "Captura manual"})
            assert response.json()["nom036"]["factores"] == capture["factores"]
        elif mutation == "finding":
            finding = detail["hallazgos"][0]["id"]
            response = client.post(f"/casos/C-001/hallazgos/{finding}/revision", json={
                "accion": "descartar", "motivo": "Verificado manualmente"})
            assert next(h for h in response.json()["hallazgos"] if h["id"] == finding)["descartado"]
        elif mutation == "recommendation":
            response = client.post("/casos/C-001/recomendaciones", json={
                "nivel_control": "ingenieria", "tipo_cambio": "planta", "titulo": "Nueva mesa",
                "texto": "Elevar la mesa", "motivo": "Mejorar postura"})
            assert response.json() == {"ok": True, "id": "E1"}
        elif mutation == "confirm":
            angle = next(a for a in detail["angulos"] if a["angulo_grados"] is not None)
            response = client.post(f"/casos/C-001/angulos/lateral/{angle['segmento']}/confirmar", json=ERGO)
            assert next(a for a in response.json()["angulos"] if a["segmento"] == angle["segmento"])["confirmado"]
        else:
            with patch("backend.app.core_agent.llm_factory.LLMFactory.get_llm", return_value=lambda value: value), \
                 patch("backend.app.core_agent.ergo_agent.ErgoAIAgent.evaluar_caso", return_value={
                     "titulo": "Elevar superficie", "descripcion_tecnica": "Ajustar la mesa", "fundamento_normativo": "NOM-036"}):
                response = client.post("/casos/C-001/generar-plan-ia", json={})
            assert response.json()["recomendaciones"]
        assert response.status_code == 200, response.text
        legacy = get_ok(client, "/casos")
        svc = client.app.state.servicio
        with patch.object(svc, "_cargar", side_effect=AssertionError("warm mutation payload")), \
             patch.object(svc, "_evaluar", side_effect=AssertionError("warm mutation evaluation")), \
             patch("cv2.imread", side_effect=AssertionError("warm mutation image")):
            assert get_ok(client, "/casos/pagina")["items"] == legacy
            expected = get_ok(client, "/metricas/dashboard")
        assert expected["niveles"][legacy[0]["nivel"]] == 1
        assert expected["decisiones_pendientes"] == legacy[0]["decisiones_pendientes"]
        assert expected["por_autorizar"] == legacy[0]["por_autorizar"]
        assert get_ok(client, "/bitacora/verificar")["ok"]
    with TestClient(create_app(workspace_dir=tmp_path, sembrar=False)) as restarted:
        with patch.object(restarted.app.state.servicio, "_cargar", side_effect=AssertionError("restart payload")):
            assert get_ok(restarted, "/metricas/dashboard") == expected
            assert get_ok(restarted, "/casos/pagina")["items"] == legacy


def test_legacy_geometry_rebuild_and_media_invalidation(tmp_path):
    import cv2
    import numpy as np
    from tests.test_vision import _foto_jpg, _resultado
    from backend.app.vision.estimador import estimador

    with TestClient(create_app(workspace_dir=tmp_path, sembrar=False)) as client:
        with patch.object(estimador, "estado", return_value=(True, "simulado")), \
             patch.object(estimador, "analizar", side_effect=_resultado):
            created = client.post("/casos", data={"datos": json.dumps({"estacion": "Mesa legacy"})},
                                  files={"lateral": ("foto.jpg", _foto_jpg(), "image/jpeg")})
        assert created.status_code == 200
        # Simulate a pre-summary workspace without touching its original case/audit/privacy files.
        (tmp_path / "C-001" / "resumen_consulta.json").unlink()
        before = snapshot(tmp_path)
        svc = client.app.state.servicio
        with patch.object(svc, "_cargar", wraps=svc._cargar) as loads, \
             patch.object(svc, "_evaluar", wraps=svc._evaluar) as evaluations, \
             patch("cv2.imread", wraps=cv2.imread) as images:
            get_ok(client, "/metricas/dashboard")
            assert loads.call_count == evaluations.call_count == images.call_count == 1
            get_ok(client, "/casos/pagina")
            assert loads.call_count == evaluations.call_count == images.call_count == 1
        assert all(snapshot(tmp_path)[k] == v for k, v in before.items())
        # A changed image must invalidate even if caso.json is unchanged.
        assert cv2.imwrite(str(tmp_path / "C-001" / "inputs" / "lateral.jpg"), np.zeros((20, 20, 3), np.uint8))
        changed = snapshot(tmp_path)
        with patch.object(svc, "_cargar", wraps=svc._cargar) as loads, \
             patch.object(svc, "_evaluar", wraps=svc._evaluar) as evaluations:
            page = get_ok(client, "/casos/pagina")
            assert loads.call_count == evaluations.call_count == 1
            get_ok(client, "/metricas/dashboard")
            assert loads.call_count == evaluations.call_count == 1
        assert page["items"] == get_ok(client, "/casos")
        detail = get_ok(client, "/casos/C-001")
        assert detail["imagenes"][0]["puntos"] == []
        assert all(snapshot(tmp_path)[k] == v for k, v in changed.items() if not k.endswith("resumen_consulta.json"))


def test_corrupt_source_is_not_fabricated(client, workspace):
    get_ok(client, "/metricas/dashboard")
    source = workspace / "C-001" / "caso.json"
    source.write_text("{", encoding="utf-8")
    before = snapshot(workspace)
    with pytest.raises(json.JSONDecodeError):
        client.get("/metricas/dashboard")
    assert snapshot(workspace) == before
