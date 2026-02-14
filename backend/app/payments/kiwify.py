# backend/app/payments/kiwify.py
from __future__ import annotations

from typing import Any, Optional, Dict, Iterable
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


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


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


def _candidate_values(payload: Dict[str, Any]) -> Iterable[str]:
    """
    Coleta campos típicos que variam entre webhooks (venda única e recorrência).
    """
    return [
        _norm(payload.get("status")),
        _norm(payload.get("sale_status")),
        _norm(payload.get("event")),
        _norm(payload.get("type")),
        _norm(payload.get("name")),
        _norm(payload.get("action")),
        _norm(_dig(payload, "order", "status")),
        _norm(_dig(payload, "data", "status")),
        _norm(_dig(payload, "purchase", "status")),
        _norm(_dig(payload, "payment", "status")),
        _norm(_dig(payload, "transaction", "status")),
        # recorrência costuma aparecer como "subscription" / "recurring" / "renewal"
        _norm(_dig(payload, "subscription", "status")),
        _norm(_dig(payload, "data", "subscription_status")),
        _norm(_dig(payload, "data", "event")),
        _norm(_dig(payload, "data", "type")),
    ]


def is_payment_refunded_or_chargeback(payload: Dict[str, Any]) -> bool:
    """
    Detecta eventos negativos (reembolso/chargeback/cancelamento) para recorrência.
    Não altera o fluxo atual; serve pra você usar quando for controlar acesso.
    """
    payload = _normalize_payload(payload)
    if not isinstance(payload, dict):
        return False

    bad_values = {
        "refunded",
        "refund",
        "chargeback",
        "charged_back",
        "chargedback",
        "dispute",
        "canceled",
        "cancelled",
        "cancel",
        "voided",
        "failed",
        "declined",
        "denied",
        "reversed",
        "reversal",
        "expired",
        "unpaid",
    }

    for c in _candidate_values(payload):
        if not c:
            continue
        if c in bad_values:
            return True
        if c.endswith(".refunded") or c.endswith(".chargeback") or c.endswith(".canceled") or c.endswith(".cancelled"):
            return True
        if c.endswith(":refunded") or c.endswith(":chargeback") or c.endswith(":canceled") or c.endswith(":cancelled"):
            return True
        if "chargeback" in c or "refunded" in c or "cancel" in c:
            return True

    # alguns payloads trazem flags booleanas
    if bool(payload.get("refunded")) or bool(payload.get("chargeback")):
        return True

    return False


def is_payment_approved(payload: Dict[str, Any]) -> bool:
    """
    Verifica se o webhook representa um pagamento aprovado.
    Compatível com variações reais da Kiwify.
    (Mantém compatibilidade com o que já funciona e melhora para recorrência.)
    """
    payload = _normalize_payload(payload)
    if not isinstance(payload, dict):
        return False

    # Se for claramente um evento negativo, não aprova.
    if is_payment_refunded_or_chargeback(payload):
        return False

    # valores comuns vistos em webhooks/integrações (inclui recorrência)
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
        # recorrência (nomes comuns em integrações)
        "subscription_paid",
        "subscription.paid",
        "subscription_approved",
        "subscription.approved",
        "recurring_payment_approved",
        "recurring.payment_approved",
        "renewed",
        "subscription_renewed",
        "subscription.renewed",
    }

    # alguns payloads trazem flag booleana explícita
    if payload.get("approved") is True or payload.get("paid") is True:
        return True

    for c in _candidate_values(payload):
        if not c:
            continue
        if c in ok_values:
            return True

        # padrões "order.paid" / "sale.approved" / "subscription.paid"
        if (
            c.endswith(".approved")
            or c.endswith(".paid")
            or c.endswith(".succeeded")
            or c.endswith(".completed")
            or c.endswith(":approved")
            or c.endswith(":paid")
            or c.endswith(":succeeded")
            or c.endswith(":completed")
        ):
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
        # recorrência
        ("subscription", "customer", "email"),
        ("subscription", "customer", "email_address"),
        ("data", "subscription", "customer", "email"),
        ("data", "subscription", "customer", "email_address"),
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
