"""Organizations (API consumers) and their API keys."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    # 'personal' or 'business' account (as chosen on signup)
    account_type: Mapped[str] = mapped_column(String(20), default="business")
    # Prepaid wallet balance — CRB/KYC calls debit this (mirrors reference APIs).
    wallet_balance: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Password auth for the human dashboard (app/api/v1/auth.py). Nullable
    # because it was added after API keys existed as the only credential —
    # an org created before this column existed simply can't log in with a
    # password until one is set. Bearer API keys (below) remain the
    # credential every actual API request is authorized with; a password
    # only ever gets you a fresh API key via POST /auth/login.
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_reset_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    password_reset_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    api_keys: Mapped[list["ApiKey"]] = relationship(back_populates="organization", cascade="all, delete-orphan")


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    # Only the hash is stored; the raw key is shown once at creation.
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    public_prefix: Mapped[str] = mapped_column(String(32))
    label: Mapped[str] = mapped_column(String(120), default="default")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    organization: Mapped[Organization] = relationship(back_populates="api_keys")
