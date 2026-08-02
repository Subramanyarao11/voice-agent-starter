"""Request correlation.

Every response carries an X-Request-ID, and the same value is bound into the
log context, so one identifier follows a turn across the API, the graph nodes,
and the provider calls.
"""

from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from sahaayak_api.telemetry import record_telemetry
from sahaayak_common import get_logger, new_id, request_id_var

log = get_logger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Honour an inbound ID so a telephony provider's trace and ours line up.
        request_id = request.headers.get(REQUEST_ID_HEADER) or new_id("req")
        token = request_id_var.set(request_id)
        started = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            log.exception(
                "request_failed",
                method=request.method,
                path=request.url.path,
                duration_ms=round((time.perf_counter() - started) * 1000, 1),
            )
            raise
        finally:
            record_telemetry(
                event_type="http",
                route=request.url.path,
                method=request.method,
                status_code=response.status_code if "response" in locals() else 500,
                duration_ms=(time.perf_counter() - started) * 1000,
                surface=("admin" if request.url.path.startswith("/api/admin") else "system"),
                outcome=(
                    "error"
                    if "response" not in locals() or response.status_code >= 500
                    else "success"
                ),
                error_code=(
                    str(response.status_code)
                    if "response" in locals() and response.status_code >= 400
                    else None
                ),
            )
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
