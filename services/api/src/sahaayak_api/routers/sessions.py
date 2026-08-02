"""Inspecting a caller's durable session.

Exposed mainly so the demo can show that the agent remembers a caller between
calls — the profile and transcript here are the evidence for that claim.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from sahaayak_common import ConversationTurnLog, UserSession, get_session

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


class TurnOut(BaseModel):
    turn_index: int
    role: str
    text: str
    created_at: datetime


class SessionOut(BaseModel):
    id: str
    phone_or_session_id: str
    state_code: str
    language_code: str
    profile: dict = Field(default_factory=dict)
    conversation_state: dict = Field(default_factory=dict)
    matched_benefit_ids: list[str] = Field(default_factory=list)
    turn_count: int
    created_at: datetime
    last_contact_at: datetime


@router.get("/{caller_id}", response_model=SessionOut)
def get_session_for_caller(
    caller_id: str, db: Session = Depends(get_session)
) -> SessionOut:
    row = db.exec(
        select(UserSession).where(UserSession.phone_or_session_id == caller_id)
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="No session for this caller")
    return SessionOut.model_validate(row.model_dump())


@router.get("/{caller_id}/transcript", response_model=list[TurnOut])
def get_transcript(
    caller_id: str, limit: int = 100, db: Session = Depends(get_session)
) -> list[TurnOut]:
    session_row = db.exec(
        select(UserSession).where(UserSession.phone_or_session_id == caller_id)
    ).first()
    if session_row is None:
        raise HTTPException(status_code=404, detail="No session for this caller")

    rows = db.exec(
        select(ConversationTurnLog)
        .where(ConversationTurnLog.session_id == session_row.id)
        .order_by(ConversationTurnLog.created_at)
        .limit(limit)
    ).all()
    return [TurnOut.model_validate(row.model_dump()) for row in rows]


@router.delete("/{caller_id}", status_code=204)
def reset_session(caller_id: str, db: Session = Depends(get_session)) -> None:
    """Clear a caller's memory.

    Needed for demos and re-testing, and it is also the honest answer to
    "delete what you know about me" for a service holding income and caste.
    """
    row = db.exec(
        select(UserSession).where(UserSession.phone_or_session_id == caller_id)
    ).first()
    if row is None:
        return
    for turn in db.exec(
        select(ConversationTurnLog).where(ConversationTurnLog.session_id == row.id)
    ).all():
        db.delete(turn)
    db.delete(row)
    db.commit()
