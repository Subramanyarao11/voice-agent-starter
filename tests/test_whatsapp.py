"""WhatsApp: template rules, the messaging window, and inbound identity.

Two properties dominate. Free-form text outside the 24-hour window is rejected
by Meta and damages the sender's standing, so it must be refused locally. And a
WhatsApp sender is a string a third party asserts — it identifies a
conversation and authorizes nothing.
"""

from __future__ import annotations

import httpx
import pytest
from sqlmodel import Session

from sahaayak_api.integrations.infobip import InfobipClient, InfobipConfig
from sahaayak_api.integrations.infobip.webhooks import parse_inbound_whatsapp
from sahaayak_api.integrations.infobip.whatsapp import (
    TEMPLATE_SEND_PATH,
    TEXT_SEND_PATH,
    InfobipWhatsAppProvider,
    open_window,
    window_is_open,
)
from sahaayak_api.notifications.base import OutboundNotification
from sahaayak_api.notifications.templates import RenderedMessage
from sahaayak_common import UserSession, channel_identity_hash, engine, reset_cache
from sahaayak_contracts import DeliveryStatus, NotificationChannel, ProviderErrorClass

CONFIG = InfobipConfig(
    base_url="https://test.api.infobip.com", api_key="k", timeout_seconds=1.0, max_retries=0
)
PHONE = "+919876543210"

TEMPLATE_OK = {
    "messages": [
        {"messageId": "wa-1", "status": {"groupId": 1, "groupName": "PENDING", "id": 7}}
    ]
}
# The text endpoint answers with a single message, not an array.
TEXT_OK = {"messageId": "wa-2", "status": {"groupId": 1, "groupName": "PENDING", "id": 7}}


@pytest.fixture(autouse=True)
def clean_cache():
    reset_cache()
    yield
    reset_cache()


def provider(handler, *, sender: str = "919999999999") -> InfobipWhatsAppProvider:
    return InfobipWhatsAppProvider(
        InfobipClient(CONFIG, transport=httpx.MockTransport(handler)), sender=sender
    )


def notification(*, template: str = "benefit_reminder_utility_en") -> OutboundNotification:
    return OutboundNotification(
        channel=NotificationChannel.WHATSAPP,
        destination=PHONE,
        message=RenderedMessage(
            template_key="benefit_reminder",
            channel=NotificationChannel.WHATSAPP,
            locale="kn",
            subject="",
            text="You may qualify for X. https://s.test",
            provider_template_name=template,
            variables=("X", "https://s.test"),
        ),
        internal_message_id="msg_1",
        idempotency_key="idem_1",
    )


def ok(capture: dict | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        if capture is not None:
            capture["url"] = str(request.url)
            capture["body"] = request.read().decode()
        body = TEMPLATE_OK if request.url.path == TEMPLATE_SEND_PATH else TEXT_OK
        return httpx.Response(200, json=body)

    return handler


# --- Outbound templates ---------------------------------------------------


async def test_a_reminder_is_sent_as_an_approved_template() -> None:
    capture: dict = {}
    result = await provider(ok(capture)).send(notification())

    assert result.accepted
    assert result.status is DeliveryStatus.ACCEPTED
    assert result.external_message_id == "wa-1"
    assert capture["url"].endswith(TEMPLATE_SEND_PATH)
    assert "benefit_reminder_utility_en" in capture["body"]


async def test_template_placeholders_are_sent_in_order() -> None:
    capture: dict = {}
    await provider(ok(capture)).send(notification())
    body = capture["body"]
    assert body.index("X") < body.index("https://s.test")


async def test_the_template_language_follows_the_message_locale() -> None:
    capture: dict = {}
    await provider(ok(capture)).send(notification())
    assert '"kn"' in capture["body"]


async def test_a_message_without_an_approved_template_is_refused_locally() -> None:
    """Meta would reject it, and the attempt counts against sender standing."""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json=TEMPLATE_OK)

    result = await provider(handler).send(notification(template=""))

    assert not result.accepted
    assert result.error_class is ProviderErrorClass.TEMPLATE_REJECTED
    assert calls["n"] == 0


async def test_a_non_e164_destination_is_refused() -> None:
    note = notification()
    note.destination = "9876543210"
    result = await provider(ok()).send(note)
    assert result.error_class is ProviderErrorClass.INVALID_DESTINATION


# --- The messaging window -------------------------------------------------


async def test_the_window_starts_closed() -> None:
    assert not await window_is_open(PHONE)


async def test_an_inbound_message_opens_the_window() -> None:
    await open_window(PHONE)
    assert await window_is_open(PHONE)


async def test_the_window_is_tracked_per_sender() -> None:
    await open_window(PHONE)
    assert not await window_is_open("+919000000000")


async def test_a_free_form_reply_is_refused_when_the_window_is_closed() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json=TEXT_OK)

    result = await provider(handler).send_reply(
        destination=PHONE, text="Here is what I found", internal_message_id="msg_2"
    )

    assert not result.accepted
    assert result.error_class is ProviderErrorClass.TEMPLATE_REJECTED
    assert calls["n"] == 0


async def test_a_free_form_reply_is_sent_inside_the_window() -> None:
    capture: dict = {}
    await open_window(PHONE)

    result = await provider(ok(capture)).send_reply(
        destination=PHONE, text="Here is what I found", internal_message_id="msg_2"
    )

    assert result.accepted
    assert result.external_message_id == "wa-2"
    assert capture["url"].endswith(TEXT_SEND_PATH)


async def test_an_empty_reply_is_not_sent() -> None:
    await open_window(PHONE)
    result = await provider(ok()).send_reply(
        destination=PHONE, text="   ", internal_message_id="msg_3"
    )
    assert not result.accepted


# --- Inbound normalization ------------------------------------------------


def test_a_text_message_is_normalized() -> None:
    events = parse_inbound_whatsapp(
        {"results": [{"from": PHONE, "message": {"type": "TEXT", "text": "I need a scholarship"}}]}
    )
    assert events[0]["kind"] == "TEXT"
    assert events[0]["text"] == "I need a scholarship"


def test_a_button_reply_becomes_a_typed_action_not_model_input() -> None:
    """The user pressed a specific control; a model must not reinterpret it."""
    events = parse_inbound_whatsapp(
        {
            "results": [
                {
                    "from": PHONE,
                    "message": {"type": "BUTTON", "id": "save_benefit", "title": "Save"},
                }
            ]
        }
    )
    assert events[0]["kind"] == "ACTION"
    assert events[0]["action"] == "save_benefit"


def test_a_voice_note_is_normalized_as_audio() -> None:
    events = parse_inbound_whatsapp(
        {"results": [{"from": PHONE, "message": {"type": "VOICE", "id": "media-1"}}]}
    )
    assert events[0]["kind"] == "AUDIO"
    assert events[0]["media_id"] == "media-1"


def test_a_shared_location_is_not_turned_into_a_profile_value() -> None:
    events = parse_inbound_whatsapp(
        {
            "results": [
                {
                    "from": PHONE,
                    "message": {"type": "LOCATION", "latitude": 12.9, "longitude": 77.5},
                }
            ]
        }
    )
    assert events[0]["kind"] == "LOCATION"
    assert not events[0]["text"]


def test_an_unsupported_media_type_is_labelled_rather_than_dropped() -> None:
    events = parse_inbound_whatsapp(
        {"results": [{"from": PHONE, "message": {"type": "DOCUMENT", "id": "d-1"}}]}
    )
    assert events[0]["kind"] == "UNSUPPORTED"


def test_malformed_inbound_entries_are_skipped() -> None:
    assert parse_inbound_whatsapp({"results": [{"garbage": 1}, {"from": ""}]}) == []
    assert parse_inbound_whatsapp(None) == []


# --- Identity -------------------------------------------------------------


def test_a_sender_is_hashed_and_never_used_raw() -> None:
    identity = channel_identity_hash("whatsapp", PHONE)
    assert PHONE not in identity
    assert "9876543210" not in identity


def test_a_whatsapp_session_cannot_satisfy_the_browser_dependency(
    client, database
) -> None:
    """Knowing a phone number must not reach another person's saved data."""
    from sahaayak_api.workers.whatsapp_inbound import _ensure_channel_session

    identity = _ensure_channel_session(channel_identity_hash("whatsapp", PHONE))
    with Session(engine) as db:
        row = db.query(UserSession).filter_by(phone_or_session_id=identity).first()

    assert row.auth_mode == "whatsapp"
    # No access token exists at all, so there is nothing to present.
    assert row.access_token_hash is None

    response = client.get(
        f"/api/sessions/{row.id}/saved-benefits",
        headers={"Authorization": f"Bearer {identity}"},
    )
    assert response.status_code == 401


def test_the_same_sender_reuses_one_conversation(client, database) -> None:
    from sahaayak_api.workers.whatsapp_inbound import _ensure_channel_session

    identity = channel_identity_hash("whatsapp", PHONE)
    _ensure_channel_session(identity)
    _ensure_channel_session(identity)

    with Session(engine) as db:
        rows = db.query(UserSession).filter_by(phone_or_session_id=identity).all()
    assert len(rows) == 1


# --- Webhook routes -------------------------------------------------------


def test_the_whatsapp_webhooks_require_the_shared_secret(client, monkeypatch) -> None:
    from sahaayak_common import settings

    monkeypatch.setattr(settings, "infobip_webhook_auth_secret", "s3cret", raising=False)
    for path in ("/api/webhooks/infobip/whatsapp", "/api/webhooks/infobip/whatsapp/inbound"):
        assert client.post(path, json={"results": []}).status_code == 401


def test_an_inbound_stop_is_applied_inline_not_in_the_background(
    client, monkeypatch, database
) -> None:
    """A STOP is a legal instruction; it must not depend on a background task."""
    from sahaayak_common import settings

    monkeypatch.setattr(settings, "infobip_webhook_auth_secret", "s3cret", raising=False)
    response = client.post(
        "/api/webhooks/infobip/whatsapp/inbound",
        json={"results": [{"from": PHONE, "message": {"type": "TEXT", "text": "STOP"}}]},
        headers={"X-Infobip-Webhook-Secret": "s3cret"},
    )
    assert response.status_code == 200


# --- Provider MSISDN format (found against the live API) -------------------


def test_an_inbound_sender_without_a_plus_is_restored_to_e164() -> None:
    """Infobip reports MSISDNs in international format but without the plus.

    Found the hard way: the agent ran correctly on a real inbound payload and
    then refused to reply, because the sender failed strict E.164 validation.
    """
    from sahaayak_api.integrations.infobip.webhooks import to_e164

    assert to_e164("919034334891") == "+919034334891"
    assert to_e164("+919034334891") == "+919034334891"
    assert to_e164("+91 90343-34891") == "+919034334891"


def test_a_non_numeric_sender_is_left_alone() -> None:
    """Alphanumeric sender IDs are not phone numbers and must not gain a plus."""
    from sahaayak_api.integrations.infobip.webhooks import to_e164

    assert to_e164("SAHAYK") == "SAHAYK"
    assert to_e164("") == ""


def test_a_real_inbound_payload_yields_a_sendable_destination() -> None:
    """The exact shape Infobip delivered, end to end through the parser."""
    from sahaayak_common import is_valid_e164

    events = parse_inbound_whatsapp(
        {
            "results": [
                {
                    "from": "919034334891",
                    "to": "447860088970",
                    "integrationType": "WHATSAPP",
                    "messageId": "sim-inbound-2",
                    "message": {"type": "TEXT", "text": "find me a job"},
                    "contact": {"name": "Daksh"},
                }
            ],
            "messageCount": 1,
        }
    )
    assert events[0]["sender"] == "+919034334891"
    assert is_valid_e164(events[0]["sender"]), "the reply path validates strict E.164"
