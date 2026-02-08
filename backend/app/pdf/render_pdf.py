from __future__ import annotations

from io import BytesIO
import logging
from typing import Optional
from datetime import date

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
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

        heading = ParagraphStyle(
            "Heading",
            parent=normal,
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=16,
            spaceBefore=8,
            spaceAfter=6,
        )

        small = ParagraphStyle(
            "Small",
            parent=normal,
            fontSize=9.5,
            leading=13,
            textColor=black,
            spaceBefore=6,
            spaceAfter=0,
        )

        # ===== CABEÇALHO (OBRIGATÓRIO) =====
        y = height - 2 * cm

        c.setFont("Helvetica-Bold", 18)
        c.drawString(2 * cm, y, "PROPOSTA COMERCIAL")
        y -= 1.0 * cm

        c.setFont("Helvetica", 11)

        # Campos obrigatórios (exibir mesmo que vazios)
        c.drawString(2 * cm, y, f"Cliente: {client_name}")
        y -= 0.6 * cm

        c.drawString(2 * cm, y, f"Serviço: {service}")
        y -= 0.6 * cm

        c.drawString(2 * cm, y, f"Prazo: {deadline_value}")
        y -= 0.6 * cm

        c.drawString(2 * cm, y, f"Valor: {price}")
        y -= 0.6 * cm

        data_str = date.today().strftime("%d/%m/%Y")
        c.drawString(2 * cm, y, f"Data: {data_str}")
        y -= 0.9 * cm

        # Linha de separação (organização visual)
        c.setLineWidth(0.7)
        c.line(2 * cm, y, width - 2 * cm, y)
        y -= 0.8 * cm

        # ===== CORPO (ORGANIZAÇÃO VISUAL) =====
        # Garante altura mínima do frame (evita erro se y ficar muito pequeno)
        frame_top = max(y, 6 * cm)

        frame = Frame(
            2 * cm,
            2 * cm,
            width - 4 * cm,
            frame_top - 2 * cm,
            showBoundary=0,
        )

        paragraphs = []

        # Título da seção do conteúdo (sem mudar o texto, só organização)
        paragraphs.append(Paragraph("Detalhamento da proposta", heading))

        # Mantém o texto atual; só organiza em blocos menores
        lines = proposal_text.split("\n") if proposal_text else [""]
        for line in lines:
            if line.strip():
                paragraphs.append(Paragraph(line, normal))
            else:
                paragraphs.append(Paragraph("&nbsp;", normal))

        # ===== BLOCO DE FECHAMENTO (OBRIGATÓRIO) =====
        paragraphs.append(Paragraph("&nbsp;", normal))
        paragraphs.append(Paragraph("Aprovação da proposta", heading))
        paragraphs.append(
            Paragraph(
                "Esta proposta tem validade de 7 dias.<br/>"
                "Ao aprovar, o cliente concorda com os termos descritos acima.",
                normal,
            )
        )
        paragraphs.append(Paragraph("&nbsp;", normal))
        paragraphs.append(
            Paragraph(
                "Assinatura do prestador:<br/>_________________________",
                normal,
            )
        )
        paragraphs.append(Paragraph("&nbsp;", normal))
        paragraphs.append(
            Paragraph(
                "Assinatura do cliente:<br/>_________________________",
                normal,
            )
        )

        # ===== FRASE FINAL DE AUTORIDADE (OBRIGATÓRIA) =====
        paragraphs.append(Paragraph("&nbsp;", normal))
        paragraphs.append(
            Paragraph(
                "Proposta elaborada com foco em clareza, profissionalismo e cumprimento de prazos.",
                small,
            )
        )

        frame.addFromList(paragraphs, c)

        c.showPage()
        c.save()

        buffer.seek(0)
        return buffer.read()

    except Exception:
        # Log somente em caso de falha (útil no Render e local)
        logger.exception("Falha ao gerar PDF da proposta")
        raise
