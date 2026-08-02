"""Inspecting a caller's durable session.

Exposed mainly so the demo can show that the agent remembers a caller between
calls — the profile and transcript here are the evidence for that claim.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from sahaayak_api.browser_auth import BrowserSessionPrincipal, require_browser_session
from sahaayak_common import ConversationTurnLog, Reminder, SavedBenefit, UserSession, get_session

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
    for turn in db.exec(
        select(ConversationTurnLog).where(ConversationTurnLog.session_id == row.id)
    ).all():
        db.delete(turn)
    for saved in db.exec(
        select(SavedBenefit).where(SavedBenefit.session_id == row.id)
    ).all():
        db.delete(saved)
    for reminder in db.exec(
        select(Reminder).where(Reminder.session_id == row.id)
    ).all():
        db.delete(reminder)
    db.delete(row)
    db.commit()


def _require_own_session(session_id: str, principal: BrowserSessionPrincipal) -> None:
    if session_id != principal.session_id:
        # Do not reveal whether another public identifier exists.
        raise HTTPException(status_code=404, detail="No session for this caller")
