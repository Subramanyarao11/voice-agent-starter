"""Parsing Infobip callbacks into provider-neutral status updates.

Kept apart from the route so the mapping — which provider status means what,
which failures mean the destination itself is unusable, which events revoke
consent — is a pure function over a payload, testable without HTTP.

Two properties matter more than completeness here. A callback is untrusted
input from the public internet, so every field is optional and nothing is
indexed without checking. And provider reports arrive duplicated and out of
order routinely, so the output is designed to be applied idempotently rather
than assumed to be a fresh, ordered event.
"""

from __future__ import annotations

import re
from typing import Any

from sahaayak_api.integrations.infobip.models import InfobipDeliveryReport
from sahaayak_api.integrations.infobip.outbound import status_for_group
from sahaayak_contracts import (
    DeliveryStatus,
    DeliveryStatusUpdate,
    NotificationChannel,
    ProviderErrorClass,
)

# Email report status names, which are words rather than the numeric groups
# SMS uses. Opens and clicks are recorded as delivery: the product does not
# track engagement, and a row that regresses from "opened" to "delivered" on a
# late callback would be worse than not distinguishing them.
_EMAIL_STATUS_NAMES: dict[str, DeliveryStatus] = {
    "PENDING": DeliveryStatus.ACCEPTED,
    "ACCEPTED": DeliveryStatus.ACCEPTED,
    "QUEUED": DeliveryStatus.ACCEPTED,
    "DELIVERED": DeliveryStatus.DELIVERED,
    "OPENED": DeliveryStatus.DELIVERED,
    "CLICKED": DeliveryStatus.DELIVERED,
    "SEEN": DeliveryStatus.SEEN,
    "BOUNCED": DeliveryStatus.FAILED,
    "REJECTED": DeliveryStatus.FAILED,
    "UNDELIVERABLE": DeliveryStatus.FAILED,
    "EXPIRED": DeliveryStatus.FAILED,
    "SPAM": DeliveryStatus.FAILED,
    "COMPLAINT": DeliveryStatus.FAILED,
    "UNSUBSCRIBED": DeliveryStatus.SUPPRESSED,
}

# A hard bounce or an unknown subscriber means this destination will never
# work. Retrying it forever wastes money and, on SMS, may be billed each time.
_INVALID_DESTINATION = re.compile(
    r"hard[_ ]?bounce"
    r"|invalid[_ ]?(address|destination|recipient|number)"
    r"|unknown[_ ]?(user|subscriber)"
    r"|no[_ ]?such[_ ]?(user|address)"
    r"|not[_ ]?exist"
    r"|absent[_ ]?subscriber",
    re.IGNORECASE,
)

# A complaint or an unsubscribe is the person saying stop. It withdraws
# consent, which is a stronger and more durable statement than a failure.
_CONSENT_REVOKED = re.compile(
    r"unsubscrib|complaint|spam[_ ]?report|opt[_ ]?out|blacklist|do[_ ]?not[_ ]?contact",
    re.IGNORECASE,
)

# Keywords that revoke consent when a caller replies to an SMS. Deliberately
# generous across the languages this service speaks, and matched on the whole
# reply rather than as a substring, so "stop asking me things" counts but a
# sentence merely containing "band" does not.
STOP_KEYWORDS = frozenset(
    {
        "stop",
        "stopall",
        "unsubscribe",
        "cancel",
        "end",
        "quit",
        "optout",
        "opt-out",
        "band",  # band karo — Hindi, transliterated
        "बंद",
        "रोको",
        "ನಿಲ್ಲಿಸಿ",
        "ಬೇಡ",
    }
)


def results_from(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    """The report array, tolerating the shapes a callback may arrive in."""
    if not isinstance(payload, dict):
        return []
    for key in ("results", "messages"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def parse_delivery_reports(
    payload: dict[str, Any] | None, *, channel: NotificationChannel
) -> list[DeliveryStatusUpdate]:
    updates: list[DeliveryStatusUpdate] = []
    for entry in results_from(payload):
        update = _parse_one(entry, channel=channel)
        if update is not None:
            updates.append(update)
    return updates


def _parse_one(
    entry: dict[str, Any], *, channel: NotificationChannel
) -> DeliveryStatusUpdate | None:
    try:
        report = InfobipDeliveryReport.model_validate(entry)
    except Exception:
        # A callback we cannot parse is discarded rather than allowed to fail
        # the whole batch: one malformed entry must not block the valid
        # reports delivered alongside it.
        return None

    if not report.message_id:
        return None

    status_name = (report.status.name if report.status else "").upper()
    group_name = (report.status.group_name if report.status else "").upper()
    error = report.error
    error_text = " ".join(
        filter(None, [error.name if error else "", error.description if error else ""])
    )
    haystack = f"{status_name} {group_name} {error_text}"

    status = _status_for(channel, report, status_name, group_name)

    # An error block with a non-zero id is a real failure even when the status
    # group still reads as pending.
    if error is not None and error.id not in (None, 0) and status not in (
        DeliveryStatus.SUPPRESSED,
    ):
        status = DeliveryStatus.FAILED

    destination_invalid = bool(_INVALID_DESTINATION.search(haystack)) or bool(
        error is not None and error.permanent and status is DeliveryStatus.FAILED
    )
    consent_revoked = bool(_CONSENT_REVOKED.search(haystack))

    price = report.price
    return DeliveryStatusUpdate(
        external_message_id=report.message_id,
        channel=channel,
        status=status,
        provider="infobip",
        provider_status_code=report.status.code if report.status else "",
        provider_status_group=group_name,
        provider_error_code=str(error.id) if error and error.id is not None else "",
        error_class=(
            ProviderErrorClass.INVALID_DESTINATION
            if destination_invalid
            else ProviderErrorClass.PROVIDER_ERROR
            if status is DeliveryStatus.FAILED
            else ProviderErrorClass.NONE
        ),
        cost_minor_units=price.minor_units() if price else None,
        cost_currency=price.currency if price else "",
        destination_invalid=destination_invalid,
        consent_revoked=consent_revoked,
        callback_reference=report.callback_data,
    )


def _status_for(
    channel: NotificationChannel,
    report: InfobipDeliveryReport,
    status_name: str,
    group_name: str,
) -> DeliveryStatus:
    if channel is NotificationChannel.EMAIL:
        for candidate in (status_name, group_name):
            if candidate in _EMAIL_STATUS_NAMES:
                return _EMAIL_STATUS_NAMES[candidate]
    # SMS and WhatsApp report a numeric group; fall back to it for email too,
    # since the numeric grouping is shared across channels.
    return status_for_group(
        report.status.group_id if report.status else None,
        default=DeliveryStatus.ACCEPTED,
    )


def is_stop_keyword(text: str) -> bool:
    """Whether an inbound reply is a request to stop messaging.

    Compared against the whole normalized reply. Substring matching would let
    an ordinary sentence silently unsubscribe someone who wanted help.
    """
    normalized = re.sub(r"[^\wऀ-ॿಀ-೿-]+", " ", text.strip().lower())
    words = [word for word in normalized.split() if word]
    if not words:
        return False
    if len(words) <= 2 and any(word in STOP_KEYWORDS for word in words):
        return True
    return words[0] in STOP_KEYWORDS


def parse_call_events(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Normalize Calls API events into the vocabulary the call worker uses.

    The caller's number is passed through raw for the worker to hash
    immediately; like a WhatsApp sender, a caller ID is asserted by the network
    and proves nothing about who is on the line.
    """
    if not isinstance(payload, dict):
        return []

    entries = payload.get("events")
    if not isinstance(entries, list):
        entries = [payload]

    events: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        properties = entry.get("properties") if isinstance(entry.get("properties"), dict) else {}
        call = properties.get("call") if isinstance(properties.get("call"), dict) else {}

        call_id = (
            entry.get("callId")
            or call.get("id")
            or properties.get("callId")
            or entry.get("call_id")
            or ""
        )
        if not call_id:
            continue

        endpoint = call.get("endpoint") if isinstance(call.get("endpoint"), dict) else {}
        events.append(
            {
                "type": str(entry.get("type") or entry.get("name") or "").upper(),
                "call_id": str(call_id),
                "from": str(endpoint.get("phoneNumber") or call.get("from") or entry.get("from")
                             or ""),
                "text": str(properties.get("text") or entry.get("text") or ""),
                "reason": str(properties.get("reason") or entry.get("reason") or ""),
                "error_code": str(properties.get("errorCode") or ""),
            }
        )
    return events


def parse_inbound_whatsapp(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Normalize inbound WhatsApp events into a small typed vocabulary.

    Returns dicts rather than a Pydantic model because the sender must be
    hashed by the caller before anything is constructed around it, and handing
    back a tidy object holding a raw phone number invites it being stored.

    Button and list replies are mapped to a typed action and never sent to a
    language model. The user pressed a specific control; asking a model to
    interpret which one would be strictly worse than reading the payload.
    """
    events: list[dict[str, Any]] = []
    for entry in results_from(payload):
        sender = entry.get("from") or entry.get("sender") or ""
        if not isinstance(sender, str) or not sender:
            continue

        message = entry.get("message")
        if not isinstance(message, dict):
            continue

        kind = str(message.get("type") or "").upper()
        event: dict[str, Any] = {
            "sender": sender,
            "kind": kind,
            "provider_message_id": entry.get("messageId") or "",
            "text": "",
            "media_id": "",
            "media_mime_type": "",
            "action": "",
        }

        if kind in ("TEXT", ""):
            event["kind"] = "TEXT"
            event["text"] = message.get("text") or ""
        elif kind in ("AUDIO", "VOICE"):
            event["kind"] = "AUDIO"
            event["media_id"] = message.get("id") or message.get("mediaId") or ""
            event["media_mime_type"] = message.get("mimeType") or "audio/ogg"
        elif kind in ("BUTTON", "INTERACTIVE_BUTTON_REPLY"):
            event["kind"] = "ACTION"
            event["action"] = _action_id(message)
            event["text"] = message.get("title") or message.get("text") or ""
        elif kind in ("LIST", "INTERACTIVE_LIST_REPLY"):
            event["kind"] = "ACTION"
            event["action"] = _action_id(message)
            event["text"] = message.get("title") or message.get("text") or ""
        elif kind == "LOCATION":
            # Never written to the caller's profile automatically. A location
            # narrows eligibility, and inferring it from a shared pin is a
            # profile mutation the caller did not ask for.
            event["kind"] = "LOCATION"
        else:
            event["kind"] = "UNSUPPORTED"

        events.append(event)
    return events


def _action_id(message: dict[str, Any]) -> str:
    for key in ("id", "payload", "postbackData", "buttonId"):
        value = message.get(key)
        if isinstance(value, str) and value:
            return value[:64]
    return ""


def parse_inbound_sms(payload: dict[str, Any] | None) -> list[tuple[str, str]]:
    """Inbound SMS as (sender, text) pairs.

    The sender is returned raw for the caller to hash immediately. It is a
    channel identity asserted by the network, never an authenticated user.
    """
    messages: list[tuple[str, str]] = []
    for entry in results_from(payload):
        sender = entry.get("from") or entry.get("sender") or ""
        message = entry.get("message")
        text = ""
        if isinstance(message, dict):
            text = message.get("text") or ""
        elif isinstance(entry.get("text"), str):
            text = entry["text"]
        elif isinstance(entry.get("cleanText"), str):
            text = entry["cleanText"]
        if isinstance(sender, str) and isinstance(text, str) and sender and text:
            messages.append((sender, text))
    return messages
