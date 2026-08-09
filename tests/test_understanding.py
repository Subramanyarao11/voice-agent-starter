"""Tests for the rule-based extractor.

These cover the phrasings real callers actually use — code-switched sentences,
spoken magnitudes, and native-script digits — because that is what the agent
receives, not tidy English.
"""

from __future__ import annotations

import pytest

from sahaayak_agent.understanding import rules
from sahaayak_contracts import EducationLevel, Gender, Intent, SlotName, SocialCategory


@pytest.mark.parametrize(
    ("utterance", "expected"),
    [
        ("2 lakh", 200_000),
        ("2.5 lakh", 250_000),
        ("250000", 250_000),
        ("2,50,000", 250_000),
        ("fifty thousand", 50_000),
        ("1 crore", 10_000_000),
        ("दो लाख", 200_000),
        ("२ लाख", 200_000),
        ("೧ ಲಕ್ಷ", 100_000),
        ("₹45000", 45_000),
        ("I am 22 years old and my annual family income is 12 lakh", 1_200_000),
        ("I am 22 years old and earn ₹4,50,000", 450_000),
        ("age 22 and income is 450000 rupees", 450_000),
    ],
)
def test_money_handles_indian_magnitudes_and_scripts(utterance, expected):
    assert rules.parse_money(utterance) == expected


@pytest.mark.parametrize(
    ("utterance", "expected"),
    [
        ("22", 22),
        ("I am 22 years old", 22),
        ("मेरी उम्र 30 साल है", 30),
        ("twenty", 20),
        ("450000", None),  # an income misheard as an age must be rejected
        ("no idea", None),
    ],
)
def test_age_rejects_values_outside_a_human_range(utterance, expected):
    assert rules.parse_age(utterance) == expected


def test_category_abbreviations_respect_word_boundaries():
    """Bare "sc" inside "school" must not classify someone as Scheduled Caste."""
    assert rules.parse_category("I am SC") is SocialCategory.SC
    assert rules.parse_category("I go to school") is None
    assert rules.parse_category("general category") is SocialCategory.GENERAL


@pytest.mark.parametrize(
    ("utterance", "expected"),
    [
        ("ಎಸ್ ಸಿ", SocialCategory.SC),
        ("मैं ओबीसी से हूँ", SocialCategory.OBC),
        ("अनुसूचित जनजाति", SocialCategory.ST),
        ("EWS", SocialCategory.EWS),
    ],
)
def test_category_is_recognised_across_languages(utterance, expected):
    assert rules.parse_category(utterance) is expected


def test_education_prefers_the_more_specific_match():
    """"Post graduate" contains "graduate", so ordering decides correctness."""
    assert rules.parse_education("post graduate") is EducationLevel.PG
    assert rules.parse_education("I am doing my degree") is EducationLevel.UG
    assert rules.parse_education("ಪದವಿ") is EducationLevel.UG
    assert rules.parse_education("SSLC pass") is EducationLevel.CLASS_10
    assert rules.parse_education("12") is EducationLevel.CLASS_12
    assert rules.parse_education("I studied up to class 10") is EducationLevel.CLASS_10
    assert (
        rules.parse_education("I am 22 and my income is 12 lakh and I studied class 10")
        is EducationLevel.CLASS_10
    )


def test_negation_wins_over_a_stray_affirmative():
    """"No, I don't have one" contains "no" and "don't" but no "yes" — and a
    sentence containing both must not be read as agreement."""
    assert rules.parse_boolean("no, I don't have one") is False
    assert rules.parse_boolean("ಇಲ್ಲ") is False
    assert rules.parse_boolean("हाँ") is True
    assert rules.parse_boolean("maybe") is None


@pytest.mark.parametrize(
    ("utterance", "expected"),
    [
        ("I need a scholarship", Intent.FIND_SCHOLARSHIP),
        ("ವಿದ್ಯಾರ್ಥಿವೇತನ ಬೇಕು", Intent.FIND_SCHOLARSHIP),
        ("मुझे नौकरी चाहिए", Intent.FIND_JOB),
        # Romanised Hindi, which is how a lot of callers actually type and how
        # transcription often renders code-switched speech.
        ("koi sarkari yojana batao", Intent.FIND_SCHEME),
        ("कोई सरकारी योजना बताइए", Intent.FIND_SCHEME),
        ("let me talk to a person", Intent.REQUEST_HUMAN),
        ("tell me about this benefit", Intent.ASK_ABOUT_BENEFIT),
        ("how do I apply for this scheme", Intent.ASK_HOW_TO_APPLY),
        ("namaste", Intent.GREETING),
    ],
)
def test_intent_detection_across_languages(utterance, expected):
    assert rules.detect_intent(utterance) is expected


def test_volunteered_details_are_picked_up_without_being_asked():
    found = rules.extract_volunteered_slots("I am a 22 year old SC girl doing my degree")
    assert found[SlotName.AGE] == 22
    assert found[SlotName.SOCIAL_CATEGORY] == SocialCategory.SC.value
    assert found[SlotName.GENDER] == Gender.FEMALE.value
    assert found[SlotName.EDUCATION_LEVEL] == EducationLevel.UG.value


def test_age_is_not_mistaken_for_the_income_in_a_combined_answer():
    found = rules.extract_volunteered_slots(
        "I am 22 years old and my annual family income is 12 lakh"
    )
    assert found[SlotName.AGE] == 22
    assert found[SlotName.ANNUAL_FAMILY_INCOME] == 1_200_000


def test_bare_numbers_are_not_guessed_as_income():
    """Out of context a number could be an age, a year, or an amount, so it is
    left for the pending question to interpret."""
    assert SlotName.ANNUAL_FAMILY_INCOME not in rules.extract_volunteered_slots("22")
    assert (
        rules.extract_volunteered_slots("we earn 2 lakh a year")[
            SlotName.ANNUAL_FAMILY_INCOME
        ]
        == 200_000
    )


def test_the_pending_question_decides_how_a_number_is_read():
    assert rules.parse_slot(SlotName.AGE, "22") == 22
    assert rules.parse_slot(SlotName.ANNUAL_FAMILY_INCOME, "22") == 22
    assert rules.parse_slot(SlotName.ANNUAL_FAMILY_INCOME, "2 lakh") == 200_000
