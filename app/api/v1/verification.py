"""Identity, telco, bank and CRB verification endpoints.

Every endpoint:
  * requires explicit borrower ``consent`` + ``consent_collected_by`` (legal),
  * routes through the configured provider (mock in dev),
  * persists a ``Verification`` record for audit,
  * returns the provider envelope unchanged.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_org
from app.core.errors import AppError
from app.core.responses import ok
from app.database import get_db
from app.models import Organization, Verification
from app.schemas import (
    BankAccountCheck,
    ConsentMixin,
    CrbCheck,
    IdentityCheck,
    KraCheck,
    MpesaKycCheck,
    PhoneCheck,
)
from app.services.kyc import get_provider

router = APIRouter(prefix="/verify", tags=["verification"])


def _require_consent(payload: ConsentMixin) -> None:
    if not payload.consent:
        raise AppError("Consent is required to run this verification.", 403)


def _log(db: Session, org: Organization, check_type: str, identifier: str | None,
         payload: ConsentMixin, result: dict) -> Verification:
    v = Verification(
        organization_id=org.id,
        check_type=check_type,
        identifier=identifier,
        provider=result.get("provider", "mock"),
        consent=payload.consent,
        consent_collected_by=payload.consent_collected_by,
        status="completed",
        result=result,
    )
    db.add(v)
    db.commit()
    return v


@router.post("/identity")
def verify_identity(payload: IdentityCheck, org: Organization = Depends(get_current_org), db: Session = Depends(get_db)):
    _require_consent(payload)
    result = get_provider().verify_identity(payload.identifier)
    v = _log(db, org, "identity", payload.identifier, payload, result)
    return ok({"reference_id": str(v.reference_id), **result})


@router.post("/passport")
def verify_passport(payload: IdentityCheck, org: Organization = Depends(get_current_org), db: Session = Depends(get_db)):
    _require_consent(payload)
    result = get_provider().verify_passport(payload.identifier)
    v = _log(db, org, "passport", payload.identifier, payload, result)
    return ok({"reference_id": str(v.reference_id), **result})


@router.post("/kra-pin")
def verify_kra(payload: KraCheck, org: Organization = Depends(get_current_org), db: Session = Depends(get_db)):
    _require_consent(payload)
    result = get_provider().verify_kra_pin(payload.identifier, payload.search_type)
    v = _log(db, org, "kra_pin", payload.identifier, payload, result)
    return ok({"reference_id": str(v.reference_id), **result})


@router.post("/alien-id")
def verify_alien(payload: IdentityCheck, org: Organization = Depends(get_current_org), db: Session = Depends(get_db)):
    _require_consent(payload)
    result = get_provider().verify_alien_id(payload.identifier)
    v = _log(db, org, "alien_id", payload.identifier, payload, result)
    return ok({"reference_id": str(v.reference_id), **result})


@router.post("/crb/metropol")
def crb_metropol(payload: CrbCheck, org: Organization = Depends(get_current_org), db: Session = Depends(get_db)):
    _require_consent(payload)
    result = get_provider().crb_metropol(payload.identifier, full=payload.full)
    v = _log(db, org, "metropol", payload.identifier, payload, result)
    return ok({"reference_id": str(v.reference_id), **result})


@router.post("/crb/creditinfo")
def crb_creditinfo(payload: CrbCheck, org: Organization = Depends(get_current_org), db: Session = Depends(get_db)):
    _require_consent(payload)
    result = get_provider().crb_creditinfo(payload.identifier, score_only=payload.score_only)
    v = _log(db, org, "creditinfo", payload.identifier, payload, result)
    return ok({"reference_id": str(v.reference_id), **result})


@router.post("/phone/hakikisha")
def phone_hakikisha(payload: PhoneCheck, org: Organization = Depends(get_current_org), db: Session = Depends(get_db)):
    _require_consent(payload)
    result = get_provider().phone_hakikisha(payload.identifier, national_id=payload.national_id)
    v = _log(db, org, "phone_hakikisha", payload.identifier, payload, result)
    return ok({"reference_id": str(v.reference_id), **result})


@router.post("/mpesa-kyc")
def mpesa_kyc(payload: MpesaKycCheck, org: Organization = Depends(get_current_org), db: Session = Depends(get_db)):
    _require_consent(payload)
    result = get_provider().mpesa_kyc(payload.phone_number, payload.identifier)
    v = _log(db, org, "mpesa_kyc", payload.phone_number, payload, result)
    return ok({"reference_id": str(v.reference_id), **result})


@router.post("/sim-swap")
def sim_swap(payload: PhoneCheck, org: Organization = Depends(get_current_org), db: Session = Depends(get_db)):
    _require_consent(payload)
    result = get_provider().sim_swap(payload.identifier)
    v = _log(db, org, "sim_swap", payload.identifier, payload, result)
    return ok({"reference_id": str(v.reference_id), **result})


@router.post("/phone-search")
def phone_search(payload: IdentityCheck, org: Organization = Depends(get_current_org), db: Session = Depends(get_db)):
    _require_consent(payload)
    result = get_provider().phone_search(payload.identifier)
    v = _log(db, org, "phone_search", payload.identifier, payload, result)
    return ok({"reference_id": str(v.reference_id), **result})


@router.post("/bank-account")
def bank_account(payload: BankAccountCheck, org: Organization = Depends(get_current_org), db: Session = Depends(get_db)):
    _require_consent(payload)
    result = get_provider().bank_account_validation(payload.identifier, payload.bank)
    v = _log(db, org, "bank_account", payload.identifier, payload, result)
    return ok({"reference_id": str(v.reference_id), **result})


@router.post("/full-kyc")
def full_kyc(payload: IdentityCheck, org: Organization = Depends(get_current_org), db: Session = Depends(get_db)):
    _require_consent(payload)
    result = get_provider().full_kyc(payload.identifier)
    v = _log(db, org, "full_kyc", payload.identifier, payload, result)
    return ok({"reference_id": str(v.reference_id), **result})


@router.post("/employer")
def employer(payload: IdentityCheck, org: Organization = Depends(get_current_org), db: Session = Depends(get_db)):
    _require_consent(payload)
    result = get_provider().employer_verification(payload.identifier)
    v = _log(db, org, "employer", payload.identifier, payload, result)
    return ok({"reference_id": str(v.reference_id), **result})


@router.post("/driving-licence")
def driving_licence(payload: IdentityCheck, org: Organization = Depends(get_current_org), db: Session = Depends(get_db)):
    _require_consent(payload)
    result = get_provider().driving_licence(payload.identifier)
    v = _log(db, org, "driving_licence", payload.identifier, payload, result)
    return ok({"reference_id": str(v.reference_id), **result})


@router.post("/face-match")
async def face_match(
    id_number: str = Form(...),
    consent: bool = Form(...),
    consent_collected_by: str = Form(...),
    selfie: UploadFile = File(...),
    national_id_image: UploadFile = File(...),
    org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    if not consent:
        raise AppError("Consent is required to run this verification.", 403)
    selfie_bytes = await selfie.read()
    id_bytes = await national_id_image.read()
    result = get_provider().face_match(id_number, selfie_bytes, id_bytes)
    v = Verification(
        organization_id=org.id, check_type="face_match", identifier=id_number,
        provider=result.get("provider", "mock"), consent=consent,
        consent_collected_by=consent_collected_by, status="completed", result=result,
    )
    db.add(v)
    db.commit()
    return ok({"reference_id": str(v.reference_id), **result})
