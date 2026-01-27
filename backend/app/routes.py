# backend/app/routes.py
from __future__ import annotations

from datetime import datetime

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

    proposal_text = generate_proposal_text(data)

    summary = (
        f"Cliente: {data['client_name']}\n"
        f"Serviço: {data['service']}\n"
        f"Prazo: {data['deadline']}\n"
        f"Preço: {data['price']}\n"
        f"Pagamento: {data['payment_terms']}\n"
        f"Tom: {data['tone']} | Objetivo: {data['objective']}\n"
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
