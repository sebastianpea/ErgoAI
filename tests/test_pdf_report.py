from backend.app.exporters.pdf_report_builder import PdfReportBuilder


def test_pdf_report_builds_without_case_data(tmp_path):
    builder = PdfReportBuilder()
    output_path = tmp_path / "informe_caso.pdf"
    builder.build(case_id="C-000", output_path=str(output_path))
    assert output_path.exists()
    assert output_path.read_bytes()[:4] == b"%PDF"


def test_pdf_report_contains_expected_sections(tmp_path):
    builder = PdfReportBuilder()
    output_path = tmp_path / "informe_caso.pdf"
    builder.build(case_id="C-000", output_path=str(output_path))
    content = output_path.read_bytes()
    for section in [b"REBA", b"NOM-036", b"Bitacora"]:
        assert section in content, f"Missing section: {section}"
