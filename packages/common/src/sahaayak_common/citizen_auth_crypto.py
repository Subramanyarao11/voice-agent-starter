"""Encryption for provider tokens held by the citizen OIDC/BFF."""

from __future__ import annotations

from functools import lru_cache

from sahaayak_common.settings import settings


class CitizenAuthEncryptionUnavailable(RuntimeError):
    """Raised when the BFF cannot protect an identity-provider token."""


@lru_cache(maxsize=1)
def _fernet():
    key = settings.citizen_auth_encryption_key.strip()
    if not key:
        raise CitizenAuthEncryptionUnavailable(
            "CITIZEN_AUTH_ENCRYPTION_KEY is not configured"
        )
    try:
        from cryptography.fernet import Fernet

        return Fernet(key.encode("utf-8"))
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise CitizenAuthEncryptionUnavailable("cryptography is not installed") from exc
    except (TypeError, ValueError) as exc:
        raise CitizenAuthEncryptionUnavailable(
            "CITIZEN_AUTH_ENCRYPTION_KEY is not a valid Fernet key"
        ) from exc


def reset_citizen_auth_encryption_cache() -> None:
    _fernet.cache_clear()


def encrypt_provider_token(token: str) -> str:
    if not token or len(token) > 16_000:
        raise ValueError("Provider token is empty or too large")
    return _fernet().encrypt(token.encode("utf-8")).decode("ascii")


def decrypt_provider_token(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except Exception as exc:  # Fernet invalid-token/corruption must fail safe.
        raise CitizenAuthEncryptionUnavailable("Stored provider token is invalid") from exc
