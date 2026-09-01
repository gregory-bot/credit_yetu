-- Password-based auth for the human dashboard, on top of the existing
-- Bearer API-key model (unchanged — a password only ever mints a fresh key).
-- Apply with: psql "$DATABASE_URL" -f migrations/0003_password_auth.sql

ALTER TABLE organizations
    ADD COLUMN IF NOT EXISTS password_hash               VARCHAR(255),
    ADD COLUMN IF NOT EXISTS password_reset_token_hash    VARCHAR(64),
    ADD COLUMN IF NOT EXISTS password_reset_expires_at    TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS ix_organizations_reset_token ON organizations(password_reset_token_hash);
