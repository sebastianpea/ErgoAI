from pathlib import Path

from backend.app.exporters.jabil_xlsm_filler import JabilXlsmFiller


def test_xlsm_filler_opens_template_and_writes_sheets(tmp_path):
    filler = JabilXlsmFiller()
    template = Path("casos_jabil_workspace/templates/16-PE80-6500-00014-H_base.xlsm")
    output = tmp_path / "rellenado.xlsx"
    filler.fill(case_id="C-001", template_path=str(template), output_path=str(output))
    assert output.exists()


def test_xlsm_filler_has_required_sheets(tmp_path):
    filler = JabilXlsmFiller()
    template = Path("casos_jabil_workspace/templates/16-PE80-6500-00014-H_base.xlsm")
    output = tmp_path / "rellenado.xlsx"
    filler.fill(case_id="C-001", template_path=str(template), output_path=str(output))
    from openpyxl import load_workbook
    wb = load_workbook(output)
    required = ["Mov", "Levantamiento (1)", "Transporte (2)", "Resultado"]
    for sheet in required:
        assert sheet in wb.sheetnames, f"Missing sheet: {sheet}"
