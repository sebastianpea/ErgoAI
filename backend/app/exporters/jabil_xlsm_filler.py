from pathlib import Path

from backend.app.services.casos import ServicioCasos
from backend.app.session_store.audit_file_manager import AuditFileManager
from backend.app.settings import WORKSPACE_DIR, CONFIG_DIR
from backend.app.session_store.config_loader import NormativeConfigLoader

from openpyxl import Workbook, load_workbook


class JabilXlsmFiller:
    REQUIRED_SHEETS = [
        "Mov",
        "Levantamiento (1)",
        "Transporte (2)",
        "Equipo (3)",
        "sin auxiliar (4)",
        "con auxiliar (5)",
        "EAWS",
        "Resultado",
        "OBSERVACIONES Y MEJORAS",
    ]

    def __init__(self, servicio: ServicioCasos | None = None):
        if servicio is None:
            try:
                config = NormativeConfigLoader(CONFIG_DIR)
                mgr = AuditFileManager(workspace_root=WORKSPACE_DIR)
                servicio = ServicioCasos(mgr, config)
            except Exception:
                servicio = None
        self.servicio = servicio

    def fill(self, case_id: str, template_path: str, output_path: str) -> str:
        template = Path(template_path)
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        detalle = None
        if self.servicio is not None:
            try:
                detalle = self.servicio.obtener(case_id)
            except Exception:
                detalle = None

        if template.exists():
            wb = load_workbook(template)
            # Ensure required sheets exist
            for sheet in self.REQUIRED_SHEETS:
                if sheet not in wb.sheetnames:
                    wb.create_sheet(sheet)
        else:
            wb = Workbook()
            wb.remove(wb.active)
            for sheet in self.REQUIRED_SHEETS:
                wb.create_sheet(sheet)

        # Fill Mov sheet with basic case data
        if "Mov" in wb.sheetnames:
            ws = wb["Mov"]
            ws["A1"] = "Caso"
            ws["B1"] = case_id
            ws["A2"] = "Estacion"
            ws["B2"] = detalle.estacion if detalle else "-"
            ws["A3"] = "Fecha"
            ws["B3"] = detalle.fecha if detalle else "-"

        # Fill Resultado sheet
        if "Resultado" in wb.sheetnames:
            ws = wb["Resultado"]
            ws["A1"] = "Resultado consolidado"
            ws["A2"] = "Caso"
            ws["B2"] = case_id
            if detalle and detalle.reba:
                ws["A3"] = "REBA final"
                ws["B3"] = detalle.reba.final
                ws["A4"] = "Nivel REBA"
                ws["B4"] = detalle.reba.nivel
            if detalle and detalle.nom036:
                ws["A5"] = "NOM-036 metodo"
                ws["B5"] = detalle.nom036.metodo
                ws["A6"] = "NOM-036 total"
                ws["B6"] = detalle.nom036.total
                ws["A7"] = "NOM-036 nivel"
                ws["B7"] = detalle.nom036.nivel

        # Fill Observaciones y Mejoras
        if "OBSERVACIONES Y MEJORAS" in wb.sheetnames:
            ws = wb["OBSERVACIONES Y MEJORAS"]
            ws["A1"] = "Plan de accion y observaciones"
            ws["A2"] = "Caso"
            ws["B2"] = case_id
            ws["A3"] = "Responsable"
            ws["B3"] = "-"
            ws["A4"] = "Fecha compromiso"
            ws["B4"] = "-"

        wb.save(output)
        return str(output)
