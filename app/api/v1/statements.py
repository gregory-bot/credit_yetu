"""Statement upload, processing status, scoring results and report downloads."""
from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_org
from app.config import settings
from app.core.errors import AppError, NotFound
from app.core.responses import accepted, ok
from app.database import get_db
from app.models import Customer, Organization, Statement
from app.services.ml.shadow import shadow_predict
from app.services.pipeline import process_statement

router = APIRouter(prefix="/statements", tags=["statements"])

_ALLOWED_TYPES = {"mpesa", "bank", "till", "paybill", "sacco"}
_ALLOWED_EXT = {".pdf", ".png", ".jpg", ".jpeg"}


@router.post("/upload")
async def upload_statement(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    statement_type: str = Form(...),
    national_id: str | None = Form(None),
    passcode: str | None = Form(None),
    product: str = Form("personal"),
    crb_obligation: float = Form(0.0),
    bank_code: str | None = Form(None),
    callback_url: str | None = Form(None),
    org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """Upload an M-Pesa / bank / SACCO statement for extraction and scoring.

    Processing is asynchronous: this returns ``202`` with a ``reference_id``;
    poll ``GET /statements/{reference_id}`` for status, then fetch the score.
    """
    stype = statement_type.lower()
    if stype not in _ALLOWED_TYPES:
        raise AppError(f"Unsupported statement_type '{statement_type}'. Allowed: {sorted(_ALLOWED_TYPES)}.")

    ext = Path(file.filename or "").suffix.lower()
    if ext not in _ALLOWED_EXT:
        raise AppError(f"Unsupported file type '{ext}'. Allowed: {sorted(_ALLOWED_EXT)}.")

    ref = uuid.uuid4()
    dest = settings.storage_path / "uploads" / f"{ref}{ext}"

    size = 0
    with dest.open("wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > settings.max_upload_bytes:
                out.close()
                dest.unlink(missing_ok=True)
                raise AppError(f"File exceeds maximum size of {settings.max_upload_mb} MB.", 413)
            out.write(chunk)

    # Link to an existing customer profile by national_id, if one exists for
    # this org — lets a customer's detail page show their statement/score
    # history without a separate lookup endpoint.
    customer = None
    if national_id:
        customer = db.scalar(
            select(Customer).where(Customer.organization_id == org.id, Customer.national_id == national_id)
        )

    stmt = Statement(
        reference_id=ref,
        organization_id=org.id,
        customer_id=customer.id if customer else None,
        national_id=national_id,
        statement_type=stype,
        source=stype,
        bank_code=bank_code,
        file_name=file.filename or f"{ref}{ext}",
        file_path=str(dest),
        status="received",
        callback_url=callback_url,
    )
    db.add(stmt)
    db.commit()

    background.add_task(process_statement, stmt.id, product, crb_obligation, passcode)

    return accepted(
        {"reference_id": str(ref), "status": "received", "poll_url": f"{settings.api_v1_prefix}/statements/{ref}"},
        message="Statement received and queued for processing",
    )


@router.get("")
def list_statements(
    national_id: str | None = None,
    org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """List this org's statements, newest first (capped at 200).

    Pass ``?national_id=`` to scope to one customer — this is how a customer
    detail page gets its statement/score history, without a separate
    per-customer endpoint.
    """
    query = select(Statement).where(Statement.organization_id == org.id)
    if national_id:
        query = query.where(Statement.national_id == national_id)
    rows = db.scalars(query.order_by(Statement.created_at.desc()).limit(200)).all()
    return ok([
        {
            "reference_id": str(s.reference_id),
            "statement_type": s.statement_type,
            "status": s.status,
            "national_id": s.national_id,
            "account_holder": s.account_holder,
            "needs_review": s.needs_review,
            "created_at": s.created_at.isoformat(),
            "completed_at": s.completed_at.isoformat() if s.completed_at else None,
            "score": {
                "credit_score": s.score.credit_score,
                "grade": s.score.grade,
                "avg_monthly_income": s.score.avg_monthly_income,
                "limit_low": s.score.limit_low,
                "limit_high": s.score.limit_high,
            } if s.score else None,
        }
        for s in rows
    ])


def _statement_or_404(reference_id: str, org: Organization, db: Session) -> Statement:
    try:
        ref = uuid.UUID(reference_id)
    except ValueError as exc:
        raise NotFound("Invalid reference_id.") from exc
    stmt = db.scalar(select(Statement).where(Statement.reference_id == ref, Statement.organization_id == org.id))
    if not stmt:
        raise NotFound("Statement not found.")
    return stmt


@router.get("/{reference_id}")
def statement_status(reference_id: str, org: Organization = Depends(get_current_org), db: Session = Depends(get_db)):
    stmt = _statement_or_404(reference_id, org, db)
    return ok({
        "reference_id": str(stmt.reference_id),
        "status": stmt.status,
        "statement_type": stmt.statement_type,
        "extraction_method": stmt.extraction_method,
        "needs_review": stmt.needs_review,
        "status_message": stmt.status_message,
        "account_holder": stmt.account_holder,
        "transaction_count": len(stmt.transactions),
        "scored": stmt.score is not None,
    })


@router.get("/{reference_id}/score")
def statement_score(reference_id: str, org: Organization = Depends(get_current_org), db: Session = Depends(get_db)):
    stmt = _statement_or_404(reference_id, org, db)
    if stmt.score is None:
        return ok({"reference_id": str(stmt.reference_id), "status": stmt.status}, message="Scoring not complete")
    s = stmt.score
    ml_shadow = shadow_predict(db, s.financial_summary, s.fraud_data, s.avg_monthly_income or 0.0)
    return ok({
        "reference_id": str(stmt.reference_id),
        "score_data": {
            "credit_score": s.credit_score,
            "grade": s.grade,
            "probability": s.probability,
            "affordability": {"low": s.limit_low, "high": s.limit_high},
            "avg_monthly_income": s.avg_monthly_income,
            "dti_pct": s.dti_pct,
            "month_count": s.month_count,
        },
        "reason_codes": s.reason_codes,
        "score_breakdown": s.score_breakdown,
        "fraud_data": s.fraud_data,
        "needs_review": stmt.needs_review,
        # Non-authoritative — see app/services/ml/shadow.py. credit_score/grade above are final.
        "ml_shadow": ml_shadow,
    })


@router.get("/{reference_id}/summary")
def statement_summary(reference_id: str, org: Organization = Depends(get_current_org), db: Session = Depends(get_db)):
    stmt = _statement_or_404(reference_id, org, db)
    if stmt.score is None:
        raise NotFound("Financial summary not available yet.")
    return ok({"reference_id": str(stmt.reference_id), "financial_summary": stmt.score.financial_summary})


@router.get("/{reference_id}/transactions")
def statement_transactions(reference_id: str, org: Organization = Depends(get_current_org), db: Session = Depends(get_db)):
    stmt = _statement_or_404(reference_id, org, db)
    return ok([
        {
            "date": t.transaction_datetime.isoformat() if t.transaction_datetime else None,
            "reference": t.transaction_ref,
            "description": t.description,
            "paid_in": t.paid_in,
            "withdrawn": t.withdrawn,
            "balance": t.balance,
            "label": t.label,
            "category": t.category,
            "is_flagged": t.is_flagged,
            "flag_reason": t.flag_reason,
        }
        for t in stmt.transactions
    ])


@router.get("/{reference_id}/report/pdf")
def download_pdf(reference_id: str, org: Organization = Depends(get_current_org), db: Session = Depends(get_db)):
    stmt = _statement_or_404(reference_id, org, db)
    if not stmt.score or not stmt.score.pdf_path or not Path(stmt.score.pdf_path).exists():
        raise NotFound("PDF report not available.")
    return FileResponse(stmt.score.pdf_path, media_type="application/pdf",
                        filename=f"scorecard_{stmt.reference_id}.pdf")


@router.get("/{reference_id}/report/excel")
def download_excel(reference_id: str, org: Organization = Depends(get_current_org), db: Session = Depends(get_db)):
    stmt = _statement_or_404(reference_id, org, db)
    if not stmt.score or not stmt.score.excel_path or not Path(stmt.score.excel_path).exists():
        raise NotFound("Excel report not available.")
    return FileResponse(
        stmt.score.excel_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"financial_summary_{stmt.reference_id}.xlsx",
    )
