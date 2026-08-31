"""Render a scorecard PDF with reportlab.

The PDF is a rendered *view* of the same score/summary/fraud data persisted to
the database — never a separate computation — so it can't disagree with the API
response or the Excel export.
"""
from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.config import settings

_ACCENT = colors.HexColor("#3B2F8F")
_LIGHT = colors.HexColor("#F0EEFA")


def _kv_table(rows: list[tuple[str, str]], col_widths=(60 * mm, 100 * mm)) -> Table:
    t = Table([[Paragraph(f"<b>{k}</b>", getSampleStyleSheet()["BodyText"]), v] for k, v in rows], colWidths=col_widths)
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, _LIGHT]),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def build_scorecard_pdf(statement, score) -> str:
    styles = getSampleStyleSheet()
    out_dir = settings.storage_path / "reports"
    path = str(out_dir / f"scorecard_{statement.reference_id}.pdf")

    doc = SimpleDocTemplate(path, pagesize=A4, topMargin=18 * mm, bottomMargin=18 * mm)
    story = []

    title = Paragraph("<b>Credit Scorecard</b>", styles["Title"])
    story += [title, Spacer(1, 4 * mm)]

    story.append(Paragraph(
        f"Reference: {statement.reference_id} &nbsp;&nbsp; "
        f"Statement type: {statement.statement_type.upper()}", styles["Normal"]))
    story.append(Spacer(1, 6 * mm))

    # Headline score band.
    band = Table([[
        Paragraph(f"<font size=28><b>{score.credit_score}</b></font><br/>Credit Score", styles["BodyText"]),
        Paragraph(f"<font size=20><b>{score.grade}</b></font><br/>Grade", styles["BodyText"]),
        Paragraph(f"<font size=14><b>KSh {score.limit_low:,.0f} – {score.limit_high:,.0f}</b></font><br/>Loan Limit", styles["BodyText"]),
    ]], colWidths=(55 * mm, 45 * mm, 70 * mm))
    band.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _LIGHT),
        ("BOX", (0, 0), (-1, -1), 1, _ACCENT),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story += [band, Spacer(1, 8 * mm)]

    # Applicant / account.
    story.append(Paragraph("<b>Account</b>", styles["Heading3"]))
    story.append(_kv_table([
        ("Account holder", str(statement.account_holder or "—")),
        ("National ID", str(statement.national_id or "—")),
        ("Phone", str(statement.phone_number or "—")),
        ("Statement period", str(statement.statement_period or "—")),
        ("Extraction method", str(statement.extraction_method or "—")),
    ]))
    story.append(Spacer(1, 6 * mm))

    # Financial summary highlights.
    summary = score.financial_summary or {}
    totals = summary.get("totals", {})
    behaviour = summary.get("behaviour", {})
    lending = summary.get("lending", {})
    story.append(Paragraph("<b>Financial Summary</b>", styles["Heading3"]))
    story.append(_kv_table([
        ("Total received", f"KSh {totals.get('total_received', 0):,.2f}"),
        ("Total sent", f"KSh {totals.get('total_sent', 0):,.2f}"),
        ("Net position", f"KSh {totals.get('net_position', 0):,.2f}"),
        ("Avg monthly income (qualifying)", f"KSh {score.avg_monthly_income:,.2f}"),
        ("Loans received / repaid", f"KSh {lending.get('loan_received_total', 0):,.0f} / {lending.get('loan_repaid_total', 0):,.0f}"),
        ("Betting spend", f"KSh {behaviour.get('betting_out', 0):,.0f}"),
        ("Expenses-to-income", f"{behaviour.get('expenses_to_income', 0):.2f}"),
        ("Transactions", str(totals.get("transaction_count", 0))),
    ]))
    story.append(Spacer(1, 6 * mm))

    # Score reasons (transparency).
    story.append(Paragraph("<b>Score Reasons</b>", styles["Heading3"]))
    reason_rows = [["Rule", "Points", "Reason"]]
    for rc in (score.reason_codes or [])[:14]:
        reason_rows.append([rc.get("code", ""), str(rc.get("points", 0)), rc.get("reason", "")])
    rt = Table(reason_rows, colWidths=(35 * mm, 18 * mm, 107 * mm))
    rt.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _ACCENT),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _LIGHT]),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story += [rt, Spacer(1, 6 * mm)]

    # Fraud.
    fraud = score.fraud_data or {}
    story.append(Paragraph("<b>Authenticity Check</b>", styles["Heading3"]))
    story.append(_kv_table([
        ("Risk score", str(fraud.get("risk_score", "—"))),
        ("Risk level", str(fraud.get("risk_level", "—"))),
        ("Notes", "; ".join(fraud.get("reasons", [])[:3]) or "—"),
    ]))

    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph(
        "<font size=7 color='grey'>Generated by the Credit Scoring API. "
        "Score is derived from a transparent, rule-based engine; every flagged "
        "item traces to a documented rule.</font>", styles["Normal"]))

    doc.build(story)
    return path
