"""Generic bank-statement parser.

Banks differ far more than M-Pesa, so this parser is column-inference based:
it locates a header row containing date/description/debit/credit/balance-style
labels, maps columns by their labels, and reads the ruled table. A per-bank
subclass/override can be added under this package as specific formats are
onboarded (mirrors the "multi-engine, format-specific fixes" approach in the
Umba handoff doc) without touching the calling code.
"""
from __future__ import annotations

import pdfplumber

from app.services.extraction.models import ExtractedTransaction, ExtractionResult
from app.services.extraction.patterns import parse_amount, parse_datetime

_DATE_HINTS = ("date", "value date", "txn date", "posting")
_DESC_HINTS = ("description", "narration", "details", "particulars", "transaction")
_DEBIT_HINTS = ("debit", "withdrawal", "dr", "money out", "paid out")
_CREDIT_HINTS = ("credit", "deposit", "cr", "money in", "paid in")
_BAL_HINTS = ("balance", "running balance")


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


def parse_bank(path: str, passcode: str | None = None, bank_code: str | None = None) -> ExtractionResult:
    result = ExtractionResult(method="text")
    txns: list[ExtractedTransaction] = []

    with pdfplumber.open(path, password=passcode or "") as pdf:
        result.pages = len(pdf.pages)
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
