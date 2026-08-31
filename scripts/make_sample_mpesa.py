"""Generate a realistic text-native M-Pesa statement PDF for testing."""
from __future__ import annotations

import sys

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet

ROWS = [
    # receipt, datetime, details, status, paid_in, withdrawn, balance
    ("RA11AA001", "2024-01-05 09:12:33", "Salary from ACME LTD PAYROLL", "Completed", "85,000.00", "", "86,200.00"),
    ("RA11AA002", "2024-01-06 18:03:10", "Pay Bill to KPLC TOKEN", "Completed", "", "1,500.00", "84,700.00"),
    ("RA11AA003", "2024-01-08 20:41:55", "Buy Goods SPORTPESA BET", "Completed", "", "2,000.00", "82,700.00"),
    ("RA11AA004", "2024-01-12 07:22:01", "Customer Transfer to 254712345678", "Completed", "", "5,000.00", "77,700.00"),
    ("RA11AA005", "2024-01-15 12:15:44", "M-Shwari Withdraw", "Completed", "3,000.00", "", "80,700.00"),
    ("RA11AA006", "2024-01-20 16:50:12", "Fuliza M-Pesa charge", "Completed", "", "450.00", "80,250.00"),
    ("RA11AA007", "2024-01-25 11:05:33", "Airtime Purchase", "Completed", "", "500.00", "79,750.00"),
    ("RA11AA008", "2024-02-05 09:14:02", "Salary from ACME LTD PAYROLL", "Completed", "85,000.00", "", "164,750.00"),
    ("RA11AA009", "2024-02-07 19:22:41", "Agent Withdrawal 555555", "Completed", "", "10,000.00", "154,750.00"),
    ("RA11AA010", "2024-02-10 13:00:00", "KCB M-PESA Loan Disbursement", "Completed", "20,000.00", "", "174,750.00"),
    ("RA11AA011", "2024-02-14 21:33:19", "Buy Goods BETIKA", "Completed", "", "1,500.00", "173,250.00"),
    ("RA11AA012", "2024-02-18 08:45:00", "Pay Bill to ZUKU FIBER", "Completed", "", "3,499.00", "169,751.00"),
    ("RA11AA013", "2024-02-22 10:10:10", "KCB M-PESA Loan Repayment", "Completed", "", "20,500.00", "149,251.00"),
    ("RA11AA014", "2024-02-27 17:05:23", "Customer Transfer from JOHN DOE", "Completed", "4,000.00", "", "153,251.00"),
    ("RA11AA015", "2024-03-05 09:10:11", "Salary from ACME LTD PAYROLL", "Completed", "85,000.00", "", "238,251.00"),
    ("RA11AA016", "2024-03-08 20:00:00", "Fuliza M-Pesa", "Completed", "", "1,200.00", "237,051.00"),
    ("RA11AA017", "2024-03-12 14:23:00", "M-Shwari Lock Savings Deposit", "Completed", "", "15,000.00", "222,051.00"),
    ("RA11AA018", "2024-03-15 19:45:33", "Buy Goods ODIBET", "Completed", "", "3,000.00", "219,051.00"),
    ("RA11AA019", "2024-03-20 08:00:00", "Agent Withdrawal 555555", "Completed", "", "8,000.00", "211,051.00"),
    ("RA11AA020", "2024-03-28 12:12:12", "Pay Bill to NAIROBI WATER", "Completed", "", "2,300.00", "208,751.00"),
]


def build(path: str) -> None:
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(path, pagesize=A4, topMargin=15 * mm, bottomMargin=15 * mm)
    story = [
        Paragraph("<b>M-PESA STATEMENT</b>", styles["Title"]),
        Paragraph("Customer Name: JOHN DOE", styles["Normal"]),
        Paragraph("Mobile Number: 254712345678", styles["Normal"]),
        Paragraph("Statement Period: 2024-01-01 - 2024-03-31", styles["Normal"]),
        Spacer(1, 6 * mm),
    ]
    header = ["Receipt No.", "Completion Time", "Details", "Transaction Status", "Paid In", "Withdrawn", "Balance"]
    data = [header] + [list(r) for r in ROWS]
    t = Table(data, repeatRows=1, colWidths=[22*mm, 30*mm, 42*mm, 22*mm, 20*mm, 20*mm, 22*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0A7D32")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(t)
    doc.build(story)


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "sample_mpesa.pdf"
    build(out)
    print("Wrote", out)
