import base64
import re
import zlib

from backend.app.exporters.pdf_report_builder import PdfReportBuilder


def _pdf_content(content: bytes) -> bytes:
    streams = []
    for match in re.finditer(rb"stream\r?\n(.*?)endstream", content, re.DOTALL):
        stream = match.group(1).strip()
        if stream.endswith(b"~>"):
            stream = base64.a85decode(stream, adobe=True)
        try:
            stream = zlib.decompress(stream)
        except zlib.error:
            pass
        streams.append(stream)
    return b"\n".join([content, *streams])


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
    content = _pdf_content(output_path.read_bytes())
    for section in [b"REBA", b"NOM-036", b"Bit"]:
        assert section in content, f"Missing section: {section}"
    assert b"cora" in content
