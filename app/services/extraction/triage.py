"""Triage an uploaded document before parsing.

Decides three things, cheaply, up front:

1. Is the PDF encrypted, and does the supplied passcode open it?
2. Is it text-native (selectable text) or effectively scanned (image-only)?
3. Roughly how many characters per page (the signal for text vs. scan)?

The rest of the pipeline branches on this result.
"""
from __future__ import annotations

from dataclasses import dataclass

from pypdf import PdfReader
from pypdf.errors import PdfReadError

# Below this many extractable characters per page, we treat the page as scanned.
TEXT_CHARS_PER_PAGE_THRESHOLD = 100


@dataclass
class TriageResult:
    is_pdf: bool
    encrypted: bool
    unlocked: bool
    is_text_native: bool
    page_count: int
    avg_chars_per_page: float
    note: str = ""


def triage(path: str, passcode: str | None = None) -> TriageResult:
    if not path.lower().endswith(".pdf"):
        # Images (jpg/png) are always routed to OCR.
        return TriageResult(False, False, True, False, 1, 0.0, "non-pdf: route to OCR")

    try:
        reader = PdfReader(path)
    except (PdfReadError, OSError) as exc:
        return TriageResult(True, False, False, False, 0, 0.0, f"unreadable pdf: {exc}")

    encrypted = reader.is_encrypted
    unlocked = True
    if encrypted:
        try:
            # pypdf returns 0 on failure, 1/2 on success.
            unlocked = bool(reader.decrypt(passcode or ""))
        except Exception:  # noqa: BLE001 - defensive; malformed encryption dicts exist
            unlocked = False
        if not unlocked:
            return TriageResult(True, True, False, False, len(reader.pages), 0.0, "wrong or missing passcode")

    pages = len(reader.pages)
    total_chars = 0
    sample = reader.pages[: min(pages, 5)]  # sampling 5 pages is enough to classify
    for page in sample:
        try:
            total_chars += len(page.extract_text() or "")
        except Exception:  # noqa: BLE001
            continue
    avg = total_chars / max(len(sample), 1)
    is_text = avg >= TEXT_CHARS_PER_PAGE_THRESHOLD

    return TriageResult(
        is_pdf=True,
        encrypted=encrypted,
        unlocked=unlocked,
        is_text_native=is_text,
        page_count=pages,
        avg_chars_per_page=avg,
        note="text-native" if is_text else "scanned/image-only: route to OCR",
    )
