"""Citizen application journeys and manually reported status evidence."""

from __future__ import annotations

import hashlib
import html
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal
from urllib.parse import urlparse

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
    Reminder,
    benefit_snapshot,
    encrypt_reference,
    feature_flag_enabled,
    get_session,
    mask_reference,
    new_id,
    normalize_reference,
    reference_hash,
    settings,
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
    current_benefit_revision: int | None
    benefit_change_state: str
    benefit_change_items: list[str]
    source_stale: bool
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


class ApplicationPackPreviewOut(BaseModel):
    html: str
    generated_at: datetime
    expires_at: datetime
    content_sha256: str


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
    _schedule_deadline_reminder(db, case, snapshot, now=now)
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
    "/{session_id}/applications/{application_id}/packs/preview",
    response_model=ApplicationPackPreviewOut,
)
async def preview_application_pack(
    session_id: str,
    application_id: str,
    request: Request,
    http_response: Response,
    db: Session = Depends(get_session),
    principal: BrowserSessionPrincipal = Depends(require_browser_session),
) -> ApplicationPackPreviewOut:
    _require_own_session(session_id, principal)
    _require_application_copilot(principal)
    if not feature_flag_enabled(
        "application_pack",
        subject=principal.session_id,
        language_code=principal.language_code,
        state_code=principal.state_code,
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application packs are not available in this rollout.",
        )
    decision = await enforce_rate_limit(
        request, session_id=principal.session_id, bucket="application_pack"
    )
    apply_rate_limit_headers(http_response, decision)
    case = _case_for_session(db, principal.session_id, application_id)
    generated_at = datetime.now(UTC)
    expires_at = generated_at + timedelta(minutes=15)
    pack_html = _render_pack_html(db, case, generated_at=generated_at, expires_at=expires_at)
    http_response.headers["Cache-Control"] = "no-store, private"
    http_response.headers["Content-Security-Policy"] = (
        "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'"
    )
    return ApplicationPackPreviewOut(
        html=pack_html,
        generated_at=generated_at,
        expires_at=expires_at,
        content_sha256=hashlib.sha256(pack_html.encode("utf-8")).hexdigest(),
    )


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
    if payload.status == "action_required":
        _ensure_in_app_reminder(
            db,
            case,
            due_at=now + timedelta(days=1),
            note="Review the action requested by the department.",
        )
    else:
        _cancel_action_reminders(db, case)
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
    current_benefit = db.get(Benefit, case.benefit_id)
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
    change_state, change_items, source_stale = _benefit_change_state(
        snapshot,
        current_benefit,
        case.benefit_revision,
    )
    return ApplicationCaseOut(
        id=case.id,
        benefit_id=case.benefit_id,
        benefit_name=str(snapshot.get("name") or case.benefit_id),
        benefit_domain=str(snapshot.get("domain") or "scheme"),
        benefit_state_code=snapshot.get("state_code"),
        benefit_revision=case.benefit_revision,
        benefit_verification_status=str(snapshot.get("verification_status") or ""),
        current_benefit_revision=(current_benefit.content_revision if current_benefit else None),
        benefit_change_state=change_state,
        benefit_change_items=change_items,
        source_stale=source_stale,
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


def _benefit_change_state(
    snapshot: dict,
    current: Benefit | None,
    starting_revision: int,
) -> tuple[str, list[str], bool]:
    """Compare the starting public snapshot with the current governed row."""
    if current is None or not current.is_active:
        return "application_invalidated", ["The benefit is no longer published."], True

    verification_value = getattr(current.verification_status, "value", current.verification_status)
    source_stale = (
        verification_value != VerificationStatus.HUMAN_VERIFIED.value
        or current.last_verified_date
        < date.today() - timedelta(days=settings.freshness_stale_days)
    )
    if current.content_revision == starting_revision:
        return "none", [], source_stale

    items: list[str] = []
    if list(snapshot.get("documents_required") or []) != list(current.documents_required or []):
        items.append("Required documents changed.")
    if str(snapshot.get("application_process") or "") != current.application_process:
        items.append("Application steps changed.")
    if str(snapshot.get("source_document_url") or snapshot.get("source_url") or "") != (
        current.source_document_url or current.source_url
    ):
        items.append("Official application source changed.")
    current_deadline = current.valid_until.isoformat() if current.valid_until else None
    if snapshot.get("valid_until") != current_deadline:
        items.append("The published validity or deadline changed.")
    if dict(snapshot.get("eligibility_initial") or {}) != dict(current.eligibility_initial or {}):
        items.append("Eligibility criteria changed; ask a person before relying on this case.")
        return "application_invalidated", items, source_stale
    if not items:
        return "informational", ["The source has a newer governed revision."], source_stale
    return "action_required", items, source_stale


def _render_pack_html(
    db: Session,
    case: ApplicationCase,
    *,
    generated_at: datetime,
    expires_at: datetime,
) -> str:
    """Render a bounded, escaped HTML pack without persisting an artifact."""
    snapshot = dict(case.benefit_snapshot or {})
    tasks = db.exec(
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
    source_url = str(snapshot.get("source_document_url") or snapshot.get("source_url") or "")
    safe_source_url = _safe_http_url(source_url)
    source_link = (
        f'<a href="{html.escape(safe_source_url, quote=True)}">Open official source</a>'
        if safe_source_url
        else html.escape(source_url)
    )
    document_items = "".join(
        f"<li>{html.escape(task.title)} — {html.escape(task.status)}</li>"
        for task in tasks
        if task.kind == "document"
    ) or "<li>Confirm the document list in the official notification.</li>"
    step_items = "".join(
        f"<li>{html.escape(task.title)}: {html.escape(task.description)}</li>"
        for task in tasks
        if task.kind == "application_step"
    ) or "<li>Follow the official source for application instructions.</li>"
    warning_items = "".join(
        f"<li>{html.escape(blocker)}</li>"
        for blocker in _readiness(tasks)[1]
    ) or "<li>Confirm the latest official instructions before submitting.</li>"
    deadline = str(snapshot.get("valid_until") or "Not stated")
    description = str(snapshot.get("description") or "")
    benefits_text = str(snapshot.get("benefits_text") or "")
    generated_text = generated_at.astimezone(UTC).isoformat()
    expiry_text = expires_at.astimezone(UTC).isoformat()
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Sahaayak application preparation pack</title>
  <style>
    :root {{ color-scheme: light; font-family: system-ui, sans-serif; line-height: 1.5; }}
    body {{ color: #17202a; margin: 2rem auto; max-width: 52rem; padding: 0 1rem; }}
    h1, h2 {{ line-height: 1.2; }}
    section {{ border-top: 1px solid #c7ced6; margin-top: 1.5rem; padding-top: 1rem; }}
    .notice {{ background: #fff4d6; border-left: 0.25rem solid #a86500; padding: 0.75rem 1rem; }}
    .meta {{ color: #44515e; font-size: 0.9rem; }}
    a {{ color: #005ea8; }}
    @media print {{ body {{ margin: 0; }} .no-print {{ display: none; }} }}
  </style>
</head>
<body>
  <p class="meta">Sahaayak preparation pack · This is not a government form or
    proof of submission.</p>
  <h1>{html.escape(str(snapshot.get("name") or case.benefit_id))}</h1>
  <p>{html.escape(description)}</p>
  <section><h2>Source and application channel</h2>
    <p>Channel: {html.escape(case.application_channel)}</p>
    <p>Source: {source_link}</p>
    <p>Benefit revision: {case.benefit_revision} · Last stated deadline: {html.escape(deadline)}</p>
  </section>
  <section><h2>What this provides</h2><p>{html.escape(benefits_text)}</p></section>
  <section><h2>Documents to prepare</h2><ul>{document_items}</ul></section>
  <section><h2>Application steps</h2><ol>{step_items}</ol></section>
  <section class="notice"><h2>Before you submit</h2><ul>{warning_items}</ul></section>
  <section><h2>Generated details</h2>
    <p class="meta">Generated at {html.escape(generated_text)} UTC. Preview expires at
      {html.escape(expiry_text)} UTC.</p>
  </section>
</body>
</html>"""


def _safe_http_url(value: str) -> str:
    parsed = urlparse(value.strip())
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return value.strip()
    return ""


def _schedule_deadline_reminder(
    db: Session,
    case: ApplicationCase,
    snapshot: dict,
    *,
    now: datetime,
) -> None:
    raw_deadline = snapshot.get("valid_until")
    if not raw_deadline:
        metadata = snapshot.get("job_metadata")
        if isinstance(metadata, dict):
            raw_deadline = metadata.get("application_deadline")
    if not raw_deadline:
        return
    try:
        deadline = date.fromisoformat(str(raw_deadline)[:10])
    except ValueError:
        return
    if deadline <= now.date():
        return
    due_date = deadline - timedelta(days=7)
    due_at = datetime.combine(due_date, time(hour=9), tzinfo=UTC)
    if due_at <= now:
        due_at = now + timedelta(hours=1)
    _ensure_in_app_reminder(
        db,
        case,
        due_at=due_at,
        note="Check the application deadline and submit through the official channel.",
    )


def _ensure_in_app_reminder(
    db: Session,
    case: ApplicationCase,
    *,
    due_at: datetime,
    note: str,
) -> None:
    existing = db.exec(
        select(Reminder).where(
            Reminder.application_case_id == case.id,
            Reminder.channel == "in_app",
            Reminder.status == "scheduled",
            Reminder.note == note,
        )
    ).first()
    if existing is not None:
        return
    db.add(
        Reminder(
            id=new_id("reminder"),
            session_id=case.session_id,
            benefit_id=case.benefit_id,
            application_case_id=case.id,
            note=note,
            due_at=due_at,
            timezone="Asia/Kolkata",
            channel="in_app",
            status="scheduled",
        )
    )


def _cancel_action_reminders(db: Session, case: ApplicationCase) -> None:
    action_note = "Review the action requested by the department."
    rows = db.exec(
        select(Reminder).where(
            Reminder.application_case_id == case.id,
            Reminder.channel == "in_app",
            Reminder.status == "scheduled",
            Reminder.note == action_note,
        )
    ).all()
    for row in rows:
        row.status = "cancelled"
        db.add(row)


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
