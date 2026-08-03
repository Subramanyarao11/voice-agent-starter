"""Encryption, hashing, and masking for contact destinations.

A phone number or email address is the most sensitive thing this system stores
about a caller who never created an account. Three representations exist, and
each is used for exactly one job:

- ciphertext, decryptable only by the process holding the key, used solely at
  the moment a message is dispatched;
- a keyed hash, used for deduplication and lookup, so the database can answer
  "is this contact already registered" without holding the value;
- a masked suffix, safe for the browser and the admin console.

Nothing else may read the plaintext. In particular the API never returns a
destination it was given, and no log line, telemetry row, or trace attribute
takes one.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from functools import lru_cache

from sahaayak_common.settings import settings


class ContactEncryptionUnavailable(RuntimeError):
    """Raised when a destination must be handled but no key is configured.

    Deliberately fatal rather than degrading to plaintext. A missing key is a
    deployment mistake, and silently storing an unencrypted phone number is a
    worse outcome than a failed request.
    """


@lru_cache(maxsize=1)
def _fernet():
    key = settings.infobip_contact_encryption_key.strip()
    if not key:
        raise ContactEncryptionUnavailable(
            "INFOBIP_CONTACT_ENCRYPTION_KEY is not configured"
        )
    try:
        from cryptography.fernet import Fernet
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise ContactEncryptionUnavailable("cryptography is not installed") from exc

    try:
        return Fernet(key.encode("utf-8"))
    except (ValueError, TypeError) as exc:
        raise ContactEncryptionUnavailable(
            "INFOBIP_CONTACT_ENCRYPTION_KEY is not a valid Fernet key"
        ) from exc


def reset_encryption_cache() -> None:
    """Drop the cached cipher after a settings change, mainly for tests."""
    _fernet.cache_clear()


def encrypt_destination(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_destination(ciphertext: str) -> str:
    """Recover a destination for dispatch. Never call this to display one."""
    from cryptography.fernet import InvalidToken

    try:
        return _fernet().decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError) as exc:
        # Almost always a rotated key. Say so without echoing the ciphertext.
        raise ContactEncryptionUnavailable(
            "stored destination could not be decrypted with the current key"
        ) from exc


def destination_hash(channel: str, value: str) -> str:
    """A keyed, channel-scoped lookup hash.

    Keyed rather than a bare SHA-256: the space of Indian mobile numbers is
    small enough to enumerate exhaustively, so an unkeyed digest of a phone
    number is not meaningfully better than storing the number.
    """
    salt = settings.rate_limit_key_salt or settings.infobip_contact_encryption_key or "sahaayak"
    return hmac.new(
        salt.encode("utf-8"),
        f"{channel}:{normalize_destination(channel, value)}".encode(),
        hashlib.sha256,
    ).hexdigest()


def channel_identity_hash(channel: str, external_id: str) -> str:
    """Hash an inbound channel identity, e.g. a WhatsApp sender.

    Same construction as a destination hash, but named separately because the
    two must never be conflated: a sender string a third party asserts is not
    a contact the caller registered and verified.
    """
    return destination_hash(f"identity:{channel}", external_id)


_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s.]+(\.[^@\s.]+)+$")
_E164_PATTERN = re.compile(r"^\+[1-9]\d{7,14}$")
_PHONE_STRIP = re.compile(r"[\s\-().]")


def normalize_destination(channel: str, value: str) -> str:
    """Canonical form, so one contact cannot be registered twice."""
    cleaned = value.strip()
    if channel == "email":
        return cleaned.lower()
    return _PHONE_STRIP.sub("", cleaned)


def is_valid_email(value: str) -> bool:
    candidate = normalize_destination("email", value)
    return bool(candidate) and len(candidate) <= 254 and bool(_EMAIL_PATTERN.match(candidate))


def is_valid_e164(value: str) -> bool:
    """Strict E.164 only.

    Rejecting a bare ten-digit number is intentional even though Indian
    callers will type one: guessing the country code server-side is how a
    reminder ends up delivered to a stranger in another country.
    """
    return bool(_E164_PATTERN.match(normalize_destination("sms", value)))


def is_valid_destination(channel: str, value: str) -> bool:
    if channel == "email":
        return is_valid_email(value)
    return is_valid_e164(value)


def mask_destination(channel: str, value: str) -> str:
    """A display form safe to return to a browser or show an operator."""
    candidate = normalize_destination(channel, value)
    if channel == "email":
        local, _, domain = candidate.partition("@")
        if not domain:
            return "***"
        head = local[0] if local else ""
        return f"{head}***@{domain}"
    tail = candidate[-4:] if len(candidate) >= 4 else candidate
    return f"******{tail}"
