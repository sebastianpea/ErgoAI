# backend/app/services/exportador_excel.py
from __future__ import annotations

import io
from typing import Any
import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from backend.app.api.schemas import CasoDetalle


def generar_excel_caso(caso: CasoDetalle, bitacora_hash: str | None = None) -> io.BytesIO:
    """
    Genera un libro de cálculo Excel (.xlsx) exhaustivo y formateado con la identidad
    visual de Jabil para auditorías legales y de EHS (NOM-036-1-STPS-2018 y REBA).
    """
    wb = openpyxl.Workbook()
    # Eliminar hoja por defecto
    wb.remove(wb.active)

    # Paleta de estilos oficiales Jabil
    NAVY_FILL = PatternFill(start_color="163E6A", end_color="163E6A", fill_type="solid")
    CYAN_FILL = PatternFill(start_color="3CB4E5", end_color="3CB4E5", fill_type="solid")
    LIGHT_GRAY_FILL = PatternFill(start_color="F4F6F8", end_color="F4F6F8", fill_type="solid")
    OK_FILL = PatternFill(start_color="E3F4EA", end_color="E3F4EA", fill_type="solid")
    WARN_FILL = PatternFill(start_color="FDE8E8", end_color="FDE8E8", fill_type="solid")

    FONT_TITLE = Font(name="Roboto", size=14, bold=True, color="FFFFFF")
    FONT_HEADER = Font(name="Roboto", size=11, bold=True, color="FFFFFF")
    FONT_SUBTITLE = Font(name="Roboto", size=11, bold=True, color="163E6A")
    FONT_REGULAR = Font(name="Roboto", size=10, bold=False, color="1F2937")
    FONT_BOLD = Font(name="Roboto", size=10, bold=True, color="1F2937")
    FONT_MUTED = Font(name="Roboto", size=9, italic=True, color="60605B")

    THIN_BORDER = Border(
        left=Side(style="thin", color="E1E5EA"),
        right=Side(style="thin", color="E1E5EA"),
        top=Side(style="thin", color="E1E5EA"),
        bottom=Side(style="thin", color="E1E5EA"),
    )

    # =========================================================================
    # HOJA 1: RESUMEN Y AUDITORÍA
    # =========================================================================
    ws1 = wb.create_sheet(title="Resumen del Caso")
    ws1.views.sheetView[0].showGridLines = True

    # Banner del Título
    ws1.merge_cells("A1:F2")
    cell_title = ws1["A1"]
    cell_title.value = f"INFORME DE EVALUACIÓN ERGONÓMICA INDUSTRIAL — CASO {caso.id_caso}"
    cell_title.font = FONT_TITLE
    cell_title.fill = NAVY_FILL
    cell_title.alignment = Alignment(horizontal="center", vertical="center")

    # Datos Generales
    ws1["A4"] = "DATOS GENERALES DE LA ESTACIÓN"
    ws1["A4"].font = FONT_SUBTITLE
    ws1["A4"].fill = CYAN_FILL

    campos_generales = [
        ("Identificador del Caso", caso.id_caso),
        ("Estación de Trabajo", caso.estacion),
        ("Tipo de Tarea / Operación", caso.tipo_tarea.replace("_", " ").title()),
        ("Fecha de Evaluación", caso.fecha),
        ("Carga Manipulada (kg)", f"{caso.contexto.carga_kg:g} kg"),
        ("Calidad del Agarre", str(caso.contexto.agarre).capitalize()),
        ("Frecuencia / Nivel de Actividad", f"Nivel {caso.contexto.actividad}"),
        ("Apoyo Unilateral", "Sí" if caso.contexto.apoyo_unilateral else "No"),
    ]

    row_idx = 5
    for label, val in campos_generales:
        ws1[f"A{row_idx}"] = label
        ws1[f"A{row_idx}"].font = FONT_BOLD
        ws1[f"A{row_idx}"].fill = LIGHT_GRAY_FILL
        ws1[f"A{row_idx}"].border = THIN_BORDER

        ws1[f"B{row_idx}"] = val
        ws1[f"B{row_idx}"].font = FONT_REGULAR
        ws1[f"B{row_idx}"].border = THIN_BORDER
        row_idx += 1

    # Dictamen Biomecánico y Legal
    ws1["D4"] = "DICTAMEN TÉCNICO Y NORMATIVO"
    ws1["D4"].font = FONT_SUBTITLE
    ws1["D4"].fill = CYAN_FILL

    reba_score = caso.reba.final if caso.reba else "N/A"
    reba_nivel = str(caso.reba.nivel).upper() if caso.reba else "N/A"
    nom_total = caso.nom036.total if caso.nom036 else "N/A"
    nom_nivel = str(caso.nom036.nivel).upper() if caso.nom036 else "N/A"

    campos_dictamen = [
        ("Puntaje Final REBA Inicial", reba_score),
        ("Nivel de Riesgo REBA Inicial", reba_nivel),
        ("Puntaje Total NOM-036-1-STPS", nom_total),
        ("Nivel de Acción NOM-036", nom_nivel),
        ("Estado de Validación del Plan", "APROBADO E IMPLEMENTADO" if caso.validacion.completa else "EN REVISIÓN"),
        ("Recomendaciones Implementadas", f"{caso.validacion.implementadas} aplicadas"),
        ("Sello Criptográfico SHA-256", bitacora_hash or "Verificado en bitácora inmutable"),
    ]

    row_idx = 5
    for label, val in campos_dictamen:
        ws1[f"D{row_idx}"] = label
        ws1[f"D{row_idx}"].font = FONT_BOLD
        ws1[f"D{row_idx}"].fill = LIGHT_GRAY_FILL
        ws1[f"D{row_idx}"].border = THIN_BORDER

        ws1[f"E{row_idx}"] = str(val)
        ws1[f"E{row_idx}"].font = FONT_BOLD if "Puntaje" in label or "Nivel" in label else FONT_REGULAR
        ws1[f"E{row_idx}"].border = THIN_BORDER
        row_idx += 1

    # =========================================================================
    # HOJA 2: EVALUACIÓN REBA (ÁNGULOS BIOMECÁNICOS)
    # =========================================================================
    ws2 = wb.create_sheet(title="Evaluación REBA")
    ws2.views.sheetView[0].showGridLines = True

    headers_reba = ["Segmento Anatómico", "Vista", "Lado", "Ángulo Medido (°)", "Puntos REBA", "Modificadores Biomecánicos", "Estado de Medición"]
    for col_idx, h in enumerate(headers_reba, start=1):
        cell = ws2.cell(row=1, column=col_idx, value=h)
        cell.font = FONT_HEADER
        cell.fill = NAVY_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = THIN_BORDER

    for row_idx, a in enumerate(caso.angulos, start=2):
        ws2.cell(row=row_idx, column=1, value=str(a.segmento).upper()).font = FONT_BOLD
        ws2.cell(row=row_idx, column=2, value=str(a.vista).capitalize()).alignment = Alignment(horizontal="center")
        ws2.cell(row=row_idx, column=3, value=str(a.lado or "N/A").upper()).alignment = Alignment(horizontal="center")

        ang_cell = ws2.cell(row=row_idx, column=4, value=f"{a.angulo_grados:.1f}°" if a.angulo_grados is not None else "N/A")
        ang_cell.alignment = Alignment(horizontal="right")
        ang_cell.font = FONT_REGULAR

        pts_cell = ws2.cell(row=row_idx, column=5, value=a.puntaje_reba)
        pts_cell.alignment = Alignment(horizontal="center")
        pts_cell.font = FONT_BOLD

        mod_txt = ", ".join(a.modificadores) if a.modificadores else "Sin factores adicionales"
        ws2.cell(row=row_idx, column=6, value=mod_txt).font = FONT_REGULAR

        est_cell = ws2.cell(row=row_idx, column=7, value=str(a.estado).upper())
        est_cell.alignment = Alignment(horizontal="center")
        est_cell.fill = OK_FILL if a.estado == "ok" else WARN_FILL

        for c_i in range(1, 8):
            ws2.cell(row=row_idx, column=c_i).border = THIN_BORDER

    # =========================================================================
    # HOJA 3: PLAN DE MITIGACIÓN E IMPLEMENTACIÓN
    # =========================================================================
    ws3 = wb.create_sheet(title="Plan de Mitigación")
    ws3.views.sheetView[0].showGridLines = True

    headers_plan = [
        "Código", "Nivel de Control", "Tipo Cambio", "Título de la Recomendación",
        "Descripción Técnica", "Fundamento Normativo (STPS/Jabil)", "Estado",
        "Implementación", "Aprobado Por", "Autorizado Por (Ing.)", "Implementado Por", "Fecha Compromiso"
    ]

    for col_idx, h in enumerate(headers_plan, start=1):
        cell = ws3.cell(row=1, column=col_idx, value=h)
        cell.font = FONT_HEADER
        cell.fill = NAVY_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = THIN_BORDER

    for row_idx, r in enumerate(caso.recomendaciones, start=2):
        ws3.cell(row=row_idx, column=1, value=r.id).font = FONT_BOLD
        ws3.cell(row=row_idx, column=2, value=str(r.nivel_control).capitalize()).alignment = Alignment(horizontal="center")
        ws3.cell(row=row_idx, column=3, value=str(r.tipo_cambio).capitalize()).alignment = Alignment(horizontal="center")
        ws3.cell(row=row_idx, column=4, value=r.titulo).font = FONT_BOLD
        ws3.cell(row=row_idx, column=5, value=r.texto).font = FONT_REGULAR
        ws3.cell(row=row_idx, column=6, value=r.referencia).font = FONT_MUTED

        ws3.cell(row=row_idx, column=7, value=str(r.estado).upper()).alignment = Alignment(horizontal="center")

        imp_cell = ws3.cell(row=row_idx, column=8, value=str(r.implementacion or "Pendiente").upper())
        imp_cell.alignment = Alignment(horizontal="center")
        imp_cell.font = FONT_BOLD
        imp_cell.fill = OK_FILL if r.implementacion == "implementada" else WARN_FILL

        ws3.cell(row=row_idx, column=9, value=r.aprobado_por or "—").alignment = Alignment(horizontal="center")
        ws3.cell(row=row_idx, column=10, value=r.autorizado_por or "—").alignment = Alignment(horizontal="center")
        ws3.cell(row=row_idx, column=11, value=r.implementado_por or "—").alignment = Alignment(horizontal="center")
        ws3.cell(row=row_idx, column=12, value=str(r.fecha_compromiso or "Inmediato")).alignment = Alignment(horizontal="center")

        for c_i in range(1, 13):
            ws3.cell(row=row_idx, column=c_i).border = THIN_BORDER

    # Autoajustar anchos de columna en todas las hojas
    for ws in [ws1, ws2, ws3]:
        for col in ws.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                val = str(cell.value or "")
                # Evitar longitudes gigantes por descripciones largas
                if len(val) > max_len and len(val) < 80:
                    max_len = len(val)
            ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

    # Ancho específico para descripciones en hoja de plan
    ws3.column_dimensions["D"].width = 28
    ws3.column_dimensions["E"].width = 45
    ws3.column_dimensions["F"].width = 30

    # User-authored strings must never become executable spreadsheet formulas.
    for ws in wb.worksheets:
        for row in ws:
            for cell in row:
                if cell.data_type == "f":
                    cell.data_type = "s"

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer
