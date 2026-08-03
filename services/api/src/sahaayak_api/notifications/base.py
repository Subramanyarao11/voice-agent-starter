"""The interface every notification channel implements.

Product code builds an ``OutboundNotification`` and hands it to a provider. It
does not know whether that provider is Infobip, an in-app record, or a fake in
a test, and it never sees an HTTP status code — which is the point: the reminder
logic must be readable without knowing anything about a vendor's API.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from sahaayak_api.notifications.templates import RenderedMessage
from sahaayak_contracts import NotificationChannel, ProviderSendResult


@dataclass(slots=True)
class OutboundNotification:
    """One message, ready to hand to a provider.

    ``destination`` holds decrypted plaintext and exists only for the duration
    of a send. It is never logged, never returned by the API, never written to
    telemetry, and never stored on a delivery row — the masked suffix on the
    contact point is what anything user-facing displays.
    """

    channel: NotificationChannel
    destination: str
    message: RenderedMessage
    internal_message_id: str
    idempotency_key: str = ""
    session_id: str = ""
    contact_point_id: str = ""
    safe_metadata: dict[str, str] = field(default_factory=dict)

    def redacted(self) -> dict[str, str]:
        """The log-safe view of this notification."""
        return {
            "channel": self.channel.value,
            "template_key": self.message.template_key,
            "locale": self.message.locale,
            "internal_message_id": self.internal_message_id,
            **self.safe_metadata,
        }


@runtime_checkable
class NotificationProvider(Protocol):
    """A single channel's transport.

    Implementations return a ``ProviderSendResult`` for provider-reported
    failures rather than raising. A rejected message is an outcome to record
    and show an operator, not an exception for the caller to interpret.
    """

    name: str
    channel: NotificationChannel

    def available(self) -> bool:
        """Whether this provider is configured and permitted to be attempted."""
        ...

    async def send(self, notification: OutboundNotification) -> ProviderSendResult:
        ...
