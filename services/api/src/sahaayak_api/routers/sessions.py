"""Inspecting a caller's durable session.

Exposed mainly so the demo can show that the agent remembers a caller between
calls — the profile and transcript here are the evidence for that claim.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import delete, update
from sqlmodel import Session, select

from sahaayak_api.browser_auth import BrowserSessionPrincipal, require_browser_session
from sahaayak_common import (
    ApplicationCase,
    ApplicationFieldValue,
    ApplicationOutcomeFeedback,
    ApplicationRequirement,
    ApplicationStatusEvent,
    ApplicationTask,
    AssistanceAction,
    AssistanceConsent,
    AssistanceSession,
    BenefitIssueReport,
    CallSession,
    ConsentEvent,
    ContactPoint,
    ConversationTurnLog,
    EscalationTicket,
    GuestMigration,
    MemberRecommendation,
    NotificationDelivery,
    Reminder,
    SavedBenefit,
    UserSession,
    get_session,
)

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


class TurnOut(BaseModel):
    turn_index: int
    role: str
    text: str
    created_at: datetime


class SessionOut(BaseModel):
    id: str
    state_code: str
    language_code: str
    profile: dict = Field(default_factory=dict)
    conversation_state: dict = Field(default_factory=dict)
    matched_benefit_ids: list[str] = Field(default_factory=list)
    turn_count: int
    created_at: datetime
    last_contact_at: datetime


@router.get("/{session_id}", response_model=SessionOut)
def get_session_for_caller(
    session_id: str,
    db: Session = Depends(get_session),
    principal: BrowserSessionPrincipal = Depends(require_browser_session),
) -> SessionOut:
    _require_own_session(session_id, principal)
    row = db.get(UserSession, principal.session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="No session for this caller")
    return SessionOut.model_validate(row.model_dump())


@router.get("/{session_id}/transcript", response_model=list[TurnOut])
def get_transcript(
    session_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_session),
    principal: BrowserSessionPrincipal = Depends(require_browser_session),
) -> list[TurnOut]:
    _require_own_session(session_id, principal)
    session_row = db.get(UserSession, principal.session_id)
    if session_row is None:
        raise HTTPException(status_code=404, detail="No session for this caller")

    rows = db.exec(
        select(ConversationTurnLog)
        .where(ConversationTurnLog.session_id == session_row.id)
        .order_by(ConversationTurnLog.created_at)
        .limit(limit)
    ).all()
    return [TurnOut.model_validate(row.model_dump()) for row in rows]


@router.delete("/{session_id}", status_code=204)
def reset_session(
    session_id: str,
    db: Session = Depends(get_session),
    principal: BrowserSessionPrincipal = Depends(require_browser_session),
) -> None:
    """Clear a caller's memory.

    Needed for demos and re-testing, and it is also the honest answer to
    "delete what you know about me" for a service holding income and caste.
    """
    _require_own_session(session_id, principal)
    row = db.get(UserSession, principal.session_id)
    if row is None:
        return

    # This endpoint is a user-requested deletion, not a soft UI reset. Delete
    # every guest-owned row in dependency order so old escalations, contact
    # points, application workspaces, and delivery records cannot prevent the
    # session itself from being removed.
    case_ids = list(
        db.exec(select(ApplicationCase.id).where(ApplicationCase.session_id == row.id)).all()
    )
    if case_ids:
        db.exec(
            update(MemberRecommendation)
            .where(MemberRecommendation.linked_application_case_id.in_(case_ids))
            .values(linked_application_case_id=None)
        )
        db.exec(
            delete(ApplicationFieldValue).where(
                ApplicationFieldValue.application_case_id.in_(case_ids)
            )
        )
        db.exec(
            delete(ApplicationOutcomeFeedback).where(
                ApplicationOutcomeFeedback.application_case_id.in_(case_ids)
            )
        )
        db.exec(
            delete(ApplicationRequirement).where(
                ApplicationRequirement.application_case_id.in_(case_ids)
            )
        )
        db.exec(
            delete(ApplicationStatusEvent).where(
                ApplicationStatusEvent.application_case_id.in_(case_ids)
            )
        )

    task_ids = list(
        db.exec(select(ApplicationTask.id).where(ApplicationTask.session_id == row.id)).all()
    )
    if task_ids:
        db.exec(
            update(ApplicationRequirement)
            .where(ApplicationRequirement.task_id.in_(task_ids))
            .values(task_id=None)
        )
    db.exec(delete(ApplicationTask).where(ApplicationTask.session_id == row.id))
    if case_ids:
        case_reminder_ids = list(
            db.exec(
                select(Reminder.id).where(Reminder.application_case_id.in_(case_ids))
            ).all()
        )
        if case_reminder_ids:
            db.exec(
                delete(NotificationDelivery).where(
                    NotificationDelivery.reminder_id.in_(case_reminder_ids)
                )
            )
        db.exec(delete(Reminder).where(Reminder.application_case_id.in_(case_ids)))
        db.exec(delete(ApplicationCase).where(ApplicationCase.id.in_(case_ids)))

    assistance_ids = list(
        db.exec(
            select(AssistanceSession.id).where(
                AssistanceSession.citizen_session_id == row.id
            )
        ).all()
    )
    if assistance_ids:
        db.exec(
            delete(AssistanceAction).where(
                AssistanceAction.assistance_session_id.in_(assistance_ids)
            )
        )
        db.exec(
            delete(AssistanceConsent).where(
                AssistanceConsent.assistance_session_id.in_(assistance_ids)
            )
        )
        db.exec(delete(AssistanceSession).where(AssistanceSession.id.in_(assistance_ids)))

    contact_ids = list(
        db.exec(select(ContactPoint.id).where(ContactPoint.session_id == row.id)).all()
    )
    db.exec(delete(ConsentEvent).where(ConsentEvent.session_id == row.id))
    db.exec(delete(NotificationDelivery).where(NotificationDelivery.session_id == row.id))
    db.exec(delete(Reminder).where(Reminder.session_id == row.id))
    if contact_ids:
        db.exec(
            delete(ConsentEvent).where(ConsentEvent.contact_point_id.in_(contact_ids))
        )
    db.exec(delete(ContactPoint).where(ContactPoint.session_id == row.id))

    saved_ids = list(
        db.exec(select(SavedBenefit.id).where(SavedBenefit.session_id == row.id)).all()
    )
    if saved_ids:
        db.exec(
            update(MemberRecommendation)
            .where(MemberRecommendation.linked_saved_benefit_id.in_(saved_ids))
            .values(linked_saved_benefit_id=None)
        )

    for model in (
        BenefitIssueReport,
        CallSession,
        ConversationTurnLog,
        EscalationTicket,
        SavedBenefit,
    ):
        db.exec(delete(model).where(model.session_id == row.id))
    db.exec(delete(GuestMigration).where(GuestMigration.guest_session_id == row.id))

    db.delete(row)
    db.commit()


def _require_own_session(session_id: str, principal: BrowserSessionPrincipal) -> None:
    if session_id != principal.session_id:
        # Do not reveal whether another public identifier exists.
        raise HTTPException(status_code=404, detail="No session for this caller")
