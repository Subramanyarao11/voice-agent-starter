"""Bounded feature-flag defaults and deterministic rollout evaluation."""

from __future__ import annotations

import hashlib
from typing import Any

from sqlmodel import select

from sahaayak_common.db import session_scope
from sahaayak_common.models import FeatureFlag, LanguageReadinessReview

DEFAULT_FEATURE_FLAGS: dict[str, dict[str, Any]] = {
    "language_rollout": {
        "description": "Core language availability with deterministic cohort rollout controls.",
        "enabled": True,
        "rollout_percentage": 100,
    },
    "state_rollout": {
        "description": "State-by-state product and data rollout controls.",
        "enabled": True,
        "rollout_percentage": 100,
        "target_states": ["KA", "DL"],
    },
    "voice_streaming": {
        "description": "Browser streaming voice with local VAD and interruption support.",
        "enabled": True,
        "rollout_percentage": 100,
    },
    "provider_stt": {
        "description": "Speech-to-text provider rollout and emergency kill switch.",
        "enabled": True,
        "rollout_percentage": 100,
    },
    "provider_tts": {
        "description": "Text-to-speech provider rollout and emergency kill switch.",
        "enabled": True,
        "rollout_percentage": 100,
    },
    "provider_rag": {
        "description": "Hosted retrieval provider rollout and emergency kill switch.",
        "enabled": True,
        "rollout_percentage": 100,
    },
    "government_jobs": {
        "description": "Government-job discovery surfaces for reviewed official postings.",
        "enabled": True,
        "rollout_percentage": 100,
    },
    "infobip_reminders": {
        "description": (
            "External SMS, WhatsApp, and email reminders after consent and provider approval."
        ),
        "enabled": False,
        "rollout_percentage": 0,
    },
    "ten_language_rollout": {
        "description": (
            "Staged rollout of the additional Indian-language interface and voice profiles."
        ),
        "enabled": False,
        "rollout_percentage": 0,
    },
    "application_copilot": {
        "description": (
            "Citizen application checklist and manually reported status journey "
            "for reviewed benefits."
        ),
        "enabled": True,
        "rollout_percentage": 100,
    },
    "application_pack": {
        "description": "On-demand, source-backed application preparation pack preview.",
        "enabled": True,
        "rollout_percentage": 100,
    },
    "application_status_sync": {
        "description": (
            "Authorized provider adapters that verify application status from official systems."
        ),
        "enabled": False,
        "rollout_percentage": 0,
    },
}


def ensure_default_feature_flags() -> None:
    """Create safe defaults without overwriting an operator's changes."""
    with session_scope() as db:
        for key, defaults in DEFAULT_FEATURE_FLAGS.items():
            if db.exec(select(FeatureFlag).where(FeatureFlag.key == key)).first() is not None:
                continue
            db.add(
                FeatureFlag(
                    id=f"flag:{key}",
                    key=key,
                    description=str(defaults["description"]),
                    enabled=bool(defaults["enabled"]),
                    rollout_percentage=int(defaults["rollout_percentage"]),
                    target_languages=list(defaults.get("target_languages", [])),
                    target_states=list(defaults.get("target_states", [])),
                )
            )


def feature_flag_enabled(
    key: str,
    *,
    subject: str = "",
    language_code: str | None = None,
    state_code: str | None = None,
) -> bool:
    """Evaluate a flag using a stable bucket, never a random per-request value."""
    with session_scope() as db:
        flag = db.exec(select(FeatureFlag).where(FeatureFlag.key == key)).first()
        if flag is None:
            defaults = DEFAULT_FEATURE_FLAGS.get(key)
            if defaults is None:
                return False
            enabled = bool(defaults["enabled"])
            percentage = int(defaults["rollout_percentage"])
            languages: list[str] = []
            states: list[str] = []
        else:
            enabled = flag.enabled
            percentage = flag.rollout_percentage
            languages = list(flag.target_languages)
            states = list(flag.target_states)

    if not enabled or percentage <= 0:
        return False
    if languages and language_code not in languages:
        return False
    if states and state_code not in states:
        return False
    if percentage >= 100:
        return True
    if not subject:
        return False
    bucket = int(hashlib.sha256(f"{key}:{subject}".encode()).hexdigest()[:8], 16) % 100
    return bucket < percentage


CORE_LANGUAGE_CODES = frozenset({"en", "hi", "kn"})


def language_rollout_enabled(
    code: str, *, subject: str = "", state_code: str | None = None
) -> bool:
    """Whether a language is currently available to this caller cohort."""
    normalized = code.strip().lower()
    if normalized not in CORE_LANGUAGE_CODES and not language_release_ready(normalized):
        return False
    key = "language_rollout" if normalized in CORE_LANGUAGE_CODES else "ten_language_rollout"
    return feature_flag_enabled(
        key,
        subject=subject,
        language_code=normalized,
        state_code=state_code,
    )


def language_release_ready(code: str) -> bool:
    """Require all release evidence before an expansion locale can roll out."""
    normalized = code.strip().lower()
    with session_scope() as db:
        review = db.get(LanguageReadinessReview, normalized)
        if review is None:
            return False
        return all(
            status == "approved"
            for status in (
                review.native_speaker_status,
                review.interface_status,
                review.prompt_status,
                review.content_status,
                review.understanding_status,
                review.voice_status,
                review.accessibility_status,
            )
        )


def state_rollout_enabled(code: str, *, subject: str = "") -> bool:
    """Whether a state is in the staged product/data rollout."""
    return feature_flag_enabled(
        "state_rollout",
        subject=subject,
        state_code=code.strip().upper(),
    )


def provider_rollout_enabled(
    provider_kind: str,
    *,
    subject: str = "",
    language_code: str | None = None,
    state_code: str | None = None,
) -> bool:
    """Evaluate a provider kill switch without knowing the provider vendor."""
    return feature_flag_enabled(
        f"provider_{provider_kind.strip().lower()}",
        subject=subject,
        language_code=language_code,
        state_code=state_code,
    )
