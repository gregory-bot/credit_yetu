"""Value objects shared by the extraction layer."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ExtractedTransaction:
    description: str = ""
    counterparty: str | None = None
    transaction_ref: str | None = None
    transaction_datetime: datetime | None = None
    paid_in: float = 0.0
    withdrawn: float = 0.0
    balance: float | None = None
    raw: dict = field(default_factory=dict)


@dataclass
class ExtractionResult:
    transactions: list[ExtractedTransaction] = field(default_factory=list)
    method: str = "text"                # text | ocr | mixed
    account_holder: str | None = None
    account_number: str | None = None
    phone_number: str | None = None
    statement_period: str | None = None
    pages: int = 0
    needs_review: bool = False
    warnings: list[str] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.transactions)
