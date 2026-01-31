# backend/app/routes.py
from __future__ import annotations

import os
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


# =========================
# REGRAS:
# / (home) -> pago: /create | não pago: /paywall | deslogado: /login
# /paywall -> definido em app/auth/routes.py (único lugar)
# /create, /history, /proposal/* -> só pago
# =========================


def _env_flag(name: str, default: str = "0") -> bool:
    v = (os.getenv(name) or default).strip().lower()
    return v in ("1", "true", "yes", "on", "y")


def _build_premium_prompt(data: dict) -> str:
    """
    Prompt Premium: GPT escreve a proposta inteira, em PT-BR, com estrutura vendável.
    """
    client_name = data.get("client_name", "")
    service = data.get("service", "")
    scope = data.get("scope", "")
    deadline = data.get("deadline", "")
    price = data.get("price", "")
    payment_terms = data.get("payment_terms", "")
    differentiators = data.get("differentiators", "")
    warranty_support = data.get("warranty_support", "")
    tone = data.get("tone", "")
    objective = data.get("objective", "")

    return f"""
Você é um consultor comercial sênior e redator de propostas profissionais.

Crie uma PROPOSTA COMERCIAL COMPLETA em português (PT-BR), bem formatada para copiar/colar no WhatsApp, Email ou PDF.
O texto deve soar humano, profissional, claro e persuasivo, com linguagem fácil e objetiva.

Regras:
- Não invente dados que não existam. Se algo estiver vazio, escreva de forma genérica sem citar "não informado".
- Use títulos e seções claras.
- Faça uma proposta realmente "vendável": valor, benefícios, confiança, fechamento.
- Inclua um CTA final para aprovação e início.
- Evite exageros e promessas irreais.
- Use tom "{tone}" e objetivo "{objective}".

Dados do cliente e serviço:
- Cliente: {client_name}
- Serviço: {service}
- Escopo / Inclusões: {scope}
- Prazo: {deadline}
- Preço / Investimento: {price}
- Condições de pagamento: {payment_terms}
- Diferenciais: {differentiators}
- Garantia / Suporte: {warranty_support}

Estrutura sugerida (siga isso):
1) Abertura curta e profissional (contexto + objetivo)
2) Entendimento do que será entregue
3) Escopo e etapas (em bullets)
4) Prazo e cronograma (curto)
5) Investimento e condições de pagamento
6) Diferenciais (por que escolher você)
7) Garantia / suporte (se fizer sentido)
8) Próximos passos (CTA de aprovação)
9) Assinatura simples (sem inventar nome da empresa)

Gere SOMENTE o texto final da proposta (sem comentários).
""".strip()


def _generate_with_openai_if_available(data: dict) -> tuple[str | None, str | None]:
    """
    Tenta gerar com OpenAI (Premium). Retorna (texto, debug_info).
    Se não houver API key ou der erro, retorna (None, debug_info).
    """
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        return None, "OPENAI_API_KEY ausente"

    model = (os.getenv("OPENAI_MODEL") or "gpt-4o-mini").strip()
    debug_ai = _env_flag("DEBUG_AI", "0")

    prompt = _build_premium_prompt(data)

    # Chat Completions (compatível e simples)
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "temperature": 0.7,
        "messages": [
            {
                "role": "system",
                "content": "Você escreve propostas comerciais profissionais, claras e persuasivas, em PT-BR.",
            },
            {"role": "user", "content": prompt},
        ],
    }

    try:
        timeout = httpx.Timeout(25.0, connect=10.0)
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, headers=headers, json=payload)

        if resp.status_code >= 400:
            if debug_ai:
                print("OPENAI DEBUG >>> status=", resp.status_code, "body=", resp.text[:400])
            return None, f"OpenAI HTTP {resp.status_code}"

        data_json = resp.json()
        text = (
            data_json.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        text = (text or "").strip()

        if debug_ai:
            print(
                "OPENAI DEBUG >>> ok | model=",
                model,
                "| chars=",
                len(text),
            )

        if not text:
            return None, "OpenAI retornou vazio"

        return text, "OpenAI OK"

    except Exception as e:
        if debug_ai:
            print("OPENAI DEBUG >>> exception:", repr(e))
        return None, f"OpenAI exception: {type(e).__name__}"


@router.get("/")
def home(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    if user.is_paid:
        return RedirectResponse(url="/create", status_code=303)
    return RedirectResponse(url="/paywall", status_code=303)


@router.get("/create")
def create_page(request: Request, db: Session = Depends(get_db)):
    # só pago
    try:
        user = require_paid_user(request, db)
    except PermissionError:
        # se está logado mas não pago -> /paywall
        u = get_current_user(request, db)
        return RedirectResponse(url="/paywall" if u else "/login", status_code=303)

    return request.app.state.templates.TemplateResponse(
        "create_proposal.html",
        {"request": request, "user": user, "error": None},
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
    # só pago
    try:
        user = require_paid_user(request, db)
    except PermissionError:
        u = get_current_user(request, db)
        return RedirectResponse(url="/paywall" if u else "/login", status_code=303)

    # validação mínima
    client_name = (client_name or "").strip()
    service = (service or "").strip()
    if len(client_name) < 2 or len(service) < 2:
        return request.app.state.templates.TemplateResponse(
            "create_proposal.html",
            {"request": request, "user": user, "error": "Preencha nome do cliente e serviço."},
            status_code=400,
        )

    data = {
        "client_name": client_name,
        "service": service,
        "scope": (scope or "").strip(),
        "deadline": (deadline or "").strip(),
        "price": (price or "").strip(),
        "payment_terms": (payment_terms or "").strip(),
        "differentiators": (differentiators or "").strip(),
        "warranty_support": (warranty_support or "").strip(),
        "tone": (tone or "").strip().lower(),
        "objective": (objective or "").strip().lower(),
    }

    # =========================
    # PREMIUM (GPT) com fallback
    # =========================
    proposal_text, ai_info = _generate_with_openai_if_available(data)
    if not proposal_text:
        # fallback para o gerador atual (não quebra o app)
        proposal_text = generate_proposal_text(data)

    # DEBUG opcional (não expõe secrets)
    if _env_flag("DEBUG_AI", "0"):
        print(
            "PROPOSAL DEBUG >>> user_id=",
            user.id,
            "| ai=",
            ai_info,
            "| tone=",
            data.get("tone"),
            "| objective=",
            data.get("objective"),
        )

    summary = (
        f"Cliente: {data['client_name']}\n"
        f"Serviço: {data['service']}\n"
        f"Prazo: {data['deadline']}\n"
        f"Preço: {data['price']}\n"
        f"Pagamento: {data['payment_terms']}\n"
        f"Tom: {data['tone']} | Objetivo: {data['objective']}\n"
        f"IA: {ai_info}\n"
    )

    p = Proposal(
        user_id=user.id,
        client_name=data["client_name"],
        service=data["service"],
        price=data["price"],
        deadline=data["deadline"],
        tone=data["tone"],
        objective=data["objective"],
        proposal_text=proposal_text,
        input_summary=summary,
        created_at=datetime.utcnow(),
    )
    db.add(p)
    db.commit()
    db.refresh(p)

    return request.app.state.templates.TemplateResponse(
        "result.html",
        {"request": request, "user": user, "proposal": p},
    )


@router.get("/history")
def history(request: Request, db: Session = Depends(get_db)):
    # só pago
    try:
        user = require_paid_user(request, db)
    except PermissionError:
        u = get_current_user(request, db)
        return RedirectResponse(url="/paywall" if u else "/login", status_code=303)

    proposals = (
        db.query(Proposal)
        .filter(Proposal.user_id == user.id)
        .order_by(Proposal.created_at.desc())
        .limit(50)
        .all()
    )

    return request.app.state.templates.TemplateResponse(
        "history.html",
        {"request": request, "user": user, "proposals": proposals},
    )


@router.get("/proposal/{proposal_id}")
def proposal_detail(proposal_id: int, request: Request, db: Session = Depends(get_db)):
    # só pago
    try:
        user = require_paid_user(request, db)
    except PermissionError:
        u = get_current_user(request, db)
        return RedirectResponse(url="/paywall" if u else "/login", status_code=303)

    p = (
        db.query(Proposal)
        .filter(Proposal.id == proposal_id, Proposal.user_id == user.id)
        .first()
    )
    if not p:
        return RedirectResponse(url="/history", status_code=303)

    return request.app.state.templates.TemplateResponse(
        "proposal_detail.html",
        {"request": request, "user": user, "proposal": p},
    )


@router.get("/proposal/{proposal_id}/pdf")
def proposal_pdf(proposal_id: int, request: Request, db: Session = Depends(get_db)):
    # só pago
    try:
        user = require_paid_user(request, db)
    except PermissionError:
        u = get_current_user(request, db)
        return RedirectResponse(url="/paywall" if u else "/login", status_code=303)

    p = (
        db.query(Proposal)
        .filter(Proposal.id == proposal_id, Proposal.user_id == user.id)
        .first()
    )
    if not p:
        return RedirectResponse(url="/history", status_code=303)

    pdf_bytes = build_proposal_pdf(
        title=f"Proposta - {p.client_name}",
        client_name=p.client_name,
        service=p.service,
        deadline=p.deadline,
        price=p.price,
        proposal_text=p.proposal_text,
    )

    filename = f"proposta_{p.id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
