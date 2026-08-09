"""Distributed sliding-window abuse limits for guest and paid endpoints."""

from __future__ import annotations

import asyncio
import hashlib
import secrets
import time
from collections import deque
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, Request, Response, status

from sahaayak_common import get_logger, settings

log = get_logger(__name__)


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    limit: int
    remaining: int
    reset_seconds: int
    dimension: str


class RateLimitUnavailable(RuntimeError):
    """Raised when production cannot reach the shared limiter."""


class _MemorySlidingWindow:
    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = {}
        self._lock = asyncio.Lock()

    async def consume(self, key: str, *, limit: int, window_seconds: int) -> RateLimitDecision:
        now = time.monotonic()
        cutoff = now - window_seconds
        async with self._lock:
            events = self._events.setdefault(key, deque())
            while events and events[0] <= cutoff:
                events.popleft()
            allowed = len(events) < limit
            if allowed:
                events.append(now)
            retry = 0 if allowed or not events else max(1, int(events[0] + window_seconds - now))
            return RateLimitDecision(
                allowed=allowed,
                limit=limit,
                remaining=max(0, limit - len(events)),
                reset_seconds=retry or window_seconds,
                dimension="memory",
            )

    def reset(self) -> None:
        self._events.clear()


class _RedisSlidingWindow:
    _SCRIPT = """
    local now = tonumber(ARGV[1])
    local window = tonumber(ARGV[2])
    local limit = tonumber(ARGV[3])
    redis.call('ZREMRANGEBYSCORE', KEYS[1], 0, now - window)
    local count = redis.call('ZCARD', KEYS[1])
    if count >= limit then
      local oldest = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
      local retry = window
      if oldest[2] then
        retry = math.max(1, tonumber(oldest[2]) + window - now)
      end
      redis.call('EXPIRE', KEYS[1], math.ceil(window / 1000) + 1)
      return {0, count, retry}
    end
    redis.call('ZADD', KEYS[1], now, ARGV[4])
    redis.call('EXPIRE', KEYS[1], math.ceil(window / 1000) + 1)
    return {1, count + 1, window}
    """

    def __init__(self, redis_client: Any) -> None:
        self._redis = redis_client

    async def consume(self, key: str, *, limit: int, window_seconds: int) -> RateLimitDecision:
        now_ms = int(time.time() * 1000)
        window_ms = window_seconds * 1000
        member = f"{now_ms}:{secrets.token_hex(6)}"
        result = await self._redis.eval(
            self._SCRIPT,
            1,
            key,
            now_ms,
            window_ms,
            limit,
            member,
        )
        allowed = bool(int(result[0]))
        count = int(result[1])
        retry_ms = max(1, int(float(result[2])))
        return RateLimitDecision(
            allowed=allowed,
            limit=limit,
            remaining=max(0, limit - count),
            reset_seconds=max(1, (retry_ms + 999) // 1000),
            dimension="redis",
        )


_memory_backend = _MemorySlidingWindow()
_backend: _MemorySlidingWindow | _RedisSlidingWindow | None = None
_backend_lock = asyncio.Lock()


async def _get_backend():
    global _backend
    if _backend is not None:
        return _backend
    async with _backend_lock:
        if _backend is not None:
            return _backend
        if not settings.redis_url:
            _backend = _memory_backend
            return _backend
        try:
            from redis.asyncio import Redis

            client = Redis.from_url(settings.redis_url, decode_responses=True)
            await client.ping()
            _backend = _RedisSlidingWindow(client)
            log.info("rate_limit_backend_selected", backend="redis")
        except Exception as exc:
            if settings.rate_limit_fail_closed and not (
                settings.is_development or settings.is_test
            ):
                log.error("rate_limit_backend_unavailable", error=exc.__class__.__name__)
                raise RateLimitUnavailable from exc
            log.warning(
                "rate_limit_redis_unavailable_using_memory",
                error=exc.__class__.__name__,
                impact="limits are process-local until Redis recovers",
            )
            _backend = _memory_backend
    return _backend


def _fingerprint(value: str) -> str:
    salt = settings.rate_limit_key_salt or "sahaayak-development-rate-limit"
    return hashlib.sha256(f"{salt}:{value}".encode()).hexdigest()[:24]


def _client_ip(request: Request) -> str:
    # Do not trust X-Forwarded-For until the deployment explicitly configures
    # its trusted proxy chain. The direct socket address cannot be caller-set.
    return request.client.host if request.client else "unknown"


def reset_rate_limiter() -> None:
    """Reset the local backend between tests; Redis state is TTL-bound."""
    global _backend
    _memory_backend.reset()
    _backend = None


async def enforce_rate_limit(
    request: Request,
    *,
    session_id: str | None,
    bucket: str,
) -> RateLimitDecision | None:
    if not settings.rate_limit_enabled:
        return None

    window = max(1, settings.rate_limit_window_seconds)
    config: dict[str, tuple[int, int]] = {
        "session_create": (0, settings.rate_limit_session_create_per_ip),
        "text": (settings.rate_limit_text_per_session, settings.rate_limit_text_per_ip),
        "voice": (settings.rate_limit_voice_per_session, settings.rate_limit_voice_per_ip),
        "rag": (settings.rate_limit_rag_per_session, settings.rate_limit_rag_per_ip),
        "application_create": (
            settings.rate_limit_application_create_per_session,
            settings.rate_limit_application_create_per_ip,
        ),
        "application_status": (
            settings.rate_limit_application_status_per_session,
            settings.rate_limit_application_status_per_ip,
        ),
        "application_pack": (
            settings.rate_limit_application_pack_per_session,
            settings.rate_limit_application_pack_per_ip,
        ),
        "assistance": (
            settings.rate_limit_assistance_per_session,
            settings.rate_limit_assistance_per_ip,
        ),
        "radar": (
            settings.rate_limit_radar_per_session,
            settings.rate_limit_radar_per_ip,
        ),
        "life_event": (
            settings.rate_limit_life_event_per_session,
            settings.rate_limit_life_event_per_ip,
        ),
        "migration": (
            settings.rate_limit_migration_per_session,
            settings.rate_limit_migration_per_ip,
        ),
        # Contact verification gets its own budget rather than sharing the
        # text bucket. Each challenge sends a real charged message, and the
        # attempt limit is an anti-guessing control as much as an abuse one.
        "contact_verify": (
            settings.rate_limit_contact_verify_per_session,
            settings.rate_limit_contact_verify_per_ip,
        ),
        "feedback": (
            settings.rate_limit_feedback_per_session,
            settings.rate_limit_feedback_per_ip,
        ),
    }
    limits = config.get(bucket)
    if limits is None:
        raise RuntimeError(f"unknown rate-limit bucket: {bucket}")

    try:
        backend = await _get_backend()
    except RateLimitUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Abuse protection is temporarily unavailable",
        ) from exc

    identities = [("ip", _fingerprint(_client_ip(request)), limits[1])]
    if bucket != "session_create" and session_id:
        identities.insert(0, ("session", _fingerprint(session_id), limits[0]))

    decisions: list[RateLimitDecision] = []
    for dimension, identity, limit in identities:
        decision = await backend.consume(
            f"sahaayak:rate:{bucket}:{dimension}:{identity}",
            limit=max(1, limit),
            window_seconds=window,
        )
        decision = RateLimitDecision(
            allowed=decision.allowed,
            limit=decision.limit,
            remaining=decision.remaining,
            reset_seconds=decision.reset_seconds,
            dimension=dimension,
        )
        decisions.append(decision)
        if not decision.allowed:
            _raise_rate_limit(decision)

    return min(decisions, key=lambda item: (item.remaining, item.reset_seconds))


async def consume_channel_limit(
    identity: str, *, bucket: str, limit: int, window_seconds: int
) -> RateLimitDecision:
    """Consume one unit of an inbound-channel budget.

    For surfaces with no HTTP request to derive an IP from — a WhatsApp sender,
    a telephony caller — where the identity is a hash the channel supplied.
    Kept independent of the browser buckets: a flood of inbound WhatsApp must
    not exhaust the limit protecting the web demo.

    Returns the decision rather than raising, because an inbound channel
    answers a provider webhook that must still get a 2xx.
    """
    backend = await _get_backend()
    return await backend.consume(
        f"sahaayak:rate:{bucket}:{_fingerprint(identity)}",
        limit=max(1, limit),
        window_seconds=max(1, window_seconds),
    )


def _raise_rate_limit(decision: RateLimitDecision) -> None:
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Too many requests. Please wait before trying again.",
        headers=_rate_limit_headers(decision),
    )


def apply_rate_limit_headers(response: Response, decision: RateLimitDecision | None) -> None:
    if decision is None:
        return
    response.headers.update(_rate_limit_headers(decision))


def _rate_limit_headers(decision: RateLimitDecision) -> dict[str, str]:
    return {
        "Retry-After": str(decision.reset_seconds),
        "X-RateLimit-Limit": str(decision.limit),
        "X-RateLimit-Remaining": str(max(0, decision.remaining)),
        "X-RateLimit-Reset": str(decision.reset_seconds),
    }
