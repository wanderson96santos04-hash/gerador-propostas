print(">>> KIWIFY ROUTES.PY CARREGADO (versao NEVER400 v4 - SCALE USER_ID + FIX POST-PAYMENT) <<<")

import os
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func

from app.db.session import SessionLocal
from app.db import models

# ✅ usa o parser "robusto" que você já tem
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


@router.post("/kiwify")
async def kiwify_webhook(request: Request):
    """
    Webhook da Kiwify.

    REGRA DE OURO:
    ✅ Nunca retornar 400/500 para a Kiwify (sempre 200).
    ✅ Se der erro, retorna 200 e registra motivo.

    MODO ESCALA:
    ✅ Prioriza liberar por user_id (enviado no link do checkout: ?user_id=123)
    ✅ Fallback por email (case-insensitive)
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
        # 2) Identificar event_id (pra idempotência)
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
        # 3) Só processar se for pagamento aprovado
        # =========================
        if not is_payment_approved(data):
            ev = _pick(data, "event", "type", "status") or "unknown"
            return {"ok": True, "ignored": True, "reason": "nao_aprovado", "event": ev}

        # =========================
        # 4) Extrair email do comprador (fallback)
        # =========================
        buyer_email = extract_buyer_email(data)
        buyer_email = buyer_email.strip().lower() if buyer_email else None

        # =========================
        # 4.5) Pegar user_id do checkout (MODO ESCALA)
        # =========================
        # A forma mais confiável é enviar ?user_id=<id> no link do checkout.
        # Alguns gateways também podem devolver em "metadata".
        user_id_raw = (
            request.query_params.get("user_id")
            or _pick(data, "user_id", "customer_id")
            or _pick(data.get("metadata", {}) if isinstance(data.get("metadata"), dict) else {}, "user_id")
            or _pick(data.get("custom_fields", {}) if isinstance(data.get("custom_fields"), dict) else {}, "user_id")
        )
        user_id = _safe_int(user_id_raw)

        # =========================
        # 5) Liberar acesso + idempotência (SEM travar antes do user)
        # =========================
        db: Session = SessionLocal()
        try:
            WebhookEvent = _get_webhook_event_model()

            # 5.0) Idempotência: se já processou, não faz nada
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

            # 5.1) Achar o usuário: PRIORIDADE user_id
            user = None
            if user_id is not None:
                user = db.query(models.User).filter(models.User.id == user_id).one_or_none()

            # 5.2) Fallback por email (case-insensitive)
            if user is None and buyer_email:
                user = (
                    db.query(models.User)
                    .filter(func.lower(models.User.email) == buyer_email)
                    .one_or_none()
                )

            if not user:
                # Não grava WebhookEvent aqui, pra permitir retry.
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

            # 5.3) Liberar acesso
            changed = False
            if not getattr(user, "is_paid", False):
                user.is_paid = True
                db.add(user)
                db.commit()
                changed = True
            else:
                db.rollback()

            # 5.4) Registrar idempotência só DEPOIS de liberar (se existir)
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
        # ✅ NUNCA MAIS 400/500 — SEMPRE 200
        body = await request.body()
        print("KIWIFY_WEBHOOK ERRO:", repr(e))
        print("KIWIFY_WEBHOOK QUERY:", dict(request.query_params))
        print("KIWIFY_WEBHOOK HEADER x-kiwify-token:", request.headers.get("x-kiwify-token"))
        print("KIWIFY_WEBHOOK BODY (primeiros 2000):", body.decode("utf-8", "ignore")[:2000])

        return {"ok": True, "ignored": True, "debug_error": str(e)}
