"""HTTP routes, grouped by what they are for."""

from sahaayak_api.routers import (
    admin,
    browser_sessions,
    catalog,
    escalations,
    health,
    rag,
    sessions,
    turns,
)

__all__ = [
    "admin",
    "browser_sessions",
    "catalog",
    "escalations",
    "health",
    "rag",
    "sessions",
    "turns",
]
