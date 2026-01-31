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

router = APIRouter()

FINAL_SIGNATURE = "Atenciosamente,\nEquipe Comercial"


def _env_flag(name: str, default: str = "0") -> bool:
    v = (os.getenv(name) or default).strip().lower()
    return v in ("1", "true", "yes", "on", "y")


def _sanitize_proposal_text(text: str) -> str:
    """
    SANITIZAÇÃO FINAL DEFINITIVA.
    Nada de assinatura pessoal, placeholders ou texto após 'Próximos passos'.
    """
    if not text:
        return FINAL_SIGNATURE

    t = text.strip()

    # 1) Remove QUALQUER coisa entre colchetes [ ... ]
    t = re.sub(r"\[.*?\]", "", t, flags=re.DOTALL)

    # 2) REMOVE TUDO após qualquer variação de "Próximos passos"
    t = re.split(
        r"(?is)(\*\*\s*)?(##\s*)?próximos passos(\s*\*\*)?:?",
        t,
    )[0]

    # 3) Remove qualquer tentativa de assinatura ou linguagem pessoal restante
    t = re.sub(
        r"(?is)\b("
        r"atenciosamente|cordialmente|assinado|assine|"
        r"aguardo|aguardamos|peço|podemos|"
        r"estou à disposição|estamos à disposição|"
        r"fico à disposição|qualquer dúvida|"
        r"entre em contato|emitido em"
        r").*$",
        "",
        t,
    ).strip()

    # 4) Limpeza visual final
    t = t.rstrip(" \n\r-—")

    # 5) Normaliza linhas em branco
    t = re.sub(r"\n{3,}", "\n\n", t).strip()

    # 6) Encerramento FIXO e IMUTÁVEL
    if not t:
        return FINAL_SIGNATURE

    return f"{t}\n\n{FINAL_SIGNATURE}"


def _build_premium_prompt(data: dict) -> str:
    return f"""
Você é um redator sênior de propostas comerciais profissionais.

Crie uma PROPOSTA COMERCIAL COMPLETA em português (PT-BR), clara, objetiva e profissional.

REGRAS ABSOLUTAS:
- Não utilize colchetes "[]".
- Não utilize placeholders.
- Não use linguagem em primeira pessoa.
- Não inclua nomes, cargos, telefones, e-mails ou empresa.
- NÃO crie assinatura pessoal.
- NÃO escreva nada após o encerramento.

ENCERRAMENTO OBRIGATÓRIO (termine exatamente assim):
Atenciosamente,
Equipe Comercial

Dados:
- Cliente: {data.get("client_name")}
- Serviço: {data.get("service")}
- Escopo: {data.get("scope")}
- Prazo: {data.get("deadline")}
- Investimento: {data.get("price")}
- Condições de pagamento: {data.get("payment_terms")}
- Diferenciais: {data.get("differentiators")}
- Garantia / Suporte: {data.get("warranty_support")}

Use tom "{data.get("tone")}" e objetivo "{data.get("objective")}".

Gere somente o texto final da proposta.
""".strip()


def _generate_with_openai_if_available(data: dict):
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        return None

    model = (os.getenv("OPENAI_MODEL") or "gpt-4o-mini").strip()

    payload = {
        "model": model,
        "temperature": 0.4,
        "messages": [
            {"role": "system", "content": "Você escreve propostas comerciais profissionais em PT-BR."},
            {"role": "user", "content": _build_premium_prompt(data)},
        ],
    }

    try:
        with httpx.Client(timeout=25.0) as client:
            resp = client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )

        if resp.status_code >= 400:
            return None

        return (
            resp.json()
            .get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )

    except Exception:
        return None


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
        "tone": tone.strip().lower(),
        "objective": objective.strip().lower(),
    }

    text = _generate_with_openai_if_available(data)
    if not text:
        text = generate_proposal_text(data)

    # 🔒 SANITIZAÇÃO FINAL (ÚLTIMO PASSO DO FLUXO)
    text = _sanitize_proposal_text(text)

    p = Proposal(
        user_id=user.id,
        client_name=data["client_name"],
        service=data["service"],
        price=data["price"],
        deadline=data["deadline"],
        tone=data["tone"],
        objective=data["objective"],
        proposal_text=text,
        created_at=datetime.utcnow(),
    )

    db.add(p)
    db.commit()
    db.refresh(p)

    return request.app.state.templates.TemplateResponse(
        "result.html",
        {"request": request, "proposal": p},
    )


@router.get("/proposal/{proposal_id}/pdf")
def proposal_pdf(proposal_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_paid_user(request, db)

    p = (
        db.query(Proposal)
        .filter(Proposal.id == proposal_id, Proposal.user_id == user.id)
        .first()
    )
    if not p:
        return RedirectResponse("/history", status_code=303)

    pdf_bytes = build_proposal_pdf(
        title=f"Proposta - {p.client_name}",
        client_name=p.client_name,
        service=p.service,
        deadline=p.deadline,
        price=p.price,
        proposal_text=p.proposal_text,
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="proposta_{p.id}.pdf"'},
    )
