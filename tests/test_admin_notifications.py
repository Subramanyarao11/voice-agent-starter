"""The admin notifications view and the messaging metrics.

The property under test is the one an operator most needs and is least likely
to notice: accepted is not delivered. A channel can look perfectly healthy by
send-side numbers while every message silently fails to arrive, so the view
must surface messages that were accepted and never reported on.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlmodel import Session

from sahaayak_api.routers.admin_notifications import STALE_AFTER, notification_metrics
from sahaayak_common import (
    ContactPoint,
    NotificationDelivery,
    NotificationTemplate,
    UserSession,
    engine,
    new_id,
)
from sahaayak_contracts import DeliveryStatus

ADMIN = {"X-Admin-Token": "test-admin-token"}


@pytest.fixture(autouse=True)
def clean(database):
    _wipe()
    yield
    _wipe()


def _wipe() -> None:
    with Session(engine) as db:
        for model in (NotificationDelivery, NotificationTemplate, ContactPoint):
            for row in db.query(model).all():
                db.delete(row)
        db.commit()


def make_session() -> str:
    session_id = new_id("ses")
    with Session(engine) as db:
        db.add(
            UserSession(
                id=session_id,
                phone_or_session_id=new_id("caller"),
                state_code="KA",
                language_code="en",
            )
        )
        db.commit()
    return session_id


def add_delivery(
    session_id: str,
    *,
    channel: str = "sms",
    status: DeliveryStatus = DeliveryStatus.ACCEPTED,
    updated_at: datetime | None = None,
    cost: int | None = None,
    error_class: str = "",
) -> str:
    row_id = new_id("nd")
    now = datetime.now(UTC)
    with Session(engine) as db:
        db.add(
            NotificationDelivery(
                id=row_id,
                session_id=session_id,
                channel=channel,
                provider="infobip",
                template_key="benefit_reminder",
                locale="en",
                internal_message_id=new_id("msg"),
                external_message_id=new_id("ext"),
                status=status.value,
                idempotency_key=new_id("snd"),
                cost_minor_units=cost,
                provider_error_class=error_class,
                created_at=now,
                updated_at=updated_at or now,
            )
        )
        db.commit()
    return row_id


def card(client, channel: str) -> dict:
    response = client.get("/api/admin/notifications", headers=ADMIN)
    assert response.status_code == 200, response.text
    return next(item for item in response.json()["channels"] if item["channel"] == channel)


# --- Access ---------------------------------------------------------------


def test_the_view_requires_a_workforce_token(client) -> None:
    response = client.get("/api/admin/notifications", headers={"X-Admin-Token": "wrong"})
    assert response.status_code in (401, 403)


def test_a_guest_session_token_does_not_open_the_admin_view(client, guest_session) -> None:
    session = guest_session()
    response = client.get("/api/admin/notifications", headers=session["headers"])
    assert response.status_code in (401, 403)


# --- Channel posture ------------------------------------------------------


def test_every_channel_is_reported(client) -> None:
    body = client.get("/api/admin/notifications", headers=ADMIN).json()
    assert {item["channel"] for item in body["channels"]} == {
        "email",
        "sms",
        "whatsapp",
        "in_app",
    }


def test_in_app_is_always_configured(client) -> None:
    assert card(client, "in_app")["configured"]


def test_external_channels_report_unconfigured_by_default(client) -> None:
    for channel in ("email", "sms", "whatsapp"):
        item = card(client, channel)
        assert not item["configured"]
        assert not item["policy_enabled"]


def test_sms_is_not_template_ready_without_a_registered_provider_template(client) -> None:
    """Sending would be rejected by the operator every time."""
    item = card(client, "sms")
    assert not item["template_ready"]
    assert "template" in item["note"].lower()


def test_registering_an_approved_template_makes_sms_template_ready(client) -> None:
    with Session(engine) as db:
        db.add(
            NotificationTemplate(
                id=new_id("nt"),
                template_key="benefit_reminder",
                channel="sms",
                locale="en",
                provider_template_name="benefit_reminder_utility_en",
                approval_status="approved",
                active=True,
            )
        )
        db.commit()

    item = card(client, "sms")
    assert item["template_ready"]
    assert item["templates_approved"] == 1


# --- Delivery reality -----------------------------------------------------


def test_accepted_is_counted_apart_from_delivered(client) -> None:
    session_id = make_session()
    add_delivery(session_id, status=DeliveryStatus.ACCEPTED)
    add_delivery(session_id, status=DeliveryStatus.DELIVERED)

    item = card(client, "sms")
    assert item["accepted"] == 1
    assert item["delivered"] == 1


def test_messages_accepted_but_never_reported_on_are_surfaced(client) -> None:
    """The failure mode that looks exactly like success from the send side."""
    session_id = make_session()
    add_delivery(
        session_id,
        status=DeliveryStatus.ACCEPTED,
        updated_at=datetime.now(UTC) - STALE_AFTER - timedelta(hours=1),
    )

    item = card(client, "sms")
    assert item["stale_awaiting_report"] == 1
    assert "callback" in item["note"].lower()


def test_a_recent_accepted_message_is_not_yet_stale(client) -> None:
    session_id = make_session()
    add_delivery(session_id, status=DeliveryStatus.ACCEPTED)

    item = card(client, "sms")
    assert item["awaiting_report"] == 1
    assert item["stale_awaiting_report"] == 0


def test_delivery_rate_reflects_what_actually_arrived(client) -> None:
    session_id = make_session()
    add_delivery(session_id, status=DeliveryStatus.DELIVERED)
    add_delivery(session_id, status=DeliveryStatus.FAILED)

    assert card(client, "sms")["delivery_rate"] == pytest.approx(0.5)


def test_suppression_is_reported_separately_from_failure(client) -> None:
    session_id = make_session()
    add_delivery(session_id, status=DeliveryStatus.SUPPRESSED)

    item = card(client, "sms")
    assert item["suppressed"] == 1
    assert item["failed"] == 0


def test_the_dominant_error_class_is_reported(client) -> None:
    session_id = make_session()
    for _ in range(3):
        add_delivery(session_id, status=DeliveryStatus.FAILED, error_class="invalid_destination")
    add_delivery(session_id, status=DeliveryStatus.FAILED, error_class="rate_limited")

    assert card(client, "sms")["top_error_class"] == "invalid_destination"


def test_cost_is_reported_in_minor_units_with_a_currency(client) -> None:
    session_id = make_session()
    add_delivery(session_id, cost=25)
    add_delivery(session_id, cost=30)

    item = card(client, "sms")
    assert item["cost_minor_units"] == 55
    assert item["cost_currency"] == "INR"


# --- Privacy --------------------------------------------------------------


def test_no_recipient_or_body_appears_anywhere_in_the_view(client) -> None:
    session_id = make_session()
    with Session(engine) as db:
        db.add(
            ContactPoint(
                id=new_id("cp"),
                session_id=session_id,
                channel="sms",
                destination_ciphertext="ciphertext",
                destination_hash="hash",
                display_suffix="******3210",
                verification_status="verified",
                consent_status="opted_in",
            )
        )
        db.commit()
    add_delivery(session_id)

    body = client.get("/api/admin/notifications", headers=ADMIN).text

    assert "******3210" not in body, "even a masked destination is unnecessary here"
    assert "ciphertext" not in body
    assert "hash" not in body


def test_contact_counts_are_aggregate_only(client) -> None:
    session_id = make_session()
    with Session(engine) as db:
        for status in ("opted_in", "opted_out"):
            db.add(
                ContactPoint(
                    id=new_id("cp"),
                    session_id=session_id,
                    channel="sms",
                    destination_ciphertext="c",
                    destination_hash=new_id("h"),
                    display_suffix="******0000",
                    verification_status="verified",
                    consent_status=status,
                )
            )
        db.commit()

    item = card(client, "sms")
    assert item["verified_contacts"] == 2
    assert item["opted_out_contacts"] == 1


# --- Metrics --------------------------------------------------------------


def test_metrics_expose_messaging_counters(client) -> None:
    session_id = make_session()
    add_delivery(session_id, status=DeliveryStatus.DELIVERED)

    body = client.get("/metrics").text

    assert "sahaayak_notification_delivery_total" in body
    assert "sahaayak_provider_webhook_lag_total" in body


def test_metrics_carry_no_channel_label(client) -> None:
    """A channel label would let an unauthenticated scraper infer what is on."""
    session_id = make_session()
    add_delivery(session_id, channel="whatsapp")

    body = client.get("/metrics").text

    for line in body.splitlines():
        if line.startswith("sahaayak_notification"):
            assert "{" not in line


def test_metric_counts_match_the_delivery_rows(client) -> None:
    session_id = make_session()
    add_delivery(session_id, status=DeliveryStatus.DELIVERED)
    add_delivery(session_id, status=DeliveryStatus.FAILED)

    with Session(engine) as db:
        counts = notification_metrics(db)

    assert counts["delivered"] == 1
    assert counts["failed"] == 1
