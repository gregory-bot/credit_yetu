"""End-to-end statement processing pipeline.

Runs after a statement is uploaded. Deliberately resilient: extraction/scoring
failures mark the statement ``failed`` with a message rather than crashing the
worker, and report generation failures never block persistence of the score
(the credit team still gets numbers even if a PDF hiccups).

Invoked via FastAPI BackgroundTasks by default; swap ``TASK_BACKEND=celery`` and
point a Celery task at ``process_statement`` for a real queue.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from app.database import SessionLocal
from app.models import Score, Statement, Transaction
from app.services.classification import ClientIdentity, classify
from app.services.extraction import extract
from app.services.fraud import analyze as fraud_analyze
from app.services.reporting import build_financial_workbook, build_scorecard_pdf
from app.services.scoring import score_statement
from app.services.summary import build_summary

logger = logging.getLogger("pipeline")


def _fire_callback(url: str, payload: dict) -> None:
    try:
        httpx.post(url, json=payload, timeout=15)
    except Exception as exc:  # noqa: BLE001 - callbacks must never break processing
        logger.warning("Callback to %s failed: %s", url, exc)


def process_statement(
    statement_id: int,
    product: str = "personal",
    crb_obligation: float = 0.0,
    passcode: str | None = None,
) -> None:
    db = SessionLocal()
    try:
        stmt: Statement | None = db.get(Statement, statement_id)
        if stmt is None:
            logger.error("Statement %s not found", statement_id)
            return

        stmt.status = "extracting"
        stmt.status_message = None
        db.commit()

        # 1. Extract
        result = extract(stmt.file_path, stmt.statement_type, passcode=passcode, bank_code=stmt.bank_code)
        stmt.extraction_method = result.method
        stmt.account_holder = result.account_holder or stmt.account_holder
        stmt.account_number = result.account_number
        stmt.phone_number = result.phone_number
        stmt.statement_period = result.statement_period
        stmt.needs_review = result.needs_review
        stmt.status_message = "; ".join(result.warnings) if result.warnings else None

        if result.count == 0:
            stmt.status = "failed"
            stmt.status_message = (stmt.status_message or "") + " No transactions extracted."
            db.commit()
            if stmt.callback_url:
                _fire_callback(stmt.callback_url, {"status": 422, "reference_id": str(stmt.reference_id),
                                                   "message": "No transactions extracted", "data": None})
            return

        # 2. Classify (needs client identity for contra detection)
        client = ClientIdentity(name=result.account_holder, phone=result.phone_number)
        classify(result.transactions, client)

        # Persist transactions
        for t in result.transactions:
            db.add(Transaction(
                statement_id=stmt.id,
                transaction_ref=t.transaction_ref,
                transaction_datetime=t.transaction_datetime,
                description=t.description[:4000] if t.description else "",
                counterparty=t.counterparty,
                paid_in=t.paid_in,
                withdrawn=t.withdrawn,
                balance=t.balance,
                label=t.raw.get("label", "normal"),
                category=t.raw.get("category"),
                is_flagged=bool(t.raw.get("is_flagged")),
                flag_reason=t.raw.get("flag_reason"),
                raw=t.raw,
            ))
        stmt.status = "scoring"
        db.commit()

        # 3. Financial summary
        summary = build_summary(result.transactions)

        # 4. Fraud
        fraud = fraud_analyze(stmt.file_path, result.transactions)

        # 5. Score
        sr = score_statement(summary, fraud_data=fraud, product=product, crb_obligation=crb_obligation)

        score = Score(
            statement_id=stmt.id,
            credit_score=sr.credit_score,
            grade=sr.grade,
            probability=sr.probability,
            limit_low=sr.limit_low,
            limit_high=sr.limit_high,
            avg_monthly_income=sr.avg_monthly_income,
            dti_pct=sr.dti_pct,
            month_count=sr.month_count,
            reason_codes=sr.reason_codes,
            score_breakdown=sr.breakdown,
            financial_summary=summary,
            fraud_data=fraud,
        )
        db.add(score)
        db.flush()  # ensure score is queryable and relationship is populated

        # Refresh statement.transactions for report generation
        db.refresh(stmt)

        # 6. Reports (non-fatal)
        try:
            score.pdf_path = build_scorecard_pdf(stmt, score)
        except Exception as exc:  # noqa: BLE001
            logger.warning("PDF generation failed for %s: %s", stmt.reference_id, exc)
        try:
            score.excel_path = build_financial_workbook(stmt, score)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Excel generation failed for %s: %s", stmt.reference_id, exc)

        stmt.status = "needs_review" if (sr.needs_review or result.needs_review) else "scored"
        stmt.completed_at = datetime.now(timezone.utc)
        db.commit()

        # 7. Callback
        if stmt.callback_url:
            _fire_callback(stmt.callback_url, {
                "status": 200,
                "reference_id": str(stmt.reference_id),
                "message": "Statement scored successfully",
                "data": {
                    "score_data": {
                        "credit_score": sr.credit_score,
                        "grade": sr.grade,
                        "probability": sr.probability,
                        "limit": [sr.limit_low, sr.limit_high],
                    },
                    "financial_summary": summary,
                    "fraud_data": fraud,
                },
            })

    except Exception as exc:  # noqa: BLE001 - last-resort guard
        logger.exception("Pipeline failed for statement %s", statement_id)
        stmt = db.get(Statement, statement_id)
        if stmt:
            stmt.status = "failed"
            stmt.status_message = f"Processing error: {exc}"
            db.commit()
    finally:
        db.close()
