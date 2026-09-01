# Credit Yetu

**Transparent credit scoring, explained.**

Credit Yetu is a backend that turns an M-Pesa, bank, or SACCO statement into a
credit score — but the whole point of the project is *why* it gave that score.
Every point on the scorecard traces back to a documented rule a credit analyst
can read in plain English. No black box, no "trust the model."

That matters because the usual failure mode in credit scoring isn't a bad
score — it's a score nobody can explain, and a financial summary that misses
the details the credit team actually needed to make the call. Credit Yetu is
built to close both gaps at once: extract every transaction (even from a
scanned, photographed, or oddly-formatted statement), reconcile it into a
proper financial summary, and score it with rules a human can audit line by
line.

## Contents

- [What it does](#what-it-does)
- [Why it's built this way](#why-its-built-this-way)
- [ML shadow-scoring](#ml-shadow-scoring)
- [Architecture](#architecture)
- [Quick start](#quick-start)
- [Usage](#usage)
- [Endpoints](#endpoints)
- [The scorecard PDF and Excel export](#the-scorecard-pdf-and-excel-export)
- [Swapping the mock KYC provider for a real one](#swapping-the-mock-kyc-provider-for-a-real-one)
- [Security notes](#security-notes)
- [Tested](#tested)

## What it does

- **Extracts every transaction, however the statement is laid out.** Text-native
  PDFs go through deterministic parsing (pdfplumber); scanned or photographed
  statements fall back to OCR (Tesseract). A reconciliation pass recovers any
  row the table parser missed, so nothing silently drops out.
- **Classifies every transaction** as normal, loan, contra (a transfer between
  the client's own accounts), or a one-off outlier — plus a spending/income
  category (Fuliza, M-Shwari, betting, airtime, salary, utilities, P2P…).
  Anything flagged always comes with a plain-English reason.
- **Builds the financial summary credit teams actually need** — the piece a
  bare score usually skips: totals, per-category in/out, a month-by-month
  Credits/Loans/Outliers/Net reconciliation table, and balance trends. It's
  derived straight from the same classified transactions the score uses, so
  the two can never disagree.
- **Checks the statement's own authenticity.** PDF metadata signatures,
  running-balance reconciliation, and Benford's-law digit analysis combine
  into a risk score that routes a statement to manual review — it never
  auto-declines on its own.
- **Scores transparently.** A base score adjusted by isolated, individually
  auditable rules, each worth a documented number of points with its own
  reason code; a DTI-based loan limit (product-specific) net of any CRB
  obligation; grade bands from D to AA.
- **Generates a branded PDF scorecard and Excel workbook** from that same
  persisted data — see [below](#the-scorecard-pdf-and-excel-export).
- **Covers the full identity/KYC/CRB surface** (IPRS, passport, face match, KRA
  PIN, alien ID, Metropol, Creditinfo, phone hakikisha, bank account, M-Pesa
  KYC, sim swap, phone search, full KYC, employer, business, driving licence)
  behind one swappable provider interface. Ships with a clearly-labelled
  **sandbox mock** so the whole system runs end-to-end today; plugging in a
  real provider later is a one-line config change, not a rewrite.

## Why it's built this way

1. **The rule engine decides, not a black box.** `credit_score`, `grade`, and
   the loan limit always come from the transparent rule engine — never from a
   classifier quoting a made-up accuracy figure. Manufacturing that kind of
   false confidence is exactly what erodes a credit team's trust in scoring
   in the first place. (See [ML shadow-scoring](#ml-shadow-scoring) for how a
   real, honestly-evaluated model still fits in without compromising this.)
2. **Real identity/CRB data sources are gated, honestly.** IPRS, Metropol,
   Creditinfo, Safaricom, KRA, and BRS all require signed contracts — and
   often regulated-entity status — before they'll return real data. They sit
   behind one `IdentityProvider` interface; the sandbox implementation always
   marks its output `"sandbox": true` so it can never be mistaken for the
   real thing. If a provider is selected but not actually implemented yet,
   the registry raises a clear error rather than quietly faking a response.

## ML shadow-scoring

`credit_score` is, and stays, the rule engine's output. But "should we
eventually use a trained model?" deserves a real answer rather than either
extreme — quoting a made-up accuracy, or refusing to ever measure one — so
there's a second, **non-authoritative** track:

1. **Record real outcomes.** Once a loan issued off a scored statement
   matures, `POST /api/v1/ml/outcomes/{reference_id}` with
   `outcome: repaid|delinquent|defaulted` (or `current` while still active).
   This is the *only* source of labels anywhere in the codebase — there is no
   synthetic or proxy data used to train anything.
2. **Train once there's enough signal.** `POST /api/v1/ml/train` builds a
   feature vector per statement from the same financial summary the rule
   engine already computed (deliberately excluding the rule score itself, so
   the model reflects the underlying signals rather than a copy of the
   rules), fits both a `LogisticRegression` baseline and a
   `HistGradientBoostingClassifier`, and reports **real** accuracy /
   precision / recall / F1 / ROC-AUC / KS-statistic on a held-out test split.
   Training is refused — with a clear explanation, never a fabricated number —
   below `ML_MIN_SAMPLES` (default 40) labeled outcomes, or fewer than 8
   examples of the rarer class. `GET /api/v1/ml/status` shows labeling
   progress; `GET /api/v1/ml/models` is the full audit trail of every
   training run, promoted or not.
3. **Shadow, don't decide.** Once a model clears that bar it's marked
   `shadow`, and every `.../score` response gains a non-authoritative
   `ml_shadow` block (`probability_of_default`, the model version, its test
   metrics) purely for monitoring and calibration. `credit_score`, `grade`,
   and the loan limit are computed *before* `ml_shadow` is even looked up.

Promoting a shadow model to actually influence scoring is a deliberate future
step — versioned, documented, reversible — once its track record earns it.
Nothing in this codebase does that automatically.

## Architecture

```
app/
  main.py                 FastAPI app, CORS, exception handlers, health/config
  config.py               env-driven settings          database.py  SQLAlchemy engine/session
  core/                   security (API keys), response & error envelopes
  models/                 Organization/ApiKey, Customer, Statement/Transaction/Score,
                           Verification/Audit, LoanOutcome/MLModelVersion
  schemas.py              Pydantic request models
  api/
    deps.py               Bearer API-key auth -> Organization
    v1/                   auth, customers, statements, transactions, verification, business, ml
  services/
    extraction/           triage, patterns, mpesa_parser, bank_parser, ocr_parser, engine, ordering
    classification/       keywords, classifier (contra/loan/outlier/category, distress signals)
    summary/              financial_summary  (the credit-team gap-closer)
    fraud/                forensics (metadata / balance / Benford)
    scoring/               reason_codes, rules, engine (transparent, DTI limit) — authoritative
    ml/                    features, train (logreg + HistGradientBoosting, real metrics), shadow (inference)
    kyc/                   base (ABC), mock_provider (sandbox), registry
    reporting/              pdf_report (reportlab + gauge), excel_report (openpyxl), fonts (Consolas)
    pipeline.py            orchestration: extract -> classify -> summary -> fraud -> score -> reports -> callback
migrations/               0001_init.sql, 0002_ml_shadow_scoring.sql
scripts/                  init_db, sample-statement generator, train_model (CLI for ml.train)
```

Requires **Python 3.11 or 3.12** (scikit-learn/numpy wheels aren't published
for 3.14 on every platform yet; 3.14 fails at `pip install`, not at runtime).

Processing runs as a **FastAPI background task** by default (no extra infra
needed); set `TASK_BACKEND=celery` and point a Celery task at
`pipeline.process_statement` for a real queue.

## Quick start

```bash
# 1. Python deps
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. System deps for OCR (optional but recommended for scanned statements)
#    Ubuntu/Debian:
sudo apt-get install -y tesseract-ocr poppler-utils
#    macOS:
brew install tesseract poppler

# 3. Postgres (Docker)
docker compose up -d db

# 4. Config
cp .env.example .env
#   then edit DATABASE_URL, SECRET_KEY, API_KEY_PEPPER
#   using a managed/shared Postgres instance? see the DATABASE_URL comments
#   in .env.example for the schema + connection-pool-size guidance

# 5. Create tables
python -m scripts.init_db          # or: psql "$DATABASE_URL" -f migrations/0001_init.sql -f migrations/0002_ml_shadow_scoring.sql

# 6. Run
uvicorn app.main:app --reload
#   Interactive docs at http://localhost:8000/docs
```

## Usage

```bash
# Create an organization + first API key (key is shown once)
curl -X POST localhost:8000/api/v1/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"name":"Acme Capital","email":"ops@acmecapital.co","account_type":"business"}'

KEY=pk_test_...   # from the response

# Upload a statement (async -> returns a reference_id)
curl -X POST localhost:8000/api/v1/statements/upload \
  -H "Authorization: Bearer $KEY" \
  -F "file=@statement.pdf" -F "statement_type=mpesa" \
  -F "national_id=12345678" -F "product=employed" -F "passcode="

# Poll status, then fetch results
curl -H "Authorization: Bearer $KEY" localhost:8000/api/v1/statements/<reference_id>
curl -H "Authorization: Bearer $KEY" localhost:8000/api/v1/statements/<reference_id>/score
curl -H "Authorization: Bearer $KEY" localhost:8000/api/v1/statements/<reference_id>/summary
curl -H "Authorization: Bearer $KEY" localhost:8000/api/v1/statements/<reference_id>/report/pdf -o scorecard.pdf

# Score already-parsed transactions synchronously (no upload)
curl -X POST localhost:8000/api/v1/transactions/score \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"product":"personal","transactions":[{"date":"2024-01-05","description":"Salary","paid_in":85000}]}'

# A KYC check (consent is mandatory)
curl -X POST localhost:8000/api/v1/verify/crb/metropol \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"identifier":"12345678","full":true,"consent":true,"consent_collected_by":"loan officer J. Doe"}'

# Look up any past verification result by its reference_id
curl -H "Authorization: Bearer $KEY" localhost:8000/api/v1/verify/<reference_id>
```

## Endpoints

Auth is a Bearer API key on everything except signup and the meta routes.

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/auth/signup` | Create org (personal/business) + first key |
| POST | `/api/v1/auth/api-keys` | Mint another API key |
| GET  | `/api/v1/auth/me` | Current org |
| POST/GET | `/api/v1/customers` | Register / list customers |
| GET  | `/api/v1/customers/{national_id}` | Fetch a customer |
| POST | `/api/v1/statements/upload` | Upload statement (async scoring) |
| GET  | `/api/v1/statements/{ref}` | Processing status |
| GET  | `/api/v1/statements/{ref}/score` | Score + reason codes + fraud |
| GET  | `/api/v1/statements/{ref}/summary` | Full financial summary |
| GET  | `/api/v1/statements/{ref}/transactions` | Classified transactions |
| GET  | `/api/v1/statements/{ref}/report/{pdf,excel}` | Download reports |
| POST | `/api/v1/transactions/score` | Score pre-parsed transactions |
| POST | `/api/v1/verify/identity` · `/passport` · `/kra-pin` · `/alien-id` · `/driving-licence` | Identity checks |
| POST | `/api/v1/verify/crb/metropol` · `/crb/creditinfo` | CRB checks |
| POST | `/api/v1/verify/phone/hakikisha` · `/mpesa-kyc` · `/sim-swap` · `/phone-search` | Telco checks |
| POST | `/api/v1/verify/bank-account` · `/full-kyc` · `/employer` · `/face-match` | Bank / composite |
| GET  | `/api/v1/verify/{reference_id}` | Fetch a past verification result (any check type, incl. `/business/verify`'s) |
| POST | `/api/v1/business/verify` | Business (SME) registration lookup |
| POST | `/api/v1/ml/outcomes/{ref}` · `/ml/train` | Record a loan outcome; (re)train the shadow model |
| GET  | `/api/v1/ml/status` · `/ml/models` | Labeling progress; full training audit trail |
| GET  | `/health` · `/config` · `/` | Meta |

## The scorecard PDF and Excel export

Both are rendered straight from the same persisted score/summary/fraud data —
never a separate computation — so neither can ever disagree with the API
response or with each other.

- **PDF** (`app/services/reporting/pdf_report.py`): a two-page scorecard —
  client info, a semicircular score gauge (banded Poor → Excellent, needle on
  the client's actual score), the month-by-month financial reconciliation
  table, the full list of scoring reasons, every flagged transaction with its
  reason, and the authenticity check. Set in **Consolas** where a licensed
  copy is available on the machine generating the report (it's a commercial
  Microsoft font, never bundled with this project); falls back to Courier
  automatically otherwise, so report generation never breaks over a missing
  font.
- **Excel** (`app/services/reporting/excel_report.py`): three sheets —
  Summary, Monthly Detail (the same reconciliation table), and every
  transaction with its classification, flagged rows highlighted with a
  filter enabled.

## Swapping the mock KYC provider for a real one

1. Implement `app/services/kyc/base.IdentityProvider` in a new module, calling
   the upstream API with `httpx` and your `KYC_API_KEY` / `KYC_BASE_URL`.
2. Register it in `app/services/kyc/registry._PROVIDERS`.
3. Set `KYC_PROVIDER=<name>` in `.env`. No endpoint or application code
   changes needed.

The registry's `_NotConfiguredProvider` raises a clear error if a provider is
selected but not implemented — so nothing ever ships believing a real
integration exists when it doesn't.

## Security notes

- API keys are shown once; only a **peppered SHA-256 hash** is stored;
  verification is constant-time.
- All borrower checks require explicit `consent` + `consent_collected_by`,
  persisted on every `Verification` row — and every result is fetchable
  later, org-scoped, via `GET /api/v1/verify/{reference_id}`.
- Uploads are size-limited and extension-checked.
- The database connection pool is deliberately small (`DB_POOL_SIZE` /
  `DB_MAX_OVERFLOW`, default 5 + 5) — on a shared/managed Postgres instance
  with a low `max_connections`, this app alone won't exhaust it.
- Set a strong `SECRET_KEY` / `API_KEY_PEPPER`, explicit `CORS_ORIGINS`, and
  put file storage behind an object store (add a storage adapter) before
  production.

## Tested

Verified two ways:

- `scripts/make_sample_mpesa.py` generates a realistic synthetic statement;
  the full pipeline (extraction → classification → summary → fraud → scoring
  → PDF/Excel) runs end-to-end on it, and every module compiles and imports
  cleanly.
- The full stack — upload through a real bank statement, scoring, report
  generation, and every identity/KYC/CRB endpoint — has also been run
  end-to-end against a real Postgres instance over the network (not just
  SQLite/local), including the security checks (missing/invalid API key,
  cross-organization data isolation, consent enforcement).
