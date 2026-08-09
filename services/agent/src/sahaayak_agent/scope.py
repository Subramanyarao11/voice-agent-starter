"""Deterministic product-scope guardrails for every AI-facing input.

Sahaayak is a focused public-service assistant, not a general chatbot. This
small classifier runs before model-backed understanding and retrieval. It is
intentionally conservative: known benefit/application requests and structured
answers are allowed; unrelated or prompt-injection-shaped requests are
answered with a fixed local-language redirect without calling a provider.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ScopeDecision:
    allowed: bool
    reason: str = ""


_PRODUCT_MARKERS = re.compile(
    r"(?:scheme|schemes|scholarship|scholarships|benefit|benefits|yojana|subsidy|"
    r"pension|government|govt|सरकार|योजना|छात्रवृत्ति|वजीफा|पेंशन|सब्सिडी|"
    r"ಸರ್ಕಾರಿ|ಯೋಜನೆ|ವಿದ್ಯಾರ್ಥಿವೇತನ|ಪಿಂಚಣಿ|ಸಹಾಯ|"
    r"job|jobs|vacancy|vacancies|employment|naukri|rozgar|recruitment|"
    r"नौकरी|रोजगार|भर्ती|ಉದ್ಯೋಗ|ನೌಕರಿ|"
    r"apply|application|eligib|eligible|eligibility|document|certificate|"
    r"deadline|status|registration|how to|official source|department|district|"
    r"pincode|income|caste|category|disability|student|farmer|"
    r"अर्ज|आवेदन|पात्र|दस्तावेज|आय|जाति|जिला|पिनकोड|"
    r"ಅರ್ಜಿ|ಅರ್ಹ|ದಾಖಲೆ|ಆದಾಯ|ಜಾತಿ|ಜಿಲ್ಲೆ|ಪಿನ್)",
    re.IGNORECASE,
)
_CONVERSATION_MARKERS = re.compile(
    r"(?:hello|hi|hey|namaste|namaskar|help|human|person|operator|agent|"
    r"नमस्ते|मदद|व्यक्ति|ಮನುಷ್ಯ|ಮદદ|ಸಹಾಯ)",
    re.IGNORECASE,
)
_PROMPT_INJECTION_MARKERS = re.compile(
    r"(?:ignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions?|"
    r"system\s+prompt|developer\s+message|reveal\s+(?:the\s+)?(?:prompt|key|secret)|"
    r"show\s+(?:me\s+)?(?:your\s+instructions|hidden\s+instructions)|"
    r"jailbreak|disregard\s+(?:the\s+)?rules|act\s+as\s+(?:a\s+)?(?:different|general)\s+assistant)",
    re.IGNORECASE,
)
_UNSUPPORTED_REQUEST_MARKERS = re.compile(
    r"(?:\b(?:write|generate|debug|fix|create)\s+(?:me\s+)?(?:code|python|javascript|sql|a\s+script)|"
    r"\b(?:tell|write|make)\s+(?:me\s+)?(?:a\s+)?(?:joke|story|poem|song|recipe)|"
    r"\b(?:weather|sports? scores?|stock prices?|cryptocurrency|crypto|movies?|music)\b|"
    r"(?:diagnose|prescription|medical treatment|legal representation))",
    re.IGNORECASE,
)

_OUT_OF_SCOPE_MESSAGES = {
    "en": (
        "I can help only with government schemes, scholarships, jobs, eligibility, "
        "applications, and official department information. Please ask about one of those."
    ),
    "hi": (
        "मैं केवल सरकारी योजनाओं, छात्रवृत्ति, नौकरियों, पात्रता, आवेदन और सरकारी "
        "विभाग की आधिकारिक जानकारी में मदद कर सकता हूँ। कृपया इन्हीं में से कुछ पूछिए।"
    ),
    "kn": (
        "ನಾನು ಸರ್ಕಾರಿ ಯೋಜನೆಗಳು, ವಿದ್ಯಾರ್ಥಿವೇತನ, ಉದ್ಯೋಗ, ಅರ್ಹತೆ, ಅರ್ಜಿ ಮತ್ತು ಅಧಿಕೃತ "
        "ಇಲಾಖೆ ಮಾಹಿತಿಯಲ್ಲಿ ಮಾತ್ರ ಸಹಾಯ ಮಾಡಬಲ್ಲೆ. ದಯವಿಟ್ಟು ಇವುಗಳಲ್ಲಿ ಒಂದನ್ನು ಕೇಳಿ."
    ),
}


def assess_scope(
    text: str,
    *,
    pending_slot: object | None = None,
    has_structured_slots: bool = False,
    known_intent: object | None = None,
) -> ScopeDecision:
    """Return whether an utterance belongs to Sahaayak's bounded purpose."""
    normalized = " ".join(text.strip().split())
    if not normalized:
        return ScopeDecision(False, "empty_input")
    if _PROMPT_INJECTION_MARKERS.search(normalized):
        return ScopeDecision(False, "prompt_injection_pattern")
    if _UNSUPPORTED_REQUEST_MARKERS.search(normalized):
        return ScopeDecision(False, "outside_product_scope")
    if pending_slot is not None or has_structured_slots or known_intent is not None:
        return ScopeDecision(True)
    if _PRODUCT_MARKERS.search(normalized) or _CONVERSATION_MARKERS.search(normalized):
        return ScopeDecision(True)
    return ScopeDecision(False, "outside_product_scope")


def out_of_scope_message(language_code: str | None) -> str:
    """Return a fixed, non-model-generated redirect for the caller."""
    return _OUT_OF_SCOPE_MESSAGES.get(
        (language_code or "en").lower(), _OUT_OF_SCOPE_MESSAGES["en"]
    )


__all__ = ["ScopeDecision", "assess_scope", "out_of_scope_message"]
