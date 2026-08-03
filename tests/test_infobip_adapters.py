"""SMS and email adapters against a mocked Infobip.

The segmentation tests carry the most weight. A message that is one cheap
segment in English becomes several expensive ones in Kannada, and this service
pays per segment on behalf of people who have very little money.
"""

from __future__ import annotations

import httpx
import pytest

from sahaayak_api.integrations.infobip import InfobipClient, InfobipConfig
from sahaayak_api.integrations.infobip.email import InfobipEmailProvider
from sahaayak_api.integrations.infobip.sms import (
    GSM_CONCAT_LIMIT,
    UCS2_CONCAT_LIMIT,
    InfobipSmsProvider,
    count_segments,
    encoding_for,
    is_gsm7,
)
from sahaayak_api.notifications.base import OutboundNotification
from sahaayak_api.notifications.templates import RenderedMessage
from sahaayak_common import settings
from sahaayak_contracts import (
    DeliveryStatus,
    NotificationChannel,
    ProviderErrorClass,
)

CONFIG = InfobipConfig(
    base_url="https://test.api.infobip.com", api_key="k", timeout_seconds=1.0, max_retries=0
)

ACCEPTED_BODY = {
    "bulkId": "bulk-1",
    "messages": [
        {
            "messageId": "msg-1",
            "status": {"groupId": 1, "groupName": "PENDING", "id": 26, "name": "PENDING_ACCEPTED"},
        }
    ],
}


def make_notification(
    *,
    channel: NotificationChannel = NotificationChannel.SMS,
    destination: str = "+919876543210",
    text: str = "Sahaayak reminder: you may qualify. https://x.test",
    subject: str = "Reminder",
) -> OutboundNotification:
    return OutboundNotification(
        channel=channel,
        destination=destination,
        message=RenderedMessage(
            template_key="benefit_reminder",
            channel=channel,
            locale="en",
            subject=subject,
            text=text,
            html=f"<p>{text}</p>",
        ),
        internal_message_id="msg_internal_1",
        idempotency_key="idem-1",
    )


def sms_provider(handler) -> InfobipSmsProvider:
    return InfobipSmsProvider(
        InfobipClient(CONFIG, transport=httpx.MockTransport(handler)), sender="SAHAYK"
    )


def email_provider(handler) -> InfobipEmailProvider:
    return InfobipEmailProvider(
        InfobipClient(CONFIG, transport=httpx.MockTransport(handler)),
        sender="noreply@sahaayak.test",
        sender_name="Sahaayak",
    )


def accepting(capture: dict | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        if capture is not None:
            capture["body"] = request.read().decode()
            capture["url"] = str(request.url)
        return httpx.Response(200, json=ACCEPTED_BODY)

    return handler


# --- Segmentation ---------------------------------------------------------


def test_plain_english_uses_the_cheap_gsm_alphabet() -> None:
    assert is_gsm7("Sahaayak reminder: you may qualify. https://x.test")
    assert encoding_for("Hello") == "GSM7"


@pytest.mark.parametrize(
    "text",
    [
        "ಸಹಾಯಕ ಜ್ಞಾಪನೆ",  # Kannada
        "सहायक अनुस्मारक",  # Hindi
        "Reminder ಸಹಾಯಕ",  # mixed
    ],
)
def test_indian_language_text_forces_the_expensive_encoding(text: str) -> None:
    assert not is_gsm7(text)
    assert encoding_for(text) == "UCS2"


def test_one_non_gsm_character_downgrades_the_whole_message() -> None:
    """This is why a friendly extra sentence is a real recurring cost."""
    assert encoding_for("Reminder" + "ಸ") == "UCS2"


def test_an_empty_message_has_no_segments() -> None:
    assert count_segments("") == 0


def test_a_short_english_message_is_one_segment() -> None:
    assert count_segments("a" * 160) == 1
    assert count_segments("a" * 161) == 2


def test_long_english_messages_use_the_concatenated_limit() -> None:
    assert count_segments("a" * (GSM_CONCAT_LIMIT * 2)) == 2
    assert count_segments("a" * (GSM_CONCAT_LIMIT * 2 + 1)) == 3


def test_a_short_kannada_message_is_one_segment() -> None:
    assert count_segments("ಸ" * 70) == 1
    assert count_segments("ಸ" * 71) == 2


def test_long_kannada_messages_use_the_smaller_concatenated_limit() -> None:
    assert count_segments("ಸ" * (UCS2_CONCAT_LIMIT * 3)) == 3


def test_kannada_costs_more_segments_than_english_of_the_same_length() -> None:
    assert count_segments("ಸ" * 300) > count_segments("a" * 300)


def test_gsm_extended_characters_cost_two_septets() -> None:
    assert count_segments("{" * 80) == 1
    assert count_segments("{" * 81) == 2


# --- SMS sending ----------------------------------------------------------


async def test_an_accepted_sms_is_recorded_as_accepted_not_delivered() -> None:
    result = await sms_provider(accepting()).send(make_notification())
    assert result.accepted
    assert result.status is DeliveryStatus.ACCEPTED
    assert result.external_message_id == "msg-1"
    assert result.external_bulk_id == "bulk-1"


async def test_the_sms_payload_carries_the_sender_and_opaque_callback_id() -> None:
    capture: dict = {}
    await sms_provider(accepting(capture)).send(make_notification())
    body = capture["body"]
    assert '"sender": "SAHAYK"' in body or '"sender":"SAHAYK"' in body
    assert "msg_internal_1" in body
    assert capture["url"].endswith("/sms/3/messages")


async def test_the_sms_payload_never_carries_the_session_id() -> None:
    capture: dict = {}
    notification = make_notification()
    notification.session_id = "ses_secret"
    await sms_provider(accepting(capture)).send(notification)
    assert "ses_secret" not in capture["body"]


async def test_a_non_e164_number_is_refused_without_calling_the_provider() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json=ACCEPTED_BODY)

    result = await sms_provider(handler).send(make_notification(destination="9876543210"))

    assert not result.accepted
    assert result.error_class is ProviderErrorClass.INVALID_DESTINATION
    assert not result.retryable
    assert calls["n"] == 0


async def test_an_over_budget_message_is_refused_before_it_is_billed(monkeypatch) -> None:
    monkeypatch.setattr(settings, "sms_max_segments", 2, raising=False)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json=ACCEPTED_BODY)

    result = await sms_provider(handler).send(make_notification(text="ಸ" * 500))

    assert not result.accepted
    assert result.error_class is ProviderErrorClass.INVALID_REQUEST
    assert calls["n"] == 0


async def test_an_empty_body_is_refused() -> None:
    result = await sms_provider(accepting()).send(make_notification(text="   "))
    assert not result.accepted
    assert result.error_class is ProviderErrorClass.INVALID_REQUEST


async def test_a_missing_sender_is_a_configuration_failure() -> None:
    provider = InfobipSmsProvider(
        InfobipClient(CONFIG, transport=httpx.MockTransport(accepting())), sender=""
    )
    result = await provider.send(make_notification())
    assert result.error_class is ProviderErrorClass.NOT_CONFIGURED


async def test_a_provider_rejection_is_returned_not_raised() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "requestError": {
                    "serviceException": {"messageId": "E1", "text": "Invalid destination"}
                }
            },
        )

    result = await sms_provider(handler).send(make_notification())

    assert not result.accepted
    assert result.error_class is ProviderErrorClass.INVALID_DESTINATION


async def test_a_rate_limited_send_is_marked_retryable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "5"}, json={})

    result = await sms_provider(handler).send(make_notification())

    assert not result.accepted
    assert result.retryable
    assert result.retry_after_seconds == 5


async def test_a_success_without_a_message_id_is_treated_as_failure() -> None:
    """With no external ID there is nothing to reconcile a report against."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"messages": []})

    result = await sms_provider(handler).send(make_notification())

    assert not result.accepted
    assert result.error_class is ProviderErrorClass.MALFORMED_RESPONSE
    assert not result.retryable


async def test_a_rejected_status_group_is_reported_as_failed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "messages": [
                    {
                        "messageId": "m-2",
                        "status": {"groupId": 5, "groupName": "REJECTED", "id": 6},
                    }
                ]
            },
        )

    result = await sms_provider(handler).send(make_notification())
    assert result.status is DeliveryStatus.FAILED


# --- Email sending --------------------------------------------------------


async def test_an_accepted_email_is_recorded_as_accepted() -> None:
    result = await email_provider(accepting()).send(
        make_notification(channel=NotificationChannel.EMAIL, destination="a@b.test")
    )
    assert result.accepted
    assert result.status is DeliveryStatus.ACCEPTED
    assert result.external_message_id == "msg-1"


async def test_email_always_sends_a_plain_text_alternative() -> None:
    capture: dict = {}
    await email_provider(accepting(capture)).send(
        make_notification(channel=NotificationChannel.EMAIL, destination="a@b.test")
    )
    body = capture["body"]
    assert '"text"' in body
    assert '"html"' in body


async def test_the_email_from_header_includes_the_display_name() -> None:
    capture: dict = {}
    await email_provider(accepting(capture)).send(
        make_notification(channel=NotificationChannel.EMAIL, destination="a@b.test")
    )
    assert "Sahaayak <noreply@sahaayak.test>" in capture["body"]


async def test_a_malformed_address_is_refused_without_calling_the_provider() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json=ACCEPTED_BODY)

    result = await email_provider(handler).send(
        make_notification(channel=NotificationChannel.EMAIL, destination="not-an-address")
    )

    assert result.error_class is ProviderErrorClass.INVALID_DESTINATION
    assert calls["n"] == 0


async def test_an_overlong_subject_is_truncated_rather_than_rejected() -> None:
    capture: dict = {}
    await email_provider(accepting(capture)).send(
        make_notification(
            channel=NotificationChannel.EMAIL, destination="a@b.test", subject="s" * 500
        )
    )
    assert "s" * 500 not in capture["body"]


async def test_a_bounce_style_rejection_is_not_retried() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "requestError": {
                    "serviceException": {"messageId": "E2", "text": "Invalid address"}
                }
            },
        )

    result = await email_provider(handler).send(
        make_notification(channel=NotificationChannel.EMAIL, destination="a@b.test")
    )
    assert result.error_class is ProviderErrorClass.INVALID_DESTINATION
    assert not result.retryable


# --- Availability ---------------------------------------------------------


def test_adapters_report_unavailable_when_the_channel_is_switched_off() -> None:
    assert not sms_provider(accepting()).available()
    assert not email_provider(accepting()).available()
