"""Loan outcomes (ground truth) and trained model versions for ML shadow-scoring.

These two tables exist to answer one question honestly: does the transparent
rule-based score actually predict repayment, and can a model trained on the
same underlying signals do it better? Nothing here ever overrides ``Score`` —
see ``app/services/ml/shadow.py`` and the README's "ML shadow-scoring"
section for why the rule engine stays authoritative until real outcomes
justify otherwise.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class LoanOutcome(Base):
    """Ground-truth repayment result for a loan issued off a scored statement.

    One row per statement (a statement is scored once; if a loan was issued
    against that score, its eventual outcome is recorded here). This is the
    only source of labels the training pipeline is allowed to use — there is
    no synthetic or proxy labelling anywhere in this codebase.
    """
    __tablename__ = "loan_outcomes"

    id: Mapped[int] = mapped_column(primary_key=True)
    statement_id: Mapped[int] = mapped_column(
        ForeignKey("statements.id", ondelete="CASCADE"), unique=True, index=True
    )
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)

    loan_amount: Mapped[float] = mapped_column(Float)
    disbursed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # current    -> loan still active/performing, not yet a final label (excluded from training)
    # repaid     -> closed, fully repaid on/ahead of schedule (good = 0)
    # delinquent -> currently in arrears but not written off (treated as bad = 1)
    # defaulted  -> written off / non-performing (bad = 1)
    outcome: Mapped[str] = mapped_column(String(20), index=True)
    days_past_due: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MLModelVersion(Base):
    """A trained shadow-scoring model and the honest metrics it earned on a
    held-out test split.

    ``status`` is one of:
      * ``shadow``               — the current model used for shadow predictions.
      * ``retired``               — superseded by a newer ``shadow`` version.
      * ``trained_insufficient``  — training ran but didn't clear the minimum
        sample / class-balance bar, so it was never activated. Kept in the
        audit trail; never served.
    """
    __tablename__ = "ml_model_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    algorithm: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(24), default="retired", index=True)

    n_samples: Mapped[int] = mapped_column(Integer)
    n_train: Mapped[int] = mapped_column(Integer)
    n_test: Mapped[int] = mapped_column(Integer)
    n_positive: Mapped[int] = mapped_column(Integer)   # bad/default label count, full dataset
    n_negative: Mapped[int] = mapped_column(Integer)

    feature_names: Mapped[list] = mapped_column(JSONB)
    metrics: Mapped[dict] = mapped_column(JSONB)                      # accuracy/precision/recall/f1/roc_auc/ks/...
    baseline_metrics: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # the model that lost the comparison
    artifact_path: Mapped[str] = mapped_column(String(1024))

    trained_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    trained_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
