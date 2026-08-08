"""Reminder dispatch: claiming, gate re-checks, retries, and suppression.

The gate re-check tests carry the weight. A reminder set three weeks ago may
belong to someone who has since opted out or to a channel an operator has since
switched off, and the worker must act on the state now rather than the state
when the reminder was created.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from cryptography.fernet import Fernet
from sqlmodel import Session, select

from sahaayak_api.notifications import register_provider, reset_providers
from sahaayak_api.notifications.base import OutboundNotification
from sahaayak_api.workers.notification_worker import (
    MAX_ATTEMPTS,
    NotificationWorker,
    claim_due_reminders,
    pending_delivery_count,
)
from sahaayak_common import (
    ContactPoint,
    FeatureFlag,
    NotificationDelivery,
    ProviderPolicy,
    Reminder,
    UserSession,
    encrypt_destination,
    engine,
    new_id,
    reset_encryption_cache,
    settings,
)
from sahaayak_contracts import (
    DeliveryStatus,
    NotificationChannel,
    ProviderErrorClass,
    ProviderSendResult,
)

PHONE = "+919876543210"


class ScriptedProvider:
    """A provider whose outcome each test decides."""

    name = "test_sms"
    channel = NotificationChannel.SMS

    def __init__(self, *results: ProviderSendResult) -> None:
        self.queue = list(results)
        self.sent: list[OutboundNotification] = []

    def available(self) -> bool:
        return True

    async def send(self, notification: OutboundNotification) -> ProviderSendResult:
        self.sent.append(notification)
        if self.queue:
            return self.queue.pop(0)
        return accepted()


def accepted() -> ProviderSendResult:
    return ProviderSendResult(
        accepted=True,
        provider="test_sms",
        channel=NotificationChannel.SMS,
        status=DeliveryStatus.ACCEPTED,
        external_message_id=new_id("ext"),
    )


def transient() -> ProviderSendResult:
    return ProviderSendResult.failure(
        provider="test_sms",
        channel=NotificationChannel.SMS,
        error_class=ProviderErrorClass.PROVIDER_ERROR,
        detail="upstream 503",
    )


def permanent() -> ProviderSendResult:
    return ProviderSendResult.failure(
        provider="test_sms",
        channel=NotificationChannel.SMS,
        error_class=ProviderErrorClass.INVALID_DESTINATION,
        detail="unknown subscriber",
    )


@pytest.fixture(autouse=True)
def isolated_queue(database):
    """Start every test with an empty queue.

    The worker claims across the whole table, so a reminder left by an earlier
    test is indistinguishable from one this test created. Cleaning up front
    rather than after means a failing test cannot poison the next one.
    """
    _wipe()
    yield
    _wipe()
    reset_providers()


def _wipe() -> None:
    from sahaayak_common import ConsentEvent, NotificationTemplate

    with Session(engine) as db:
        for model in (
            NotificationDelivery,
            NotificationTemplate,
            ConsentEvent,
            Reminder,
            ContactPoint,
        ):
            for row in db.query(model).all():
                db.delete(row)
        db.commit()


@pytest.fixture
def sms_ready(monkeypatch, database):
    monkeypatch.setattr(
        settings,
        "infobip_contact_encryption_key",
        Fernet.generate_key().decode(),
        raising=False,
    )
    reset_encryption_cache()
    monkeypatch.setattr(settings, "infobip_enabled", True, raising=False)
    monkeypatch.setattr(settings, "infobip_base_url", "https://x.api.infobip.com", raising=False)
    monkeypatch.setattr(settings, "infobip_api_key", "k", raising=False)
    monkeypatch.setattr(settings, "infobip_sms_enabled", True, raising=False)
    monkeypatch.setattr(settings, "infobip_sms_sender", "SAHAYK", raising=False)

    previous_flag: tuple[bool, int, list[str], list[str]] | None = None
    with Session(engine) as db:
        flag = db.exec(
            select(FeatureFlag).where(FeatureFlag.key == "infobip_reminders")
        ).first()
        if flag is not None:
            previous_flag = (
                flag.enabled,
                flag.rollout_percentage,
                list(flag.target_languages),
                list(flag.target_states),
            )
            flag.enabled = True
            flag.rollout_percentage = 100
            flag.target_languages = []
            flag.target_states = []
            db.add(flag)
        db.merge(
            ProviderPolicy(
                id=new_id("pp"),
                provider="sms",
                scope="*",
                enabled=True,
                primary_provider="infobip_sms",
                fallback_provider="in_app",
            )
        )
        db.commit()
    yield
    reset_encryption_cache()
    reset_providers()
    with Session(engine) as db:
        flag = db.exec(
            select(FeatureFlag).where(FeatureFlag.key == "infobip_reminders")
        ).first()
        if flag is not None and previous_flag is not None:
            flag.enabled, flag.rollout_percentage, flag.target_languages, flag.target_states = (
                previous_flag
            )
            db.add(flag)
        for row in db.query(ProviderPolicy).all():
            db.delete(row)
        db.commit()


@pytest.fixture
def due_reminder(sms_ready):
    """A verified, consenting contact with an SMS reminder due now."""
    from scripts.seed_demo import DEMO_BENEFITS

    ids = {
        "session": new_id("ses"),
        "contact": new_id("cp"),
        "reminder": new_id("rem"),
    }
    now = datetime.now(UTC)
    with Session(engine) as db:
        db.add(
            UserSession(
                id=ids["session"],
                phone_or_session_id=new_id("caller"),
                state_code="KA",
                language_code="en",
            )
        )
        db.add(
            ContactPoint(
                id=ids["contact"],
                session_id=ids["session"],
                channel="sms",
                destination_ciphertext=encrypt_destination(PHONE),
                destination_hash=new_id("h"),
                display_suffix="******3210",
                locale="en",
                verification_status="verified",
                consent_status="opted_in",
                verified_at=now,
            )
        )
        db.add(
            Reminder(
                id=ids["reminder"],
                session_id=ids["session"],
                benefit_id=DEMO_BENEFITS[0]["id"],
                due_at=now - timedelta(minutes=1),
                channel="sms",
                contact_point_id=ids["contact"],
                template_key="benefit_reminder",
                next_attempt_at=now - timedelta(minutes=1),
            )
        )
        db.commit()
    return ids


def approve_sms_template() -> None:
    from sahaayak_common import NotificationTemplate

    with Session(engine) as db:
        db.add(
            NotificationTemplate(
                id=new_id("nt"),
                template_key="benefit_reminder",
                channel="sms",
                locale="en",
                provider_template_name="benefit_reminder_utility_en",
                body="You may qualify for {benefit_name}. {source_url}",
                approval_status="approved",
                active=True,
            )
        )
        db.commit()


def read_reminder(reminder_id: str) -> Reminder:
    with Session(engine) as db:
        return db.get(Reminder, reminder_id)


def deliveries_for(reminder_id: str) -> list[NotificationDelivery]:
    with Session(engine) as db:
        return list(
            db.query(NotificationDelivery)
            .filter(NotificationDelivery.reminder_id == reminder_id)
            .all()
        )


# --- Claiming -------------------------------------------------------------


def test_an_in_app_reminder_is_never_claimed(sms_ready) -> None:
    """It has no external delivery step; the row is what the browser reads."""
    from scripts.seed_demo import DEMO_BENEFITS

    session_id = new_id("ses")
    now = datetime.now(UTC)
    with Session(engine) as db:
        db.add(
            UserSession(
                id=session_id,
                phone_or_session_id=new_id("caller"),
                state_code="KA",
                language_code="en",
            )
        )
        db.add(
            Reminder(
                id=new_id("rem"),
                session_id=session_id,
                benefit_id=DEMO_BENEFITS[0]["id"],
                due_at=now - timedelta(minutes=1),
                channel="in_app",
                next_attempt_at=now - timedelta(minutes=1),
            )
        )
        db.commit()

        claimed = claim_due_reminders(db, now=now)
    assert all(row.channel != "in_app" for row in claimed)


def test_a_future_reminder_is_not_claimed(sms_ready, due_reminder) -> None:
    with Session(engine) as db:
        row = db.get(Reminder, due_reminder["reminder"])
        row.due_at = datetime.now(UTC) + timedelta(days=1)
        row.next_attempt_at = row.due_at
        db.add(row)
        db.commit()

        claimed = claim_due_reminders(db, now=datetime.now(UTC))
    assert due_reminder["reminder"] not in {row.id for row in claimed}


def test_claiming_takes_a_lease_so_a_second_worker_skips_it(
    sms_ready, due_reminder
) -> None:
    now = datetime.now(UTC)
    with Session(engine) as db:
        first = claim_due_reminders(db, now=now)
        assert due_reminder["reminder"] in {row.id for row in first}

        second = claim_due_reminders(db, now=now)
    assert due_reminder["reminder"] not in {row.id for row in second}


def test_an_expired_lease_is_reclaimed(sms_ready, due_reminder) -> None:
    """A worker killed mid-send must not strand the reminder forever."""
    now = datetime.now(UTC)
    with Session(engine) as db:
        claim_due_reminders(db, now=now)
        later = now + timedelta(hours=1)
        reclaimed = claim_due_reminders(db, now=later)
    assert due_reminder["reminder"] in {row.id for row in reclaimed}


# --- Sending --------------------------------------------------------------


async def test_a_due_reminder_is_sent(sms_ready, due_reminder) -> None:
    approve_sms_template()
    provider = ScriptedProvider(accepted())
    register_provider(NotificationChannel.SMS, provider)

    stats = await NotificationWorker().run_once()

    assert stats.sent == 1
    assert len(provider.sent) == 1
    rows = deliveries_for(due_reminder["reminder"])
    assert [row.status for row in rows] == [DeliveryStatus.ACCEPTED.value]


async def test_an_accepted_send_does_not_mark_the_reminder_delivered(
    sms_ready, due_reminder
) -> None:
    """Delivered is the delivery report's word; the webhook closes the row."""
    approve_sms_template()
    register_provider(NotificationChannel.SMS, ScriptedProvider(accepted()))

    await NotificationWorker().run_once()

    reminder = read_reminder(due_reminder["reminder"])
    assert reminder.status == "scheduled"
    assert reminder.delivered_at is None
    assert reminder.next_attempt_at is None


async def test_the_message_carries_no_caller_profile_data(
    sms_ready, due_reminder
) -> None:
    approve_sms_template()
    provider = ScriptedProvider(accepted())
    register_provider(NotificationChannel.SMS, provider)

    await NotificationWorker().run_once()

    text = provider.sent[0].message.text
    assert due_reminder["session"] not in text
    assert PHONE not in text


async def test_a_sent_reminder_is_not_sent_again_on_the_next_run(
    sms_ready, due_reminder
) -> None:
    approve_sms_template()
    provider = ScriptedProvider(accepted(), accepted())
    register_provider(NotificationChannel.SMS, provider)

    await NotificationWorker().run_once()
    await NotificationWorker().run_once()

    assert len(provider.sent) == 1


# --- Gate re-checks at send time ------------------------------------------


async def test_consent_withdrawn_after_scheduling_suppresses_the_send(
    sms_ready, due_reminder
) -> None:
    approve_sms_template()
    provider = ScriptedProvider(accepted())
    register_provider(NotificationChannel.SMS, provider)

    with Session(engine) as db:
        contact = db.get(ContactPoint, due_reminder["contact"])
        contact.consent_status = "opted_out"
        db.add(contact)
        db.commit()

    stats = await NotificationWorker().run_once()

    assert stats.suppressed == 1
    assert not provider.sent
    rows = deliveries_for(due_reminder["reminder"])
    assert rows[0].status == DeliveryStatus.SUPPRESSED.value


async def test_a_channel_disabled_after_scheduling_suppresses_the_send(
    sms_ready, due_reminder
) -> None:
    approve_sms_template()
    provider = ScriptedProvider(accepted())
    register_provider(NotificationChannel.SMS, provider)

    with Session(engine) as db:
        policy = db.query(ProviderPolicy).filter(ProviderPolicy.provider == "sms").first()
        policy.enabled = False
        db.add(policy)
        db.commit()

    stats = await NotificationWorker().run_once()

    assert stats.suppressed == 1
    assert not provider.sent


async def test_a_suppressed_reminder_is_kept_not_cancelled(
    sms_ready, due_reminder
) -> None:
    """Re-enabling the channel should make it deliverable again."""
    approve_sms_template()
    register_provider(NotificationChannel.SMS, ScriptedProvider(accepted()))
    with Session(engine) as db:
        contact = db.get(ContactPoint, due_reminder["contact"])
        contact.consent_status = "opted_out"
        db.add(contact)
        db.commit()

    await NotificationWorker().run_once()

    reminder = read_reminder(due_reminder["reminder"])
    assert reminder.status == "scheduled"


async def test_an_unapproved_template_suppresses_rather_than_sending(
    sms_ready, due_reminder
) -> None:
    """SMS without a registered DLT template is rejected by the operator anyway."""
    provider = ScriptedProvider(accepted())
    register_provider(NotificationChannel.SMS, provider)

    stats = await NotificationWorker().run_once()

    assert stats.suppressed == 1
    assert not provider.sent


async def test_a_long_overdue_reminder_is_abandoned(sms_ready, due_reminder) -> None:
    """Telling someone about a deadline that has passed is worse than silence."""
    approve_sms_template()
    provider = ScriptedProvider(accepted())
    register_provider(NotificationChannel.SMS, provider)

    with Session(engine) as db:
        row = db.get(Reminder, due_reminder["reminder"])
        row.due_at = datetime.now(UTC) - timedelta(days=30)
        db.add(row)
        db.commit()

    stats = await NotificationWorker().run_once()

    assert stats.failed == 1
    assert not provider.sent
    assert read_reminder(due_reminder["reminder"]).status == "failed"


# --- Retries --------------------------------------------------------------


async def test_a_transient_failure_is_rescheduled(sms_ready, due_reminder) -> None:
    approve_sms_template()
    register_provider(NotificationChannel.SMS, ScriptedProvider(transient()))

    stats = await NotificationWorker().run_once()

    assert stats.retrying == 1
    reminder = read_reminder(due_reminder["reminder"])
    assert reminder.status == "scheduled"
    assert reminder.next_attempt_at is not None
    assert reminder.next_attempt_at > datetime.now(UTC).replace(tzinfo=None)


async def test_a_permanent_failure_is_not_retried(sms_ready, due_reminder) -> None:
    approve_sms_template()
    provider = ScriptedProvider(permanent())
    register_provider(NotificationChannel.SMS, provider)

    stats = await NotificationWorker().run_once()

    assert stats.failed == 1
    assert stats.retrying == 0
    assert read_reminder(due_reminder["reminder"]).status == "failed"


async def test_repeated_transient_failures_eventually_give_up(
    sms_ready, due_reminder
) -> None:
    approve_sms_template()
    register_provider(
        NotificationChannel.SMS, ScriptedProvider(*[transient()] * (MAX_ATTEMPTS + 2))
    )
    worker = NotificationWorker()

    now = datetime.now(UTC)
    for attempt in range(MAX_ATTEMPTS + 1):
        # Jump past each backoff window rather than sleeping through it.
        await worker.run_once(now=now + timedelta(hours=attempt * 2))

    assert read_reminder(due_reminder["reminder"]).status == "failed"


async def test_each_attempt_reuses_one_delivery_row(sms_ready, due_reminder) -> None:
    """Otherwise the delivery log grows a duplicate per retry."""
    approve_sms_template()
    register_provider(NotificationChannel.SMS, ScriptedProvider(transient(), accepted()))
    worker = NotificationWorker()

    now = datetime.now(UTC)
    await worker.run_once(now=now)
    await worker.run_once(now=now + timedelta(hours=2))

    rows = deliveries_for(due_reminder["reminder"])
    assert len(rows) == 1, "a retry must not create a second delivery record"


# --- Reporting ------------------------------------------------------------


async def test_pending_count_tracks_deliveries_awaiting_a_report(
    sms_ready, due_reminder
) -> None:
    approve_sms_template()
    register_provider(NotificationChannel.SMS, ScriptedProvider(accepted()))

    await NotificationWorker().run_once()

    with Session(engine) as db:
        assert pending_delivery_count(db) >= 1


async def test_an_empty_queue_is_a_no_op(sms_ready) -> None:
    stats = await NotificationWorker().run_once()
    assert stats.claimed == 0
    assert stats.sent == 0
