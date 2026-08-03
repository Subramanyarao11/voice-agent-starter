"""Normalizing Infobip failures into the shared error taxonomy.

The mapping table is the integration's retry policy in one place. Getting it
wrong is expensive in both directions: retrying a rejected DLT template burns
rate-limit budget forever and never succeeds, while giving up on a 503 loses a
reminder the caller was relying on.
"""

from __future__ import annotations

import re

from sahaayak_contracts import ProviderErrorClass

# Status-code mapping. 429 is retryable but only with Retry-After respected;
# 401/403 are not retryable and should trip the channel's circuit, because
# hammering a revoked key is how an account gets locked.
_STATUS_MAP: dict[int, ProviderErrorClass] = {
    400: ProviderErrorClass.INVALID_REQUEST,
    401: ProviderErrorClass.AUTHENTICATION,
    403: ProviderErrorClass.AUTHORIZATION,
    404: ProviderErrorClass.INVALID_REQUEST,
    409: ProviderErrorClass.INVALID_REQUEST,
    413: ProviderErrorClass.INVALID_REQUEST,
    422: ProviderErrorClass.INVALID_REQUEST,
    429: ProviderErrorClass.RATE_LIMITED,
}

# Infobip reports the real reason in a group/name pair rather than the HTTP
# status, so a 400 may mean "this number does not exist" or "your template was
# rejected" — outcomes the product must treat very differently.
_DESTINATION_PATTERNS = re.compile(
    r"invalid[_ ]?(destination|number|recipient|address|msisdn|email)"
    r"|unknown[_ ]?subscriber"
    r"|not[_ ]?a[_ ]?valid[_ ]?(number|email)"
    r"|absent[_ ]?subscriber"
    r"|reject(ed)?[_ ]?not[_ ]?enroll",
    re.IGNORECASE,
)
_TEMPLATE_PATTERNS = re.compile(
    r"template"
    r"|dlt"
    r"|principal[_ ]?entity"
    r"|content[_ ]?(rejected|violation)"
    r"|not[_ ]?approved"
    r"|window[_ ]?(expired|closed)",
    re.IGNORECASE,
)


class InfobipError(RuntimeError):
    """A provider failure that could not be expressed as a send result.

    Adapters generally return a failed ``ProviderSendResult`` rather than
    raising; this exists for the client layer, where there is no channel
    context yet to build a result from.
    """

    def __init__(
        self,
        message: str,
        *,
        error_class: ProviderErrorClass = ProviderErrorClass.PROVIDER_ERROR,
        status_code: int | None = None,
        retry_after_seconds: int | None = None,
    ) -> None:
        super().__init__(message)
        self.error_class = error_class
        self.status_code = status_code
        self.retry_after_seconds = retry_after_seconds


def classify_status(status_code: int) -> ProviderErrorClass:
    if 200 <= status_code < 300:
        return ProviderErrorClass.NONE
    if status_code in _STATUS_MAP:
        return _STATUS_MAP[status_code]
    if status_code >= 500:
        return ProviderErrorClass.PROVIDER_ERROR
    return ProviderErrorClass.INVALID_REQUEST


def refine_error_class(
    base: ProviderErrorClass, *, provider_error_code: str = "", description: str = ""
) -> ProviderErrorClass:
    """Sharpen a status-derived class using the provider's own error text.

    Only applied to client-side rejections. A 500 that happens to mention the
    word "template" is still a server problem worth retrying.
    """
    if base is not ProviderErrorClass.INVALID_REQUEST:
        return base
    haystack = f"{provider_error_code} {description}"
    if _DESTINATION_PATTERNS.search(haystack):
        return ProviderErrorClass.INVALID_DESTINATION
    if _TEMPLATE_PATTERNS.search(haystack):
        return ProviderErrorClass.TEMPLATE_REJECTED
    return base


def parse_retry_after(value: str | None) -> int | None:
    """Read a Retry-After header, ignoring HTTP-date form.

    Infobip sends delta-seconds. A date form is treated as absent rather than
    parsed loosely, because a misparsed date could stall a queue for hours.
    """
    if not value:
        return None
    try:
        seconds = int(float(value.strip()))
    except ValueError:
        return None
    if seconds < 0:
        return None
    # A provider asking us to wait longer than an hour is a policy problem for
    # the worker to surface, not something to sleep on inside a request.
    return min(seconds, 3600)
