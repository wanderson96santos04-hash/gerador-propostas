# backend/app/routes.py
from __future__ import annotations

import os
import re
from datetime import datetime

import httpx
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from app.config import settings  # ✅ ADIÇÃO SEGURA: apenas lê variáveis do .env/Render
from app.db.session import get_db
from app.db.models import Proposal
from app.auth.routes import get_current_user, require_paid_user
from app.services.proposal_generator import generate_proposal_text
from app.pdf.render_pdf import build_proposal_pdf

# ✅ NOVO: presets inteligentes (1 clique)
from app.templates.intelligent_presets import PRESETS

router = APIRouter()

FINAL_SIGNATURE = "Atenciosamente,\nEquipe Comercial"


def _redirect_paywall() -> RedirectResponse:
    # 303 garante GET no destino (bom para evitar re-POST)
    return RedirectResponse("/paywall", status_code=303)


def _sanitize_proposal_text(text: str) -> str:
    """
    Blindagem DEFINITIVA:
    - Remove qualquer coisa entre colchetes [ ... ]
    - Remove tudo após "Próximos passos" (qualquer variação)
    - Remove fechos pessoais
    - Remove QUALQUER assinatura existente (inclusive duplicada)
    - Garante UMA assinatura final fixa (sem duplicar)
    """
    if not text:
        return FINAL_SIGNATURE

    t = (text or "")

    # ✅ normaliza quebras de linha + NBSP (espaço invisível)
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    t = t.replace("\u00a0", " ").strip()

    # 1) remove QUALQUER coisa entre colchetes
    t = re.sub(r"\[.*?\]", "", t, flags=re.DOTALL).strip()

    # 2) corta tudo após "Próximos passos" (variações)
    t = re.split(
        r"(?is)(\*\*próximos passos\*\*|##\s*próximos passos|próximos passos)",
        t,
        maxsplit=1,
    )[0].strip()

    # 3) remove fechos pessoais comuns (sem matar o texto inteiro por engano)
    t = re.sub(
        r"(?is)\b(aguardo|aguardamos|peço|podemos|estamos à disposição|fico à disposição).*?$",
        "",
        t,
    ).strip()

    # 4) REMOÇÃO DEFINITIVA: remove assinaturas repetidas SOMENTE no FINAL (por linhas)
    def _norm(s: str) -> str:
        s = (s or "").replace("\u00a0", " ").strip().lower()
        s = re.sub(r"\s+", " ", s)
        return s

    lines = t.split("\n")

    def _pop_blank_end():
        while lines and _norm(lines[-1]) == "":
            lines.pop()

    def _is_atenciosamente(line: str) -> bool:
        return re.fullmatch(r"atenciosamente\s*[,:\-]?", _norm(line)) is not None

    def _is_equipe(line: str) -> bool:
        return re.fullmatch(r"equipe comercial\.?", _norm(line)) is not None

    def _is_both(line: str) -> bool:
        return re.fullmatch(
            r"atenciosamente\s*[,:\-]?\s*equipe comercial\.?",
            _norm(line),
        ) is not None

    _pop_blank_end()

    while True:
        _pop_blank_end()
        if not lines:
            break

        if _is_both(lines[-1]):
            lines.pop()
            continue

        if _is_equipe(lines[-1]):
            lines.pop()
            _pop_blank_end()
            if lines and _is_atenciosamente(lines[-1]):
                lines.pop()
            continue

        if _is_atenciosamente(lines[-1]):
            lines.pop()
            continue

        break

    t = "\n".join(lines).strip()

    # 5) limpa excesso de linhas
    t = re.sub(r"\n{3,}", "\n\n", t).strip()

    if not t:
        return FINAL_SIGNATURE

    # ✅ garante UMA única assinatura final
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


# ✅ NOVO: lista presets (para UI de 1 clique)
@router.get("/presets")
def list_presets(request: Request, db: Session = Depends(get_db)):
    try:
        require_paid_user(request, db)
    except PermissionError:
        return {"presets": []}

    return {
        "presets": [{"id": k, "label": v.get("label", k)} for k, v in PRESETS.items()]
    }


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
    # ✅ NOVO: preset_id opcional (1 clique)
    preset_id: str = Form(None),
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

    # ✅ aplica preset (1 clique) se veio preset_id
    preset_id_clean = (preset_id or "").strip()
    if preset_id_clean and preset_id_clean in PRESETS:
        preset = PRESETS[preset_id_clean]

        # Preenche apenas se o usuário deixou vazio (não sobrescreve)
        if not data["service"]:
            data["service"] = (preset.get("service") or "").strip()
        if not data["scope"]:
            data["scope"] = (preset.get("scope") or "").strip()
        if not data["differentiators"]:
            data["differentiators"] = (preset.get("differentiators") or "").strip()
        if not data["warranty_support"]:
            data["warranty_support"] = (preset.get("warranty_support") or "").strip()

    text = _generate_with_openai_if_available(data)
    if not text:
        text = generate_proposal_text(data)

    text = _sanitize_proposal_text(text)

    input_summary = _build_input_summary(data)

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
