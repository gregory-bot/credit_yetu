"""Shared FastAPI dependencies (authentication, etc.)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import Unauthorized
from app.core.security import hash_api_key
from app.database import get_db
from app.models import ApiKey, Organization

# How stale `last_used_at` may get before we bother writing a fresh value.
# This dependency runs on every authenticated request; against a remote DB
# each round trip is expensive, so writing on every single call would double
# that cost for a timestamp nobody reads at that resolution anyway.
_LAST_USED_WRITE_INTERVAL = timedelta(minutes=5)


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

    # A single joined query instead of two separate round trips (API key,
    # then organization by id) — meaningful against a remote, higher-latency
    # database where every extra round trip is felt directly by the caller.
    row = db.execute(
        select(ApiKey, Organization)
        .join(Organization, Organization.id == ApiKey.organization_id)
        .where(ApiKey.key_hash == key_hash, ApiKey.is_active.is_(True))
    ).first()
    if row is None:
        raise Unauthorized("Invalid API key.")
    api_key, org = row
    if not org.is_active:
        raise Unauthorized("Organization is inactive or does not exist.")

    now = datetime.now(timezone.utc)
    if api_key.last_used_at is None or now - api_key.last_used_at > _LAST_USED_WRITE_INTERVAL:
        api_key.last_used_at = now
        db.commit()
    return org
