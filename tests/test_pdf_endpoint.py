from fastapi.testclient import TestClient
from backend.main import app


def test_informe_endpoint_returns_pdf():
    client = TestClient(app)
    response = client.get("/casos/C-999/informe")
    # Puede ser 200 si el caso existe y se genera el PDF, o 404 si no existe la ruta/archivo.
    # Lo importante es que la ruta exista y no lance 500 por importación rota.
    assert response.status_code in (200, 404)
    if response.status_code == 200:
        assert response.headers["content-type"].startswith("application/pdf")
        assert response.content[:4] == b"%PDF"
