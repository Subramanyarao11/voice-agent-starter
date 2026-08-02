"""Optional library-level OpenTelemetry instrumentation."""

from __future__ import annotations

from sahaayak_agent.tracing import get_otel_tracer_provider
from sahaayak_common import engine, get_logger, settings

log = get_logger(__name__)
_instrumented = False


def configure_library_instrumentation() -> None:
    global _instrumented
    if _instrumented or not settings.otel_enabled:
        return
    provider = get_otel_tracer_provider()
    if provider is None:
        return
    try:
        from opentelemetry.instrumentation.redis import RedisInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

        SQLAlchemyInstrumentor().instrument(engine=engine, tracer_provider=provider)
        RedisInstrumentor().instrument(tracer_provider=provider)
        _instrumented = True
        log.info("otel_library_instrumentation_configured", libraries="sqlalchemy,redis")
    except Exception as exc:  # pragma: no cover - optional deployment packages
        log.warning("otel_library_instrumentation_failed", error=exc.__class__.__name__)


def shutdown_library_instrumentation() -> None:
    global _instrumented
    if not _instrumented:
        return
    try:
        from opentelemetry.instrumentation.redis import RedisInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

        SQLAlchemyInstrumentor().uninstrument()
        RedisInstrumentor().uninstrument()
    except Exception as exc:  # pragma: no cover - optional deployment packages
        log.warning("otel_library_instrumentation_shutdown_failed", error=exc.__class__.__name__)
    finally:
        _instrumented = False
