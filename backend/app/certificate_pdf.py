from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

import reportlab
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

FONT_DIRECTORY = Path(reportlab.__file__).parent / "fonts"
pdfmetrics.registerFont(TTFont("Vera", str(FONT_DIRECTORY / "Vera.ttf")))
pdfmetrics.registerFont(TTFont("Vera-Bold", str(FONT_DIRECTORY / "VeraBd.ttf")))


def render_certificate_pdf(
    *,
    church_name: str,
    certificate_type: str,
    member_name: str,
    details: str,
    issued_on: str,
    certificate_number: str,
) -> bytes:
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="ChurchName",
        parent=styles["Normal"],
        fontName="Vera-Bold",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#59665d"),
        alignment=TA_CENTER,
        spaceAfter=18 * mm,
    ))
    styles.add(ParagraphStyle(
        name="CertificateTitle",
        parent=styles["Title"],
        fontName="Vera",
        fontSize=28,
        leading=34,
        textColor=colors.HexColor("#775c2a"),
        alignment=TA_CENTER,
        spaceAfter=12 * mm,
    ))
    styles.add(ParagraphStyle(
        name="CertificateBody",
        parent=styles["Normal"],
        fontName="Vera",
        fontSize=14,
        leading=20,
        textColor=colors.HexColor("#20362c"),
        alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        name="MemberName",
        parent=styles["Normal"],
        fontName="Vera-Bold",
        fontSize=24,
        leading=32,
        textColor=colors.HexColor("#20362c"),
        alignment=TA_CENTER,
        spaceBefore=8 * mm,
        spaceAfter=8 * mm,
    ))
    styles.add(ParagraphStyle(
        name="CertificateDetails",
        parent=styles["Normal"],
        fontName="Vera",
        fontSize=12,
        leading=18,
        textColor=colors.HexColor("#20362c"),
        alignment=TA_CENTER,
        spaceBefore=5 * mm,
        spaceAfter=10 * mm,
    ))
    styles.add(ParagraphStyle(
        name="CertificateMeta",
        parent=styles["Normal"],
        fontName="Vera",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#59665d"),
        alignment=TA_CENTER,
    ))

    def draw_border(canvas, document) -> None:
        canvas.saveState()
        page_width, page_height = landscape(A4)
        canvas.setStrokeColor(colors.HexColor("#8a7041"))
        canvas.setLineWidth(2)
        canvas.rect(12 * mm, 12 * mm, page_width - 24 * mm, page_height - 24 * mm)
        canvas.setLineWidth(0.6)
        canvas.rect(15 * mm, 15 * mm, page_width - 30 * mm, page_height - 30 * mm)
        canvas.restoreState()

    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=28 * mm,
        rightMargin=28 * mm,
        topMargin=30 * mm,
        bottomMargin=24 * mm,
        title=f"{certificate_type} - {member_name}",
        author=church_name,
    )
    story = [
        Paragraph(escape(church_name), styles["ChurchName"]),
        Paragraph(escape(certificate_type), styles["CertificateTitle"]),
        Paragraph("This is to certify that", styles["CertificateBody"]),
        Paragraph(escape(member_name), styles["MemberName"]),
    ]
    if details:
        story.append(Paragraph(escape(details).replace("\n", "<br/>"), styles["CertificateDetails"]))
    story.extend([
        Spacer(1, 5 * mm),
        Paragraph(
            f"Issued {escape(issued_on)} &nbsp;&nbsp;&nbsp; Certificate No. {escape(certificate_number)}",
            styles["CertificateMeta"],
        ),
    ])
    document.build(story, onFirstPage=draw_border, onLaterPages=draw_border)
    return buffer.getvalue()
