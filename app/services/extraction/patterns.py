"""Regexes and small helpers shared by the statement parsers."""
from __future__ import annotations

import re
from datetime import datetime

# Safaricom M-Pesa receipt code, e.g. "PLV6XV3WK2" (10 alphanumerics, starts with a letter).
MPESA_RECEIPT_RE = re.compile(r"\b([A-Z]{2}[A-Z0-9]{8})\b")

# A monetary amount, optionally with thousands separators and a decimal part.
# Negative values may appear as -1,234.00 or (1,234.00).
AMOUNT_RE = re.compile(r"-?\(?\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?\)?")

# Common datetime shapes across Safaricom / bank statements.
_DATE_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%d-%m-%Y %H:%M:%S",
    "%d/%m/%Y %H:%M:%S",
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%Y-%m-%d",
    "%d %b %Y",
    "%d %B %Y",
    "%m/%d/%Y %I:%M:%S %p",
)

DATETIME_RE = re.compile(
    r"\b(\d{4}[-/]\d{2}[-/]\d{2}(?:[ T]\d{2}:\d{2}:\d{2})?"
    r"|\d{2}[-/]\d{2}[-/]\d{4}(?:\s+\d{2}:\d{2}:\d{2})?)\b"
)

PHONE_RE = re.compile(r"\b(?:254|\+254|0)7\d{8}\b")


def parse_amount(token: str | None) -> float:
    """Parse a monetary token to float. Returns 0.0 on failure."""
    if not token:
        return 0.0
    t = token.strip().replace(",", "").replace(" ", "")
    negative = t.startswith("(") and t.endswith(")")
    t = t.strip("()")
    try:
        value = float(t)
    except ValueError:
        return 0.0
    return -value if negative else value


def parse_datetime(token: str | None) -> datetime | None:
    if not token:
        return None
    token = token.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(token, fmt)
        except ValueError:
            continue
    # Last resort: pull a date-like substring and retry.
    m = DATETIME_RE.search(token)
    if m:
        for fmt in _DATE_FORMATS:
            try:
                return datetime.strptime(m.group(1), fmt)
            except ValueError:
                continue
    return None
