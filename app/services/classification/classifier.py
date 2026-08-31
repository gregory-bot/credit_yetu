"""Classify extracted transactions.

Each transaction receives:
  * ``label``    — normal | contra | loan | outlier
  * ``category`` — a spending/income bucket (or None)
  * ``is_flagged`` + ``flag_reason`` for anything a human should glance at

Rules (all transparent and individually auditable):

* contra   — a transfer between the client's *own* accounts. Detected only when
  the counterparty name/phone matches the client's own name/phone. Conservative
  by design: a false contra would wrongly cancel real income.
* loan     — word-boundary match against the curated loan keyword list.
* outlier  — a one-off large credit *or* debit, flagged with an IQR threshold
  computed independently over the client's own recurring credit/debit amounts
  (not a raw ceiling), so a genuine salary or a normal-sized bill is never
  flagged merely for being large.
* category — first matching bucket from the curated category keywords.

Every transaction that ends up ``is_flagged`` always carries a human-readable
``flag_reason`` — contra/outlier/distress reasons stack (joined, not
overwritten) when more than one applies to the same row, so nothing is ever
flagged without an auditable explanation of why.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.classification.keywords import CATEGORY_KEYWORDS, DISTRESS_KEYWORDS, LOAN_KEYWORDS
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

    # Independent IQR fences over recurring credit / debit amounts.
    #
    # Debits mix two very different populations on a real statement: tiny
    # recurring fee/duty lines (bank/M-Pesa charges, excise duty — almost
    # always under KES 100) and substantive payments. Feeding both into one
    # IQR computation lets the fee cluster drag the fence down so far that
    # ordinary transfers get flagged as "one-off outliers" (confirmed on a
    # real statement: median debit KES 47, fence collapsed to ~8,600,
    # flagging 22 of 79 substantive transfers). Excluding the fee-sized tail
    # before computing the fence keeps it meaningful for genuinely
    # exceptional debits only.
    _FEE_FLOOR = 100.0
    credit_fence = _iqr_upper_fence([t.paid_in for t in transactions if t.paid_in > 0])
    debit_fence = _iqr_upper_fence([t.withdrawn for t in transactions if t.withdrawn >= _FEE_FLOOR])

    for t in transactions:
        desc = t.description or ""
        tags = t.raw.setdefault("tags", {})

        label = "normal"
        reasons: list[str] = []

        # --- contra ---
        cp_tokens = _name_tokens(t.counterparty or desc)
        name_overlap = bool(client_tokens & cp_tokens) and len(client_tokens) > 0
        phone_overlap = bool(client_phone_tail) and client_phone_tail in desc
        if name_overlap or phone_overlap:
            label = "contra"
            reasons.append("Transfer between client's own accounts (self-transfer).")

        # --- loan ---
        loan_hit = _word_boundary_hit(desc, LOAN_KEYWORDS)
        if loan_hit and label != "contra":
            label = "loan"
            tags["loan_keyword"] = loan_hit

        # --- outlier (credit or debit side; only if not already contra/loan) ---
        if label == "normal" and credit_fence is not None and t.paid_in > credit_fence:
            label = "outlier"
            reasons.append(
                f"One-off large credit {t.paid_in:,.0f} exceeds IQR fence "
                f"{credit_fence:,.0f} over recurring credits."
            )
        elif label == "normal" and debit_fence is not None and t.withdrawn > debit_fence:
            label = "outlier"
            reasons.append(
                f"One-off large debit {t.withdrawn:,.0f} exceeds IQR fence "
                f"{debit_fence:,.0f} over recurring debits."
            )

        # --- distress signal (independent of label — can stack with any of the above) ---
        distress_hit = _word_boundary_hit(desc, DISTRESS_KEYWORDS)
        if distress_hit:
            reasons.append(f"Distress signal: description matches '{distress_hit}'.")

        category = _categorize(desc)
        is_flagged = label in ("contra", "outlier") or bool(distress_hit)
        flag_reason = "; ".join(reasons)[:255] if reasons else None

        tags["label"] = label
        tags["category"] = category
        t.raw["label"] = label
        t.raw["category"] = category
        t.raw["is_flagged"] = is_flagged
        t.raw["flag_reason"] = flag_reason
