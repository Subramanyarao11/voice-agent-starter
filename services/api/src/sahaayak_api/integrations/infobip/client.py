"""The shared Infobip HTTP client.

One long-lived async client per process. Building a new client per message
would re-establish TLS on every reminder, which on a queue drain is both slow
and a good way to exhaust local ports.

Nothing in this module knows what a reminder is. It moves JSON, applies the
retry policy, normalizes failures, and refuses to log anything that could
identify a recipient.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from sahaayak_agent.tracing import start_span
from sahaayak_api.integrations.infobip import retry as retry_policy
from sahaayak_api.integrations.infobip.config import InfobipConfig
from sahaayak_api.integrations.infobip.errors import (
    InfobipError,
    classify_status,
    parse_retry_after,
    refine_error_class,
)
from sahaayak_api.integrations.infobip.models import InfobipRequestError
from sahaayak_common import get_logger, new_id, request_id_var, settings
from sahaayak_contracts import ProviderErrorClass

log = get_logger(__name__)

# Provider error text is written by the provider, may quote our request, and is
# surfaced in the admin console. Truncate it so a verbose upstream message
# cannot flood a telemetry row or a log line.
MAX_ERROR_DETAIL = 240


@dataclass(slots=True)
class InfobipResponse:
    """A completed Infobip exchange, successful or not."""

    status_code: int
    payload: dict[str, Any] = field(default_factory=dict)
    error_class: ProviderErrorClass = ProviderErrorClass.NONE
    error_detail: str = ""
    provider_error_code: str = ""
    retry_after_seconds: int | None = None
    attempts: int = 1
    duration_ms: float = 0.0
    correlation_id: str = ""

    @property
    def ok(self) -> bool:
        return self.error_class is ProviderErrorClass.NONE

    @property
    def retryable(self) -> bool:
        return self.error_class in (
            ProviderErrorClass.TIMEOUT,
            ProviderErrorClass.NETWORK,
            ProviderErrorClass.RATE_LIMITED,
            ProviderErrorClass.PROVIDER_ERROR,
        )


class InfobipClient:
    """Transport for every Infobip channel adapter.

    The ``transport`` argument exists so tests drive the full retry and
    normalization path against ``httpx.MockTransport`` rather than a stubbed
    client — the code under test is then the code that ships.
    """

    def __init__(
        self,
        config: InfobipConfig | None = None,
        *,
        transport: httpx.BaseTransport | httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._config = config or InfobipConfig.from_settings()
        self._transport = transport
        self._client: httpx.AsyncClient | None = None
        self._lock = asyncio.Lock()

    @property
    def config(self) -> InfobipConfig:
        return self._config

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is not None:
            return self._client
        async with self._lock:
            if self._client is None:
                self._client = httpx.AsyncClient(
                    base_url=self._config.base_url,
                    timeout=httpx.Timeout(
                        connect=min(5.0, self._config.timeout_seconds),
                        read=self._config.timeout_seconds,
                        write=self._config.timeout_seconds,
                        pool=self._config.timeout_seconds,
                    ),
                    headers={
                        "Authorization": self._config.authorization_header(),
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                    },
                    transport=self._transport,  # type: ignore[arg-type]
                )
        return self._client

    async def aclose(self) -> None:
        client, self._client = self._client, None
        if client is not None:
            await client.aclose()

    async def post(
        self,
        path: str,
        payload: dict[str, Any],
        *,
        operation: str,
        channel: str,
        idempotency_key: str = "",
    ) -> InfobipResponse:
        return await self.request(
            "POST",
            path,
            payload=payload,
            operation=operation,
            channel=channel,
            idempotency_key=idempotency_key,
        )

    async def request(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        operation: str,
        channel: str,
        idempotency_key: str = "",
    ) -> InfobipResponse:
        if not self._config.configured:
            raise InfobipError(
                "Infobip is not configured",
                error_class=ProviderErrorClass.NOT_CONFIGURED,
            )

        # Correlates our logs, the provider's records, and the delivery row
        # without carrying any recipient data across the boundary.
        correlation_id = request_id_var.get() or new_id("ifb")
        headers = {"X-Request-ID": correlation_id}
        if idempotency_key:
            headers["X-Idempotency-Key"] = idempotency_key

        client = await self._get_client()
        started = time.perf_counter()
        attempt = 0
        last: InfobipResponse | None = None

        with start_span(
            "infobip.request",
            {
                "sahaayak.provider": "infobip",
                "sahaayak.channel": channel,
                "sahaayak.operation": operation,
                "http.request.method": method,
                "url.path": path,
            },
        ) as span:
            while True:
                attempt += 1
                result = await self._attempt(
                    client,
                    method,
                    path,
                    payload=payload,
                    headers=headers,
                    attempt=attempt,
                )
                last = result

                decision = retry_policy.decide(
                    error_class=result.error_class,
                    attempt=attempt,
                    max_retries=self._config.max_retries,
                    retry_after_seconds=result.retry_after_seconds,
                    idempotent=bool(idempotency_key),
                )
                if not decision.should_retry:
                    break

                log.info(
                    "infobip_request_retrying",
                    channel=channel,
                    operation=operation,
                    attempt=attempt,
                    delay_seconds=decision.delay_seconds,
                    reason=decision.reason,
                    error_class=result.error_class.value,
                    correlation_id=correlation_id,
                )
                await asyncio.sleep(decision.delay_seconds)

            assert last is not None
            last.attempts = attempt
            last.duration_ms = round((time.perf_counter() - started) * 1000, 2)
            last.correlation_id = correlation_id

            if span is not None:
                span.set_attribute("sahaayak.attempts", attempt)
                span.set_attribute("sahaayak.status_group", last.error_class.value)
                span.set_attribute("http.response.status_code", last.status_code)

            self._log_outcome(last, channel=channel, operation=operation, path=path)
            return last

    async def _attempt(
        self,
        client: httpx.AsyncClient,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None,
        headers: dict[str, str],
        attempt: int,
    ) -> InfobipResponse:
        try:
            response = await client.request(
                method, path, json=payload, headers=headers
            )
        except httpx.TimeoutException as exc:
            return InfobipResponse(
                status_code=0,
                error_class=ProviderErrorClass.TIMEOUT,
                error_detail=exc.__class__.__name__,
                attempts=attempt,
            )
        except httpx.HTTPError as exc:
            return InfobipResponse(
                status_code=0,
                error_class=ProviderErrorClass.NETWORK,
                error_detail=exc.__class__.__name__,
                attempts=attempt,
            )

        return self._normalize(response, attempt=attempt)

    def _normalize(self, response: httpx.Response, *, attempt: int) -> InfobipResponse:
        body: dict[str, Any] = {}
        parse_failed = False
        if response.content:
            try:
                parsed = response.json()
            except (json.JSONDecodeError, ValueError):
                parse_failed = True
            else:
                body = parsed if isinstance(parsed, dict) else {"data": parsed}

        error_class = classify_status(response.status_code)
        if error_class is ProviderErrorClass.NONE and parse_failed:
            # A 200 we cannot parse is not a success: we have no message ID to
            # reconcile the eventual delivery report against.
            error_class = ProviderErrorClass.MALFORMED_RESPONSE

        detail = ""
        provider_error_code = ""
        if error_class is not ProviderErrorClass.NONE:
            request_error = InfobipRequestError.from_payload(body)
            if request_error is not None:
                detail = request_error.text
                provider_error_code = request_error.message_id
            elif parse_failed:
                detail = "unparseable response body"
            error_class = refine_error_class(
                error_class,
                provider_error_code=provider_error_code,
                description=detail,
            )

        return InfobipResponse(
            status_code=response.status_code,
            payload=body,
            error_class=error_class,
            error_detail=detail[:MAX_ERROR_DETAIL],
            provider_error_code=provider_error_code,
            retry_after_seconds=parse_retry_after(response.headers.get("Retry-After")),
            attempts=attempt,
        )

    def _log_outcome(
        self, result: InfobipResponse, *, channel: str, operation: str, path: str
    ) -> None:
        """Log the shape of the exchange and nothing about who it was for.

        Deliberately omits the request and response bodies. Both contain the
        destination and the message text, and a provider integration is exactly
        the place where those leak into an aggregator by accident.
        """
        fields = {
            "provider": "infobip",
            "channel": channel,
            "operation": operation,
            "path": path,
            "status_code": result.status_code,
            "attempts": result.attempts,
            "duration_ms": result.duration_ms,
            "correlation_id": result.correlation_id,
            "environment": self._config.environment,
        }
        if result.ok:
            log.info("infobip_request_ok", **fields)
            return
        log.warning(
            "infobip_request_failed",
            error_class=result.error_class.value,
            provider_error_code=result.provider_error_code,
            error_detail=result.error_detail,
            **fields,
        )


_client: InfobipClient | None = None


def get_infobip_client() -> InfobipClient | None:
    """The process-wide client, or None when Infobip is off or unconfigured."""
    global _client
    if not settings.infobip_ready:
        return None
    if _client is None:
        _client = InfobipClient()
    return _client


async def shutdown_infobip_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


def reset_infobip_client() -> None:
    """Drop the cached client between tests without awaiting a close."""
    global _client
    _client = None
