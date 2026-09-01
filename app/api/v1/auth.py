"""Organization signup/login (password-based) and API-key management.

Password auth is the front door for the human dashboard: signup and login
both end by minting a fresh Bearer API key, which is what every other
endpoint actually authorizes against (see app/api/deps.py). Nothing
downstream of that changes — a password only ever gets you a key.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_org
from app.config import settings
from app.core.errors import AppError, Conflict, Forbidden, Unauthorized
from app.core.responses import ok
from app.core.security import (
    generate_api_key,
    generate_reset_token,
    hash_api_key,
    hash_password,
    verify_password,
)
from app.database import get_db
from app.models import ApiKey, Organization
from app.schemas import ApiKeyCreate, ForgotPasswordRequest, LoginRequest, OrgSignup, ResetPasswordRequest
from app.services.email import send_email

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger("auth")

_RESET_TOKEN_TTL = timedelta(hours=1)


def _org_view(org: Organization) -> dict:
    return {"uuid": str(org.uuid), "name": org.name, "email": org.email, "account_type": org.account_type}


def _issue_session_key(db: Session, org: Organization, label: str) -> str:
    raw, prefix, key_hash = generate_api_key(live=False)
    db.add(ApiKey(organization_id=org.id, key_hash=key_hash, public_prefix=prefix, label=label))
    db.commit()
    return raw


@router.post("/signup")
def signup(payload: OrgSignup, db: Session = Depends(get_db)):
    """Create an organization (personal or business) with a password, and
    hand back a first API key for immediate use.

    The raw API key is returned exactly once here — store it securely (or,
    from the dashboard, just let the frontend hold onto it; it's the
    password that's memorable, not this key).
    """
    existing = db.scalar(select(Organization).where(Organization.email == payload.email))
    if existing:
        raise Conflict("An organization with this email already exists.")

    org = Organization(
        name=payload.name, email=payload.email, account_type=payload.account_type,
        password_hash=hash_password(payload.password),
    )
    db.add(org)
    db.flush()

    raw = _issue_session_key(db, org, label="default")

    return ok(
        {"organization": _org_view(org), "api_key": raw, "note": "Store this API key now — it will not be shown again."},
        message="Organization created",
        status=201,
    )


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """Password sign-in. Issues a fresh API key on success — there is no
    session cookie/JWT here, just another Bearer key like any other."""
    org = db.scalar(select(Organization).where(Organization.email == payload.email))
    if not org or not org.password_hash or not verify_password(payload.password, org.password_hash):
        raise Unauthorized("Incorrect email or password.")
    if not org.is_active:
        raise Forbidden("This account has been deactivated.")

    raw = _issue_session_key(db, org, label="session-login")
    return ok({"organization": _org_view(org), "api_key": raw}, message="Signed in")


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Always returns the same generic message whether or not the email is
    registered — an endpoint that answers differently for known vs unknown
    emails is a user-enumeration leak."""
    org = db.scalar(select(Organization).where(Organization.email == payload.email))
    if org:
        raw_token, token_hash = generate_reset_token()
        org.password_reset_token_hash = token_hash
        org.password_reset_expires_at = datetime.now(timezone.utc) + _RESET_TOKEN_TTL
        db.commit()

        reset_link = f"{settings.frontend_base_url}/reset-password?token={raw_token}"
        sent = send_email(
            org.email,
            "Reset your Credit Yetu password",
            "We received a request to reset your Credit Yetu password.\n\n"
            f"Reset it here (expires in 1 hour):\n{reset_link}\n\n"
            "If you didn't request this, you can safely ignore this email.",
        )
        logger.info("Password reset requested for %s (email %s)", org.email, "sent" if sent else "logged, not sent — no SMTP configured")

    return ok(None, message="If that email is registered, a reset link has been sent.")


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    token_hash = hash_api_key(payload.token)
    org = db.scalar(select(Organization).where(Organization.password_reset_token_hash == token_hash))
    if not org or not org.password_reset_expires_at or org.password_reset_expires_at < datetime.now(timezone.utc):
        raise AppError("This reset link is invalid or has expired. Request a new one.", 400)

    org.password_hash = hash_password(payload.new_password)
    org.password_reset_token_hash = None
    org.password_reset_expires_at = None
    db.commit()
    return ok(None, message="Password updated — you can now sign in.")


@router.post("/api-keys")
def create_api_key(payload: ApiKeyCreate, org: Organization = Depends(get_current_org), db: Session = Depends(get_db)):
    raw, prefix, key_hash = generate_api_key(live=payload.live)
    db.add(ApiKey(organization_id=org.id, key_hash=key_hash, public_prefix=prefix, label=payload.label))
    db.commit()
    return ok({"api_key": raw, "api_key_prefix": prefix, "label": payload.label},
              message="API key created", status=201)


@router.get("/me")
def me(org: Organization = Depends(get_current_org)):
    return ok({
        "uuid": str(org.uuid),
        "name": org.name,
        "email": org.email,
        "account_type": org.account_type,
        "wallet_balance": float(org.wallet_balance),
    })
