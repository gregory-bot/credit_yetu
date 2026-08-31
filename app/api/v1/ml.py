"""Loan-outcome labeling and the ML shadow-model lifecycle.

This is the only place ground-truth labels enter the system, and the only
place a shadow model gets (re)trained. Nothing here changes ``credit_score``,
``grade`` or the loan limit computed by ``app.services.scoring`` — see
``app/services/ml/shadow.py``.
"""
from __future__ import annotations

import uuid

from dateutil import parser as dtparser
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_org
from app.config import settings
from app.core.errors import AppError, NotFound
from app.core.responses import ok
from app.database import get_db
from app.models import LoanOutcome, MLModelVersion, Organization, Statement
from app.schemas import LoanOutcomeCreate
from app.services.ml.train import train_and_evaluate

router = APIRouter(prefix="/ml", tags=["ml"])

_FINAL_OUTCOMES = ("repaid", "delinquent", "defaulted")


def _scored_statement_or_404(reference_id: str, org: Organization, db: Session) -> Statement:
    try:
        ref = uuid.UUID(reference_id)
    except ValueError as exc:
        raise NotFound("Invalid reference_id.") from exc
    stmt = db.scalar(select(Statement).where(Statement.reference_id == ref, Statement.organization_id == org.id))
    if not stmt:
        raise NotFound("Statement not found.")
    if stmt.score is None:
        raise AppError("Statement has not been scored yet; outcomes can only be recorded against scored statements.")
    return stmt


@router.post("/outcomes/{reference_id}")
def record_outcome(
    reference_id: str,
    payload: LoanOutcomeCreate,
    org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """Record (or update) the real repayment outcome of a loan issued off a
    scored statement. This is the ground truth the shadow model trains on —
    there is no other source of labels in this system."""
    stmt = _scored_statement_or_404(reference_id, org, db)
    disbursed = dtparser.parse(payload.disbursed_at) if payload.disbursed_at else None

    existing = db.scalar(select(LoanOutcome).where(LoanOutcome.statement_id == stmt.id))
    if existing:
        existing.loan_amount = payload.loan_amount
        existing.disbursed_at = disbursed
        existing.outcome = payload.outcome
        existing.days_past_due = payload.days_past_due
        existing.notes = payload.notes
        existing.recorded_by = payload.recorded_by
    else:
        db.add(LoanOutcome(
            statement_id=stmt.id, organization_id=org.id, loan_amount=payload.loan_amount,
            disbursed_at=disbursed, outcome=payload.outcome, days_past_due=payload.days_past_due,
            notes=payload.notes, recorded_by=payload.recorded_by,
        ))
    db.commit()
    return ok({"reference_id": reference_id, "outcome": payload.outcome}, message="Loan outcome recorded")


@router.get("/status")
def ml_status(db: Session = Depends(get_db)):
    """Labeling progress across all organizations and the currently active
    shadow model, if any."""
    rows = db.execute(select(LoanOutcome.outcome, func.count()).group_by(LoanOutcome.outcome)).all()
    breakdown = {outcome: count for outcome, count in rows}
    n_final = sum(breakdown.get(o, 0) for o in _FINAL_OUTCOMES)

    active = db.scalar(select(MLModelVersion).where(MLModelVersion.status == "shadow"))
    return ok({
        "outcome_breakdown": breakdown,
        "labeled_final_outcomes": n_final,
        "min_required_to_train": settings.ml_min_samples,
        "ready_to_train": n_final >= settings.ml_min_samples,
        "active_shadow_model": {
            "version": active.version,
            "algorithm": active.algorithm,
            "trained_at": active.trained_at.isoformat(),
            "n_samples": active.n_samples,
            "metrics": active.metrics,
        } if active else None,
    })


@router.post("/train")
def train_model(org: Organization = Depends(get_current_org), db: Session = Depends(get_db)):
    """(Re)train the shadow model on every recorded loan outcome so far.

    Returns real train/test metrics, or explains exactly what's missing if
    there isn't yet enough labeled data — never a fabricated number.
    """
    report = train_and_evaluate(db, trained_by=org.name)
    if report.status == "trained_insufficient":
        return ok({
            "status": report.status,
            "reason": report.reason,
            "n_samples": report.n_samples,
            "n_positive": report.n_positive,
            "n_negative": report.n_negative,
        }, message="Not enough labeled outcomes to activate a shadow model yet")
    return ok({
        "status": report.status,
        "version": report.version,
        "n_samples": report.n_samples,
        "n_train": report.n_train,
        "n_test": report.n_test,
        "n_positive": report.n_positive,
        "n_negative": report.n_negative,
        "metrics": report.metrics,
        "baseline_metrics": report.baseline_metrics,
    }, message="Shadow model trained and activated")


@router.get("/models")
def list_models(db: Session = Depends(get_db)):
    """Full audit trail of every training run, promoted or not."""
    rows = db.scalars(select(MLModelVersion).order_by(MLModelVersion.trained_at.desc())).all()
    return ok([
        {
            "version": r.version,
            "algorithm": r.algorithm,
            "status": r.status,
            "n_samples": r.n_samples,
            "n_train": r.n_train,
            "n_test": r.n_test,
            "n_positive": r.n_positive,
            "n_negative": r.n_negative,
            "metrics": r.metrics,
            "baseline_metrics": r.baseline_metrics,
            "trained_at": r.trained_at.isoformat(),
            "trained_by": r.trained_by,
        }
        for r in rows
    ])
