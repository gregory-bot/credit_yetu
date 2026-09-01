"""Pydantic request models. Responses use the envelope in core/responses.py."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, EmailStr, Field


# --- Auth / org ---
class OrgSignup(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    account_type: Literal["personal", "business"] = "business"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=10)
    new_password: str = Field(min_length=8, max_length=128)


class ApiKeyCreate(BaseModel):
    label: str = Field(default="default", max_length=120)
    live: bool = False


# --- Customer ---
class CustomerCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=255)
    national_id: str = Field(min_length=4, max_length=32)
    phone: str | None = None
    gender: Literal["M", "F", "male", "female"] | None = None
    location: str | None = None
    email: EmailStr | None = None
    date_of_birth: str | None = None
    entity_type: Literal["individual", "business"] = "individual"
    business_name: str | None = None
    business_reg_no: str | None = None
    tax_id: str | None = None


# --- Verification (KYC) ---
class ConsentMixin(BaseModel):
    consent: bool = Field(..., description="Borrower consent to run this check (legally required).")
    consent_collected_by: str = Field(..., min_length=2, description="Who collected the consent.")


class IdentityCheck(ConsentMixin):
    identifier: str = Field(..., description="National ID / passport / alien ID number.")


class KraCheck(ConsentMixin):
    identifier: str
    search_type: Literal["pin", "id"] = "pin"


class CrbCheck(ConsentMixin):
    identifier: str
    full: bool = False
    score_only: bool = False


class PhoneCheck(ConsentMixin):
    identifier: str = Field(..., description="Phone number in 2547XXXXXXXX format.")
    national_id: str | None = None


class MpesaKycCheck(ConsentMixin):
    phone_number: str
    identifier: str


class BankAccountCheck(ConsentMixin):
    identifier: str = Field(..., description="Bank account number.")
    bank: str


class BusinessCheck(ConsentMixin):
    registration_no: str


# --- Transactions scoring (pre-extracted data) ---
class RawTransaction(BaseModel):
    date: str | None = None
    description: str = ""
    paid_in: float = 0.0
    withdrawn: float = 0.0
    balance: float | None = None
    reference: str | None = None


class TransactionsScoreRequest(BaseModel):
    national_id: str | None = None
    account_holder: str | None = None
    phone: str | None = None
    product: Literal["personal", "employed", "business_registered", "business_unregistered", "sme", "vehicle"] = "personal"
    crb_obligation: float = 0.0
    transactions: list[RawTransaction]


# --- Loan outcomes (ML shadow-scoring ground truth) ---
class LoanOutcomeCreate(BaseModel):
    loan_amount: float = Field(gt=0)
    disbursed_at: str | None = Field(None, description="ISO date/datetime the loan was disbursed.")
    outcome: Literal["current", "repaid", "delinquent", "defaulted"] = Field(
        ..., description="'current' loans are excluded from training until they reach a final outcome."
    )
    days_past_due: int = Field(0, ge=0)
    notes: str | None = None
    recorded_by: str | None = Field(None, description="Who recorded this outcome (credit ops analyst, system, etc).")
