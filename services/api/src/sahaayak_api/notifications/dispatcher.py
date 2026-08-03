"""Deciding whether a message may be sent, and recording what happened.

Every reason a notification might not go out is checked in one place and
reported as a named gate. That matters for two audiences: the caller, who is
owed a plain explanation of why a channel is unavailable rather than a greyed
out button, and the operator, who needs to tell "we chose not to send" apart
from "the provider rejected it".

Order is deliberate. Consent is checked before configuration, so a caller who
has opted out is never counted as blocked by a provider outage, and the answer
does not change when the outage clears.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlmodel import Session

from sahaayak_api.notifications.base import NotificationProvider, OutboundNotification
from sahaayak_api.notifications.in_app import InAppProvider
from sahaayak_api.notifications.templates import (
    ResolvedTemplate,
    TemplateNotFound,
    render,
    resolve,
)
from sahaayak_common import (
    ContactEncryptionUnavailable,
    ContactPoint,
    NotificationDelivery,
    decrypt_destination,
    evaluate_budget,
    get_effective_provider_policy,
    get_logger,
    new_id,
    settings,
)
from sahaayak_contracts import (
    ConsentStatus,
    DeliveryStatus,
    NotificationChannel,
    ProviderErrorClass,
    ProviderSendResult,
    VerificationStatusValue,
)

log = get_logger(__name__)


class Gate(str):
    """Named reason a channel is unavailable.

    A plain string subclass so it serializes straight into an API response and
    a telemetry dimension without a conversion at each boundary.
    """


GATE_OK = Gate("ok")
GATE_CHANNEL_UNKNOWN = Gate("channel_unknown")
GATE_CONTACT_MISSING = Gate("contact_missing")
GATE_CONTACT_UNVERIFIED = Gate("contact_unverified")
GATE_CONTACT_REVOKED = Gate("contact_revoked")
GATE_CONSENT_MISSING = Gate("consent_missing")
GATE_CONSENT_WITHDRAWN = Gate("consent_withdrawn")
GATE_POLICY_DISABLED = Gate("policy_disabled")
GATE_CIRCUIT_OPEN = Gate("circuit_open")
GATE_PROVIDER_NOT_CONFIGURED = Gate("provider_not_configured")
GATE_TEMPLATE_MISSING = Gate("template_missing")
GATE_TEMPLATE_NOT_APPROVED = Gate("template_not_approved")
GATE_BUDGET_EXHAUSTED = Gate("budget_exhausted")
GATE_SESSION_MISMATCH = Gate("session_mismatch")

# What a caller is told. Kept free of provider names and internal state: the
# person waiting on a reminder needs to know what to do next, not which vendor
# is down.
GATE_MESSAGES: dict[str, str] = {
    GATE_CHANNEL_UNKNOWN: "That delivery channel is not supported.",
    GATE_CONTACT_MISSING: "Add and verify a contact for this channel first.",
    GATE_CONTACT_UNVERIFIED: "Verify this contact before using it for reminders.",
    GATE_CONTACT_REVOKED: "This contact has been removed. Add it again to use it.",
    GATE_CONSENT_MISSING: "Agree to receive messages on this channel first.",
    GATE_CONSENT_WITHDRAWN: "You opted out of messages on this channel.",
    GATE_POLICY_DISABLED: "This channel is currently switched off. In-app reminders still work.",
    GATE_CIRCUIT_OPEN: "This channel is paused after repeated failures. In-app reminders "
    "still work.",
    GATE_PROVIDER_NOT_CONFIGURED: "This channel is not available yet. In-app reminders "
    "still work.",
    GATE_TEMPLATE_MISSING: "No approved message exists for this reminder on this channel.",
    GATE_TEMPLATE_NOT_APPROVED: "The message for this channel is still awaiting approval.",
    GATE_BUDGET_EXHAUSTED: "This channel has reached its sending limit for now. In-app "
    "reminders still work.",
    GATE_SESSION_MISMATCH: "That contact belongs to a different session.",
}


@dataclass(frozen=True, slots=True)
class ChannelAvailability:
    channel: NotificationChannel
    available: bool
    gate: Gate = GATE_OK
    provider: str = ""
    fallback_provider: str = ""

    @property
    def reason(self) -> str:
        """A plain-language explanation, always populated when blocked."""
        if self.available:
            return ""
        return GATE_MESSAGES.get(self.gate, "This channel is unavailable.")


def channel_policy(channel: NotificationChannel) -> dict:
    return get_effective_provider_policy(channel.value)


def check_channel(
    db: Session,
    *,
    channel: NotificationChannel,
    contact: ContactPoint | None = None,
    session_id: str = "",
    template_key: str = "",
    locale: str = "en",
) -> ChannelAvailability:
    """Whether one message could be sent on one channel right now."""
    if channel is NotificationChannel.IN_APP:
        # Always available, by design. It is the guarantee every other branch
        # in this function falls back to.
        return ChannelAvailability(channel, True, provider="in_app")

    if channel not in (
        NotificationChannel.EMAIL,
        NotificationChannel.SMS,
        NotificationChannel.WHATSAPP,
    ):
        return ChannelAvailability(channel, False, GATE_CHANNEL_UNKNOWN)

    gate = _contact_gate(contact, session_id=session_id)
    if gate is not GATE_OK:
        return ChannelAvailability(channel, False, gate)

    policy = channel_policy(channel)
    if not policy.get("enabled", False):
        return ChannelAvailability(
            channel,
            False,
            GATE_POLICY_DISABLED,
            fallback_provider=policy.get("fallback_provider", "in_app"),
        )
    if policy.get("circuit_state", "closed") == "open":
        return ChannelAvailability(
            channel,
            False,
            GATE_CIRCUIT_OPEN,
            fallback_provider=policy.get("fallback_provider", "in_app"),
        )

    if not settings.infobip_channel_ready(channel.value):
        return ChannelAvailability(channel, False, GATE_PROVIDER_NOT_CONFIGURED)

    if template_key:
        gate = _template_gate(db, channel=channel, template_key=template_key, locale=locale)
        if gate is not GATE_OK:
            return ChannelAvailability(channel, False, gate)

    if not evaluate_budget(db, channel=channel.value).allowed:
        return ChannelAvailability(channel, False, GATE_BUDGET_EXHAUSTED)

    return ChannelAvailability(
        channel,
        True,
        provider=policy.get("primary_provider", ""),
        fallback_provider=policy.get("fallback_provider", "in_app"),
    )


def _contact_gate(contact: ContactPoint | None, *, session_id: str) -> Gate:
    if contact is None:
        return GATE_CONTACT_MISSING
    if session_id and contact.session_id != session_id:
        # Never leak whether the contact exists at all; the caller is told the
        # same thing they would be told for a made-up identifier.
        return GATE_SESSION_MISMATCH
    if contact.verification_status == VerificationStatusValue.REVOKED.value:
        return GATE_CONTACT_REVOKED
    if contact.verification_status != VerificationStatusValue.VERIFIED.value:
        return GATE_CONTACT_UNVERIFIED
    if contact.consent_status == ConsentStatus.OPTED_OUT.value:
        return GATE_CONSENT_WITHDRAWN
    if contact.consent_status != ConsentStatus.OPTED_IN.value:
        return GATE_CONSENT_MISSING
    return GATE_OK


def _template_gate(
    db: Session, *, channel: NotificationChannel, template_key: str, locale: str
) -> Gate:
    try:
        template = resolve(db, template_key=template_key, channel=channel, locale=locale)
    except TemplateNotFound:
        return GATE_TEMPLATE_MISSING
    return GATE_OK if template.provider_ready else GATE_TEMPLATE_NOT_APPROVED


def available_channels(
    db: Session,
    *,
    contacts: dict[NotificationChannel, ContactPoint],
    session_id: str,
    template_key: str = "",
    locale: str = "en",
) -> list[ChannelAvailability]:
    """Availability of every channel, for the reminder form to render."""
    return [
        check_channel(
            db,
            channel=channel,
            contact=contacts.get(channel),
            session_id=session_id,
            template_key=template_key,
            locale=locale,
        )
        for channel in NotificationChannel
    ]


def idempotency_key(*parts: str) -> str:
    """A stable key for one logical send.

    Derived from what the send *is* rather than when it was attempted, so a
    duplicate worker claim or a retried 5xx produces the same key and cannot
    bill a caller's phone twice.
    """
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()
    return f"snd_{digest[:32]}"


def create_delivery(
    db: Session,
    *,
    channel: NotificationChannel,
    session_id: str,
    template_key: str,
    locale: str,
    reminder_id: str | None = None,
    contact_point_id: str | None = None,
    provider: str = "infobip",
    safe_metadata: dict | None = None,
) -> NotificationDelivery:
    """Record the intent to send, before anything leaves the process.

    Written first on purpose: a crash between the provider call and the
    database write must leave evidence that a message may have gone out, not a
    silent gap.
    """
    internal_message_id = new_id("msg")
    row = NotificationDelivery(
        id=new_id("nd"),
        reminder_id=reminder_id,
        session_id=session_id,
        contact_point_id=contact_point_id,
        channel=channel.value,
        provider=provider if channel is not NotificationChannel.IN_APP else "in_app",
        template_key=template_key,
        locale=locale,
        internal_message_id=internal_message_id,
        status=DeliveryStatus.QUEUED.value,
        idempotency_key=idempotency_key(
            session_id, channel.value, template_key, reminder_id or internal_message_id
        ),
        cost_currency=settings.infobip_cost_currency,
        safe_metadata=safe_metadata or {},
    )
    db.add(row)
    db.flush()
    return row


def record_result(
    db: Session, delivery: NotificationDelivery, result: ProviderSendResult
) -> NotificationDelivery:
    """Apply a provider outcome to a delivery row."""
    now = datetime.now(UTC)
    delivery.status = result.status.value
    delivery.attempt_count += max(1, result.attempt_count)
    delivery.provider_status_code = result.provider_status_code
    delivery.provider_status_group = result.provider_status_group
    delivery.provider_error_code = result.provider_error_code
    delivery.provider_error_class = result.error_class.value
    delivery.updated_at = now

    if result.external_message_id:
        delivery.external_message_id = result.external_message_id
    if result.external_bulk_id:
        delivery.external_bulk_id = result.external_bulk_id
    if result.cost_minor_units is not None:
        delivery.cost_minor_units = result.cost_minor_units
        delivery.cost_currency = result.cost_currency or delivery.cost_currency

    if result.accepted:
        delivery.sent_at = delivery.sent_at or now
    if result.status is DeliveryStatus.DELIVERED:
        delivery.delivered_at = delivery.delivered_at or now
    elif result.status in (DeliveryStatus.FAILED, DeliveryStatus.SUPPRESSED):
        delivery.failed_at = now

    db.add(delivery)
    return delivery


def suppress(
    db: Session, delivery: NotificationDelivery, *, gate: Gate
) -> NotificationDelivery:
    """Mark a delivery as deliberately not sent.

    Distinct from a failure: nothing went wrong with the provider, the system
    decided not to send. Collapsing the two would make a consent withdrawal
    look like an outage on the admin dashboard.
    """
    return record_result(
        db,
        delivery,
        ProviderSendResult(
            accepted=False,
            provider=delivery.provider,
            channel=NotificationChannel(delivery.channel),
            status=DeliveryStatus.SUPPRESSED,
            error_class=ProviderErrorClass.POLICY_DISABLED,
            error_detail=gate,
        ),
    )


async def dispatch(
    db: Session,
    *,
    provider: NotificationProvider,
    contact: ContactPoint | None,
    delivery: NotificationDelivery,
    template: ResolvedTemplate,
    variables: dict[str, str] | None = None,
) -> ProviderSendResult:
    """Render, send, and record one notification.

    The plaintext destination is decrypted here and does not outlive the call.
    """
    channel = NotificationChannel(delivery.channel)
    destination = ""
    if channel is not NotificationChannel.IN_APP:
        if contact is None:
            return _record_and_return(
                db,
                delivery,
                ProviderSendResult.failure(
                    provider=provider.name,
                    channel=channel,
                    error_class=ProviderErrorClass.INVALID_DESTINATION,
                    detail="contact_missing",
                ),
            )
        try:
            destination = decrypt_destination(contact.destination_ciphertext)
        except ContactEncryptionUnavailable as exc:
            log.error(
                "notification_destination_undecryptable",
                contact_point_id=contact.id,
                channel=channel.value,
                error=str(exc),
            )
            return _record_and_return(
                db,
                delivery,
                ProviderSendResult.failure(
                    provider=provider.name,
                    channel=channel,
                    error_class=ProviderErrorClass.NOT_CONFIGURED,
                    detail="destination_undecryptable",
                ),
            )

    notification = OutboundNotification(
        channel=channel,
        destination=destination,
        message=render(template, variables),
        internal_message_id=delivery.internal_message_id,
        idempotency_key=delivery.idempotency_key,
        session_id=delivery.session_id,
        contact_point_id=delivery.contact_point_id or "",
    )

    delivery.status = DeliveryStatus.SENDING.value
    db.add(delivery)
    db.flush()

    result = await provider.send(notification)
    return _record_and_return(db, delivery, result)


def _record_and_return(
    db: Session, delivery: NotificationDelivery, result: ProviderSendResult
) -> ProviderSendResult:
    record_result(db, delivery, result)
    return result


def in_app_provider() -> InAppProvider:
    return InAppProvider()
