"""Offline checks for the complete Indian-language catalog.

These tests do not claim native fluency. They catch the cheaper, deterministic
failures before a reviewer spends time listening to a recording: a missing
locale, an English fallback, or text that is not in the expected script.
"""

from __future__ import annotations

import pytest

from sahaayak_agent.languages import ALL_PROFILES
from sahaayak_agent.prompts import (
    bundle_review_status,
    get_catalog,
    supported_languages,
)

EXPECTED_CODES = {"en", "hi", "kn", "ta", "te", "mr", "bn", "gu", "ml", "pa", "or"}

SCRIPT_RANGES = {
    "hi": (0x0900, 0x097F),
    "mr": (0x0900, 0x097F),
    "bn": (0x0980, 0x09FF),
    "pa": (0x0A00, 0x0A7F),
    "gu": (0x0A80, 0x0AFF),
    "or": (0x0B00, 0x0B7F),
    "ta": (0x0B80, 0x0BFF),
    "te": (0x0C00, 0x0C7F),
    "kn": (0x0C80, 0x0CFF),
    "ml": (0x0D00, 0x0D7F),
}


def test_all_registered_profiles_have_prompt_catalogs() -> None:
    assert {profile.code for profile in ALL_PROFILES} == EXPECTED_CODES
    assert EXPECTED_CODES <= set(supported_languages())


@pytest.mark.parametrize("language_code", sorted(SCRIPT_RANGES))
def test_localized_greeting_uses_the_expected_script(language_code: str) -> None:
    start, end = SCRIPT_RANGES[language_code]
    greeting = get_catalog(language_code).render("greeting")
    assert any(start <= ord(character) <= end for character in greeting)


def test_expansion_bundles_are_visible_as_machine_assisted_drafts() -> None:
    for language_code in EXPECTED_CODES - {"en", "hi", "kn"}:
        assert bundle_review_status(language_code) == "machine_assisted"


@pytest.mark.parametrize("language_code", sorted(EXPECTED_CODES))
def test_provider_locales_are_explicitly_resolvable(language_code: str) -> None:
    profile = next(profile for profile in ALL_PROFILES if profile.code == language_code)
    assert profile.resolved_stt_locale()
    assert profile.resolved_tts_locale().endswith("-IN")
