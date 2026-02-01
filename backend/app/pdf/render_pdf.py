from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, Frame
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.colors import black


def build_proposal_pdf(
    client_name: str,
    service: str,
    price: str,
    proposal_text: str,
) -> bytes:
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
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
    c.drawString(2 * cm, y, "Proposta Comercial")
    y -= 1 * cm

    c.setFont("Helvetica", 11)
    c.drawString(2 * cm, y, f"Cliente: {client_name}")
    y -= 0.6 * cm

    c.drawString(2 * cm, y, f"Serviço: {service}")
    y -= 0.6 * cm

    c.drawString(2 * cm, y, f"Investimento: {price}")
    y -= 1.2 * cm

    # ===== CORPO =====
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

    buffer.seek(0)
    return buffer.read()
