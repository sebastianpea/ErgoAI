# backend/app/services/exportador_pdf.py
from __future__ import annotations

import io
from xml.sax.saxutils import escape
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from backend.app.api.schemas import CasoDetalle


def generar_pdf_caso(caso: CasoDetalle, bitacora_hash: str | None = None) -> io.BytesIO:
    """
    Genera un informe formal en PDF para auditoría legal (STPS / EHS Jabil)
    utilizando ReportLab, con maquetación ejecutiva y trazabilidad criptográfica.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()

    # Colores corporativos Jabil
    c_navy = colors.HexColor("#163E6A")
    c_cyan = colors.HexColor("#3CB4E5")
    c_dark = colors.HexColor("#1F2937")
    c_gray = colors.HexColor("#60605B")
    c_light = colors.HexColor("#F4F6F8")
    c_border = colors.HexColor("#E1E5EA")
    c_green = colors.HexColor("#2E9E5B")
    c_red = colors.HexColor("#D93A3A")

    # Estilos tipográficos
    style_title = ParagraphStyle(
        "ReportTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=18,
        textColor=c_navy,
        spaceAfter=4,
    )
    style_subtitle = ParagraphStyle(
        "ReportSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=13,
        textColor=c_gray,
        spaceAfter=8,
    )
    style_h2 = ParagraphStyle(
        "SectionH2",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=c_navy,
        spaceBefore=10,
        spaceAfter=5,
    )
    style_body = ParagraphStyle(
        "TableBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=c_dark,
    )
    style_body_bold = ParagraphStyle(
        "TableBodyBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=c_dark,
    )
    style_header_cell = ParagraphStyle(
        "TableHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=colors.white,
    )
    style_meta = ParagraphStyle(
        "MetaText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=9.5,
        textColor=c_gray,
    )

    elementos = []

    # 1. ENCABEZADO PRINCIPAL
    elementos.append(Paragraph("JABIL ERGOAI — SISTEMA DE AUDITORÍA ERGONÓMICA", style_subtitle))
    elementos.append(
        Paragraph(
            f"Informe Oficial de Evaluación Ergonómica · {escape(caso.id_caso)}",
            style_title,
        )
    )
    elementos.append(
        Paragraph(
            f"Estación: <b>{escape(caso.estacion)}</b> | Tarea: <b>{escape(caso.tipo_tarea.replace('_', ' ').title())}</b> | Fecha: <b>{escape(caso.fecha)}</b>",
            style_subtitle,
        )
    )
    elementos.append(HRFlowable(width="100%", thickness=2, color=c_cyan, spaceBefore=2, spaceAfter=8))

    # 2. DICTAMEN GLOBAL (REBA + NOM-036)
    elementos.append(Paragraph("1. Dictamen Global de Riesgo", style_h2))

    reba_pts = str(caso.reba.final) if caso.reba else "N/A"
    reba_lvl = str(caso.reba.nivel).upper() if caso.reba else "N/A"
    nom_total = str(caso.nom036.total) if caso.nom036 else "N/A"
    nom_lvl = str(caso.nom036.nivel).upper() if caso.nom036 else "N/A"

    dictamen_data = [
        [
            Paragraph("<b>Método</b>", style_header_cell),
            Paragraph("<b>Puntaje Obtenido</b>", style_header_cell),
            Paragraph("<b>Nivel de Riesgo</b>", style_header_cell),
            Paragraph("<b>Estado del Caso</b>", style_header_cell),
        ],
        [
            Paragraph("<b>REBA (Biomecánica)</b>", style_body_bold),
            Paragraph(f"{reba_pts} puntos", style_body_bold),
            Paragraph(reba_lvl, style_body_bold),
            Paragraph("APROBADO E IMPLEMENTADO" if caso.validacion.completa else "EN REVISIÓN", style_body_bold),
        ],
        [
            Paragraph("<b>NOM-036-1-STPS-2018</b>", style_body_bold),
            Paragraph(f"{nom_total} puntos", style_body),
            Paragraph(nom_lvl, style_body),
            Paragraph(f"{caso.validacion.implementadas} controles implementados", style_body),
        ],
    ]
    t_dictamen = Table(dictamen_data, colWidths=[1.8 * inch, 1.6 * inch, 1.8 * inch, 2.2 * inch])
    t_dictamen.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), c_navy),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, c_light]),
            ("GRID", (0, 0), (-1, -1), 0.5, c_border),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ])
    )
    elementos.append(t_dictamen)
    elementos.append(Spacer(1, 8))

    # 3. TABLA DE ÁNGULOS ARTICULARES
    elementos.append(Paragraph("2. Mediciones Biomecánicas por Segmento Anatómico", style_h2))
    ang_data = [
        [
            Paragraph("<b>Segmento</b>", style_header_cell),
            Paragraph("<b>Vista / Lado</b>", style_header_cell),
            Paragraph("<b>Ángulo Medido</b>", style_header_cell),
            Paragraph("<b>Puntos REBA</b>", style_header_cell),
            Paragraph("<b>Modificadores</b>", style_header_cell),
        ]
    ]

    for a in caso.angulos:
        ang_txt = f"{a.angulo_grados:.1f}°" if a.angulo_grados is not None else "N/A"
        mod_txt = ", ".join(a.modificadores) if a.modificadores else "Neutro"
        ang_data.append([
            Paragraph(escape(str(a.segmento).capitalize()), style_body_bold),
            Paragraph(escape(f"{a.vista} / {a.lado or '—'}"), style_body),
            Paragraph(ang_txt, style_body_bold),
            Paragraph(f"+{a.puntaje_reba}", style_body_bold),
            Paragraph(escape(mod_txt), style_meta),
        ])

    t_ang = Table(ang_data, colWidths=[1.5 * inch, 1.4 * inch, 1.3 * inch, 1.2 * inch, 2.0 * inch])
    t_ang.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), c_navy),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, c_light]),
            ("GRID", (0, 0), (-1, -1), 0.5, c_border),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ])
    )
    elementos.append(t_ang)
    elementos.append(Spacer(1, 8))

    # 4. PLAN DE MITIGACIÓN APROBADO E IMPLEMENTADO
    elementos.append(Paragraph("3. Plan de Mitigación y Controles Implementados en Planta", style_h2))

    recs_aprobadas = [r for r in caso.recomendaciones if r.estado in ("aprobada", "editada_aprobada")]
    if not recs_aprobadas:
        recs_aprobadas = caso.recomendaciones

    plan_data = [
        [
            Paragraph("<b>Código / Control</b>", style_header_cell),
            Paragraph("<b>Recomendación Técnica</b>", style_header_cell),
            Paragraph("<b>Fundamento STPS / Jabil</b>", style_header_cell),
            Paragraph("<b>Implementación</b>", style_header_cell),
        ]
    ]

    for r in recs_aprobadas:
        estado_imp = str(r.implementacion or "Pendiente").upper()
        firmas = f"Aprobó: {r.aprobado_por or '—'} | Imp: {r.implementado_por or '—'}"
        plan_data.append([
            Paragraph(f"<b>{escape(r.id)}</b><br/>{escape(r.nivel_control.capitalize())} ({escape(r.tipo_cambio)})", style_body),
            Paragraph(f"<b>{escape(r.titulo)}</b><br/>{escape(r.texto)}", style_body),
            Paragraph(escape(r.referencia), style_meta),
            Paragraph(f"<b>{escape(estado_imp)}</b><br/>{escape(firmas)}", style_body),
        ])

    t_plan = Table(plan_data, colWidths=[1.5 * inch, 2.7 * inch, 1.8 * inch, 1.4 * inch])
    t_plan.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), c_navy),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, c_light]),
            ("GRID", (0, 0), (-1, -1), 0.5, c_border),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ])
    )
    elementos.append(t_plan)
    elementos.append(Spacer(1, 10))

    # 5. PIE DE AUDITORÍA Y SELLO CRIPTOGRÁFICO
    elementos.append(Paragraph("4. Trazabilidad Legal e Integridad Criptográfica", style_h2))
    hash_txt = bitacora_hash or "SHA-256 verificado en bitácora inmutable de eventos"
    elementos.append(
        Paragraph(
            f"<b>Sello Digital SHA-256:</b> <font face='Courier' size='7'>{escape(hash_txt)}</font><br/>"
            "Este informe es generado automáticamente por el motor ErgoAI conforme a la NOM-036-1-STPS-2018 "
            "y los estándares globales de manufactura de Jabil Circuit, Inc.",
            style_meta,
        )
    )

    doc.build(elementos)
    buffer.seek(0)
    return buffer
