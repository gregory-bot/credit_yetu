"""Customer registration and lookup."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_org
from app.core.errors import NotFound
from app.core.responses import ok
from app.database import get_db
from app.models import Customer, Organization
from app.schemas import CustomerCreate

router = APIRouter(prefix="/customers", tags=["customers"])


def _serialize(c: Customer) -> dict:
    return {
        "uuid": str(c.uuid),
        "full_name": c.full_name,
        "national_id": c.national_id,
        "phone": c.phone,
        "gender": c.gender,
        "location": c.location,
        "email": c.email,
        "entity_type": c.entity_type,
        "business_name": c.business_name,
        "business_reg_no": c.business_reg_no,
    }


@router.post("")
def create_customer(payload: CustomerCreate, org: Organization = Depends(get_current_org), db: Session = Depends(get_db)):
    customer = Customer(organization_id=org.id, **payload.model_dump())
    db.add(customer)
    db.commit()
    return ok(_serialize(customer), message="Customer registered", status=201)


@router.get("")
def list_customers(org: Organization = Depends(get_current_org), db: Session = Depends(get_db)):
    rows = db.scalars(select(Customer).where(Customer.organization_id == org.id)).all()
    return ok([_serialize(c) for c in rows])


@router.get("/{national_id}")
def get_customer(national_id: str, org: Organization = Depends(get_current_org), db: Session = Depends(get_db)):
    c = db.scalar(select(Customer).where(Customer.organization_id == org.id, Customer.national_id == national_id))
    if not c:
        raise NotFound("Customer not found.")
    return ok(_serialize(c))
