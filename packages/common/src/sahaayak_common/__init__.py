"""Infrastructure shared by every Sahaayak service."""

from sahaayak_common.cache import Cache, InMemoryCache, RedisCache, get_cache, reset_cache
from sahaayak_common.db import engine, get_session, init_db, run_migrations, session_scope
from sahaayak_common.ids import new_id, session_id, slugify, ticket_id, turn_id
from sahaayak_common.logging import configure_logging, get_logger, request_id_var
from sahaayak_common.models import (
    AuditEvent,
    Benefit,
    ConversationTurnLog,
    DataImportRun,
    EscalationTicket,
    Language,
    State,
    TelemetryEvent,
    UserSession,
)
from sahaayak_common.openai_budget import (
    BudgetError,
    BudgetExceeded,
    BudgetReservation,
    OpenAIBudgetLedger,
)
from sahaayak_common.settings import REPO_ROOT, Settings, get_settings, settings

__all__ = [
    "REPO_ROOT",
    "AuditEvent",
    "Benefit",
    "BudgetError",
    "BudgetExceeded",
    "BudgetReservation",
    "Cache",
    "ConversationTurnLog",
    "DataImportRun",
    "EscalationTicket",
    "InMemoryCache",
    "Language",
    "OpenAIBudgetLedger",
    "RedisCache",
    "Settings",
    "State",
    "TelemetryEvent",
    "UserSession",
    "configure_logging",
    "engine",
    "get_cache",
    "get_logger",
    "get_session",
    "get_settings",
    "init_db",
    "new_id",
    "request_id_var",
    "reset_cache",
    "run_migrations",
    "session_id",
    "session_scope",
    "settings",
    "slugify",
    "ticket_id",
    "turn_id",
]
