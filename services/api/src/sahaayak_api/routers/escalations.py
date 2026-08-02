"""The volunteer queue.

A stub in the sense that no one is paged yet, but the tickets are real rows
written whenever the agent declined to guess. That makes the handoff auditable
now and turns "notify a volunteer" into a delivery detail later.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from sahaayak_common import EscalationTicket, get_session

router = APIRouter(prefix="/api/escalations", tags=["escalations"])


class TicketOut(BaseModel):
    id: str
    session_id: str
    reason: str
    caller_context: dict = Field(default_factory=dict)
    transcript_excerpt: str
    status: str
    created_at: datetime
    resolved_at: datetime | None = None


@router.get("", response_model=list[TicketOut])
def list_tickets(
    status: str = "open", limit: int = 50, db: Session = Depends(get_session)
) -> list[TicketOut]:
    rows = db.exec(
        select(EscalationTicket)
        .where(EscalationTicket.status == status)
        .order_by(EscalationTicket.created_at.desc())
        .limit(limit)
    ).all()
    return [TicketOut.model_validate(row.model_dump()) for row in rows]


@router.post("/{ticket_id}/resolve", response_model=TicketOut)
def resolve_ticket(ticket_id: str, db: Session = Depends(get_session)) -> TicketOut:
    row = db.get(EscalationTicket, ticket_id)
    if row is None:
        raise HTTPException(status_code=404, detail="No such ticket")
    row.status = "resolved"
    row.resolved_at = datetime.now(UTC)
    db.add(row)
    db.commit()
    db.refresh(row)
    return TicketOut.model_validate(row.model_dump())
