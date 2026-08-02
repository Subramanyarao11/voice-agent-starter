"""Tests for the phrase catalogs.

The coverage test is the one that matters: it is the executable form of the
claim that adding a language is a data change. If a new language module misses
a key, this fails rather than a caller hearing English mid-sentence.
"""

from __future__ import annotations

import pytest

from sahaayak_agent.prompts import CATALOGS, get_catalog, missing_keys, supported_languages
from sahaayak_contracts import SLOT_REGISTRY


@pytest.mark.parametrize("language_code", sorted(CATALOGS))
def test_every_language_covers_every_phrase(language_code):
    assert missing_keys(language_code) == []


@pytest.mark.parametrize("language_code", sorted(CATALOGS))
def test_every_slot_has_a_question_in_every_language(language_code):
    catalog = get_catalog(language_code)
    for spec in SLOT_REGISTRY.values():
        assert catalog.has(spec.prompt_key), f"{language_code} lacks {spec.prompt_key}"


@pytest.mark.parametrize("language_code", sorted(CATALOGS))
def test_placeholders_agree_with_the_english_reference(language_code):
    """A translation that drops {state} would render a question with no subject."""
    reference = CATALOGS["en"]
    for key, template in CATALOGS[language_code].items():
        expected = {
            part.split("}")[0] for part in reference[key].split("{")[1:]
        }
        actual = {part.split("}")[0] for part in template.split("{")[1:]}
        assert actual == expected, f"{language_code}:{key}"


def test_rendering_substitutes_parameters():
    assert "Karnataka" in get_catalog("en").render("ask_state_residency", state="Karnataka")


def test_unknown_language_falls_back_to_english():
    """A partly configured language should degrade, not end the call."""
    catalog = get_catalog("xx")
    assert catalog.render("ask_age") == CATALOGS["en"]["ask_age"]


def test_missing_parameter_returns_the_template_rather_than_raising():
    rendered = get_catalog("en").render("ask_state_residency")
    assert rendered  # no exception, and the caller still hears something


def test_kannada_and_hindi_are_served():
    assert {"kn", "hi", "en"} <= set(supported_languages())
