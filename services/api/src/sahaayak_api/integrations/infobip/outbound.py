"""Turning an Infobip HTTP exchange into a provider-neutral send result.

Shared by every outbound channel so that "what does a 200 with no message ID
mean" is answered once. It means failure: without an external message ID there
is nothing to reconcile the eventual delivery report against, and a row stuck
in ``accepted`` forever is worse than a row that says it failed.
"""

from __future__ import annotations

from sahaayak_api.integrations.infobip.client import InfobipResponse
from sahaayak_api.integrations.infobip.models import InfobipSendResponse
from sahaayak_contracts import (
    DeliveryStatus,
    NotificationChannel,
    ProviderErrorClass,
    ProviderSendResult,
)

# Infobip groups statuses numerically. Group 1 is PENDING and 3 is DELIVERED;
# 2 (UNDELIVERABLE), 4 (EXPIRED), and 5 (REJECTED) are terminal failures.
_GROUP_TO_STATUS: dict[int, DeliveryStatus] = {
    0: DeliveryStatus.ACCEPTED,  # ACCEPTED
    1: DeliveryStatus.ACCEPTED,  # PENDING
    2: DeliveryStatus.FAILED,  # UNDELIVERABLE
    3: DeliveryStatus.DELIVERED,
    4: DeliveryStatus.FAILED,  # EXPIRED
    5: DeliveryStatus.FAILED,  # REJECTED
}


def _parse_send(payload: dict) -> InfobipSendResponse:
    """Normalize the two send-response shapes into one.

    Bulk endpoints answer with a ``messages`` array; the WhatsApp text endpoint
    answers with a single message object. Wrapping the latter here keeps every
    adapter reading one shape.
    """
    if isinstance(payload, dict) and "messages" not in payload and "messageId" in payload:
        return InfobipSendResponse.model_validate({"messages": [payload]})
    return InfobipSendResponse.model_validate(payload)


def status_for_group(group_id: int | None, *, default: DeliveryStatus) -> DeliveryStatus:
    if group_id is None:
        return default
    return _GROUP_TO_STATUS.get(group_id, default)


def result_from_response(
    response: InfobipResponse,
    *,
    provider: str,
    channel: NotificationChannel,
) -> ProviderSendResult:
    """Map one send response onto the shared result contract."""
    if not response.ok:
        return ProviderSendResult(
            accepted=False,
            provider=provider,
            channel=channel,
            status=DeliveryStatus.FAILED,
            error_class=response.error_class,
            error_detail=response.error_detail,
            provider_error_code=response.provider_error_code,
            retryable=response.retryable,
            retry_after_seconds=response.retry_after_seconds,
            attempt_count=response.attempts,
            duration_ms=response.duration_ms,
        )

    parsed = _parse_send(response.payload)
    message = parsed.first()
    if message is None or not message.message_id:
        return ProviderSendResult(
            accepted=False,
            provider=provider,
            channel=channel,
            status=DeliveryStatus.FAILED,
            error_class=ProviderErrorClass.MALFORMED_RESPONSE,
            error_detail="response contained no message id",
            attempt_count=response.attempts,
            duration_ms=response.duration_ms,
            retryable=False,
        )

    status = message.status
    return ProviderSendResult(
        accepted=True,
        provider=provider,
        channel=channel,
        # ACCEPTED, never DELIVERED. The provider took the request; only a
        # delivery report can say a handset or mailbox received anything.
        status=status_for_group(
            status.group_id if status else None, default=DeliveryStatus.ACCEPTED
        ),
        external_message_id=message.message_id,
        external_bulk_id=parsed.bulk_id,
        provider_status_code=status.code if status else "",
        provider_status_group=status.group_name if status else "",
        attempt_count=response.attempts,
        duration_ms=response.duration_ms,
    )
