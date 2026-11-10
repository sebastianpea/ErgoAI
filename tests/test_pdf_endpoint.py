from fastapi.testclient import TestClient
from backend.main import create_app


def test_informe_endpoint_returns_pdf(tmp_path):
    # Alias de /casos/{id}/exportar/pdf: la ruta existe y un caso inexistente da 404, no 500.
    with TestClient(create_app(workspace_dir=tmp_path, sembrar=False)) as client:
        response = client.get("/casos/C-999/informe")
    assert response.status_code == 404
