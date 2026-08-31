"""Business (SME) verification — registration lookup via the provider."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_org
from app.core.errors import AppError
from app.core.responses import ok
from app.database import get_db
from app.models import Organization, Verification
from app.schemas import BusinessCheck
from app.services.kyc import get_provider

router = APIRouter(prefix="/business", tags=["business"])


@router.post("/verify")
def verify_business(payload: BusinessCheck, org: Organization = Depends(get_current_org), db: Session = Depends(get_db)):
    if not payload.consent:
        raise AppError("Consent is required to run this verification.", 403)
    result = get_provider().business_verification(payload.registration_no)
    v = Verification(
        organization_id=org.id,
        check_type="business",
        identifier=payload.registration_no,
        provider=result.get("provider", "mock"),
        consent=payload.consent,
        consent_collected_by=payload.consent_collected_by,
        status="completed",
        result=result,
    )
    db.add(v)
    db.commit()
    return ok({"reference_id": str(v.reference_id), **result})
