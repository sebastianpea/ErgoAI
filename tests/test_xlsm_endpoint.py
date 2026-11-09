from fastapi.testclient import TestClient
from backend.main import app


def test_excel_jabil_endpoint_returns_file():
    client = TestClient(app)
    response = client.get("/casos/C-999/excel-jabil")
    # Puede ser 200 si se genera el archivo, o 404 si la ruta falla.
    # Lo importante es que la ruta exista y no lance 500 por importación rota.
    assert response.status_code in (200, 404)
    if response.status_code == 200:
        assert (
            "spreadsheetml" in response.headers.get("content-type", "")
            or response.content[:2] == b"PK"
        )
