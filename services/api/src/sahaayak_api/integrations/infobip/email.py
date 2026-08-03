"""Infobip email adapter.

Email is the first external channel worth enabling: it needs no DLT
registration, no Meta approval, and it carries Kannada and Hindi without a
segment cost. It still needs a verified sending domain with SPF, DKIM, and
DMARC — without those the message is delivered to a spam folder, which looks
identical to success from the API's point of view.

Both parts are always sent. A plain-text alternative is not a nicety here: the
recipients this serves are often on low-end mail clients, and an HTML-only
message that fails to render is a reminder that silently did not arrive.

What email must not carry is a caller's profile. Income, category, disability,
and transcripts stay out of the body by construction — the templates reference
a benefit name and a source URL, and anything more sensitive belongs behind an
authenticated page rather than in a mailbox.
"""

from __future__ import annotations

from sahaayak_api.integrations.infobip.client import InfobipClient, get_infobip_client
from sahaayak_api.integrations.infobip.outbound import result_from_response
from sahaayak_api.notifications.base import OutboundNotification
from sahaayak_common import get_logger, is_valid_email, normalize_destination, settings
from sahaayak_contracts import NotificationChannel, ProviderErrorClass, ProviderSendResult

log = get_logger(__name__)

# The JSON messages endpoint rather than the multipart send endpoint: the
# shared client speaks JSON, and no template here has an attachment. The
# account's available API version is confirmed during provider onboarding;
# see docs/infobip-operations.md.
EMAIL_SEND_PATH = "/email/3/send"

MAX_SUBJECT_CHARACTERS = 160


class InfobipEmailProvider:
    name = "infobip_email"
    channel = NotificationChannel.EMAIL

    def __init__(
        self, client: InfobipClient, *, sender: str = "", sender_name: str = ""
    ) -> None:
        self._client = client
        self._sender = sender or settings.infobip_email_sender.strip()
        self._sender_name = sender_name or settings.infobip_email_sender_name.strip()

    def available(self) -> bool:
        return bool(
            settings.infobip_channel_ready("email")
            and self._sender
            and self._client.config.configured
        )

    def _from_header(self) -> str:
        if self._sender_name:
            return f"{self._sender_name} <{self._sender}>"
        return self._sender

    async def send(self, notification: OutboundNotification) -> ProviderSendResult:
        destination = normalize_destination("email", notification.destination)

        if not is_valid_email(destination):
            return self._failure(
                ProviderErrorClass.INVALID_DESTINATION, "destination is not a valid address"
            )
        if not self._sender:
            return self._failure(
                ProviderErrorClass.NOT_CONFIGURED, "no verified sending address configured"
            )

        message = notification.message
        if not message.text.strip():
            return self._failure(ProviderErrorClass.INVALID_REQUEST, "empty message body")

        subject = (message.subject or "Sahaayak").strip()[:MAX_SUBJECT_CHARACTERS]

        payload = {
            "messages": [
                {
                    "from": self._from_header(),
                    "to": [{"destination": destination}],
                    "subject": subject,
                    # Both parts, always. See the module docstring.
                    "text": message.text,
                    "html": message.html or None,
                    "webhooks": {
                        "delivery": {"callbackData": notification.internal_message_id}
                    },
                }
            ]
        }

        response = await self._client.post(
            EMAIL_SEND_PATH,
            payload,
            operation="send",
            channel="email",
            idempotency_key=notification.idempotency_key,
        )
        result = result_from_response(response, provider=self.name, channel=self.channel)

        log.info(
            "email_send_attempted",
            accepted=result.accepted,
            status=result.status.value,
            error_class=result.error_class.value,
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


def build_email_provider() -> InfobipEmailProvider | None:
    client = get_infobip_client()
    if client is None or not settings.infobip_channel_ready("email"):
        return None
    provider = InfobipEmailProvider(client)
    return provider if provider.available() else None
