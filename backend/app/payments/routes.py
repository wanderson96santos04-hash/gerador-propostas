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

DEBUG_PAYMENTS = (os.getenv("DEBUG_PAYMENTS") == "1")

if DEBUG_PAYMENTS:
    print(">>> KIWIFY ROUTES.PY CARREGADO (versao NEVER400 v8 - FREE/PRO ready + SAFE ATTRS + PRODUCT MAP) <<<")

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


# =========================
# ✅ CONFIG PRO (RECORRÊNCIA)
# =========================
# Coloque no .env (recomendado):
# KIWIFY_PRO_PRODUCT_ID=xxxx
# KIWIFY_PRO_OFFER_ID=yyyy
# KIWIFY_PRO_PLAN_ID=zzzz  (se existir no seu payload)
#
# Obs: se você ainda não sabe os IDs, deixa vazio. O código NÃO quebra.
KIWIFY_PRO_PRODUCT_ID = (os.getenv("KIWIFY_PRO_PRODUCT_ID") or "").strip()
KIWIFY_PRO_OFFER_ID = (os.getenv("KIWIFY_PRO_OFFER_ID") or "").strip()
KIWIFY_PRO_PLAN_ID = (os.getenv("KIWIFY_PRO_PLAN_ID") or "").strip()


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


def _get_webhook_event_model():
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


def _safe_str(v: Any) -> str:
    return str(v or "").strip()


def _set_attr_if_exists(obj: Any, attr: str, value: Any) -> bool:
    """
    Seta atributo somente se existir no model, sem quebrar o sistema atual.
    Retorna True se setou.
    """
    try:
        if hasattr(obj, attr):
            setattr(obj, attr, value)
            return True
    except Exception:
        pass
    return False


def _extract_user_id_from_payload(data: Dict[str, Any]) -> Optional[int]:
    """
    Tenta achar o user_id dentro do payload (custom_fields/metadata),
    e também aceita s1 (muito comum na Kiwify).
    """

    # 0) tracking.* (alguns webhooks colocam s1 aqui)
    tracking = data.get("tracking")
    if isinstance(tracking, dict):
        uid = _safe_int(_pick(tracking, "s1", "s2", "s3", "s4", "s5"))
        if uid is not None:
            return uid

    # 1) s1 / s2 (tracking no root)
    uid = _safe_int(_pick(data, "s1", "s2", "s3", "s4", "s5"))
    if uid is not None:
        return uid

    # 2) nível raiz
    uid = _safe_int(_pick(data, "user_id", "customer_id", "external_id"))
    if uid is not None:
        return uid

    # 3) metadata raiz
    meta = data.get("metadata")
    if isinstance(meta, dict):
        uid = _safe_int(_pick(meta, "user_id", "customer_id", "external_id", "s1"))
        if uid is not None:
            return uid

    # 4) custom_fields raiz
    cf = data.get("custom_fields")
    if isinstance(cf, dict):
        uid = _safe_int(_pick(cf, "user_id", "customer_id", "external_id", "s1"))
        if uid is not None:
            return uid

    # 5) order.*
    order = data.get("order")
    if isinstance(order, dict):
        order_cf = order.get("custom_fields")
        if isinstance(order_cf, dict):
            uid = _safe_int(_pick(order_cf, "user_id", "customer_id", "external_id", "s1"))
            if uid is not None:
                return uid

        order_meta = order.get("metadata")
        if isinstance(order_meta, dict):
            uid = _safe_int(_pick(order_meta, "user_id", "customer_id", "external_id", "s1"))
            if uid is not None:
                return uid

        order_tracking = order.get("tracking")
        if isinstance(order_tracking, dict):
            uid = _safe_int(_pick(order_tracking, "s1", "s2", "s3", "s4", "s5"))
            if uid is not None:
                return uid

    # 6) buyer.*
    buyer = data.get("buyer")
    if isinstance(buyer, dict):
        buyer_cf = buyer.get("custom_fields")
        if isinstance(buyer_cf, dict):
            uid = _safe_int(_pick(buyer_cf, "user_id", "customer_id", "external_id", "s1"))
            if uid is not None:
                return uid

        buyer_meta = buyer.get("metadata")
        if isinstance(buyer_meta, dict):
            uid = _safe_int(_pick(buyer_meta, "user_id", "customer_id", "external_id", "s1"))
            if uid is not None:
                return uid

        buyer_tracking = buyer.get("tracking")
        if isinstance(buyer_tracking, dict):
            uid = _safe_int(_pick(buyer_tracking, "s1", "s2", "s3", "s4", "s5"))
            if uid is not None:
                return uid

    return None


def _extract_product_markers(data: Dict[str, Any]) -> Dict[str, str]:
    """
    Extrai possíveis IDs de produto/oferta/plano do payload (varia na Kiwify).
    Retorna strings normalizadas.
    """
    # possíveis caminhos (root / order / data / purchase etc.)
    candidates = [
        ("product_id",),
        ("offer_id",),
        ("plan_id",),
        ("subscription_plan_id",),
        ("product", "id"),
        ("offer", "id"),
        ("plan", "id"),
        ("order", "product_id"),
        ("order", "offer_id"),
        ("order", "plan_id"),
        ("order", "subscription_plan_id"),
        ("data", "product_id"),
        ("data", "offer_id"),
        ("data", "plan_id"),
        ("purchase", "product_id"),
        ("purchase", "offer_id"),
        ("purchase", "plan_id"),
    ]

    out = {"product_id": "", "offer_id": "", "plan_id": ""}
    for path in candidates:
        cur: Any = data
        ok = True
        for k in path:
            if not isinstance(cur, dict) or k not in cur:
                ok = False
                break
            cur = cur[k]
        if not ok:
            continue

        val = _safe_str(cur)
        if not val:
            continue

        key = path[-1]
        if "product" in key:
            out["product_id"] = out["product_id"] or val
        elif "offer" in key:
            out["offer_id"] = out["offer_id"] or val
        elif "plan" in key:
            out["plan_id"] = out["plan_id"] or val

    return out


def _is_pro_purchase(data: Dict[str, Any]) -> bool:
    """
    Decide se o evento aprovado deve ativar PRO (recorrência).
    Regra:
    - Se você setar KIWIFY_PRO_PRODUCT_ID / OFFER_ID / PLAN_ID, bate por eles
    - Se não setar, não arrisca (não ativa Pro “por engano”).
    """
    markers = _extract_product_markers(data)

    if DEBUG_PAYMENTS:
        print(
            "KIWIFY_WEBHOOK >>> markers:",
            markers,
            "| env:",
            {"PRO_PRODUCT": KIWIFY_PRO_PRODUCT_ID, "PRO_OFFER": KIWIFY_PRO_OFFER_ID, "PRO_PLAN": KIWIFY_PRO_PLAN_ID},
        )

    # Se não configurou nada, não tenta adivinhar
    if not (KIWIFY_PRO_PRODUCT_ID or KIWIFY_PRO_OFFER_ID or KIWIFY_PRO_PLAN_ID):
        return False

    if KIWIFY_PRO_PRODUCT_ID and markers["product_id"] == KIWIFY_PRO_PRODUCT_ID:
        return True
    if KIWIFY_PRO_OFFER_ID and markers["offer_id"] == KIWIFY_PRO_OFFER_ID:
        return True
    if KIWIFY_PRO_PLAN_ID and markers["plan_id"] == KIWIFY_PRO_PLAN_ID:
        return True

    return False


@router.post("/kiwify")
async def kiwify_webhook(request: Request):
    """
    REGRA:
    - nunca 400/500 (sempre 200)
    - valida token SEM derrubar
    - libera por user_id (payload/s1) OU fallback por email
    - ✅ agora: diferencia FREE vs PRO (recorrência) sem quebrar is_paid atual
    """
    try:
        # =========================
        # 0) Validar token (aceita signature também)
        # =========================
        expected_token = (os.getenv("KIWIFY_WEBHOOK_TOKEN") or "").strip()

        received_token = (
            request.headers.get("x-kiwify-token")
            or request.headers.get("X-Kiwify-Token")
            or request.query_params.get("token")
            or request.query_params.get("signature")  # ✅ aceita signature
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

        if DEBUG_PAYMENTS:
            # cuidado: loga só quando DEBUG_PAYMENTS=1
            print("KIWIFY_WEBHOOK >>> payload_keys=", list(payload.keys())[:30], "| data_keys=", list(data.keys())[:30])

        # =========================
        # 2) event_id (idempotência)
        # =========================
        event_id = _pick(
            data, "id", "event_id", "order_id", "transaction_id", "charge_id", "sale_id"
        )
        if not event_id:
            raw = await request.body()
            event_id = f"noid-{len(raw)}-{datetime.utcnow().isoformat()}"

        # =========================
        # 3) só aprovado
        # =========================
        if not is_payment_approved(data):
            ev = _pick(data, "event", "type", "status") or "unknown"
            return {"ok": True, "ignored": True, "reason": "nao_aprovado", "event": ev}

        # =========================
        # 4) user_id real + email fallback
        # =========================
        user_id = _extract_user_id_from_payload(data)

        buyer_email = extract_buyer_email(data)
        buyer_email = buyer_email.strip().lower() if buyer_email else None

        # ✅ Decide se esse pagamento ativa PRO (recorrência)
        is_pro = _is_pro_purchase(data)

        if DEBUG_PAYMENTS:
            print(
                "KIWIFY_WEBHOOK >>> approved",
                "| event_id=", str(event_id),
                "| user_id=", user_id,
                "| email=", buyer_email,
                "| is_pro=", is_pro,
            )

        # =========================
        # 5) liberar + idempotência
        # =========================
        db: Session = SessionLocal()
        try:
            WebhookEvent = _get_webhook_event_model()

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
                    if DEBUG_PAYMENTS:
                        print("KIWIFY_WEBHOOK idempotency check error (ignored):", repr(e))

            user = None

            # prioridade user_id
            if user_id is not None:
                user = db.query(models.User).filter(models.User.id == user_id).one_or_none()

            # fallback email (case-insensitive)
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

                if DEBUG_PAYMENTS:
                    print("KIWIFY_WEBHOOK >>>", reason, "| event_id=", str(event_id))
                return {"ok": True, "ignored": True, "reason": reason, "event_id": str(event_id)}

            changed = False

            # ✅ REGRA NOVA (sem quebrar): só ativa "pago" se for PRO
            # Se você quer manter o pagamento único antigo como PRO também,
            # configure os IDs dele em KIWIFY_PRO_* (recomendado).
            if is_pro:
                if not getattr(user, "is_paid", False):
                    user.is_paid = True
                    changed = True

                # Se seu model tiver campos extras (não quebra se não tiver)
                _set_attr_if_exists(user, "plan", "pro")
                _set_attr_if_exists(user, "paid_plan", "pro")
                _set_attr_if_exists(user, "subscription_status", "active")
                _set_attr_if_exists(user, "paid_at", datetime.utcnow())
                _set_attr_if_exists(user, "last_payment_at", datetime.utcnow())
                _set_attr_if_exists(user, "payment_provider", "kiwify")

                db.add(user)
                db.commit()
            else:
                # Não ativa pago (fica Free)
                db.rollback()

            # registra evento (idempotência)
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
                    if DEBUG_PAYMENTS:
                        print("KIWIFY_WEBHOOK event record error (ignored):", repr(e))

            if DEBUG_PAYMENTS:
                print(
                    "KIWIFY_WEBHOOK >>> done | user_id=", user.id,
                    "| changed=", changed,
                    "| is_pro=", is_pro,
                    "| event_id=", str(event_id)
                )

            return {
                "ok": True,
                "approved": True,
                "is_pro": is_pro,
                "paid": bool(getattr(user, "is_paid", False)),
                "changed": changed,
                "email": buyer_email,
                "user_id": user.id,
                "event_id": str(event_id),
            }

        finally:
            db.close()

    except Exception as e:
        # Nunca falha: sempre 200.
        if DEBUG_PAYMENTS:
            body = await request.body()
            print("KIWIFY_WEBHOOK ERRO:", repr(e))
            print("KIWIFY_WEBHOOK QUERY:", dict(request.query_params))
            print("KIWIFY_WEBHOOK HEADER x-kiwify-token:", request.headers.get("x-kiwify-token"))
            print("KIWIFY_WEBHOOK BODY (primeiros 2000):", body.decode("utf-8", "ignore")[:2000])
        else:
            # log mínimo sem vazar dados
            print("KIWIFY_WEBHOOK ERRO (debug off):", repr(e))
        return {"ok": True, "ignored": True, "debug_error": str(e)}
