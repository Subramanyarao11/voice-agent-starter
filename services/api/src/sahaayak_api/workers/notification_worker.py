"""Dispatching due reminders on external channels.

A separate process, not a background task inside the API. Sending an SMS means
waiting on a third party that may take ten seconds to fail, and a citizen
waiting on an API response must never be behind that queue.

Three properties drive the design.

*Claims are leases, not flags.* A worker that is killed mid-send does not
strand a reminder forever; the lease expires and another worker picks it up.
Combined with the stable idempotency key, a lease that expires while a send was
actually in flight cannot bill the caller's phone twice.

*Gates are re-checked at send time, not trusted from creation time.* A reminder
set three weeks ago may belong to someone who has since opted out, or to a
channel an operator has since disabled. The state that matters is the state now.

*Nothing is deleted on failure.* A suppressed reminder keeps its row and its
reason, because "we chose not to send this" is something an operator has to be
able to see and explain.
"""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlmodel import Session, select

from sahaayak_api.notifications import (
    check_channel,
    create_delivery,
    dispatch,
    get_provider,
    resolve,
    suppress,
)
from sahaayak_api.notifications.dispatcher import Gate
from sahaayak_api.notifications.templates import TemplateNotFound
from sahaayak_api.telemetry import record_telemetry
from sahaayak_common import (
    Benefit,
    ContactPoint,
    NotificationDelivery,
    Reminder,
    UserSession,
    get_logger,
    session_scope,
    settings,
)
from sahaayak_contracts import DeliveryStatus, NotificationChannel

log = get_logger(__name__)

# How long a claimed reminder stays invisible to other workers. Long enough to
# cover a slow provider plus retries within one attempt, short enough that a
# killed worker's reminders are picked up while they still matter.
LEASE_SECONDS = 300

# Attempts before a reminder is abandoned. Each attempt is a separate provider
# call on a separate schedule; this is not the in-request retry count.
MAX_ATTEMPTS = 4

# Backoff between attempts. Deliberately in minutes: a reminder is not
# latency-sensitive, and a provider having a bad ten minutes should not cost
# the message.
RETRY_BASE_SECONDS = 120
RETRY_MAX_SECONDS = 3600

# A reminder nobody dispatched within this window is stale. Delivering a
# deadline reminder a week after the deadline is worse than not sending it.
MAX_LATENESS = timedelta(days=2)

BATCH_SIZE = 20


@dataclass
class RunStats:
    claimed: int = 0
    sent: int = 0
    suppressed: int = 0
    failed: int = 0
    retrying: int = 0
    reasons: dict[str, int] = field(default_factory=dict)

    def note(self, reason: str) -> None:
        self.reasons[reason] = self.reasons.get(reason, 0) + 1

    def as_metadata(self) -> dict[str, int | str]:
        return {
            "claimed": self.claimed,
            "sent": self.sent,
            "suppressed": self.suppressed,
            "failed": self.failed,
            "retrying": self.retrying,
        }


def _supports_skip_locked() -> bool:
    """SQLite has no row-level locking; the lease alone serializes there.

    Fine for local development, where there is one worker. Production runs
    Postgres and gets real row claiming.
    """
    return not settings.using_sqlite


def claim_due_reminders(
    db: Session, *, now: datetime, limit: int = BATCH_SIZE
) -> list[Reminder]:
    """Take a lease on up to ``limit`` reminders that are ready to send.

    in-app reminders are never claimed. They have no external delivery step;
    the row itself is what the browser reads.
    """
    statement = (
        select(Reminder)
        .where(
            Reminder.status == "scheduled",
            Reminder.channel != NotificationChannel.IN_APP.value,
            Reminder.due_at <= now,
            # Null next_attempt_at means it was never scheduled for dispatch,
            # which for an external reminder is a bug rather than a state to
            # act on, so it is left alone and visible.
            Reminder.next_attempt_at.is_not(None),  # type: ignore[union-attr]
            Reminder.next_attempt_at <= now,  # type: ignore[operator]
        )
        .order_by(Reminder.due_at.asc())
        .limit(limit)
    )
    if _supports_skip_locked():
        statement = statement.with_for_update(skip_locked=True)

    rows = list(db.exec(statement).all())
    lease_until = now + timedelta(seconds=LEASE_SECONDS)
    for row in rows:
        row.next_attempt_at = lease_until
        db.add(row)
    db.commit()
    for row in rows:
        db.refresh(row)
    return rows


class NotificationWorker:
    """Claims due reminders and sends them, one batch at a time."""

    def __init__(self, *, batch_size: int = BATCH_SIZE) -> None:
        self.batch_size = batch_size

    async def run_once(self, *, now: datetime | None = None) -> RunStats:
        moment = now or datetime.now(UTC)
        stats = RunStats()

        with session_scope() as db:
            reminders = claim_due_reminders(db, now=moment, limit=self.batch_size)
            stats.claimed = len(reminders)

            for reminder in reminders:
                await self._process(db, reminder, stats=stats, now=moment)

            db.commit()

        if stats.claimed:
            log.info("notification_worker_batch", **stats.as_metadata())
            record_telemetry(
                event_type="notification",
                route="worker/notifications",
                method="WORKER",
                surface="system",
                outcome="processed",
                safe_metadata=stats.as_metadata(),
            )
        return stats

    async def run_forever(self, *, interval_seconds: float = 30.0) -> None:  # pragma: no cover
        log.info("notification_worker_started", interval_seconds=interval_seconds)
        while True:
            try:
                await self.run_once()
            except Exception as exc:
                # One bad batch must not end the process; the lease on those
                # reminders expires and they are retried.
                log.error(
                    "notification_worker_batch_failed",
                    error=str(exc),
                    error_type=exc.__class__.__name__,
                    exc_info=True,
                )
            await asyncio.sleep(interval_seconds)

    async def _process(
        self, db: Session, reminder: Reminder, *, stats: RunStats, now: datetime
    ) -> None:
        channel = _channel_of(reminder)
        if channel is None:
            self._abandon(db, reminder, reason="unknown_channel", stats=stats)
            return

        if _as_utc(reminder.due_at) < now - MAX_LATENESS:
            # Better to say nothing than to tell someone about a deadline that
            # has already passed.
            self._abandon(db, reminder, reason="too_late", stats=stats)
            return

        contact = (
            db.get(ContactPoint, reminder.contact_point_id)
            if reminder.contact_point_id
            else None
        )
        template_key = reminder.template_key or "benefit_reminder"
        session_row = db.get(UserSession, reminder.session_id)

        # Re-checked now, not trusted from when the reminder was created.
        availability = check_channel(
            db,
            channel=channel,
            contact=contact,
            session_id=reminder.session_id,
            template_key=template_key,
            locale=_locale_of(contact),
            state_code=session_row.state_code if session_row else None,
            respect_rollout=True,
        )
        if not availability.available:
            self._suppress(db, reminder, channel=channel, gate=availability.gate, stats=stats)
            return

        provider = get_provider(channel, allow_fallback=False)
        if provider is None or not provider.available():
            self._suppress(
                db,
                reminder,
                channel=channel,
                gate=Gate("provider_not_configured"),
                stats=stats,
            )
            return

        try:
            template = resolve(
                db, template_key=template_key, channel=channel, locale=_locale_of(contact)
            )
        except TemplateNotFound:
            self._abandon(db, reminder, reason="template_missing", stats=stats)
            return

        delivery = self._delivery_for(
            db,
            reminder,
            channel=channel,
            template_key=template_key,
            locale=template.locale,
            provider_name=provider.name,
        )
        result = await dispatch(
            db,
            provider=provider,
            contact=contact,
            delivery=delivery,
            template=template,
            variables=_variables_for(db, reminder),
        )

        reminder.last_delivery_id = delivery.id
        if result.accepted:
            stats.sent += 1
            # Not "delivered": that is the delivery report's word, and the
            # webhook will close the reminder when it arrives.
            reminder.next_attempt_at = None
            reminder.status = "scheduled"
            db.add(reminder)
            return

        if result.retryable and delivery.attempt_count < MAX_ATTEMPTS:
            delay = _retry_delay(delivery.attempt_count, result.retry_after_seconds)
            reminder.next_attempt_at = now + timedelta(seconds=delay)
            delivery.next_attempt_at = reminder.next_attempt_at
            # Back to queued rather than left failed: the row is the same
            # logical send, waiting for its next attempt. Leaving it FAILED
            # would show an operator a failure that is still in progress.
            delivery.status = DeliveryStatus.QUEUED.value
            delivery.failed_at = None
            db.add(reminder)
            db.add(delivery)
            stats.retrying += 1
            stats.note(result.error_class.value)
            log.info(
                "notification_retry_scheduled",
                reminder_id=reminder.id,
                channel=channel.value,
                attempt=delivery.attempt_count,
                delay_seconds=delay,
                error_class=result.error_class.value,
            )
            return

        reminder.status = "failed"
        reminder.next_attempt_at = None
        db.add(reminder)
        stats.failed += 1
        stats.note(result.error_class.value)
        log.warning(
            "notification_permanently_failed",
            reminder_id=reminder.id,
            channel=channel.value,
            attempts=delivery.attempt_count,
            error_class=result.error_class.value,
        )

    def _delivery_for(
        self,
        db: Session,
        reminder: Reminder,
        *,
        channel: NotificationChannel,
        template_key: str,
        locale: str,
        provider_name: str,
    ) -> NotificationDelivery:
        """The delivery row for this send, reused across retries.

        One logical send is one row. Creating a fresh row per attempt would
        restart the attempt counter — so the give-up ceiling would never be
        reached and a failing provider would be retried forever — and would
        also collide on the idempotency key, which is derived from the
        reminder rather than the attempt.
        """
        existing = (
            db.get(NotificationDelivery, reminder.last_delivery_id)
            if reminder.last_delivery_id
            else None
        )
        if existing is not None and existing.status not in (
            DeliveryStatus.DELIVERED.value,
            DeliveryStatus.SEEN.value,
            DeliveryStatus.CANCELLED.value,
        ):
            existing.provider = provider_name
            existing.locale = locale
            db.add(existing)
            return existing

        return create_delivery(
            db,
            channel=channel,
            session_id=reminder.session_id,
            template_key=template_key,
            locale=locale,
            reminder_id=reminder.id,
            contact_point_id=reminder.contact_point_id,
            provider=provider_name,
        )

    def _suppress(
        self,
        db: Session,
        reminder: Reminder,
        *,
        channel: NotificationChannel,
        gate: Gate,
        stats: RunStats,
    ) -> None:
        """Record a deliberate non-send, keeping the reminder intact.

        The reminder is not cancelled: an operator re-enabling the channel, or
        a caller opting back in, should make it deliverable again rather than
        require it to be recreated.
        """
        delivery = create_delivery(
            db,
            channel=channel,
            session_id=reminder.session_id,
            template_key=reminder.template_key or "benefit_reminder",
            locale="en",
            reminder_id=reminder.id,
            contact_point_id=reminder.contact_point_id,
        )
        suppress(db, delivery, gate=gate)
        reminder.last_delivery_id = delivery.id
        reminder.next_attempt_at = None
        db.add(reminder)
        stats.suppressed += 1
        stats.note(str(gate))
        log.info(
            "notification_suppressed",
            reminder_id=reminder.id,
            channel=channel.value,
            gate=str(gate),
        )

    def _abandon(
        self, db: Session, reminder: Reminder, *, reason: str, stats: RunStats
    ) -> None:
        reminder.status = "failed"
        reminder.next_attempt_at = None
        db.add(reminder)
        stats.failed += 1
        stats.note(reason)
        log.warning(
            "notification_abandoned", reminder_id=reminder.id, reason=reason
        )


def _retry_delay(attempt: int, retry_after_seconds: int | None) -> float:
    """Backoff for the next attempt, honouring a provider's own pacing."""
    if retry_after_seconds is not None:
        return float(min(retry_after_seconds, RETRY_MAX_SECONDS))
    ceiling = min(RETRY_MAX_SECONDS, RETRY_BASE_SECONDS * (2 ** max(0, attempt - 1)))
    # Jittered so a provider outage does not produce a synchronized stampede
    # when every reminder retries at the same instant.
    return round(ceiling * (0.5 + random.random() / 2), 2)


def _channel_of(reminder: Reminder) -> NotificationChannel | None:
    try:
        return NotificationChannel(reminder.channel)
    except ValueError:
        return None


def _locale_of(contact: ContactPoint | None) -> str:
    return (contact.locale if contact and contact.locale else "en") or "en"


def _variables_for(db: Session, reminder: Reminder) -> dict[str, str]:
    """Template variables for one reminder.

    Only the benefit's public identity and its source link. Nothing from the
    caller's profile goes into an outbound message.
    """
    benefit = db.get(Benefit, reminder.benefit_id)
    return {
        "benefit_name": benefit.name if benefit else reminder.benefit_id,
        "source_url": (
            (benefit.source_document_url or benefit.source_url) if benefit else ""
        ),
        "due_date": _as_utc(reminder.due_at).strftime("%d %b %Y"),
    }


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def pending_delivery_count(db: Session) -> int:
    """Deliveries accepted by a provider but not yet reported on.

    Exposed for the admin console and alerting: a number that climbs and never
    falls means delivery reports have stopped arriving.
    """
    return len(
        db.exec(
            select(NotificationDelivery).where(
                NotificationDelivery.status.in_(  # type: ignore[union-attr]
                    [DeliveryStatus.ACCEPTED.value, DeliveryStatus.SENDING.value]
                )
            )
        ).all()
    )
