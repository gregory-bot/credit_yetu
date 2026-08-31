"""Canonicalize extracted transactions to chronological (oldest-first) order.

Source documents disagree on direction: this project's own M-Pesa sample
generator produces oldest-first, but plenty of real statements — the
Safaricom app's own M-Pesa statement export, and several bank e-statement
formats (confirmed on a real Standard Chartered statement during testing) —
list newest-first. The parsers themselves are direction-agnostic; they just
emit rows in whatever order the source table has.

Two downstream consumers silently assume oldest-first and produce wrong
results on a newest-first statement without this step:

  * ``app.services.fraud.forensics._balance_reconciliation`` walks consecutive
    pairs computing ``prev_balance + credit - debit == next_balance``. Fed a
    reversed statement, every single row mismatches — a real statement with
    zero tampering was observed scoring 100/100 fraud risk (100% of rows
    flagged as discontinuities) purely from this, before this fix.
  * ``app.services.summary.financial_summary.build_summary`` records "the
    last balance seen" per calendar month as that month's closing balance —
    on a reversed statement this captures the *first* (oldest) balance of
    the month instead, silently corrupting the monthly trend the credit team
    relies on.
"""
from __future__ import annotations

from app.services.extraction.models import ExtractedTransaction


def ensure_chronological(transactions: list[ExtractedTransaction]) -> list[ExtractedTransaction]:
    """Reverse (not re-sort) a newest-first list back to oldest-first.

    A reversal, rather than sorting by date, is deliberate: same-day rows
    carry no timestamp to disambiguate their true order, so a sort would
    scramble same-day sequencing while a reversal preserves it exactly as
    the source document presented it.
    """
    dated = [t for t in transactions if t.transaction_datetime is not None]
    if len(dated) < 2:
        return transactions
    if dated[0].transaction_datetime > dated[-1].transaction_datetime:
        return list(reversed(transactions))
    return transactions
