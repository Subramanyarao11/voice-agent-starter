"""Deterministic extraction of intent and slot values from an utterance.

This exists for three reasons, in order of importance. Most answers in this
conversation are a number, a category name, or yes/no, and spending a model
call plus a round-trip of latency to read "22" is waste on a phone call. It
keeps the whole dialogue testable offline, with no key and no network. And when
no OpenAI key is configured the agent still holds a usable conversation instead
of failing.

Matching is multilingual by keyword rather than by translation, because callers
code-switch constantly: "mera age 22 hai" is the norm, not the exception.
"""

from __future__ import annotations

import re

from sahaayak_contracts import (
    Domain,
    EducationLevel,
    Gender,
    Intent,
    SlotName,
    SlotValue,
    SocialCategory,
)

# --- Numbers --------------------------------------------------------------

# Whisper usually returns digits, but spelled-out numbers still appear for
# small values, which are exactly the ones ages and year-counts use.
_WORD_NUMBERS: dict[str, int] = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
    "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
    "eighty": 80, "ninety": 90, "hundred": 100,
    "ek": 1, "do": 2, "teen": 3, "char": 4, "paanch": 5,
    "एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पाँच": 5, "पांच": 5,
    "ಒಂದು": 1, "ಎರಡು": 2, "ಮೂರು": 3, "ನಾಲ್ಕು": 4, "ಐದು": 5,
}

# Indian magnitude words. Their absence is meaningful too: a caller who says
# "fifty thousand" and one who says "50000" must land on the same number.
_MULTIPLIERS: list[tuple[str, int]] = [
    ("crore", 10_000_000), ("करोड़", 10_000_000), ("करोड", 10_000_000), ("ಕೋಟಿ", 10_000_000),
    ("lakhs", 100_000), ("lakh", 100_000), ("lac", 100_000),
    ("लाख", 100_000), ("ಲಕ್ಷ", 100_000),
    ("thousand", 1_000), ("हज़ार", 1_000), ("हजार", 1_000), ("ಸಾವಿರ", 1_000),
]

_NUMERIC = re.compile(r"(\d[\d,]*\.?\d*)")
_TOKEN_SEPARATOR = re.compile(r"[\s,.;:!?।₹]+")

# Devanagari and Kannada digits, which Whisper occasionally emits verbatim.
_DIGIT_TRANSLATION = str.maketrans("०१२३४५६७८९೦೧೨೩೪೫೬೭೮೯", "01234567890123456789")


def _normalise(text: str) -> str:
    return text.translate(_DIGIT_TRANSLATION).strip()


def extract_number(text: str) -> float | None:
    """First number in the text, whether written as digits or as a word."""
    normalised = _normalise(text)
    match = _NUMERIC.search(normalised)
    if match:
        try:
            return float(match.group(1).replace(",", ""))
        except ValueError:
            return None

    # Split on separators rather than matching word characters: Devanagari and
    # Kannada vowel signs are combining marks, so a \w-based token pattern
    # shreds "दो" into its constituent code points and never matches.
    for token in _TOKEN_SEPARATOR.split(normalised.lower()):
        if token in _WORD_NUMBERS:
            return float(_WORD_NUMBERS[token])
    return None


def parse_money(text: str) -> int | None:
    """Parse an amount, applying lakh/crore/thousand multipliers.

    "2.5 lakh" and "250000" both yield 250000. A bare number is taken at face
    value, since callers reading off an income certificate say the full figure.
    """
    normalised = _normalise(text).lower()
    number = extract_number(normalised)
    if number is None:
        return None

    for word, factor in _MULTIPLIERS:
        if word in normalised:
            return int(round(number * factor))
    return int(round(number))


def parse_age(text: str) -> int | None:
    number = extract_number(text)
    if number is None:
        return None
    age = int(round(number))
    # Anything outside this is a misheard income or year, not an age.
    return age if 1 <= age <= 120 else None


def parse_years(text: str) -> int | None:
    number = extract_number(text)
    if number is None:
        return None
    years = int(round(number))
    return years if 0 <= years <= 60 else None


# --- Keyword tables -------------------------------------------------------


def _keyword_matcher(keywords: list[str]) -> re.Pattern:
    """Match keywords whole-word where the script has word boundaries.

    Latin abbreviations need boundaries — bare "sc" would otherwise match
    "school" and miscategorise the caller. Indic scripts are matched as plain
    substrings because \\b does not behave usefully against them.
    """
    parts = []
    for keyword in keywords:
        escaped = re.escape(keyword)
        if keyword.isascii():
            parts.append(rf"\b{escaped}\b")
        else:
            parts.append(escaped)
    return re.compile("|".join(parts), re.IGNORECASE | re.UNICODE)


_CATEGORY_PATTERNS: list[tuple[SocialCategory, re.Pattern]] = [
    (SocialCategory.SC, _keyword_matcher([
        "sc", "s c", "scheduled caste", "एससी", "एस सी", "अनुसूचित जाति",
        "ಎಸ್ಸಿ", "ಎಸ್ ಸಿ", "ಪರಿಶಿಷ್ಟ ಜಾತಿ",
    ])),
    (SocialCategory.ST, _keyword_matcher([
        "st", "s t", "scheduled tribe", "एसटी", "एस टी", "अनुसूचित जनजाति",
        "ಎಸ್ಟಿ", "ಎಸ್ ಟಿ", "ಪರಿಶಿಷ್ಟ ಪಂಗಡ",
    ])),
    (SocialCategory.OBC, _keyword_matcher([
        "obc", "o b c", "other backward", "ओबीसी", "ओ बी सी", "पिछड़ा",
        "ಒಬಿಸಿ", "ಒ ಬಿ ಸಿ", "ಹಿಂದುಳಿದ",
    ])),
    (SocialCategory.EWS, _keyword_matcher([
        "ews", "e w s", "economically weaker", "ईडब्ल्यूएस", "ಇಡಬ್ಲ್ಯುಎಸ್",
    ])),
    (SocialCategory.GENERAL, _keyword_matcher([
        "general", "gen", "जनरल", "सामान्य", "ಸಾಮಾನ್ಯ",
    ])),
]

# Ordered most specific first: "post graduate" must win before "graduate".
_EDUCATION_PATTERNS: list[tuple[EducationLevel, re.Pattern]] = [
    (EducationLevel.PHD, _keyword_matcher([
        "phd", "ph d", "doctorate", "पीएचडी", "ಪಿಎಚ್ಡಿ",
    ])),
    (EducationLevel.PG, _keyword_matcher([
        "pg", "post graduate", "postgraduate", "masters", "master's", "mba", "msc", "ma",
        "स्नातकोत्तर", "पोस्ट ग्रेजुएट", "एमए", "ಸ್ನಾತಕೋತ್ತರ", "ಎಂಎ",
    ])),
    (EducationLevel.UG, _keyword_matcher([
        "ug", "under graduate", "undergraduate", "graduate", "graduation", "degree",
        "bachelor", "bachelors", "ba", "bsc", "bcom", "btech", "engineering", "college",
        "स्नातक", "ग्रेजुएट", "डिग्री", "कॉलेज", "ಪದವಿ", "ಕಾಲೇಜು",
    ])),
    (EducationLevel.ITI_DIPLOMA, _keyword_matcher([
        "iti", "diploma", "polytechnic", "डिप्लोमा", "आईटीआई", "ಡಿಪ್ಲೊಮಾ", "ಐಟಿಐ",
    ])),
    (EducationLevel.CLASS_12, _keyword_matcher([
        "12th", "12", "twelfth", "puc", "pu", "intermediate", "plus two", "+2",
        "बारहवीं", "बारहवी", "ಪಿಯುಸಿ", "ಹನ್ನೆರಡನೇ",
    ])),
    (EducationLevel.CLASS_10, _keyword_matcher([
        "10th", "10", "tenth", "sslc", "matric", "matriculation",
        "दसवीं", "दसवी", "ಎಸ್ಎಸ್ಎಲ್ಸಿ", "ಹತ್ತನೇ",
    ])),
    (EducationLevel.CLASS_8, _keyword_matcher([
        "8th", "8", "eighth", "आठवीं", "ಎಂಟನೇ",
    ])),
    (EducationLevel.PRIMARY, _keyword_matcher([
        "primary", "5th", "प्राथमिक", "ಪ್ರಾಥಮಿಕ",
    ])),
    (EducationLevel.NONE, _keyword_matcher([
        "not studied", "no school", "never went to school", "illiterate",
        "नहीं पढ़ा", "ಓದಿಲ್ಲ",
    ])),
]

_GENDER_PATTERNS: list[tuple[Gender, re.Pattern]] = [
    (Gender.FEMALE, _keyword_matcher([
        "female", "woman", "girl", "lady", "महिला", "औरत", "लड़की", "स्त्री",
        "ಮಹಿಳೆ", "ಹೆಣ್ಣು", "ಹುಡುಗಿ",
    ])),
    (Gender.MALE, _keyword_matcher([
        "male", "man", "boy", "पुरुष", "आदमी", "लड़का", "ಪುರುಷ", "ಗಂಡು", "ಹುಡುಗ",
    ])),
    (Gender.OTHER, _keyword_matcher([
        "other", "transgender", "अन्य", "ಇತರ",
    ])),
]

_AFFIRMATIVE = _keyword_matcher([
    "yes", "yeah", "yep", "haan", "han", "ha", "correct", "right", "sure",
    "हाँ", "हां", "जी", "जी हाँ", "ಹೌದು", "ಸರಿ", "ಇದೆ",
])
_NEGATIVE = _keyword_matcher([
    "no", "nope", "nahi", "nahin", "not", "don't", "dont",
    "नहीं", "नही", "ना", "ಇಲ್ಲ", "ಅಲ್ಲ",
])

_ENROLLMENT_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("correspondence", _keyword_matcher(["correspondence", "पत्राचार", "ಪತ್ರವ್ಯವಹಾರ"])),
    ("distance", _keyword_matcher([
        "distance", "open university", "online", "दूरस्थ", "ದೂರಶಿಕ್ಷಣ",
    ])),
    ("regular", _keyword_matcher([
        "regular", "full time", "fulltime", "नियमित", "रेगुलर", "ನಿಯಮಿತ",
    ])),
    ("not_studying", _keyword_matcher([
        "not studying", "finished", "completed", "पढ़ाई नहीं", "ಓದುತ್ತಿಲ್ಲ",
    ])),
]

_INTENT_PATTERNS: list[tuple[Intent, re.Pattern]] = [
    (Intent.REQUEST_HUMAN, _keyword_matcher([
        "human", "person", "someone", "agent", "operator", "talk to a person",
        "व्यक्ति", "आदमी से बात", "किसी से बात", "ಮನುಷ್ಯ", "ವ್ಯಕ್ತಿಯ ಜೊತೆ",
    ])),
    (Intent.FIND_SCHOLARSHIP, _keyword_matcher([
        "scholarship", "scholarships", "stipend", "fee reimbursement",
        "छात्रवृत्ति", "स्कॉलरशिप", "ವಿದ್ಯಾರ್ಥಿವೇತನ", "ಸ್ಕಾಲರ್ಶಿಪ್",
    ])),
    (Intent.FIND_JOB, _keyword_matcher([
        "job", "jobs", "vacancy", "vacancies", "employment", "naukri", "rozgar",
        "नौकरी", "रोजगार", "रोज़गार", "भर्ती", "ಉದ್ಯೋಗ", "ಕೆಲಸ", "ನೌಕರಿ",
    ])),
    (Intent.ASK_HOW_TO_APPLY, _keyword_matcher([
        "how to apply", "how do i apply", "apply", "application",
        "कैसे आवेदन", "आवेदन कैसे", "अर्जी", "ಅರ್ಜಿ", "ಹೇಗೆ ಅರ್ಜಿ",
    ])),
    (Intent.ASK_ABOUT_BENEFIT, _keyword_matcher([
        "tell me about", "what is", "details about", "explain", "more about",
        "के बारे में बताइए", "ಮಾಹಿತಿ", "ಬಗ್ಗೆ ಹೇಳಿ",
    ])),
    (Intent.FIND_SCHEME, _keyword_matcher([
        "scheme", "schemes", "yojana", "benefit", "subsidy", "pension", "government help",
        "योजना", "योजनाएं", "सरकारी", "सब्सिडी", "पेंशन",
        "ಯೋಜನೆ", "ಸರ್ಕಾರಿ", "ಸಬ್ಸಿಡಿ", "ಪಿಂಚಣಿ",
    ])),
    (Intent.GREETING, _keyword_matcher([
        "hello", "hi", "namaste", "namaskar", "नमस्ते", "नमस्कार", "ನಮಸ್ಕಾರ", "ಹಲೋ",
    ])),
]


# --- Extraction -----------------------------------------------------------


def detect_intent(text: str) -> Intent:
    for intent, pattern in _INTENT_PATTERNS:
        if pattern.search(text):
            return intent
    return Intent.UNKNOWN


def parse_boolean(text: str) -> bool | None:
    """Negation is checked first: "no, I don't have one" contains both."""
    if _NEGATIVE.search(text):
        return False
    if _AFFIRMATIVE.search(text):
        return True
    return None


def parse_category(text: str) -> SocialCategory | None:
    for category, pattern in _CATEGORY_PATTERNS:
        if pattern.search(text):
            return category
    return None


def parse_education(text: str) -> EducationLevel | None:
    for level, pattern in _EDUCATION_PATTERNS:
        if pattern.search(text):
            return level
    return None


def parse_gender(text: str) -> Gender | None:
    for gender, pattern in _GENDER_PATTERNS:
        if pattern.search(text):
            return gender
    return None


def parse_enrollment_mode(text: str) -> str | None:
    for mode, pattern in _ENROLLMENT_PATTERNS:
        if pattern.search(text):
            return mode
    return None


def parse_slot(slot: SlotName, text: str) -> SlotValue | None:
    """Parse an utterance as an answer to one specific question.

    Context is what disambiguates: the same "22" is an age when the agent asked
    for an age and an amount when it asked for income, so parsing is driven by
    the pending slot rather than guessed from the number alone.
    """
    match slot:
        case SlotName.AGE:
            return parse_age(text)
        case SlotName.ANNUAL_FAMILY_INCOME:
            return parse_money(text)
        case SlotName.EXPERIENCE_YEARS:
            return parse_years(text)
        case SlotName.SOCIAL_CATEGORY:
            category = parse_category(text)
            return category.value if category else None
        case SlotName.EDUCATION_LEVEL:
            level = parse_education(text)
            return level.value if level else None
        case SlotName.GENDER:
            gender = parse_gender(text)
            return gender.value if gender else None
        case SlotName.ENROLLMENT_MODE:
            return parse_enrollment_mode(text)
        case SlotName.DISABILITY | SlotName.STATE_RESIDENCY:
            return parse_boolean(text)
        case SlotName.OCCUPATION | SlotName.LOCATION:
            cleaned = text.strip()
            return cleaned or None
    return None


def extract_volunteered_slots(text: str) -> dict[SlotName, SlotValue]:
    """Pick up details the caller offered without being asked.

    Someone who opens with "I'm a 22-year-old SC student" should not then be
    asked their age and category. Only unambiguous signals are taken here;
    bare numbers are skipped because without a pending question there is no way
    to tell an age from an income.
    """
    found: dict[SlotName, SlotValue] = {}

    category = parse_category(text)
    if category:
        found[SlotName.SOCIAL_CATEGORY] = category.value

    education = parse_education(text)
    if education:
        found[SlotName.EDUCATION_LEVEL] = education.value

    gender = parse_gender(text)
    if gender:
        found[SlotName.GENDER] = gender.value

    enrollment = parse_enrollment_mode(text)
    if enrollment:
        found[SlotName.ENROLLMENT_MODE] = enrollment

    age_match = re.search(
        r"(\d{1,3})\s*(?:years?\s*old|year old|साल|वर्ष|ವರ್ಷ)", _normalise(text), re.IGNORECASE
    )
    if age_match:
        age = int(age_match.group(1))
        if 1 <= age <= 120:
            found[SlotName.AGE] = age

    # An income needs an explicit magnitude word or currency marker; a bare
    # number in free speech is far more often an age or a year.
    lowered = _normalise(text).lower()
    if any(word in lowered for word, _ in _MULTIPLIERS) or "₹" in text or "rupees" in lowered:
        income = parse_money(text)
        if income is not None and income >= 1000:
            found[SlotName.ANNUAL_FAMILY_INCOME] = income

    return found


def infer_domain(intent: Intent, previous: Domain | None) -> Domain | None:
    """Keep the established domain when a turn carries no new signal."""
    return intent.domain or previous
