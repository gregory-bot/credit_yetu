"""Render a scorecard PDF with reportlab.

The PDF is a rendered *view* of the same score/summary/fraud data persisted to
the database — never a separate computation — so it can't disagree with the API
response or the Excel export.

Layout is deliberately modeled on a conventional lender scorecard (client
info -> monthly financial reconciliation -> score data -> reasons -> flagged
items -> authenticity check -> disclaimer) so a credit analyst who already
reads scorecards can navigate this one without a legend.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.graphics.shapes import Circle, Drawing, Line, Rect, String, Wedge
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.config import settings
from app.services.reporting.fonts import register_consolas

_MONO = register_consolas()
_MONO_BOLD = _MONO + "-Bold" if _MONO != "Courier" else "Courier-Bold"

_ACCENT = colors.HexColor("#3B2F8F")
_ACCENT_DARK = colors.HexColor("#241C5C")
_LIGHT = colors.HexColor("#F3F1FB")
_INK = colors.HexColor("#1F2430")
_MUTED = colors.HexColor("#6B7280")
_GOOD = colors.HexColor("#1E8E3E")
_WARN = colors.HexColor("#B45309")
_BAD = colors.HexColor("#C22222")

# Table column-header backgrounds: amber with dark text, not the purple/white
# combination used elsewhere — kept distinct from the brand accent so the
# headings read clearly at small sizes.
_HEADER_BG = colors.HexColor("#F2A93C")
_HEADER_TEXT = colors.HexColor("#1F1400")

_styles = getSampleStyleSheet()
for _base in ("Normal", "BodyText", "Title", "Heading3"):
    _styles[_base].fontName = _MONO
_styles["Title"].leading = 22
_styles.add(ParagraphStyle("Wordmark", parent=_styles["Title"], fontName=_MONO_BOLD, textColor=_ACCENT, fontSize=20, leading=24))
_styles.add(ParagraphStyle("Tagline", parent=_styles["Normal"], fontName=_MONO, textColor=_MUTED, fontSize=8, leading=10))
_styles.add(ParagraphStyle("SectionHead", parent=_styles["Heading3"], fontName=_MONO_BOLD, textColor=_ACCENT_DARK, spaceBefore=1, spaceAfter=2))
_styles.add(ParagraphStyle("Cell", parent=_styles["BodyText"], fontName=_MONO, fontSize=8, leading=10))
_styles.add(ParagraphStyle("CellSmall", parent=_styles["BodyText"], fontName=_MONO, fontSize=6.5, leading=8))
_styles.add(ParagraphStyle("StatValue", parent=_styles["Normal"], fontName=_MONO_BOLD, fontSize=24, leading=27, textColor=_INK, alignment=1))
_styles.add(ParagraphStyle("StatLabel", parent=_styles["Normal"], fontName=_MONO, fontSize=8, leading=10, textColor=_MUTED, alignment=1))
_styles.add(ParagraphStyle("Footer", parent=_styles["Normal"], fontName=_MONO, fontSize=7, leading=9, textColor=_MUTED))


def _status(statement, score) -> tuple[str, colors.Color]:
    if statement.status == "failed":
        return "FAILED", _BAD
    if statement.needs_review or (score.fraud_data or {}).get("risk_level") == "high":
        return "NEEDS REVIEW", _WARN
    return "SCORED", _GOOD


def _kv_table(rows: list[tuple[str, str]], col_widths=(58 * mm, 112 * mm)) -> Table:
    t = Table(
        [[Paragraph(f"<b>{k}</b>", _styles["Cell"]), Paragraph(str(v), _styles["Cell"])] for k, v in rows],
        colWidths=col_widths,
    )
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, _LIGHT]),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D9D5EC")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E8E5F5")),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


def _stat_card(value: str, label: str, width: float, accent: colors.Color = _ACCENT, value_font_size: int = 24) -> Table:
    """A single stat card: value on top, label below — two independent rows,
    so mixed font sizes never fight over one row's height."""
    value_style = _styles["StatValue"]
    if value_font_size != 24:
        value_style = ParagraphStyle(f"StatValue{value_font_size}", parent=value_style,
                                      fontSize=value_font_size, leading=value_font_size + 3)
    t = Table([[Paragraph(value, value_style)], [Paragraph(label, _styles["StatLabel"])]], colWidths=[width])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _LIGHT),
        ("BOX", (0, 0), (-1, -1), 1, accent),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (0, 0), 9),
        ("BOTTOMPADDING", (0, 0), (0, 0), 2),
        ("TOPPADDING", (0, 1), (0, 1), 0),
        ("BOTTOMPADDING", (0, 1), (0, 1), 9),
    ]))
    return t


def _section(title: str) -> Paragraph:
    return Paragraph(title.upper(), _styles["SectionHead"])


def _money(v: float | None) -> str:
    return f"KSh {v:,.2f}" if v is not None else "—"


def _money0(v: float | None) -> str:
    return f"KSh {v:,.0f}" if v is not None else "—"


# --- Score gauge -------------------------------------------------------
# A semicircular dial, banded by grade, with a needle over the client's own
# score and the score/grade printed inside the dial's hollow center — the
# score reads *from* the gauge rather than sitting in a plain box beside it.
_GAUGE_MIN, _GAUGE_MAX = 300, 900
_GAUGE_BANDS = (
    (300, 480, colors.HexColor("#D9382B"), "POOR"),
    (480, 600, colors.HexColor("#F0932B"), "FAIR"),
    (600, 670, colors.HexColor("#F5C518"), "GOOD"),
    (670, 800, colors.HexColor("#8BC34A"), "VERY GOOD"),
    (800, 900, colors.HexColor("#2E8B3D"), "EXCELLENT"),
)


def _gauge_angle(score: float) -> float:
    frac = max(0.0, min(1.0, (score - _GAUGE_MIN) / (_GAUGE_MAX - _GAUGE_MIN)))
    return 180 - frac * 180  # 180° at the left (min), 0° at the right (max)


def _score_gauge(score: int, grade: str) -> Drawing:
    """A compact gauge card: rounded-corner border, gauge sized to fit inside
    it with room to spare, meant to sit beside the loan-limit card rather
    than spanning the page on its own.

    The pivot sits above the card's bottom edge (not on it) so the score and
    grade readout can go *below* the pivot: the needle is a line from the
    pivot outward at an angle in [0°, 180°], which means it can never have a
    negative y-component — putting the readout below the pivot guarantees
    the needle can never cross it, at any score.
    """
    width, height = 84 * mm, 59 * mm
    cx, cy = width / 2, 19 * mm
    outer_r, inner_r = 25 * mm, 14.5 * mm
    d = Drawing(width, height)

    # Rounded-corner card background, drawn first so everything else sits on top.
    d.add(Rect(0.6 * mm, 0.6 * mm, width - 1.2 * mm, height - 1.2 * mm,
               rx=4 * mm, ry=4 * mm, fillColor=colors.white, strokeColor=colors.HexColor("#D9D5EC"), strokeWidth=1))

    for lo, hi, color, label in _GAUGE_BANDS:
        a0, a1 = _gauge_angle(hi), _gauge_angle(lo)  # higher score -> smaller angle (right side)
        d.add(Wedge(cx, cy, outer_r, a0, a1, radius1=inner_r, fillColor=color, strokeColor=colors.white, strokeWidth=0.7))
        mid = math.radians((a0 + a1) / 2)
        lx, ly = cx + (outer_r + 4.4 * mm) * math.cos(mid), cy + (outer_r + 4.4 * mm) * math.sin(mid)
        d.add(String(lx, ly, label, fontSize=4, fillColor=_INK, textAnchor="middle", fontName=_MONO_BOLD))

    # Needle, clamped into [min, max] even if a rule pushed the score to the
    # engine's hard floor/ceiling.
    clamped = max(_GAUGE_MIN, min(_GAUGE_MAX, score))
    ang = math.radians(_gauge_angle(clamped))
    needle_len = outer_r * 0.85
    d.add(Line(cx, cy, cx + needle_len * math.cos(ang), cy + needle_len * math.sin(ang),
               strokeColor=colors.HexColor("#1F2430"), strokeWidth=1.6))
    d.add(Circle(cx, cy, 1.6 * mm, fillColor=_INK, strokeColor=None))

    # Score + grade readout, below the pivot — see the docstring for why
    # that's the position the needle can never reach.
    d.add(String(cx, cy - 8 * mm, str(score), fontSize=15, fillColor=_INK, textAnchor="middle", fontName=_MONO_BOLD))
    d.add(String(cx, cy - 12.5 * mm, f"GRADE {grade}", fontSize=6, fillColor=_MUTED, textAnchor="middle", fontName=_MONO_BOLD))
    return d


def _monthly_table(monthly: dict) -> Table:
    headers = ["Month", "Credits", "Loans (Cr)", "Outliers (Cr)", "Net (CR)",
               "Debits", "Loans (Dr)", "Outliers (Dr)", "Net (DR)", "Highest Bal", "Lowest Bal"]
    rows = [[Paragraph(f"<b>{h}</b>", _styles["CellSmall"]) for h in headers]]

    # Whole shillings here, not cents: at this column width (11 columns on a
    # portrait page) a value like "743,284.65" wraps mid-digit onto a second
    # line — the exact "rolled-over text" this report was rebuilt to fix.
    # Full precision is still in the API response and the Excel export.
    def fmt(v):
        return "" if v is None else f"{v:,.0f}"

    for r in monthly.get("rows", []):
        rows.append([
            Paragraph(r["month"], _styles["CellSmall"]),
            Paragraph(fmt(r["credits"]), _styles["CellSmall"]),
            Paragraph(fmt(r["loan_credits"]), _styles["CellSmall"]),
            Paragraph(fmt(r["outlier_credits"]), _styles["CellSmall"]),
            Paragraph(fmt(r["net_credit"]), _styles["CellSmall"]),
            Paragraph(fmt(r["debits"]), _styles["CellSmall"]),
            Paragraph(fmt(r["loan_debits"]), _styles["CellSmall"]),
            Paragraph(fmt(r["outlier_debits"]), _styles["CellSmall"]),
            Paragraph(fmt(r["net_debit"]), _styles["CellSmall"]),
            Paragraph(fmt(r["highest_balance"]), _styles["CellSmall"]),
            Paragraph(fmt(r["lowest_balance"]), _styles["CellSmall"]),
        ])

    for label, key_row in (("Total", monthly.get("totals", {})), ("Average", monthly.get("averages", {}))):
        rows.append([
            Paragraph(f"<b>{label}</b>", _styles["CellSmall"]),
            Paragraph(f"<b>{fmt(key_row.get('credits'))}</b>", _styles["CellSmall"]),
            Paragraph(f"<b>{fmt(key_row.get('loan_credits'))}</b>", _styles["CellSmall"]),
            Paragraph(f"<b>{fmt(key_row.get('outlier_credits'))}</b>", _styles["CellSmall"]),
            Paragraph(f"<b>{fmt(key_row.get('net_credit'))}</b>", _styles["CellSmall"]),
            Paragraph(f"<b>{fmt(key_row.get('debits'))}</b>", _styles["CellSmall"]),
            Paragraph(f"<b>{fmt(key_row.get('loan_debits'))}</b>", _styles["CellSmall"]),
            Paragraph(f"<b>{fmt(key_row.get('outlier_debits'))}</b>", _styles["CellSmall"]),
            Paragraph(f"<b>{fmt(key_row.get('net_debit'))}</b>", _styles["CellSmall"]),
            Paragraph(f"<b>{fmt(key_row.get('highest_balance'))}</b>", _styles["CellSmall"]),
            Paragraph(f"<b>{fmt(key_row.get('lowest_balance'))}</b>", _styles["CellSmall"]),
        ])

    n_data_rows = len(monthly.get("rows", []))
    col_widths = [14 * mm] + [16 * mm] * 9 + [14 * mm]
    t = Table(rows, colWidths=col_widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), _HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), _HEADER_TEXT),
        ("ROWBACKGROUNDS", (0, 1), (-1, n_data_rows), [colors.white, _LIGHT]),
        ("BACKGROUND", (0, n_data_rows + 1), (-1, -1), colors.HexColor("#E8E5F5")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#DDDAE8")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#B9B3DC")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]
    t.setStyle(TableStyle(style))
    return t


def _flagged_transactions_table(statement) -> Table | None:
    flagged = [t for t in statement.transactions if t.is_flagged]
    if not flagged:
        return None
    flagged = sorted(flagged, key=lambda t: t.transaction_datetime or datetime.min)
    rows = [[Paragraph(f"<b>{h}</b>", _styles["CellSmall"])
             for h in ("Date", "Description", "Amount", "Dir.", "Reason")]]
    for t in flagged[:40]:
        date_str = t.transaction_datetime.strftime("%d %b %Y") if t.transaction_datetime else "—"
        amount = t.paid_in if t.paid_in else t.withdrawn
        direction = "IN" if t.paid_in else "OUT"
        rows.append([
            Paragraph(date_str, _styles["CellSmall"]),
            Paragraph((t.description or "")[:80], _styles["CellSmall"]),
            Paragraph(f"{amount:,.2f}", _styles["CellSmall"]),
            Paragraph(direction, _styles["CellSmall"]),
            Paragraph(t.flag_reason or "—", _styles["CellSmall"]),
        ])
    t = Table(rows, colWidths=(20 * mm, 55 * mm, 20 * mm, 12 * mm, 55 * mm), repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), _HEADER_TEXT),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FDF3E7")]),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E8C48A")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    return t


def build_scorecard_pdf(statement, score) -> str:
    out_dir = settings.storage_path / "reports"
    path = str(out_dir / f"scorecard_{statement.reference_id}.pdf")

    doc = SimpleDocTemplate(path, pagesize=A4, topMargin=12 * mm, bottomMargin=12 * mm,
                             leftMargin=12 * mm, rightMargin=12 * mm)
    story = []

    # --- Header: brand wordmark + generation meta + status ---
    status_label, status_color = _status(statement, score)
    header = Table([[
        Paragraph(f"<b>{settings.app_name}</b>", _styles["Wordmark"]),
        Paragraph(
            f"Generated {datetime.now(timezone.utc).strftime('%d %b %Y, %H:%M UTC')}<br/>"
            f"Reference: {statement.reference_id}<br/>Statement type: {statement.statement_type.upper()}",
            _styles["Cell"],
        ),
    ]], colWidths=(85 * mm, 95 * mm))
    header.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("ALIGN", (1, 0), (1, 0), "RIGHT")]))
    story.append(header)
    story.append(Paragraph("Transparent credit scoring, explained.", _styles["Tagline"]))
    story.append(Spacer(1, 3 * mm))
    story.append(HRFlowable(width="100%", thickness=1.2, color=_ACCENT))
    story.append(Spacer(1, 2 * mm))

    status_bar = Table([[Paragraph(f"<b>Status: {status_label}</b>", _styles["Cell"])]], colWidths=(186 * mm,))
    status_bar.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), status_color),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story += [status_bar, Spacer(1, 3 * mm)]

    # --- Headline: loan limit on the left, score gauge on the right ---
    headline = Table(
        [[
            _stat_card(f"{_money0(score.limit_low)} – {_money0(score.limit_high)}", "LOAN LIMIT",
                       76 * mm, value_font_size=14),
            _score_gauge(score.credit_score, score.grade),
        ]],
        colWidths=(93 * mm, 93 * mm),
    )
    headline.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (0, 0), (0, 0), "LEFT"),
                                   ("ALIGN", (1, 0), (1, 0), "RIGHT")]))
    story.append(headline)
    story.append(Spacer(1, 3 * mm))

    # --- Client / account ---
    story.append(_section("Client Information"))
    product = (score.score_breakdown or {}).get("product", "—")
    story.append(_kv_table([
        ("Client name", statement.account_holder or "—"),
        ("National ID", statement.national_id or "—"),
        ("Account number", statement.account_number or "—"),
        ("Phone", statement.phone_number or "—"),
        ("Product", str(product).replace("_", " ").title()),
        ("Statement period", statement.statement_period or "—"),
        ("Extraction method", statement.extraction_method or "—"),
    ]))
    story.append(Spacer(1, 3 * mm))

    # --- Monthly financial reconciliation ---
    summary = score.financial_summary or {}
    monthly = summary.get("monthly_detail") or {}
    if monthly.get("rows"):
        story.append(_section("Client Financial Summary"))
        story.append(_monthly_table(monthly))
        contra_total = summary.get("behaviour", {}).get("contra_total", 0)
        contra_count = summary.get("behaviour", {}).get("contra_count", 0)
        if contra_count:
            story.append(Spacer(1, 2 * mm))
            story.append(Paragraph(
                f"<i>Contra entries excluded from the above: {contra_count} self-transfer(s), "
                f"totaling {_money(contra_total)}.</i>", _styles["Footer"],
            ))
        story.append(Spacer(1, 3 * mm))

    # --- Score card data ---
    story.append(_section("Score Card Data"))
    breakdown = score.score_breakdown or {}
    story.append(_kv_table([
        ("Avg monthly income (qualifying)", _money(score.avg_monthly_income)),
        ("DTI %", f"{score.dti_pct:.0%}" if score.dti_pct is not None else "—"),
        ("CRB obligation", _money(breakdown.get("crb_obligation", 0))),
        ("Qualified amount (DTI − CRB)", _money(breakdown.get("qualified_amount", 0))),
        ("Statement months", f"{score.month_count:.2f}" if score.month_count is not None else "—"),
        ("Needs review", "Yes" if statement.needs_review else "No"),
    ]))
    story.append(Spacer(1, 3 * mm))

    # --- Score reasons (transparency) ---
    story.append(_section("Score Reasons"))
    reason_rows = [[Paragraph("<b>Rule</b>", _styles["Cell"]), Paragraph("<b>Points</b>", _styles["Cell"]),
                    Paragraph("<b>Reason</b>", _styles["Cell"])]]
    for rc in (score.reason_codes or [])[:16]:
        pts = rc.get("points", 0)
        pts_str = f"+{pts}" if pts > 0 else str(pts)
        reason_rows.append([
            Paragraph(rc.get("code", ""), _styles["Cell"]),
            Paragraph(pts_str, _styles["Cell"]),
            Paragraph(f"{rc.get('reason', '')} <font color='#6B7280'>({rc.get('detail', '')})</font>", _styles["Cell"]),
        ])
    rt = Table(reason_rows, colWidths=(32 * mm, 16 * mm, 112 * mm), repeatRows=1)
    rt.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), _HEADER_TEXT),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _LIGHT]),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#DDDAE8")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#B9B3DC")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story += [rt, Spacer(1, 3 * mm)]

    # --- Flagged transactions (every flag ships with its reason) ---
    flagged_table = _flagged_transactions_table(statement)
    if flagged_table is not None:
        n_flagged = sum(1 for t in statement.transactions if t.is_flagged)
        story.append(KeepTogether([
            _section(f"Flagged Transactions ({n_flagged})"),
            Paragraph(
                "Every flagged transaction below traces to a specific rule — self-transfer between the "
                "client's own accounts, a one-off amount outside their normal pattern, or a distress "
                "keyword in the description. Flags route items to review; they do not by themselves fail "
                "the score.", _styles["Footer"],
            ),
            Spacer(1, 2 * mm),
        ]))
        story.append(flagged_table)
        if n_flagged > 40:
            story.append(Paragraph(f"<i>Showing the first 40 of {n_flagged} flagged transactions — "
                                    "see the Excel export for the full list.</i>", _styles["Footer"]))
        story.append(Spacer(1, 3 * mm))

    # --- Authenticity / fraud check ---
    fraud = score.fraud_data or {}
    story.append(_section("Authenticity Check"))
    story.append(_kv_table([
        ("Risk score", f"{fraud.get('risk_score', '—')} / 100"),
        ("Risk level", str(fraud.get("risk_level", "—")).upper()),
        ("Signals", "; ".join(fraud.get("reasons", [])[:4]) or "No tampering signals detected."),
    ]))

    story.append(Spacer(1, 4 * mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#DDDAE8")))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        f"Generated by {settings.app_name} on {datetime.now(timezone.utc).strftime('%d %b %Y %H:%M UTC')}. "
        "Score is derived from a transparent, rule-based engine — every point and every flag traces to a "
        "documented rule. Figures are based on submitted statement data and subject to verification.",
        _styles["Footer"],
    ))

    doc.build(story)
    return path
