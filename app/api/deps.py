"""Shared FastAPI dependencies (authentication, etc.)."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import Unauthorized
from app.core.security import hash_api_key
from app.database import get_db
from app.models import ApiKey, Organization


def get_current_org(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Organization:
    """Resolve the caller's organization from a Bearer API key.

    Expects: ``Authorization: Bearer pk_live_xxx``. Only the key *hash* is ever
    compared against the database.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise Unauthorized("Missing or malformed Authorization header (expected Bearer token).")

    raw_key = authorization.split(" ", 1)[1].strip()
    key_hash = hash_api_key(raw_key)

    api_key = db.scalar(select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.is_active.is_(True)))
    if api_key is None:
        raise Unauthorized("Invalid API key.")

    org = db.get(Organization, api_key.organization_id)
    if org is None or not org.is_active:
        raise Unauthorized("Organization is inactive or does not exist.")

    api_key.last_used_at = datetime.now(timezone.utc)
    db.commit()
    return org
