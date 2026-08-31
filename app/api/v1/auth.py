"""Organization signup and API-key management."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_org
from app.core.errors import Conflict
from app.core.responses import ok
from app.core.security import generate_api_key
from app.database import get_db
from app.models import ApiKey, Organization
from app.schemas import ApiKeyCreate, OrgSignup

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup")
def signup(payload: OrgSignup, db: Session = Depends(get_db)):
    """Create an organization (personal or business) and its first API key.

    The raw API key is returned exactly once here — store it securely.
    """
    existing = db.scalar(select(Organization).where(Organization.email == payload.email))
    if existing:
        raise Conflict("An organization with this email already exists.")

    org = Organization(name=payload.name, email=payload.email, account_type=payload.account_type)
    db.add(org)
    db.flush()

    raw, prefix, key_hash = generate_api_key(live=False)
    db.add(ApiKey(organization_id=org.id, key_hash=key_hash, public_prefix=prefix, label="default"))
    db.commit()

    return ok(
        {
            "organization": {"uuid": str(org.uuid), "name": org.name, "email": org.email, "account_type": org.account_type},
            "api_key": raw,
            "api_key_prefix": prefix,
            "note": "Store this API key now — it will not be shown again.",
        },
        message="Organization created",
        status=201,
    )


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
