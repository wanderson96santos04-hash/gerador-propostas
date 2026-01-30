print(">>> KIWIFY ROUTES.PY CARREGADO (versao NEVER400 v5 - REAL SCALE VIA CUSTOM_FIELDS/METADATA) <<<")

import os
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func

from app.db.session import SessionLocal
from app.db import models

from app.payments.kiwify import is_payment_approved, extract_buyer_email

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _pick(d: Dict[str, Any], *keys: str) -> Optional[Any]:
    for k in keys:
        v = d.get(k)
        if v not in (None, "", {}, []):
            return v
    return None


def _nested(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Algumas integrações mandam o conteúdo dentro de 'data' ou 'payload'.
    Se não existir, usa o payload inteiro.
    """
    if isinstance(payload.get("data"), dict):
        return payload["data"]
    if isinstance(payload.get("payload"), dict):
        return payload["payload"]
    return payload


def _get_webhook_event_model():
    """
    WebhookEvent pode não existir / não estar migrado em produção.
    Não pode impedir a liberação do usuário.
    """
    return getattr(models, "WebhookEvent", None)


def _safe_int(v: Any) -> Optional[int]:
    try:
        if v is None:
            return None
        if isinstance(v, bool):
            return None
        if isinstance(v, int):
            return v
        s = str(v).strip()
        if not s:
            return None
        return int(s)
    except Exception:
        return None


def _extract_user_id_from_payload(data: Dict[str, Any]) -> Optional[int]:
    """
    ✅ O user_id NÃO vem em request.query_params no webhook da Kiwify.
    Ele precisa estar DENTRO do payload, em algum campo customizado/metadata.

    Tentamos vários locais comuns:
    - data.user_id / data.customer_id
    - data.metadata.user_id
    - data.custom_fields.user_id
    - data.order.custom_fields.user_id
    - data.order.metadata.user_id
    - data.buyer.custom_fields.user_id
    - data.buyer.metadata.user_id
    """
    # 1) nível raiz
    direct = _pick(data, "user_id", "customer_id")
    uid = _safe_int(direct)
    if uid is not None:
        return uid

    # 2) metadata raiz
    meta = data.get("metadata")
    if isinstance(meta, dict):
        uid = _safe_int(_pick(meta, "user_id", "customer_id", "external_id"))
        if uid is not None:
            return uid

    # 3) custom_fields raiz
    cf = data.get("custom_fields")
    if isinstance(cf, dict):
        uid = _safe_int(_pick(cf, "user_id", "customer_id", "external_id"))
        if uid is not None:
            return uid

    # 4) order.*
    order = data.get("order")
    if isinstance(order, dict):
        order_cf = order.get("custom_fields")
        if isinstance(order_cf, dict):
            uid = _safe_int(_pick(order_cf, "user_id", "customer_id", "external_id"))
            if uid is not None:
                return uid

        order_meta = order.get("metadata")
        if isinstance(order_meta, dict):
            uid = _safe_int(_pick(order_meta, "user_id", "customer_id", "external_id"))
            if uid is not None:
                return uid

    # 5) buyer.*
    buyer = data.get("buyer")
    if isinstance(buyer, dict):
        buyer_cf = buyer.get("custom_fields")
        if isinstance(buyer_cf, dict):
            uid = _safe_int(_pick(buyer_cf, "user_id", "customer_id", "external_id"))
            if uid is not None:
                return uid

        buyer_meta = buyer.get("metadata")
        if isinstance(buyer_meta, dict):
            uid = _safe_int(_pick(buyer_meta, "user_id", "customer_id", "external_id"))
            if uid is not None:
                return uid

    return None


@router.post("/kiwify")
async def kiwify_webhook(request: Request):
    """
    Webhook da Kiwify.

    REGRA DE OURO:
    ✅ Nunca retornar 400/500 para a Kiwify (sempre 200).
    ✅ Se der erro, retorna 200 e registra motivo.

    ✅ MODO ESCALA (correto):
    - user_id tem que estar NO PAYLOAD (custom_fields/metadata)
    - fallback por email (case-insensitive)
    """

    try:
        # =========================
        # 0) Validar token (sem derrubar)
        # =========================
        expected_token = (os.getenv("KIWIFY_WEBHOOK_TOKEN") or "").strip()

        received_token = (
            request.headers.get("x-kiwify-token")
            or request.headers.get("X-Kiwify-Token")
            or request.query_params.get("token")
        )

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
            try:
                form = await request.form()
                payload = dict(form) if form else {}
            except Exception:
                payload = {}

        if not payload:
            return {"ok": True, "ignored": True, "reason": "payload vazio (teste?)"}

        data = _nested(payload)

        # =========================
        # 2) Identificar event_id (idempotência)
        # =========================
        event_id = _pick(
            data,
            "id",
            "event_id",
            "order_id",
            "transaction_id",
            "charge_id",
            "sale_id",
        )
        if not event_id:
            raw = await request.body()
            event_id = f"noid-{len(raw)}-{datetime.utcnow().isoformat()}"

        # =========================
        # 3) Só processar se aprovado
        # =========================
        if not is_payment_approved(data):
            ev = _pick(data, "event", "type", "status") or "unknown"
            return {"ok": True, "ignored": True, "reason": "nao_aprovado", "event": ev}

        # =========================
        # 4) Extrair user_id (REAL) + email fallback
        # =========================
        user_id = _extract_user_id_from_payload(data)

        buyer_email = extract_buyer_email(data)
        buyer_email = buyer_email.strip().lower() if buyer_email else None

        print("KIWIFY_WEBHOOK >>> approved",
              "| event_id=", str(event_id),
              "| user_id=", user_id,
              "| email=", buyer_email)

        # =========================
        # 5) Liberar acesso + idempotência
        # =========================
        db: Session = SessionLocal()
        try:
            WebhookEvent = _get_webhook_event_model()

            # 5.0) idempotência
            if WebhookEvent is not None:
                try:
                    already = (
                        db.query(WebhookEvent)
                        .filter(WebhookEvent.event_id == str(event_id))
                        .one_or_none()
                    )
                    if already:
                        return {"ok": True, "idempotent": True, "event_id": str(event_id)}
                except Exception as e:
                    print("KIWIFY_WEBHOOK idempotency check error (ignored):", repr(e))

            # 5.1) achar usuário: prioridade user_id
            user = None
            if user_id is not None:
                user = db.query(models.User).filter(models.User.id == user_id).one_or_none()

            # 5.2) fallback por email
            if user is None and buyer_email:
                user = (
                    db.query(models.User)
                    .filter(func.lower(models.User.email) == buyer_email)
                    .one_or_none()
                )

            if not user:
                reason = "user_nao_encontrado"
                if user_id is not None and buyer_email:
                    reason += f":user_id={user_id};email={buyer_email}"
                elif user_id is not None:
                    reason += f":user_id={user_id}"
                elif buyer_email:
                    reason += f":email={buyer_email}"
                else:
                    reason += ":sem_user_id_sem_email"
                return {"ok": True, "ignored": True, "reason": reason, "event_id": str(event_id)}

            # 5.3) liberar
            changed = False
            if not getattr(user, "is_paid", False):
                user.is_paid = True
                db.add(user)
                db.commit()
                changed = True
            else:
                db.rollback()

            # 5.4) registrar event
            if WebhookEvent is not None:
                try:
                    event = WebhookEvent(
                        event_id=str(event_id),
                        event_type=str(_pick(data, "event", "type", "status") or "approved"),
                        processed_at=datetime.utcnow(),
                    )
                    db.add(event)
                    db.commit()
                except IntegrityError:
                    db.rollback()
                except Exception as e:
                    db.rollback()
                    print("KIWIFY_WEBHOOK event record error (ignored):", repr(e))

            return {
                "ok": True,
                "paid": True,
                "changed": changed,
                "email": buyer_email,
                "user_id": user.id,
                "event_id": str(event_id),
            }

        finally:
            db.close()

    except Exception as e:
        body = await request.body()
        print("KIWIFY_WEBHOOK ERRO:", repr(e))
        print("KIWIFY_WEBHOOK QUERY:", dict(request.query_params))
        print("KIWIFY_WEBHOOK HEADER x-kiwify-token:", request.headers.get("x-kiwify-token"))
        print("KIWIFY_WEBHOOK BODY (primeiros 2000):", body.decode("utf-8", "ignore")[:2000])
        return {"ok": True, "ignored": True, "debug_error": str(e)}
