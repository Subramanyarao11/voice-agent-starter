"""Private saved-benefit and reminder APIs for anonymous sessions."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from sahaayak_api.browser_auth import BrowserSessionPrincipal, require_browser_session
from sahaayak_api.notifications import check_channel
from sahaayak_common import (
    Benefit,
    ConsentEvent,
    ContactPoint,
    NotificationDelivery,
    Reminder,
    SavedBenefit,
    get_session,
    new_id,
)
from sahaayak_contracts import ConsentStatus, NotificationChannel, VerificationStatusValue

router = APIRouter(prefix="/api/sessions", tags=["saved benefits"])

# Every benefit reminder uses one application template key; the channel and
# locale are resolved from it at send time.
TEMPLATE_KEY = "benefit_reminder"


class SavedBenefitOut(BaseModel):
    id: str
    benefit_id: str
    name: str
    domain: str
    state_code: str | None
    description: str
    source_title: str
    source_document_url: str
    verification_status: str
    saved_at: datetime
    job_metadata: dict = {}


class SaveBenefitRequest(BaseModel):
    benefit_id: str = Field(min_length=1, max_length=160)


class ReminderCreate(BaseModel):
    benefit_id: str
    due_at: datetime
    note: str = Field(default="", max_length=240)
    timezone: str = Field(default="Asia/Kolkata", min_length=1, max_length=64)
    # External channels are accepted here but granted only after the full gate
    # list passes. in_app remains the default and never depends on a provider.
    channel: Literal["in_app", "email", "sms", "whatsapp"] = "in_app"


class ReminderOut(BaseModel):
    id: str
    benefit_id: str
    benefit_name: str
    due_at: datetime
    note: str
    timezone: str
    channel: str
    status: str
    created_at: datetime
    delivered_at: datetime | None
    # Masked only, and null for in-app reminders.
    contact_display_suffix: str = ""
    delivery_status: str = ""


@router.get("/{session_id}/saved-benefits", response_model=list[SavedBenefitOut])
def list_saved_benefits(
    session_id: str,
    db: Session = Depends(get_session),
    principal: BrowserSessionPrincipal = Depends(require_browser_session),
) -> list[SavedBenefitOut]:
    _require_own_session(session_id, principal)
    rows = db.exec(
        select(SavedBenefit)
        .where(SavedBenefit.session_id == principal.session_id)
        .order_by(SavedBenefit.created_at.desc())
    ).all()
    return [item for row in rows if (item := _saved_out(db, row)) is not None]


@router.post(
    "/{session_id}/saved-benefits",
    response_model=SavedBenefitOut,
    status_code=status.HTTP_201_CREATED,
)
def save_benefit(
    session_id: str,
    payload: SaveBenefitRequest,
    db: Session = Depends(get_session),
    principal: BrowserSessionPrincipal = Depends(require_browser_session),
) -> SavedBenefitOut:
    _require_own_session(session_id, principal)
    benefit = _active_benefit(db, payload.benefit_id)
    existing = db.exec(
        select(SavedBenefit).where(
            SavedBenefit.session_id == principal.session_id,
            SavedBenefit.benefit_id == payload.benefit_id,
        )
    ).first()
    if existing is not None:
        return _saved_out(db, existing, benefit=benefit)  # type: ignore[return-value]
    row = SavedBenefit(
        id=new_id("saved"),
        session_id=principal.session_id,
        benefit_id=benefit.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _saved_out(db, row, benefit=benefit)  # type: ignore[return-value]


@router.delete("/{session_id}/saved-benefits/{benefit_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_saved_benefit(
    session_id: str,
    benefit_id: str,
    db: Session = Depends(get_session),
    principal: BrowserSessionPrincipal = Depends(require_browser_session),
) -> None:
    _require_own_session(session_id, principal)
    row = db.exec(
        select(SavedBenefit).where(
            SavedBenefit.session_id == principal.session_id,
            SavedBenefit.benefit_id == benefit_id,
        )
    ).first()
    if row is not None:
        db.delete(row)
        db.commit()


@router.get("/{session_id}/reminders", response_model=list[ReminderOut])
def list_reminders(
    session_id: str,
    db: Session = Depends(get_session),
    principal: BrowserSessionPrincipal = Depends(require_browser_session),
) -> list[ReminderOut]:
    _require_own_session(session_id, principal)
    rows = db.exec(
        select(Reminder)
        .where(Reminder.session_id == principal.session_id)
        .order_by(Reminder.due_at.asc())
    ).all()
    return [_reminder_out(db, row) for row in rows]


@router.post("/{session_id}/reminders", response_model=ReminderOut, status_code=201)
def create_reminder(
    session_id: str,
    payload: ReminderCreate,
    db: Session = Depends(get_session),
    principal: BrowserSessionPrincipal = Depends(require_browser_session),
) -> ReminderOut:
    _require_own_session(session_id, principal)
    benefit = _active_benefit(db, payload.benefit_id)
    saved = db.exec(
        select(SavedBenefit).where(
            SavedBenefit.session_id == principal.session_id,
            SavedBenefit.benefit_id == benefit.id,
        )
    ).first()
    if saved is None:
        raise HTTPException(status_code=400, detail="Save the benefit before setting a reminder")

    due_at = _as_utc(payload.due_at)
    now = datetime.now(UTC)
    if due_at <= now:
        raise HTTPException(status_code=400, detail="Reminder time must be in the future")
    if due_at > now + timedelta(days=365):
        raise HTTPException(
            status_code=400, detail="Reminder time cannot be more than one year away"
        )

    channel = NotificationChannel(payload.channel)
    contact = _verified_contact(db, principal.session_id, channel)
    availability = check_channel(
        db,
        channel=channel,
        contact=contact,
        session_id=principal.session_id,
        template_key=TEMPLATE_KEY,
        locale=principal.language_code,
    )
    if not availability.available:
        # 409 rather than 400: the request is well-formed, the channel is not
        # currently usable. The reason is the caller-facing sentence, so the UI
        # can show it verbatim instead of inventing its own wording.
        raise HTTPException(status_code=409, detail=availability.reason)

    consent_snapshot = _latest_consent(db, contact) if contact is not None else None

    row = Reminder(
        id=new_id("rem"),
        session_id=principal.session_id,
        benefit_id=benefit.id,
        note=payload.note.strip(),
        due_at=due_at,
        timezone=payload.timezone,
        channel=channel.value,
        contact_point_id=contact.id if contact else None,
        template_key=TEMPLATE_KEY if channel is not NotificationChannel.IN_APP else None,
        consent_snapshot_id=consent_snapshot,
        next_attempt_at=due_at if channel is not NotificationChannel.IN_APP else None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _reminder_out(db, row, benefit=benefit)


@router.delete("/{session_id}/reminders/{reminder_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_reminder(
    session_id: str,
    reminder_id: str,
    db: Session = Depends(get_session),
    principal: BrowserSessionPrincipal = Depends(require_browser_session),
) -> None:
    _require_own_session(session_id, principal)
    row = db.exec(
        select(Reminder).where(
            Reminder.id == reminder_id,
            Reminder.session_id == principal.session_id,
        )
    ).first()
    if row is not None and row.status == "scheduled":
        row.status = "cancelled"
        db.add(row)
        db.commit()


def _active_benefit(db: Session, benefit_id: str) -> Benefit:
    benefit = db.get(Benefit, benefit_id)
    if benefit is None or not benefit.is_active:
        raise HTTPException(status_code=404, detail="Benefit not found")
    return benefit


def _saved_out(
    db: Session, row: SavedBenefit, *, benefit: Benefit | None = None
) -> SavedBenefitOut | None:
    benefit = benefit or db.get(Benefit, row.benefit_id)
    if benefit is None:
        return None
    return SavedBenefitOut(
        id=row.id,
        benefit_id=benefit.id,
        name=benefit.name,
        domain=benefit.domain.value,
        state_code=benefit.state_code,
        description=benefit.description,
        source_title=benefit.source_title,
        source_document_url=benefit.source_document_url or benefit.source_url,
        verification_status=benefit.verification_status.value,
        saved_at=row.created_at,
        job_metadata=dict(benefit.job_metadata or {}),
    )


def _reminder_out(
    db: Session, row: Reminder, *, benefit: Benefit | None = None
) -> ReminderOut:
    benefit = benefit or db.get(Benefit, row.benefit_id)
    contact = (
        db.get(ContactPoint, row.contact_point_id) if row.contact_point_id else None
    )
    delivery = (
        db.get(NotificationDelivery, row.last_delivery_id) if row.last_delivery_id else None
    )
    return ReminderOut(
        id=row.id,
        benefit_id=row.benefit_id,
        benefit_name=benefit.name if benefit else row.benefit_id,
        due_at=row.due_at,
        note=row.note,
        timezone=row.timezone,
        channel=row.channel,
        status=row.status,
        created_at=row.created_at,
        delivered_at=row.delivered_at,
        contact_display_suffix=contact.display_suffix if contact else "",
        delivery_status=delivery.status if delivery else "",
    )


def _verified_contact(
    db: Session, session_id: str, channel: NotificationChannel
) -> ContactPoint | None:
    """The usable contact for a channel, if the caller has one.

    Returns None for in-app, which needs no destination, and for a channel with
    no contact at all — the gate check then reports the specific reason.
    """
    if channel is NotificationChannel.IN_APP:
        return None
    return db.exec(
        select(ContactPoint)
        .where(
            ContactPoint.session_id == session_id,
            ContactPoint.channel == channel.value,
            ContactPoint.verification_status == VerificationStatusValue.VERIFIED.value,
        )
        .order_by(ContactPoint.created_at.desc())
    ).first()


def _latest_consent(db: Session, contact: ContactPoint) -> str | None:
    """The opt-in in force right now, recorded on the reminder.

    Pinning it means a later opt-out is visibly a change of mind rather than a
    rewrite of what was agreed when the reminder was set.
    """
    row = db.exec(
        select(ConsentEvent)
        .where(
            ConsentEvent.contact_point_id == contact.id,
            ConsentEvent.status == ConsentStatus.OPTED_IN.value,
        )
        .order_by(ConsentEvent.created_at.desc())
    ).first()
    return row.id if row else None


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _require_own_session(session_id: str, principal: BrowserSessionPrincipal) -> None:
    if session_id != principal.session_id:
        raise HTTPException(status_code=404, detail="No session for this caller")
