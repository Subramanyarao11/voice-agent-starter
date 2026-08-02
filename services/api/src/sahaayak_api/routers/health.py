"""Liveness and a readable view of which optional pieces are configured."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from sahaayak_agent.prompts import supported_languages
from sahaayak_common import RedisCache, engine, get_logger, settings

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
