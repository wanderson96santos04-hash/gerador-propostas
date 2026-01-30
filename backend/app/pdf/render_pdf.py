from io import BytesIO
from datetime import datetime
from typing import Any, Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    ListFlowable,
    ListItem,
)
from reportlab.lib.colors import black, HexColor


# =========================
# Branding (pode editar)
# =========================
BRAND_NAME = "Gerador de Propostas"
BRAND_SIGNATURE = "Gerador de Propostas que Fecham Vendas"
BRAND_TAGLINE = "Propostas profissionais — texto pronto + PDF"
BRAND_CONTACT = ""  # ex: "seusite.com" ou "contato@seusite.com"


def _s(v: Any) -> str:
    if v is None:
        return ""
    return str(v)


def _strip_md_inline(text: str) -> str:
    t = text
    t = t.replace("**", "")
    t = t.replace("__", "")
    t = t.replace("`", "")
    return t


def _extract_text_from_any(obj: Any) -> str:
    if obj is None:
        return ""

    if isinstance(obj, str):
        return obj

    if isinstance(obj, dict):
        for key in ("proposal_text", "content", "text", "body", "body_text"):
            if key in obj and obj[key]:
                return _s(obj[key])
        return ""

    for attr in ("proposal_text", "content", "text", "body", "body_text"):
        if hasattr(obj, attr):
            val = getattr(obj, attr)
            if val:
                return _s(val)

    return ""


def _footer_canvas(canvas, doc, generated_at: datetime):
    """
    Rodapé fixo em TODAS as páginas (discreto e profissional).
    """
    canvas.saveState()

    # Linha sutil
    canvas.setStrokeColor(HexColor("#DDDDDD"))
    canvas.setLineWidth(0.6)
    y_line = 1.7 * cm
    canvas.line(doc.leftMargin, y_line, A4[0] - doc.rightMargin, y_line)

    # Texto do rodapé
    canvas.setFillColor(HexColor("#666666"))
    canvas.setFont("Helvetica", 9)

    left_text = BRAND_SIGNATURE or BRAND_NAME
    right_parts = [generated_at.strftime("%d/%m/%Y %H:%M")]
    if BRAND_CONTACT:
        right_parts.insert(0, BRAND_CONTACT)

    right_text = " • ".join(right_parts)

    y_text = 1.2 * cm
    canvas.drawString(doc.leftMargin, y_text, left_text)
    canvas.drawRightString(A4[0] - doc.rightMargin, y_text, right_text)

    canvas.restoreState()


def build_proposal_pdf(*args, **kwargs) -> bytes:
    """
    PDF profissional e estável:
    - bullets entram no ponto certo
    - rodapé fixo em todas as páginas (mais profissional)
    """

    title = ""
    client_name = ""
    service = ""
    deadline = ""
    price = ""
    proposal_text = ""

    # args padrão (compat)
    if len(args) >= 1:
        title = _s(args[0])
    if len(args) >= 2:
        client_name = _s(args[1])
    if len(args) >= 3:
        service = _s(args[2])
    if len(args) >= 4:
        deadline = _s(args[3])
    if len(args) >= 5:
        price = _s(args[4])
    if len(args) >= 6:
        proposal_text = _s(args[5])

    # kwargs prioridade
    title = _s(kwargs.get("title", title))
    client_name = _s(kwargs.get("client_name", kwargs.get("client", client_name)))
    service = _s(kwargs.get("service", service))
    deadline = _s(kwargs.get("deadline", deadline))
    price = _s(kwargs.get("price", kwargs.get("investment", price)))

    raw_text = kwargs.get("proposal_text", kwargs.get("content", proposal_text))
    proposal_text = _extract_text_from_any(raw_text) or _s(raw_text) or proposal_text

    if not title:
        title = f"Proposta - {client_name or 'Cliente'}"

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2.2 * cm,  # um pouco maior pra caber o rodapé
        title=title,
    )

    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="TitleStyle",
            fontSize=20,
            leading=24,
            spaceAfter=16,
            alignment=TA_CENTER,
            textColor=black,
        )
    )
    styles.add(
        ParagraphStyle(
            name="HeaderStyle",
            fontSize=14,
            leading=18,
            spaceBefore=12,
            spaceAfter=8,
            textColor=black,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BodyStyle",
            fontSize=11,
            leading=15,
            spaceAfter=6,
            alignment=TA_LEFT,
        )
    )
    styles.add(
        ParagraphStyle(
            name="MutedStyle",
            fontSize=10,
            leading=14,
            textColor=HexColor("#555555"),
        )
    )

    story = []

    # Título
    story.append(Paragraph(_strip_md_inline(title), styles["TitleStyle"]))
    story.append(Spacer(1, 10))

    # Resumo
    story.append(Paragraph("<b>Resumo</b>", styles["HeaderStyle"]))
    if client_name:
        story.append(Paragraph(f"<b>Cliente:</b> {_strip_md_inline(client_name)}", styles["BodyStyle"]))
    if service:
        story.append(Paragraph(f"<b>Serviço:</b> {_strip_md_inline(service)}", styles["BodyStyle"]))
    if deadline:
        story.append(Paragraph(f"<b>Prazo:</b> {_strip_md_inline(deadline)}", styles["BodyStyle"]))
    if price:
        story.append(Paragraph(f"<b>Investimento:</b> {_strip_md_inline(price)}", styles["BodyStyle"]))
    story.append(Spacer(1, 14))

    # Corpo
    story.append(Paragraph("<b>Proposta</b>", styles["HeaderStyle"]))

    if not proposal_text.strip():
        story.append(
            Paragraph(
                "Texto da proposta não foi encontrado. Gere novamente a proposta e tente baixar o PDF.",
                styles["MutedStyle"],
            )
        )
    else:
        def flush_bullets(items):
            if not items:
                return
            story.append(
                ListFlowable(
                    items,
                    bulletType="bullet",
                    start="circle",
                    leftIndent=14,
                )
            )

        bullet_items = []

        for raw in proposal_text.splitlines():
            line = (raw or "").strip()

            if not line:
                flush_bullets(bullet_items)
                bullet_items = []
                story.append(Spacer(1, 6))
                continue

            if line.startswith("#"):
                flush_bullets(bullet_items)
                bullet_items = []
                text = _strip_md_inline(line.lstrip("#").strip())
                if text:
                    story.append(Paragraph(text, styles["HeaderStyle"]))
                continue

            if line.startswith("- "):
                bullet_items.append(
                    ListItem(
                        Paragraph(_strip_md_inline(line[2:]), styles["BodyStyle"]),
                        leftIndent=10,
                    )
                )
                continue

            flush_bullets(bullet_items)
            bullet_items = []
            story.append(Paragraph(_strip_md_inline(line), styles["BodyStyle"]))

        flush_bullets(bullet_items)

    generated_at = datetime.now()

    # Rodapé fixo em todas as páginas
    doc.build(
        story,
        onFirstPage=lambda canvas, d: _footer_canvas(canvas, d, generated_at),
        onLaterPages=lambda canvas, d: _footer_canvas(canvas, d, generated_at),
    )

    pdf = buffer.getvalue()
    buffer.close()
    return pdf
