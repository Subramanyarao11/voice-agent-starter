"""Infobip SMS adapter.

Two things make Indian SMS different from a generic messaging integration, and
both are enforced here rather than left to a caller.

Segmentation: an SMS carrying Kannada or Hindi cannot use the 7-bit GSM
alphabet, so it drops to UCS-2 and fits 67 characters per segment instead of
153. A message that reads as one short line in English can be five billable
segments in Kannada. Since this service exists for people with little money and
the sender pays per segment, an over-long message is refused rather than
quietly costing five times as much.

Approval: a template that is not registered under DLT will be rejected by the
operator every single time. Sending it anyway spends rate-limit budget to learn
something already known, so the dispatcher's template gate is the real check
and this adapter refuses too.
"""

from __future__ import annotations

from sahaayak_api.integrations.infobip.client import InfobipClient, get_infobip_client
from sahaayak_api.integrations.infobip.outbound import result_from_response
from sahaayak_api.notifications.base import OutboundNotification
from sahaayak_common import get_logger, is_valid_e164, normalize_destination, settings
from sahaayak_contracts import NotificationChannel, ProviderErrorClass, ProviderSendResult

log = get_logger(__name__)

# SMS v3. The account's available API version is confirmed during provider
# onboarding; see docs/infobip-operations.md.
SMS_SEND_PATH = "/sms/3/messages"

# The GSM 03.38 basic alphabet. Anything outside it forces the whole message to
# UCS-2 — one Kannada character in an otherwise-English message doubles the
# cost of every character in it.
_GSM_BASIC = set(
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?"
    "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà"
)
# These occupy two septets each in GSM-7.
_GSM_EXTENDED = set("^{}\\[~]|€")

GSM_SINGLE_LIMIT = 160
GSM_CONCAT_LIMIT = 153
UCS2_SINGLE_LIMIT = 70
UCS2_CONCAT_LIMIT = 67


def is_gsm7(text: str) -> bool:
    return all(char in _GSM_BASIC or char in _GSM_EXTENDED for char in text)


def encoding_for(text: str) -> str:
    return "GSM7" if is_gsm7(text) else "UCS2"


def count_segments(text: str) -> int:
    """Billable segments for one message body."""
    if not text:
        return 0
    if is_gsm7(text):
        length = sum(2 if char in _GSM_EXTENDED else 1 for char in text)
        single, concat = GSM_SINGLE_LIMIT, GSM_CONCAT_LIMIT
    else:
        length = len(text)
        single, concat = UCS2_SINGLE_LIMIT, UCS2_CONCAT_LIMIT

    if length <= single:
        return 1
    return -(-length // concat)  # ceiling division


class InfobipSmsProvider:
    name = "infobip_sms"
    channel = NotificationChannel.SMS

    def __init__(self, client: InfobipClient, *, sender: str = "") -> None:
        self._client = client
        self._sender = sender or settings.infobip_sms_sender.strip()

    def available(self) -> bool:
        return bool(
            settings.infobip_channel_ready("sms")
            and self._sender
            and self._client.config.configured
        )

    async def send(self, notification: OutboundNotification) -> ProviderSendResult:
        destination = normalize_destination("sms", notification.destination)

        if not is_valid_e164(destination):
            # Not retryable and not the provider's fault. A bare ten-digit
            # number is rejected rather than guessed at, because guessing a
            # country code delivers someone's reminder to a stranger.
            return self._failure(
                ProviderErrorClass.INVALID_DESTINATION, "destination is not valid E.164"
            )

        if not self._sender:
            return self._failure(ProviderErrorClass.NOT_CONFIGURED, "no SMS sender configured")

        text = notification.message.text
        if not text.strip():
            return self._failure(ProviderErrorClass.INVALID_REQUEST, "empty message body")

        segments = count_segments(text)
        if segments > settings.sms_max_segments:
            log.warning(
                "sms_over_segment_budget",
                segments=segments,
                limit=settings.sms_max_segments,
                encoding=encoding_for(text),
                **notification.redacted(),
            )
            return self._failure(
                ProviderErrorClass.INVALID_REQUEST,
                f"message is {segments} segments, over the {settings.sms_max_segments} limit",
            )

        payload = {
            "messages": [
                {
                    "sender": self._sender,
                    "destinations": [{"to": destination}],
                    "content": {"text": text},
                    # Our opaque internal ID, echoed back on the delivery
                    # report. Never anything derived from the destination.
                    "webhooks": {"delivery": {"callbackData": notification.internal_message_id}},
                }
            ]
        }

        response = await self._client.post(
            SMS_SEND_PATH,
            payload,
            operation="send",
            channel="sms",
            idempotency_key=notification.idempotency_key,
        )
        result = result_from_response(response, provider=self.name, channel=self.channel)

        log.info(
            "sms_send_attempted",
            accepted=result.accepted,
            status=result.status.value,
            error_class=result.error_class.value,
            segments=segments,
            encoding=encoding_for(text),
            **notification.redacted(),
        )
        return result

    def _failure(self, error_class: ProviderErrorClass, detail: str) -> ProviderSendResult:
        return ProviderSendResult.failure(
            provider=self.name,
            channel=self.channel,
            error_class=error_class,
            detail=detail,
        )


def build_sms_provider() -> InfobipSmsProvider | None:
    client = get_infobip_client()
    if client is None or not settings.infobip_channel_ready("sms"):
        return None
    provider = InfobipSmsProvider(client)
    return provider if provider.available() else None
