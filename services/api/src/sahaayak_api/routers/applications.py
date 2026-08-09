"""Citizen application journeys and manually reported status evidence."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlmodel import Session, select

from sahaayak_api.browser_auth import BrowserSessionPrincipal, require_browser_session
from sahaayak_api.rate_limit import apply_rate_limit_headers, enforce_rate_limit
from sahaayak_api.routers.saved_benefits import (
    ApplicationTaskOut,
    ensure_application_tasks,
    task_out,
)
from sahaayak_common import (
    ApplicationCase,
    ApplicationDataEncryptionUnavailable,
    ApplicationStatusEvent,
    ApplicationTask,
    Benefit,
    benefit_snapshot,
    encrypt_reference,
    feature_flag_enabled,
    get_session,
    mask_reference,
    new_id,
    normalize_reference,
    reference_hash,
)
from sahaayak_contracts import VerificationStatus

router = APIRouter(prefix="/api/sessions", tags=["applications"])

ApplicationStatus = Literal[
    "portal_opened",
    "submitted",
    "acknowledged",
    "under_review",
    "action_required",
    "approved",
    "delivered",
    "rejected",
    "withdrawn",
]

_TERMINAL_STATUSES = {"delivered", "rejected", "withdrawn"}
_ALLOWED_NEXT: dict[str, set[str]] = {
    "draft": {"portal_opened", "submitted", "withdrawn"},
    "portal_opened": {"submitted", "withdrawn"},
    "submitted": {
        "acknowledged",
        "under_review",
        "action_required",
        "approved",
        "rejected",
        "withdrawn",
    },
    "acknowledged": {
        "under_review",
        "action_required",
        "approved",
        "rejected",
        "withdrawn",
    },
    "under_review": {"action_required", "approved", "rejected", "withdrawn"},
    "action_required": {"submitted", "under_review", "withdrawn"},
    "approved": {"delivered", "withdrawn"},
    "delivered": set(),
    "rejected": set(),
    "withdrawn": set(),
}


class ApplicationCaseCreate(BaseModel):
    benefit_id: str = Field(min_length=1, max_length=160)
    application_channel: Literal["official_portal", "in_person", "assisted", "other"] = (
        "official_portal"
    )


class ApplicationStatusEventCreate(BaseModel):
    status: ApplicationStatus
    occurred_at: datetime | None = None
    submission_date: date | None = None
    external_reference: str | None = Field(default=None, max_length=160)
    reason_code: str | None = Field(default=None, max_length=80)


class ApplicationStatusEventOut(BaseModel):
    id: str
    status: str
    provenance: str
    actor_type: str
    occurred_at: datetime
    recorded_at: datetime
    source_url: str
    reason_code: str
    external_reference_masked: str


class ApplicationCaseOut(BaseModel):
    id: str
    benefit_id: str
    benefit_name: str
    benefit_domain: str
    benefit_state_code: str | None
    benefit_revision: int
    benefit_verification_status: str
    source_title: str
    source_document_url: str
    last_verified_date: str | None
    application_channel: str
    status: str
    status_provenance: str
    status_recorded_at: datetime
    status_source_url: str
    readiness_state: str
    readiness_blockers: list[str]
    external_reference_masked: str
    submission_date: date | None
    revision: int
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None
    tasks: list[ApplicationTaskOut]
    status_events: list[ApplicationStatusEventOut]


@router.get("/{session_id}/applications", response_model=list[ApplicationCaseOut])
def list_applications(
    session_id: str,
    db: Session = Depends(get_session),
    principal: BrowserSessionPrincipal = Depends(require_browser_session),
) -> list[ApplicationCaseOut]:
    _require_own_session(session_id, principal)
    _require_application_copilot(principal)
    rows = db.exec(
        select(ApplicationCase)
        .where(ApplicationCase.session_id == principal.session_id)
        .order_by(ApplicationCase.updated_at.desc())
    ).all()
    return [_case_out(db, row) for row in rows]


@router.post(
    "/{session_id}/applications",
    response_model=ApplicationCaseOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_application(
    session_id: str,
    payload: ApplicationCaseCreate,
    request: Request,
    http_response: Response,
    db: Session = Depends(get_session),
    principal: BrowserSessionPrincipal = Depends(require_browser_session),
) -> ApplicationCaseOut:
    _require_own_session(session_id, principal)
    _require_application_copilot(principal)
    decision = await enforce_rate_limit(
        request, session_id=principal.session_id, bucket="application_create"
    )
    apply_rate_limit_headers(http_response, decision)

    benefit = _reviewed_active_benefit(db, payload.benefit_id, principal)
    existing = db.exec(
        select(ApplicationCase)
        .where(
            ApplicationCase.session_id == principal.session_id,
            ApplicationCase.benefit_id == benefit.id,
        )
        .order_by(ApplicationCase.updated_at.desc())
    ).first()
    if existing is not None:
        # POST is intentionally idempotent per guest session and benefit. A
        # reload or a double tap cannot create two status journeys.
        http_response.status_code = status.HTTP_200_OK
        return _case_out(db, existing)

    snapshot = benefit_snapshot(benefit)
    snapshot["content_revision"] = benefit.content_revision
    source_url = benefit.source_document_url or benefit.source_url
    now = datetime.now(UTC)
    case = ApplicationCase(
        id=new_id("application"),
        session_id=principal.session_id,
        benefit_id=benefit.id,
        benefit_revision=benefit.content_revision,
        benefit_snapshot=snapshot,
        application_channel=payload.application_channel,
        status="draft",
        status_provenance="system_derived",
        status_recorded_at=now,
        status_source_url=source_url,
        readiness_state="not_ready",
        readiness_blockers=[],
        revision=1,
        created_at=now,
        updated_at=now,
    )
    db.add(case)
    db.flush()
    ensure_application_tasks(
        db,
        principal.session_id,
        benefit,
        application_case_id=case.id,
    )
    db.add(
        ApplicationStatusEvent(
            id=new_id("application-event"),
            application_case_id=case.id,
            status="draft",
            provenance="system_derived",
            actor_type="system",
            actor_id="application-copilot",
            occurred_at=now,
            recorded_at=now,
            source_url=source_url,
            reason_code="case_created",
        )
    )
    db.commit()
    db.refresh(case)
    return _case_out(db, case)


@router.get("/{session_id}/applications/{application_id}", response_model=ApplicationCaseOut)
def get_application(
    session_id: str,
    application_id: str,
    db: Session = Depends(get_session),
    principal: BrowserSessionPrincipal = Depends(require_browser_session),
) -> ApplicationCaseOut:
    _require_own_session(session_id, principal)
    _require_application_copilot(principal)
    case = _case_for_session(db, principal.session_id, application_id)
    return _case_out(db, case)


@router.post(
    "/{session_id}/applications/{application_id}/status-events",
    response_model=ApplicationCaseOut,
)
async def record_application_status(
    session_id: str,
    application_id: str,
    payload: ApplicationStatusEventCreate,
    request: Request,
    http_response: Response,
    db: Session = Depends(get_session),
    principal: BrowserSessionPrincipal = Depends(require_browser_session),
) -> ApplicationCaseOut:
    _require_own_session(session_id, principal)
    _require_application_copilot(principal)
    decision = await enforce_rate_limit(
        request, session_id=principal.session_id, bucket="application_status"
    )
    apply_rate_limit_headers(http_response, decision)

    case = _case_for_session(db, principal.session_id, application_id)
    allowed = _ALLOWED_NEXT.get(case.status, set())
    if payload.status != case.status and payload.status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"A {case.status.replace('_', ' ')} application cannot move to "
                f"{payload.status.replace('_', ' ')}."
            ),
        )

    occurred_at = _as_utc(payload.occurred_at or datetime.now(UTC))
    now = datetime.now(UTC)
    if occurred_at > now + timedelta(minutes=5):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Status time cannot be in the future.",
        )
    if occurred_at < _as_utc(case.created_at) - timedelta(days=1):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Status time is earlier than this application journey.",
        )

    masked_reference = ""
    encrypted_reference = None
    reference_digest = None
    if payload.external_reference:
        try:
            normalized_reference = normalize_reference(payload.external_reference)
            masked_reference = mask_reference(normalized_reference)
            encrypted_reference = encrypt_reference(normalized_reference)
            reference_digest = reference_hash(normalized_reference)
        except ApplicationDataEncryptionUnavailable as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Application reference capture is not configured on this deployment.",
            ) from exc
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    source_url = case.status_source_url or str(
        case.benefit_snapshot.get("source_document_url", "")
    )
    case.status = payload.status
    case.status_provenance = "citizen_reported"
    case.status_recorded_at = occurred_at
    case.updated_at = now
    case.revision += 1
    if payload.submission_date is not None:
        case.submission_date = payload.submission_date
    if encrypted_reference is not None:
        case.external_reference_ciphertext = encrypted_reference
        case.external_reference_hash = reference_digest
        case.external_reference_masked = masked_reference
    if payload.status in _TERMINAL_STATUSES:
        case.closed_at = now
    elif case.closed_at is not None:
        case.closed_at = None
    db.add(case)
    db.add(
        ApplicationStatusEvent(
            id=new_id("application-event"),
            application_case_id=case.id,
            status=payload.status,
            provenance="citizen_reported",
            actor_type="citizen",
            actor_id=principal.session_id,
            occurred_at=occurred_at,
            recorded_at=now,
            source_url=source_url,
            reason_code=(payload.reason_code or "").strip(),
            external_reference_masked=masked_reference,
        )
    )
    db.commit()
    db.refresh(case)
    return _case_out(db, case)


def _require_application_copilot(principal: BrowserSessionPrincipal) -> None:
    if not feature_flag_enabled(
        "application_copilot",
        subject=principal.session_id,
        language_code=principal.language_code,
        state_code=principal.state_code,
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application assistance is not available in this rollout.",
        )


def _reviewed_active_benefit(
    db: Session,
    benefit_id: str,
    principal: BrowserSessionPrincipal,
) -> Benefit:
    benefit = db.get(Benefit, benefit_id)
    if benefit is None or not benefit.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Benefit not found")
    if benefit.verification_status is not VerificationStatus.HUMAN_VERIFIED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This benefit has not passed human publication review yet.",
        )
    if benefit.state_code and benefit.state_code != principal.state_code:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This benefit is not published for your selected state.",
        )
    return benefit


def _case_for_session(db: Session, session_id: str, application_id: str) -> ApplicationCase:
    case = db.exec(
        select(ApplicationCase).where(
            ApplicationCase.id == application_id,
            ApplicationCase.session_id == session_id,
        )
    ).first()
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return case


def _case_out(db: Session, case: ApplicationCase) -> ApplicationCaseOut:
    snapshot = dict(case.benefit_snapshot or {})
    task_rows = db.exec(
        select(ApplicationTask)
        .where(
            ApplicationTask.session_id == case.session_id,
            ApplicationTask.benefit_id == case.benefit_id,
            or_(
                ApplicationTask.application_case_id == case.id,
                ApplicationTask.application_case_id.is_(None),
            ),
        )
        .order_by(ApplicationTask.position, ApplicationTask.created_at)
    ).all()
    event_rows = db.exec(
        select(ApplicationStatusEvent)
        .where(ApplicationStatusEvent.application_case_id == case.id)
        .order_by(ApplicationStatusEvent.occurred_at, ApplicationStatusEvent.recorded_at)
    ).all()
    readiness_state, blockers = _readiness(task_rows)
    return ApplicationCaseOut(
        id=case.id,
        benefit_id=case.benefit_id,
        benefit_name=str(snapshot.get("name") or case.benefit_id),
        benefit_domain=str(snapshot.get("domain") or "scheme"),
        benefit_state_code=snapshot.get("state_code"),
        benefit_revision=case.benefit_revision,
        benefit_verification_status=str(snapshot.get("verification_status") or ""),
        source_title=str(snapshot.get("source_title") or ""),
        source_document_url=str(
            snapshot.get("source_document_url") or snapshot.get("source_url") or ""
        ),
        last_verified_date=snapshot.get("last_verified_date"),
        application_channel=case.application_channel,
        status=case.status,
        status_provenance=case.status_provenance,
        status_recorded_at=case.status_recorded_at,
        status_source_url=case.status_source_url,
        readiness_state=readiness_state,
        readiness_blockers=blockers,
        external_reference_masked=case.external_reference_masked,
        submission_date=case.submission_date,
        revision=case.revision,
        created_at=case.created_at,
        updated_at=case.updated_at,
        closed_at=case.closed_at,
        tasks=[task_out(db, row) for row in task_rows],
        status_events=[_status_event_out(row) for row in event_rows],
    )


def _readiness(tasks: list[ApplicationTask]) -> tuple[str, list[str]]:
    if not tasks:
        return (
            "ready_with_warnings",
            ["No structured checklist was available; confirm the official instructions."],
        )
    pending = [task.title for task in tasks if task.status == "pending"]
    skipped = [task.title for task in tasks if task.status == "skipped"]
    if pending:
        return "not_ready", [f"Complete: {title}" for title in pending[:8]]
    if skipped:
        return "ready_with_warnings", [f"Confirm skipped item: {title}" for title in skipped[:8]]
    return "ready", []


def _status_event_out(row: ApplicationStatusEvent) -> ApplicationStatusEventOut:
    return ApplicationStatusEventOut(
        id=row.id,
        status=row.status,
        provenance=row.provenance,
        actor_type=row.actor_type,
        occurred_at=row.occurred_at,
        recorded_at=row.recorded_at,
        source_url=row.source_url,
        reason_code=row.reason_code,
        external_reference_masked=row.external_reference_masked,
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _require_own_session(session_id: str, principal: BrowserSessionPrincipal) -> None:
    if session_id != principal.session_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No session for this caller",
        )
