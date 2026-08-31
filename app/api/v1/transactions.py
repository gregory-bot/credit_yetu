"""Score a set of already-extracted transactions synchronously.

For callers who have parsed transactions themselves (or pull them from another
system) and just want the scoring + summary, without uploading a PDF.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_org
from app.core.errors import AppError
from app.core.responses import ok
from app.database import get_db
from app.models import Organization
from app.schemas import TransactionsScoreRequest
from app.services.classification import ClientIdentity, classify
from app.services.extraction.models import ExtractedTransaction
from app.services.extraction.ordering import ensure_chronological
from app.services.extraction.patterns import parse_datetime
from app.services.ml.shadow import shadow_predict
from app.services.scoring import score_statement
from app.services.summary import build_summary

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.post("/score")
def score_transactions(
    payload: TransactionsScoreRequest,
    org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    if not payload.transactions:
        raise AppError("At least one transaction is required.")

    txns = [
        ExtractedTransaction(
            description=t.description,
            transaction_ref=t.reference,
            transaction_datetime=parse_datetime(t.date),
            paid_in=t.paid_in,
            withdrawn=t.withdrawn,
            balance=t.balance,
            raw={},
        )
        for t in payload.transactions
    ]

    # Callers may submit rows in either order; the monthly balance trend in
    # build_summary assumes oldest-first (see services/extraction/ordering.py).
    txns = ensure_chronological(txns)
    classify(txns, ClientIdentity(name=payload.account_holder, phone=payload.phone))
    summary = build_summary(txns)
    result = score_statement(summary, fraud_data=None, product=payload.product, crb_obligation=payload.crb_obligation)
    ml_shadow = shadow_predict(db, summary, None, result.avg_monthly_income)

    return ok({
        "score_data": {
            "credit_score": result.credit_score,
            "grade": result.grade,
            "probability": result.probability,
            "loan_limit": {"low": result.limit_low, "high": result.limit_high},
            "avg_monthly_income": result.avg_monthly_income,
            "dti_pct": result.dti_pct,
        },
        "reason_codes": result.reason_codes,
        "score_breakdown": result.breakdown,
        "financial_summary": summary,
        "needs_review": result.needs_review,
        # Non-authoritative — see app/services/ml/shadow.py. credit_score/grade above are final.
        "ml_shadow": ml_shadow,
    }, message="Transactions scored")
