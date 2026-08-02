"""Liveness and a readable view of which optional pieces are configured."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlmodel import Session, func, select

from sahaayak_agent.prompts import supported_languages
from sahaayak_common import (
    RedisCache,
    TelemetryEvent,
    UserSession,
    engine,
    get_logger,
    get_session,
    settings,
)

log = get_logger(__name__)

router = APIRouter(tags=["health"])


class HealthReport(BaseModel):
    status: str
    environment: str
    database: str
    cache: str
    # Reported rather than asserted: the app runs without these, in a reduced
    # mode, and hiding that would make a text-only deployment look broken.
    speech_to_text: bool
    text_to_speech: bool
    reasoning_model: bool
    tracing: bool
    languages: list[str]


@router.get("/health", response_model=HealthReport)
async def health() -> HealthReport:
    database = "ok"
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:
        database = f"unavailable: {exc.__class__.__name__}"
        log.warning("health_database_unreachable", error=str(exc))

    cache = "memory"
    if settings.redis_url:
        cache = "redis" if await RedisCache(settings.redis_url).ping() else "memory (redis down)"

    return HealthReport(
        status="ok" if database == "ok" else "degraded",
        environment=settings.env,
        database=database,
        cache=cache,
        speech_to_text=settings.llm_enabled,
        text_to_speech=settings.tts_enabled,
        reasoning_model=settings.llm_enabled,
        tracing=settings.tracing_enabled or settings.otel_enabled,
        languages=supported_languages(),
    )


@router.get("/readyz")
async def ready(response: Response) -> dict[str, str]:
    """Readiness probe used by the reverse proxy and deployment monitor.

    Liveness remains deliberately cheap at ``/health``. Readiness fails when
    the shared database is unavailable or production has configured Redis but
    the cache cannot be reached.
    """
    database_ok = True
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        database_ok = False
    cache_ok = not settings.redis_url or await RedisCache(settings.redis_url).ping()
    if not database_ok or not cache_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "not_ready",
            "database": "ok" if database_ok else "down",
            "cache": "ok" if cache_ok else "down",
        }
    return {"status": "ready", "database": "ok", "cache": "ok"}


@router.get("/metrics", response_class=PlainTextResponse)
async def metrics(db: Session = Depends(get_session)) -> str:
    """Expose aggregate, privacy-safe Prometheus text metrics.

    Labels intentionally exclude session IDs, IP addresses, languages, and
    provider names. Detailed traces remain in the configured OTel/Langfuse
    backend; this endpoint is for alert thresholds only.
    """
    now = datetime.now(UTC)
    window = now - timedelta(minutes=5)
    requests = int(
        db.exec(
            select(func.count())
            .select_from(TelemetryEvent)
            .where(TelemetryEvent.event_type == "http", TelemetryEvent.created_at >= window)
        ).one()
        or 0
    )
    errors = int(
        db.exec(
            select(func.count())
            .select_from(TelemetryEvent)
            .where(
                TelemetryEvent.event_type == "http",
                TelemetryEvent.created_at >= window,
                TelemetryEvent.status_code >= 500,
            )
        ).one()
        or 0
    )
    active_sessions = int(
        db.exec(
            select(func.count())
            .select_from(UserSession)
            .where(UserSession.last_contact_at >= now - timedelta(minutes=30))
        ).one()
        or 0
    )
    health_report = await health()
    lines = [
        "# HELP sahaayak_http_requests_total HTTP requests observed in the last five minutes.",
        "# TYPE sahaayak_http_requests_total gauge",
        f"sahaayak_http_requests_total {requests}",
        "# HELP sahaayak_http_errors_total HTTP 5xx responses observed in the last five minutes.",
        "# TYPE sahaayak_http_errors_total gauge",
        f"sahaayak_http_errors_total {errors}",
        "# HELP sahaayak_active_sessions Active sessions contacted in the last thirty minutes.",
        "# TYPE sahaayak_active_sessions gauge",
        f"sahaayak_active_sessions {active_sessions}",
        "# HELP sahaayak_database_up Whether the database health check passed.",
        "# TYPE sahaayak_database_up gauge",
        f"sahaayak_database_up {1 if health_report.database == 'ok' else 0}",
        "# HELP sahaayak_cache_up Whether the configured cache health check passed.",
        "# TYPE sahaayak_cache_up gauge",
        f"sahaayak_cache_up {1 if health_report.cache in {'redis', 'memory'} else 0}",
    ]
    return "\n".join(lines) + "\n"
