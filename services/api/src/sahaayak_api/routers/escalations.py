"""Auditable operator handoffs.

Tickets are created by the agent, then owned and advanced by authenticated
workforce users. Claiming is an atomic state transition so two operators do
not both believe they own the same caller. Notes and routing changes are
durable rows-in-JSON with an audit event for every mutation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import update
from sqlmodel import Session, select

from sahaayak_api.admin_auth import AdminPrincipal, require_admin_role
from sahaayak_api.telemetry import make_audit_event
from sahaayak_common import EscalationTicket, get_session, new_id

router = APIRouter(prefix="/api/escalations", tags=["escalations"])

TicketStatus = Literal["open", "claimed", "resolved"]
ResolutionCode = Literal["answered", "referred", "no_action", "duplicate", "unreachable"]


class TicketNoteOut(BaseModel):
    id: str
    actor_id: str
    actor_role: str
    text: str
    created_at: datetime


class TicketOut(BaseModel):
    id: str
    session_id: str
    reason: str
    caller_context: dict = Field(default_factory=dict)
    transcript_excerpt: str
    status: str
    assigned_to: str | None = None
    claimed_at: datetime | None = None
    sla_due_at: datetime | None = None
    sla_breached: bool = False
    department: str
    routing_location: str
    routing_source: str
    operator_notes: list[TicketNoteOut] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime | None = None
    resolved_at: datetime | None = None
    resolved_by: str | None = None
    resolution_code: str | None = None
    resolution_note: str = ""


class AddNoteRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2_000)


class RouteRequest(BaseModel):
    department: str = Field(min_length=2, max_length=160)
    routing_location: str = Field(default="", max_length=120)


class ResolveRequest(BaseModel):
    resolution_code: ResolutionCode = "answered"
    note: str = Field(default="", max_length=2_000)


@router.get("", response_model=list[TicketOut])
def list_tickets(
    status: Literal["open", "claimed", "resolved", "active", "all"] = "open",
    limit: int = 50,
    department: str | None = None,
    overdue_only: bool = False,
    db: Session = Depends(get_session),
    principal: AdminPrincipal = Depends(
        require_admin_role("observer", "operator", "reviewer", "admin")
    ),
) -> list[TicketOut]:
    limit = max(1, min(limit, 100))
    statement = select(EscalationTicket)
    if status == "active":
        statement = statement.where(EscalationTicket.status.in_(["open", "claimed"]))
    elif status != "all":
        statement = statement.where(EscalationTicket.status == status)
    if department:
        statement = statement.where(EscalationTicket.department == department[:160])
    rows = db.exec(statement.limit(limit)).all()
    now = datetime.now(UTC)
    if overdue_only:
        rows = [row for row in rows if _sla_breached(row, now)]
    # SLA-first ordering makes the queue actionable even when a large number
    # of tickets arrived at the same time.
    rows.sort(key=lambda row: _queue_sort_key(row, now))
    return [_ticket_out(row, principal, now=now) for row in rows]


@router.post("/{ticket_id}/claim", response_model=TicketOut)
def claim_ticket(
    ticket_id: str,
    db: Session = Depends(get_session),
    principal: AdminPrincipal = Depends(require_admin_role("operator", "admin")),
) -> TicketOut:
    now = datetime.now(UTC)
    result = db.execute(
        update(EscalationTicket)
        .where(
            EscalationTicket.id == ticket_id,
            EscalationTicket.status == "open",
        )
        .values(
            status="claimed",
            assigned_to=principal.actor_id,
            claimed_at=now,
            updated_at=now,
        )
    )
    if result.rowcount != 1:
        row = db.get(EscalationTicket, ticket_id)
        if row is None:
            raise HTTPException(status_code=404, detail="No such ticket")
        if row.status == "claimed" and row.assigned_to == principal.actor_id:
            return _ticket_out(row, principal, now=now)
        raise HTTPException(status_code=409, detail="Ticket is already claimed or resolved")

    row = db.get(EscalationTicket, ticket_id)
    if row is None:  # pragma: no cover - the update already matched the row
        raise HTTPException(status_code=404, detail="No such ticket")
    db.add(
        make_audit_event(
            principal=principal,
            action="escalation.claim",
            target_type="escalation_ticket",
            target_id=row.id,
            reason="Claimed from the operator queue",
            safe_before={"status": "open", "assigned": False},
            safe_after={"status": row.status, "assigned": True},
        )
    )
    db.commit()
    db.refresh(row)
    return _ticket_out(row, principal, now=now)


@router.post("/{ticket_id}/notes", response_model=TicketOut)
def add_ticket_note(
    ticket_id: str,
    payload: AddNoteRequest,
    db: Session = Depends(get_session),
    principal: AdminPrincipal = Depends(require_admin_role("operator", "admin")),
) -> TicketOut:
    row = _get_ticket(db, ticket_id)
    if row.status == "resolved":
        raise HTTPException(
            status_code=409,
            detail="Resolved tickets cannot receive operational notes",
        )

    now = datetime.now(UTC)
    note = {
        "id": new_id("note"),
        "actor_id": principal.actor_id[:120],
        "actor_role": principal.role[:32],
        "text": payload.text.strip(),
        "created_at": now.isoformat(),
    }
    row.operator_notes = [*row.operator_notes, note]
    row.updated_at = now
    db.add(row)
    db.add(
        make_audit_event(
            principal=principal,
            action="escalation.note.add",
            target_type="escalation_ticket",
            target_id=row.id,
            reason="Added an operator note",
            safe_before={"note_count": len(row.operator_notes) - 1},
            safe_after={"note_count": len(row.operator_notes)},
        )
    )
    db.commit()
    db.refresh(row)
    return _ticket_out(row, principal, now=now)


@router.post("/{ticket_id}/route", response_model=TicketOut)
def route_ticket(
    ticket_id: str,
    payload: RouteRequest,
    db: Session = Depends(get_session),
    principal: AdminPrincipal = Depends(require_admin_role("operator", "admin")),
) -> TicketOut:
    row = _get_ticket(db, ticket_id)
    if row.status == "resolved":
        raise HTTPException(status_code=409, detail="Resolved tickets cannot be rerouted")

    now = datetime.now(UTC)
    previous_routing_source = row.routing_source
    previous_location_present = bool(row.routing_location)
    row.department = payload.department.strip()
    row.routing_location = payload.routing_location.strip()
    row.routing_source = "operator_override"
    row.updated_at = now
    db.add(row)
    db.add(
        make_audit_event(
            principal=principal,
            action="escalation.route.update",
            target_type="escalation_ticket",
            target_id=row.id,
            reason="Updated the department routing target",
            safe_before={
                "routing_source": previous_routing_source,
                "location_present": previous_location_present,
            },
            safe_after={
                "routing_source": row.routing_source,
                "location_present": bool(row.routing_location),
            },
        )
    )
    db.commit()
    db.refresh(row)
    return _ticket_out(row, principal, now=now)


@router.post("/{ticket_id}/resolve", response_model=TicketOut)
def resolve_ticket(
    ticket_id: str,
    payload: ResolveRequest | None = None,
    db: Session = Depends(get_session),
    principal: AdminPrincipal = Depends(require_admin_role("operator", "admin")),
) -> TicketOut:
    row = _get_ticket(db, ticket_id)
    if row.status == "resolved":
        return _ticket_out(row, principal)

    payload = payload or ResolveRequest()
    now = datetime.now(UTC)
    before = {
        "status": row.status,
        "assigned": bool(row.assigned_to),
        "resolved": row.resolved_at is not None,
    }
    row.status = "resolved"
    row.resolved_at = now
    row.resolved_by = principal.actor_id
    row.resolution_code = payload.resolution_code
    row.resolution_note = payload.note.strip()
    row.updated_at = now
    db.add(row)
    db.add(
        make_audit_event(
            principal=principal,
            action="escalation.resolve",
            target_type="escalation_ticket",
            target_id=row.id,
            reason="Resolved from the admin operations queue",
            safe_before=before,
            safe_after={
                "status": row.status,
                "assigned": bool(row.assigned_to),
                "resolution_code": row.resolution_code,
            },
        )
    )
    db.commit()
    db.refresh(row)
    return _ticket_out(row, principal, now=now)


def _get_ticket(db: Session, ticket_id: str) -> EscalationTicket:
    row = db.get(EscalationTicket, ticket_id)
    if row is None:
        raise HTTPException(status_code=404, detail="No such ticket")
    return row


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _sla_breached(row: EscalationTicket, now: datetime | None = None) -> bool:
    return (
        row.status != "resolved"
        and row.sla_due_at is not None
        and _aware(row.sla_due_at) < _aware(now or datetime.now(UTC))
    )


def _queue_sort_key(row: EscalationTicket, now: datetime) -> tuple[int, datetime, datetime]:
    due = _aware(row.sla_due_at) if row.sla_due_at else datetime.max.replace(tzinfo=UTC)
    created = _aware(row.created_at)
    return (0 if _sla_breached(row, now) else 1, due, created)


def _ticket_out(
    row: EscalationTicket,
    principal: AdminPrincipal,
    *,
    now: datetime | None = None,
) -> TicketOut:
    privileged = principal.role in {"operator", "admin"}
    notes = (
        [TicketNoteOut.model_validate(note) for note in row.operator_notes]
        if privileged
        else []
    )
    return TicketOut(
        id=row.id,
        session_id=row.session_id,
        reason=row.reason,
        caller_context=row.caller_context if privileged else {},
        transcript_excerpt=row.transcript_excerpt if privileged else "",
        status=row.status,
        assigned_to=row.assigned_to if privileged else None,
        claimed_at=row.claimed_at if privileged else None,
        sla_due_at=row.sla_due_at,
        sla_breached=_sla_breached(row, now),
        department=row.department,
        routing_location=row.routing_location if privileged else "",
        routing_source=row.routing_source,
        operator_notes=notes,
        created_at=row.created_at,
        updated_at=row.updated_at,
        resolved_at=row.resolved_at,
        resolved_by=row.resolved_by if privileged else None,
        resolution_code=row.resolution_code,
        resolution_note=row.resolution_note if privileged else "",
    )
