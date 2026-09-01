# Credit Yetu: Your Loan Edge

i need us build the spin mobile replica... so spin mobile is used for credit.. and we already have the endpoints here... Build a web frontend called "Credit Yetu" — a credit-scoring and identity-verification
platform for loan officers at a lending business. This app is a pure frontend: it
consumes an existing FastAPI REST backend I already have running. Do NOT create your
own backend, database, or auth system (no Supabase auth) — every piece of data comes
from HTTP calls to my API.

====================================================================
CRITICAL: HOW THIS BACKEND'S AUTH ACTUALLY WORKS (read before building sign-up/login)
====================================================================
There is NO username/password login. Authentication is a single Bearer API key:

1. "Create Account" calls POST /api/v1/auth/signup with {name, email, account_type}
   where account_type is "personal" or "business" — this is the Individual vs
   Company toggle. The response includes an `api_key` that is shown EXACTLY ONCE
   and never retrievable again.
2. Every other request sends that key as a header: Authorization: Bearer <api_key>.
3. There is no password-recovery or session endpoint. So:
   - After signup, show the api_key in a prominent "copy this now, it will never
     be shown again" panel, store it in localStorage, and log the user straight in.
   - Also build a separate "Sign In" screen that's just a single field: "Paste your
     API key" — that's the only way a returning user resumes a session. Do not
     invent a password field; it doesn't exist on the backend.
   - Add a "Generate another API key" action (POST /api/v1/auth/api-keys) for
     org admins who need a second key (e.g. for a teammate).

====================================================================
BASE URL & RESPONSE FORMAT
====================================================================
- Base URL: put it in an environment variable (e.g. VITE_API_BASE_URL), default to
  http://localhost:8000 for now — I'll swap in the real deployed URL later.
- EVERY response (success or error) is wrapped:
    success: { "status": 200, "message": "...", "data": <actual payload> }
    error:   { "status": 400, "message": "...", "errors": ["field: reason", ...] }
  Always unwrap `.data` for the real payload, and surface `.message`/`.errors` on
  failures as toast/inline errors.
- Statement upload and face-match are multipart/form-data; everything else is JSON.

====================================================================
DESIGN SYSTEM
====================================================================
Brand: "Credit Yetu" — tagline "Transparent credit scoring, explained."
Reference the layout style of the two screenshots I'm sharing (clean SaaS dashboard:
amber top nav bar with logo + nav links on the right, a bold hero section with a
red primary CTA button on the marketing/home page, then a sidebar-filters +
card-grid dashboard with charts). Match that structure, not the voter-data content.

Color palette (use these exact roles — they mirror the color language already used
in this product's PDF reports, so keep the app visually consistent with them):
  - Amber  #F2A93C  — brand/nav bar, highlighted table headers, "needs review" state
  - Red    #D9382B  — primary CTA buttons, destructive actions, "failed"/high-risk state
  - Green  #2E8B3D  — success state, "scored"/approved, positive deltas
  - Ink    #1F2430  — primary text
  - Muted  #6B7280  — secondary text
  - Backgrounds: white cards on a very light gray (#F7F7F8) page background, subtle
    borders (#E5E5EA), rounded corners (8-12px), soft shadows — matching the reference.
Typography: a clean modern sans-serif for UI text (Inter or system-ui). For scores,
amounts, and reference IDs specifically, use a monospace font (e.g. JetBrains Mono)
as an accent — echoes the monospace styling used in this product's PDF scorecards.

Status color mapping — use this consistently everywhere a statement/verification
has a status, it's the same mapping the backend's own PDF report uses:
  scored / verified / match       -> green
  needs_review / medium risk      -> amber
  failed / high risk / mismatch   -> red

====================================================================
INFORMATION ARCHITECTURE
====================================================================
1. Public marketing home page (hero + "Open Dashboard"/"Get Started" CTA, brief
   feature highlights: transparent scoring, statement extraction, identity
   verification — mirror the reference screenshot's hero layout)
2. /signup — Create Account: name, email, and an Individual/Company toggle
   (maps to account_type: personal/business). Show the API key once on success.
3. /login — "Paste your API key to continue" (see auth section above)
4. /dashboard — Overview: KPI cards (customers, statements processed this month,
   average score, count needing review) + charts (grade distribution donut,
   score distribution bar, monthly upload volume) — sidebar filters by date range
   / product type, matching the reference dashboard's sidebar-filter pattern.
5. /customers — searchable table (name, national ID, phone, entity_type), a
   "New Customer" form (Individual vs Company toggle -> entity_type), and a
   detail view per customer.
6. /statements — upload a new statement (drag-and-drop file, pick statement_type:
   mpesa/bank/till/paybill/sacco, product, optional crb_obligation, optional
   passcode for encrypted PDFs) -> shows a processing state, then polls status
   until scored/needs_review/failed -> statement detail page:
     - Score gauge (semicircular, banded red->amber->green like the reference
       gauge concept, needle on credit_score, 300-900 range, grade shown)
     - "Affordability" range (score_data.affordability.low/high)
     - Breakdown donut (financial_summary category shares) + an "Important
       Ratios" panel (score_breakdown.ratios: debt_to_income, income_volatility,
       betting_to_income, expenses_to_income)
     - Monthly reconciliation table (financial_summary.monthly_detail.rows)
     - Full reason-code list (why the score is what it is)
     - Flagged transactions table, each row showing its flag_reason
     - Authenticity/fraud panel (fraud_data.risk_score/risk_level/reasons)
     - Download buttons for the PDF and Excel reports (GET .../report/pdf,
       .../report/excel — these are file downloads, open in new tab or trigger
       browser download)
7. /verify — "Verify a Client" workflow (this is the important one):
     Step 1: enter the client's national ID number.
     Step 2: consent capture — a required checkbox ("client has consented to
       this verification") + a "consent collected by" text field (default to
       the logged-in staff member's name) — every verification call requires
       both consent=true and consent_collected_by, or the API returns 403.
     Step 3: upload two files — a photo/scan of their ID card, and a selfie —
       then run:
         - POST /verify/identity (official record lookup by ID number) ->
           display as an "Official Record" card (name, DOB, gender, citizenship)
         - POST /verify/face-match (multipart: id_number, consent,
           consent_collected_by, selfie, national_id_image) -> a prominent
           result badge: green "VERIFIED — 98% match" or red "MISMATCH — 42%
           match" based on is_match/match_score
     Step 4: optional one-click additional checks, each its own card with a
       "Run check" button: KRA PIN (/verify/kra-pin), CRB score
       (/verify/crb/metropol or /verify/crb/creditinfo), phone verification
       (/verify/phone/hakikisha). Each shows its own result card once run.
     Keep a client-side "recent verifications" list (reference_id + type +
     timestamp, stored in localStorage) since there is currently no backend
     endpoint to list all past verifications for an org — only fetch-by-id
     via GET /verify/{reference_id}. Clicking a past entry re-fetches and
     re-displays that result.
8. /settings — org info (GET /auth/me), API key management.

====================================================================
KEY API ENDPOINTS YOU'LL NEED (all except signup require the Bearer header)
====================================================================
Auth
  POST /api/v1/auth/signup        { name, email, account_type: "personal"|"business" }
  POST /api/v1/auth/api-keys      { label }
  GET  /api/v1/auth/me

Customers
  POST /api/v1/customers          { full_name, national_id, phone, gender, location,
                                     email, date_of_birth, entity_type: "individual"|"business",
                                     business_name, business_reg_no, tax_id }
  GET  /api/v1/customers
  GET  /api/v1/customers/{national_id}

Statements (multipart upload)
  POST /api/v1/statements/upload  form fields: file, statement_type, national_id,
                                   passcode, product, crb_obligation, bank_code
  GET  /api/v1/statements/{ref}                -> processing status
  GET  /api/v1/statements/{ref}/score          -> score_data, reason_codes, score_breakdown, fraud_data, ml_shadow
  GET  /api/v1/statements/{ref}/summary        -> full financial_summary
  GET  /api/v1/statements/{ref}/transactions   -> classified transactions (with is_flagged/flag_reason)
  GET  /api/v1/statements/{ref}/report/pdf     -> file download
  GET  /api/v1/statements/{ref}/report/excel   -> file download

Identity / KYC / CRB verification (all require { ..., consent: true, consent_collected_by: "<name>" })
  POST /api/v1/verify/identity          { identifier }              // IPRS
  POST /api/v1/verify/passport          { identifier }
  POST /api/v1/verify/kra-pin           { identifier, search_type }
  POST /api/v1/verify/alien-id          { identifier }
  POST /api/v1/verify/face-match        multipart: id_number, consent, consent_collected_by, selfie, national_id_image
  POST /api/v1/verify/crb/metropol      { identifier, full }
  POST /api/v1/verify/crb/creditinfo    { identifier, score_only }
  POST /api/v1/verify/phone/hakikisha   { identifier, national_id }
  POST /api/v1/verify/mpesa-kyc         { phone_number, identifier }
  POST /api/v1/verify/sim-swap          { identifier }
  POST /api/v1/verify/phone-search      { identifier }
  POST /api/v1/verify/bank-account      { identifier, bank }
  POST /api/v1/verify/full-kyc          { identifier }
  POST /api/v1/verify/employer          { identifier }
  POST /api/v1/verify/driving-licence   { identifier }
  GET  /api/v1/verify/{reference_id}    -> fetch any past verification result
  POST /api/v1/business/verify          { registration_no, consent, consent_collected_by }- Do not fabricate endpoints not listed above.
- Do not build a backend, database, or use Supabase for data — this is a REST
  client to my existing FastAPI service only.
- Do not skip the consent checkbox on any verification call — the real API
  rejects the request with a 403 if consent isn't true. also ensure that we have a cool login page with form where someone selects if they are individual or company... like the one here.. so the image is on the left then the input login filed is on the right... let's have that... so we shall create an endpoint for the forgot password. also after loging in they get to homepage.. so if its creating account or signup its in the same page as login not many pages.... so its should be the same as the spinmobile https://www.spinmobile.co/ so create excatly the same... we have the endpoints i have shared...

This project was built with [Lovable](https://lovable.dev).

## Build with Lovable

Continue developing this project in the [Lovable editor](https://lovable.dev/projects/b33fca1f-f07e-4440-af5c-80eee62ea500).

- **Ship faster**: describe what you want to build and Lovable handles the code.
- **Stay in sync**: every change made in Lovable is committed straight to this repository.
- **Full ownership**: this code is yours. Push to `main` on GitHub and your changes sync back into Lovable, ready for your next prompt.

## Development

Prefer working locally? You need Node.js and npm — [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating).

```sh
git clone <this-repository-url>
cd <repository-name>
npm i
npm run dev
```
