from fastapi.testclient import TestClient
from backend.main import create_app


def test_reports_route_exists(tmp_path):
    with TestClient(create_app(workspace_dir=tmp_path, sembrar=False)) as client:
        response = client.get("/casos/C-999/informe")
    assert response.status_code in (404, 422)
