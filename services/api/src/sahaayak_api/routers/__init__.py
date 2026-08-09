"""HTTP routes, grouped by what they are for."""

from sahaayak_api.routers import (
    admin,
    admin_directory,
    applications,
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
    "admin_directory",
    "applications",
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
