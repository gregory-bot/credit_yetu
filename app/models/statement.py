"""Uploaded statements and the transactions extracted from them."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Statement(Base):
    __tablename__ = "statements"

    id: Mapped[int] = mapped_column(primary_key=True)
    reference_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id", ondelete="SET NULL"), nullable=True)

    national_id: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    # mpesa | bank | till | paybill | sacco
    statement_type: Mapped[str] = mapped_column(String(20))
    source: Mapped[str | None] = mapped_column(String(20), nullable=True)  # e.g. 'user_statement'
    bank_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    file_name: Mapped[str] = mapped_column(String(512))
    file_path: Mapped[str] = mapped_column(String(1024))

    # Lifecycle: received -> extracting -> extracted -> scoring -> scored -> failed
    status: Mapped[str] = mapped_column(String(20), default="received", index=True)
    extraction_method: Mapped[str | None] = mapped_column(String(30), nullable=True)  # text | ocr | mixed
    status_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    needs_review: Mapped[bool] = mapped_column(default=False)

    # Extracted metadata
    account_holder: Mapped[str | None] = mapped_column(String(255), nullable=True)
    account_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    statement_period: Mapped[str | None] = mapped_column(String(64), nullable=True)
    callback_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="statement", cascade="all, delete-orphan"
    )
    score: Mapped["Score"] = relationship(back_populates="statement", uselist=False, cascade="all, delete-orphan")


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    statement_id: Mapped[int] = mapped_column(ForeignKey("statements.id", ondelete="CASCADE"), index=True)

    transaction_ref: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    transaction_datetime: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    counterparty: Mapped[str | None] = mapped_column(String(255), nullable=True)

    paid_in: Mapped[float] = mapped_column(Float, default=0.0)     # received / credit
    withdrawn: Mapped[float] = mapped_column(Float, default=0.0)   # sent / debit
    balance: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Classification (see services/classification)
    label: Mapped[str] = mapped_column(String(20), default="normal")  # normal|contra|loan|outlier
    category: Mapped[str | None] = mapped_column(String(40), nullable=True)  # betting, airtime, fuliza...
    is_flagged: Mapped[bool] = mapped_column(default=False)
    flag_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    raw: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    statement: Mapped[Statement] = relationship(back_populates="transactions")


class Score(Base):
    __tablename__ = "scores"

    id: Mapped[int] = mapped_column(primary_key=True)
    statement_id: Mapped[int] = mapped_column(ForeignKey("statements.id", ondelete="CASCADE"), unique=True, index=True)

    credit_score: Mapped[int] = mapped_column(Integer, default=0)
    grade: Mapped[str] = mapped_column(String(4), default="NA")
    probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    limit_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    limit_high: Mapped[float | None] = mapped_column(Float, nullable=True)

    avg_monthly_income: Mapped[float | None] = mapped_column(Float, nullable=True)
    dti_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    month_count: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Full transparent breakdown: every rule, its points and its reason.
    reason_codes: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    score_breakdown: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    financial_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    fraud_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    pdf_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    excel_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    statement: Mapped[Statement] = relationship(back_populates="score")
