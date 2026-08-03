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
    # Messaging channels default to disabled. Unlike the model providers above,
    # these spend money per message and reach a person's phone, so the safe
    # default is off until an operator turns one on deliberately — and each
    # falls back to in-app rather than to another paid channel.
    ("email", "*"): {
        "enabled": False,
        "primary_provider": "infobip_email",
        "fallback_provider": "in_app",
        "circuit_state": "closed",
    },
    ("sms", "*"): {
        "enabled": False,
        "primary_provider": "infobip_sms",
        "fallback_provider": "in_app",
        "circuit_state": "closed",
    },
    ("whatsapp", "*"): {
        "enabled": False,
        "primary_provider": "infobip_whatsapp",
        # Deliberately in-app and not SMS. Falling back from WhatsApp to a
        # charged channel requires separate SMS consent, which the caller may
        # not have given, so that route is opted into per contact rather than
        # assumed here.
        "fallback_provider": "in_app",
        "circuit_state": "closed",
    },
    ("telephony", "*"): {
        "enabled": False,
        "primary_provider": "infobip_calls",
        "fallback_provider": "browser_voice_or_text",
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
    # Every attribute is read inside the session. Reading them after the block
    # closed worked only while no policy row existed: the moment an operator
    # saves one, the rows come back detached and touching `.scope` raises.
    with session_scope() as db:
        rows = db.exec(
            select(ProviderPolicy).where(
                ProviderPolicy.provider == provider,
                ProviderPolicy.scope.in_([scope, "*"]),
            )
        ).all()

        # A scope-specific policy wins over the wildcard, so a per-locale
        # override is not silently outranked by the global default.
        row = next((item for item in rows if item.scope == scope), None) or next(
            (item for item in rows if item.scope == "*"), None
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
