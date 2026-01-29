print(">>> KIWIFY ROUTES.PY CARREGADO (versao NEVER400 v1) <<<")

import os
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.db.session import SessionLocal
from app.db import models

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _pick(d: Dict[str, Any], *keys: str) -> Optional[Any]:
    for k in keys:
        v = d.get(k)
        if v not in (None, "", {}, []):
            return v
    return None


def _nested(payload: Dict[str, Any]) -> Dict[str, Any]:
    if isinstance(payload.get("data"), dict):
        return payload["data"]
    if isinstance(payload.get("payload"), dict):
        return payload["payload"]
    return payload


@router.post("/kiwify")
async def kiwify_webhook(request: Request):
    """
    Webhook da Kiwify.

    REGRA DE OURO (teste/produção):
    ✅ Nunca retornar 400/500 para a Kiwify durante testes.
    ✅ Se der qualquer erro, retorna 200 e loga motivo.
    """

    try:
        # =========================
        # 0) Capturar token (sem derrubar)
        # =========================
        expected_token = os.getenv("KIWIFY_WEBHOOK_TOKEN")

        received_token = (
            request.headers.get("x-kiwify-token")
            or request.headers.get("X-Kiwify-Token")
            or request.query_params.get("token")
        )

        # Se existir token esperado, mas não bater -> não derruba (retorna 200)
        if expected_token:
            if not received_token:
                return {"ok": True, "ignored": True, "reason": "token ausente"}
            if isinstance(received_token, str) and received_token.lower().startswith("bearer "):
                received_token = received_token.split(" ", 1)[1].strip()
            if received_token != expected_token:
                return {"ok": True, "ignored": True, "reason": "token invalido"}

        # =========================
        # 1) Ler payload (robusto)
        # =========================
        payload: Dict[str, Any] = {}
        try:
            payload = await request.json()
        except Exception:
            # tenta form-data
            try:
                form = await request.form()
                payload = dict(form) if form else {}
            except Exception:
                payload = {}

        # Teste da Kiwify pode vir vazio -> 200
        if not payload:
            return {"ok": True, "ignored": True, "reason": "payload vazio (teste?)"}

        data = _nested(payload)

        # =========================
        # 2) Identificar evento e tipo
        # =========================
        event_id = _pick(data, "id", "event_id", "order_id", "transaction_id", "charge_id")
        event_type = _pick(data, "event", "type", "status")

        if not event_id or not event_type:
            # NÃO derruba com 400
            return {
                "ok": True,
                "ignored": True,
                "reason": "sem event_id/event_type",
                "keys": list(data.keys())[:50],
            }

        # =========================
        # 3) Só processar “pagamento aprovado”
        # =========================
        paid_events = {
            "order_paid",
            "payment_confirmed",
            "order.approved",
            "approved",
            "paid",
            "order.paid",
            "order_paid_success",
        }

        if str(event_type).lower() not in {x.lower() for x in paid_events}:
            return {"ok": True, "ignored": True, "event_type": event_type}

        # =========================
        # 4) Pegar email do comprador
        # =========================
        customer = data.get("customer") or data.get("buyer") or {}
        if not isinstance(customer, dict):
            customer = {}

        buyer_email = (
            customer.get("email")
            or data.get("email")
            or data.get("customer_email")
            or data.get("buyer_email")
        )

        if not buyer_email:
            return {"ok": True, "ignored": True, "reason": "sem email do comprador"}

        # =========================
        # 5) Idempotência + liberar acesso
        # =========================
        db: Session = SessionLocal()
        try:
            try:
                event = models.WebhookEvent(
                    event_id=str(event_id),
                    event_type=str(event_type),
                    processed_at=datetime.utcnow(),
                )
                db.add(event)
                db.commit()
            except IntegrityError:
                db.rollback()
                return {"ok": True, "idempotent": True}

            user = db.query(models.User).filter(models.User.email == buyer_email).one_or_none()
            if not user:
                return {"ok": True, "ignored": True, "reason": f"user nao encontrado: {buyer_email}"}

            if not user.is_paid:
                user.is_paid = True
                db.add(user)
                db.commit()

            return {"ok": True, "paid": True, "email": buyer_email, "user_id": user.id}

        finally:
            db.close()

    except Exception as e:
        # ✅ NUNCA MAIS 400/500 — SEMPRE 200
        body = await request.body()
        print("KIWIFY_WEBHOOK ERRO:", repr(e))
        print("KIWIFY_WEBHOOK QUERY:", dict(request.query_params))
        print("KIWIFY_WEBHOOK HEADER x-kiwify-token:", request.headers.get("x-kiwify-token"))
        print("KIWIFY_WEBHOOK BODY (primeiros 2000):", body.decode("utf-8", "ignore")[:2000])

        return {"ok": True, "ignored": True, "debug_error": str(e)}
