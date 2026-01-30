# backend/app/auth/routes.py
import os  # necessário para ler KIWIFY_CHECKOUT_URL do ambiente

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse, PlainTextResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.db.models import User
from app.auth.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
)

router = APIRouter()

COOKIE_NAME = "access_token"


# =========================
# AUTH HELPERS
# =========================
def get_current_user(request: Request, db: Session) -> User | None:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None

    payload = decode_access_token(token)
    if not payload:
        return None

    sub = payload.get("sub")
    if not sub:
        return None

    try:
        user_id = int(sub)
    except ValueError:
        return None

    return db.query(User).filter(User.id == user_id).first()


def require_user(request: Request, db: Session) -> User:
    user = get_current_user(request, db)
    if not user:
        raise PermissionError("não autenticado")
    return user


def require_paid_user(request: Request, db: Session) -> User:
    """
    Produto vendável:
    - precisa estar logado
    - precisa estar com is_paid=True
    """
    user = require_user(request, db)
    if not user.is_paid:
        raise PermissionError("não pago")
    return user


# =========================
# REGISTER
# =========================
@router.get("/register")
def register_page(request: Request):
    return request.app.state.templates.TemplateResponse(
        "register.html",
        {"request": request, "error": None},
    )


@router.post("/register")
def register_action(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    email = (email or "").strip().lower()
    if "@" not in email or "." not in email or len(email) > 255:
        return request.app.state.templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Email inválido."},
            status_code=400,
        )

    if db.query(User).filter(User.email == email).first():
        return request.app.state.templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Esse email já está cadastrado."},
            status_code=400,
        )

    try:
        pwd_hash = hash_password(password)
    except ValueError as e:
        return request.app.state.templates.TemplateResponse(
            "register.html",
            {"request": request, "error": str(e)},
            status_code=400,
        )

    # usuário entra NÃO pago
    user = User(email=email, password_hash=pwd_hash, is_paid=False)
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id, user.email)

    resp = RedirectResponse(url="/paywall", status_code=303)
    resp.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        path="/",
        max_age=7 * 24 * 60 * 60,
    )
    return resp


# =========================
# LOGIN / LOGOUT
# =========================
@router.get("/login")
def login_page(request: Request):
    return request.app.state.templates.TemplateResponse(
        "login.html",
        {"request": request, "error": None},
    )


@router.post("/login")
def login_action(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    email = (email or "").strip().lower()
    user = db.query(User).filter(User.email == email).first()

    if not user or not verify_password(password, user.password_hash):
        return request.app.state.templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Email ou senha inválidos."},
            status_code=401,
        )

    token = create_access_token(user.id, user.email)
    next_url = "/create" if user.is_paid else "/paywall"

    resp = RedirectResponse(url=next_url, status_code=303)
    resp.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        path="/",
        max_age=7 * 24 * 60 * 60,
    )
    return resp


@router.get("/logout")
def logout():
    resp = RedirectResponse(url="/login", status_code=303)
    resp.delete_cookie(COOKIE_NAME, path="/")
    return resp


# =========================
# PAYWALL (DEBUG DEFINITIVO)
# =========================
@router.get("/paywall")
def paywall(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    if user.is_paid:
        return RedirectResponse(url="/create", status_code=303)

    checkout_url = (os.getenv("KIWIFY_CHECKOUT_URL") or "").strip()
    if not checkout_url:
        checkout_url = (getattr(settings, "kiwify_checkout_url", "") or "").strip()

    # 🔴 DEBUG DEFINITIVO (prova de deploy)
    print(
        "PAYWALL DEBUG >>> user_id =",
        user.id,
        "| checkout_before =",
        checkout_url,
    )

    if checkout_url:
        sep = "&" if "?" in checkout_url else "?"
        checkout_url = f"{checkout_url}{sep}user_id={user.id}&dbg=PAYWALL_OK"

    return request.app.state.templates.TemplateResponse(
        "paywall.html",
        {
            "request": request,
            "user": user,
            "checkout_url": checkout_url,
        },
    )


# =========================
# ADMIN UNLOCK (MVP)
# =========================
@router.get("/admin/unlock")
def admin_unlock(
    request: Request,
    email: str,
    key: str,
    db: Session = Depends(get_db),
):
    admin_key = (settings.admin_key or "").strip()
    if not admin_key or key != admin_key:
        return PlainTextResponse("forbidden", status_code=403)

    email = (email or "").strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return PlainTextResponse("user_not_found", status_code=404)

    user.is_paid = True
    db.add(user)
    db.commit()

    return PlainTextResponse("ok_unlocked")


# =========================
# DEBUG AUXILIAR
# =========================
@router.get("/debug-cookie")
def debug_cookie(request: Request):
    token = request.cookies.get(COOKIE_NAME)
    return PlainTextResponse(f"cookie_recebido={bool(token)}")


@router.get("/debug-kiwify")
def debug_kiwify():
    v = (os.getenv("KIWIFY_CHECKOUT_URL") or "").strip()
    return PlainTextResponse(
        f"KIWIFY_CHECKOUT_URL={'OK' if v else 'VAZIO'} len={len(v)} value={v[:80]}"
    )
