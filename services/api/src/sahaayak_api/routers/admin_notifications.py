"""Admin visibility for messaging channels.

Separate from the model-provider console because the questions are different.
For OpenAI or Sarvam an operator asks how much has been spent and whether the
circuit is open. For a messaging channel they ask whether anything is actually
arriving — accepted is not delivered, and a channel can be perfectly healthy by
every provider metric while every message silently bounces.

Everything here is aggregate. No recipient, no message body, and no contact
destination appears, even masked: an operator debugging a delivery rate does
not need to know who was written to.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func
from sqlmodel import Session, select

from sahaayak_api.admin_auth import AdminPrincipal, require_admin_role
from sahaayak_api.notifications import channel_policy
from sahaayak_api.notifications.templates import PREAPPROVAL_REQUIRED
from sahaayak_common import (
    CallSession,
    ContactPoint,
    NotificationDelivery,
    NotificationTemplate,
    evaluate_budget,
    get_effective_provider_policy,
    get_session,
    settings,
)
from sahaayak_contracts import DeliveryStatus, NotificationChannel

router = APIRouter(prefix="/api/admin", tags=["admin"])

READ_ROLES = ("admin", "operator", "reviewer")

# Deliveries accepted but never reported on. A number that only climbs means
# the callbacks have stopped arriving, which looks identical to success from
# the send side alone — the single most important thing on this page.
STALE_AFTER = timedelta(hours=6)


class ChannelCardOut(BaseModel):
    channel: str
    # Credentials and sender are present. Says nothing about entitlement:
    # DLT, domain verification, and Meta approval are invisible from here.
    configured: bool
    policy_enabled: bool
    circuit_state: str
    primary_provider: str
    fallback_provider: str
    sender_ready: bool
    templates_total: int
    templates_approved: int
    # False when this channel needs pre-approved templates and has none.
    template_ready: bool

    accepted: int = 0
    delivered: int = 0
    failed: int = 0
    suppressed: int = 0
    awaiting_report: int = 0
    stale_awaiting_report: int = 0
    delivery_rate: float = 0.0

    last_success_at: datetime | None = None
    last_failure_at: datetime | None = None
    last_report_at: datetime | None = None
    top_error_class: str = ""

    cost_minor_units: int = 0
    cost_currency: str = "INR"

    verified_contacts: int = 0
    opted_out_contacts: int = 0
    note: str = ""


class VoiceCardOut(BaseModel):
    configured: bool
    policy_enabled: bool
    calls: int = 0
    answered: int = 0
    ended: int = 0
    average_duration_seconds: float = 0.0
    note: str = ""


class NotificationOverviewOut(BaseModel):
    generated_at: datetime
    window_hours: int
    channels: list[ChannelCardOut]
    voice: VoiceCardOut
    budget_daily_spent_minor_units: int
    budget_daily_limit_minor_units: int | None
    budget_monthly_spent_minor_units: int
    budget_monthly_limit_minor_units: int | None
    cost_currency: str
    controls_note: str


@router.get("/notifications", response_model=NotificationOverviewOut)
def admin_notifications(
    hours: int = 24,
    db: Session = Depends(get_session),
    _principal: AdminPrincipal = Depends(require_admin_role(*READ_ROLES)),
) -> NotificationOverviewOut:
    window_hours = max(1, min(hours, 24 * 30))
    now = datetime.now(UTC)
    since = now - timedelta(hours=window_hours)

    deliveries = db.exec(
        select(NotificationDelivery).where(NotificationDelivery.created_at >= since)
    ).all()
    templates = db.exec(select(NotificationTemplate)).all()
    contacts = db.exec(select(ContactPoint)).all()
    budget = evaluate_budget(db, now=now)

    channels = [
        _channel_card(
            channel,
            deliveries=[d for d in deliveries if d.channel == channel.value],
            templates=[t for t in templates if t.channel == channel.value],
            contacts=[c for c in contacts if c.channel == channel.value],
            now=now,
        )
        for channel in (
            NotificationChannel.EMAIL,
            NotificationChannel.SMS,
            NotificationChannel.WHATSAPP,
            NotificationChannel.IN_APP,
        )
    ]

    return NotificationOverviewOut(
        generated_at=now,
        window_hours=window_hours,
        channels=channels,
        voice=_voice_card(db, since=since),
        budget_daily_spent_minor_units=budget.daily_spent_minor_units,
        budget_daily_limit_minor_units=budget.daily_budget_minor_units,
        budget_monthly_spent_minor_units=budget.monthly_spent_minor_units,
        budget_monthly_limit_minor_units=budget.monthly_budget_minor_units,
        cost_currency=budget.currency,
        controls_note=(
            "Disable a channel through its provider policy; reminders are then "
            "suppressed with a reason rather than lost, and in-app delivery "
            "keeps working. A configured channel is not an entitled one: DLT, "
            "sending-domain, and WhatsApp approvals are not visible from here."
        ),
    )


def _channel_card(
    channel: NotificationChannel,
    *,
    deliveries: list[NotificationDelivery],
    templates: list[NotificationTemplate],
    contacts: list[ContactPoint],
    now: datetime,
) -> ChannelCardOut:
    policy = channel_policy(channel)
    counts = {status: 0 for status in DeliveryStatus}
    for row in deliveries:
        try:
            counts[DeliveryStatus(row.status)] += 1
        except ValueError:
            continue

    in_flight = [
        row
        for row in deliveries
        if row.status in (DeliveryStatus.ACCEPTED.value, DeliveryStatus.SENDING.value)
    ]
    stale = [row for row in in_flight if _as_utc(row.updated_at) < now - STALE_AFTER]

    reached = counts[DeliveryStatus.DELIVERED] + counts[DeliveryStatus.SEEN]
    attempted = reached + counts[DeliveryStatus.FAILED] + len(in_flight)

    approved = [t for t in templates if t.active and t.approval_status == "approved"]
    template_ready = (
        any(t.provider_template_name for t in approved)
        if channel in PREAPPROVAL_REQUIRED
        else True
    )

    errors: dict[str, int] = {}
    for row in deliveries:
        if row.provider_error_class:
            errors[row.provider_error_class] = errors.get(row.provider_error_class, 0) + 1

    return ChannelCardOut(
        channel=channel.value,
        configured=(
            True
            if channel is NotificationChannel.IN_APP
            else settings.infobip_channel_ready(channel.value)
        ),
        policy_enabled=bool(policy.get("enabled", False)),
        circuit_state=str(policy.get("circuit_state", "closed")),
        primary_provider=str(policy.get("primary_provider", "")),
        fallback_provider=str(policy.get("fallback_provider", "")),
        sender_ready=_sender_ready(channel),
        templates_total=len(templates),
        templates_approved=len(approved),
        template_ready=template_ready,
        accepted=counts[DeliveryStatus.ACCEPTED],
        delivered=reached,
        failed=counts[DeliveryStatus.FAILED],
        suppressed=counts[DeliveryStatus.SUPPRESSED],
        awaiting_report=len(in_flight),
        stale_awaiting_report=len(stale),
        delivery_rate=(reached / attempted) if attempted else 0.0,
        last_success_at=_latest(row.delivered_at for row in deliveries),
        last_failure_at=_latest(row.failed_at for row in deliveries),
        last_report_at=_latest(
            row.updated_at for row in deliveries if row.external_message_id
        ),
        top_error_class=max(errors, key=errors.get) if errors else "",  # type: ignore[arg-type]
        cost_minor_units=sum(row.cost_minor_units or 0 for row in deliveries),
        cost_currency=settings.infobip_cost_currency,
        verified_contacts=sum(1 for c in contacts if c.verification_status == "verified"),
        opted_out_contacts=sum(1 for c in contacts if c.consent_status == "opted_out"),
        note=_note_for(channel, stale=len(stale), template_ready=template_ready),
    )


def _note_for(channel: NotificationChannel, *, stale: int, template_ready: bool) -> str:
    if channel is NotificationChannel.IN_APP:
        return "Always available. Used as the fallback when an external channel is off."
    # Ordered by what already happened over what is merely configured: messages
    # accepted with no report mean something went out and vanished, which is
    # more urgent than a template that has not been registered yet.
    if stale:
        return (
            f"{stale} message(s) accepted but never reported on. Check that delivery "
            "callbacks are reaching /api/webhooks/infobip."
        )
    if not template_ready:
        return "No approved provider template. Sending is refused until one is registered."
    return ""


def _sender_ready(channel: NotificationChannel) -> bool:
    return {
        NotificationChannel.EMAIL: bool(settings.infobip_email_sender.strip()),
        NotificationChannel.SMS: bool(settings.infobip_sms_sender.strip()),
        NotificationChannel.WHATSAPP: bool(settings.infobip_whatsapp_sender.strip()),
        NotificationChannel.IN_APP: True,
    }.get(channel, False)


def _voice_card(db: Session, *, since: datetime) -> VoiceCardOut:
    rows = db.exec(select(CallSession).where(CallSession.started_at >= since)).all()
    durations = [row.duration_seconds for row in rows if row.duration_seconds is not None]
    # Voice lives under the "telephony" policy scope, not a messaging channel.
    policy = get_effective_provider_policy("telephony")
    return VoiceCardOut(
        configured=settings.infobip_channel_ready("voice"),
        policy_enabled=bool(policy.get("enabled", False)),
        calls=len(rows),
        answered=sum(1 for row in rows if row.answered_at is not None),
        ended=sum(1 for row in rows if row.ended_at is not None),
        average_duration_seconds=(sum(durations) / len(durations)) if durations else 0.0,
        note="Clip-based inbound only. Outbound calling is not implemented.",
    )


def _latest(values) -> datetime | None:
    present = [value for value in values if value is not None]
    return max(present) if present else None


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def notification_metrics(db: Session, *, window_minutes: int = 60) -> dict[str, int]:
    """Aggregate counters for the Prometheus endpoint.

    Deliberately unlabelled by channel: the metrics endpoint is for alert
    thresholds, and per-channel breakdowns belong in the admin console where
    access is authenticated.
    """
    since = datetime.now(UTC) - timedelta(minutes=window_minutes)
    rows = db.exec(
        select(NotificationDelivery.status, func.count())
        .where(NotificationDelivery.created_at >= since)
        .group_by(NotificationDelivery.status)
    ).all()
    counts = {str(status): int(count) for status, count in rows}

    stale = int(
        db.exec(
            select(func.count())
            .select_from(NotificationDelivery)
            .where(
                NotificationDelivery.status.in_(  # type: ignore[union-attr]
                    [DeliveryStatus.ACCEPTED.value, DeliveryStatus.SENDING.value]
                ),
                NotificationDelivery.updated_at < datetime.now(UTC) - STALE_AFTER,
            )
        ).one()
        or 0
    )
    return {
        "sent": counts.get(DeliveryStatus.ACCEPTED.value, 0),
        "delivered": counts.get(DeliveryStatus.DELIVERED.value, 0)
        + counts.get(DeliveryStatus.SEEN.value, 0),
        "failed": counts.get(DeliveryStatus.FAILED.value, 0),
        "suppressed": counts.get(DeliveryStatus.SUPPRESSED.value, 0),
        "stale_awaiting_report": stale,
    }
