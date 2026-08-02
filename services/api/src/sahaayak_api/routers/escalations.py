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

from sahaayak_api.admin_auth import AdminPrincipal, require_admin_role
from sahaayak_api.telemetry import make_audit_event
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
    status: str = "open",
    limit: int = 50,
    db: Session = Depends(get_session),
    principal: AdminPrincipal = Depends(
        require_admin_role("observer", "operator", "reviewer", "admin")
    ),
) -> list[TicketOut]:
    limit = max(1, min(limit, 100))
    rows = db.exec(
        select(EscalationTicket)
        .where(EscalationTicket.status == status)
        .order_by(EscalationTicket.created_at.desc())
        .limit(limit)
    ).all()
    return [_ticket_out(row, principal) for row in rows]


@router.post("/{ticket_id}/resolve", response_model=TicketOut)
def resolve_ticket(
    ticket_id: str,
    db: Session = Depends(get_session),
    principal: AdminPrincipal = Depends(require_admin_role("operator", "admin")),
) -> TicketOut:
    row = db.get(EscalationTicket, ticket_id)
    if row is None:
        raise HTTPException(status_code=404, detail="No such ticket")
    before = {"status": row.status, "resolved": row.resolved_at is not None}
    row.status = "resolved"
    row.resolved_at = datetime.now(UTC)
    db.add(row)
    db.add(
        make_audit_event(
            principal=principal,
            action="escalation.resolve",
            target_type="escalation_ticket",
            target_id=row.id,
            reason="Resolved from the admin operations queue",
            safe_before=before,
            safe_after={"status": row.status, "resolved": True},
        )
    )
    db.commit()
    db.refresh(row)
    return _ticket_out(row, principal)


def _ticket_out(row: EscalationTicket, principal: AdminPrincipal) -> TicketOut:
    if principal.role in {"operator", "admin"}:
        return TicketOut.model_validate(row.model_dump())
    return TicketOut(
        id=row.id,
        session_id=row.session_id,
        reason=row.reason,
        caller_context={},
        transcript_excerpt="",
        status=row.status,
        created_at=row.created_at,
        resolved_at=row.resolved_at,
    )
