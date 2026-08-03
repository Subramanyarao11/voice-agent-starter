"""Shared Infobip client: URL handling, retry policy, and error normalization.

Every case runs against ``httpx.MockTransport``, so the retry loop, the header
construction, and the response parsing under test are the ones that ship. No
test in this file reaches the network.
"""

from __future__ import annotations

import httpx
import pytest

from sahaayak_api.integrations.infobip import (
    InfobipClient,
    InfobipConfig,
    InfobipError,
    classify_status,
    join_url,
    normalize_base_url,
    parse_retry_after,
    refine_error_class,
)
from sahaayak_api.integrations.infobip import retry as retry_policy
from sahaayak_contracts import ProviderErrorClass

CONFIG = InfobipConfig(
    base_url="https://test.api.infobip.com",
    api_key="test-key",
    timeout_seconds=1.0,
    max_retries=2,
)


def build_client(handler, *, config: InfobipConfig = CONFIG) -> InfobipClient:
    return InfobipClient(config, transport=httpx.MockTransport(handler))


async def send(client: InfobipClient, **kwargs):
    return await client.post(
        "/sms/3/messages",
        {"messages": []},
        operation="send",
        channel="sms",
        **kwargs,
    )


# --- Base URL and headers -------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("abc.api.infobip.com", "https://abc.api.infobip.com"),
        ("https://abc.api.infobip.com", "https://abc.api.infobip.com"),
        ("https://abc.api.infobip.com/", "https://abc.api.infobip.com"),
        ("  abc.api.infobip.com  ", "https://abc.api.infobip.com"),
        ("http://localhost:8080", "http://localhost:8080"),
        ("", ""),
    ],
)
def test_base_url_is_normalized_to_an_origin(raw: str, expected: str) -> None:
    assert normalize_base_url(raw) == expected


def test_scheme_defaults_to_https_so_the_key_never_travels_in_the_clear() -> None:
    assert normalize_base_url("abc.api.infobip.com").startswith("https://")


def test_join_url_tolerates_slashes_on_either_side() -> None:
    assert join_url("https://a.infobip.com/", "/sms/3/messages") == (
        "https://a.infobip.com/sms/3/messages"
    )


def test_authorization_uses_the_infobip_app_scheme() -> None:
    assert CONFIG.authorization_header() == "App test-key"


async def test_request_sends_auth_and_correlation_headers() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(request.headers)
        return httpx.Response(200, json={"messages": [{"messageId": "m1"}]})

    result = await send(build_client(handler), idempotency_key="idem-1")

    assert result.ok
    assert seen["authorization"] == "App test-key"
    assert seen["x-idempotency-key"] == "idem-1"
    assert seen["x-request-id"]
    assert result.correlation_id == seen["x-request-id"]


async def test_unconfigured_client_raises_rather_than_calling_out() -> None:
    client = InfobipClient(InfobipConfig(base_url="", api_key=""))
    with pytest.raises(InfobipError) as excinfo:
        await send(client)
    assert excinfo.value.error_class is ProviderErrorClass.NOT_CONFIGURED


# --- Status classification ------------------------------------------------


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (200, ProviderErrorClass.NONE),
        (201, ProviderErrorClass.NONE),
        (400, ProviderErrorClass.INVALID_REQUEST),
        (401, ProviderErrorClass.AUTHENTICATION),
        (403, ProviderErrorClass.AUTHORIZATION),
        (429, ProviderErrorClass.RATE_LIMITED),
        (500, ProviderErrorClass.PROVIDER_ERROR),
        (503, ProviderErrorClass.PROVIDER_ERROR),
    ],
)
def test_status_codes_map_to_the_shared_taxonomy(
    status_code: int, expected: ProviderErrorClass
) -> None:
    assert classify_status(status_code) is expected


def test_invalid_destination_is_distinguished_from_a_generic_bad_request() -> None:
    refined = refine_error_class(
        ProviderErrorClass.INVALID_REQUEST,
        description="Invalid destination number",
    )
    assert refined is ProviderErrorClass.INVALID_DESTINATION


def test_template_rejection_is_distinguished_from_a_generic_bad_request() -> None:
    refined = refine_error_class(
        ProviderErrorClass.INVALID_REQUEST,
        description="DLT template not approved for this header",
    )
    assert refined is ProviderErrorClass.TEMPLATE_REJECTED


def test_server_errors_are_never_reclassified_as_content_problems() -> None:
    refined = refine_error_class(
        ProviderErrorClass.PROVIDER_ERROR, description="template service unavailable"
    )
    assert refined is ProviderErrorClass.PROVIDER_ERROR


@pytest.mark.parametrize(
    ("header", "expected"),
    [("30", 30), ("30.7", 30), (None, None), ("", None), ("soon", None), ("-5", None)],
)
def test_retry_after_parsing_ignores_values_it_cannot_trust(
    header: str | None, expected: int | None
) -> None:
    assert parse_retry_after(header) == expected


def test_retry_after_is_capped_so_a_bad_header_cannot_stall_a_queue() -> None:
    assert parse_retry_after("99999") == 3600


# --- Retry policy ---------------------------------------------------------


def test_timeouts_are_retried_with_backoff() -> None:
    decision = retry_policy.decide(
        error_class=ProviderErrorClass.TIMEOUT, attempt=1, max_retries=2, jitter=1.0
    )
    assert decision.should_retry
    assert decision.delay_seconds > 0


def test_rate_limiting_respects_the_provider_retry_after() -> None:
    decision = retry_policy.decide(
        error_class=ProviderErrorClass.RATE_LIMITED,
        attempt=1,
        max_retries=2,
        retry_after_seconds=7,
    )
    assert decision.should_retry
    assert decision.delay_seconds == 7


def test_server_errors_are_not_retried_without_an_idempotency_key() -> None:
    decision = retry_policy.decide(
        error_class=ProviderErrorClass.PROVIDER_ERROR, attempt=1, max_retries=2
    )
    assert not decision.should_retry
    assert decision.reason == "not_idempotent"


def test_server_errors_are_retried_when_the_send_is_idempotent() -> None:
    decision = retry_policy.decide(
        error_class=ProviderErrorClass.PROVIDER_ERROR,
        attempt=1,
        max_retries=2,
        idempotent=True,
        jitter=1.0,
    )
    assert decision.should_retry


@pytest.mark.parametrize(
    "error_class",
    [
        ProviderErrorClass.AUTHENTICATION,
        ProviderErrorClass.AUTHORIZATION,
        ProviderErrorClass.INVALID_REQUEST,
        ProviderErrorClass.INVALID_DESTINATION,
        ProviderErrorClass.TEMPLATE_REJECTED,
    ],
)
def test_permanent_failures_are_never_retried(error_class: ProviderErrorClass) -> None:
    decision = retry_policy.decide(
        error_class=error_class, attempt=1, max_retries=5, idempotent=True
    )
    assert not decision.should_retry


def test_retries_stop_once_attempts_are_exhausted() -> None:
    decision = retry_policy.decide(
        error_class=ProviderErrorClass.TIMEOUT, attempt=3, max_retries=2
    )
    assert not decision.should_retry
    assert decision.reason == "attempts_exhausted"


def test_backoff_grows_and_is_capped() -> None:
    delays = [retry_policy.backoff_delay(attempt, jitter=1.0) for attempt in range(1, 12)]
    assert delays[0] < delays[1] < delays[2]
    assert max(delays) <= retry_policy.MAX_DELAY_SECONDS


# --- End-to-end retry behaviour through the transport ---------------------


async def test_a_timeout_is_retried_and_can_succeed(monkeypatch) -> None:
    monkeypatch.setattr("asyncio.sleep", _no_sleep)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ReadTimeout("timed out", request=request)
        return httpx.Response(200, json={"messages": [{"messageId": "m1"}]})

    result = await send(build_client(handler))

    assert result.ok
    assert result.attempts == 2


async def test_persistent_timeouts_stop_at_the_configured_ceiling(monkeypatch) -> None:
    monkeypatch.setattr("asyncio.sleep", _no_sleep)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        raise httpx.ConnectTimeout("timed out", request=request)

    result = await send(build_client(handler))

    assert not result.ok
    assert result.error_class is ProviderErrorClass.TIMEOUT
    # One initial attempt plus max_retries.
    assert calls["n"] == 3
    assert result.attempts == 3


async def test_rate_limited_responses_are_retried_and_expose_retry_after(monkeypatch) -> None:
    slept: list[float] = []

    async def record(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr("asyncio.sleep", record)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, headers={"Retry-After": "3"}, json={})
        return httpx.Response(200, json={"messages": [{"messageId": "m1"}]})

    result = await send(build_client(handler))

    assert result.ok
    assert slept == [3.0]


async def test_authentication_failures_are_not_retried() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(401, json={})

    result = await send(build_client(handler))

    assert not result.ok
    assert result.error_class is ProviderErrorClass.AUTHENTICATION
    assert calls["n"] == 1
    assert not result.retryable


async def test_bad_request_surfaces_the_provider_reason() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "requestError": {
                    "serviceException": {
                        "messageId": "BAD_REQUEST",
                        "text": "Invalid destination number",
                    }
                }
            },
        )

    result = await send(build_client(handler))

    assert result.error_class is ProviderErrorClass.INVALID_DESTINATION
    assert result.provider_error_code == "BAD_REQUEST"
    assert result.error_detail == "Invalid destination number"


async def test_a_malformed_success_body_is_not_treated_as_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<html>not json</html>")

    result = await send(build_client(handler))

    assert not result.ok
    assert result.error_class is ProviderErrorClass.MALFORMED_RESPONSE


async def test_server_errors_retry_only_when_an_idempotency_key_is_present(monkeypatch) -> None:
    monkeypatch.setattr("asyncio.sleep", _no_sleep)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(503, json={})

    without_key = await send(build_client(handler))
    assert without_key.attempts == 1

    calls["n"] = 0
    with_key = await send(build_client(handler), idempotency_key="idem-2")
    assert with_key.attempts == 3


async def test_error_detail_is_truncated() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "requestError": {
                    "serviceException": {"messageId": "X", "text": "y" * 5_000}
                }
            },
        )

    result = await send(build_client(handler))
    assert len(result.error_detail) <= 240


async def _no_sleep(_seconds: float) -> None:
    return None
