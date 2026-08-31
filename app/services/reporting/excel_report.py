"""Two-sheet financial-summary Excel export.

Sheet 1 (Summary): headline figures, category totals and monthly trends.
Sheet 2 (Transactions): every extracted transaction with its classification.

This is the reconciliation artefact the credit team asked for — and a usable
fallback when the scorecard PDF is slow or fails, because it's generated
independently from the same persisted data.
"""
from __future__ import annotations

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from app.config import settings

_HEADER_FILL = PatternFill("solid", fgColor="3B2F8F")
_HEADER_FONT = Font(color="FFFFFF", bold=True)
_TITLE_FONT = Font(bold=True, size=13)


def _style_header(ws, row: int, ncols: int) -> None:
    for c in range(1, ncols + 1):
        cell = ws.cell(row=row, column=c)
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
        cell.alignment = Alignment(horizontal="center")


def _autosize(ws, max_width: int = 60) -> None:
    for col in ws.columns:
        length = max((len(str(c.value)) for c in col if c.value is not None), default=10)
        ws.column_dimensions[get_column_letter(col[0].column)].width = min(length + 2, max_width)


def build_financial_workbook(statement, score) -> str:
    summary = score.financial_summary or {}
    out_dir = settings.storage_path / "reports"
    path = str(out_dir / f"financial_summary_{statement.reference_id}.xlsx")

    wb = Workbook()

    # ---- Summary sheet ----
    ws = wb.active
    ws.title = "Summary"
    ws["A1"] = "Financial Summary"
    ws["A1"].font = _TITLE_FONT
    ws["A2"] = f"Reference: {statement.reference_id}"
    ws["A3"] = f"Account holder: {statement.account_holder or '—'}"
    ws["A4"] = f"Credit score: {score.credit_score}  |  Grade: {score.grade}  |  Limit: {score.limit_low:,.0f}–{score.limit_high:,.0f}"

    row = 6
    ws.cell(row=row, column=1, value="Metric")
    ws.cell(row=row, column=2, value="Value")
    _style_header(ws, row, 2)
    row += 1

    def put(label: str, value) -> None:
        nonlocal row
        ws.cell(row=row, column=1, value=label)
        ws.cell(row=row, column=2, value=value)
        row += 1

    totals = summary.get("totals", {})
    behaviour = summary.get("behaviour", {})
    lending = summary.get("lending", {})
    period = summary.get("period", {})
    for label, value in [
        ("Total received", totals.get("total_received", 0)),
        ("Total sent", totals.get("total_sent", 0)),
        ("Net position", totals.get("net_position", 0)),
        ("Transaction count", totals.get("transaction_count", 0)),
        ("Avg credit", totals.get("avg_credit", 0)),
        ("Avg debit", totals.get("avg_debit", 0)),
        ("Loan received total", lending.get("loan_received_total", 0)),
        ("Loan repaid total", lending.get("loan_repaid_total", 0)),
        ("Fuliza out", lending.get("fuliza_out", 0)),
        ("Betting out", behaviour.get("betting_out", 0)),
        ("Salary in", behaviour.get("salary_in", 0)),
        ("P2P received", behaviour.get("p2p_received", 0)),
        ("P2P sent", behaviour.get("p2p_sent", 0)),
        ("Expenses-to-income", behaviour.get("expenses_to_income", 0)),
        ("Statement months", period.get("statement_months", 0)),
        ("Active months", period.get("active_months", 0)),
    ]:
        put(label, value)

    # Category block.
    row += 1
    ws.cell(row=row, column=1, value="Category")
    ws.cell(row=row, column=2, value="In")
    ws.cell(row=row, column=3, value="Out")
    ws.cell(row=row, column=4, value="Count")
    _style_header(ws, row, 4)
    row += 1
    for cat, vals in (summary.get("categories") or {}).items():
        ws.cell(row=row, column=1, value=cat)
        ws.cell(row=row, column=2, value=vals.get("in", 0))
        ws.cell(row=row, column=3, value=vals.get("out", 0))
        ws.cell(row=row, column=4, value=vals.get("count", 0))
        row += 1

    # Monthly trends block.
    row += 1
    ws.cell(row=row, column=1, value="Month")
    ws.cell(row=row, column=2, value="Received")
    ws.cell(row=row, column=3, value="Sent")
    ws.cell(row=row, column=4, value="Closing balance")
    _style_header(ws, row, 4)
    row += 1
    trends = summary.get("trends", {})
    months = sorted(set(trends.get("received", {})) | set(trends.get("sent", {})) | set(trends.get("balance", {})))
    for m in months:
        ws.cell(row=row, column=1, value=m)
        ws.cell(row=row, column=2, value=trends.get("received", {}).get(m, 0))
        ws.cell(row=row, column=3, value=trends.get("sent", {}).get(m, 0))
        ws.cell(row=row, column=4, value=trends.get("balance", {}).get(m))
        row += 1

    _autosize(ws)

    # ---- Transactions sheet ----
    tx = wb.create_sheet("Transactions")
    headers = ["Date", "Reference", "Description", "Paid In", "Withdrawn", "Balance", "Label", "Category", "Flag reason"]
    tx.append(headers)
    _style_header(tx, 1, len(headers))
    for t in statement.transactions:
        tx.append([
            t.transaction_datetime.isoformat() if t.transaction_datetime else "",
            t.transaction_ref or "",
            t.description or "",
            t.paid_in,
            t.withdrawn,
            t.balance,
            t.label,
            t.category or "",
            t.flag_reason or "",
        ])
    tx.freeze_panes = "A2"
    _autosize(tx)

    wb.save(path)
    return path
