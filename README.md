# Credit Scoring API

A backend for scoring personal and SME creditworthiness from **M-Pesa / bank /
SACCO statements**, built around one principle: **every number is explainable**.
The score is produced by a transparent, rule-based engine — not a black-box
model with a headline accuracy figure — so a credit analyst can trace any point,
flag, or decline back to a documented rule. That auditability is the whole point.

## What it does

- **Statement extraction that leaves nothing out.** Triage → deterministic
  text/table parsing (pdfplumber) → OCR fallback (Tesseract) for scanned or
  photographed statements, with a line-level reconciliation pass that recovers
  any transaction the table parser missed.
- **Transaction classification.** Loan / contra (self-transfer) / outlier
  labelling plus category tagging (Fuliza, M-Shwari, KCB M-Pesa, betting,
  airtime, salary, utilities, agent, P2P…), all via auditable keyword and IQR
  rules.
- **A comprehensive financial summary** — the piece credit teams say the current
  scorecard misses: headline totals, per-category in/out (full + trailing 6-month
  window), lending behaviour, and monthly received/sent/balance trends. Derived
  straight from the classified transactions, so it can never drift from the score.
- **Fraud / tampering forensics.** PDF metadata signatures, running-balance
  reconciliation, and Benford's-law digit analysis → a risk score that routes to
  **manual review**, never an automatic decline.
- **Transparent scoring.** A base score adjusted by isolated, pure-function rules,
  each emitting points + a reason code; DTI-based limit (product-specific) net of
  any CRB obligation; grade bands AA–D.
- **PDF scorecard + Excel workbook** generated from the same persisted data.
- **KYC / CRB adapter** with the full identity surface (IPRS, passport, face
  match, KRA PIN, alien ID, Metropol, Creditinfo, phone hakikisha, bank account,
  M-Pesa KYC, sim swap, phone search, full KYC, employer, business, driving
  licence) behind a swappable provider. Ships with a clearly-labelled **sandbox
  mock**; drop in a real provider with one config change.

## Two deliberate design decisions

1. **No fabricated ML metrics as the decision-maker.** `credit_score`, `grade` and
   the loan limit always come from the transparent rule engine, never from a
   classifier reporting a made-up F1/accuracy. Manufacturing that false confidence
   is precisely what erodes credit-team trust. See **ML shadow-scoring** below for
   how a real, honestly-evaluated model still fits into this without compromising it.
2. **Real identity/CRB sources are gated.** IPRS, Metropol, Creditinfo, Safaricom,
   KRA and BRS require signed contracts (and often regulated-entity status). They
   live behind `IdentityProvider`; the sandbox provider returns synthetic data that
   always carries `"sandbox": true`. Swapping to production is a config change,
   not a rewrite — and the registry refuses to silently fake a "real" provider.

## ML shadow-scoring

`credit_score` is, and stays, the rule engine's output. But "should we eventually
use a trained model?" deserves a real, honest answer rather than either extreme
(quoting a made-up accuracy, or refusing to ever measure one) — so there's a
second, **non-authoritative** track:

1. **Record real outcomes.** Once a loan issued off a scored statement matures,
   `POST /api/v1/ml/outcomes/{reference_id}` with `outcome: repaid|delinquent|defaulted`
   (or `current` while still active). This is the *only* source of labels anywhere
   in this codebase — no synthetic or proxy data is ever used to train anything.
2. **Train once there's enough signal.** `POST /api/v1/ml/train` builds a feature
   vector per statement from the same `financial_summary` the rule engine already
   computed (deliberately excluding the rule score itself, so the model reflects
   the underlying signals, not a copy of the rules), fits both a
   `LogisticRegression` baseline (the industry's usual interpretable default) and
   a `HistGradientBoostingClassifier`, and reports **real** accuracy / precision /
   recall / F1 / ROC-AUC / KS-statistic on a held-out test split for both. Training
   is refused — with a clear reason, not a fake number — below
   `ML_MIN_SAMPLES` (default 40) labeled final outcomes, or fewer than 8 examples
   of the rarer class. `GET /api/v1/ml/status` shows labeling progress;
   `GET /api/v1/ml/models` is the full audit trail of every run, promoted or not.
3. **Shadow, don't decide.** Once a model clears that bar it's marked `shadow` and
   every `.../score` response gains a `ml_shadow` block (`probability_of_default`,
   the model version, its test metrics) purely for monitoring/calibration.
   `credit_score`, `grade` and the loan limit are computed before `ml_shadow` is
   even looked up and never read it back.

Promoting a shadow model to actually influence scoring is a deliberate future
step (versioned, documented, reversible) once its track record earns it — not
something this codebase does automatically.

## Architecture

```
app/
  main.py                 FastAPI app, CORS, exception handlers, health/config
  config.py               env-driven settings          database.py  SQLAlchemy engine/session
  core/                   security (API keys), response & error envelopes
  models/                 Organization/ApiKey, Customer, Statement/Transaction/Score, Verification/Audit
  schemas.py              Pydantic request models
  api/
    deps.py               Bearer API-key auth -> Organization
    v1/                   auth, customers, statements, transactions, verification, business
  services/
    extraction/           triage, patterns, mpesa_parser, bank_parser, ocr_parser, engine
    classification/       keywords, classifier (contra/loan/outlier/category)
    summary/              financial_summary  (the credit-team gap-closer)
    fraud/                forensics (metadata / balance / Benford)
    scoring/              reason_codes, rules, engine (transparent, DTI limit) — authoritative
    ml/                   features, train (logreg + HistGradientBoosting, real metrics), shadow (inference)
    kyc/                  base (ABC), mock_provider (sandbox), registry
    reporting/           pdf_report (reportlab), excel_report (openpyxl)
    pipeline.py           orchestration: extract -> classify -> summary -> fraud -> score -> reports -> callback
migrations/               0001_init.sql, 0002_ml_shadow_scoring.sql
scripts/                  init_db, sample-statement generator, train_model (CLI for ml.train)
```

Requires **Python 3.11 or 3.12** (scikit-learn/numpy wheels aren't yet published
for 3.14 on every platform; 3.14 will fail at `pip install`, not at runtime).

Processing runs as a **FastAPI background task** by default (no extra infra);
set `TASK_BACKEND=celery` and point a Celery task at `pipeline.process_statement`
for a real queue.

## Quick start

```bash
# 1. Python deps
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. System deps for OCR (optional but recommended for scanned statements)
#    Ubuntu/Debian:
sudo apt-get install -y tesseract-ocr poppler-utils

# 3. Postgres (Docker)
docker compose up -d db

# 4. Config
cp .env.example .env
#   then edit DATABASE_URL, SECRET_KEY, API_KEY_PEPPER

# 5. Create tables
python -m scripts.init_db          # or: psql "$DATABASE_URL" -f migrations/0001_init.sql -f migrations/0002_ml_shadow_scoring.sql
#    Targeting a non-`public` schema on a shared/managed instance? Table names
#    in both the ORM and the raw SQL are unqualified — just point DATABASE_URL's
#    search_path at your schema (see .env.example) and either approach lands
#    everything there automatically, with zero code changes.

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
| POST | `/api/v1/business/verify` | Business (SME) registration lookup |
| GET  | `/health` · `/config` · `/` | Meta |

## Swapping the mock KYC provider for a real one

1. Implement `app/services/kyc/base.IdentityProvider` in a new module, calling the
   upstream API with `httpx` and your `KYC_API_KEY` / `KYC_BASE_URL`.
2. Register it in `app/services/kyc/registry._PROVIDERS`.
3. Set `KYC_PROVIDER=<name>` in `.env`. No endpoint or application code changes.

The registry's `_NotConfiguredProvider` raises a clear error if a provider is
selected but not implemented — so nothing ever ships believing a real integration
exists when it doesn't.

## Security notes

- API keys are shown once; only a **peppered SHA-256 hash** is stored; verification
  is constant-time.
- All borrower checks require explicit `consent` + `consent_collected_by`, persisted
  on every `Verification` row.
- Uploads are size-limited and extension-checked.
- Set strong `SECRET_KEY` / `API_KEY_PEPPER`, explicit `CORS_ORIGINS`, and put file
  storage behind an object store (add a storage adapter) before production.

## Tested

`scripts/make_sample_mpesa.py` generates a realistic statement; the full service
pipeline (extraction → classification → summary → fraud → scoring → PDF/Excel) has
been verified end-to-end on it, and every module compiles and imports cleanly.
