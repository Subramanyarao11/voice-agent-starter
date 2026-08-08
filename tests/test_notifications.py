"""Templates, channel gating, and delivery recording.

The gate tests are the important ones. They pin down that an external channel
stays shut unless a verified contact, live consent, an enabled policy, a
configured provider, an approved template, and budget headroom are all present
— and that in-app never depends on any of them.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from cryptography.fernet import Fernet
from sqlmodel import Session

from sahaayak_api.notifications import (
    GATE_OK,
    InAppProvider,
    TemplateNotFound,
    available_channels,
    check_channel,
    create_delivery,
    dispatch,
    dispatcher,
    get_provider,
    idempotency_key,
    record_result,
    register_provider,
    render,
    reset_providers,
    resolve,
    suppress,
)
from sahaayak_api.notifications.templates import PREAPPROVAL_REQUIRED
from sahaayak_common import (
    ConsentEvent,
    ContactPoint,
    NotificationTemplate,
    ProviderPolicy,
    UserSession,
    encrypt_destination,
    engine,
    evaluate_budget,
    mask_destination,
    new_id,
    reset_encryption_cache,
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


@pytest.fixture
def db(database):
    with Session(engine) as session:
        yield session
        session.rollback()


@pytest.fixture
def encryption_key(monkeypatch):
    monkeypatch.setattr(
        settings,
        "infobip_contact_encryption_key",
        Fernet.generate_key().decode(),
        raising=False,
    )
    reset_encryption_cache()
    yield
    reset_encryption_cache()


@pytest.fixture(autouse=True)
def clean_providers():
    reset_providers()
    yield
    reset_providers()


@pytest.fixture
def session_row(db: Session) -> UserSession:
    row = UserSession(
        id=new_id("ses"),
        phone_or_session_id=new_id("caller"),
        state_code="KA",
        language_code="en",
    )
    db.add(row)
    db.commit()
    return row


def make_contact(
    db: Session,
    session_row: UserSession,
    *,
    channel: NotificationChannel = NotificationChannel.SMS,
    verification: str = VerificationStatusValue.VERIFIED.value,
    consent: str = ConsentStatus.OPTED_IN.value,
    destination: str = "+919876543210",
) -> ContactPoint:
    contact = ContactPoint(
        id=new_id("cp"),
        session_id=session_row.id,
        channel=channel.value,
        destination_ciphertext=encrypt_destination(destination),
        destination_hash=new_id("h"),
        display_suffix=mask_destination(channel.value, destination),
        verification_status=verification,
        consent_status=consent,
        verified_at=datetime.now(UTC),
    )
    db.add(contact)
    db.commit()
    return contact


@pytest.fixture
def enabled_sms(db: Session, monkeypatch):
    """Policy on, provider configured, template approved."""
    _set_policy(db, "sms", enabled=True)
    monkeypatch.setattr(settings, "infobip_enabled", True, raising=False)
    monkeypatch.setattr(settings, "infobip_base_url", "https://x.api.infobip.com", raising=False)
    monkeypatch.setattr(settings, "infobip_api_key", "k", raising=False)
    monkeypatch.setattr(settings, "infobip_sms_enabled", True, raising=False)
    monkeypatch.setattr(settings, "infobip_sms_sender", "SAHAYK", raising=False)
    _approve_template(db, "benefit_reminder", NotificationChannel.SMS)
    yield
    _clear_policies(db)
    _clear_templates(db)


def _set_policy(db: Session, provider: str, *, enabled: bool, circuit: str = "closed") -> None:
    row = ProviderPolicy(
        id=new_id("pp"),
        provider=provider,
        scope="*",
        enabled=enabled,
        primary_provider=f"infobip_{provider}",
        fallback_provider="in_app",
        circuit_state=circuit,
    )
    db.merge(row)
    db.commit()


def _clear_policies(db: Session) -> None:
    for row in db.query(ProviderPolicy).all():
        db.delete(row)
    db.commit()


def _approve_template(db: Session, key: str, channel: NotificationChannel) -> None:
    db.add(
        NotificationTemplate(
            id=new_id("nt"),
            template_key=key,
            channel=channel.value,
            locale="en",
            provider_template_name=f"{key}_utility_en",
            subject="Reminder: {benefit_name}",
            body="You may qualify for {benefit_name}. {source_url}",
            approval_status="approved",
            active=True,
        )
    )
    db.commit()


def _clear_templates(db: Session) -> None:
    for row in db.query(NotificationTemplate).all():
        db.delete(row)
    db.commit()


# --- Templates ------------------------------------------------------------


def test_builtin_content_exists_for_every_supported_locale() -> None:
    for locale in ("en", "hi", "kn"):
        template = resolve(
            None, template_key="benefit_reminder", channel=NotificationChannel.EMAIL, locale=locale
        )
        assert template.locale == locale
        assert template.body.strip()


def test_an_unknown_locale_falls_back_to_english_rather_than_sending_nothing() -> None:
    template = resolve(
        None, template_key="benefit_reminder", channel=NotificationChannel.EMAIL, locale="ta"
    )
    assert template.locale == "en"
    assert template.body.strip()


def test_an_unknown_template_key_is_an_error_not_an_empty_message() -> None:
    with pytest.raises(TemplateNotFound):
        resolve(None, template_key="nope", channel=NotificationChannel.EMAIL, locale="en")


def test_a_database_template_overrides_builtin_content(db: Session) -> None:
    _approve_template(db, "benefit_reminder", NotificationChannel.EMAIL)
    template = resolve(
        db, template_key="benefit_reminder", channel=NotificationChannel.EMAIL, locale="en"
    )
    assert template.approval_status == "approved"
    assert template.provider_template_name == "benefit_reminder_utility_en"
    _clear_templates(db)


def test_channels_needing_preapproval_are_not_ready_without_a_provider_template() -> None:
    for channel in PREAPPROVAL_REQUIRED:
        template = resolve(
            None, template_key="benefit_reminder", channel=channel, locale="en"
        )
        assert not template.provider_ready


def test_email_does_not_require_a_preregistered_provider_template() -> None:
    template = resolve(
        None, template_key="benefit_reminder", channel=NotificationChannel.EMAIL, locale="en"
    )
    assert template.provider_ready


def test_rendering_substitutes_known_variables() -> None:
    template = resolve(
        None, template_key="benefit_reminder", channel=NotificationChannel.EMAIL, locale="en"
    )
    message = render(
        template, {"benefit_name": "Post Matric Scholarship", "source_url": "https://x.test"}
    )
    assert "Post Matric Scholarship" in message.text
    assert "https://x.test" in message.text


def test_an_unknown_placeholder_stays_visible_rather_than_vanishing() -> None:
    template = resolve(
        None, template_key="benefit_reminder", channel=NotificationChannel.EMAIL, locale="en"
    )
    message = render(template, {"benefit_name": "X"})
    assert "{source_url}" in message.text


def test_rendering_does_not_evaluate_attribute_access_in_variables() -> None:
    """A template is operator-editable; it must not reach into objects."""
    template = resolve(
        None, template_key="benefit_reminder", channel=NotificationChannel.EMAIL, locale="en"
    )
    message = render(template, {"benefit_name": "{__class__}", "source_url": "u"})
    assert "{__class__}" in message.text


def test_html_variables_are_escaped() -> None:
    template = resolve(
        None, template_key="benefit_reminder", channel=NotificationChannel.EMAIL, locale="en"
    )
    message = render(
        template, {"benefit_name": "<script>alert(1)</script>", "source_url": "u"}
    )
    assert "<script>" not in message.html
    assert "&lt;script&gt;" in message.html


def test_no_builtin_template_promises_approval() -> None:
    """Eligibility is decided by the matcher, never asserted by a reminder."""
    forbidden = ("you are eligible", "approved", "guaranteed", "you will receive")
    for key in ("benefit_reminder", "application_deadline", "benefit_source_link"):
        for locale in ("en",):
            template = resolve(
                None, template_key=key, channel=NotificationChannel.EMAIL, locale=locale
            )
            lowered = template.body.lower()
            assert not any(phrase in lowered for phrase in forbidden)


# --- Channel gates --------------------------------------------------------


def test_in_app_is_always_available(db: Session, session_row: UserSession) -> None:
    result = check_channel(db, channel=NotificationChannel.IN_APP, session_id=session_row.id)
    assert result.available
    assert result.gate == GATE_OK


def test_an_external_channel_without_a_contact_is_blocked(
    db: Session, session_row: UserSession
) -> None:
    result = check_channel(db, channel=NotificationChannel.SMS, session_id=session_row.id)
    assert not result.available
    assert result.gate == dispatcher.GATE_CONTACT_MISSING
    assert result.reason


def test_an_unverified_contact_is_blocked(
    db: Session, session_row: UserSession, encryption_key
) -> None:
    contact = make_contact(db, session_row, verification="pending")
    result = check_channel(
        db, channel=NotificationChannel.SMS, contact=contact, session_id=session_row.id
    )
    assert result.gate == dispatcher.GATE_CONTACT_UNVERIFIED


def test_a_verified_contact_without_consent_is_blocked(
    db: Session, session_row: UserSession, encryption_key
) -> None:
    """Typing a number is not agreeing to be messaged at it."""
    contact = make_contact(db, session_row, consent=ConsentStatus.UNKNOWN.value)
    result = check_channel(
        db, channel=NotificationChannel.SMS, contact=contact, session_id=session_row.id
    )
    assert result.gate == dispatcher.GATE_CONSENT_MISSING


def test_an_opted_out_contact_is_blocked(
    db: Session, session_row: UserSession, encryption_key
) -> None:
    contact = make_contact(db, session_row, consent=ConsentStatus.OPTED_OUT.value)
    result = check_channel(
        db, channel=NotificationChannel.SMS, contact=contact, session_id=session_row.id
    )
    assert result.gate == dispatcher.GATE_CONSENT_WITHDRAWN


def test_consent_for_another_purpose_does_not_unlock_reminders(
    db: Session, session_row: UserSession, encryption_key
) -> None:
    contact = make_contact(db, session_row)
    contact.consent_purpose = "support"
    db.add(contact)
    db.commit()

    result = check_channel(
        db, channel=NotificationChannel.SMS, contact=contact, session_id=session_row.id
    )
    assert result.gate == dispatcher.GATE_CONSENT_PURPOSE


def test_a_contact_from_another_session_is_refused(
    db: Session, session_row: UserSession, encryption_key
) -> None:
    contact = make_contact(db, session_row)
    result = check_channel(
        db, channel=NotificationChannel.SMS, contact=contact, session_id="ses_someone_else"
    )
    assert result.gate == dispatcher.GATE_SESSION_MISMATCH


def test_consent_is_checked_before_provider_configuration(
    db: Session, session_row: UserSession, encryption_key
) -> None:
    """An opt-out must not be reported as an outage that could later clear."""
    contact = make_contact(db, session_row, consent=ConsentStatus.OPTED_OUT.value)
    result = check_channel(
        db, channel=NotificationChannel.SMS, contact=contact, session_id=session_row.id
    )
    assert result.gate == dispatcher.GATE_CONSENT_WITHDRAWN


def test_a_disabled_policy_blocks_a_fully_verified_contact(
    db: Session, session_row: UserSession, encryption_key
) -> None:
    contact = make_contact(db, session_row)
    result = check_channel(
        db, channel=NotificationChannel.SMS, contact=contact, session_id=session_row.id
    )
    assert result.gate == dispatcher.GATE_POLICY_DISABLED
    assert "in-app" in result.reason.lower()


def test_messaging_channels_default_to_disabled() -> None:
    """A paid channel that reaches a phone is off until switched on."""
    for channel in (NotificationChannel.SMS, NotificationChannel.EMAIL,
                    NotificationChannel.WHATSAPP):
        assert not dispatcher.channel_policy(channel)["enabled"]


def test_an_open_circuit_blocks_the_channel(
    db: Session, session_row: UserSession, encryption_key
) -> None:
    _set_policy(db, "sms", enabled=True, circuit="open")
    contact = make_contact(db, session_row)
    result = check_channel(
        db, channel=NotificationChannel.SMS, contact=contact, session_id=session_row.id
    )
    assert result.gate == dispatcher.GATE_CIRCUIT_OPEN
    _clear_policies(db)


def test_an_enabled_policy_without_credentials_is_still_blocked(
    db: Session, session_row: UserSession, encryption_key
) -> None:
    _set_policy(db, "sms", enabled=True)
    contact = make_contact(db, session_row)
    result = check_channel(
        db, channel=NotificationChannel.SMS, contact=contact, session_id=session_row.id
    )
    assert result.gate == dispatcher.GATE_PROVIDER_NOT_CONFIGURED
    _clear_policies(db)


def test_a_fully_configured_channel_is_available(
    db: Session, session_row: UserSession, encryption_key, enabled_sms
) -> None:
    contact = make_contact(db, session_row)
    result = check_channel(
        db,
        channel=NotificationChannel.SMS,
        contact=contact,
        session_id=session_row.id,
        template_key="benefit_reminder",
    )
    assert result.available, result.gate


def test_an_unapproved_template_blocks_a_preapproval_channel(
    db: Session, session_row: UserSession, encryption_key, enabled_sms
) -> None:
    contact = make_contact(db, session_row)
    result = check_channel(
        db,
        channel=NotificationChannel.SMS,
        contact=contact,
        session_id=session_row.id,
        template_key="human_help_followup",
    )
    assert result.gate == dispatcher.GATE_TEMPLATE_NOT_APPROVED


def test_an_exhausted_budget_blocks_the_channel(
    db: Session, session_row: UserSession, encryption_key, enabled_sms, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "infobip_daily_budget_minor_units", 0, raising=False)
    contact = make_contact(db, session_row)
    result = check_channel(
        db,
        channel=NotificationChannel.SMS,
        contact=contact,
        session_id=session_row.id,
        template_key="benefit_reminder",
    )
    assert result.gate == dispatcher.GATE_BUDGET_EXHAUSTED


def test_availability_listing_always_includes_a_usable_in_app_option(
    db: Session, session_row: UserSession
) -> None:
    results = available_channels(db, contacts={}, session_id=session_row.id)
    in_app = next(r for r in results if r.channel is NotificationChannel.IN_APP)
    assert in_app.available
    assert all(not r.available for r in results if r.channel is not NotificationChannel.IN_APP)


def test_every_blocked_channel_explains_itself(db: Session, session_row: UserSession) -> None:
    """A caller is owed a reason, not a greyed-out button."""
    for result in available_channels(db, contacts={}, session_id=session_row.id):
        if not result.available:
            assert result.reason.strip()


# --- Budget ---------------------------------------------------------------


def test_no_configured_budget_permits_sending(db: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "infobip_daily_budget_minor_units", None, raising=False)
    monkeypatch.setattr(settings, "infobip_monthly_budget_minor_units", None, raising=False)
    assert evaluate_budget(db).allowed


def test_budget_uses_minor_units_and_an_explicit_currency(db: Session) -> None:
    posture = evaluate_budget(db)
    assert posture.currency == settings.infobip_cost_currency
    assert isinstance(posture.daily_spent_minor_units, int)


# --- Delivery records -----------------------------------------------------


def test_a_delivery_row_is_created_before_anything_is_sent(
    db: Session, session_row: UserSession
) -> None:
    delivery = create_delivery(
        db,
        channel=NotificationChannel.IN_APP,
        session_id=session_row.id,
        template_key="benefit_reminder",
        locale="en",
    )
    assert delivery.status == DeliveryStatus.QUEUED.value
    assert delivery.internal_message_id
    assert delivery.idempotency_key


def test_the_idempotency_key_is_stable_for_the_same_logical_send() -> None:
    first = idempotency_key("ses_1", "sms", "benefit_reminder", "rem_1")
    second = idempotency_key("ses_1", "sms", "benefit_reminder", "rem_1")
    assert first == second


def test_the_idempotency_key_differs_across_reminders() -> None:
    assert idempotency_key("ses_1", "sms", "benefit_reminder", "rem_1") != idempotency_key(
        "ses_1", "sms", "benefit_reminder", "rem_2"
    )


def test_a_delivery_row_never_holds_a_message_body(
    db: Session, session_row: UserSession
) -> None:
    delivery = create_delivery(
        db,
        channel=NotificationChannel.IN_APP,
        session_id=session_row.id,
        template_key="benefit_reminder",
        locale="en",
    )
    assert not hasattr(delivery, "body")
    assert delivery.template_key == "benefit_reminder"


def test_recording_an_accepted_result_does_not_claim_delivery(
    db: Session, session_row: UserSession
) -> None:
    delivery = create_delivery(
        db,
        channel=NotificationChannel.SMS,
        session_id=session_row.id,
        template_key="benefit_reminder",
        locale="en",
    )
    record_result(
        db,
        delivery,
        ProviderSendResult(
            accepted=True,
            provider="infobip_sms",
            channel=NotificationChannel.SMS,
            status=DeliveryStatus.ACCEPTED,
            external_message_id="ext-1",
        ),
    )
    assert delivery.status == DeliveryStatus.ACCEPTED.value
    assert delivery.sent_at is not None
    assert delivery.delivered_at is None


def test_suppression_is_recorded_separately_from_failure(
    db: Session, session_row: UserSession
) -> None:
    delivery = create_delivery(
        db,
        channel=NotificationChannel.SMS,
        session_id=session_row.id,
        template_key="benefit_reminder",
        locale="en",
    )
    suppress(db, delivery, gate=dispatcher.GATE_CONSENT_WITHDRAWN)
    assert delivery.status == DeliveryStatus.SUPPRESSED.value
    assert delivery.provider_error_class == ProviderErrorClass.POLICY_DISABLED.value


async def test_in_app_dispatch_completes_without_a_provider(
    db: Session, session_row: UserSession
) -> None:
    delivery = create_delivery(
        db,
        channel=NotificationChannel.IN_APP,
        session_id=session_row.id,
        template_key="benefit_reminder",
        locale="en",
    )
    template = resolve(
        db, template_key="benefit_reminder", channel=NotificationChannel.IN_APP, locale="en"
    )
    result = await dispatch(
        db,
        provider=InAppProvider(),
        contact=None,
        delivery=delivery,
        template=template,
        variables={"benefit_name": "X", "source_url": "u"},
    )
    assert result.accepted
    assert delivery.status == DeliveryStatus.DELIVERED.value
    assert delivery.cost_minor_units == 0


async def test_dispatch_fails_cleanly_when_the_destination_cannot_be_decrypted(
    db: Session, session_row: UserSession, encryption_key, monkeypatch
) -> None:
    contact = make_contact(db, session_row)
    monkeypatch.setattr(
        settings,
        "infobip_contact_encryption_key",
        Fernet.generate_key().decode(),
        raising=False,
    )
    reset_encryption_cache()

    delivery = create_delivery(
        db,
        channel=NotificationChannel.SMS,
        session_id=session_row.id,
        template_key="benefit_reminder",
        locale="en",
        contact_point_id=contact.id,
    )
    template = resolve(
        db, template_key="benefit_reminder", channel=NotificationChannel.SMS, locale="en"
    )
    result = await dispatch(
        db,
        provider=InAppProvider(),
        contact=contact,
        delivery=delivery,
        template=template,
    )
    assert not result.accepted
    assert result.error_class is ProviderErrorClass.NOT_CONFIGURED


# --- Registry -------------------------------------------------------------


def test_an_unconfigured_external_channel_falls_back_to_in_app() -> None:
    provider = get_provider(NotificationChannel.SMS)
    assert isinstance(provider, InAppProvider)


def test_fallback_can_be_refused_when_the_caller_wants_to_know() -> None:
    assert get_provider(NotificationChannel.SMS, allow_fallback=False) is None


def test_a_registered_provider_wins() -> None:
    class Fake(InAppProvider):
        name = "fake"

    register_provider(NotificationChannel.SMS, Fake())
    assert get_provider(NotificationChannel.SMS).name == "fake"


def test_consent_history_rows_are_append_only_by_construction(
    db: Session, session_row: UserSession
) -> None:
    """Two opposing decisions coexist; the later one does not erase the first."""
    for status in (ConsentStatus.OPTED_IN, ConsentStatus.OPTED_OUT):
        db.add(
            ConsentEvent(
                id=new_id("ce"),
                session_id=session_row.id,
                channel="sms",
                status=status.value,
                source="browser",
                created_at=datetime.now(UTC)
                + timedelta(seconds=0 if status is ConsentStatus.OPTED_IN else 1),
            )
        )
    db.commit()
    rows = (
        db.query(ConsentEvent).filter(ConsentEvent.session_id == session_row.id).all()
    )
    assert len(rows) == 2
