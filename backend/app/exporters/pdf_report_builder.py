from pathlib import Path

from backend.app.services.casos import ServicioCasos
from backend.app.session_store.audit_file_manager import AuditFileManager
from backend.app.settings import WORKSPACE_DIR, CONFIG_DIR
from backend.app.session_store.config_loader import NormativeConfigLoader


class PdfReportBuilder:
    def __init__(self, servicio: ServicioCasos | None = None):
        if servicio is None:
            try:
                config = NormativeConfigLoader(CONFIG_DIR)
                mgr = AuditFileManager(workspace_root=WORKSPACE_DIR)
                servicio = ServicioCasos(mgr, config)
            except Exception:
                servicio = None
        self.servicio = servicio

    def build(self, case_id: str, output_path: str) -> str:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        detalle = None
        if self.servicio is not None:
            try:
                detalle = self.servicio.obtener(case_id)
            except Exception:
                detalle = None

        # Intenta generar PDF real con reportlab; si no está disponible, fallback mínimo.
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.pdfgen import canvas

            c = canvas.Canvas(str(path), pagesize=letter)
            width, height = letter
            y = height - 50

            c.setFont("Helvetica-Bold", 16)
            c.drawString(50, y, "ErgoAI - Informe de Evaluación Ergonómica")
            y -= 20
            c.setFont("Helvetica", 10)
            c.drawString(50, y, f"Caso: {case_id}  Estación: {detalle.estacion if detalle else '—'}  Fecha: {detalle.fecha if detalle else '—'}")
            y -= 30

            # REBA
            c.setFont("Helvetica-Bold", 12)
            c.drawString(50, y, "REBA")
            y -= 15
            c.setFont("Helvetica", 10)
            if detalle and detalle.reba:
                c.drawString(50, y, f"Puntaje final: {detalle.reba.final}  Nivel: {detalle.reba.nivel}")
            else:
                c.drawString(50, y, "Sin cálculo REBA disponible")
            y -= 25

            # NOM-036
            c.setFont("Helvetica-Bold", 12)
            c.drawString(50, y, "NOM-036-1-STPS-2018")
            y -= 15
            c.setFont("Helvetica", 10)
            if detalle and detalle.nom036:
                c.drawString(50, y, f"Método: {detalle.nom036.metodo}  Total: {detalle.nom036.total}  Nivel: {detalle.nom036.nivel}")
            else:
                c.drawString(50, y, "Sin evaluación NOM-036")
            y -= 25

            # Bitácora / Trazabilidad
            c.setFont("Helvetica-Bold", 12)
            c.drawString(50, y, "Bitácora / Trazabilidad del Especialista")
            y -= 15
            c.setFont("Helvetica", 10)
            c.drawString(50, y, "Validación humana obligatoria para riesgos Alto/Muy Alto.")
            y -= 20
            c.drawString(50, y, "Firma Ergonomía: ____________________    Firma Ingeniería: ____________________")

            c.showPage()
            c.save()
            return str(path)

        except ImportError:
            content = (
                b"%PDF-1.4\n"
                b"ErgoAI Informe Caso: " + case_id.encode("utf-8") + b"\n"
                b"Estacion: " + (detalle.estacion.encode("utf-8") if detalle else b"-") + b"\n"
                b"REBA\n"
                b"NOM-036\n"
                b"Bitacora\n"
                b"%EOF\n"
            )
            path.write_bytes(content)
            return str(path)
