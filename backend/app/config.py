import os
from dataclasses import dataclass
from dotenv import load_dotenv

# Carrega o .env que está na RAIZ do backend (um nível acima da pasta app)
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))


def _get_env(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


@dataclass(frozen=True)
class Settings:
    # =========================
    # Segurança
    # =========================
    jwt_secret: str = _get_env("JWT_SECRET", "dev-secret-mude-isso")
    jwt_algorithm: str = _get_env("JWT_ALG", "HS256")
    jwt_exp_minutes: int = int(_get_env("JWT_EXP_MIN", "10080"))  # 7 dias

    # =========================
    # Banco de dados
    # =========================
    sqlite_path: str = _get_env("SQLITE_PATH", "./data/app.db")

    # =========================
    # IA (opcional)
    # =========================
    ai_mode: str = _get_env("AI_MODE", "stub")
    openai_api_key: str = _get_env("OPENAI_API_KEY", "")

    # =========================
    # App
    # =========================
    app_name: str = _get_env("APP_NAME", "Gerador de Propostas que Fecham Vendas")
    base_url: str = _get_env("BASE_URL", "http://127.0.0.1:8000")

    # =========================
    # Paywall / Venda (MVP)
    # =========================
    admin_key: str = _get_env("ADMIN_KEY", "123456")
    paywall_price_brl: str = _get_env("PAYWALL_PRICE_BRL", "29,90")

    # =========================
    # Kiwify
    # =========================
    kiwify_checkout_url: str = _get_env("KIWIFY_CHECKOUT_URL", "")
    kiwify_webhook_token: str = _get_env("KIWIFY_WEBHOOK_TOKEN", "mude-isto")


settings = Settings()
