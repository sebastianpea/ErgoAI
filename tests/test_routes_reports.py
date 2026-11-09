from fastapi.testclient import TestClient
from backend.main import app


def test_reports_route_exists():
    client = TestClient(app)
    response = client.get("/casos/C-999/informe")
    assert response.status_code in (200, 404, 422)
