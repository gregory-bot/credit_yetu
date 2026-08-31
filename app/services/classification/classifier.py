"""Classify extracted transactions.

Each transaction receives:
  * ``label``    — normal | contra | loan | outlier
  * ``category`` — a spending/income bucket (or None)
  * ``is_flagged`` + ``flag_reason`` for anything a human should glance at

Rules (all transparent and individually auditable):

* contra  — a transfer between the client's *own* accounts. Detected only when
  the counterparty name/phone matches the client's own name/phone. Conservative
  by design: a false contra would wrongly cancel real income.
* loan    — word-boundary match against the curated loan keyword list.
* outlier — a one-off large credit, flagged with an IQR threshold computed over
  the client's *own* recurring credit amounts (not a raw ceiling), so a genuine
  salary is never flagged merely for being large.
* category — first matching bucket from the curated category keywords.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.classification.keywords import CATEGORY_KEYWORDS, LOAN_KEYWORDS
from app.services.extraction.models import ExtractedTransaction


@dataclass
class ClientIdentity:
    name: str | None = None
    phone: str | None = None


def _word_boundary_hit(text: str, keywords: tuple[str, ...]) -> str | None:
    low = text.lower()
    for kw in keywords:
        # Escape and match on word boundaries; keywords with spaces still work.
        if re.search(rf"(?<![a-z0-9]){re.escape(kw)}(?![a-z0-9])", low):
            return kw
    return None


def _categorize(description: str) -> str | None:
    for category, kws in CATEGORY_KEYWORDS.items():
        if _word_boundary_hit(description, kws):
            return category
    return None


def _name_tokens(name: str | None) -> set[str]:
    if not name:
        return set()
    return {t for t in re.split(r"\s+", name.lower()) if len(t) > 2}


def _iqr_upper_fence(values: list[float]) -> float | None:
    """Return Q3 + 1.5*IQR for a list of positive values, or None if too small."""
    vals = sorted(v for v in values if v > 0)
    n = len(vals)
    if n < 8:  # not enough recurring history to define an outlier fence
        return None

    def q(p: float) -> float:
        idx = p * (n - 1)
        lo = int(idx)
        frac = idx - lo
        if lo + 1 < n:
            return vals[lo] * (1 - frac) + vals[lo + 1] * frac
        return vals[lo]

    q1, q3 = q(0.25), q(0.75)
    return q3 + 1.5 * (q3 - q1)


def classify(transactions: list[ExtractedTransaction], client: ClientIdentity) -> None:
    """Annotate each transaction in place with label/category/flag.

    The transactions are plain dicts on the ORM side, so we return structured
    tags via the ``raw`` dict and dedicated attributes the caller copies over.
    """
    client_tokens = _name_tokens(client.name)
    client_phone_tail = (client.phone or "")[-6:]

    # Build the IQR fence over recurring credit amounts.
    credit_values = [t.paid_in for t in transactions if t.paid_in > 0]
    fence = _iqr_upper_fence(credit_values)

    for t in transactions:
        desc = t.description or ""
        tags = t.raw.setdefault("tags", {})

        label = "normal"
        flag_reason = None

        # --- contra ---
        cp_tokens = _name_tokens(t.counterparty or desc)
        name_overlap = bool(client_tokens & cp_tokens) and len(client_tokens) > 0
        phone_overlap = bool(client_phone_tail) and client_phone_tail in desc
        if name_overlap or phone_overlap:
            label = "contra"
            flag_reason = "Transfer between client's own accounts (self-transfer)."

        # --- loan ---
        loan_hit = _word_boundary_hit(desc, LOAN_KEYWORDS)
        if loan_hit and label != "contra":
            label = "loan"
            tags["loan_keyword"] = loan_hit

        # --- outlier (only for credits, and only if not already contra/loan) ---
        if label == "normal" and fence is not None and t.paid_in > fence:
            label = "outlier"
            flag_reason = (
                f"One-off large credit {t.paid_in:,.0f} exceeds IQR fence "
                f"{fence:,.0f} over recurring credits."
            )

        category = _categorize(desc)

        tags["label"] = label
        tags["category"] = category
        t.raw["label"] = label
        t.raw["category"] = category
        t.raw["is_flagged"] = label in ("contra", "outlier")
        t.raw["flag_reason"] = flag_reason
