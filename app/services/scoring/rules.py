"""Individual scoring rules.

Each rule is a pure function of the financial summary (plus a couple of derived
inputs) and returns a ``RuleOutcome`` carrying the points it contributed and the
reason. The engine simply sums them on top of a base score. Because rules are
isolated and explainable, the whole score is auditable line by line — which is
the entire point of this project.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass

from app.services.scoring.reason_codes import REASON_CODES


@dataclass
class RuleOutcome:
    code: str
    points: int
    detail: str

    def as_dict(self) -> dict:
        return {"code": self.code, "points": self.points, "reason": REASON_CODES.get(self.code, ""), "detail": self.detail}


def rule_history(summary: dict) -> RuleOutcome:
    months = summary["period"]["statement_months"] or 0
    if months < 2:
        return RuleOutcome("HIST_SHORT", -40, f"Only {months} month(s) of history.")
    if months >= 6:
        return RuleOutcome("HIST_OK", 30, f"{months} months of history.")
    return RuleOutcome("HIST_OK", 10, f"{months} months of history.")


def rule_income_level(summary: dict, avg_monthly_income: float) -> RuleOutcome:
    if avg_monthly_income < 10_000:
        return RuleOutcome("INCOME_LOW", -30, f"Avg monthly income {avg_monthly_income:,.0f}.")
    if avg_monthly_income >= 80_000:
        return RuleOutcome("INCOME_STRONG", 60, f"Avg monthly income {avg_monthly_income:,.0f}.")
    if avg_monthly_income >= 30_000:
        return RuleOutcome("INCOME_STRONG", 35, f"Avg monthly income {avg_monthly_income:,.0f}.")
    return RuleOutcome("INCOME_STRONG", 15, f"Avg monthly income {avg_monthly_income:,.0f}.")


def income_volatility(summary: dict) -> float | None:
    """Coefficient of variation of monthly received amounts — ``None`` when
    there isn't enough history to judge it (mirrors the threshold
    ``rule_income_stability`` itself uses). Exposed separately so it can be
    surfaced as its own ratio (e.g. in the scorecard) rather than living only
    inside that rule's free-text detail string.
    """
    monthly = list(summary["trends"]["received"].values())
    if len(monthly) < 3:
        return None
    mean = statistics.mean(monthly)
    if mean <= 0:
        return None
    return statistics.pstdev(monthly) / mean


def rule_income_stability(summary: dict) -> RuleOutcome:
    monthly = list(summary["trends"]["received"].values())
    if len(monthly) < 3:
        return RuleOutcome("INCOME_UNSTABLE", 0, "Too few months to judge stability.")
    mean = statistics.mean(monthly)
    if mean <= 0:
        return RuleOutcome("INCOME_UNSTABLE", -20, "No positive monthly income.")
    cv = income_volatility(summary)
    if cv < 0.4:
        return RuleOutcome("INCOME_STABLE", 40, f"Coefficient of variation {cv:.2f}.")
    if cv > 1.0:
        return RuleOutcome("INCOME_UNSTABLE", -30, f"Coefficient of variation {cv:.2f}.")
    return RuleOutcome("INCOME_STABLE", 10, f"Coefficient of variation {cv:.2f}.")


def rule_betting(summary: dict) -> RuleOutcome:
    ratio = summary["behaviour"]["betting_to_income"]
    if ratio > 0.3:
        return RuleOutcome("BETTING_HIGH", -50, f"Betting is {ratio:.0%} of income.")
    if ratio > 0.1:
        return RuleOutcome("BETTING_HIGH", -20, f"Betting is {ratio:.0%} of income.")
    return RuleOutcome("BETTING_HIGH", 0, f"Betting is {ratio:.0%} of income.")


def rule_loan_repayment(summary: dict) -> RuleOutcome:
    received = summary["lending"]["loan_received_total"]
    repaid = summary["lending"]["loan_repaid_total"]
    if received <= 0:
        return RuleOutcome("LOAN_REPAY_GOOD", 10, "No digital-loan disbursements observed.")
    ratio = repaid / received
    if ratio >= 0.9:
        return RuleOutcome("LOAN_REPAY_GOOD", 40, f"Repaid {ratio:.0%} of loans taken.")
    if ratio < 0.5:
        return RuleOutcome("LOAN_REPAY_POOR", -40, f"Repaid only {ratio:.0%} of loans taken.")
    return RuleOutcome("LOAN_REPAY_GOOD", 5, f"Repaid {ratio:.0%} of loans taken.")


def rule_fuliza(summary: dict) -> RuleOutcome:
    fuliza = summary["lending"]["fuliza_out"]
    income = summary["totals"]["total_received"] or 1
    ratio = fuliza / income
    if ratio > 0.2:
        return RuleOutcome("FULIZA_HIGH", -30, f"Fuliza usage {ratio:.0%} of inflow.")
    if ratio > 0.05:
        return RuleOutcome("FULIZA_HIGH", -10, f"Fuliza usage {ratio:.0%} of inflow.")
    return RuleOutcome("FULIZA_HIGH", 0, "Low Fuliza reliance.")


def rule_balance_trend(summary: dict) -> RuleOutcome:
    balances = list(summary["trends"]["balance"].values())
    if len(balances) < 2:
        return RuleOutcome("BALANCE_GROWTH", 0, "Insufficient balance points.")
    if balances[-1] > balances[0] * 1.1:
        return RuleOutcome("BALANCE_GROWTH", 25, "Closing balances trending up.")
    if balances[-1] < balances[0] * 0.9:
        return RuleOutcome("BALANCE_DECLINE", -25, "Closing balances trending down.")
    return RuleOutcome("BALANCE_GROWTH", 5, "Balances broadly stable.")


def rule_activity(summary: dict) -> RuleOutcome:
    count = summary["totals"]["transaction_count"]
    active = summary["period"]["active_months"] or 1
    per_month = count / active
    if per_month < 5:
        return RuleOutcome("ACTIVITY_LOW", -20, f"{per_month:.0f} transactions/month.")
    if per_month >= 20:
        return RuleOutcome("ACTIVITY_HEALTHY", 25, f"{per_month:.0f} transactions/month.")
    return RuleOutcome("ACTIVITY_HEALTHY", 10, f"{per_month:.0f} transactions/month.")


def rule_net_position(summary: dict) -> RuleOutcome:
    net = summary["totals"]["net_position"]
    if net >= 0:
        return RuleOutcome("NET_POSITIVE", 15, f"Net position {net:,.0f}.")
    return RuleOutcome("NET_NEGATIVE", -20, f"Net position {net:,.0f}.")


def rule_outlier_dependency(summary: dict) -> RuleOutcome:
    outliers = summary["behaviour"]["outlier_credit_total"]
    total = summary["totals"]["total_received"] or 1
    ratio = outliers / total
    if ratio > 0.5:
        return RuleOutcome("OUTLIER_DEPENDENT", -25, f"{ratio:.0%} of inflow is one-off outliers.")
    return RuleOutcome("OUTLIER_DEPENDENT", 0, f"{ratio:.0%} of inflow is one-off outliers.")


ALL_RULES = (
    rule_history,
    rule_income_stability,
    rule_betting,
    rule_loan_repayment,
    rule_fuliza,
    rule_balance_trend,
    rule_activity,
    rule_net_position,
    rule_outlier_dependency,
)
