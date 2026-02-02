from __future__ import annotations

from io import BytesIO
import logging
from typing import Optional

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, Frame
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.colors import black


logger = logging.getLogger(__name__)


def build_proposal_pdf(
    *,
    title: str,
    client_name: str,
    service: str,
    deadline: Optional[str],
    price: str,
    proposal_text: str,
) -> bytes:
    """
    Gera um PDF de proposta e retorna os bytes (não salva em disco).
    Compatível com Linux (Render) e Windows (local).
    """
    try:
        # Normaliza entradas (evita crash com None)
        title = (title or "").strip() or "Proposta Comercial"
        client_name = (client_name or "").strip()
        service = (service or "").strip()
        price = (price or "").strip()
        proposal_text = proposal_text or ""

        deadline_value = (deadline or "").strip()  # pode ser ""

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
        c.drawString(2 * cm, y, title)
        y -= 1 * cm

        c.setFont("Helvetica", 11)
        if client_name:
            c.drawString(2 * cm, y, f"Cliente: {client_name}")
            y -= 0.6 * cm

        if service:
            c.drawString(2 * cm, y, f"Serviço: {service}")
            y -= 0.6 * cm

        # deadline é opcional (não crasha se vazio)
        if deadline_value:
            c.drawString(2 * cm, y, f"Prazo: {deadline_value}")
            y -= 0.6 * cm

        if price:
            c.drawString(2 * cm, y, f"Investimento: {price}")
            y -= 1.2 * cm
        else:
            y -= 0.6 * cm

        # ===== CORPO =====
        # Garante altura mínima do frame (evita erro se y ficar muito pequeno)
        frame_top = max(y, 4 * cm)

        frame = Frame(
            2 * cm,
            2 * cm,
            width - 4 * cm,
            frame_top - 2 * cm,
            showBoundary=0,
        )

        paragraphs = []
        # Se o texto vier vazio, ainda gera um parágrafo “em branco”
        lines = proposal_text.split("\n") if proposal_text else [""]
        for line in lines:
            if line.strip():
                paragraphs.append(Paragraph(line, normal))
            else:
                paragraphs.append(Paragraph("&nbsp;", normal))

        frame.addFromList(paragraphs, c)

        c.showPage()
        c.save()

        buffer.seek(0)
        return buffer.read()

    except Exception:
        # Log somente em caso de falha (útil no Render e local)
        logger.exception("Falha ao gerar PDF da proposta")
        raise
