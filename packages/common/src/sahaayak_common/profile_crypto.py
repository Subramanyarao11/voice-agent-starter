"""Key-separated encryption and masking for citizen/household data."""

from __future__ import annotations

import hashlib
import hmac
from functools import lru_cache

from sahaayak_common.settings import settings


class ProfileDataEncryptionUnavailable(RuntimeError):
    """Raised when household data cannot be protected on this deployment."""


@lru_cache(maxsize=1)
def _fernet():
    key = settings.profile_data_encryption_key.strip()
    if not key:
        raise ProfileDataEncryptionUnavailable(
            "PROFILE_DATA_ENCRYPTION_KEY is not configured"
        )
    try:
        from cryptography.fernet import Fernet

        return Fernet(key.encode("utf-8"))
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise ProfileDataEncryptionUnavailable("cryptography is not installed") from exc
    except (TypeError, ValueError) as exc:
        raise ProfileDataEncryptionUnavailable(
            "PROFILE_DATA_ENCRYPTION_KEY is not a valid Fernet key"
        ) from exc


def reset_profile_encryption_cache() -> None:
    _fernet.cache_clear()


def normalize_profile_value(value: str) -> str:
    normalized = " ".join(value.replace("\x00", "").split())
    if not normalized or len(normalized) > 2_000:
        raise ValueError("Profile value must be 1–2,000 printable characters")
    return normalized


def encrypt_profile_value(value: str) -> str:
    return _fernet().encrypt(normalize_profile_value(value).encode("utf-8")).decode("ascii")


def decrypt_profile_value(ciphertext: str) -> str:
    """Decrypt a profile fact for an internal, consent-scoped computation.

    Callers must never use this to build an API response. The radar worker is
    the only current consumer, and it immediately converts the value into
    matcher slots before persisting redacted evidence.
    """
    try:
        decrypted = _fernet().decrypt(ciphertext.encode("ascii")).decode("utf-8")
        return normalize_profile_value(decrypted)
    except Exception as exc:  # Fernet invalid-token/corruption must fail safe.
        raise ProfileDataEncryptionUnavailable("Profile fact ciphertext is invalid") from exc


def profile_value_hash(value: str) -> str:
    key = settings.profile_hash_key.strip()
    if not key:
        raise ProfileDataEncryptionUnavailable("PROFILE_HASH_KEY is not configured")
    return hmac.new(
        key.encode("utf-8"),
        normalize_profile_value(value).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def mask_profile_value(value: str) -> str:
    normalized = normalize_profile_value(value)
    return "••••" if len(normalized) <= 4 else f"••••{normalized[-4:]}"


def citizen_subject_hash(subject: str) -> str:
    key = settings.citizen_identity_hash_key.strip()
    if not key:
        raise ProfileDataEncryptionUnavailable("CITIZEN_IDENTITY_HASH_KEY is not configured")
    normalized = normalize_profile_value(subject)
    return hmac.new(key.encode("utf-8"), normalized.encode("utf-8"), hashlib.sha256).hexdigest()
