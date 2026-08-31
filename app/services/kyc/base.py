"""Provider-agnostic identity & CRB interface.

Every real integration (IPRS, Metropol, Creditinfo, Safaricom, BRS, etc.) is
gated behind signed contracts and, often, regulated-entity status. This ABC
defines the surface your application calls; concrete providers implement it.

The application code never imports a concrete provider directly — it goes
through ``registry.get_provider()`` — so switching from the sandbox mock to a
live provider is a single config change (KYC_PROVIDER=...), no endpoint edits.

All methods return a plain ``dict`` following the standard envelope.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class IdentityProvider(ABC):
    name: str = "base"

    # --- Identity ---
    @abstractmethod
    def verify_identity(self, identifier: str, **ctx) -> dict: ...

    @abstractmethod
    def verify_passport(self, identifier: str, **ctx) -> dict: ...

    @abstractmethod
    def face_match(self, id_number: str, selfie: bytes, national_id_img: bytes, **ctx) -> dict: ...

    @abstractmethod
    def verify_kra_pin(self, identifier: str, search_type: str = "pin", **ctx) -> dict: ...

    @abstractmethod
    def verify_alien_id(self, identifier: str, **ctx) -> dict: ...

    # --- CRB ---
    @abstractmethod
    def crb_metropol(self, identity_number: str, full: bool = False, **ctx) -> dict: ...

    @abstractmethod
    def crb_creditinfo(self, identifier: str, score_only: bool = False, **ctx) -> dict: ...

    # --- Telco / phone ---
    @abstractmethod
    def phone_hakikisha(self, identifier: str, **ctx) -> dict: ...

    @abstractmethod
    def mpesa_kyc(self, phone_number: str, identifier: str, **ctx) -> dict: ...

    @abstractmethod
    def sim_swap(self, identifier: str, **ctx) -> dict: ...

    @abstractmethod
    def phone_search(self, identifier: str, **ctx) -> dict: ...

    # --- Bank ---
    @abstractmethod
    def bank_account_validation(self, identifier: str, bank: str, **ctx) -> dict: ...

    # --- Composite / business ---
    @abstractmethod
    def full_kyc(self, identifier: str, **ctx) -> dict: ...

    @abstractmethod
    def employer_verification(self, identifier: str, **ctx) -> dict: ...

    @abstractmethod
    def business_verification(self, registration_no: str, **ctx) -> dict: ...

    @abstractmethod
    def driving_licence(self, identifier: str, **ctx) -> dict: ...
