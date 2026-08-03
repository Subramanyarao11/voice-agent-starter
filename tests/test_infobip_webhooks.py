"""Provider callback handling: auth, replay, ordering, and consent effects.

These are the only unauthenticated routes in the application, and they mutate
delivery and consent state, so the tests lean hard on what a stranger who finds
the URL can and cannot do.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlmodel import Session

from sahaayak_api.integrations.infobip.webhooks import (
    is_stop_keyword,
    parse_delivery_reports,
    parse_inbound_sms,
)
from sahaayak_common import (
    ConsentEvent,
    ContactPoint,
    NotificationDelivery,
    Reminder,
    destination_hash,
    engine,
    new_id,
    reset_cache,
    settings,
)
from sahaayak_contracts import DeliveryStatus, NotificationChannel

SECRET = "webhook-secret-for-tests"
PHONE = "+919876543210"


@pytest.fixture
def webhook_enabled(monkeypatch, database):
    monkeypatch.setattr(settings, "infobip_webhook_auth_secret", SECRET, raising=False)
    reset_cache()
    yield
    reset_cache()


@pytest.fixture
def headers() -> dict[str, str]:
    return {"X-Infobip-Webhook-Secret": SECRET}


@pytest.fixture
def delivery_row(database):
    """A session, contact, reminder, and an accepted delivery awaiting a report."""
    from sahaayak_common import UserSession
    from scripts.seed_demo import DEMO_BENEFITS

    session_id = new_id("ses")
    contact_id = new_id("cp")
    delivery_id = new_id("nd")
    external_id = new_id("ext")
    internal_id = new_id("msg")

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
            ContactPoint(
                id=contact_id,
                session_id=session_id,
                channel="sms",
                destination_ciphertext="ignored-for-this-test",
                destination_hash=destination_hash("sms", PHONE),
                display_suffix="******3210",
                verification_status="verified",
                consent_status="opted_in",
            )
        )
        reminder_id = new_id("rem")
        db.add(
            Reminder(
                id=reminder_id,
                session_id=session_id,
                benefit_id=DEMO_BENEFITS[0]["id"],
                due_at=datetime.now(UTC),
                channel="sms",
                contact_point_id=contact_id,
                template_key="benefit_reminder",
            )
        )
        db.add(
            NotificationDelivery(
                id=delivery_id,
                reminder_id=reminder_id,
                session_id=session_id,
                contact_point_id=contact_id,
                channel="sms",
                provider="infobip_sms",
                template_key="benefit_reminder",
                locale="en",
                internal_message_id=internal_id,
                external_message_id=external_id,
                status=DeliveryStatus.ACCEPTED.value,
                idempotency_key=new_id("snd"),
            )
        )
        db.commit()

    return {
        "session_id": session_id,
        "contact_id": contact_id,
        "delivery_id": delivery_id,
        "reminder_id": reminder_id,
        "external_id": external_id,
        "internal_id": internal_id,
    }


def report(external_id: str, *, group_id: int = 3, group_name: str = "DELIVERED", **extra):
    entry = {
        "messageId": external_id,
        "status": {"groupId": group_id, "groupName": group_name, "id": 5, "name": group_name},
    }
    entry.update(extra)
    return {"results": [entry]}


def read_delivery(delivery_id: str) -> NotificationDelivery:
    with Session(engine) as db:
        return db.get(NotificationDelivery, delivery_id)


def read_contact(contact_id: str) -> ContactPoint:
    with Session(engine) as db:
        return db.get(ContactPoint, contact_id)


# --- Authentication -------------------------------------------------------


def test_a_callback_without_the_secret_is_refused(client, webhook_enabled) -> None:
    response = client.post("/api/webhooks/infobip/sms", json=report("x"))
    assert response.status_code == 401


def test_a_callback_with_the_wrong_secret_is_refused(client, webhook_enabled) -> None:
    response = client.post(
        "/api/webhooks/infobip/sms",
        json=report("x"),
        headers={"X-Infobip-Webhook-Secret": "not-the-secret"},
    )
    assert response.status_code == 401


def test_callbacks_are_closed_when_no_secret_is_configured(client, monkeypatch) -> None:
    """An unauthenticated endpoint that mutates delivery state is worse than none."""
    monkeypatch.setattr(settings, "infobip_webhook_auth_secret", "", raising=False)
    response = client.post(
        "/api/webhooks/infobip/sms",
        json=report("x"),
        headers={"X-Infobip-Webhook-Secret": "anything"},
    )
    assert response.status_code == 503


def test_a_browser_session_token_does_not_authorize_a_webhook(
    client, webhook_enabled, guest_session
) -> None:
    session = guest_session()
    response = client.post(
        "/api/webhooks/infobip/sms", json=report("x"), headers=session["headers"]
    )
    assert response.status_code == 401


def test_the_admin_token_does_not_authorize_a_webhook(client, webhook_enabled) -> None:
    """The TestClient sends X-Admin-Token by default; it must not help here."""
    response = client.post("/api/webhooks/infobip/sms", json=report("x"))
    assert response.status_code == 401


# --- Payload limits -------------------------------------------------------


def test_an_oversized_payload_is_refused(client, webhook_enabled, headers, monkeypatch) -> None:
    monkeypatch.setattr(settings, "infobip_max_webhook_bytes", 128, raising=False)
    response = client.post(
        "/api/webhooks/infobip/sms",
        content=b'{"results": [' + b'{"messageId": "x"},' * 200 + b"]}",
        headers={**headers, "Content-Type": "application/json"},
    )
    assert response.status_code == 413


def test_a_malformed_body_is_refused(client, webhook_enabled, headers) -> None:
    response = client.post(
        "/api/webhooks/infobip/sms",
        content=b"not json at all",
        headers={**headers, "Content-Type": "application/json"},
    )
    assert response.status_code == 400


def test_an_empty_payload_is_accepted_without_doing_anything(
    client, webhook_enabled, headers
) -> None:
    response = client.post("/api/webhooks/infobip/sms", json={}, headers=headers)
    assert response.status_code == 200
    assert response.json()["processed"] == 0


def test_the_response_does_not_reveal_whether_a_message_exists(
    client, webhook_enabled, headers
) -> None:
    response = client.post(
        "/api/webhooks/infobip/sms", json=report("never-sent-this"), headers=headers
    )
    assert response.status_code == 200
    assert response.json()["processed"] == 0


# --- Status application ---------------------------------------------------


def test_a_delivered_report_updates_the_delivery(
    client, webhook_enabled, headers, delivery_row
) -> None:
    response = client.post(
        "/api/webhooks/infobip/sms", json=report(delivery_row["external_id"]), headers=headers
    )
    assert response.status_code == 200

    row = read_delivery(delivery_row["delivery_id"])
    assert row.status == DeliveryStatus.DELIVERED.value
    assert row.delivered_at is not None


def test_a_delivered_report_closes_the_reminder(
    client, webhook_enabled, headers, delivery_row
) -> None:
    client.post(
        "/api/webhooks/infobip/sms", json=report(delivery_row["external_id"]), headers=headers
    )
    with Session(engine) as db:
        reminder = db.get(Reminder, delivery_row["reminder_id"])
    assert reminder.status == "delivered"
    assert reminder.delivered_at is not None


def test_a_report_matches_on_our_own_callback_reference(
    client, webhook_enabled, headers, delivery_row
) -> None:
    """Works even when the response carrying the external ID was lost."""
    payload = report("some-id-we-never-recorded")
    payload["results"][0]["callbackData"] = delivery_row["internal_id"]

    client.post("/api/webhooks/infobip/sms", json=payload, headers=headers)

    assert read_delivery(delivery_row["delivery_id"]).status == DeliveryStatus.DELIVERED.value


def test_a_duplicate_report_is_acknowledged_but_not_reapplied(
    client, webhook_enabled, headers, delivery_row
) -> None:
    payload = report(delivery_row["external_id"])
    first = client.post("/api/webhooks/infobip/sms", json=payload, headers=headers)
    second = client.post("/api/webhooks/infobip/sms", json=payload, headers=headers)

    assert first.json()["processed"] == 1
    assert second.status_code == 200
    assert second.json()["processed"] == 0


def test_a_late_accepted_report_does_not_walk_a_delivered_row_backwards(
    client, webhook_enabled, headers, delivery_row
) -> None:
    """Providers routinely deliver reports out of order."""
    client.post(
        "/api/webhooks/infobip/sms", json=report(delivery_row["external_id"]), headers=headers
    )
    client.post(
        "/api/webhooks/infobip/sms",
        json=report(delivery_row["external_id"], group_id=1, group_name="PENDING"),
        headers=headers,
    )

    assert read_delivery(delivery_row["delivery_id"]).status == DeliveryStatus.DELIVERED.value


def test_a_failed_report_is_recorded_as_failed(
    client, webhook_enabled, headers, delivery_row
) -> None:
    client.post(
        "/api/webhooks/infobip/sms",
        json=report(delivery_row["external_id"], group_id=5, group_name="REJECTED"),
        headers=headers,
    )
    row = read_delivery(delivery_row["delivery_id"])
    assert row.status == DeliveryStatus.FAILED.value
    assert row.failed_at is not None


def test_reported_cost_is_stored_in_minor_units(
    client, webhook_enabled, headers, delivery_row
) -> None:
    payload = report(delivery_row["external_id"])
    payload["results"][0]["price"] = {"pricePerMessage": 0.25, "currency": "INR"}

    client.post("/api/webhooks/infobip/sms", json=payload, headers=headers)

    row = read_delivery(delivery_row["delivery_id"])
    assert row.cost_minor_units == 25
    assert row.cost_currency == "INR"


def test_one_malformed_entry_does_not_discard_the_valid_ones(
    client, webhook_enabled, headers, delivery_row
) -> None:
    payload = {
        "results": [
            {"garbage": True},
            {"messageId": ""},
            report(delivery_row["external_id"])["results"][0],
        ]
    }
    response = client.post("/api/webhooks/infobip/sms", json=payload, headers=headers)
    assert response.json()["processed"] == 1


# --- Consent and destination effects --------------------------------------


def test_a_hard_bounce_marks_the_contact_invalid(
    client, webhook_enabled, headers, delivery_row
) -> None:
    payload = report(delivery_row["external_id"], group_id=5, group_name="REJECTED")
    payload["results"][0]["error"] = {
        "id": 6004,
        "name": "EC_INVALID_DESTINATION_ADDRESS",
        "description": "Invalid destination number",
        "permanent": True,
    }

    client.post("/api/webhooks/infobip/sms", json=payload, headers=headers)

    assert read_contact(delivery_row["contact_id"]).verification_status == "invalid"


def test_a_complaint_revokes_consent(client, webhook_enabled, headers, delivery_row) -> None:
    payload = report(delivery_row["external_id"], group_id=5, group_name="REJECTED")
    payload["results"][0]["error"] = {
        "id": 7001,
        "name": "EC_UNSUBSCRIBED",
        "description": "Recipient unsubscribed",
        "permanent": True,
    }

    client.post("/api/webhooks/infobip/sms", json=payload, headers=headers)

    contact = read_contact(delivery_row["contact_id"])
    assert contact.consent_status == "opted_out"
    with Session(engine) as db:
        events = db.query(ConsentEvent).filter(
            ConsentEvent.contact_point_id == delivery_row["contact_id"]
        ).all()
    assert any(event.status == "opted_out" for event in events)


# --- Inbound STOP ---------------------------------------------------------


@pytest.mark.parametrize(
    "text", ["STOP", "stop", " Stop ", "UNSUBSCRIBE", "opt-out", "band", "बंद", "ನಿಲ್ಲಿಸಿ"]
)
def test_stop_keywords_are_recognised(text: str) -> None:
    assert is_stop_keyword(text)


@pytest.mark.parametrize(
    "text",
    [
        "",
        "I need a scholarship",
        "please tell me about the bus pass scheme",
        "my income is two lakh",
    ],
)
def test_ordinary_replies_are_not_treated_as_opt_out(text: str) -> None:
    """Substring matching here would silently unsubscribe someone asking for help."""
    assert not is_stop_keyword(text)


def test_an_inbound_stop_revokes_consent(
    client, webhook_enabled, headers, delivery_row
) -> None:
    response = client.post(
        "/api/webhooks/infobip/sms/inbound",
        json={"results": [{"from": PHONE, "message": {"text": "STOP"}}]},
        headers=headers,
    )

    assert response.status_code == 200
    # Every contact registered against that number is silenced, not just one:
    # a STOP is an instruction about the handset, not about one session.
    assert response.json()["processed"] >= 1
    assert read_contact(delivery_row["contact_id"]).consent_status == "opted_out"


def test_an_ordinary_inbound_message_changes_nothing(
    client, webhook_enabled, headers, delivery_row
) -> None:
    response = client.post(
        "/api/webhooks/infobip/sms/inbound",
        json={"results": [{"from": PHONE, "message": {"text": "I need help"}}]},
        headers=headers,
    )
    assert response.json()["processed"] == 0
    assert read_contact(delivery_row["contact_id"]).consent_status == "opted_in"


def test_inbound_sms_requires_the_webhook_secret(client, webhook_enabled) -> None:
    response = client.post(
        "/api/webhooks/infobip/sms/inbound",
        json={"results": [{"from": PHONE, "message": {"text": "STOP"}}]},
    )
    assert response.status_code == 401


# --- Parsing --------------------------------------------------------------


def test_email_status_names_map_to_delivery_states() -> None:
    updates = parse_delivery_reports(
        {"results": [{"messageId": "m", "status": {"name": "BOUNCED", "groupName": "BOUNCED"}}]},
        channel=NotificationChannel.EMAIL,
    )
    assert updates[0].status is DeliveryStatus.FAILED


def test_an_unsubscribe_maps_to_suppressed_not_failed() -> None:
    updates = parse_delivery_reports(
        {
            "results": [
                {
                    "messageId": "m",
                    "status": {"name": "UNSUBSCRIBED", "groupName": "UNSUBSCRIBED"},
                }
            ]
        },
        channel=NotificationChannel.EMAIL,
    )
    assert updates[0].status is DeliveryStatus.SUPPRESSED
    assert updates[0].consent_revoked


def test_inbound_parsing_tolerates_the_shapes_a_callback_arrives_in() -> None:
    assert parse_inbound_sms({"results": [{"from": "+91", "message": {"text": "STOP"}}]}) == [
        ("+91", "STOP")
    ]
    assert parse_inbound_sms({"results": [{"from": "+91", "text": "STOP"}]}) == [("+91", "STOP")]
    assert parse_inbound_sms({"results": [{"garbage": 1}]}) == []
    assert parse_inbound_sms(None) == []
