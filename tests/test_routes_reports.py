from unittest.mock import patch

from fastapi.testclient import TestClient
from backend.main import app


def test_reports_route_exists():
    client = TestClient(app)
    response = client.get("/casos/C-999/informe")
    assert response.status_code in (200, 404, 422)


def test_legacy_report_routes_reject_invalid_case_ids_without_running_exporters():
    client = TestClient(app, raise_server_exceptions=False)
    with (
        patch("backend.app.api.routes_reports.PdfReportBuilder.build", side_effect=AssertionError),
        patch("backend.app.api.routes_reports.JabilXlsmFiller.fill", side_effect=AssertionError),
    ):
        for route in ("informe", "excel-jabil"):
            response = client.get(f"/casos/C-001.bad/{route}")
            assert response.status_code == 422
            assert response.json()["detail"][0]["loc"] == ["path", "id_caso"]


def test_legacy_report_routes_keep_valid_id_responses_without_writing_workspace(tmp_path):
    pdf_path = tmp_path / "report.pdf"
    pdf_path.write_bytes(b"%PDF fixture")
    xlsx_path = tmp_path / "report.xlsx"
    xlsx_path.write_bytes(b"PK fixture")
    client = TestClient(app)
    with (
        patch("backend.app.api.routes_reports.PdfReportBuilder.build", return_value=str(pdf_path)) as build_pdf,
        patch("backend.app.api.routes_reports.JabilXlsmFiller.fill", return_value=str(xlsx_path)) as fill_xlsx,
    ):
        pdf = client.get("/casos/C-001/informe")
        xlsx = client.get("/casos/C-001/excel-jabil")
    assert (pdf.status_code, pdf.content, pdf.headers["content-type"]) == (200, b"%PDF fixture", "application/pdf")
    assert (xlsx.status_code, xlsx.content, xlsx.headers["content-type"]) == (
        200, b"PK fixture", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    build_pdf.assert_called_once_with("C-001", "casos_jabil_workspace/C-001/outputs/informe.pdf")
    fill_xlsx.assert_called_once_with(
        "C-001", "casos_jabil_workspace/templates/16-PE80-6500-00014-H_base.xlsm",
        "casos_jabil_workspace/C-001/outputs/evaluacion_jabil.xlsx",
    )
