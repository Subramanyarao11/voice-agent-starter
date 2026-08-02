"""Privacy-safe Langfuse and OpenTelemetry instrumentation.

Langfuse is the LLM/graph evidence surface; OpenTelemetry carries service
spans and metrics to an OTLP collector or compatible backend. Both are
optional and both are fail-open for application availability. Inputs,
outputs, transcripts, audio, and sensitive slot values are never exported by
the helpers in this module.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from contextlib import ExitStack, contextmanager
from contextvars import ContextVar
from functools import wraps
from inspect import iscoroutinefunction
from typing import Any, TypeVar, cast

from sahaayak_common import get_logger, request_id_var, settings

log = get_logger(__name__)

F = TypeVar("F", bound=Callable[..., Any])

_langfuse_trace_id: ContextVar[str | None] = ContextVar("langfuse_trace_id", default=None)
_langfuse_trace_url: ContextVar[str | None] = ContextVar("langfuse_trace_url", default=None)
_otel_tracer_provider: Any = None
_otel_meter_provider: Any = None
_http_duration: Any = None
_turn_duration: Any = None
_turn_count: Any = None


def _safe_metadata(value: Mapping[str, Any] | None) -> dict[str, str | int | float | bool]:
    if not value:
        return {}
    safe: dict[str, str | int | float | bool] = {}
    for key, item in value.items():
        if len(safe) >= 12 or not isinstance(key, str) or len(key) > 64:
            continue
        if isinstance(item, (str, int, float, bool)):
            safe[key] = str(item)[:160] if isinstance(item, str) else item
    return safe


def _parse_headers(raw: str) -> dict[str, str]:
    headers: dict[str, str] = {}
    for item in raw.split(","):
        key, separator, value = item.partition("=")
        if separator and key.strip() and value.strip():
            headers[key.strip()] = value.strip()
    return headers


def _endpoint(base: str, explicit: str, suffix: str) -> str:
    if explicit.strip():
        return explicit.strip()
    if not base.strip():
        return ""
    return f"{base.rstrip('/')}{suffix}"


def configure_observability() -> None:
    """Install the process-wide OTel providers once, if configured."""
    global _otel_meter_provider, _otel_tracer_provider
    if _otel_tracer_provider is not None or not settings.otel_enabled:
        return
    try:
        from opentelemetry import metrics, trace
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import (
            ConsoleMetricExporter,
            PeriodicExportingMetricReader,
        )
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import (
            BatchSpanProcessor,
            ConsoleSpanExporter,
            SimpleSpanProcessor,
        )
        from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

        resource = Resource.create(
            {
                "service.name": settings.otel_service_name,
                "service.version": "0.1.0",
                "deployment.environment": settings.env,
            }
        )
        sampler = TraceIdRatioBased(min(1.0, max(0.0, settings.otel_sample_ratio)))
        tracer_provider = TracerProvider(resource=resource, sampler=sampler)
        trace_endpoint = _endpoint(
            settings.otel_exporter_otlp_endpoint,
            settings.otel_exporter_otlp_traces_endpoint,
            "/v1/traces",
        )
        metric_endpoint = _endpoint(
            settings.otel_exporter_otlp_endpoint,
            settings.otel_exporter_otlp_metrics_endpoint,
            "/v1/metrics",
        )
        headers = _parse_headers(settings.otel_exporter_otlp_headers)
        if trace_endpoint:
            tracer_provider.add_span_processor(
                BatchSpanProcessor(OTLPSpanExporter(endpoint=trace_endpoint, headers=headers))
            )
        if settings.otel_console_exporter:
            tracer_provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
        trace.set_tracer_provider(tracer_provider)

        readers = []
        if metric_endpoint:
            readers.append(
                PeriodicExportingMetricReader(
                    OTLPMetricExporter(endpoint=metric_endpoint, headers=headers),
                    export_interval_millis=15_000,
                )
            )
        if settings.otel_console_exporter:
            readers.append(
                PeriodicExportingMetricReader(
                    ConsoleMetricExporter(), export_interval_millis=15_000
                )
            )
        meter_provider = MeterProvider(resource=resource, metric_readers=readers)
        metrics.set_meter_provider(meter_provider)
        _otel_tracer_provider = tracer_provider
        _otel_meter_provider = meter_provider
        _init_metrics()
        log.info(
            "otel_configured",
            service=settings.otel_service_name,
            traces=bool(trace_endpoint or settings.otel_console_exporter),
            metrics=bool(metric_endpoint or settings.otel_console_exporter),
        )
    except Exception as exc:  # pragma: no cover - depends on deployment SDK/config
        log.warning("otel_configuration_failed", error=exc.__class__.__name__)


def shutdown_observability() -> None:
    """Flush exporters during an orderly API shutdown."""
    if _otel_tracer_provider is not None:
        try:
            _otel_tracer_provider.force_flush()
            _otel_tracer_provider.shutdown()
        except Exception as exc:  # pragma: no cover - exporter failure path
            log.warning("otel_shutdown_failed", error=exc.__class__.__name__)
    if _otel_meter_provider is not None:
        try:
            _otel_meter_provider.force_flush()
            _otel_meter_provider.shutdown()
        except Exception as exc:  # pragma: no cover - exporter failure path
            log.warning("otel_metric_shutdown_failed", error=exc.__class__.__name__)
    if settings.tracing_enabled:
        try:
            from langfuse import get_client

            get_client().flush()
        except Exception as exc:  # pragma: no cover - optional SDK/network path
            log.warning("langfuse_flush_failed", error=exc.__class__.__name__)


def get_otel_tracer_provider() -> Any:
    return _otel_tracer_provider


@contextmanager
def start_span(name: str, attributes: Mapping[str, Any] | None = None) -> Iterator[Any]:
    """Start an OTel span with bounded primitive attributes."""
    try:
        from opentelemetry import trace

        tracer = trace.get_tracer("sahaayak")
        with tracer.start_as_current_span(name) as span:
            for key, value in _safe_metadata(attributes).items():
                span.set_attribute(key, value)
            yield span
    except ImportError:
        yield None


def current_otel_trace_id() -> str | None:
    try:
        from opentelemetry import trace

        context = trace.get_current_span().get_span_context()
        return f"{context.trace_id:032x}" if context.is_valid else None
    except ImportError:
        return None


def current_langfuse_trace() -> tuple[str | None, str | None]:
    return _langfuse_trace_id.get(), _langfuse_trace_url.get()


def clear_trace_context() -> None:
    _langfuse_trace_id.set(None)
    _langfuse_trace_url.set(None)


def _init_metrics() -> None:
    global _http_duration, _turn_duration, _turn_count
    if _otel_meter_provider is None or _http_duration is not None:
        return
    try:
        from opentelemetry import metrics

        meter = metrics.get_meter("sahaayak")
        _http_duration = meter.create_histogram(
            "http.server.duration", unit="ms", description="HTTP request duration"
        )
        _turn_duration = meter.create_histogram(
            "sahaayak.turn.duration", unit="ms", description="Conversation turn duration"
        )
        _turn_count = meter.create_counter(
            "sahaayak.turn.count", description="Conversation turns processed"
        )
    except Exception as exc:  # pragma: no cover - optional SDK path
        log.warning("otel_metrics_initialization_failed", error=exc.__class__.__name__)


def record_http_metric(duration_ms: float, *, route: str, status_code: int, surface: str) -> None:
    if _http_duration is not None:
        _http_duration.record(
            duration_ms,
            {"http.route": route[:120], "http.status_code": status_code, "surface": surface},
        )


def record_turn_metric(
    duration_ms: float,
    *,
    surface: str,
    language_code: str,
    outcome: str,
) -> None:
    attributes = {
        "surface": surface,
        "language": language_code[:16],
        "outcome": outcome[:32],
    }
    if _turn_duration is not None:
        _turn_duration.record(duration_ms, attributes)
    if _turn_count is not None:
        _turn_count.add(1, attributes)


def _load_observe() -> Callable | None:
    """Find Langfuse's decorator across supported SDK layouts."""
    try:
        from langfuse import observe

        return observe
    except ImportError:
        pass
    try:
        from langfuse.decorators import observe

        return observe
    except ImportError:
        return None


@contextmanager
def langfuse_turn(
    *, session_id: str, metadata: Mapping[str, Any] | None = None
) -> Iterator[Any]:
    """Create one redacted root observation around a complete graph turn."""
    if not settings.tracing_enabled:
        yield None
        return
    stack: ExitStack | None = None
    try:
        from langfuse import get_client, propagate_attributes

        stack = ExitStack()
        client = get_client()
        safe = _safe_metadata({"request_id": request_id_var.get(), **(metadata or {})})
        observation = stack.enter_context(
            client.start_as_current_observation(
                as_type="span",
                name="conversation.turn",
                metadata=safe,
            )
        )
        stack.enter_context(
            propagate_attributes(
                session_id=session_id,
                metadata=safe,
                trace_name="sahaayak.turn",
                environment=settings.env,
                tags=["sahaayak", "conversation"],
            )
        )
        trace_id = client.get_current_trace_id()
        _langfuse_trace_id.set(trace_id)
        _langfuse_trace_url.set(client.get_trace_url(trace_id=trace_id) if trace_id else None)
    except Exception as exc:  # pragma: no cover - optional SDK/config path
        log.warning("langfuse_root_trace_unavailable", error=exc.__class__.__name__)
        if stack is not None:
            stack.close()
        yield None
        return

    try:
        yield observation
    finally:
        if stack is not None:
            stack.close()


def update_langfuse_observation(observation: Any, metadata: Mapping[str, Any]) -> None:
    if observation is None:
        return
    try:
        observation.update(metadata=_safe_metadata(metadata))
    except Exception as exc:  # pragma: no cover - optional SDK path
        log.debug("langfuse_observation_update_failed", error=exc.__class__.__name__)


def traced(name: str) -> Callable[[F], F]:
    """Wrap a graph node in a redacted Langfuse observation and OTel span."""

    def decorator(func: F) -> F:
        observed: Callable[..., Any] = func
        if settings.tracing_enabled:
            observe = _load_observe()
            if observe is None:
                log.warning("langfuse_not_installed", node=name)
            else:
                try:
                    observed = observe(
                        name=name,
                        as_type="span",
                        capture_input=False,
                        capture_output=False,
                    )(observed)
                except Exception as exc:
                    log.warning("tracing_decorator_failed", node=name, error=exc.__class__.__name__)

        if not settings.otel_enabled:
            return cast(F, observed)
        if iscoroutinefunction(observed):

            @wraps(observed)
            async def async_node(*args: Any, **kwargs: Any) -> Any:
                with start_span(f"agent.node.{name}", {"agent.node": name}):
                    return await observed(*args, **kwargs)

            return cast(F, async_node)

        @wraps(observed)
        def sync_node(*args: Any, **kwargs: Any) -> Any:
            with start_span(f"agent.node.{name}", {"agent.node": name}):
                return observed(*args, **kwargs)

        return cast(F, sync_node)

    return decorator
