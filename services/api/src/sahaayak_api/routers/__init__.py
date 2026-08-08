"""HTTP routes, grouped by what they are for."""

from sahaayak_api.routers import (
    admin,
    benefit_feedback,
    browser_sessions,
    catalog,
    escalations,
    health,
    rag,
    saved_benefits,
    sessions,
    telephony,
    turns,
    voice_stream,
)

__all__ = [
    "admin",
    "benefit_feedback",
    "browser_sessions",
    "catalog",
    "escalations",
    "health",
    "rag",
    "saved_benefits",
    "sessions",
    "telephony",
    "turns",
    "voice_stream",
]
