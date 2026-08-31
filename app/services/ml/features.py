"""Deterministic feature engineering for ML shadow-scoring.

Features are derived **only** from the same ``financial_summary`` /
``fraud_data`` the rule engine already computed for every statement — no new
data collection, no external calls, nothing the borrower hasn't already
implicitly consented to via the statement upload itself.

Deliberately excludes the rule engine's own ``credit_score`` and ``grade``:
the point of shadow-scoring is to see whether the underlying signals predict
real repayment, not to let the model learn to parrot the rules it exists to
check.

``FEATURE_NAMES`` is authoritative and ordered — every trained artifact
stores it alongside the model (see ``train.py``), so a later schema change
(a feature added or removed) is detected at load time instead of silently
misaligning columns.
"""
from __future__ import annotations

FEATURE_NAMES: list[str] = [
    "avg_monthly_income",
    "total_received",
    "total_sent",
    "net_position",
    "transaction_count",
    "avg_credit",
    "avg_debit",
    "expenses_to_income",
    "betting_to_income",
    "fuliza_dependency",
    "loan_dependency",
    "salary_dependency",
    "p2p_received_ratio",
    "p2p_sent_ratio",
    "contra_ratio",
    "outlier_ratio",
    "statement_months",
    "active_months_ratio",
    "fraud_risk_score",
]


def _safe_div(a: float, b: float) -> float:
    return round(a / b, 6) if b else 0.0


def extract_features(summary: dict, fraud_data: dict | None, avg_monthly_income: float) -> dict[str, float]:
    """Build the fixed feature vector for one scored statement.

    ``summary`` is the dict produced by ``app.services.summary.build_summary``;
    ``fraud_data`` is the dict from ``app.services.fraud.analyze`` (or ``None``
    for the synchronous pre-parsed-transactions endpoint, which never runs
    fraud forensics against a source PDF).
    """
    totals = summary["totals"]
    lending = summary["lending"]
    behaviour = summary["behaviour"]
    period = summary["period"]

    total_received = totals["total_received"]
    statement_months = period["statement_months"] or 0.0

    return {
        "avg_monthly_income": avg_monthly_income,
        "total_received": total_received,
        "total_sent": totals["total_sent"],
        "net_position": totals["net_position"],
        "transaction_count": float(totals["transaction_count"]),
        "avg_credit": totals["avg_credit"],
        "avg_debit": totals["avg_debit"],
        "expenses_to_income": behaviour["expenses_to_income"],
        "betting_to_income": behaviour["betting_to_income"],
        "fuliza_dependency": _safe_div(lending["fuliza_out"], total_received),
        "loan_dependency": _safe_div(lending["loan_received_total"], total_received),
        "salary_dependency": _safe_div(behaviour["salary_in"], total_received),
        "p2p_received_ratio": _safe_div(behaviour["p2p_received"], total_received),
        "p2p_sent_ratio": _safe_div(behaviour["p2p_sent"], total_received),
        "contra_ratio": _safe_div(behaviour["contra_total"], total_received),
        "outlier_ratio": _safe_div(behaviour["outlier_credit_total"], total_received),
        "statement_months": statement_months,
        "active_months_ratio": _safe_div(period["active_months"], statement_months),
        "fraud_risk_score": float((fraud_data or {}).get("risk_score", 0.0)),
    }


def to_vector(features: dict[str, float]) -> list[float]:
    """Order a feature dict into the fixed vector the model expects."""
    return [float(features.get(name, 0.0)) for name in FEATURE_NAMES]
