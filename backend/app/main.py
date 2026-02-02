# backend/main.py

import os
from dotenv import load_dotenv

# ✅ Carrega .env da raiz do backend, independente do CWD
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(dotenv_path=os.path.join(BASE_DIR, ".env"))

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from jinja2 import select_autoescape

from app.config import settings
from app.db.session import engine
from app.db.base import Base

# ✅ IMPORTANTE: garante que TODOS os models sejam registrados no Base antes do create_all()
import app.db.models  # noqa: F401

from app.auth.routes import router as auth_router
from app.routes import router as app_router
from app.payments.routes import router as payments_router


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)

    # ✅ PROVA: mostra exatamente qual arquivo está rodando
    @app.get("/__whoami")
    def whoami():
        return {"file": __file__, "cwd": os.getcwd(), "app_name": settings.app_name}

    # ✅ PING: rota que deve existir SEMPRE
    @app.get("/webhooks/ping")
    def ping_webhooks():
        return {"pong": True}

    # Banco: cria tabelas (agora com models carregados)
    Base.metadata.create_all(bind=engine)

    # Templates
    templates = Jinja2Templates(directory="app/templates")
    templates.env.autoescape = select_autoescape(["html", "xml"])
    templates.env.trim_blocks = True
    templates.env.lstrip_blocks = True

    templates.env.globals["APP_NAME"] = settings.app_name
    templates.env.globals["PAYWALL_PRICE_BRL"] = getattr(settings, "paywall_price_brl", "29,90")
    templates.env.globals["CHECKOUT_URL"] = getattr(settings, "checkout_url", "")
    templates.env.globals["KIWIFY_CHECKOUT_URL"] = getattr(settings, "kiwify_checkout_url", "")

    app.state.templates = templates

    # Static
    app.mount("/static", StaticFiles(directory="app/static"), name="static")

    # Routers
    app.include_router(auth_router)
    app.include_router(app_router)
    app.include_router(payments_router)

    # PermissionError -> redirects
    @app.exception_handler(PermissionError)
    async def permission_error_handler(request: Request, exc: PermissionError):
        msg = (str(exc) or "").lower()
        if "não pago" in msg or "nao pago" in msg or "not paid" in msg:
            return RedirectResponse(url="/paywall", status_code=303)
        return RedirectResponse(url="/login", status_code=303)

    # Health
    @app.get("/health")
    def health():
        return {"ok": True, "ai_mode": settings.ai_mode, "app_name": settings.app_name}

    return app


app = create_app()
