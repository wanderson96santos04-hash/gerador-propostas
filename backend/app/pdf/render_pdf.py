from __future__ import annotations

from typing import Optional

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, Frame
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.colors import black


def build_proposal_pdf(
    file_path: str,
    client_name: str,
    service: str,
    price: str,
    proposal_text: str,
    title: Optional[str] = None,  # ✅ aceita "title" sem quebrar nada
):
    c = canvas.Canvas(file_path, pagesize=A4)
    width, height = A4

    styles = getSampleStyleSheet()
    normal = styles["Normal"]
    normal.fontSize = 11
    normal.leading = 15
    normal.textColor = black
    normal.alignment = TA_LEFT

    # ===== CABEÇALHO =====
    y = height - 2 * cm

    c.setFont("Helvetica-Bold", 18)

    # ✅ Se vier title, usa; senão mantém o padrão
    header_title = (title or "Proposta Comercial").strip() or "Proposta Comercial"
    c.drawString(2 * cm, y, header_title)
    y -= 1 * cm

    c.setFont("Helvetica", 11)
    c.drawString(2 * cm, y, f"Cliente: {client_name}")
    y -= 0.6 * cm

    c.drawString(2 * cm, y, f"Serviço: {service}")
    y -= 0.6 * cm

    c.drawString(2 * cm, y, f"Investimento: {price}")
    y -= 1.2 * cm

    # ===== CORPO DA PROPOSTA =====
    frame = Frame(
        2 * cm,
        2 * cm,
        width - 4 * cm,
        y - 2 * cm,
        showBoundary=0,
    )

    paragraphs = []
    for line in proposal_text.split("\n"):
        if line.strip():
            paragraphs.append(Paragraph(line, normal))
        else:
            paragraphs.append(Paragraph("&nbsp;", normal))

    frame.addFromList(paragraphs, c)

    c.showPage()
    c.save()
