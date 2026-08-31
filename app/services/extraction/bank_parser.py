"""Generic bank-statement parser.

Banks differ far more than M-Pesa, so this parser is column-inference based:
it locates a header row containing date/description/debit/credit/balance-style
labels, maps columns by their labels, and reads the ruled table. A per-bank
subclass/override can be added under this package as specific formats are
onboarded (mirrors the "multi-engine, format-specific fixes" approach in the
Umba handoff doc) without touching the calling code.
"""
from __future__ import annotations

import re

import pdfplumber

from app.services.extraction.models import ExtractedTransaction, ExtractionResult
from app.services.extraction.patterns import DATETIME_RE, PHONE_RE, parse_amount, parse_datetime

_DATE_HINTS = ("date", "value date", "txn date", "posting")
_DESC_HINTS = ("description", "narration", "details", "particulars", "transaction")
_DEBIT_HINTS = ("debit", "withdrawal", "dr", "money out", "paid out")
_CREDIT_HINTS = ("credit", "deposit", "cr", "money in", "paid in")
_BAL_HINTS = ("balance", "running balance")

# Tried in order against the header block only (see `_header_block`) — never
# against the whole document, since a transaction line like "254724128531-
# MOBILE MONEY" would otherwise be misread as the account holder's own name
# or phone number.
_NAME_PATTERNS = (
    re.compile(r"Name\s+([A-Z][A-Za-z .,'\-]{2,60}?)\s+Account\s+Type", re.IGNORECASE),
    re.compile(r"(?:Account\s+Name|Customer\s+Name|Client\s+Name|Account\s+Holder)\s*[:\-]?\s*"
               r"([A-Z][A-Za-z .,'\-]{2,60})", re.IGNORECASE),
    re.compile(r"^\s*Name\s*[:\-]\s*([A-Z][A-Za-z .,'\-]{2,60})\s*$", re.IGNORECASE | re.MULTILINE),
)
_ACCOUNT_NUMBER_RE = re.compile(r"Account\s+Number\s*[:\-]?\s*([A-Za-z0-9*]{4,32})", re.IGNORECASE)
_PERIOD_PATTERNS = (
    re.compile(r"From\s+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s+To\s+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", re.IGNORECASE),
    re.compile(r"Statement\s+Period\s*[:\-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s*(?:to|-|–)\s*"
               r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", re.IGNORECASE),
)


def _match(cell: str, hints: tuple[str, ...]) -> bool:
    c = (cell or "").lower().strip()
    return any(h in c for h in hints)


def _map_columns(header: list[str]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for idx, cell in enumerate(header):
        if "date" in mapping and _match(cell, _DATE_HINTS):
            continue
        if _match(cell, _DATE_HINTS):
            mapping["date"] = idx
        elif _match(cell, _DESC_HINTS):
            mapping["desc"] = idx
        elif _match(cell, _DEBIT_HINTS):
            mapping["debit"] = idx
        elif _match(cell, _CREDIT_HINTS):
            mapping["credit"] = idx
        elif _match(cell, _BAL_HINTS):
            mapping["balance"] = idx
    return mapping


def _is_header(row: list[str]) -> bool:
    joined = " ".join((c or "").lower() for c in row)
    has_date = any(h in joined for h in _DATE_HINTS)
    has_money = any(h in joined for h in _DEBIT_HINTS + _CREDIT_HINTS + _BAL_HINTS)
    return has_date and has_money


def _header_block(page1_text: str) -> str:
    """Everything before the transaction table's column-header line.

    Bank letterheads put account holder / account number / statement period
    above the table on page 1 — but that same page's linear text also
    contains the first several transaction rows (each potentially embedding
    a counterparty's phone number). Isolating the block above the table
    header keeps metadata extraction from ever reading a transaction line.
    """
    lines = page1_text.splitlines()
    for i, line in enumerate(lines):
        if _is_header([line]):
            return "\n".join(lines[:i])
    return page1_text  # no recognizable table header on page 1 — use it all


def _extract_bank_meta(page1_text: str) -> dict[str, str | None]:
    header = _header_block(page1_text)

    holder = None
    for pattern in _NAME_PATTERNS:
        m = pattern.search(header)
        if m:
            holder = re.sub(r"\s+", " ", m.group(1)).strip(" ,.-")
            break

    acct_match = _ACCOUNT_NUMBER_RE.search(header)
    account_number = acct_match.group(1).strip() if acct_match else None

    phone_match = PHONE_RE.search(header)
    phone = phone_match.group(0) if phone_match else None

    period = None
    for pattern in _PERIOD_PATTERNS:
        m = pattern.search(header)
        if m:
            period = f"{m.group(1)} - {m.group(2)}"
            break
    if period is None:
        dates = DATETIME_RE.findall(header)
        if len(dates) >= 2:
            period = f"{dates[0]} - {dates[-1]}"

    return {"holder": holder, "account_number": account_number, "phone": phone, "period": period}


def parse_bank(path: str, passcode: str | None = None, bank_code: str | None = None) -> ExtractionResult:
    result = ExtractionResult(method="text")
    txns: list[ExtractedTransaction] = []

    with pdfplumber.open(path, password=passcode or "") as pdf:
        result.pages = len(pdf.pages)
        if pdf.pages:
            meta = _extract_bank_meta(pdf.pages[0].extract_text() or "")
            result.account_holder = meta["holder"]
            result.account_number = meta["account_number"]
            result.phone_number = meta["phone"]
            result.statement_period = meta["period"]

        col_map: dict[str, int] = {}
        for page in pdf.pages:
            for table in page.extract_tables() or []:
                for row in table:
                    if not row or all((c or "").strip() == "" for c in row):
                        continue
                    if _is_header(row):
                        col_map = _map_columns(row)
                        continue
                    if not col_map or "date" not in col_map:
                        continue

                    def cell(key: str) -> str:
                        i = col_map.get(key)
                        return (row[i] if i is not None and i < len(row) else "") or ""

                    dt = parse_datetime(cell("date"))
                    desc = cell("desc").strip()
                    if not dt and not desc:
                        continue

                    debit = abs(parse_amount(cell("debit")))
                    credit = parse_amount(cell("credit"))
                    if not dt and txns:
                        # Wrapped narration row.
                        txns[-1].description += f" {desc}"
                        continue

                    txns.append(
                        ExtractedTransaction(
                            description=desc,
                            transaction_datetime=dt,
                            paid_in=credit,
                            withdrawn=debit,
                            balance=parse_amount(cell("balance")) or None,
                            raw={"source": "table", "bank": bank_code},
                        )
                    )

    result.transactions = txns
    if not txns:
        result.needs_review = True
        result.warnings.append(
            f"No transactions parsed for bank '{bank_code or 'unknown'}'. "
            "A format-specific parser may be required."
        )
    return result
