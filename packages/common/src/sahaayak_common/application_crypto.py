"""Encryption, lookup hashing, and masking for application references."""

from __future__ import annotations

import hashlib
import hmac
import re
from functools import lru_cache

from sahaayak_common.settings import settings


class ApplicationDataEncryptionUnavailable(RuntimeError):
    """Raised when a sensitive application reference cannot be protected."""


@lru_cache(maxsize=1)
def _fernet():
    key = settings.application_data_encryption_key.strip()
    if not key:
        raise ApplicationDataEncryptionUnavailable(
            "APPLICATION_DATA_ENCRYPTION_KEY is not configured"
        )
    try:
        from cryptography.fernet import Fernet
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise ApplicationDataEncryptionUnavailable("cryptography is not installed") from exc

    try:
        return Fernet(key.encode("utf-8"))
    except (ValueError, TypeError) as exc:
        raise ApplicationDataEncryptionUnavailable(
            "APPLICATION_DATA_ENCRYPTION_KEY is not a valid Fernet key"
        ) from exc


def reset_application_encryption_cache() -> None:
    """Drop the cached cipher after a settings change, mainly for tests."""
    _fernet.cache_clear()


def normalize_reference(value: str) -> str:
    """Normalize a provider acknowledgement/reference without changing it."""
    candidate = " ".join(value.strip().split())
    if not candidate or len(candidate) > 160 or any(ord(char) < 32 for char in candidate):
        raise ValueError("Application reference must be 1–160 printable characters")
    return candidate


def encrypt_reference(value: str) -> str:
    return _fernet().encrypt(normalize_reference(value).encode("utf-8")).decode("ascii")


def reference_hash(value: str) -> str:
    """Return a keyed hash for duplicate detection without exposing the value."""
    key = settings.application_data_encryption_key.strip()
    if not key:
        raise ApplicationDataEncryptionUnavailable(
            "APPLICATION_DATA_ENCRYPTION_KEY is not configured"
        )
    return hmac.new(
        key.encode("utf-8"), normalize_reference(value).encode("utf-8"), hashlib.sha256
    ).hexdigest()


def mask_reference(value: str) -> str:
    """A short display value safe for the citizen UI and operator console."""
    candidate = normalize_reference(value)
    suffix_match = re.findall(r"[A-Za-z0-9]+", candidate)
    suffix = (suffix_match[-1] if suffix_match else candidate)[-4:]
    return f"••••{suffix}"

