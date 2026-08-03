"""Infobip WhatsApp adapter.

WhatsApp has a rule no other channel here has: outside a 24-hour window opened
by the user's own message, only a template approved in advance by Meta may be
sent. Free-form text outside that window is rejected, and repeatedly attempting
it is the kind of thing that gets a sender's quality rating cut.

So the window is tracked rather than guessed. It lives in the cache with a TTL
equal to the window itself, which makes expiry automatic and makes the failure
mode safe: if the cache is lost, the window reads as closed and the adapter
falls back to requiring a template.

The other rule that shapes this file is that a WhatsApp sender is a channel
identity, not an authenticated user. It is a string a third party asserts. It
is hashed on arrival, it never authorizes anything, and it is never
automatically merged with a browser session.
"""

from __future__ import annotations

from datetime import timedelta

from sahaayak_api.integrations.infobip.client import InfobipClient, get_infobip_client
from sahaayak_api.integrations.infobip.outbound import result_from_response
from sahaayak_api.notifications.base import OutboundNotification
from sahaayak_common import (
    channel_identity_hash,
    get_cache,
    get_logger,
    is_valid_e164,
    normalize_destination,
    settings,
)
from sahaayak_contracts import NotificationChannel, ProviderErrorClass, ProviderSendResult

log = get_logger(__name__)

TEMPLATE_SEND_PATH = "/whatsapp/1/message/template"
TEXT_SEND_PATH = "/whatsapp/1/message/text"
MEDIA_PATH = "/whatsapp/1/senders/{sender}/media/{media_id}"

# Meta's customer-service window. Kept slightly short of 24 hours so a message
# is never attempted in the last moments before expiry, when the provider's
# clock and ours may disagree.
WINDOW = timedelta(hours=23, minutes=45)

# Inbound media is downloaded only to transcribe it and is then discarded.
# Roughly a minute of voice note; anything larger is a client problem.
MAX_INBOUND_MEDIA_BYTES = 10 * 1024 * 1024


def _window_key(destination: str) -> str:
    return f"sahaayak:wa:window:{channel_identity_hash('whatsapp', destination)}"


async def open_window(destination: str) -> None:
    """Record that the user messaged us, opening the free-form window."""
    cache = await get_cache()
    await cache.set(_window_key(destination), b"1", ttl_seconds=int(WINDOW.total_seconds()))


async def window_is_open(destination: str) -> bool:
    cache = await get_cache()
    return await cache.get(_window_key(destination)) is not None


class InfobipWhatsAppProvider:
    """Sends WhatsApp messages, choosing template or free-form by window state.

    ``send`` is the notification-provider entry point and always uses a
    template: it serves reminders, which by definition are initiated by us
    rather than by the user. ``send_reply`` is for answering someone inside an
    open window during a conversation.
    """

    name = "infobip_whatsapp"
    channel = NotificationChannel.WHATSAPP

    def __init__(self, client: InfobipClient, *, sender: str = "") -> None:
        self._client = client
        self._sender = sender or settings.infobip_whatsapp_sender.strip()

    def available(self) -> bool:
        return bool(
            settings.infobip_channel_ready("whatsapp")
            and self._sender
            and self._client.config.configured
        )

    async def send(self, notification: OutboundNotification) -> ProviderSendResult:
        destination = normalize_destination("whatsapp", notification.destination)
        if not is_valid_e164(destination):
            return self._failure(
                ProviderErrorClass.INVALID_DESTINATION, "destination is not valid E.164"
            )
        if not self._sender:
            return self._failure(
                ProviderErrorClass.NOT_CONFIGURED, "no WhatsApp sender configured"
            )

        message = notification.message
        if not message.provider_template_name:
            # Refused locally: Meta would reject it, and an unapproved template
            # attempt counts against the sender's standing.
            return self._failure(
                ProviderErrorClass.TEMPLATE_REJECTED,
                "no approved WhatsApp template for this message",
            )

        payload = {
            "messages": [
                {
                    "from": self._sender,
                    "to": destination,
                    "content": {
                        "templateName": message.provider_template_name,
                        "templateData": {"body": {"placeholders": list(message.variables)}},
                        "language": _language_tag(message.locale),
                    },
                    "callbackData": notification.internal_message_id,
                }
            ]
        }

        response = await self._client.post(
            TEMPLATE_SEND_PATH,
            payload,
            operation="send_template",
            channel="whatsapp",
            idempotency_key=notification.idempotency_key,
        )
        result = result_from_response(response, provider=self.name, channel=self.channel)
        log.info(
            "whatsapp_template_send_attempted",
            accepted=result.accepted,
            status=result.status.value,
            error_class=result.error_class.value,
            **notification.redacted(),
        )
        return result

    async def send_reply(
        self, *, destination: str, text: str, internal_message_id: str
    ) -> ProviderSendResult:
        """Answer a user inside the open window with free-form text.

        Refuses rather than falling back to a template when the window has
        closed: a conversational reply arriving as a canned utility template
        hours later is confusing, and choosing a template is the caller's
        decision to make explicitly.
        """
        normalized = normalize_destination("whatsapp", destination)
        if not is_valid_e164(normalized):
            return self._failure(
                ProviderErrorClass.INVALID_DESTINATION, "destination is not valid E.164"
            )
        if not text.strip():
            return self._failure(ProviderErrorClass.INVALID_REQUEST, "empty message body")
        if not await window_is_open(normalized):
            return self._failure(
                ProviderErrorClass.TEMPLATE_REJECTED,
                "the free-form messaging window has closed",
            )

        payload = {
            "from": self._sender,
            "to": normalized,
            "content": {"text": text},
            "callbackData": internal_message_id,
        }
        response = await self._client.post(
            TEXT_SEND_PATH,
            payload,
            operation="send_text",
            channel="whatsapp",
            idempotency_key=internal_message_id,
        )
        result = result_from_response(response, provider=self.name, channel=self.channel)
        log.info(
            "whatsapp_reply_send_attempted",
            accepted=result.accepted,
            status=result.status.value,
            error_class=result.error_class.value,
            internal_message_id=internal_message_id,
        )
        return result

    async def download_media(self, media_id: str) -> bytes | None:
        """Fetch inbound media for processing, with a hard size ceiling.

        The bytes are returned to be transcribed and dropped. Nothing here
        writes media to disk or to the database: a voice note is a caller
        speaking about their income and family, and storing it by default
        would be collecting exactly what this system tries not to hold.
        """
        if not media_id or not self._sender:
            return None

        response = await self._client.request(
            "GET",
            MEDIA_PATH.format(sender=self._sender, media_id=media_id),
            operation="download_media",
            channel="whatsapp",
        )
        if not response.ok:
            log.warning(
                "whatsapp_media_download_failed",
                error_class=response.error_class.value,
                status_code=response.status_code,
            )
            return None

        raw = response.payload.get("data") if isinstance(response.payload, dict) else None
        if isinstance(raw, bytes):
            return raw if len(raw) <= MAX_INBOUND_MEDIA_BYTES else None
        return None

    def _failure(self, error_class: ProviderErrorClass, detail: str) -> ProviderSendResult:
        return ProviderSendResult.failure(
            provider=self.name,
            channel=self.channel,
            error_class=error_class,
            detail=detail,
        )


def _language_tag(locale: str) -> str:
    """Map a Sahaayak locale onto a WhatsApp template language tag."""
    return {"en": "en", "hi": "hi", "kn": "kn"}.get(locale, "en")


def build_whatsapp_provider() -> InfobipWhatsAppProvider | None:
    client = get_infobip_client()
    if client is None or not settings.infobip_channel_ready("whatsapp"):
        return None
    provider = InfobipWhatsAppProvider(client)
    return provider if provider.available() else None
