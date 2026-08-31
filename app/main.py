"""FastAPI application entrypoint."""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.config import settings
from app.core.errors import register_exception_handlers
from app.core.responses import ok

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description=(
        "Transparent, rule-based credit scoring from M-Pesa/bank/SACCO statements, "
        "with statement extraction (text + OCR), fraud forensics, a financial-summary "
        "engine, PDF/Excel reporting, and a swappable KYC/CRB provider adapter."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/health", tags=["meta"])
def health():
    return ok({"status": "healthy", "env": settings.env})


@app.get("/config", tags=["meta"])
def config():
    """Non-sensitive runtime config (secrets redacted)."""
    return ok({
        "app_name": settings.app_name,
        "env": settings.env,
        "api_v1_prefix": settings.api_v1_prefix,
        "kyc_provider": settings.kyc_provider,
        "ocr_enabled": settings.ocr_enabled,
        "task_backend": settings.task_backend,
        "max_upload_mb": settings.max_upload_mb,
    })


@app.get("/", tags=["meta"])
def root():
    return ok({"name": settings.app_name, "docs": "/docs", "health": "/health"})
