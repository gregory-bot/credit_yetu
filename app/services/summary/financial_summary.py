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
    "utilities", "merchant", "agent", "transfer", "savings", "remittance",
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
    contra_count = 0
    outlier_credit_total = 0.0
    outlier_debit_total = 0.0

    # --- monthly trends ---
    m_received: dict[str, float] = defaultdict(float)
    m_sent: dict[str, float] = defaultdict(float)
    m_balance: dict[str, float] = {}  # last balance seen in a month

    # --- monthly detail (mirrors the credit-team's reconciliation table:
    # Credits/Loans/Outliers/Net per direction, plus the balance range) ---
    _blank_month = lambda: {  # noqa: E731
        "credits": 0.0, "loan_credits": 0.0, "outlier_credits": 0.0,
        "debits": 0.0, "loan_debits": 0.0, "outlier_debits": 0.0,
        "highest_balance": None, "lowest_balance": None,
    }
    monthly_detail: dict[str, dict] = defaultdict(_blank_month)

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
            contra_count += 1
        elif label == "outlier":
            outlier_credit_total += t.paid_in
            outlier_debit_total += t.withdrawn

        if category == "transfer":
            p2p_received += t.paid_in
            p2p_sent += t.withdrawn

        mk = _month_key(t.transaction_datetime)
        if mk:
            m_received[mk] += t.paid_in
            m_sent[mk] += t.withdrawn
            if t.balance is not None:
                m_balance[mk] = t.balance

            md = monthly_detail[mk]
            md["credits"] += t.paid_in
            md["debits"] += t.withdrawn
            if label == "loan":
                md["loan_credits"] += t.paid_in
                md["loan_debits"] += t.withdrawn
            elif label == "outlier":
                md["outlier_credits"] += t.paid_in
                md["outlier_debits"] += t.withdrawn
            if t.balance is not None:
                md["highest_balance"] = t.balance if md["highest_balance"] is None else max(md["highest_balance"], t.balance)
                md["lowest_balance"] = t.balance if md["lowest_balance"] is None else min(md["lowest_balance"], t.balance)

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

    # Finalize monthly detail: net = gross minus loans minus outliers (so
    # "Net" reflects qualifying, non-loan, non-one-off cashflow per month),
    # rounded and ordered chronologically.
    monthly_rows = []
    for mk in sorted(monthly_detail):
        md = monthly_detail[mk]
        net_credit = md["credits"] - md["loan_credits"] - md["outlier_credits"]
        net_debit = md["debits"] - md["loan_debits"] - md["outlier_debits"]
        monthly_rows.append({
            "month": mk,
            "credits": round(md["credits"], 2),
            "loan_credits": round(md["loan_credits"], 2),
            "outlier_credits": round(md["outlier_credits"], 2),
            "net_credit": round(net_credit, 2),
            "debits": round(md["debits"], 2),
            "loan_debits": round(md["loan_debits"], 2),
            "outlier_debits": round(md["outlier_debits"], 2),
            "net_debit": round(net_debit, 2),
            "highest_balance": round(md["highest_balance"], 2) if md["highest_balance"] is not None else None,
            "lowest_balance": round(md["lowest_balance"], 2) if md["lowest_balance"] is not None else None,
        })
    all_highs = [r["highest_balance"] for r in monthly_rows if r["highest_balance"] is not None]
    all_lows = [r["lowest_balance"] for r in monthly_rows if r["lowest_balance"] is not None]
    n_months = len(monthly_rows) or 1
    monthly_totals = {
        "credits": round(sum(r["credits"] for r in monthly_rows), 2),
        "loan_credits": round(sum(r["loan_credits"] for r in monthly_rows), 2),
        "outlier_credits": round(sum(r["outlier_credits"] for r in monthly_rows), 2),
        "net_credit": round(sum(r["net_credit"] for r in monthly_rows), 2),
        "debits": round(sum(r["debits"] for r in monthly_rows), 2),
        "loan_debits": round(sum(r["loan_debits"] for r in monthly_rows), 2),
        "outlier_debits": round(sum(r["outlier_debits"] for r in monthly_rows), 2),
        "net_debit": round(sum(r["net_debit"] for r in monthly_rows), 2),
        "highest_balance": max(all_highs) if all_highs else None,
        "lowest_balance": min(all_lows) if all_lows else None,
    }
    monthly_averages = {k: (round(v / n_months, 2) if isinstance(v, (int, float)) else v)
                         for k, v in monthly_totals.items() if k not in ("highest_balance", "lowest_balance")}
    monthly_averages["highest_balance"] = monthly_totals["highest_balance"]
    monthly_averages["lowest_balance"] = monthly_totals["lowest_balance"]

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
            "contra_count": contra_count,
            "outlier_credit_total": round(outlier_credit_total, 2),
            "outlier_debit_total": round(outlier_debit_total, 2),
            "betting_to_income": _safe_div(cat_out.get("betting", 0.0), total_received),
            "expenses_to_income": _safe_div(total_sent, total_received),
        },
        "categories": categories,
        "trends": {
            "received": {k: round(v, 2) for k, v in sorted(m_received.items())},
            "sent": {k: round(v, 2) for k, v in sorted(m_sent.items())},
            "balance": {k: round(v, 2) for k, v in sorted(m_balance.items())},
        },
        "monthly_detail": {
            "rows": monthly_rows,
            "totals": monthly_totals,
            "averages": monthly_averages,
        },
        "period": {
            "first_transaction_date": first.isoformat() if first else None,
            "last_transaction_date": last.isoformat() if last else None,
            "statement_months": months_span,
            "active_months": len(m_received),
        },
    }


# A curated, headline breakdown (Betting / Salary / Loans / Remittance /
# Other) — a deliberately small, readable set for a chart or at-a-glance
# panel, as opposed to the full `categories` block above. Both the PDF and
# Excel reports import this so they can never show two different breakdowns
# of the same statement.
_BREAKDOWN_COLORS = {
    "Betting": "#F0932B",
    "Salary": "#2E8B3D",
    "Loans": "#3B2F8F",
    "Remittance": "#6B7280",
    "Other": "#D9D5EC",
}


def breakdown_slices(summary: dict) -> list[dict]:
    """Percentage-of-total-activity breakdown for the headline categories.

    "Total activity" (denominator) is total received + total sent, so the
    slices read as "how much of everything that happened in this statement
    was betting / salary / loan movement / remittance", with whatever isn't
    one of those rolled into "Other" — never silently dropped or rescaled to
    make the named categories alone add up to 100%.
    """
    totals = summary["totals"]
    behaviour = summary["behaviour"]
    lending = summary["lending"]
    categories = summary.get("categories", {})

    denom = totals["total_received"] + totals["total_sent"]
    if denom <= 0:
        return []

    remittance_cat = categories.get("remittance", {})
    named = {
        "Betting": categories.get("betting", {}).get("out", 0.0),
        "Salary": behaviour.get("salary_in", 0.0),
        "Loans": lending.get("loan_received_total", 0.0) + lending.get("loan_repaid_total", 0.0),
        "Remittance": remittance_cat.get("in", 0.0) + remittance_cat.get("out", 0.0),
    }
    other = max(0.0, denom - sum(named.values()))
    named["Other"] = other

    return [
        {"label": label, "value": round(value, 2), "pct": round(value / denom, 4), "color": _BREAKDOWN_COLORS[label]}
        for label, value in named.items()
        if value > 0
    ]
