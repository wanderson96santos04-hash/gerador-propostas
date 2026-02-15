# backend/app/db/models.py
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    String,
    Integer,
    Text,
    DateTime,
    ForeignKey,
    Boolean,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )

    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # 🔐 trava de acesso (produto vendável)
    is_paid: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",  # Postgres
        nullable=False,
        index=True,
    )

    # ✅ Plano de produto (não muda nada do fluxo atual: default "free")
    # - Pro continua sendo controlado por is_paid (compatível com seu sistema atual)
    # - Esse campo permite evoluir para Free/Pro com quota real no backend
    plan: Mapped[str] = mapped_column(
        String(20),
        default="free",
        server_default="free",  # Postgres
        nullable=False,
        index=True,
    )

    # ✅ Contador de uso do ciclo (para Free: 2/mês)
    monthly_quota_used: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",  # Postgres
        nullable=False,
    )

    # ✅ Marca o início do ciclo atual (usado para reset do contador)
    # Regra sugerida: se o mês mudou, resetar.
    quota_reset_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True,
    )

    proposals: Mapped[list["Proposal"]] = relationship(
        "Proposal",
        back_populates="user",
        cascade="all, delete-orphan",
    )


class Proposal(Base):
    __tablename__ = "proposals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="proposals")

    client_name: Mapped[str] = mapped_column(String(200), nullable=False)
    service: Mapped[str] = mapped_column(String(200), nullable=False)

    price: Mapped[str] = mapped_column(String(80), nullable=False)
    deadline: Mapped[str] = mapped_column(String(120), nullable=False)

    tone: Mapped[str] = mapped_column(String(50), nullable=False)
    objective: Mapped[str] = mapped_column(String(50), nullable=False)

    input_summary: Mapped[str] = mapped_column(Text, nullable=False)
    proposal_text: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True,
    )


class WebhookEvent(Base):
    """
    Guarda eventos de webhook já processados para garantir IDEMPOTÊNCIA.
    Se o mesmo event_id chegar de novo, ignoramos com segurança.
    """

    __tablename__ = "webhook_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    event_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )

    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    processed_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
