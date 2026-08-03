"""Retry policy for Infobip requests.

Separated from the client so the decision — *should this be tried again, and
when* — is a pure function that tests can drive directly, rather than something
only observable by watching a live HTTP loop.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from sahaayak_contracts import ProviderErrorClass

# Two attempts a second apart is not a retry policy, it is a thundering herd.
# Base delay is deliberately close to a human-perceptible pause because a
# reminder is not latency-sensitive, and the worker is not holding a request
# open while this happens.
BASE_DELAY_SECONDS = 0.5
MAX_DELAY_SECONDS = 30.0


@dataclass(frozen=True, slots=True)
class RetryDecision:
    should_retry: bool
    delay_seconds: float = 0.0
    reason: str = ""


def backoff_delay(attempt: int, *, jitter: float | None = None) -> float:
    """Exponential backoff with full jitter.

    Full jitter rather than a fixed multiplier: several workers retrying the
    same provider outage in lockstep is exactly the pattern that keeps the
    provider down.
    """
    ceiling = min(MAX_DELAY_SECONDS, BASE_DELAY_SECONDS * (2 ** max(0, attempt - 1)))
    factor = random.random() if jitter is None else jitter
    return round(ceiling * max(0.0, min(1.0, factor)), 3)


def decide(
    *,
    error_class: ProviderErrorClass,
    attempt: int,
    max_retries: int,
    retry_after_seconds: int | None = None,
    idempotent: bool = False,
    jitter: float | None = None,
) -> RetryDecision:
    """Whether attempt ``attempt`` should be followed by another one.

    ``attempt`` is 1-based, so with ``max_retries=2`` the third attempt is the
    last.
    """
    if attempt > max_retries:
        return RetryDecision(False, reason="attempts_exhausted")

    if error_class in (ProviderErrorClass.TIMEOUT, ProviderErrorClass.NETWORK):
        return RetryDecision(True, backoff_delay(attempt, jitter=jitter), "transient_network")

    if error_class is ProviderErrorClass.RATE_LIMITED:
        # Honour the provider's own pacing when it gives one; guessing faster
        # than it asked for is how a soft limit becomes a hard block.
        delay = (
            float(retry_after_seconds)
            if retry_after_seconds is not None
            else backoff_delay(attempt, jitter=jitter)
        )
        return RetryDecision(True, min(delay, MAX_DELAY_SECONDS), "rate_limited")

    if error_class is ProviderErrorClass.PROVIDER_ERROR:
        # A 5xx may still have sent the message. Without an idempotency key a
        # retry risks a caller receiving the same SMS twice, which for a
        # charged channel is worse than a missed one.
        if not idempotent:
            return RetryDecision(False, reason="not_idempotent")
        return RetryDecision(True, backoff_delay(attempt, jitter=jitter), "provider_error")

    return RetryDecision(False, reason="not_retryable")
