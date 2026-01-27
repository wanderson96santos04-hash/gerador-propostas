from fastapi import APIRouter, Request, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime

from app.db.session import SessionLocal
from app.db import models

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/kiwify")
async def kiwify_webhook(request: Request):
    """
    Webhook da Kiwify (pagamento confirmado).
    - Idempotente via webhook_events.event_id
    - Identifica usuário por email
    - Libera acesso marcando is_paid=True
    """

    payload = await request.json()

    # 🔐 1) Identificar evento e tipo
    event_id = (
        payload.get("id")
        or payload.get("event_id")
        or payload.get("order_id")
    )
    event_type = payload.get("event") or payload.get("type")

    if not event_id or not event_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payload inválido: event_id ou event_type ausente",
        )

    # ✅ 2) Considerar apenas pagamento confirmado
    # Ajuste aqui se a Kiwify usar outro nome exato
    if event_type not in {"order_paid", "payment_confirmed", "order.approved"}:
        return {"ignored": True, "event_type": event_type}

    # 🔎 3) Extrair email do comprador (padrão mais comum)
    customer = payload.get("customer") or {}
    buyer_email = customer.get("email") or payload.get("email")

    if not buyer_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email do comprador não encontrado no payload",
        )

    db: Session = SessionLocal()

    try:
        # 🔁 4) Idempotência: registrar evento
        event = models.WebhookEvent(
            event_id=str(event_id),
            event_type=str(event_type),
            processed_at=datetime.utcnow(),
        )
        db.add(event)
        db.commit()
    except IntegrityError:
        # Evento já processado
        db.rollback()
        return {"ok": True, "idempotent": True}

    try:
        # 👤 5) Buscar usuário
        user = db.query(models.User).filter(
            models.User.email == buyer_email
        ).one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Usuário não encontrado para email {buyer_email}",
            )

        # 🔓 6) Liberar acesso
        if not user.is_paid:
            user.is_paid = True
            db.add(user)
            db.commit()

        return {
            "ok": True,
            "user_id": user.id,
            "email": user.email,
            "paid": True,
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao processar webhook: {e}",
        )
    finally:
        db.close()
