"""Parser for Safaricom M-Pesa statements (full, till and paybill).

Strategy — belt *and* braces, because "no transaction left out" is the goal:

1. Primary: pdfplumber table extraction. The M-Pesa "Detailed Statement" is a
   real ruled table with a stable header
   (Receipt No. | Completion Time | Details | Transaction Status | Paid In |
   Withdrawn | Balance). We map columns by header text, not by position, so the
   parser survives minor layout drift.

2. Continuation rows: a wrapped "Details" cell produces a row with an empty
   receipt number — we append its text to the previous transaction instead of
   dropping it.

3. Fallback / reconciliation: we also line-scan every page for receipt codes.
   Any receipt found in the text but missing from the table result is recovered
   from the line fallback, and the discrepancy is recorded as a warning so the
   credit team can see exactly what happened.
"""
from __future__ import annotations

import pdfplumber

from app.services.extraction.models import ExtractedTransaction, ExtractionResult
from app.services.extraction.patterns import (
    AMOUNT_RE,
    DATETIME_RE,
    MPESA_RECEIPT_RE,
    PHONE_RE,
    parse_amount,
    parse_datetime,
)

_HEADER_HINTS = ("receipt", "completion", "details", "paid in", "withdrawn", "balance")


def _looks_like_header(row: list[str]) -> bool:
    joined = " ".join((c or "").lower() for c in row)
    return sum(h in joined for h in _HEADER_HINTS) >= 3


def _column_map(header: list[str]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for idx, cell in enumerate(header):
        c = (cell or "").lower()
        if "receipt" in c:
            mapping["receipt"] = idx
        elif "completion" in c or "date" in c:
            mapping["date"] = idx
        elif "details" in c or "description" in c:
            mapping["details"] = idx
        elif "status" in c:
            mapping["status"] = idx
        elif "paid" in c:
            mapping["paid_in"] = idx
        elif "withdraw" in c or "withdrawn" in c:
            mapping["withdrawn"] = idx
        elif "balance" in c:
            mapping["balance"] = idx
    return mapping


def _extract_meta(text: str) -> dict[str, str | None]:
    holder = None
    for line in text.splitlines():
        low = line.lower()
        if "customer name" in low or "statement for" in low:
            parts = line.split(":", 1)
            if len(parts) == 2 and parts[1].strip():
                holder = parts[1].strip()
                break
    phone_match = PHONE_RE.search(text)
    period = None
    # Look for "01 Jan 2023 - 31 Mar 2023" style ranges.
    dates = DATETIME_RE.findall(text)
    if len(dates) >= 2:
        period = f"{dates[0]} - {dates[-1]}"
    return {
        "holder": holder,
        "phone": phone_match.group(0) if phone_match else None,
        "period": period,
    }


def _parse_line_fallback(text: str) -> dict[str, ExtractedTransaction]:
    """Recover transactions directly from raw text keyed by receipt code."""
    found: dict[str, ExtractedTransaction] = {}
    for line in text.splitlines():
        m = MPESA_RECEIPT_RE.search(line)
        if not m:
            continue
        receipt = m.group(1)
        amounts = AMOUNT_RE.findall(line)
        dt = DATETIME_RE.search(line)
        # In a full row the trailing numbers are (paid_in|withdrawn) then balance.
        paid_in = withdrawn = 0.0
        balance = None
        if len(amounts) >= 2:
            balance = parse_amount(amounts[-1])
            movement = parse_amount(amounts[-2])
            if movement < 0:
                withdrawn = abs(movement)
            else:
                paid_in = movement
        found[receipt] = ExtractedTransaction(
            description=line.strip(),
            transaction_ref=receipt,
            transaction_datetime=parse_datetime(dt.group(1)) if dt else None,
            paid_in=paid_in,
            withdrawn=withdrawn,
            balance=balance,
            raw={"source": "line_fallback"},
        )
    return found


def parse_mpesa(path: str, passcode: str | None = None) -> ExtractionResult:
    result = ExtractionResult(method="text")
    table_txns: list[ExtractedTransaction] = []
    all_text_parts: list[str] = []

    with pdfplumber.open(path, password=passcode or "") as pdf:
        result.pages = len(pdf.pages)
        col_map: dict[str, int] = {}
        for page in pdf.pages:
            all_text_parts.append(page.extract_text() or "")
            for table in page.extract_tables() or []:
                for row in table:
                    if not row or all((c or "").strip() == "" for c in row):
                        continue
                    if _looks_like_header(row):
                        col_map = _column_map(row)
                        continue
                    if not col_map:
                        continue

                    def cell(key: str) -> str:
                        i = col_map.get(key)
                        return (row[i] if i is not None and i < len(row) else "") or ""

                    receipt = cell("receipt").strip()
                    details = cell("details").strip()

                    if not receipt:
                        # Continuation of the previous transaction's details.
                        if table_txns and details:
                            table_txns[-1].description += f" {details}"
                        continue

                    table_txns.append(
                        ExtractedTransaction(
                            description=details,
                            transaction_ref=receipt,
                            transaction_datetime=parse_datetime(cell("date")),
                            paid_in=parse_amount(cell("paid_in")),
                            withdrawn=abs(parse_amount(cell("withdrawn"))),
                            balance=parse_amount(cell("balance")) or None,
                            raw={"source": "table", "status": cell("status").strip()},
                        )
                    )

    full_text = "\n".join(all_text_parts)
    meta = _extract_meta(full_text)
    result.account_holder = meta["holder"]
    result.phone_number = meta["phone"]
    result.statement_period = meta["period"]

    # Reconcile: recover any receipts present in text but missing from the table.
    line_txns = _parse_line_fallback(full_text)
    table_receipts = {t.transaction_ref for t in table_txns if t.transaction_ref}
    recovered = [tx for rc, tx in line_txns.items() if rc not in table_receipts]

    if table_txns:
        result.transactions = table_txns + recovered
        if recovered:
            result.method = "mixed"
            result.warnings.append(
                f"{len(recovered)} transaction(s) recovered via line fallback "
                f"(not captured by table extraction)."
            )
    else:
        # No table at all — rely entirely on the line fallback.
        result.transactions = list(line_txns.values())
        result.warnings.append("Table extraction found nothing; used line fallback only.")
        result.needs_review = True

    if not result.transactions:
        result.needs_review = True
        result.warnings.append("No transactions extracted — manual review required.")

    return result
