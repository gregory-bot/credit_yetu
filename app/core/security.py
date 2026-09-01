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

import bcrypt

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


# --- Passwords -------------------------------------------------------------
# Deliberately a *different, slower* hash than the API-key one above. An API
# key is a 32-byte random token — brute-forcing it is infeasible regardless
# of hash speed, so a fast keyed hash (HMAC-SHA256) is fine and cheap. A
# password is user-chosen and much lower entropy; hashing it with something
# fast would make an offline dictionary attack practical if the database
# ever leaked. bcrypt is intentionally slow and self-salting for exactly
# that reason.

def hash_password(raw_password: str) -> str:
    return bcrypt.hashpw(raw_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(raw_password: str, stored_hash: str) -> bool:
    try:
        return bcrypt.checkpw(raw_password.encode("utf-8"), stored_hash.encode("utf-8"))
    except (ValueError, TypeError):
        # Malformed/missing hash (e.g. an account created before passwords
        # existed) — never let a bad hash blow up into a 500.
        return False


def generate_reset_token() -> tuple[str, str]:
    """Return ``(raw_token, token_hash)`` for a password-reset link.

    The token itself is high-entropy random (like an API key, not a
    password), so the fast peppered hash above is the right tool here too —
    reusing it rather than bcrypt keeps this cheap to verify on every
    reset-password attempt without weakening anything.
    """
    raw = secrets.token_urlsafe(32)
    return raw, hash_api_key(raw)
