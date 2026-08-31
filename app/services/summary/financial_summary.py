"""Build the comprehensive financial summary.

This is the module that closes the specific gap the credit team keeps hitting:
the score alone isn't enough — they need the full transaction-level breakdown
to reconcile against the source statement. Everything here is derived directly
from the (already classified) transactions, so the summary can never drift from
what was actually scored.

Output includes:
  * headline totals (received / sent / net / balances)
  * per-category totals over the full statement and a trailing 6-month window
  * monthly trend series for received / sent / closing balance
  * activity metrics (counts, averages, active days, first/last dates)
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from app.services.extraction.models import ExtractedTransaction

_CATEGORY_KEYS = (
    "betting", "airtime", "fuliza", "mshwari", "kcb_mpesa", "salary",
    "utilities", "merchant", "agent", "transfer", "savings",
)


def _month_key(dt: datetime | None) -> str | None:
    return dt.strftime("%Y-%m") if dt else None


def _safe_div(a: float, b: float) -> float:
    return round(a / b, 4) if b else 0.0


def build_summary(transactions: list[ExtractedTransaction]) -> dict:
    dated = [t for t in transactions if t.transaction_datetime]
    dates = [t.transaction_datetime for t in dated]
    first = min(dates) if dates else None
    last = max(dates) if dates else None

    months_span = 0.0
    if first and last:
        months_span = round(((last - first).days + 1) / 30.44, 2)

    # 6-month window relative to the last transaction.
    window_start = (last - timedelta(days=183)) if last else None

    total_received = sum(t.paid_in for t in transactions)
    total_sent = sum(t.withdrawn for t in transactions)

    # --- category aggregation ---
    cat_in: dict[str, float] = defaultdict(float)
    cat_out: dict[str, float] = defaultdict(float)
    cat_count: dict[str, int] = defaultdict(int)
    cat_in_6m: dict[str, float] = defaultdict(float)
    cat_out_6m: dict[str, float] = defaultdict(float)

    loan_received = loan_repaid = 0.0
    p2p_received = p2p_sent = 0.0
    contra_total = 0.0
    outlier_total = 0.0

    # --- monthly trends ---
    m_received: dict[str, float] = defaultdict(float)
    m_sent: dict[str, float] = defaultdict(float)
    m_balance: dict[str, float] = {}  # last balance seen in a month

    for t in transactions:
        label = t.raw.get("label", "normal")
        category = t.raw.get("category")
        in_window = bool(window_start and t.transaction_datetime and t.transaction_datetime >= window_start)

        if category:
            cat_in[category] += t.paid_in
            cat_out[category] += t.withdrawn
            cat_count[category] += 1
            if in_window:
                cat_in_6m[category] += t.paid_in
                cat_out_6m[category] += t.withdrawn

        if label == "loan":
            loan_received += t.paid_in
            loan_repaid += t.withdrawn
        elif label == "contra":
            contra_total += t.paid_in + t.withdrawn
        elif label == "outlier":
            outlier_total += t.paid_in

        if category == "transfer":
            p2p_received += t.paid_in
            p2p_sent += t.withdrawn

        mk = _month_key(t.transaction_datetime)
        if mk:
            m_received[mk] += t.paid_in
            m_sent[mk] += t.withdrawn
            if t.balance is not None:
                m_balance[mk] = t.balance

    categories = {
        key: {
            "in": round(cat_in[key], 2),
            "out": round(cat_out[key], 2),
            "count": cat_count[key],
            "in_6m": round(cat_in_6m[key], 2),
            "out_6m": round(cat_out_6m[key], 2),
        }
        for key in _CATEGORY_KEYS
    }

    net = total_received - total_sent
    credits = [t.paid_in for t in transactions if t.paid_in > 0]
    debits = [t.withdrawn for t in transactions if t.withdrawn > 0]

    return {
        "totals": {
            "total_received": round(total_received, 2),
            "total_sent": round(total_sent, 2),
            "net_position": round(net, 2),
            "transaction_count": len(transactions),
            "credit_count": len(credits),
            "debit_count": len(debits),
            "avg_credit": round(sum(credits) / len(credits), 2) if credits else 0.0,
            "avg_debit": round(sum(debits) / len(debits), 2) if debits else 0.0,
            "max_credit": round(max(credits), 2) if credits else 0.0,
            "max_debit": round(max(debits), 2) if debits else 0.0,
        },
        "lending": {
            "loan_received_total": round(loan_received, 2),
            "loan_repaid_total": round(loan_repaid, 2),
            "fuliza_out": round(cat_out.get("fuliza", 0.0), 2),
            "mshwari_activity": round(cat_in.get("mshwari", 0.0) + cat_out.get("mshwari", 0.0), 2),
            "kcb_mpesa_activity": round(cat_in.get("kcb_mpesa", 0.0) + cat_out.get("kcb_mpesa", 0.0), 2),
        },
        "behaviour": {
            "betting_out": round(cat_out.get("betting", 0.0), 2),
            "airtime_out": round(cat_out.get("airtime", 0.0), 2),
            "salary_in": round(cat_in.get("salary", 0.0), 2),
            "utilities_out": round(cat_out.get("utilities", 0.0), 2),
            "agent_withdrawal_out": round(cat_out.get("agent", 0.0), 2),
            "p2p_received": round(p2p_received, 2),
            "p2p_sent": round(p2p_sent, 2),
            "contra_total": round(contra_total, 2),
            "outlier_credit_total": round(outlier_total, 2),
            "betting_to_income": _safe_div(cat_out.get("betting", 0.0), total_received),
            "expenses_to_income": _safe_div(total_sent, total_received),
        },
        "categories": categories,
        "trends": {
            "received": {k: round(v, 2) for k, v in sorted(m_received.items())},
            "sent": {k: round(v, 2) for k, v in sorted(m_sent.items())},
            "balance": {k: round(v, 2) for k, v in sorted(m_balance.items())},
        },
        "period": {
            "first_transaction_date": first.isoformat() if first else None,
            "last_transaction_date": last.isoformat() if last else None,
            "statement_months": months_span,
            "active_months": len(m_received),
        },
    }
