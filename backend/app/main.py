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

from sqlalchemy import text  # ✅ (novo) para executar SQL seguro no endpoint de migração

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

    # ======================================================
    # ✅ MIGRAÇÃO ONE-SHOT (Render Free não tem Shell)
    # - Cria colunas novas no Postgres via ALTER TABLE
    # - Protegido por MIGRATE_KEY (env var)
    # - Rode 1x e depois REMOVA essa rota
    # ======================================================
    MIGRATE_KEY = (os.getenv("MIGRATE_KEY") or "").strip()

    @app.get("/__migrate")
    def run_migration(key: str):
        # Proteção simples e suficiente para uso pontual
        if not MIGRATE_KEY or key != MIGRATE_KEY:
            return {"ok": False, "error": "unauthorized"}

        stmts = [
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS plan VARCHAR(20) NOT NULL DEFAULT 'free';",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS monthly_quota_used INT NOT NULL DEFAULT 0;",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS quota_reset_at TIMESTAMP NULL;",
            "UPDATE users SET plan = 'pro' WHERE is_paid = true;",
            "CREATE INDEX IF NOT EXISTS idx_users_plan ON users(plan);",
        ]

        try:
            with engine.begin() as conn:
                for s in stmts:
                    conn.execute(text(s))
            return {"ok": True, "applied": len(stmts)}
        except Exception as e:
            # não quebra app, só retorna erro
            return {"ok": False, "error": str(e)}

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
