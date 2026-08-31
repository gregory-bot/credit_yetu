-- ML shadow-scoring: ground-truth loan outcomes + trained model versions.
-- Apply with: psql "$DATABASE_URL" -f migrations/0002_ml_shadow_scoring.sql
-- (Or just run `python -m scripts.init_db` — it creates tables from the ORM.)

CREATE TABLE IF NOT EXISTS loan_outcomes (
    id               SERIAL PRIMARY KEY,
    statement_id     INTEGER NOT NULL UNIQUE REFERENCES statements(id) ON DELETE CASCADE,
    organization_id  INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    loan_amount      DOUBLE PRECISION NOT NULL,
    disbursed_at     TIMESTAMPTZ,
    outcome          VARCHAR(20) NOT NULL,   -- current | repaid | delinquent | defaulted
    days_past_due    INTEGER NOT NULL DEFAULT 0,
    notes            TEXT,
    recorded_by      VARCHAR(255),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_loan_outcomes_org ON loan_outcomes(organization_id);
CREATE INDEX IF NOT EXISTS ix_loan_outcomes_outcome ON loan_outcomes(outcome);

CREATE TABLE IF NOT EXISTS ml_model_versions (
    id                SERIAL PRIMARY KEY,
    version           VARCHAR(64) NOT NULL UNIQUE,
    algorithm         VARCHAR(40) NOT NULL,
    status            VARCHAR(24) NOT NULL DEFAULT 'retired',  -- shadow | retired | trained_insufficient
    n_samples         INTEGER NOT NULL,
    n_train           INTEGER NOT NULL,
    n_test            INTEGER NOT NULL,
    n_positive        INTEGER NOT NULL,
    n_negative        INTEGER NOT NULL,
    feature_names     JSONB NOT NULL,
    metrics           JSONB NOT NULL,
    baseline_metrics  JSONB,
    artifact_path     VARCHAR(1024) NOT NULL,
    trained_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    trained_by        VARCHAR(255)
);
CREATE INDEX IF NOT EXISTS ix_ml_model_versions_status ON ml_model_versions(status);
