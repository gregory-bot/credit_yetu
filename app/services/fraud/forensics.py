"""Statement authenticity checks.

Three independent signals are computed and merged into a single risk score in
[0, 100]. A high score routes the scorecard to manual review — it never
auto-declines, matching the reference system's behaviour.

Signals
-------
1. Metadata forensics  — PDF Producer/Creator strings that reveal an editor
   (iLovePDF, PDFfiller, Photoshop, etc.) on what should be a bank-issued file.
2. Balance reconciliation — for consecutive transactions,
   ``balance[i] ≈ balance[i-1] + paid_in[i] - withdrawn[i]``. Breaks indicate
   inserted/edited/deleted rows.
3. Benford's law — first-digit distribution of transaction amounts vs. the
   expected logarithmic distribution (mean absolute deviation). Fabricated
   amounts tend to deviate.
"""
from __future__ import annotations

import math

from pypdf import PdfReader

from app.services.extraction.models import ExtractedTransaction

_EDITOR_SIGNATURES = (
    "ilovepdf", "pdffiller", "photoshop", "gimp", "canva", "wondershare",
    "smallpdf", "sejda", "foxit phantom", "nitro", "pdfescape", "pdf-xchange editor",
)

_BENFORD_EXPECTED = {d: math.log10(1 + 1 / d) for d in range(1, 10)}


def _metadata_check(path: str) -> tuple[float, list[str]]:
    reasons: list[str] = []
    score = 0.0
    if not path.lower().endswith(".pdf"):
        return 0.0, []
    try:
        meta = PdfReader(path).metadata or {}
    except Exception:  # noqa: BLE001
        return 0.0, []
    blob = " ".join(str(v).lower() for v in meta.values())
    for sig in _EDITOR_SIGNATURES:
        if sig in blob:
            score += 40
            reasons.append(f"PDF metadata references an editor: '{sig}'.")
    return min(score, 60.0), reasons


def _balance_reconciliation(txns: list[ExtractedTransaction]) -> tuple[float, list[str]]:
    seq = [t for t in txns if t.balance is not None]
    if len(seq) < 3:
        return 0.0, []
    breaks = 0
    for prev, cur in zip(seq, seq[1:]):
        expected = (prev.balance or 0) + cur.paid_in - cur.withdrawn
        if abs(expected - (cur.balance or 0)) > 1.0:  # 1 KES tolerance for rounding
            breaks += 1
    ratio = breaks / max(len(seq) - 1, 1)
    reasons: list[str] = []
    score = 0.0
    if ratio > 0.02:
        score = min(60.0, ratio * 200)
        reasons.append(f"{breaks} running-balance discontinuities ({ratio:.0%} of rows).")
    return score, reasons


def _benford_check(txns: list[ExtractedTransaction]) -> tuple[float, list[str]]:
    amounts = [abs(t.paid_in or t.withdrawn) for t in txns if (t.paid_in or t.withdrawn)]
    amounts = [a for a in amounts if a >= 1]
    if len(amounts) < 40:  # Benford is meaningless on small samples
        return 0.0, []
    counts = {d: 0 for d in range(1, 10)}
    for a in amounts:
        lead = int(str(int(a))[0])
        if 1 <= lead <= 9:
            counts[lead] += 1
    n = sum(counts.values())
    mad = sum(abs(counts[d] / n - _BENFORD_EXPECTED[d]) for d in range(1, 10)) / 9
    reasons: list[str] = []
    score = 0.0
    # MAD > ~0.015 is "nonconformity" territory in Benford practice.
    if mad > 0.015:
        score = min(40.0, (mad - 0.015) * 1500)
        reasons.append(f"First-digit distribution deviates from Benford's law (MAD={mad:.3f}).")
    return score, reasons


def analyze(path: str, txns: list[ExtractedTransaction]) -> dict:
    m_score, m_reasons = _metadata_check(path)
    b_score, b_reasons = _balance_reconciliation(txns)
    f_score, f_reasons = _benford_check(txns)

    risk = min(100.0, m_score + b_score + f_score)
    reasons = m_reasons + b_reasons + f_reasons

    if risk >= 70:
        level = "high"
    elif risk >= 35:
        level = "medium"
    else:
        level = "low"

    return {
        "risk_score": round(risk, 1),
        "risk_level": level,
        "flagged": risk >= 35,
        "reasons": reasons or ["No tampering signals detected."],
        "signals": {
            "metadata": round(m_score, 1),
            "balance_reconciliation": round(b_score, 1),
            "benford": round(f_score, 1),
        },
    }
