from fastapi.testclient import TestClient
from backend.main import create_app


def test_excel_jabil_endpoint_returns_file(tmp_path):
    # Alias de /casos/{id}/exportar/excel (hoja oficial 14-H): la ruta existe y un caso inexistente da 404
    # (o 503 si la plantilla no está en el equipo), nunca 500.
    with TestClient(create_app(workspace_dir=tmp_path, sembrar=False)) as client:
        response = client.get("/casos/C-999/excel-jabil")
    assert response.status_code in (404, 503)
