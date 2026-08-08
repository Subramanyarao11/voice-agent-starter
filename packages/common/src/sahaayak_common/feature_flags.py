"""Bounded feature-flag defaults and deterministic rollout evaluation."""

from __future__ import annotations

import hashlib
from typing import Any

from sqlmodel import select

from sahaayak_common.db import session_scope
from sahaayak_common.models import FeatureFlag

DEFAULT_FEATURE_FLAGS: dict[str, dict[str, Any]] = {
    "voice_streaming": {
        "description": "Browser streaming voice with local VAD and interruption support.",
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
