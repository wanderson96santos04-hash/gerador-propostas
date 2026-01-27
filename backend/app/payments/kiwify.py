# backend/app/payments/kiwify.py
from __future__ import annotations

from typing import Any, Optional, Dict
import json


def _normalize_payload(payload: Any) -> Any:
    """
    Kiwify/PowerShell às vezes manda payload como string JSON ou lista.
    Normaliza para dict quando possível.
    """
    # Se vier como string JSON
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:
            return payload

    # Se vier como lista (pega o primeiro dict)
    if isinstance(payload, list) and payload:
        first = payload[0]
        if isinstance(first, dict):
            return first

    return payload


def _dig(d: Any, *keys: str) -> Optional[Any]:
    """
    Acessa chaves aninhadas com segurança:
    _dig(payload, "customer", "email") -> payload["customer"]["email"] se existir.
    """
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur


def _as_email(value: Any) -> Optional[str]:
    if not value or not isinstance(value, str):
        return None
    email = value.strip().lower()
    if "@" not in email:
        return None
    return email


def is_payment_approved(payload: Dict[str, Any]) -> bool:
    """
    Decide se o evento representa pagamento aprovado.
    Aceita variações comuns:
    - status / sale_status / event / type
    - order.status / data.status / purchase.status
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
        norm(_dig(payload, "order", "status")),
        norm(_dig(payload, "data", "status")),
        norm(_dig(payload, "purchase", "status")),
    ]

    ok_values = {"approved", "paid", "payment_approved", "completed", "success"}
    return any(c in ok_values for c in candidates)


def extract_buyer_email(payload: Dict[str, Any]) -> Optional[str]:
    """
    Extrai o email do comprador tentando vários formatos comuns.
    Prioriza customer.email.
    """
    payload = _normalize_payload(payload)
    if not isinstance(payload, dict):
        return None

    paths = [
        ("customer", "email"),
        ("customer", "email_address"),
        ("buyer", "email"),
        ("buyer", "email_address"),
        ("user", "email"),
        ("user", "email_address"),
        ("order", "customer", "email"),
        ("order", "buyer", "email"),
        ("data", "customer", "email"),
        ("data", "buyer", "email"),
        ("purchase", "customer", "email"),
        ("purchase", "buyer", "email"),
    ]

    for p in paths:
        val = _dig(payload, *p)
        email = _as_email(val)
        if email:
            return email

    direct = _as_email(payload.get("email"))
    if direct:
        return direct

    return None
