# backend/app/routes.py
from __future__ import annotations

import os
import logging
from datetime import datetime, timedelta

import httpx
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db.session import get_db
from app.db.models import Proposal
from app.auth.routes import get_current_user  # vamos usar direto (mais seguro)
from app.services.proposal_generator import (
    generate_proposal_text,
    apply_next_steps,
    sanitize_proposal_text,
)
from app.pdf.render_pdf import build_proposal_pdf

# presets 1-clique
from app.templates.intelligent_presets import PRESETS

router = APIRouter()
logger = logging.getLogger(__name__)

# ===== marcador simples para provar origem da geração =====
_LAST_GEN = {"used": "unknown"}  # "openai" | "local" | "unknown"

# ===== Plano Free =====
FREE_MONTHLY_LIMIT = 2


# ======================================================
# Helpers
# ======================================================

def _redirect_login() -> RedirectResponse:
    return RedirectResponse("/login", status_code=303)


def _redirect_paywall(reason: str | None = None) -> RedirectResponse:
    url = "/paywall"
    if reason:
        url += f"?reason={reason}"
    return RedirectResponse(url, status_code=303)


def _get_user_or_redirect(request: Request, db: Session):
    """
    Retorna (user, None) se estiver OK.
    Retorna (None, RedirectResponse) se precisar redirecionar.
    """
    user = get_current_user(request, db)
    if not user:
        return None, _redirect_login()
    return user, None


def _finalize_proposal_text(text: str) -> str:
    """
    Fonte de verdade do fechamento:
    - Sanitiza sem assinatura
    - Força final padrão com "Próximos passos" (3 bullets)
    - NÃO adiciona assinatura
    """
    base = sanitize_proposal_text(text)
    return apply_next_steps(base)


def _build_input_summary(data: dict) -> str:
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


def _build_ai_prompt(data: dict) -> str:
    client = (data.get("client_name") or "").strip()
    service = (data.get("service") or "").strip()
    scope = (data.get("scope") or "").strip()
    deadline = (data.get("deadline") or "").strip()
    price = (data.get("price") or "").strip()
    payment_terms = (data.get("payment_terms") or "").strip()
    differentiators = (data.get("differentiators") or "").strip()
    warranty_support = (data.get("warranty_support") or "").strip()
    tone = (data.get("tone") or "").strip()
    objective = (data.get("objective") or "").strip()

    return f"""
Você é um especialista em PROPOSTAS COMERCIAIS para serviços (marketing, tráfego pago, social media, design, web, consultoria e prestação de serviços).

TAREFA:
Gerar uma PROPOSTA COMERCIAL completa em PT-BR, pronta para envio, com linguagem profissional, objetiva e específica ao serviço e escopo informados.

REGRAS ABSOLUTAS:
1) Proibido: colchetes, placeholders, "insira", "exemplo", "lorem ipsum".
2) Não usar 1ª pessoa ("eu", "meu", "nós"). Escreva em tom institucional.
3) Não citar e-mail, telefone, CNPJ, endereço, nome de empresa, cargo ou assinatura pessoal.
4) Não usar markdown pesado. Pode usar títulos simples e listas com hífen.
5) O texto deve ser ESPECÍFICO ao serviço e ao escopo informados. Não inventar outro serviço.
6) Variação controlada: escolha 1 de 3 estilos de abertura abaixo (use apenas 1, não liste):
   A) "Encaminha-se a presente proposta..."
   B) "Segue proposta comercial..."
   C) "Apresenta-se abaixo a proposta..."

ESTRUTURA OBRIGATÓRIA (seções curtas):
1. Diagnóstico e contexto (2–4 linhas, baseado no serviço/escopo)
2. Objetivo (1–3 linhas)
3. Escopo por entregáveis (lista objetiva; 6–12 itens no máximo, só do escopo)
4. Metodologia e alinhamentos (3–6 bullets: reuniões, aprovações, comunicação, acesso)
5. Cronograma (se prazo informado, use; senão, proponha 2 etapas simples)
6. Investimento (valor + o que inclui; sem “a partir de”)
7. Condições de pagamento (usar o texto do campo; se vazio, sugerir 2 opções curtas)
8. Garantia / Suporte (usar o campo; se vazio, 1 parágrafo curto padrão)
9. Próximos passos (3 bullets curtos)

ENCERRAMENTO (REGRA CRÍTICA):
- NÃO escreva assinatura.
- É PROIBIDO escrever “Atenciosamente” em qualquer parte do texto.
- Não escreva despedidas como “Cordialmente”, “Att”, etc.
- Termine o texto imediatamente após a seção "Próximos passos".
- Não escreva nada após finalizar "Próximos passos".

DADOS PARA USAR (não invente outros):
- Cliente: {client}
- Serviço: {service}
- Escopo: {scope}
- Prazo: {deadline}
- Investimento: {price}
- Condições de pagamento: {payment_terms}
- Diferenciais: {differentiators}
- Garantia/Suporte: {warranty_support}
- Tom: {tone}
- Objetivo: {objective}

IMPORTANTE:
- Se houver conflito entre Serviço e Escopo, trate o SERVIÇO como o nome principal e use o ESCOPO como entregáveis.

Agora gere somente o texto final da proposta.
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
            {"role": "user", "content": _build_ai_prompt(data)},
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

        text_out = (
            resp.json()
            .get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )

        if text_out:
            _LAST_GEN["used"] = "openai"

        return text_out
    except Exception:
        return None


# ======================================================
# Quota / Plano (DB first)
# ======================================================

def _first_day_next_month_utc(now: datetime) -> datetime:
    # garante reset mensal simples (UTC)
    # pega primeiro dia do mês seguinte 00:00
    year = now.year
    month = now.month + 1
    if month == 13:
        month = 1
        year += 1
    return datetime(year, month, 1, 0, 0, 0)


def _fetch_user_plan_and_quota(db: Session, user_id: int) -> dict:
    """
    Lê do banco sem depender de atributos no model (seguro mesmo se ORM não tiver campos novos).
    Espera colunas: plan, monthly_quota_used, quota_reset_at (criadas via /__migrate).
    """
    row = db.execute(
        text(
            """
            SELECT
              COALESCE(plan, 'free') AS plan,
              COALESCE(monthly_quota_used, 0) AS monthly_quota_used,
              quota_reset_at
            FROM users
            WHERE id = :uid
            """
        ),
        {"uid": user_id},
    ).mappings().first()

    if not row:
        return {"plan": "free", "monthly_quota_used": 0, "quota_reset_at": None}

    return {
        "plan": (row.get("plan") or "free").strip().lower(),
        "monthly_quota_used": int(row.get("monthly_quota_used") or 0),
        "quota_reset_at": row.get("quota_reset_at"),
    }


def _maybe_reset_monthly_quota(db: Session, user_id: int, info: dict) -> dict:
    """
    Se quota_reset_at estiver vazio OU já passou, reseta monthly_quota_used para 0
    e agenda próxima virada para o 1º dia do mês seguinte (UTC).
    """
    now = datetime.utcnow()
    reset_at = info.get("quota_reset_at")

    needs_reset = False
    if reset_at is None:
        needs_reset = True
    else:
        try:
            needs_reset = reset_at <= now
        except Exception:
            needs_reset = True

    if not needs_reset:
        return info

    next_reset = _first_day_next_month_utc(now)

    db.execute(
        text(
            """
            UPDATE users
            SET monthly_quota_used = 0,
                quota_reset_at = :next_reset
            WHERE id = :uid
            """
        ),
        {"uid": user_id, "next_reset": next_reset},
    )
    db.commit()

    info["monthly_quota_used"] = 0
    info["quota_reset_at"] = next_reset
    return info


def _is_pro_user(user, plan: str) -> bool:
    # mantém compatibilidade com is_paid já existente
    if getattr(user, "is_paid", False):
        return True
    return (plan or "free").lower() == "pro"


def _check_free_quota_or_redirect(db: Session, user, reason: str = "quota"):
    """
    Retorna (ok: bool, redirect: RedirectResponse|None, meta: dict)
    """
    info = _fetch_user_plan_and_quota(db, user.id)
    info = _maybe_reset_monthly_quota(db, user.id, info)

    plan = info["plan"]
    used = info["monthly_quota_used"]

    if _is_pro_user(user, plan):
        return True, None, {"plan": "pro", "used": used, "limit": None}

    # Free: limite real
    if used >= FREE_MONTHLY_LIMIT:
        return False, _redirect_paywall(reason), {"plan": "free", "used": used, "limit": FREE_MONTHLY_LIMIT}

    return True, None, {"plan": "free", "used": used, "limit": FREE_MONTHLY_LIMIT}


def _increment_free_quota(db: Session, user_id: int):
    """
    Incrementa uso mensal (somente para Free).
    Não explode se já estiver em Pro.
    """
    db.execute(
        text(
            """
            UPDATE users
            SET monthly_quota_used = COALESCE(monthly_quota_used, 0) + 1
            WHERE id = :uid
              AND COALESCE(plan, 'free') = 'free'
              AND COALESCE(is_paid, false) = false
            """
        ),
        {"uid": user_id},
    )
    db.commit()


# ======================================================
# Rotas
# ======================================================

@router.get("/")
def home(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return _redirect_login()
    # Agora: logado vai para criar proposta (Free também pode)
    return RedirectResponse("/create", status_code=303)


@router.get("/create")
def create_page(request: Request, db: Session = Depends(get_db)):
    user, redirect = _get_user_or_redirect(request, db)
    if redirect:
        return redirect

    # Deixa Free acessar a página (a trava real acontece no POST /create)
    return request.app.state.templates.TemplateResponse(
        "create_proposal.html",
        {"request": request, "user": user, "presets": PRESETS},
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
    user, redirect = _get_user_or_redirect(request, db)
    if redirect:
        return redirect

    # ✅ Trava real (DB) para Free: 2/mês
    ok, redir, quota_meta = _check_free_quota_or_redirect(db, user, reason="quota")
    if not ok and redir:
        return redir

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

    # aplica preset (1 clique) se veio preset_id (sem sobrescrever campos preenchidos)
    preset_id_clean = (preset_id or "").strip()
    if preset_id_clean and preset_id_clean in PRESETS:
        preset = PRESETS[preset_id_clean]
        for key in ["service", "scope", "differentiators", "warranty_support", "deadline", "price", "payment_terms"]:
            if key in preset and not data.get(key):
                data[key] = (preset.get(key) or "").strip()

    # geração GPT / fallback
    text_out = _generate_with_openai_if_available(data)
    if text_out:
        logger.info("GPT OK ✅ Proposta gerada pelo OpenAI.")
    else:
        _LAST_GEN["used"] = "local"
        logger.warning("GPT OFF ⚠️ Caindo no gerador padrão (fallback).")
        text_out = generate_proposal_text(data)

    # FINAL: padroniza fechamento e remove assinatura (fonte de verdade no backend)
    text_out = _finalize_proposal_text(text_out)

    # ✅ Se for Free, consome 1 uso (depois de gerar com sucesso)
    if quota_meta.get("plan") == "free":
        _increment_free_quota(db, user.id)

    p = Proposal(
        user_id=user.id,
        client_name=data["client_name"],
        service=data["service"],
        price=data["price"],
        deadline=data["deadline"],
        tone=data["tone"],
        objective=data["objective"],
        input_summary=_build_input_summary(data),
        proposal_text=text_out,
        created_at=datetime.utcnow(),
    )

    db.add(p)
    db.commit()
    db.refresh(p)

    created_date = ""
    try:
        if p.created_at:
            created_date = p.created_at.strftime("%d/%m/%Y")
    except Exception:
        created_date = str(p.created_at) if p.created_at else ""

    resp = request.app.state.templates.TemplateResponse(
        "result.html",
        {"request": request, "user": user, "proposal": p, "created_date": created_date},
    )

    # Headers úteis para debug
    resp.headers["X-Proposal-Generator"] = _LAST_GEN.get("used", "unknown")
    resp.headers["X-Plan"] = str(quota_meta.get("plan", "unknown"))
    resp.headers["X-Quota-Limit"] = str(quota_meta.get("limit") or "")
    resp.headers["X-Quota-Used-Before"] = str(quota_meta.get("used") or 0)

    return resp


@router.get("/history")
def history_page(request: Request, db: Session = Depends(get_db)):
    user, redirect = _get_user_or_redirect(request, db)
    if redirect:
        return redirect

    proposals = (
        db.query(Proposal)
        .filter(Proposal.user_id == user.id)
        .order_by(Proposal.id.desc())
        .limit(50)
        .all()
    )

    return request.app.state.templates.TemplateResponse(
        "history.html",
        {"request": request, "user": user, "proposals": proposals},
    )


@router.get("/proposal/{proposal_id}")
def proposal_detail(proposal_id: int, request: Request, db: Session = Depends(get_db)):
    """
    Rota que o history.html usa no link "Abrir"
    """
    user, redirect = _get_user_or_redirect(request, db)
    if redirect:
        return redirect

    p = (
        db.query(Proposal)
        .filter(Proposal.id == proposal_id, Proposal.user_id == user.id)
        .first()
    )

    if not p:
        return RedirectResponse("/history", status_code=303)

    created_date = ""
    try:
        if p.created_at:
            created_date = p.created_at.strftime("%d/%m/%Y")
    except Exception:
        created_date = str(p.created_at) if p.created_at else ""

    return request.app.state.templates.TemplateResponse(
        "proposal_detail.html",
        {"request": request, "user": user, "proposal": p, "created_date": created_date},
    )


@router.get("/proposal/{proposal_id}/pdf")
def proposal_pdf(proposal_id: int, request: Request, db: Session = Depends(get_db)):
    """
    Mantém a regra atual: PDF pode ficar PRO (como você já queria).
    Se quiser liberar PDF com watermark no Free, a gente ajusta depois.
    """
    user, redirect = _get_user_or_redirect(request, db)
    if redirect:
        return redirect

    # Se não for pago, manda pro paywall (mantém o que já funcionava)
    if not getattr(user, "is_paid", False):
        return _redirect_paywall("pdf")

    p = (
        db.query(Proposal)
        .filter(Proposal.id == proposal_id, Proposal.user_id == user.id)
        .first()
    )

    if not p:
        return RedirectResponse("/history", status_code=303)

    try:
        pdf_bytes = build_proposal_pdf(
            title="Proposta Comercial",
            client_name=p.client_name or "",
            service=p.service or "",
            deadline=p.deadline or "",
            price=p.price or "",
            proposal_text=p.proposal_text or "",
        )
    except Exception:
        logger.exception("Erro ao gerar PDF da proposta id=%s user_id=%s", p.id, user.id)
        raise

    filename = f"proposta_{p.id}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
