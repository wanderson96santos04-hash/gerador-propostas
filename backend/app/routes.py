# backend/app/routes.py
from __future__ import annotations

import os
import re
from datetime import datetime

import httpx
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Proposal
from app.auth.routes import get_current_user, require_paid_user
from app.services.proposal_generator import generate_proposal_text
from app.pdf.render_pdf import build_proposal_pdf

# presets 1-clique
from app.templates.intelligent_presets import PRESETS

router = APIRouter()

FINAL_SIGNATURE = "Atenciosamente,\nEquipe Comercial"

# ======================================================
# Helpers
# ======================================================

def _redirect_paywall():
    return RedirectResponse("/paywall", status_code=303)


def _sanitize_proposal_text(text: str) -> str:
    if not text:
        return FINAL_SIGNATURE

    t = text.replace("\r\n", "\n").replace("\r", "\n").strip()

    # remove colchetes
    t = re.sub(r"\[.*?\]", "", t, flags=re.DOTALL)

    # remove tudo após "próximos passos"
    t = re.split(
        r"(?is)(próximos passos|##\s*próximos passos|\*\*próximos passos\*\*)",
        t,
        maxsplit=1,
    )[0].strip()

    # remove assinaturas existentes
    lines = t.split("\n")

    def norm(s: str) -> str:
        return re.sub(r"\s+", " ", s.lower().strip())

    while lines and norm(lines[-1]) in {
        "atenciosamente",
        "equipe comercial",
        "atenciosamente equipe comercial",
    }:
        lines.pop()

    t = "\n".join(lines).strip()

    return f"{t}\n\n{FINAL_SIGNATURE}"


def _build_input_summary(data: dict) -> str:
    return (
        f"Cliente: {data.get('client_name')} | "
        f"Serviço: {data.get('service')} | "
        f"Valor: {data.get('price')} | "
        f"Prazo: {data.get('deadline')} | "
        f"Objetivo: {data.get('objective')}"
    )


def _build_ai_prompt(data: dict) -> str:
    return f"""
Crie uma proposta comercial profissional em português (PT-BR).

REGRAS:
- Não use colchetes
- Não use assinatura pessoal
- Não escreva após o encerramento
- Linguagem impessoal e profissional

ENCERRAMENTO OBRIGATÓRIO:
Atenciosamente,
Equipe Comercial

Dados:
Cliente: {data.get('client_name')}
Serviço: {data.get('service')}
Escopo: {data.get('scope')}
Prazo: {data.get('deadline')}
Valor: {data.get('price')}
Pagamento: {data.get('payment_terms')}
Diferenciais: {data.get('differentiators')}
Garantia: {data.get('warranty_support')}
Tom: {data.get('tone')}
Objetivo: {data.get('objective')}
""".strip()


def _generate_with_openai_if_available(data: dict):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    payload = {
        "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        "temperature": 0.4,
        "messages": [
            {"role": "system", "content": "Você escreve propostas comerciais profissionais."},
            {"role": "user", "content": _build_ai_prompt(data)},
        ],
    }

    try:
        with httpx.Client(timeout=30) as client:
            r = client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )

        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        return None


# ======================================================
# Rotas
# ======================================================

@router.get("/")
def home(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)

    return RedirectResponse("/create" if user.is_paid else "/paywall", status_code=303)


@router.get("/create")
def create_page(request: Request, db: Session = Depends(get_db)):
    require_paid_user(request, db)

    return request.app.state.templates.TemplateResponse(
        "create_proposal.html",
        {"request": request},
    )


@router.post("/create")
def create_action(
    request: Request,
    client_name: str = Form(...),
    service: str = Form(...),
    scope: str = Form(...),
    deadline: str = Form(...),
    price: str = Form(...),
    payment_terms: str = Form(...),
    differentiators: str = Form(...),
    warranty_support: str = Form(...),
    tone: str = Form(...),
    objective: str = Form(...),
    preset_id: str = Form(None),
    db: Session = Depends(get_db),
):
    user = require_paid_user(request, db)

    data = {
        "client_name": client_name.strip(),
        "service": service.strip(),
        "scope": scope.strip(),
        "deadline": deadline.strip(),
        "price": price.strip(),
        "payment_terms": payment_terms.strip(),
        "differentiators": differentiators.strip(),
        "warranty_support": warranty_support.strip(),
        "tone": tone.lower().strip(),
        "objective": objective.lower().strip(),
    }

    if preset_id and preset_id in PRESETS:
        preset = PRESETS[preset_id]
        for k in preset:
            if not data.get(k):
                data[k] = preset[k]

    text = _generate_with_openai_if_available(data)
    if not text:
        text = generate_proposal_text(data)

    text = _sanitize_proposal_text(text)

    proposal = Proposal(
        user_id=user.id,
        client_name=data["client_name"],
        service=data["service"],
        price=data["price"],
        deadline=data["deadline"],
        tone=data["tone"],
        objective=data["objective"],
        input_summary=_build_input_summary(data),
        proposal_text=text,
        created_at=datetime.utcnow(),
    )

    db.add(proposal)
    db.commit()
    db.refresh(proposal)

    return request.app.state.templates.TemplateResponse(
        "result.html",
        {
            "request": request,
            "proposal": proposal,
            "created_date": proposal.created_at.strftime("%d/%m/%Y"),
        },
    )


@router.get("/history")
def history_page(request: Request, db: Session = Depends(get_db)):
    user = require_paid_user(request, db)

    proposals = (
        db.query(Proposal)
        .filter(Proposal.user_id == user.id)
        .order_by(Proposal.id.desc())
        .all()
    )

    return request.app.state.templates.TemplateResponse(
        "history.html",
        {"request": request, "proposals": proposals},
    )


@router.get("/proposal/{proposal_id}/pdf")
def proposal_pdf(proposal_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_paid_user(request, db)

    proposal = (
        db.query(Proposal)
        .filter(Proposal.id == proposal_id, Proposal.user_id == user.id)
        .first()
    )

    if not proposal:
        return RedirectResponse("/history", status_code=303)

    pdf_bytes = build_proposal_pdf(
        client_name=proposal.client_name,
        service=proposal.service,
        price=proposal.price,
        proposal_text=proposal.proposal_text,
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="proposta_{proposal.id}.pdf"'
        },
    )
