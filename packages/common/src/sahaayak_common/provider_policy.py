"""Effective provider policy lookup shared by runtime and admin tooling."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlmodel import select

from sahaayak_common.db import session_scope
from sahaayak_common.models import ProviderPolicy

DEFAULT_PROVIDER_POLICIES: dict[tuple[str, str], dict[str, Any]] = {
    ("stt", "*"): {
        "enabled": True,
        "primary_provider": "openai_whisper",
        "fallback_provider": "none",
        "circuit_state": "closed",
    },
    ("tts", "*"): {
        "enabled": True,
        "primary_provider": "sarvam_bulbul",
        "fallback_provider": "text_only",
        "circuit_state": "closed",
    },
    ("rag", "*"): {
        "enabled": True,
        "primary_provider": "openai_vector_store",
        "fallback_provider": "structured_matcher",
        "circuit_state": "closed",
    },
    ("reasoning", "*"): {
        "enabled": True,
        "primary_provider": "openai_reasoning",
        "fallback_provider": "rules",
        "circuit_state": "closed",
    },
}


def get_effective_provider_policy(provider: str, scope: str = "*") -> dict[str, Any]:
    """Return a safe policy snapshot, falling back to built-in defaults."""
    default = dict(DEFAULT_PROVIDER_POLICIES.get((provider, "*"), {
        "enabled": True,
        "primary_provider": provider,
        "fallback_provider": "none",
        "circuit_state": "closed",
    }))
    with session_scope() as db:
        row = db.exec(
            select(ProviderPolicy).where(
                ProviderPolicy.provider == provider,
                ProviderPolicy.scope.in_([scope, "*"]),
            )
        ).all()
    row = next((item for item in row if item.scope == scope), None) or next(
        (item for item in row if item.scope == "*"), None
    )
    if row is None:
        return {"provider": provider, "scope": scope, **default, "revision": 0}

    if row.override_expires_at is not None:
        expires_at = row.override_expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= datetime.now(UTC):
            return {"provider": provider, "scope": scope, **default, "revision": row.revision}
    return {
        "provider": row.provider,
        "scope": row.scope,
        "enabled": row.enabled,
        "primary_provider": row.primary_provider,
        "fallback_provider": row.fallback_provider,
        "circuit_state": row.circuit_state,
        "daily_budget_usd": row.daily_budget_usd,
        "monthly_budget_usd": row.monthly_budget_usd,
        "override_expires_at": row.override_expires_at,
        "revision": row.revision,
    }
