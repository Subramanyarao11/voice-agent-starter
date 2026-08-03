"""Public webhook endpoints for Infobip callbacks.

These are the only routes in the application reachable without a Sahaayak
credential, so they are deliberately narrow.

They authenticate with their own shared secret and never with the browser
bearer token or an admin token: a provider must not hold a credential that
opens anything else, and a leaked webhook secret must not become session
access. When no secret is configured the routes refuse every request rather
than accepting anonymous ones — an unauthenticated endpoint that mutates
delivery state is worse than a channel with no callbacks.

They also answer quickly and unconditionally with 2xx once a payload is
accepted. A provider that sees an error retries, and a callback retried against
a handler that already applied it is how a delivery log ends up with duplicate
history. Anything that could be slow or could fail is either idempotent or
skipped.
"""

from __future__ import annotations

import hmac
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlmodel import Session, select

from sahaayak_api.integrations.infobip.webhooks import (
    is_stop_keyword,
    parse_delivery_reports,
    parse_inbound_sms,
    parse_inbound_whatsapp,
)
from sahaayak_api.telemetry import record_telemetry
from sahaayak_api.workers.whatsapp_inbound import handle_event as handle_whatsapp_event
from sahaayak_common import (
    ConsentEvent,
    ContactPoint,
    NotificationDelivery,
    Reminder,
    channel_identity_hash,
    get_cache,
    get_logger,
    get_session,
    new_id,
    settings,
)
from sahaayak_contracts import (
    ConsentStatus,
    DeliveryStatus,
    DeliveryStatusUpdate,
    NotificationChannel,
    VerificationStatusValue,
    supersedes,
)

log = get_logger(__name__)

router = APIRouter(prefix="/api/webhooks/infobip", tags=["provider webhooks"])

SECRET_HEADER = "X-Infobip-Webhook-Secret"

# How long a processed callback is remembered for replay suppression. Long
# enough to cover a provider's retry schedule, short enough that the cache
# cannot grow without bound.
REPLAY_TTL_SECONDS = 60 * 60 * 6


class WebhookAck(BaseModel):
    """Deliberately uninformative.

    The response tells an unauthenticated caller nothing about whether a
    message ID exists or what state it is in, which would otherwise make this
    endpoint an oracle for probing delivery records.
    """

    accepted: bool = True
    processed: int = 0


async def require_webhook_secret(request: Request) -> None:
    if not settings.infobip_webhook_auth_secret:
        # Closed by default. Without a configured secret there is no way to
        # tell Infobip from anyone else who found the URL.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Provider callbacks are not configured",
        )

    presented = request.headers.get(SECRET_HEADER, "")
    if not hmac.compare_digest(presented, settings.infobip_webhook_auth_secret):
        log.warning(
            "infobip_webhook_rejected",
            reason="bad_secret",
            path=request.url.path,
            secret_present=bool(presented),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook credentials"
        )


async def read_bounded_payload(request: Request) -> dict:
    """Read and parse a callback body, refusing anything oversized.

    Checked against the body actually read rather than Content-Length, which
    an attacker controls independently of what they send.
    """
    body = await request.body()
    if len(body) > settings.infobip_max_webhook_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Callback payload too large",
        )
    if not body:
        return {}
    try:
        import json

        parsed = json.loads(body)
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Malformed callback payload"
        ) from exc
    return parsed if isinstance(parsed, dict) else {}


@router.post("/sms", response_model=WebhookAck, dependencies=[Depends(require_webhook_secret)])
async def sms_delivery_reports(
    request: Request, db: Session = Depends(get_session)
) -> WebhookAck:
    payload = await read_bounded_payload(request)
    updates = parse_delivery_reports(payload, channel=NotificationChannel.SMS)
    processed = await _apply_updates(db, updates, channel=NotificationChannel.SMS)
    return WebhookAck(processed=processed)


@router.post("/email", response_model=WebhookAck, dependencies=[Depends(require_webhook_secret)])
async def email_delivery_reports(
    request: Request, db: Session = Depends(get_session)
) -> WebhookAck:
    payload = await read_bounded_payload(request)
    updates = parse_delivery_reports(payload, channel=NotificationChannel.EMAIL)
    processed = await _apply_updates(db, updates, channel=NotificationChannel.EMAIL)
    return WebhookAck(processed=processed)


@router.post(
    "/whatsapp", response_model=WebhookAck, dependencies=[Depends(require_webhook_secret)]
)
async def whatsapp_delivery_reports(
    request: Request, db: Session = Depends(get_session)
) -> WebhookAck:
    payload = await read_bounded_payload(request)
    updates = parse_delivery_reports(payload, channel=NotificationChannel.WHATSAPP)
    processed = await _apply_updates(db, updates, channel=NotificationChannel.WHATSAPP)
    return WebhookAck(processed=processed)


@router.post(
    "/whatsapp/inbound",
    response_model=WebhookAck,
    dependencies=[Depends(require_webhook_secret)],
)
async def inbound_whatsapp(
    request: Request, background: BackgroundTasks, db: Session = Depends(get_session)
) -> WebhookAck:
    """Accept an inbound WhatsApp message and answer immediately.

    The agent turn — and the transcription before it, for a voice note — takes
    far longer than a provider waits before deciding the callback failed and
    retrying it. So the work is scheduled and the acknowledgement goes back
    now. An opt-out is the exception: it is applied inline, because a STOP is a
    legal instruction and must not depend on a background task succeeding.
    """
    payload = await read_bounded_payload(request)
    events = parse_inbound_whatsapp(payload)
    scheduled = 0
    revoked = 0

    for event in events:
        sender = event.get("sender") or ""
        text = str(event.get("text") or "")
        if event.get("kind") == "TEXT" and is_stop_keyword(text):
            revoked += _revoke_by_destination(
                db, sender, channel=NotificationChannel.WHATSAPP
            )
            continue
        if await _seen_before(
            f"mo:wa:{event.get('provider_message_id') or ''}"
        ) and event.get("provider_message_id"):
            continue
        background.add_task(handle_whatsapp_event, event)
        scheduled += 1

    if revoked:
        db.commit()

    record_telemetry(
        event_type="notification",
        route="/api/webhooks/infobip/whatsapp/inbound",
        method="POST",
        surface="whatsapp",
        provider="infobip",
        outcome="accepted",
        safe_metadata={"scheduled": scheduled, "revoked": revoked},
    )
    return WebhookAck(processed=scheduled + revoked)


@router.post(
    "/sms/inbound", response_model=WebhookAck, dependencies=[Depends(require_webhook_secret)]
)
async def inbound_sms(request: Request, db: Session = Depends(get_session)) -> WebhookAck:
    """Inbound SMS, processed only for opt-out.

    A reply of STOP is a legal instruction, not a conversation opener, and this
    route deliberately does not feed anything into the agent. The sender string
    is hashed immediately and matched against registered contacts; it never
    identifies a caller on its own.
    """
    payload = await read_bounded_payload(request)
    processed = 0

    for sender, text in parse_inbound_sms(payload):
        if not is_stop_keyword(text):
            # Anything that is not an opt-out is dropped rather than stored.
            # Inbound SMS is not a supported conversation surface, and keeping
            # message bodies from it would collect content nobody reads.
            continue
        if await _seen_before(f"mo:sms:{channel_identity_hash('sms', sender)}:{text[:32]}"):
            continue
        processed += _revoke_by_destination(db, sender, channel=NotificationChannel.SMS)

    if processed:
        db.commit()
    record_telemetry(
        event_type="notification",
        route="/api/webhooks/infobip/sms/inbound",
        method="POST",
        surface="system",
        provider="infobip",
        outcome="opt_out" if processed else "ignored",
        safe_metadata={"channel": "sms", "revoked": processed},
    )
    return WebhookAck(processed=processed)


async def _apply_updates(
    db: Session, updates: list[DeliveryStatusUpdate], *, channel: NotificationChannel
) -> int:
    applied = 0
    for update in updates:
        if await _seen_before(
            f"dlr:{channel.value}:{update.external_message_id}:{update.status.value}"
        ):
            # A replayed callback for a state already recorded. Acknowledged,
            # not reapplied.
            continue
        if _apply_one(db, update, channel=channel):
            applied += 1

    if applied:
        db.commit()

    record_telemetry(
        event_type="notification",
        route=f"/api/webhooks/infobip/{channel.value}",
        method="POST",
        surface="system",
        provider="infobip",
        outcome="processed" if applied else "ignored",
        safe_metadata={
            "channel": channel.value,
            "received": len(updates),
            "applied": applied,
        },
    )
    return applied


def _apply_one(
    db: Session, update: DeliveryStatusUpdate, *, channel: NotificationChannel
) -> bool:
    delivery = _find_delivery(db, update, channel=channel)
    if delivery is None:
        # A report for a message this deployment did not send: a stale
        # callback after a database reset, or a misconfigured shared sender.
        log.info(
            "infobip_delivery_report_unmatched",
            channel=channel.value,
            status=update.status.value,
        )
        return False

    current = _current_status(delivery)
    if not supersedes(current, update.status):
        # Out-of-order or duplicate. Providers routinely deliver a "delivered"
        # callback before the "accepted" one it supersedes, and walking the row
        # backwards would report a delivered reminder as merely queued.
        return False

    now = update.occurred_at or datetime.now(UTC)
    delivery.status = update.status.value
    delivery.provider_status_code = update.provider_status_code or delivery.provider_status_code
    delivery.provider_status_group = (
        update.provider_status_group or delivery.provider_status_group
    )
    delivery.provider_error_code = update.provider_error_code or delivery.provider_error_code
    if update.error_class.value != "none":
        delivery.provider_error_class = update.error_class.value
    if update.cost_minor_units is not None:
        delivery.cost_minor_units = update.cost_minor_units
        delivery.cost_currency = update.cost_currency or delivery.cost_currency
    delivery.updated_at = now

    if update.status is DeliveryStatus.DELIVERED:
        delivery.delivered_at = delivery.delivered_at or now
        # Nothing further will be attempted, so the reminder is done.
        _close_reminder(db, delivery, delivered_at=now)
    elif update.status is DeliveryStatus.SEEN:
        delivery.seen_at = delivery.seen_at or now
    elif update.status in (DeliveryStatus.FAILED, DeliveryStatus.SUPPRESSED):
        delivery.failed_at = delivery.failed_at or now

    db.add(delivery)

    contact = (
        db.get(ContactPoint, delivery.contact_point_id)
        if delivery.contact_point_id
        else None
    )
    if contact is not None:
        if update.destination_invalid:
            _mark_invalid(db, contact)
        if update.consent_revoked:
            _revoke_consent(db, contact, source="provider_report")

    return True


def _find_delivery(
    db: Session, update: DeliveryStatusUpdate, *, channel: NotificationChannel
) -> NotificationDelivery | None:
    """Locate the delivery a report refers to.

    Our own callback reference is preferred over the provider's message ID: it
    is assigned before the send, so it matches even when the response that
    carried the external ID was lost.
    """
    if update.callback_reference:
        row = db.exec(
            select(NotificationDelivery).where(
                NotificationDelivery.internal_message_id == update.callback_reference
            )
        ).first()
        if row is not None:
            return row

    return db.exec(
        select(NotificationDelivery).where(
            NotificationDelivery.channel == channel.value,
            NotificationDelivery.external_message_id == update.external_message_id,
        )
    ).first()


def _current_status(delivery: NotificationDelivery) -> DeliveryStatus:
    try:
        return DeliveryStatus(delivery.status)
    except ValueError:
        return DeliveryStatus.QUEUED


def _close_reminder(
    db: Session, delivery: NotificationDelivery, *, delivered_at: datetime
) -> None:
    if not delivery.reminder_id:
        return
    reminder = db.get(Reminder, delivery.reminder_id)
    if reminder is None or reminder.status != "scheduled":
        return
    reminder.status = "delivered"
    reminder.delivered_at = delivered_at
    reminder.last_delivery_id = delivery.id
    reminder.next_attempt_at = None
    db.add(reminder)


def _mark_invalid(db: Session, contact: ContactPoint) -> None:
    """Stop using a destination the provider says will never work."""
    if contact.verification_status == VerificationStatusValue.INVALID.value:
        return
    contact.verification_status = VerificationStatusValue.INVALID.value
    contact.updated_at = datetime.now(UTC)
    db.add(contact)
    log.info(
        "contact_point_marked_invalid",
        contact_point_id=contact.id,
        channel=contact.channel,
    )


def _revoke_consent(db: Session, contact: ContactPoint, *, source: str) -> None:
    if contact.consent_status == ConsentStatus.OPTED_OUT.value:
        return
    now = datetime.now(UTC)
    contact.consent_status = ConsentStatus.OPTED_OUT.value
    contact.opted_out_at = now
    contact.updated_at = now
    db.add(contact)
    db.add(
        ConsentEvent(
            id=new_id("ce"),
            session_id=contact.session_id,
            contact_point_id=contact.id,
            channel=contact.channel,
            purpose=contact.consent_purpose or "reminders",
            status=ConsentStatus.OPTED_OUT.value,
            source=source,
            actor="provider",
        )
    )
    log.info(
        "consent_revoked_by_provider_event",
        contact_point_id=contact.id,
        channel=contact.channel,
        source=source,
    )


def _revoke_by_destination(
    db: Session, destination: str, *, channel: NotificationChannel
) -> int:
    """Opt out every contact matching a hashed sender.

    Matched by hash, so the incoming number is never compared against, stored
    as, or logged in plaintext. More than one session may have registered the
    same number; a STOP silences all of them, which is the only reading of the
    instruction that respects it.
    """
    from sahaayak_common import destination_hash

    digest = destination_hash(channel.value, destination)
    rows = db.exec(
        select(ContactPoint).where(
            ContactPoint.channel == channel.value,
            ContactPoint.destination_hash == digest,
        )
    ).all()
    for contact in rows:
        _revoke_consent(db, contact, source="sms_stop")
    return len(rows)


async def _seen_before(key: str) -> bool:
    """Whether this exact callback has already been handled.

    Replay suppression is best-effort by design: the cache may be memory-local
    or may have expired. The status-ordering check in `_apply_one` is the
    durable guarantee, and this only avoids the redundant work.
    """
    cache = await get_cache()
    marker = f"sahaayak:webhook:{key}"
    if await cache.get(marker) is not None:
        return True
    await cache.set(marker, b"1", ttl_seconds=REPLAY_TTL_SECONDS)
    return False
