"""Request correlation.

Every response carries an X-Request-ID, and the same value is bound into the
log context, so one identifier follows a turn across the API, the graph nodes,
and the provider calls.
"""

from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from sahaayak_agent.tracing import (
    clear_trace_context,
    record_http_metric,
    start_span,
)
from sahaayak_api.telemetry import record_telemetry
from sahaayak_common import get_logger, new_id, request_id_var, settings

log = get_logger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add browser hardening headers to direct API responses as well as Nginx."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy", "microphone=(self), camera=(), geolocation=()"
        )
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-site")
        if settings.is_production:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Honour an inbound ID so a telephony provider's trace and ours line up.
        request_id = request.headers.get(REQUEST_ID_HEADER) or new_id("req")
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        surface = (
            "admin"
            if request.url.path.startswith("/api/admin")
            else "citizen"
            if request.url.path.startswith("/api")
            else "system"
        )

        with start_span(
            "http.request",
            {
                "http.request.method": request.method,
                "url.path": request.url.path,
                "sahaayak.surface": surface,
            },
        ) as span:
            try:
                response = await call_next(request)
            except Exception as exc:
                if span is not None:
                    span.record_exception(exc)
                    span.set_attribute("error.type", exc.__class__.__name__)
                log.exception(
                    "request_failed",
                    method=request.method,
                    path=request.url.path,
                    duration_ms=round((time.perf_counter() - started) * 1000, 1),
                )
                raise
            finally:
                status_code = response.status_code if "response" in locals() else 500
                duration_ms = (time.perf_counter() - started) * 1000
                if span is not None:
                    span.set_attribute("http.response.status_code", status_code)
                    span.set_attribute("http.server.duration_ms", round(duration_ms, 2))
                record_telemetry(
                    event_type="http",
                    route=request.url.path,
                    method=request.method,
                    status_code=status_code,
                    duration_ms=duration_ms,
                    surface=surface,
                    outcome="error" if status_code >= 500 else "success",
                    error_code=str(status_code) if status_code >= 400 else None,
                )
                record_http_metric(
                    duration_ms,
                    route=request.url.path,
                    status_code=status_code,
                    surface=surface,
                )
                clear_trace_context()
                request_id_var.reset(token)

        response.headers[REQUEST_ID_HEADER] = request_id
        log.info(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=round((time.perf_counter() - started) * 1000, 1),
        )
        return response
