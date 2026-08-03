"""The in-app channel: the fallback that always works.

Everything else in this package depends on a third party being reachable, on
telecom registration, and on a caller having handed over a phone number. This
one depends on none of that, which is why it stays the default and why an
external provider failure degrades to it rather than losing the reminder.

There is no transport. The delivery row itself is the artefact the browser
reads, so a send is complete the moment it is recorded.
"""

from __future__ import annotations

from sahaayak_api.notifications.base import OutboundNotification
from sahaayak_common import get_logger
from sahaayak_contracts import DeliveryStatus, NotificationChannel, ProviderSendResult

log = get_logger(__name__)


class InAppProvider:
    name = "in_app"
    channel = NotificationChannel.IN_APP

    def available(self) -> bool:
        return True

    async def send(self, notification: OutboundNotification) -> ProviderSendResult:
        log.info("in_app_notification_recorded", **notification.redacted())
        return ProviderSendResult(
            accepted=True,
            provider=self.name,
            channel=self.channel,
            # Delivered outright, not merely accepted: there is no third party
            # that could still drop it, so waiting on a callback that will
            # never arrive would leave the row permanently in-flight.
            status=DeliveryStatus.DELIVERED,
            external_message_id=notification.internal_message_id,
            cost_minor_units=0,
        )
