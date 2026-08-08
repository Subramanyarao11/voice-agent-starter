"""Contact point registration, verification, consent, and reminder gating.

Driven through the HTTP surface, because the guarantees being defended are
guarantees about the API: that a destination never comes back out, that typing
a number is not consent, and that an in-app reminder never becomes unavailable
because a provider is down.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from cryptography.fernet import Fernet
from sqlmodel import Session, select

from sahaayak_api.notifications import register_provider, reset_providers
from sahaayak_api.notifications.base import OutboundNotification
from sahaayak_common import (
    ConsentEvent,
    ContactPoint,
    FeatureFlag,
    NotificationTemplate,
    ProviderPolicy,
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

EMAIL = "priya@example.test"


class CapturingProvider:
    """Stands in for Infobip and remembers the code it was asked to send."""

    name = "test_email"
    channel = NotificationChannel.EMAIL

    def __init__(self, *, accept: bool = True) -> None:
        self.sent: list[OutboundNotification] = []
        self.accept = accept

    def available(self) -> bool:
        return True

    async def send(self, notification: OutboundNotification) -> ProviderSendResult:
        self.sent.append(notification)
        if not self.accept:
            return ProviderSendResult.failure(
                provider=self.name,
                channel=self.channel,
                error_class=ProviderErrorClass.PROVIDER_ERROR,
                detail="upstream down",
            )
        return ProviderSendResult(
            accepted=True,
            provider=self.name,
            channel=self.channel,
            status=DeliveryStatus.ACCEPTED,
            external_message_id=new_id("ext"),
        )

    def last_code(self) -> str:
        """Recover the code from the rendered text, as a recipient would."""
        text = self.sent[-1].message.text
        return "".join(char for char in text if char.isdigit())[:6]


@pytest.fixture
def provider():
    prov = CapturingProvider()
    register_provider(NotificationChannel.EMAIL, prov)
    yield prov
    reset_providers()


@pytest.fixture
def email_enabled(monkeypatch, database):
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
    monkeypatch.setattr(settings, "infobip_email_enabled", True, raising=False)
    monkeypatch.setattr(settings, "infobip_email_sender", "no-reply@sahaayak.test", raising=False)

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
                provider="email",
                scope="*",
                enabled=True,
                primary_provider="infobip_email",
                fallback_provider="in_app",
            )
        )
        db.commit()
    yield
    reset_encryption_cache()
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
        for row in db.query(NotificationTemplate).all():
            db.delete(row)
        db.commit()


def add_contact(client, session, *, consent: bool = True, destination: str = EMAIL):
    return client.post(
        f"/api/sessions/{session['session_id']}/contact-points",
        json={
            "channel": "email",
            "destination": destination,
            "locale": "en",
            "consent": consent,
        },
        headers=session["headers"],
    )


def verify(client, session, contact_id: str, code: str):
    return client.post(
        f"/api/sessions/{session['session_id']}/contact-points/{contact_id}/verify",
        json={"code": code},
        headers=session["headers"],
    )


def save_benefit(client, session) -> str:
    from scripts.seed_demo import DEMO_BENEFITS

    benefit_id = DEMO_BENEFITS[0]["id"]
    response = client.post(
        f"/api/sessions/{session['session_id']}/saved-benefits",
        json={"benefit_id": benefit_id},
        headers=session["headers"],
    )
    assert response.status_code in (200, 201)
    return benefit_id


def make_reminder(client, session, benefit_id: str, channel: str):
    return client.post(
        f"/api/sessions/{session['session_id']}/reminders",
        json={
            "benefit_id": benefit_id,
            "due_at": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
            "channel": channel,
        },
        headers=session["headers"],
    )


# --- Registration ---------------------------------------------------------


def test_adding_a_contact_sends_a_challenge_and_returns_only_a_mask(
    client, guest_session, email_enabled, provider
) -> None:
    session = guest_session()
    response = add_contact(client, session)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["verification_status"] == "pending"
    assert body["display_suffix"] == "p***@example.test"
    # The destination itself never appears anywhere in the response.
    assert EMAIL not in response.text
    assert len(provider.sent) == 1


def test_the_verification_code_is_not_returned_to_the_caller(
    client, guest_session, email_enabled, provider
) -> None:
    session = guest_session()
    response = add_contact(client, session)
    assert provider.last_code() not in response.text


def test_a_malformed_destination_is_refused(
    client, guest_session, email_enabled, provider
) -> None:
    session = guest_session()
    response = add_contact(client, session, destination="not-an-address")
    assert response.status_code == 400
    assert not provider.sent


def test_typing_a_destination_without_ticking_consent_is_refused(
    client, guest_session, email_enabled, provider
) -> None:
    """Entering an address is not agreeing to be messaged at it."""
    session = guest_session()
    response = add_contact(client, session, consent=False)
    assert response.status_code == 400
    assert not provider.sent


def test_a_channel_with_no_provider_reports_unavailable_rather_than_pretending(
    client, guest_session, email_enabled, monkeypatch
) -> None:
    """A challenge must never fall back to in-app: a code nobody reads verifies nothing."""
    reset_providers()
    # Switch the channel off rather than merely unregistering the fake, so the
    # route takes the same path a deployment without email credentials would.
    monkeypatch.setattr(settings, "infobip_email_enabled", False, raising=False)
    session = guest_session()
    response = add_contact(client, session)
    assert response.status_code == 503


def test_a_failed_challenge_leaves_no_stranded_pending_contact(
    client, guest_session, email_enabled
) -> None:
    register_provider(NotificationChannel.EMAIL, CapturingProvider(accept=False))
    session = guest_session()
    response = add_contact(client, session)
    assert response.status_code == 502

    listing = client.get(
        f"/api/sessions/{session['session_id']}/contact-points", headers=session["headers"]
    )
    assert listing.json() == []
    reset_providers()


def test_adding_a_contact_records_an_append_only_consent_event(
    client, guest_session, email_enabled, provider
) -> None:
    session = guest_session()
    contact_id = add_contact(client, session).json()["id"]

    with Session(engine) as db:
        events = db.query(ConsentEvent).filter(
            ConsentEvent.contact_point_id == contact_id
        ).all()
    assert [event.status for event in events] == ["opted_in"]
    assert events[0].consent_text_version


# --- Verification ---------------------------------------------------------


def test_the_right_code_verifies_the_contact(
    client, guest_session, email_enabled, provider
) -> None:
    session = guest_session()
    contact_id = add_contact(client, session).json()["id"]

    response = verify(client, session, contact_id, provider.last_code())

    assert response.status_code == 200
    assert response.json()["verification_status"] == "verified"


def test_the_wrong_code_does_not_verify(
    client, guest_session, email_enabled, provider
) -> None:
    session = guest_session()
    contact_id = add_contact(client, session).json()["id"]

    assert verify(client, session, contact_id, "000000").status_code == 400


def test_the_code_is_discarded_once_used(
    client, guest_session, email_enabled, provider
) -> None:
    session = guest_session()
    contact_id = add_contact(client, session).json()["id"]
    code = provider.last_code()
    verify(client, session, contact_id, code)

    with Session(engine) as db:
        row = db.get(ContactPoint, contact_id)
        assert row.verification_code_hash is None


def test_the_plaintext_code_is_never_stored(
    client, guest_session, email_enabled, provider
) -> None:
    session = guest_session()
    contact_id = add_contact(client, session).json()["id"]
    code = provider.last_code()

    with Session(engine) as db:
        row = db.get(ContactPoint, contact_id)
        assert row.verification_code_hash != code
        assert code not in (row.verification_code_hash or "")


def test_repeated_wrong_codes_are_cut_off(
    client, guest_session, email_enabled, provider
) -> None:
    session = guest_session()
    contact_id = add_contact(client, session).json()["id"]

    statuses = [
        verify(client, session, contact_id, "111111").status_code
        for _ in range(settings.contact_verification_max_attempts + 1)
    ]
    assert 429 in statuses


def test_an_expired_code_is_refused(
    client, guest_session, email_enabled, provider
) -> None:
    session = guest_session()
    contact_id = add_contact(client, session).json()["id"]
    code = provider.last_code()

    with Session(engine) as db:
        row = db.get(ContactPoint, contact_id)
        row.verification_expires_at = datetime.now(UTC) - timedelta(minutes=1)
        db.add(row)
        db.commit()

    assert verify(client, session, contact_id, code).status_code == 410


def test_a_contact_belonging_to_another_session_is_not_found(
    client, guest_session, email_enabled, provider
) -> None:
    owner = guest_session()
    contact_id = add_contact(client, owner).json()["id"]

    intruder = guest_session()
    response = client.post(
        f"/api/sessions/{intruder['session_id']}/contact-points/{contact_id}/verify",
        json={"code": provider.last_code()},
        headers=intruder["headers"],
    )
    assert response.status_code == 404


def test_a_session_cannot_read_another_sessions_contacts(
    client, guest_session, email_enabled, provider
) -> None:
    owner = guest_session()
    add_contact(client, owner)
    intruder = guest_session()

    response = client.get(
        f"/api/sessions/{owner['session_id']}/contact-points", headers=intruder["headers"]
    )
    assert response.status_code == 403


# --- Revocation -----------------------------------------------------------


def test_revoking_keeps_the_row_and_appends_an_opt_out(
    client, guest_session, email_enabled, provider
) -> None:
    session = guest_session()
    contact_id = add_contact(client, session).json()["id"]
    verify(client, session, contact_id, provider.last_code())

    response = client.delete(
        f"/api/sessions/{session['session_id']}/contact-points/{contact_id}",
        headers=session["headers"],
    )
    assert response.status_code == 204

    with Session(engine) as db:
        row = db.get(ContactPoint, contact_id)
        assert row is not None, "the evidence of an opt-out must survive"
        assert row.consent_status == "opted_out"
        events = db.query(ConsentEvent).filter(
            ConsentEvent.contact_point_id == contact_id
        ).all()
    assert [event.status for event in events] == ["opted_in", "opted_out"]


def test_a_revoked_contact_cannot_be_used_for_a_reminder(
    client, guest_session, seeded, email_enabled, provider
) -> None:
    session = guest_session()
    contact_id = add_contact(client, session).json()["id"]
    verify(client, session, contact_id, provider.last_code())
    client.delete(
        f"/api/sessions/{session['session_id']}/contact-points/{contact_id}",
        headers=session["headers"],
    )

    benefit_id = save_benefit(client, session)
    response = make_reminder(client, session, benefit_id, "email")
    assert response.status_code == 409


# --- Channel availability -------------------------------------------------


def test_channel_listing_always_offers_in_app(client, guest_session) -> None:
    session = guest_session()
    response = client.get(
        f"/api/sessions/{session['session_id']}/notification-channels",
        headers=session["headers"],
    )
    channels = {item["channel"]: item for item in response.json()}
    assert channels["in_app"]["available"]


def test_every_unavailable_channel_explains_itself(client, guest_session) -> None:
    session = guest_session()
    response = client.get(
        f"/api/sessions/{session['session_id']}/notification-channels",
        headers=session["headers"],
    )
    for item in response.json():
        if not item["available"]:
            assert item["reason"].strip(), item["channel"]
            assert item["gate"].strip()


def test_channel_listing_shows_only_a_masked_destination(
    client, guest_session, email_enabled, provider
) -> None:
    session = guest_session()
    add_contact(client, session)
    response = client.get(
        f"/api/sessions/{session['session_id']}/notification-channels",
        headers=session["headers"],
    )
    assert EMAIL not in response.text


# --- Reminder gating ------------------------------------------------------


def test_an_in_app_reminder_still_works_with_no_contacts_at_all(
    client, guest_session, seeded
) -> None:
    session = guest_session()
    benefit_id = save_benefit(client, session)
    response = make_reminder(client, session, benefit_id, "in_app")
    assert response.status_code == 201
    assert response.json()["channel"] == "in_app"


def test_an_external_reminder_without_a_contact_is_refused_with_a_reason(
    client, guest_session, seeded
) -> None:
    session = guest_session()
    benefit_id = save_benefit(client, session)
    response = make_reminder(client, session, benefit_id, "email")
    assert response.status_code == 409
    assert response.json()["detail"].strip()


def test_an_unverified_contact_does_not_unlock_the_channel(
    client, guest_session, seeded, email_enabled, provider
) -> None:
    session = guest_session()
    add_contact(client, session)
    benefit_id = save_benefit(client, session)

    response = make_reminder(client, session, benefit_id, "email")

    assert response.status_code == 409
    assert "verify" in response.json()["detail"].lower()


def test_a_verified_consenting_contact_unlocks_the_channel(
    client, guest_session, seeded, email_enabled, provider
) -> None:
    session = guest_session()
    contact_id = add_contact(client, session).json()["id"]
    verify(client, session, contact_id, provider.last_code())
    benefit_id = save_benefit(client, session)

    response = make_reminder(client, session, benefit_id, "email")

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["channel"] == "email"
    assert body["contact_display_suffix"] == "p***@example.test"
    assert EMAIL not in response.text


def test_an_external_reminder_pins_the_consent_in_force(
    client, guest_session, seeded, email_enabled, provider
) -> None:
    session = guest_session()
    contact_id = add_contact(client, session).json()["id"]
    verify(client, session, contact_id, provider.last_code())
    benefit_id = save_benefit(client, session)
    reminder_id = make_reminder(client, session, benefit_id, "email").json()["id"]

    from sahaayak_common import Reminder

    with Session(engine) as db:
        row = db.get(Reminder, reminder_id)
        assert row.consent_snapshot_id
        assert row.template_key == "benefit_reminder"


def test_a_disabled_policy_blocks_a_verified_contact(
    client, guest_session, seeded, email_enabled, provider
) -> None:
    session = guest_session()
    contact_id = add_contact(client, session).json()["id"]
    verify(client, session, contact_id, provider.last_code())
    benefit_id = save_benefit(client, session)

    with Session(engine) as db:
        row = db.query(ProviderPolicy).filter(ProviderPolicy.provider == "email").first()
        row.enabled = False
        db.add(row)
        db.commit()

    response = make_reminder(client, session, benefit_id, "email")
    assert response.status_code == 409
    assert "in-app" in response.json()["detail"].lower()


def test_an_unknown_channel_is_rejected_by_validation(
    client, guest_session, seeded
) -> None:
    session = guest_session()
    benefit_id = save_benefit(client, session)
    response = make_reminder(client, session, benefit_id, "carrier_pigeon")
    assert response.status_code == 422


def test_contact_routes_require_a_session_token(client) -> None:
    assert client.get("/api/sessions/ses_x/contact-points").status_code == 401
