"""Generación de archivos en el servidor (ADR-009): PDF con ReportLab y Excel con openpyxl."""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from decimal import Decimal

from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

VERDE = colors.HexColor("#0F766E")
# Hoja "Detalle" del Excel: título (1), periodo y orden (2), vacía (3), encabezado (4), datos desde la 5
FILA_CABECERA = 4


@dataclass
class Reporte:
    titulo: str
    resumen: list[tuple[str, object]]
    columnas: list[str]
    filas: list[list]
    moneda: list[int] = field(default_factory=list)  # columnas en pesos: número en Excel, formato COP en PDF
    orden: str = ""  # RF-D-ADM-05.2: "fecha de registro, ascendente; luego por código" (lo dice el encabezado)
    periodo: str = ""
    generado_por: str = ""


def pesos(v) -> str:
    return "$" + f"{Decimal(v):,.0f}".replace(",", ".")


def _ahora() -> str:
    return timezone.localtime().strftime("%d/%m/%Y %H:%M")


def pdf(r: Reporte) -> bytes:
    buf = io.BytesIO()
    hoja = landscape(A4) if len(r.columnas) > 6 else A4
    doc = SimpleDocTemplate(buf, pagesize=hoja, leftMargin=14 * mm, rightMargin=14 * mm, topMargin=14 * mm, bottomMargin=14 * mm,
                            title=r.titulo, author="Alojamientos LR")
    est = getSampleStyleSheet()
    celda = est["BodyText"].clone("celda", fontSize=8, leading=10)
    cabeza = celda.clone("cabeza", textColor=colors.white, fontName="Helvetica-Bold")
    contenido = [
        Paragraph("Alojamientos LR", est["Title"].clone("t", alignment=0, textColor=VERDE, fontSize=18)),
        Paragraph(r.titulo, est["Heading2"]),
        Paragraph(f"Periodo: {r.periodo}<br/>Ordenado por: {r.orden}<br/>Generado por: {r.generado_por} · {_ahora()}", est["BodyText"]),
        Spacer(1, 6 * mm),
    ]
    resumen = Table([["Indicador", "Valor"]] + [[k, str(v)] for k, v in r.resumen], colWidths=[95 * mm, 45 * mm], hAlign="LEFT")
    resumen.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), VERDE), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CDD6D2")),
    ]))
    contenido += [resumen, Spacer(1, 6 * mm)]
    if r.filas:
        datos = [[Paragraph(c, cabeza) for c in r.columnas]] + [
            [Paragraph(pesos(v) if i in r.moneda and isinstance(v, (int, Decimal)) else str(v), celda) for i, v in enumerate(f)] for f in r.filas
        ]
        detalle = Table(datos, repeatRows=1, hAlign="LEFT")
        detalle.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), VERDE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F1F8F6")]),
            ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#E2E8E5")),
        ]))
        contenido.append(detalle)
    else:
        contenido.append(Paragraph("Sin registros en el periodo.", est["BodyText"]))

    def pie(canvas, doc_):
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.grey)
        canvas.drawRightString(hoja[0] - 14 * mm, 8 * mm, f"Página {doc_.page}")

    doc.build(contenido, onFirstPage=pie, onLaterPages=pie)
    return buf.getvalue()


def xlsx(r: Reporte) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Detalle"
    ws.append([r.titulo])
    ws["A1"].font = Font(bold=True, size=13)
    ws.append([f"Periodo: {r.periodo} · Ordenado por: {r.orden}"])
    ws.append([])
    ws.append(r.columnas)  # fila FILA_CABECERA
    for f in r.filas:
        ws.append([float(v) if isinstance(v, Decimal) else v for v in f])
    relleno = PatternFill("solid", fgColor="0F766E")
    for c in ws[FILA_CABECERA]:
        c.font, c.fill = Font(bold=True, color="FFFFFF"), relleno
    for i in r.moneda:
        for celda in ws.iter_rows(min_row=FILA_CABECERA + 1, min_col=i + 1, max_col=i + 1):
            celda[0].number_format = '"$"#,##0'
    for i, nombre in enumerate(r.columnas, start=1):
        largo = max([len(nombre)] + [len(str(f[i - 1])) + 3 for f in r.filas])
        ws.column_dimensions[get_column_letter(i)].width = min(48, largo + 2)
    # La fila de encabezado queda inmovilizada (y las de arriba) y las columnas llevan autofiltro
    ws.freeze_panes = f"A{FILA_CABECERA + 1}"
    ultima = get_column_letter(len(r.columnas))
    ws.auto_filter.ref = f"A{FILA_CABECERA}:{ultima}{FILA_CABECERA + len(r.filas)}"

    rs = wb.create_sheet("Resumen")
    rs.append([r.titulo])
    rs["A1"].font = Font(bold=True, size=14)
    rs.append([f"Periodo: {r.periodo}"])
    rs.append([f"Ordenado por: {r.orden}"])
    rs.append([f"Generado por: {r.generado_por} · {_ahora()}"])
    rs.append([])
    rs.append(["Indicador", "Valor"])
    for c in rs[6]:
        c.font, c.fill = Font(bold=True, color="FFFFFF"), relleno
    for k, v in r.resumen:
        rs.append([k, v])
    rs.column_dimensions["A"].width = 48
    rs.column_dimensions["B"].width = 24
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
