"""Contact points, verification, and consent for anonymous sessions.

Three rules shape this router.

A destination never comes back out. Responses carry a masked suffix and nothing
else, so a stolen session token yields "******3210" rather than a phone number.

Verification and consent are separate steps because they answer separate
questions. Verification proves the destination reaches the person who typed it.
Consent records that they agreed to be messaged there, and for what. A form
that treats typing a number as agreement is how a service ends up sending
unsolicited SMS to people who mistyped a digit.

The verification challenge is never allowed to fall back to in-app delivery.
Everything else in this system degrades to in-app when a provider is down, but
a code the caller cannot read verifies nothing, so an unavailable channel is
reported as unavailable.
"""

from __future__ import annotations

import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from sahaayak_api.browser_auth import BrowserSessionPrincipal, require_browser_session
from sahaayak_api.notifications import (
    check_channel,
    create_delivery,
    dispatch,
    get_provider,
    resolve,
)
from sahaayak_api.notifications.dispatcher import (
    GATE_CONTACT_MISSING,
    GATE_MESSAGES,
    GATE_PROVIDER_NOT_CONFIGURED,
)
from sahaayak_api.rate_limit import apply_rate_limit_headers, enforce_rate_limit
from sahaayak_api.telemetry import record_telemetry
from sahaayak_common import (
    ConsentEvent,
    ContactPoint,
    destination_hash,
    encrypt_destination,
    get_logger,
    get_session,
    is_valid_destination,
    mask_destination,
    new_id,
    normalize_destination,
    settings,
)
from sahaayak_contracts import (
    ConsentPurpose,
    ConsentStatus,
    NotificationChannel,
    VerificationStatusValue,
)

log = get_logger(__name__)

router = APIRouter(prefix="/api/sessions", tags=["contact points"])

# Bump when the consent copy shown in the UI changes, so a stored event records
# what that caller actually agreed to rather than today's wording.
CONSENT_TEXT_VERSION = "2026-08-03.v1"

ExternalChannel = Literal["email", "sms", "whatsapp"]


class ContactPointCreate(BaseModel):
    channel: ExternalChannel
    destination: str = Field(min_length=3, max_length=254)
    locale: str = Field(default="en", max_length=8)
    # Explicit, and required. There is no default that means "yes": the caller
    # ticks a box describing what will be sent and how to stop it.
    consent: bool = False
    purpose: Literal["reminders", "support"] = "reminders"


class ContactPointOut(BaseModel):
    id: str
    channel: str
    # Masked only. The plaintext destination is never returned by any route.
    display_suffix: str
    locale: str
    verification_status: str
    consent_status: str
    consent_purpose: str
    verified_at: datetime | None
    created_at: datetime


class VerifyRequest(BaseModel):
    code: str = Field(min_length=4, max_length=12)


class ChannelStatusOut(BaseModel):
    channel: str
    available: bool
    gate: str
    # Always populated when unavailable. A disabled control with no
    # explanation is not an accessible interface.
    reason: str
    contact_point_id: str | None = None
    display_suffix: str = ""


@router.get("/{session_id}/contact-points", response_model=list[ContactPointOut])
def list_contact_points(
    session_id: str,
    db: Session = Depends(get_session),
    principal: BrowserSessionPrincipal = Depends(require_browser_session),
) -> list[ContactPointOut]:
    _require_own_session(session_id, principal)
    rows = db.exec(
        select(ContactPoint)
        .where(ContactPoint.session_id == principal.session_id)
        .order_by(ContactPoint.created_at.desc())
    ).all()
    return [_contact_out(row) for row in rows]


@router.post(
    "/{session_id}/contact-points",
    response_model=ContactPointOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_contact_point(
    session_id: str,
    payload: ContactPointCreate,
    request: Request,
    http_response: Response,
    db: Session = Depends(get_session),
    principal: BrowserSessionPrincipal = Depends(require_browser_session),
) -> ContactPointOut:
    """Register a destination and send it a verification challenge."""
    _require_own_session(session_id, principal)
    decision = await enforce_rate_limit(
        request, session_id=principal.session_id, bucket="contact_verify"
    )
    apply_rate_limit_headers(http_response, decision)

    channel = NotificationChannel(payload.channel)
    destination = normalize_destination(channel.value, payload.destination)

    if not is_valid_destination(channel.value, destination):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Enter a valid email address."
                if channel is NotificationChannel.EMAIL
                else "Enter the number in international format, for example +919876543210."
            ),
        )
    if not payload.consent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Agree to receive messages on this channel before adding it.",
        )

    # A challenge must actually reach the caller, so no in-app fallback here.
    provider = get_provider(channel, allow_fallback=False)
    if provider is None or not provider.available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=GATE_MESSAGES[GATE_PROVIDER_NOT_CONFIGURED],
        )

    digest = destination_hash(channel.value, destination)
    existing = db.exec(
        select(ContactPoint).where(
            ContactPoint.session_id == principal.session_id,
            ContactPoint.channel == channel.value,
            ContactPoint.destination_hash == digest,
        )
    ).first()

    now = datetime.now(UTC)
    code = _new_code()
    contact = existing or ContactPoint(
        id=new_id("cp"),
        session_id=principal.session_id,
        channel=channel.value,
        destination_ciphertext=encrypt_destination(destination),
        destination_hash=digest,
        display_suffix=mask_destination(channel.value, destination),
    )
    # Re-adding a revoked contact restarts verification rather than silently
    # reinstating a destination the caller previously removed.
    contact.destination_ciphertext = encrypt_destination(destination)
    contact.display_suffix = mask_destination(channel.value, destination)
    contact.locale = payload.locale or principal.language_code
    contact.verification_status = VerificationStatusValue.PENDING.value
    contact.verification_provider = provider.name
    contact.verification_code_hash = _hash_code(code)
    contact.verification_expires_at = now + timedelta(
        seconds=settings.contact_verification_code_ttl_seconds
    )
    contact.verification_attempts = 0
    contact.verified_at = None
    contact.consent_status = ConsentStatus.OPTED_IN.value
    contact.consent_purpose = payload.purpose
    contact.consent_source = "browser"
    contact.consent_at = now
    contact.opted_out_at = None
    contact.updated_at = now
    db.add(contact)
    db.flush()

    _record_consent(
        db,
        contact=contact,
        status=ConsentStatus.OPTED_IN,
        purpose=ConsentPurpose(payload.purpose),
        source="browser",
    )

    await _send_challenge(db, contact=contact, provider=provider, code=code)
    db.commit()
    db.refresh(contact)

    record_telemetry(
        event_type="notification",
        route="/api/sessions/{session_id}/contact-points",
        method="POST",
        surface="text",
        language_code=contact.locale,
        outcome="challenge_sent",
        safe_metadata={"channel": channel.value, "provider": provider.name},
    )
    return _contact_out(contact)


@router.post(
    "/{session_id}/contact-points/{contact_id}/verify", response_model=ContactPointOut
)
async def verify_contact_point(
    session_id: str,
    contact_id: str,
    payload: VerifyRequest,
    request: Request,
    http_response: Response,
    db: Session = Depends(get_session),
    principal: BrowserSessionPrincipal = Depends(require_browser_session),
) -> ContactPointOut:
    _require_own_session(session_id, principal)
    decision = await enforce_rate_limit(
        request, session_id=principal.session_id, bucket="contact_verify"
    )
    apply_rate_limit_headers(http_response, decision)

    contact = _own_contact(db, contact_id, principal)
    now = datetime.now(UTC)

    if contact.verification_status == VerificationStatusValue.VERIFIED.value:
        return _contact_out(contact)

    if (
        not contact.verification_code_hash
        or contact.verification_expires_at is None
        or _as_utc(contact.verification_expires_at) <= now
    ):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="That code has expired. Request a new one.",
        )

    # Counted before comparison, so a client that abandons the connection
    # mid-request still spends the attempt.
    contact.verification_attempts += 1
    if contact.verification_attempts > settings.contact_verification_max_attempts:
        contact.verification_code_hash = None
        contact.updated_at = now
        db.add(contact)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many incorrect codes. Request a new one.",
        )

    # Constant-time: a timing difference here leaks the code one digit at a
    # time, and the code is the only thing standing between a session and
    # someone else's phone number.
    if not hmac.compare_digest(contact.verification_code_hash, _hash_code(payload.code)):
        db.add(contact)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="That code is not correct."
        )

    contact.verification_status = VerificationStatusValue.VERIFIED.value
    contact.verified_at = now
    # Discarded on success: it has served its purpose and keeping it only
    # creates something to steal.
    contact.verification_code_hash = None
    contact.verification_expires_at = None
    contact.updated_at = now
    db.add(contact)
    db.commit()
    db.refresh(contact)

    log.info(
        "contact_point_verified",
        contact_point_id=contact.id,
        channel=contact.channel,
        session_id=principal.session_id,
    )
    record_telemetry(
        event_type="notification",
        route="/api/sessions/{session_id}/contact-points/{contact_id}/verify",
        method="POST",
        surface="text",
        outcome="verified",
        safe_metadata={"channel": contact.channel},
    )
    return _contact_out(contact)


@router.delete(
    "/{session_id}/contact-points/{contact_id}", status_code=status.HTTP_204_NO_CONTENT
)
def revoke_contact_point(
    session_id: str,
    contact_id: str,
    db: Session = Depends(get_session),
    principal: BrowserSessionPrincipal = Depends(require_browser_session),
) -> None:
    """Revoke a contact and stop future delivery to it.

    The row is kept rather than deleted, and an opt-out event is appended. A
    deleted row would lose the evidence that the caller asked to stop, which is
    exactly the evidence a complaint about unwanted messages turns on.
    """
    _require_own_session(session_id, principal)
    contact = _own_contact(db, contact_id, principal)

    now = datetime.now(UTC)
    contact.verification_status = VerificationStatusValue.REVOKED.value
    contact.consent_status = ConsentStatus.OPTED_OUT.value
    contact.opted_out_at = now
    contact.verification_code_hash = None
    contact.verification_expires_at = None
    contact.updated_at = now
    db.add(contact)

    _record_consent(
        db,
        contact=contact,
        status=ConsentStatus.OPTED_OUT,
        purpose=ConsentPurpose(contact.consent_purpose or "reminders"),
        source="browser",
    )
    db.commit()

    log.info(
        "contact_point_revoked", contact_point_id=contact.id, channel=contact.channel
    )


@router.get("/{session_id}/notification-channels", response_model=list[ChannelStatusOut])
def list_notification_channels(
    session_id: str,
    template_key: str = "benefit_reminder",
    db: Session = Depends(get_session),
    principal: BrowserSessionPrincipal = Depends(require_browser_session),
) -> list[ChannelStatusOut]:
    """Which channels this caller can use, and why the others are unavailable.

    Exists so the reminder form can explain itself. A channel the caller cannot
    use should say what would make it usable, not present a dead control.
    """
    _require_own_session(session_id, principal)
    contacts = {
        NotificationChannel(row.channel): row
        for row in db.exec(
            select(ContactPoint).where(
                ContactPoint.session_id == principal.session_id,
                ContactPoint.verification_status != VerificationStatusValue.REVOKED.value,
            )
        ).all()
        if row.channel in {item.value for item in NotificationChannel}
    }

    results: list[ChannelStatusOut] = []
    for channel in NotificationChannel:
        contact = contacts.get(channel)
        availability = check_channel(
            db,
            channel=channel,
            contact=contact,
            session_id=principal.session_id,
            template_key=template_key,
            locale=principal.language_code,
        )
        results.append(
            ChannelStatusOut(
                channel=channel.value,
                available=availability.available,
                gate=str(availability.gate),
                reason=availability.reason,
                contact_point_id=contact.id if contact else None,
                display_suffix=contact.display_suffix if contact else "",
            )
        )
    return results


# --- Helpers --------------------------------------------------------------


async def _send_challenge(
    db: Session, *, contact: ContactPoint, provider, code: str
) -> None:
    """Deliver a verification code.

    The code is passed as a template variable and never written to a log, a
    telemetry row, a trace attribute, or the delivery record.
    """
    channel = NotificationChannel(contact.channel)
    delivery = create_delivery(
        db,
        channel=channel,
        session_id=contact.session_id,
        template_key="contact_verification",
        locale=contact.locale or "en",
        contact_point_id=contact.id,
        safe_metadata={"purpose": "verification"},
    )
    template = resolve(
        db,
        template_key="contact_verification",
        channel=channel,
        locale=contact.locale or "en",
    )
    result = await dispatch(
        db,
        provider=provider,
        contact=contact,
        delivery=delivery,
        template=template,
        variables={
            "code": code,
            "minutes": str(max(1, settings.contact_verification_code_ttl_seconds // 60)),
        },
    )
    if not result.accepted:
        # Rolled back deliberately: leaving a pending contact whose code was
        # never delivered would strand the caller waiting for a message that
        # is not coming.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not send the verification message. Try again shortly.",
        )


def _record_consent(
    db: Session,
    *,
    contact: ContactPoint,
    status: ConsentStatus,
    purpose: ConsentPurpose,
    source: str,
) -> ConsentEvent:
    event = ConsentEvent(
        id=new_id("ce"),
        session_id=contact.session_id,
        contact_point_id=contact.id,
        channel=contact.channel,
        purpose=purpose.value,
        status=status.value,
        source=source,
        consent_text_version=CONSENT_TEXT_VERSION,
        actor="caller",
    )
    db.add(event)
    db.flush()
    return event


def _new_code() -> str:
    """A six-digit numeric challenge.

    Numeric because it is read aloud from an SMS and typed by someone who may
    not be comfortable with a keyboard; six digits because the attempt limit,
    not the code length, is what makes guessing infeasible.
    """
    return f"{secrets.randbelow(1_000_000):06d}"


def _hash_code(code: str) -> str:
    """Keyed hash of a challenge code. The code itself is never persisted."""
    return destination_hash("verification-code", code.strip())


def _contact_out(row: ContactPoint) -> ContactPointOut:
    return ContactPointOut(
        id=row.id,
        channel=row.channel,
        display_suffix=row.display_suffix,
        locale=row.locale,
        verification_status=row.verification_status,
        consent_status=row.consent_status,
        consent_purpose=row.consent_purpose,
        verified_at=row.verified_at,
        created_at=row.created_at,
    )


def _own_contact(
    db: Session, contact_id: str, principal: BrowserSessionPrincipal
) -> ContactPoint:
    row = db.exec(
        select(ContactPoint).where(
            ContactPoint.id == contact_id,
            ContactPoint.session_id == principal.session_id,
        )
    ).first()
    if row is None:
        # Same response whether it belongs to someone else or does not exist,
        # so the API cannot be used to probe for other sessions' contacts.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=GATE_MESSAGES[GATE_CONTACT_MISSING]
        )
    return row


def _require_own_session(session_id: str, principal: BrowserSessionPrincipal) -> None:
    if session_id != principal.session_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="This session is not yours"
        )


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)
