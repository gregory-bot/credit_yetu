-- Initial schema for the Credit Scoring API.
-- Apply with: psql "$DATABASE_URL" -f migrations/0001_init.sql
-- (Or just run `python -m scripts.init_db` to create tables from the ORM.)

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS organizations (
    id              SERIAL PRIMARY KEY,
    uuid            UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    name            VARCHAR(255) NOT NULL,
    email           VARCHAR(255) NOT NULL UNIQUE,
    account_type    VARCHAR(20) NOT NULL DEFAULT 'business',
    wallet_balance  NUMERIC(14,2) NOT NULL DEFAULT 0,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS api_keys (
    id               SERIAL PRIMARY KEY,
    organization_id  INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    key_hash         VARCHAR(64) NOT NULL UNIQUE,
    public_prefix    VARCHAR(32) NOT NULL,
    label            VARCHAR(120) NOT NULL DEFAULT 'default',
    is_active        BOOLEAN NOT NULL DEFAULT TRUE,
    last_used_at     TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_api_keys_org ON api_keys(organization_id);

CREATE TABLE IF NOT EXISTS customers (
    id               SERIAL PRIMARY KEY,
    uuid             UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    organization_id  INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    full_name        VARCHAR(255) NOT NULL,
    national_id      VARCHAR(32) NOT NULL,
    phone            VARCHAR(20),
    gender           VARCHAR(10),
    location         VARCHAR(120),
    email            VARCHAR(255),
    date_of_birth    VARCHAR(32),
    entity_type      VARCHAR(20) NOT NULL DEFAULT 'individual',
    business_name    VARCHAR(255),
    business_reg_no  VARCHAR(64),
    tax_id           VARCHAR(64),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_customers_org ON customers(organization_id);
CREATE INDEX IF NOT EXISTS ix_customers_nid ON customers(national_id);

CREATE TABLE IF NOT EXISTS statements (
    id                SERIAL PRIMARY KEY,
    reference_id      UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    organization_id   INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    customer_id       INTEGER REFERENCES customers(id) ON DELETE SET NULL,
    national_id       VARCHAR(32),
    statement_type    VARCHAR(20) NOT NULL,
    source            VARCHAR(20),
    bank_code         VARCHAR(20),
    file_name         VARCHAR(512) NOT NULL,
    file_path         VARCHAR(1024) NOT NULL,
    status            VARCHAR(20) NOT NULL DEFAULT 'received',
    extraction_method VARCHAR(30),
    status_message    TEXT,
    needs_review      BOOLEAN NOT NULL DEFAULT FALSE,
    account_holder    VARCHAR(255),
    account_number    VARCHAR(64),
    phone_number      VARCHAR(20),
    statement_period  VARCHAR(64),
    callback_url      VARCHAR(1024),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at      TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_statements_org ON statements(organization_id);
CREATE INDEX IF NOT EXISTS ix_statements_status ON statements(status);

CREATE TABLE IF NOT EXISTS transactions (
    id                    SERIAL PRIMARY KEY,
    statement_id          INTEGER NOT NULL REFERENCES statements(id) ON DELETE CASCADE,
    transaction_ref       VARCHAR(64),
    transaction_datetime  TIMESTAMP,
    description           TEXT NOT NULL DEFAULT '',
    counterparty          VARCHAR(255),
    paid_in               DOUBLE PRECISION NOT NULL DEFAULT 0,
    withdrawn             DOUBLE PRECISION NOT NULL DEFAULT 0,
    balance               DOUBLE PRECISION,
    label                 VARCHAR(20) NOT NULL DEFAULT 'normal',
    category              VARCHAR(40),
    is_flagged            BOOLEAN NOT NULL DEFAULT FALSE,
    flag_reason           VARCHAR(255),
    raw                   JSONB
);
CREATE INDEX IF NOT EXISTS ix_transactions_stmt ON transactions(statement_id);

CREATE TABLE IF NOT EXISTS scores (
    id                  SERIAL PRIMARY KEY,
    statement_id        INTEGER NOT NULL UNIQUE REFERENCES statements(id) ON DELETE CASCADE,
    credit_score        INTEGER NOT NULL DEFAULT 0,
    grade               VARCHAR(4) NOT NULL DEFAULT 'NA',
    probability         DOUBLE PRECISION,
    limit_low           DOUBLE PRECISION,
    limit_high          DOUBLE PRECISION,
    avg_monthly_income  DOUBLE PRECISION,
    dti_pct             DOUBLE PRECISION,
    month_count         DOUBLE PRECISION,
    reason_codes        JSONB,
    score_breakdown     JSONB,
    financial_summary   JSONB,
    fraud_data          JSONB,
    pdf_path            VARCHAR(1024),
    excel_path          VARCHAR(1024),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS verifications (
    id                    SERIAL PRIMARY KEY,
    reference_id          UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    organization_id       INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    check_type            VARCHAR(40) NOT NULL,
    identifier            VARCHAR(64),
    provider              VARCHAR(40) NOT NULL DEFAULT 'mock',
    consent               BOOLEAN NOT NULL DEFAULT FALSE,
    consent_collected_by  VARCHAR(255),
    status                VARCHAR(20) NOT NULL DEFAULT 'completed',
    result                JSONB,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_verifications_org ON verifications(organization_id);
CREATE INDEX IF NOT EXISTS ix_verifications_type ON verifications(check_type);

CREATE TABLE IF NOT EXISTS audit_logs (
    id               SERIAL PRIMARY KEY,
    organization_id  INTEGER REFERENCES organizations(id) ON DELETE SET NULL,
    action           VARCHAR(80) NOT NULL,
    detail           JSONB,
    ip_address       VARCHAR(64),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_audit_action ON audit_logs(action);
