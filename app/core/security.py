"""API-key based authentication primitives.

Design notes
------------
* A raw API key is shown to the developer exactly once, at creation.
* We store only a peppered SHA-256 *hash* of the key — a database leak never
  exposes usable credentials.
* Verification is constant-time to avoid timing side-channels.
* Keys carry a short public prefix (e.g. ``pk_live_a1b2c3``) so they can be
  identified in logs/dashboards without revealing the secret.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets

from app.config import settings

_PREFIX_LIVE = "pk_live_"
_PREFIX_TEST = "pk_test_"


def generate_api_key(live: bool = False) -> tuple[str, str, str]:
    """Return ``(raw_key, public_prefix, key_hash)``.

    ``raw_key`` is returned to the caller once and never stored.
    """
    body = secrets.token_urlsafe(32)
    prefix = _PREFIX_LIVE if live else _PREFIX_TEST
    raw = f"{prefix}{body}"
    public_prefix = raw[: len(prefix) + 6]  # prefix + first 6 chars, safe to display
    return raw, public_prefix, hash_api_key(raw)


def hash_api_key(raw_key: str) -> str:
    """Peppered SHA-256 hash of an API key."""
    mac = hmac.new(settings.api_key_pepper.encode(), raw_key.encode(), hashlib.sha256)
    return mac.hexdigest()


def verify_api_key(raw_key: str, stored_hash: str) -> bool:
    """Constant-time comparison of a presented key against a stored hash."""
    return hmac.compare_digest(hash_api_key(raw_key), stored_hash)
