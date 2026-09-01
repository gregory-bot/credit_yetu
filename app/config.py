"""Central application configuration, loaded from environment / .env."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Application
    app_name: str = "Credit Yetu"
    env: str = "development"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"

    # Database
    database_url: str = "postgresql+psycopg2://credit:credit@localhost:5432/credit_scoring"
    # Conservative defaults: many managed Postgres tiers (Aiven's smaller plans
    # included) cap total connections around 20-25 and that budget is often
    # shared with other apps/tools (DBeaver, other schemas). pool_size +
    # max_overflow is the hard ceiling this app alone can open.
    db_pool_size: int = 5
    db_max_overflow: int = 5

    # Security
    secret_key: str = "dev-insecure-secret-change-me"
    api_key_pepper: str = "dev-insecure-pepper-change-me"
    cors_origins: str = "http://localhost:3000"

    # Storage
    storage_dir: str = "./_storage"

    # Extraction
    ocr_enabled: bool = True
    ocr_dpi: int = 300
    max_upload_mb: int = 25

    # KYC
    kyc_provider: str = "mock"
    kyc_base_url: str = ""
    kyc_api_key: str = ""

    # Tasks
    task_backend: str = "background"

    # ML shadow-scoring (see app/services/ml/) — the rule engine in
    # app/services/scoring stays authoritative; this never overrides it.
    ml_artifacts_dir: str = "./app/ml/artifacts"
    ml_min_samples: int = 40          # min labeled final outcomes before a shadow model may activate
    ml_test_size: float = 0.25
    ml_random_state: int = 42

    # Password auth (see app/api/v1/auth.py). The frontend that consumes this
    # app.
    frontend_base_url: str = "http://localhost:8080"

    # Outbound email (password reset). Left blank, this app never fails a
    # request over it — the email is logged instead, so local dev works with
    # no mail server configured. Fill these in for real delivery.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_use_tls: bool = True

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def storage_path(self) -> Path:
        p = Path(self.storage_dir)
        p.mkdir(parents=True, exist_ok=True)
        (p / "uploads").mkdir(exist_ok=True)
        (p / "reports").mkdir(exist_ok=True)
        return p

    @property
    def ml_artifacts_path(self) -> Path:
        p = Path(self.ml_artifacts_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
