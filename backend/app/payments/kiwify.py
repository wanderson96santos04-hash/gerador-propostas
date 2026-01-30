# backend/app/payments/kiwify.py
from __future__ import annotations

from typing import Any, Optional, Dict
import json


def _normalize_payload(payload: Any) -> Any:
    """
    A Kiwify às vezes envia:
    - string JSON
    - lista com um dict dentro
    - dict com campos internos em string JSON (ex: data)
    Normalizamos tudo para dict quando possível.
    """
    # Se vier como string JSON
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:
            return payload

    # Se vier como lista, pega o primeiro item válido
    if isinstance(payload, list) and payload:
        first = payload[0]
        if isinstance(first, dict):
            payload = first

    # Se vier como dict e tiver "data" ou "payload" como string JSON, tenta expandir
    if isinstance(payload, dict):
        for k in ("data", "payload"):
            v = payload.get(k)
            if isinstance(v, str):
                try:
                    payload[k] = json.loads(v)
                except Exception:
                    pass

    return payload


def _dig(d: Any, *keys: str) -> Optional[Any]:
    """
    Acessa chaves aninhadas com segurança:
    _dig(payload, "customer", "email")
    """
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur


def _as_email(value: Any) -> Optional[str]:
    """
    Normaliza e valida email.
    """
    if not value or not isinstance(value, str):
        return None
    email = value.strip().lower()
    # validação simples (suficiente para webhook)
    if "@" not in email or "." not in email:
        return None
    return email


def is_payment_approved(payload: Dict[str, Any]) -> bool:
    """
    Verifica se o webhook representa um pagamento aprovado.
    Compatível com variações reais da Kiwify.
    """
    payload = _normalize_payload(payload)
    if not isinstance(payload, dict):
        return False

    def norm(x: Any) -> str:
        return str(x or "").strip().lower()

    candidates = [
        norm(payload.get("status")),
        norm(payload.get("sale_status")),
        norm(payload.get("event")),
        norm(payload.get("type")),
        norm(payload.get("name")),
        norm(_dig(payload, "order", "status")),
        norm(_dig(payload, "data", "status")),
        norm(_dig(payload, "purchase", "status")),
        norm(_dig(payload, "payment", "status")),
        norm(_dig(payload, "transaction", "status")),
    ]

    # valores comuns vistos em webhooks/integrações
    ok_values = {
        "approved",
        "paid",
        "payment_approved",
        "payment-approved",
        "payment.approved",
        "completed",
        "success",
        "succeeded",
        "confirmed",
        "paid_out",
        "paidout",
    }

    # Alguns eventos vêm como "order.paid" / "sale.approved" etc.
    for c in candidates:
        if c in ok_values:
            return True
        if c.endswith(".approved") or c.endswith(".paid") or c.endswith(":approved") or c.endswith(":paid"):
            return True

    return False


def extract_buyer_email(payload: Dict[str, Any]) -> Optional[str]:
    """
    Extrai o email do comprador do webhook da Kiwify.
    Testa múltiplos caminhos porque a Kiwify varia o formato.
    """
    payload = _normalize_payload(payload)
    if not isinstance(payload, dict):
        return None

    paths = [
        # comuns
        ("customer", "email"),
        ("customer", "email_address"),
        ("buyer", "email"),
        ("buyer", "email_address"),
        ("user", "email"),
        ("user", "email_address"),
        # variações aninhadas
        ("order", "customer", "email"),
        ("order", "customer", "email_address"),
        ("order", "buyer", "email"),
        ("order", "buyer", "email_address"),
        ("data", "customer", "email"),
        ("data", "customer", "email_address"),
        ("data", "buyer", "email"),
        ("data", "buyer", "email_address"),
        ("purchase", "customer", "email"),
        ("purchase", "customer", "email_address"),
        ("purchase", "buyer", "email"),
        ("purchase", "buyer", "email_address"),
        # às vezes vem direto em data
        ("data", "email"),
        ("data", "email_address"),
    ]

    for path in paths:
        val = _dig(payload, *path)
        email = _as_email(val)
        if email:
            return email

    # fallback direto
    return _as_email(payload.get("email")) or _as_email(payload.get("email_address"))
