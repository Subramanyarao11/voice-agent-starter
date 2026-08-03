"""Contact destination encryption, hashing, validation, and masking.

The property these tests defend is narrow and absolute: after a destination
enters the system, the only way back to the plaintext is the encryption key.
Hashes must not be reversible by enumeration, and masks must not be reversible
at all.
"""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from sahaayak_common import (
    ContactEncryptionUnavailable,
    channel_identity_hash,
    decrypt_destination,
    destination_hash,
    encrypt_destination,
    is_valid_destination,
    is_valid_e164,
    is_valid_email,
    mask_destination,
    normalize_destination,
    reset_encryption_cache,
    settings,
)


@pytest.fixture
def encryption_key(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "infobip_contact_encryption_key", key, raising=False)
    reset_encryption_cache()
    yield key
    reset_encryption_cache()


# --- Encryption -----------------------------------------------------------


def test_a_destination_round_trips_through_encryption(encryption_key) -> None:
    assert decrypt_destination(encrypt_destination("+919876543210")) == "+919876543210"


def test_ciphertext_does_not_contain_the_destination(encryption_key) -> None:
    ciphertext = encrypt_destination("+919876543210")
    assert "9876543210" not in ciphertext
    assert "+91" not in ciphertext


def test_the_same_destination_encrypts_differently_each_time(encryption_key) -> None:
    """Fernet is randomized, so ciphertext equality cannot leak a match."""
    assert encrypt_destination("a@b.com") != encrypt_destination("a@b.com")


def test_encryption_refuses_to_run_without_a_key(monkeypatch) -> None:
    monkeypatch.setattr(settings, "infobip_contact_encryption_key", "", raising=False)
    reset_encryption_cache()
    with pytest.raises(ContactEncryptionUnavailable):
        encrypt_destination("+919876543210")
    reset_encryption_cache()


def test_a_malformed_key_fails_loudly_rather_than_storing_plaintext(monkeypatch) -> None:
    monkeypatch.setattr(settings, "infobip_contact_encryption_key", "not-a-key", raising=False)
    reset_encryption_cache()
    with pytest.raises(ContactEncryptionUnavailable):
        encrypt_destination("+919876543210")
    reset_encryption_cache()


def test_a_rotated_key_reports_a_clear_failure(encryption_key, monkeypatch) -> None:
    ciphertext = encrypt_destination("+919876543210")
    monkeypatch.setattr(
        settings, "infobip_contact_encryption_key", Fernet.generate_key().decode(), raising=False
    )
    reset_encryption_cache()
    with pytest.raises(ContactEncryptionUnavailable):
        decrypt_destination(ciphertext)


# --- Hashing --------------------------------------------------------------


def test_the_hash_is_stable_for_the_same_destination() -> None:
    assert destination_hash("sms", "+919876543210") == destination_hash("sms", "+919876543210")


def test_formatting_differences_hash_to_the_same_contact() -> None:
    assert destination_hash("sms", "+91 98765-43210") == destination_hash("sms", "+919876543210")


def test_email_case_does_not_create_a_second_contact() -> None:
    assert destination_hash("email", "A@B.com") == destination_hash("email", "a@b.com")


def test_the_same_value_hashes_differently_per_channel() -> None:
    assert destination_hash("sms", "+919876543210") != destination_hash(
        "whatsapp", "+919876543210"
    )


def test_an_inbound_channel_identity_is_never_confused_with_a_contact() -> None:
    """A WhatsApp sender string is asserted by a third party, not registered."""
    assert channel_identity_hash("whatsapp", "+919876543210") != destination_hash(
        "whatsapp", "+919876543210"
    )


def test_the_hash_does_not_contain_the_destination() -> None:
    assert "9876543210" not in destination_hash("sms", "+919876543210")


# --- Validation -----------------------------------------------------------


@pytest.mark.parametrize(
    "value", ["+919876543210", "+14155552671", "+91 98765 43210", "+91-98765-43210"]
)
def test_valid_e164_numbers_are_accepted(value: str) -> None:
    assert is_valid_e164(value)


@pytest.mark.parametrize(
    "value",
    [
        "9876543210",  # no country code: guessing one could misdeliver
        "+0919876543210",  # leading zero after +
        "919876543210",
        "+91987654321012345678",
        "",
        "not a number",
        "+91abcdefghij",
    ],
)
def test_ambiguous_or_malformed_numbers_are_rejected(value: str) -> None:
    assert not is_valid_e164(value)


@pytest.mark.parametrize("value", ["a@b.com", "first.last@sub.domain.in", "A@B.CO"])
def test_valid_emails_are_accepted(value: str) -> None:
    assert is_valid_email(value)


@pytest.mark.parametrize(
    "value", ["", "no-at-sign", "a@b", "a@@b.com", "a b@c.com", "@b.com", "a@.com"]
)
def test_malformed_emails_are_rejected(value: str) -> None:
    assert not is_valid_email(value)


def test_an_overlong_email_is_rejected() -> None:
    assert not is_valid_email("x" * 250 + "@example.com")


def test_channel_selects_the_right_validator() -> None:
    assert is_valid_destination("email", "a@b.com")
    assert not is_valid_destination("email", "+919876543210")
    assert is_valid_destination("sms", "+919876543210")
    assert not is_valid_destination("sms", "a@b.com")


# --- Masking --------------------------------------------------------------


def test_a_masked_number_keeps_only_the_last_four_digits() -> None:
    assert mask_destination("sms", "+919876543210") == "******3210"


def test_a_masked_email_keeps_the_domain_and_one_character() -> None:
    assert mask_destination("email", "priya@example.com") == "p***@example.com"


def test_masking_a_short_value_does_not_expose_it_whole() -> None:
    masked = mask_destination("email", "@")
    assert "@" not in masked or masked == "***"


def test_normalization_is_idempotent() -> None:
    once = normalize_destination("sms", "+91 (98765) 43210")
    assert normalize_destination("sms", once) == once
