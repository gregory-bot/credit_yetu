"""Curated keyword lists for transaction classification.

Word-boundary matching is used against these lists (see classifier.py) so that
"loan" doesn't match "Salome" and "bet" doesn't match "Robert". Keep entries
lowercase. This is deliberately transparent and auditable — every tag a
transaction receives traces back to a specific entry here.
"""
from __future__ import annotations

# Digital lenders / credit products (both disbursement and repayment show here).
LOAN_KEYWORDS: tuple[str, ...] = (
    "fuliza", "m-shwari", "mshwari", "kcb m-pesa", "kcb mpesa", "mco-op", "timiza",
    "tala", "branch", "zenka", "okash", "opesa", "stawi", "hustler fund",
    "loan", "overdraft", "credit", "advance", "izwe", "mkopo", "faraja",
    "crb", "listing", "default",
)

# Spending / income categories. Order matters only for readability; matching is
# independent per category.
CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "betting": ("betin", "sportpesa", "betika", "odibet", "1xbet", "mozzart",
                "aviator", "bet ", "shabiki", "gal sport", "melbet"),
    "airtime": ("airtime", "bundle", "bundles", "data", "safaricom offers"),
    "fuliza": ("fuliza",),
    "mshwari": ("m-shwari", "mshwari"),
    "kcb_mpesa": ("kcb m-pesa", "kcb mpesa"),
    "salary": ("salary", "payroll", "wages", "sal ", "remuneration"),
    "utilities": ("kplc", "token", "water", "zuku", "gotv", "dstv", "startimes", "faiba"),
    "merchant": ("buy goods", "till", "pay bill", "paybill", "merchant"),
    "agent": ("withdraw", "agent", "cash out"),
    "transfer": ("customer transfer", "send money", "funds transfer", "sent to", "received from"),
    "savings": ("mshwari lock", "lock savings", "goal savings", "deposit"),
    "remittance": ("western union", "worldremit", "mukuru", "sendwave", "wave remit",
                   "remitly", "moneygram", "diaspora", "swift transfer", "ria money"),
}

# Non-performing / distress signals used to flag individual transactions.
# Deliberately excludes generic "charge"/"fee" — every statement has routine
# service-fee line items (e.g. "IBANKING - MPESA CHARGE") that are not a
# distress signal, and including it flagged ~40% of a real test statement on
# nothing but its own transaction fees. These are specific enough that a
# false-positive rate that high isn't expected.
DISTRESS_KEYWORDS: tuple[str, ...] = (
    "bounced", "insufficient funds", "declined", "failed", "dishonoured", "dishonored",
    "returned cheque", "unpaid cheque", "reversal", "reversed", "penalty",
)
