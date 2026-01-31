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

# ✅ DIAGNÓSTICO (reversível): confirma que o Render está rodando ESTE arquivo
ROUTES_VERSION = "routes_v_input_summary_fix_2026-01-31"

FINAL_SIGNATURE = "Atenciosamente,\nEquipe Comercial"


@router.get("/__routes_whoami")
def routes_whoami():
    return {"file": __file__, "version": ROUTES_VERSION}


def _redirect_paywall() -> RedirectResponse:
    # 303 garante GET no destino (bom para evitar re-POST)
    return RedirectResponse("/paywall", status_code=303)


def _sanitize_proposal_text(text: str) -> str:
    """
    Blindagem DEFINITIVA:
    - Remove qualquer coisa entre colchetes [ ... ]
    - Remove tudo após "Próximos passos" (qualquer variação)
    - Remove fechos pessoais
    - Força encerramento fixo
    """
    if not text:
        return FINAL_SIGNATURE

    t = (text or "").strip()

    # 1) remove QUALQUER coisa entre colchetes
    t = re.sub(r"\[.*?\]", "", t, flags=re.DOTALL).strip()

    # 2) corta tudo após "Próximos passos" (variações)
    t = re.split(
        r"(?is)(\*\*próximos passos\*\*|##\s*próximos passos|próximos passos)",
        t,
        maxsplit=1,
    )[0].strip()

    # 3) remove assinaturas/fechos pessoais caso tenham sobrado
    t = re.sub(
        r"(?is)\b(atenciosamente|aguardo|aguardamos|peço|podemos|estamos à disposição|fico à disposição).*?$",
        "",
        t,
    ).strip()

    # 4) limpa excesso de linhas
    t = re.sub(r"\n{3,}", "\n\n", t).strip()

    if not t:
        return FINAL_SIGNATURE

    return f"{t}\n\n{FINAL_SIGNATURE}".strip()


def _build_input_summary(data: dict) -> str:
    """
    input_summary é NOT NULL no Postgres (Render).
    Aqui GARANTE string SEMPRE.
    """
    client = (data.get("client_name") or "").strip()
    service = (data.get("service") or "").strip()
    scope = (data.get("scope") or "").strip()
    price = (data.get("price") or "").strip()
    deadline = (data.get("deadline") or "").strip()
    tone = (data.get("tone") or "").strip()
    objective = (data.get("objective") or "").strip()

    summary = (
        f"Cliente: {client} | Serviço: {service} | Escopo: {scope} | Valor: {price} | "
        f"Prazo: {deadline} | Tom: {tone} | Objetivo: {objective}"
    ).strip()

    return summary if summary else "Resumo indisponível"


def _build_premium_prompt(data: dict) -> str:
    return f"""
Você é um redator sênior de propostas comerciais profissionais.

Crie uma PROPOSTA COMERCIAL COMPLETA em português (PT-BR), clara, objetiva e profissional.

REGRAS ABSOLUTAS:
- Não utilize colchetes.
- Não utilize placeholders.
- Não use linguagem em primeira pessoa.
- Não inclua nomes, cargos, telefones, e-mails ou empresa.
- NÃO crie assinatura pessoal.
- NÃO escreva nada após o encerramento.

ENCERRAMENTO OBRIGATÓRIO:
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
    try:
        require_paid_user(request, db)
    except PermissionError:
        return _redirect_paywall()

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
    try:
        user = require_paid_user(request, db)
    except PermissionError:
        return _redirect_paywall()

    data = {
        "client_name": (client_name or "").strip(),
        "service": (service or "").strip(),
        "scope": (scope or "").strip(),
        "deadline": (deadline or "").strip(),
        "price": (price or "").strip(),
        "payment_terms": (payment_terms or "").strip(),
        "differentiators": (differentiators or "").strip(),
        "warranty_support": (warranty_support or "").strip(),
        "tone": (tone or "").strip().lower(),
        "objective": (objective or "").strip().lower(),
    }

    # gera texto
    text = _generate_with_openai_if_available(data)
    if not text:
        text = generate_proposal_text(data)

    # 🔒 sanitiza antes de salvar
    text = _sanitize_proposal_text(text)

    # ✅ gera input_summary obrigatório (NOT NULL)
    input_summary = _build_input_summary(data)

    # cria proposta (✅ já passa input_summary no construtor)
    p = Proposal(
        user_id=user.id,
        client_name=data["client_name"],
        service=data["service"],
        price=data["price"],
        deadline=data["deadline"],
        tone=data["tone"],
        objective=data["objective"],
        input_summary=input_summary,
        proposal_text=text,
        created_at=datetime.utcnow(),
    )

    # ✅ BLINDAGEM EXTRA (se o model mudar depois, ainda garante)
    if hasattr(p, "input_summary"):
        setattr(p, "input_summary", getattr(p, "input_summary", None) or "Resumo indisponível")

    db.add(p)
    db.commit()
    db.refresh(p)

    created_date = ""
    try:
        if p.created_at:
            created_date = p.created_at.strftime("%d/%m/%Y")
    except Exception:
        created_date = str(p.created_at) if p.created_at else ""

    return request.app.state.templates.TemplateResponse(
        "result.html",
        {"request": request, "proposal": p, "created_date": created_date},
    )


@router.get("/proposal/{proposal_id}/pdf")
def proposal_pdf(proposal_id: int, request: Request, db: Session = Depends(get_db)):
    try:
        user = require_paid_user(request, db)
    except PermissionError:
        return _redirect_paywall()

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
