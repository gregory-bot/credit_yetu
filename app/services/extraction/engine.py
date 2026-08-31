"""Top-level extraction entry point: triage, then dispatch to a parser."""
from __future__ import annotations

from app.services.extraction.bank_parser import parse_bank
from app.services.extraction.models import ExtractionResult
from app.services.extraction.mpesa_parser import parse_mpesa
from app.services.extraction.ocr_parser import OcrUnavailable, parse_with_ocr
from app.services.extraction.triage import triage

_MPESA_TYPES = {"mpesa", "till", "paybill", "user_statement"}


def extract(path: str, statement_type: str, passcode: str | None = None, bank_code: str | None = None) -> ExtractionResult:
    """Extract transactions from a statement file.

    ``statement_type`` ∈ {mpesa, till, paybill, bank, sacco}.
    """
    t = triage(path, passcode)

    if t.encrypted and not t.unlocked:
        result = ExtractionResult(method="none", needs_review=True)
        result.warnings.append("Statement is encrypted and the passcode was missing or incorrect.")
        return result

    stype = statement_type.lower()

    # Text-native PDFs go through the deterministic parsers.
    if t.is_text_native:
        if stype in _MPESA_TYPES or stype == "mpesa":
            res = parse_mpesa(path, passcode)
        else:
            res = parse_bank(path, passcode, bank_code)

        # If the deterministic parser came up empty on a supposedly text PDF,
        # fall through to OCR as a second attempt.
        if res.count == 0:
            try:
                ocr_res = parse_with_ocr(path)
                if ocr_res.count:
                    ocr_res.warnings.insert(0, "Text parser found nothing; recovered via OCR.")
                    return ocr_res
            except OcrUnavailable as exc:
                res.warnings.append(str(exc))
        return res

    # Scanned / image-only → OCR.
    try:
        return parse_with_ocr(path)
    except OcrUnavailable as exc:
        result = ExtractionResult(method="none", needs_review=True)
        result.warnings.append(
            f"Document appears scanned but OCR is unavailable: {exc}. Manual review required."
        )
        return result
