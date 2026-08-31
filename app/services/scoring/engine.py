"""Scoring engine.

Combines the individual rules into a final score in [300, 900], derives a grade
band, and computes a DTI-based loan limit net of any CRB obligation. Two hard
gates can override the rule sum:

  * ``fraud_data.risk_level == "high"``  → force review, cap the limit at 0.
  * statement history below the minimum   → force review.

DTI percentages are product-specific and centralised here so a Credit-Policy
change is a one-line edit (kept explicit rather than hidden in the reference
system's scattered constants).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.services.scoring.rules import ALL_RULES, RuleOutcome, rule_income_level

BASE_SCORE = 500
MIN_SCORE = 300
MAX_SCORE = 900
MIN_MONTHS = 1.0

# Product-specific DTI ceilings (fraction of net monthly income).
DTI_BY_PRODUCT: dict[str, float] = {
    "personal": 0.45,
    "employed": 0.50,
    "business_registered": 0.25,
    "business_unregistered": 0.15,
    "sme": 0.25,
    "vehicle": 0.40,
}

_GRADE_BANDS = (
    (800, "AA"), (740, "A"), (670, "BB"), (600, "B"),
    (540, "CC"), (480, "C"), (420, "DD"), (0, "D"),
)


@dataclass
class ScoreResult:
    credit_score: int
    grade: str
    probability: float
    avg_monthly_income: float
    dti_pct: float
    month_count: float
    limit_low: float
    limit_high: float
    needs_review: bool
    reason_codes: list[dict] = field(default_factory=list)
    breakdown: dict = field(default_factory=dict)


def _grade(score: int) -> str:
    for threshold, letter in _GRADE_BANDS:
        if score >= threshold:
            return letter
    return "D"


def _avg_monthly_income(summary: dict) -> float:
    """Net qualifying income: recurring credits, excluding loan disbursements,
    contra transfers and one-off outliers (all already separated out)."""
    total_received = summary["totals"]["total_received"]
    loan_in = summary["lending"]["loan_received_total"]
    contra = summary["behaviour"]["contra_total"]
    outliers = summary["behaviour"]["outlier_credit_total"]
    qualifying = max(0.0, total_received - loan_in - contra - outliers)
    months = summary["period"]["statement_months"] or 1
    return qualifying / max(months, 1)


def score_statement(
    summary: dict,
    fraud_data: dict | None = None,
    product: str = "personal",
    crb_obligation: float = 0.0,
) -> ScoreResult:
    outcomes: list[RuleOutcome] = [rule(summary) for rule in ALL_RULES]

    avg_income = _avg_monthly_income(summary)
    outcomes.append(rule_income_level(summary, avg_income))

    # Fraud gate.
    needs_review = False
    if fraud_data and fraud_data.get("risk_level") == "high":
        outcomes.append(RuleOutcome("FRAUD_RISK", -80, f"Fraud risk {fraud_data.get('risk_score')}."))
        needs_review = True
    elif fraud_data and fraud_data.get("flagged"):
        outcomes.append(RuleOutcome("FRAUD_RISK", -30, f"Fraud risk {fraud_data.get('risk_score')}."))

    months = summary["period"]["statement_months"] or 0
    if months < MIN_MONTHS:
        needs_review = True

    raw_total = BASE_SCORE + sum(o.points for o in outcomes)
    score = max(MIN_SCORE, min(MAX_SCORE, raw_total))

    # Probability of good (simple monotonic map from score band).
    probability = round((score - MIN_SCORE) / (MAX_SCORE - MIN_SCORE), 4)

    # DTI limit.
    dti_pct = DTI_BY_PRODUCT.get(product, 0.45)
    dti_amount = avg_income * dti_pct
    qualified = max(0.0, dti_amount - crb_obligation)
    # Present a range (conservative..headline), mirroring the reference APIs.
    limit_low = round(qualified * 0.8, 0)
    limit_high = round(qualified, 0)
    if needs_review:
        limit_low = limit_high = 0.0

    return ScoreResult(
        credit_score=score,
        grade=_grade(score),
        probability=probability,
        avg_monthly_income=round(avg_income, 2),
        dti_pct=dti_pct,
        month_count=months,
        limit_low=limit_low,
        limit_high=limit_high,
        needs_review=needs_review,
        reason_codes=[o.as_dict() for o in outcomes],
        breakdown={
            "base_score": BASE_SCORE,
            "rule_points_total": sum(o.points for o in outcomes),
            "final_score": score,
            "product": product,
            "dti_pct": dti_pct,
            "avg_monthly_income": round(avg_income, 2),
            "crb_obligation": crb_obligation,
            "qualified_amount": round(qualified, 0),
        },
    )
