"""OCR fallback for scanned or photographed statements.

Scanned documents are rasterized and run through Tesseract, then the resulting
text is handed to the same line-based reconciliation logic used by the M-Pesa
parser. OCR output is inherently lower-confidence, so every result from this
path is marked ``needs_review=True`` — the Umba doc's principle that scanned
statements should be *reviewed*, never silently auto-accepted.

System dependencies (install separately):
    * tesseract-ocr
    * poppler-utils   (for pdf2image)

If those aren't present, this module degrades gracefully: it raises a clear
error the pipeline turns into a "manual review" status rather than crashing.
"""
from __future__ import annotations

from app.config import settings
from app.services.extraction.models import ExtractionResult
from app.services.extraction.mpesa_parser import _parse_line_fallback


class OcrUnavailable(RuntimeError):
    """Raised when OCR system dependencies are not installed."""


def _ocr_pdf_to_text(path: str, dpi: int) -> str:
    try:
        import pytesseract
        from pdf2image import convert_from_path
    except ImportError as exc:  # pragma: no cover - env dependent
        raise OcrUnavailable(f"OCR libraries not installed: {exc}") from exc

    try:
        images = convert_from_path(path, dpi=dpi)
    except Exception as exc:  # noqa: BLE001 - poppler missing, corrupt file, etc.
        raise OcrUnavailable(f"Could not rasterize PDF (is poppler installed?): {exc}") from exc

    return "\n".join(pytesseract.image_to_string(img) for img in images)


def _ocr_image_to_text(path: str) -> str:
    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:  # pragma: no cover
        raise OcrUnavailable(f"OCR libraries not installed: {exc}") from exc
    return pytesseract.image_to_string(Image.open(path))


def parse_with_ocr(path: str) -> ExtractionResult:
    if not settings.ocr_enabled:
        raise OcrUnavailable("OCR is disabled via configuration (OCR_ENABLED=false).")

    text = _ocr_image_to_text(path) if path.lower().endswith((".png", ".jpg", ".jpeg")) else _ocr_pdf_to_text(path, settings.ocr_dpi)

    result = ExtractionResult(method="ocr", needs_review=True)
    result.transactions = list(_parse_line_fallback(text).values())
    result.warnings.append("Extracted via OCR — flagged for manual review.")
    if not result.transactions:
        result.warnings.append("OCR produced no recognizable transactions.")
    return result
