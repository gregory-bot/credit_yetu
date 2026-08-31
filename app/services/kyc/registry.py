"""Provider registry — selects the active KYC/CRB provider from config.

To add a real provider (e.g. Spin Mobile), implement ``IdentityProvider`` in a
new module (calling the upstream API with ``httpx`` and your KYC_API_KEY), then
register it in ``_PROVIDERS`` below. No application/endpoint code changes.
"""
from __future__ import annotations

from functools import lru_cache

from app.config import settings
from app.services.kyc.base import IdentityProvider
from app.services.kyc.mock_provider import MockProvider


class _NotConfiguredProvider(IdentityProvider):
    """Placeholder for a real provider that hasn't been wired up yet.

    Raises a clear error rather than silently returning fake data — so nobody
    ships to production believing a real integration exists when it doesn't.
    """

    name = "unconfigured"

    def _fail(self, *_a, **_k):
        raise RuntimeError(
            f"KYC provider '{settings.kyc_provider}' is selected but not implemented. "
            "Implement it against IdentityProvider and register it in registry._PROVIDERS, "
            "or set KYC_PROVIDER=mock for sandbox."
        )

    # Point every abstract method at the same failure.
    verify_identity = verify_passport = face_match = verify_kra_pin = _fail
    verify_alien_id = crb_metropol = crb_creditinfo = phone_hakikisha = _fail
    mpesa_kyc = sim_swap = phone_search = bank_account_validation = _fail
    full_kyc = employer_verification = business_verification = driving_licence = _fail


_PROVIDERS = {
    "mock": MockProvider,
    # "spinmobile": SpinMobileProvider,   # <- add when contracts are in place
}


@lru_cache
def get_provider() -> IdentityProvider:
    cls = _PROVIDERS.get(settings.kyc_provider)
    if cls is None:
        return _NotConfiguredProvider()
    return cls()
