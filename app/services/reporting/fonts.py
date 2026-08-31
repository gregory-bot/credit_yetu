"""Register the Consolas monospace font for PDF report generation, if a copy
is available on the machine running the app.

Consolas ships with Microsoft Office / Windows — it's a commercial font this
project never bundles or redistributes. This only ever *references* a copy
already installed locally (e.g. via a licensed Office install); if none is
found, reports fall back to Courier (reportlab's built-in monospace) and
keep working rather than failing to render.
"""
from __future__ import annotations

import logging
from pathlib import Path

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

logger = logging.getLogger("reporting.fonts")

# Known locations Consolas ships in, across platforms/apps. Read-only lookups
# — nothing here is ever copied into this project or shipped with it.
_CANDIDATES: dict[str, tuple[str, ...]] = {
    "regular": (
        "/Applications/Microsoft Word.app/Contents/Resources/DFonts/Consola.ttf",
        "/Applications/Microsoft Excel.app/Contents/Resources/DFonts/Consola.ttf",
        "/Applications/Microsoft PowerPoint.app/Contents/Resources/DFonts/Consola.ttf",
        "C:/Windows/Fonts/consola.ttf",
        "/usr/share/fonts/truetype/consolas/Consola.ttf",
    ),
    "bold": (
        "/Applications/Microsoft Word.app/Contents/Resources/DFonts/Consolab.ttf",
        "/Applications/Microsoft Excel.app/Contents/Resources/DFonts/Consolab.ttf",
        "C:/Windows/Fonts/consolab.ttf",
    ),
    "italic": (
        "/Applications/Microsoft Word.app/Contents/Resources/DFonts/Consolai.ttf",
        "/Applications/Microsoft Excel.app/Contents/Resources/DFonts/Consolai.ttf",
        "C:/Windows/Fonts/consolai.ttf",
    ),
    "bold_italic": (
        "/Applications/Microsoft Word.app/Contents/Resources/DFonts/Consolaz.ttf",
        "/Applications/Microsoft Excel.app/Contents/Resources/DFonts/Consolaz.ttf",
        "C:/Windows/Fonts/consolaz.ttf",
    ),
}

_registered = False
MONO_FONT = "Courier"        # overwritten by register_consolas() if found
MONO_BOLD = "Courier-Bold"


def _first_existing(paths: tuple[str, ...]) -> str | None:
    for p in paths:
        if Path(p).exists():
            return p
    return None


def register_consolas() -> str:
    """Idempotent — safe to call on every report generation.

    Returns the font family name to actually use: ``"Consolas"`` if a copy
    was found and registered on this machine, else the built-in
    ``"Courier"`` fallback.
    """
    global _registered, MONO_FONT, MONO_BOLD
    if _registered:
        return MONO_FONT

    regular = _first_existing(_CANDIDATES["regular"])
    if not regular:
        logger.info("Consolas not found on this machine; PDF reports will use Courier instead.")
        _registered = True
        return MONO_FONT

    try:
        pdfmetrics.registerFont(TTFont("Consolas", regular))
        bold = _first_existing(_CANDIDATES["bold"]) or regular
        italic = _first_existing(_CANDIDATES["italic"]) or regular
        bold_italic = _first_existing(_CANDIDATES["bold_italic"]) or regular
        pdfmetrics.registerFont(TTFont("Consolas-Bold", bold))
        pdfmetrics.registerFont(TTFont("Consolas-Italic", italic))
        pdfmetrics.registerFont(TTFont("Consolas-BoldItalic", bold_italic))
        pdfmetrics.registerFontFamily(
            "Consolas", normal="Consolas", bold="Consolas-Bold",
            italic="Consolas-Italic", boldItalic="Consolas-BoldItalic",
        )
        MONO_FONT, MONO_BOLD = "Consolas", "Consolas-Bold"
        logger.info("Registered Consolas from %s for report generation.", regular)
    except Exception as exc:  # noqa: BLE001 — a bad font file must never break report generation
        logger.warning("Found a Consolas file but failed to register it (%s); falling back to Courier.", exc)
    _registered = True
    return MONO_FONT
