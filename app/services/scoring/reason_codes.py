"""Human-readable reason codes emitted by scoring rules.

Every rule references one of these so that a declined or low score can always
be explained to the credit team (and, where required, to the borrower).
"""
from __future__ import annotations

REASON_CODES: dict[str, str] = {
    "HIST_SHORT": "Short statement history reduces confidence in the score.",
    "HIST_OK": "Sufficient statement history to support the assessment.",
    "INCOME_LOW": "Low average monthly income.",
    "INCOME_STRONG": "Strong average monthly income.",
    "INCOME_UNSTABLE": "Irregular income — high month-to-month variation.",
    "INCOME_STABLE": "Stable, regular income across months.",
    "BETTING_HIGH": "High proportion of income spent on betting.",
    "LOAN_REPAY_GOOD": "Consistently repays digital loans.",
    "LOAN_REPAY_POOR": "Digital loans disbursed exceed repayments.",
    "FULIZA_HIGH": "Heavy reliance on Fuliza overdraft.",
    "BALANCE_GROWTH": "Average balance is trending upward.",
    "BALANCE_DECLINE": "Average balance is trending downward.",
    "ACTIVITY_LOW": "Low transaction activity.",
    "ACTIVITY_HEALTHY": "Healthy, regular transaction activity.",
    "DISTRESS": "Presence of reversals/penalties/insufficient-funds events.",
    "FRAUD_RISK": "Statement authenticity risk detected — routed to review.",
    "OUTLIER_DEPENDENT": "Income is dominated by one-off large credits.",
    "NET_POSITIVE": "Net cash position is positive over the period.",
    "NET_NEGATIVE": "Net cash position is negative over the period.",
}
