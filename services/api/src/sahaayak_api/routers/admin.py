"""Role-protected platform operations APIs.

The browser dashboard consumes bounded aggregates from here. It does not join
citizen tables directly, and overview responses intentionally contain no raw
transcript, audio, phone/session identifier, or sensitive profile values.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from enum import Enum
from typing import Any, Literal, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, text
from sqlmodel import Session, select

from sahaayak_agent.prompts import supported_languages
from sahaayak_api.admin_auth import AdminPrincipal, require_admin_role
from sahaayak_api.routers.health import HealthReport, health
from sahaayak_api.telemetry import make_audit_event
from sahaayak_common import (
    DEFAULT_PROVIDER_POLICIES,
    AuditEvent,
    Benefit,
    BenefitIssueReport,
    ConversationTurnLog,
    DataImportRun,
    EscalationTicket,
    EvaluationRun,
    FeatureFlag,
    FeatureFlagRevision,
    Language,
    OpenAIBudgetLedger,
    ProviderPolicy,
    ProviderPolicyRevision,
    State,
    TelemetryEvent,
    UserSession,
    get_logger,
    get_session,
    settings,
)
from sahaayak_contracts import VerificationStatus

log = get_logger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])

READ_ROLES = ("observer", "operator", "reviewer", "admin")

PROCESS_STARTED_AT = datetime.now(UTC)


class AdminMeOut(BaseModel):
    actor_id: str
    role: str
    permissions: list[str]
    auth_source: str
    mfa_verified: bool


class HealthOut(BaseModel):
    status: str
    environment: str
    database: str
    cache: str
    speech_to_text: bool
    text_to_speech: bool
    reasoning_model: bool
    tracing: bool
    languages: list[str]


class TrafficOut(BaseModel):
    requests: int
    errors: int
    error_rate: float
    p50_latency_ms: float
    p95_latency_ms: float
    active_sessions: int
    turns: int
    language_mix: dict[str, int]


class QualityOut(BaseModel):
    escalations: int
    open_escalations: int
    escalation_rate: float
    no_match_turns: int
    active_benefits: int
    verified_benefits: int
    machine_reviewed_benefits: int
    needs_review_benefits: int
    stale_benefits: int
    illustrative_benefits: int
    latest_import_at: datetime | None


class ProviderStatusOut(BaseModel):
    name: str
    configured: bool
    health: str
    requests: int
    failures: int
    cache_hits: int = 0
    cache_misses: int = 0
    budget_usd: float | None = None
    reserved_usd: float | None = None
    observed_usd: float | None = None
    remaining_usd: float | None = None
    controls_available: bool = False
    note: str = ""


class ProviderPolicyOut(BaseModel):
    id: str
    provider: str
    scope: str
    enabled: bool
    primary_provider: str
    fallback_provider: str | None
    circuit_state: str
    daily_budget_usd: float | None
    monthly_budget_usd: float | None
    override_expires_at: datetime | None
    revision: int
    config: dict
    updated_by: str
    updated_at: datetime


class ProviderPolicyRevisionOut(BaseModel):
    id: str
    policy_id: str
    revision: int
    action: str
    actor_id: str
    actor_role: str
    reason: str
    before: dict
    after: dict
    created_at: datetime


class ProviderPolicyListOut(BaseModel):
    generated_at: datetime
    policies: list[ProviderPolicyOut]
    revisions: list[ProviderPolicyRevisionOut]
    controls_note: str


class ProviderPolicyUpdateRequest(BaseModel):
    enabled: bool = True
    primary_provider: str = Field(min_length=2, max_length=80)
    fallback_provider: str | None = Field(default=None, max_length=80)
    circuit_state: Literal["closed", "open", "half_open"] = "closed"
    daily_budget_usd: float | None = Field(default=None, ge=0, le=15)
    monthly_budget_usd: float | None = Field(default=None, ge=0, le=15)
    override_expires_at: datetime | None = None
    reason: str = Field(min_length=3, max_length=500)


class ProviderPolicyRollbackRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)
    revision_id: str | None = Field(default=None, max_length=160)


class RecentErrorOut(BaseModel):
    request_id: str | None
    route: str
    method: str
    status_code: int | None
    error_code: str | None
    duration_ms: float | None
    created_at: datetime


class AdminOverviewOut(BaseModel):
    generated_at: datetime
    data_fresh_at: datetime | None
    partial_data: bool
    window_hours: int
    health: HealthOut
    traffic: TrafficOut
    quality: QualityOut
    providers: list[ProviderStatusOut]
    recent_errors: list[RecentErrorOut]


class ConversationSummaryOut(BaseModel):
    session_key: str
    state_code: str
    language_code: str
    turn_count: int
    created_at: datetime
    last_contact_at: datetime
    last_intent: str | None


class ConversationListOut(BaseModel):
    items: list[ConversationSummaryOut]
    total: int
    data_fresh_at: datetime | None


class TelemetryEventOut(BaseModel):
    id: str
    event_type: str
    request_id: str | None
    trace_id: str | None
    trace_url: str | None
    route: str
    method: str
    status_code: int | None
    duration_ms: float | None
    surface: str
    language_code: str | None
    state_code: str | None
    provider: str | None
    outcome: str
    error_code: str | None
    safe_metadata: dict
    created_at: datetime


class BenefitReviewOut(BaseModel):
    id: str
    domain: str
    name: str
    state_code: str | None
    verification_status: str
    is_active: bool
    source_title: str
    source_document_url: str
    source_excerpt: str | None
    automated_review: dict
    verified_by: str | None
    verified_at: datetime | None
    last_verified_date: date | None
    valid_from: date | None
    valid_until: date | None
    job_metadata: dict


class ReviewQueueOut(BaseModel):
    items: list[BenefitReviewOut]
    total: int
    status_counts: dict[str, int]
    data_fresh_at: datetime | None


class BenefitReviewRequest(BaseModel):
    verification_status: VerificationStatus
    reason: str = Field(min_length=3, max_length=500)
    activate: bool | None = None


class BenefitIssueReportOut(BaseModel):
    id: str
    benefit_id: str
    benefit_name: str
    category: str
    description: str
    locale: str
    status: str
    source_title: str
    source_document_url: str
    created_at: datetime
    resolved_at: datetime | None
    resolved_by: str | None


class BenefitIssueReportUpdate(BaseModel):
    status: Literal["acknowledged", "resolved", "dismissed"]
    reason: str = Field(min_length=3, max_length=500)


class ImportRunOut(BaseModel):
    id: str
    source_name: str
    state_code: str | None
    started_at: datetime
    completed_at: datetime | None
    model_name: str
    prompt_version: str
    input_count: int
    accepted_count: int
    failed_count: int
    review_sample_size: int
    manifest_json: dict


class EvaluationRunOut(BaseModel):
    id: str
    suite_name: str
    suite_version: str
    passed: bool
    case_count: int
    passed_count: int
    failed_count: int
    language_counts: dict
    report_json: dict
    started_at: datetime
    completed_at: datetime | None


class FreshnessSourceOut(BaseModel):
    dataset: str
    total_rows: int
    active_rows: int
    human_verified_rows: int
    machine_structured_rows: int
    stale_rows: int
    expired_rows: int
    missing_source_rows: int
    oldest_verified_date: date | None
    latest_verified_date: date | None
    latest_import_at: datetime | None
    status: str


class FreshnessOut(BaseModel):
    generated_at: datetime
    stale_after_days: int
    data_fresh_at: datetime | None
    sources: list[FreshnessSourceOut]


class FeatureFlagOut(BaseModel):
    id: str
    key: str
    description: str
    enabled: bool
    rollout_percentage: int
    target_languages: list[str]
    target_states: list[str]
    config: dict
    revision: int
    updated_by: str
    updated_at: datetime


class FeatureFlagRevisionOut(BaseModel):
    id: str
    flag_id: str
    revision: int
    action: str
    actor_id: str
    actor_role: str
    reason: str
    before: dict
    after: dict
    created_at: datetime


class FeatureFlagListOut(BaseModel):
    generated_at: datetime
    flags: list[FeatureFlagOut]
    revisions: list[FeatureFlagRevisionOut]


class FeatureFlagUpdateRequest(BaseModel):
    enabled: bool = False
    rollout_percentage: int = Field(default=0, ge=0, le=100)
    target_languages: list[str] = Field(default_factory=list, max_length=20)
    target_states: list[str] = Field(default_factory=list, max_length=20)
    reason: str = Field(min_length=3, max_length=500)


class FeatureFlagRollbackRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)
    revision_id: str | None = Field(default=None, max_length=160)


class ProviderListOut(BaseModel):
    generated_at: datetime
    providers: list[ProviderStatusOut]
    policies: list[ProviderPolicyOut] = Field(default_factory=list)
    controls_note: str


class LanguageReadinessOut(BaseModel):
    code: str
    name: str
    native_name: str
    active: bool
    prompt_ready: bool
    interface_status: str
    data_status: str
    localized_benefits: int
    active_benefits: int
    stt_provider: str
    tts_provider: str
    voice_status: str
    rollout_status: str


class AuditEventOut(BaseModel):
    id: str
    actor_id: str
    actor_role: str
    action: str
    target_type: str
    target_id: str
    reason: str
    safe_before: dict
    safe_after: dict
    request_id: str | None
    created_at: datetime


class SystemOut(BaseModel):
    environment: str
    process_started_at: datetime
    generated_at: datetime
    git_commit_sha: str
    migration_revision: str | None
    database_mode: str
    configuration: dict[str, bool]
    deployment_notes: list[str]


@router.get("/me", response_model=AdminMeOut)
async def admin_me(
    principal: AdminPrincipal = Depends(require_admin_role(*READ_ROLES)),
) -> AdminMeOut:
    permissions = {
        "observer": ["overview.read", "telemetry.read", "audit.read", "system.read"],
        "operator": [
            "overview.read",
            "telemetry.read",
            "audit.read",
            "system.read",
            "escalations.write",
        ],
        "reviewer": [
            "overview.read",
            "telemetry.read",
            "audit.read",
            "system.read",
            "benefits.write",
        ],
        "admin": [
            "overview.read",
            "telemetry.read",
            "audit.read",
            "system.read",
            "escalations.write",
            "benefits.write",
            "settings.write",
        ],
    }
    return AdminMeOut(
        actor_id=principal.actor_id,
        role=principal.role,
        permissions=permissions[principal.role],
        auth_source=principal.auth_source,
        mfa_verified=principal.mfa_verified,
    )


@router.get("/overview", response_model=AdminOverviewOut)
async def admin_overview(
    hours: int = Query(default=24, ge=1, le=168),
    db: Session = Depends(get_session),
    _principal: AdminPrincipal = Depends(require_admin_role(*READ_ROLES)),
) -> AdminOverviewOut:
    now = datetime.now(UTC)
    window_start = now - timedelta(hours=hours)
    http_events = db.exec(
        select(TelemetryEvent)
        .where(TelemetryEvent.event_type == "http", TelemetryEvent.created_at >= window_start)
        .order_by(TelemetryEvent.created_at.desc())
        .limit(5_000)
    ).all()
    turn_events = db.exec(
        select(TelemetryEvent)
        .where(TelemetryEvent.event_type == "turn", TelemetryEvent.created_at >= window_start)
        .order_by(TelemetryEvent.created_at.desc())
        .limit(5_000)
    ).all()
    durations = [event.duration_ms for event in http_events if event.duration_ms is not None]
    errors = [event for event in http_events if (event.status_code or 0) >= 500]
    requests = len(http_events)
    escalation_count = db.exec(
        select(func.count())
        .select_from(EscalationTicket)
        .where(EscalationTicket.created_at >= window_start)
    ).one()
    open_escalations = db.exec(
        select(func.count()).select_from(EscalationTicket).where(EscalationTicket.status == "open")
    ).one()
    active_sessions = db.exec(
        select(func.count())
        .select_from(UserSession)
        .where(UserSession.last_contact_at >= now - timedelta(minutes=30))
    ).one()

    verification_counts = _verification_counts(db)
    latest_import = db.exec(
        select(DataImportRun).order_by(DataImportRun.completed_at.desc()).limit(1)
    ).first()
    health_report = await health()
    providers = _provider_statuses(health_report, turn_events)
    latest_telemetry = db.exec(select(func.max(TelemetryEvent.created_at))).one()
    freshness = max(
        [
            value
            for value in (latest_telemetry, latest_import.completed_at if latest_import else None)
            if value
        ],
        default=None,
    )
    language_mix = Counter(event.language_code for event in turn_events if event.language_code)
    no_match_turns = sum(event.outcome == "no_match" for event in turn_events)
    total_active = sum(verification_counts.values())
    escalation_rate = (int(escalation_count or 0) / len(turn_events)) if turn_events else 0.0

    return AdminOverviewOut(
        generated_at=now,
        data_fresh_at=freshness,
        partial_data=False,
        window_hours=hours,
        health=HealthOut.model_validate(health_report.model_dump()),
        traffic=TrafficOut(
            requests=requests,
            errors=len(errors),
            error_rate=(len(errors) / requests) if requests else 0.0,
            p50_latency_ms=_percentile(durations, 0.50),
            p95_latency_ms=_percentile(durations, 0.95),
            active_sessions=int(active_sessions or 0),
            turns=len(turn_events),
            language_mix=dict(language_mix),
        ),
        quality=QualityOut(
            escalations=int(escalation_count or 0),
            open_escalations=int(open_escalations or 0),
            escalation_rate=escalation_rate,
            no_match_turns=no_match_turns,
            active_benefits=total_active,
            verified_benefits=verification_counts.get("human_verified", 0),
            machine_reviewed_benefits=verification_counts.get("machine_reviewed", 0),
            needs_review_benefits=verification_counts.get("needs_review", 0),
            stale_benefits=verification_counts.get("stale", 0),
            illustrative_benefits=verification_counts.get("illustrative", 0),
            latest_import_at=latest_import.completed_at if latest_import else None,
        ),
        providers=providers,
        recent_errors=[RecentErrorOut.model_validate(event.model_dump()) for event in errors[:20]],
    )


@router.get("/conversations", response_model=ConversationListOut)
def admin_conversations(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=10_000),
    state_code: str | None = None,
    language_code: str | None = None,
    db: Session = Depends(get_session),
    _principal: AdminPrincipal = Depends(require_admin_role(*READ_ROLES)),
) -> ConversationListOut:
    filters = []
    if state_code:
        filters.append(UserSession.state_code == state_code)
    if language_code:
        filters.append(UserSession.language_code == language_code)
    total = db.exec(select(func.count()).select_from(UserSession).where(*filters)).one()
    rows = db.exec(
        select(UserSession)
        .where(*filters)
        .order_by(UserSession.last_contact_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    session_ids = [row.id for row in rows]
    logs = (
        db.exec(
            select(ConversationTurnLog)
            .where(ConversationTurnLog.session_id.in_(session_ids))
            .order_by(ConversationTurnLog.created_at.desc())
        ).all()
        if session_ids
        else []
    )
    latest_intent = {}
    for row in logs:
        latest_intent.setdefault(row.session_id, row.intent or None)
    latest = db.exec(select(func.max(UserSession.last_contact_at))).one()
    return ConversationListOut(
        items=[
            ConversationSummaryOut(
                session_key=_session_key(row.phone_or_session_id),
                state_code=row.state_code,
                language_code=row.language_code,
                turn_count=row.turn_count,
                created_at=row.created_at,
                last_contact_at=row.last_contact_at,
                last_intent=latest_intent.get(row.id),
            )
            for row in rows
        ],
        total=int(total or 0),
        data_fresh_at=latest,
    )


@router.get("/telemetry/events", response_model=list[TelemetryEventOut])
def admin_telemetry_events(
    limit: int = Query(default=100, ge=1, le=500),
    event_type: str | None = None,
    surface: str | None = None,
    route: str | None = None,
    db: Session = Depends(get_session),
    _principal: AdminPrincipal = Depends(require_admin_role(*READ_ROLES)),
) -> list[TelemetryEventOut]:
    filters = []
    if event_type:
        filters.append(TelemetryEvent.event_type == event_type)
    if surface:
        filters.append(TelemetryEvent.surface == surface)
    if route:
        filters.append(TelemetryEvent.route == route)
    rows = db.exec(
        select(TelemetryEvent)
        .where(*filters)
        .order_by(TelemetryEvent.created_at.desc())
        .limit(limit)
    ).all()
    return [TelemetryEventOut.model_validate(row.model_dump()) for row in rows]


@router.get("/benefits/review", response_model=ReviewQueueOut)
def admin_benefit_reviews(
    status: str | None = None,
    active: bool | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_session),
    _principal: AdminPrincipal = Depends(require_admin_role(*READ_ROLES)),
) -> ReviewQueueOut:
    filters = []
    if status:
        filters.append(Benefit.verification_status == status)
    if active is not None:
        filters.append(cast(Any, Benefit.is_active).is_(active))
    rows = db.exec(
        select(Benefit).where(*filters).order_by(Benefit.last_verified_date.asc()).limit(limit)
    ).all()
    total = db.exec(select(func.count()).select_from(Benefit).where(*filters)).one()
    counts = _verification_counts(db, include_inactive=True)
    latest = db.exec(select(func.max(Benefit.last_verified_date))).one()
    return ReviewQueueOut(
        items=[_benefit_review_out(row) for row in rows],
        total=int(total or 0),
        status_counts=counts,
        data_fresh_at=datetime.combine(latest, datetime.min.time(), tzinfo=UTC) if latest else None,
    )


@router.post("/benefits/{benefit_id}/review", response_model=BenefitReviewOut)
def review_benefit(
    benefit_id: str,
    payload: BenefitReviewRequest,
    db: Session = Depends(get_session),
    principal: AdminPrincipal = Depends(require_admin_role("reviewer", "admin")),
) -> BenefitReviewOut:
    row = db.get(Benefit, benefit_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Benefit not found")
    if payload.activate and not (row.source_document_url or row.source_url):
        raise HTTPException(status_code=400, detail="An active benefit needs a source URL")

    before = {
        "verification_status": _wire(row.verification_status),
        "is_active": row.is_active,
        "verified_by": row.verified_by,
    }
    row.verification_status = payload.verification_status
    if payload.activate is not None:
        row.is_active = payload.activate
    if payload.verification_status is VerificationStatus.HUMAN_VERIFIED:
        row.verified_by = principal.actor_id
        row.verified_at = datetime.now(UTC)
    else:
        row.verified_by = None
        row.verified_at = None
    db.add(row)
    db.add(
        make_audit_event(
            principal=principal,
            action="benefit.review",
            target_type="benefit",
            target_id=row.id,
            reason=payload.reason,
            safe_before=before,
            safe_after={
                "verification_status": _wire(row.verification_status),
                "is_active": row.is_active,
                "verified_by": row.verified_by,
            },
        )
    )
    db.commit()
    db.refresh(row)
    return _benefit_review_out(row)


@router.get("/benefit-reports", response_model=list[BenefitIssueReportOut])
def admin_benefit_reports(
    status: str = Query(default="open"),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_session),
    principal: AdminPrincipal = Depends(require_admin_role(*READ_ROLES)),
) -> list[BenefitIssueReportOut]:
    rows = db.exec(
        select(BenefitIssueReport)
        .where(BenefitIssueReport.status == status)
        .order_by(BenefitIssueReport.created_at.desc())
        .limit(limit)
    ).all()
    return [_benefit_issue_report_out(db, row, principal) for row in rows]


@router.post(
    "/benefit-reports/{report_id}",
    response_model=BenefitIssueReportOut,
)
def update_benefit_report(
    report_id: str,
    payload: BenefitIssueReportUpdate,
    db: Session = Depends(get_session),
    principal: AdminPrincipal = Depends(require_admin_role("operator", "admin")),
) -> BenefitIssueReportOut:
    row = db.get(BenefitIssueReport, report_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Issue report not found")
    before = {"status": row.status, "resolved": row.resolved_at is not None}
    row.status = payload.status
    row.resolved_at = datetime.now(UTC) if payload.status in {"resolved", "dismissed"} else None
    row.resolved_by = principal.actor_id if row.resolved_at else None
    db.add(row)
    db.add(
        make_audit_event(
            principal=principal,
            action="benefit_issue_report.update",
            target_type="benefit_issue_report",
            target_id=row.id,
            reason=payload.reason,
            safe_before=before,
            safe_after={"status": row.status, "resolved": row.resolved_at is not None},
        )
    )
    db.commit()
    db.refresh(row)
    return _benefit_issue_report_out(db, row, principal)


@router.get("/imports", response_model=list[ImportRunOut])
def admin_imports(
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_session),
    _principal: AdminPrincipal = Depends(require_admin_role(*READ_ROLES)),
) -> list[ImportRunOut]:
    rows = db.exec(
        select(DataImportRun).order_by(DataImportRun.started_at.desc()).limit(limit)
    ).all()
    return [ImportRunOut.model_validate(row.model_dump()) for row in rows]


@router.get("/evaluations", response_model=list[EvaluationRunOut])
def admin_evaluations(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_session),
    _principal: AdminPrincipal = Depends(require_admin_role(*READ_ROLES)),
) -> list[EvaluationRunOut]:
    rows = db.exec(
        select(EvaluationRun).order_by(EvaluationRun.started_at.desc()).limit(limit)
    ).all()
    return [EvaluationRunOut.model_validate(row.model_dump()) for row in rows]


@router.get("/freshness", response_model=FreshnessOut)
def admin_freshness(
    stale_days: int = Query(default=90, ge=1, le=730),
    db: Session = Depends(get_session),
    _principal: AdminPrincipal = Depends(require_admin_role(*READ_ROLES)),
) -> FreshnessOut:
    now = datetime.now(UTC)
    cutoff = date.today() - timedelta(days=stale_days)
    rows = db.exec(select(Benefit)).all()
    imports = db.exec(select(DataImportRun)).all()
    grouped: dict[str, list[Benefit]] = {}
    for row in rows:
        metadata = row.job_metadata or {}
        source_kind = str(metadata.get("source_kind") or "")
        if row.domain.value == "job":
            dataset = {
                "upsc_recruitment": "upsc_recruitment",
                "kpsc_recruitment_notification": "state_government_jobs",
                "ncs_government_jobs_api": "ncs_government_jobs",
            }.get(source_kind, "government_jobs_other")
        else:
            dataset = "myscheme"
        grouped.setdefault(dataset, []).append(row)

    source_reports: list[FreshnessSourceOut] = []
    for dataset, dataset_rows in sorted(grouped.items()):
        verified_dates = [row.last_verified_date for row in dataset_rows if row.last_verified_date]
        stale_rows = sum(
            row.last_verified_date is None or row.last_verified_date < cutoff
            for row in dataset_rows
        )
        expired_rows = sum(
            row.valid_until is not None and row.valid_until < date.today()
            for row in dataset_rows
        )
        latest_import = max(
            (
                run.completed_at
                for run in imports
                if run.completed_at and dataset.casefold() in run.source_name.casefold()
            ),
            default=None,
        )
        missing_source = sum(
            not (row.source_document_url or row.source_url) for row in dataset_rows
        )
        if not dataset_rows or stale_rows or missing_source:
            status = "warning" if dataset_rows else "critical"
        else:
            status = "healthy"
        source_reports.append(
            FreshnessSourceOut(
                dataset=dataset,
                total_rows=len(dataset_rows),
                active_rows=sum(row.is_active for row in dataset_rows),
                human_verified_rows=sum(
                    _wire(row.verification_status) == "human_verified" for row in dataset_rows
                ),
                machine_structured_rows=sum(
                    _wire(row.verification_status) == "machine_structured"
                    for row in dataset_rows
                ),
                stale_rows=stale_rows,
                expired_rows=expired_rows,
                missing_source_rows=missing_source,
                oldest_verified_date=min(verified_dates, default=None),
                latest_verified_date=max(verified_dates, default=None),
                latest_import_at=latest_import,
                status=status,
            )
        )

    freshness_values = [
        value
        for report in source_reports
        for value in (
            report.latest_import_at,
            datetime.combine(
                report.latest_verified_date,
                datetime.min.time(),
                tzinfo=UTC,
            )
            if report.latest_verified_date
            else None,
        )
        if value
    ]
    return FreshnessOut(
        generated_at=now,
        stale_after_days=stale_days,
        data_fresh_at=max(freshness_values, default=None),
        sources=source_reports,
    )


@router.get("/providers", response_model=ProviderListOut)
async def admin_providers(
    db: Session = Depends(get_session),
    _principal: AdminPrincipal = Depends(require_admin_role(*READ_ROLES)),
) -> ProviderListOut:
    report = await health()
    events = db.exec(
        select(TelemetryEvent)
        .where(TelemetryEvent.event_type == "turn")
        .order_by(TelemetryEvent.created_at.desc())
        .limit(5_000)
    ).all()
    return ProviderListOut(
        generated_at=datetime.now(UTC),
        providers=_provider_statuses(report, events),
        policies=_provider_policy_outs(db),
        controls_note=(
            "Only the admin role can change provider policy. Every change has a "
            "reason, a before/after audit event, and an optional expiry/rollback."
        ),
    )


@router.get("/provider-policies", response_model=ProviderPolicyListOut)
def admin_provider_policies(
    db: Session = Depends(get_session),
    _principal: AdminPrincipal = Depends(require_admin_role(*READ_ROLES)),
) -> ProviderPolicyListOut:
    revisions = db.exec(
        select(ProviderPolicyRevision)
        .order_by(ProviderPolicyRevision.created_at.desc())
        .limit(100)
    ).all()
    return ProviderPolicyListOut(
        generated_at=datetime.now(UTC),
        policies=_provider_policy_outs(db),
        revisions=[ProviderPolicyRevisionOut.model_validate(row.model_dump()) for row in revisions],
        controls_note=(
            "Policy changes are restricted to admin, bounded to a 24-hour override, "
            "and reversible through the latest revision or an explicit revision ID."
        ),
    )


@router.put("/provider-policies/{provider}/{scope}", response_model=ProviderPolicyOut)
def update_provider_policy(
    provider: str,
    scope: str,
    payload: ProviderPolicyUpdateRequest,
    db: Session = Depends(get_session),
    principal: AdminPrincipal = Depends(require_admin_role("admin")),
) -> ProviderPolicyOut:
    _validate_policy_path(provider, scope)
    now = datetime.now(UTC)
    expires_at = _validated_expiry(payload.override_expires_at, now=now)
    if (not payload.enabled or payload.circuit_state != "closed") and expires_at is None:
        raise HTTPException(
            status_code=400,
            detail="Disabling or opening a circuit requires an expiry time within 24 hours",
        )

    policy_id = f"policy:{provider}:{scope}"
    row = db.get(ProviderPolicy, policy_id)
    before = (
        _provider_policy_snapshot(row)
        if row is not None
        else _default_policy_snapshot(provider, scope)
    )
    if row is None:
        row = ProviderPolicy(
            id=policy_id,
            provider=provider,
            scope=scope,
            created_at=now,
        )
    row.enabled = payload.enabled
    row.primary_provider = payload.primary_provider
    row.fallback_provider = payload.fallback_provider
    row.circuit_state = payload.circuit_state
    row.daily_budget_usd = payload.daily_budget_usd
    row.monthly_budget_usd = payload.monthly_budget_usd
    row.override_expires_at = expires_at
    row.revision += 1
    row.updated_by = principal.actor_id
    row.updated_at = now
    after = _provider_policy_snapshot(row)
    db.add(row)
    db.flush()
    db.add(
        ProviderPolicyRevision(
            id=f"polrev_{row.id.replace(':', '_')}_{row.revision}",
            policy_id=row.id,
            revision=row.revision,
            action="update",
            actor_id=principal.actor_id,
            actor_role=principal.role,
            reason=payload.reason,
            before=before,
            after=after,
        )
    )
    db.add(
        make_audit_event(
            principal=principal,
            action="provider_policy.update",
            target_type="provider_policy",
            target_id=row.id,
            reason=payload.reason,
            safe_before=before,
            safe_after=after,
        )
    )
    db.commit()
    db.refresh(row)
    return _provider_policy_out(row)


@router.post(
    "/provider-policies/{provider}/{scope}/rollback",
    response_model=ProviderPolicyOut,
)
def rollback_provider_policy(
    provider: str,
    scope: str,
    payload: ProviderPolicyRollbackRequest,
    db: Session = Depends(get_session),
    principal: AdminPrincipal = Depends(require_admin_role("admin")),
) -> ProviderPolicyOut:
    _validate_policy_path(provider, scope)
    row = db.get(ProviderPolicy, f"policy:{provider}:{scope}")
    if row is None:
        raise HTTPException(status_code=404, detail="No persisted policy exists for this scope")
    revision_query = select(ProviderPolicyRevision).where(
        ProviderPolicyRevision.policy_id == row.id
    )
    if payload.revision_id:
        revision_query = revision_query.where(ProviderPolicyRevision.id == payload.revision_id)
    target_revision = db.exec(
        revision_query.order_by(ProviderPolicyRevision.created_at.desc()).limit(1)
    ).first()
    if target_revision is None:
        raise HTTPException(status_code=404, detail="No policy revision is available to roll back")

    before = _provider_policy_snapshot(row)
    _apply_policy_snapshot(row, target_revision.before)
    row.revision += 1
    row.updated_by = principal.actor_id
    row.updated_at = datetime.now(UTC)
    after = _provider_policy_snapshot(row)
    db.add(row)
    db.flush()
    db.add(
        ProviderPolicyRevision(
            id=f"polrev_{row.id.replace(':', '_')}_{row.revision}",
            policy_id=row.id,
            revision=row.revision,
            action="rollback",
            actor_id=principal.actor_id,
            actor_role=principal.role,
            reason=payload.reason,
            before=before,
            after=after,
        )
    )
    db.add(
        make_audit_event(
            principal=principal,
            action="provider_policy.rollback",
            target_type="provider_policy",
            target_id=row.id,
            reason=payload.reason,
            safe_before=before,
            safe_after=after,
        )
    )
    db.commit()
    db.refresh(row)
    return _provider_policy_out(row)


@router.get("/feature-flags", response_model=FeatureFlagListOut)
def admin_feature_flags(
    db: Session = Depends(get_session),
    _principal: AdminPrincipal = Depends(require_admin_role(*READ_ROLES)),
) -> FeatureFlagListOut:
    flags = db.exec(select(FeatureFlag).order_by(FeatureFlag.key)).all()
    revisions = db.exec(
        select(FeatureFlagRevision)
        .order_by(FeatureFlagRevision.created_at.desc())
        .limit(100)
    ).all()
    return FeatureFlagListOut(
        generated_at=datetime.now(UTC),
        flags=[_feature_flag_out(row) for row in flags],
        revisions=[FeatureFlagRevisionOut.model_validate(row.model_dump()) for row in revisions],
    )


@router.put("/feature-flags/{key}", response_model=FeatureFlagOut)
def update_feature_flag(
    key: str,
    payload: FeatureFlagUpdateRequest,
    db: Session = Depends(get_session),
    principal: AdminPrincipal = Depends(require_admin_role("admin")),
) -> FeatureFlagOut:
    _validate_feature_flag_key(key)
    row = db.exec(select(FeatureFlag).where(FeatureFlag.key == key)).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Feature flag not found")
    before = _feature_flag_snapshot(row)
    now = datetime.now(UTC)
    row.enabled = payload.enabled
    row.rollout_percentage = payload.rollout_percentage
    row.target_languages = sorted(
        {value.strip().lower() for value in payload.target_languages if value.strip()}
    )
    row.target_states = sorted(
        {value.strip().upper() for value in payload.target_states if value.strip()}
    )
    row.revision += 1
    row.updated_by = principal.actor_id
    row.updated_at = now
    after = _feature_flag_snapshot(row)
    db.add(row)
    db.flush()
    db.add(
        FeatureFlagRevision(
            id=f"flagrev_{row.id.replace(':', '_')}_{row.revision}",
            flag_id=row.id,
            revision=row.revision,
            action="update",
            actor_id=principal.actor_id,
            actor_role=principal.role,
            reason=payload.reason,
            before=before,
            after=after,
        )
    )
    db.add(
        make_audit_event(
            principal=principal,
            action="feature_flag.update",
            target_type="feature_flag",
            target_id=row.id,
            reason=payload.reason,
            safe_before=before,
            safe_after=after,
        )
    )
    db.commit()
    db.refresh(row)
    return _feature_flag_out(row)


@router.post("/feature-flags/{key}/rollback", response_model=FeatureFlagOut)
def rollback_feature_flag(
    key: str,
    payload: FeatureFlagRollbackRequest,
    db: Session = Depends(get_session),
    principal: AdminPrincipal = Depends(require_admin_role("admin")),
) -> FeatureFlagOut:
    _validate_feature_flag_key(key)
    row = db.exec(select(FeatureFlag).where(FeatureFlag.key == key)).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Feature flag not found")
    revision_query = select(FeatureFlagRevision).where(FeatureFlagRevision.flag_id == row.id)
    if payload.revision_id:
        revision_query = revision_query.where(FeatureFlagRevision.id == payload.revision_id)
    target_revision = db.exec(
        revision_query.order_by(FeatureFlagRevision.created_at.desc()).limit(1)
    ).first()
    if target_revision is None:
        raise HTTPException(
            status_code=404,
            detail="No feature-flag revision is available to roll back",
        )
    before = _feature_flag_snapshot(row)
    _apply_feature_flag_snapshot(row, target_revision.before)
    row.revision += 1
    row.updated_by = principal.actor_id
    row.updated_at = datetime.now(UTC)
    after = _feature_flag_snapshot(row)
    db.add(row)
    db.flush()
    db.add(
        FeatureFlagRevision(
            id=f"flagrev_{row.id.replace(':', '_')}_{row.revision}",
            flag_id=row.id,
            revision=row.revision,
            action="rollback",
            actor_id=principal.actor_id,
            actor_role=principal.role,
            reason=payload.reason,
            before=before,
            after=after,
        )
    )
    db.add(
        make_audit_event(
            principal=principal,
            action="feature_flag.rollback",
            target_type="feature_flag",
            target_id=row.id,
            reason=payload.reason,
            safe_before=before,
            safe_after=after,
        )
    )
    db.commit()
    db.refresh(row)
    return _feature_flag_out(row)


@router.get("/languages", response_model=list[LanguageReadinessOut])
def admin_languages(
    db: Session = Depends(get_session),
    _principal: AdminPrincipal = Depends(require_admin_role(*READ_ROLES)),
) -> list[LanguageReadinessOut]:
    rows = db.exec(select(Language).order_by(Language.code)).all()
    result: list[LanguageReadinessOut] = []
    for language in rows:
        state_codes = [
            state.code
            for state in db.exec(
                select(State).where(State.primary_language_code == language.code)
            ).all()
        ]
        benefit_rows = db.exec(
            select(Benefit).where(
                cast(Any, Benefit.is_active).is_(True),
                (Benefit.state_code.is_(None) | Benefit.state_code.in_(state_codes))
                if state_codes
                else Benefit.state_code.is_(None),
            )
        ).all()
        localized_count = sum(
            bool(row.localized_summary.get(language.code)) for row in benefit_rows
        )
        active_count = len(benefit_rows)
        prompt_ready = language.code in supported_languages()
        voice_ready = settings.llm_enabled and settings.tts_enabled
        result.append(
            LanguageReadinessOut(
                code=language.code,
                name=language.name,
                native_name=language.native_name,
                active=language.is_active,
                prompt_ready=prompt_ready,
                interface_status="catalogued" if language.is_active else "inactive",
                data_status="localized"
                if localized_count
                else ("available" if active_count else "no active data"),
                localized_benefits=localized_count,
                active_benefits=active_count,
                stt_provider=language.stt_provider,
                tts_provider=language.tts_provider,
                voice_status="ready" if voice_ready and language.is_active else "not ready",
                rollout_status="active"
                if language.is_active and prompt_ready and active_count
                else "not ready",
            )
        )
    return result


@router.get("/audit-events", response_model=list[AuditEventOut])
def admin_audit_events(
    limit: int = Query(default=100, ge=1, le=500),
    action: str | None = None,
    db: Session = Depends(get_session),
    _principal: AdminPrincipal = Depends(require_admin_role(*READ_ROLES)),
) -> list[AuditEventOut]:
    filters = [AuditEvent.action == action] if action else []
    rows = db.exec(
        select(AuditEvent).where(*filters).order_by(AuditEvent.created_at.desc()).limit(limit)
    ).all()
    return [AuditEventOut.model_validate(row.model_dump()) for row in rows]


@router.get("/audit-events/export")
def export_admin_audit_events(
    format: Literal["csv", "json"] = Query(default="csv"),
    limit: int = Query(default=1_000, ge=1, le=5_000),
    action: str | None = None,
    db: Session = Depends(get_session),
    _principal: AdminPrincipal = Depends(require_admin_role(*READ_ROLES)),
) -> Response:
    filters = [AuditEvent.action == action] if action else []
    rows = db.exec(
        select(AuditEvent).where(*filters).order_by(AuditEvent.created_at.desc()).limit(limit)
    ).all()
    payload = [
        AuditEventOut.model_validate(row.model_dump()).model_dump(mode="json")
        for row in rows
    ]
    if format == "json":
        return Response(
            content=json.dumps(payload, ensure_ascii=False),
            media_type="application/json",
            headers={
                "Content-Disposition": 'attachment; filename="sahaayak-audit.json"',
                "Cache-Control": "no-store",
            },
        )

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=(
            "id",
            "actor_id",
            "actor_role",
            "action",
            "target_type",
            "target_id",
            "reason",
            "safe_before",
            "safe_after",
            "request_id",
            "created_at",
        ),
    )
    writer.writeheader()
    for row in payload:
        writer.writerow(
            {
                **row,
                "safe_before": json.dumps(row["safe_before"], ensure_ascii=False, sort_keys=True),
                "safe_after": json.dumps(row["safe_after"], ensure_ascii=False, sort_keys=True),
            }
        )
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="sahaayak-audit.csv"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/system", response_model=SystemOut)
def admin_system(
    db: Session = Depends(get_session),
    _principal: AdminPrincipal = Depends(require_admin_role(*READ_ROLES)),
) -> SystemOut:
    migration_revision = None
    try:
        migration_revision = db.exec(
            text("SELECT version_num FROM alembic_version LIMIT 1")
        ).first()
    except Exception:
        log.warning("admin_migration_revision_unavailable")
    if migration_revision is not None:
        try:
            migration_revision = migration_revision[0]
        except (IndexError, KeyError, TypeError):
            migration_revision = str(migration_revision)
    return SystemOut(
        environment=settings.env,
        process_started_at=PROCESS_STARTED_AT,
        generated_at=datetime.now(UTC),
        git_commit_sha=os.getenv("GIT_COMMIT_SHA", "unknown"),
        migration_revision=str(migration_revision) if migration_revision else None,
        database_mode="sqlite" if settings.using_sqlite else "postgres",
        configuration={
            "redis_configured": bool(settings.redis_url),
            "openai_configured": settings.llm_enabled,
            "vector_store_configured": settings.llm_enabled
            and bool(settings.resolved_openai_vector_store_id),
            "sarvam_configured": settings.tts_enabled,
            "langfuse_configured": settings.tracing_enabled,
            "otel_configured": settings.otel_enabled,
            "rate_limit_configured": settings.rate_limit_enabled,
            "admin_auth_configured": bool(
                settings.admin_oidc_enabled
                or (settings.admin_static_tokens_enabled
                    and (settings.admin_api_token or settings.admin_tokens_json))
            ),
            "admin_oidc_enabled": settings.admin_oidc_enabled,
        },
        deployment_notes=[
            "Overview telemetry is redacted and database-backed.",
            "Provider policy changes require the admin role, a reason, bounded expiry, "
            "and an append-only rollback revision.",
            "Raw transcripts and sensitive profile values are not included in admin aggregates.",
        ],
    )


def _feature_flag_snapshot(row: FeatureFlag) -> dict[str, Any]:
    return {
        "enabled": row.enabled,
        "rollout_percentage": row.rollout_percentage,
        "target_languages": list(row.target_languages),
        "target_states": list(row.target_states),
    }


def _feature_flag_out(row: FeatureFlag) -> FeatureFlagOut:
    return FeatureFlagOut(
        id=row.id,
        key=row.key,
        description=row.description,
        enabled=row.enabled,
        rollout_percentage=row.rollout_percentage,
        target_languages=list(row.target_languages),
        target_states=list(row.target_states),
        config=dict(row.config),
        revision=row.revision,
        updated_by=row.updated_by,
        updated_at=row.updated_at,
    )


def _apply_feature_flag_snapshot(row: FeatureFlag, snapshot: dict[str, Any]) -> None:
    row.enabled = bool(snapshot.get("enabled", False))
    row.rollout_percentage = max(0, min(100, int(snapshot.get("rollout_percentage", 0))))
    row.target_languages = [str(value) for value in snapshot.get("target_languages", [])]
    row.target_states = [str(value) for value in snapshot.get("target_states", [])]


def _validate_feature_flag_key(key: str) -> None:
    if not re.fullmatch(r"[a-z][a-z0-9_]{1,63}", key):
        raise HTTPException(status_code=400, detail="Feature flag key is not valid")


def _wire(value: object) -> str:
    if isinstance(value, Enum):
        return str(value.value)
    raw = str(value)
    return raw.rsplit(".", 1)[-1].lower()


def _session_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * fraction))))
    return round(ordered[index], 2)


def _verification_counts(db: Session, *, include_inactive: bool = False) -> dict[str, int]:
    filters = [] if include_inactive else [cast(Any, Benefit.is_active).is_(True)]
    rows = db.exec(
        select(Benefit.verification_status, func.count())
        .where(*filters)
        .group_by(Benefit.verification_status)
    ).all()
    return {_wire(status): int(count) for status, count in rows}


def _benefit_review_out(row: Benefit) -> BenefitReviewOut:
    return BenefitReviewOut(
        id=row.id,
        domain=_wire(row.domain),
        name=row.name,
        state_code=row.state_code,
        verification_status=_wire(row.verification_status),
        is_active=row.is_active,
        source_title=row.source_title,
        source_document_url=row.source_document_url or row.source_url,
        source_excerpt=row.source_excerpt,
        automated_review=dict(row.automated_review or {}),
        verified_by=row.verified_by,
        verified_at=row.verified_at,
        last_verified_date=row.last_verified_date,
        valid_from=row.valid_from,
        valid_until=row.valid_until,
        job_metadata=dict(row.job_metadata or {}),
    )


def _benefit_issue_report_out(
    db: Session, row: BenefitIssueReport, principal: AdminPrincipal
) -> BenefitIssueReportOut:
    benefit = db.get(Benefit, row.benefit_id)
    return BenefitIssueReportOut(
        id=row.id,
        benefit_id=row.benefit_id,
        benefit_name=benefit.name if benefit else row.benefit_id,
        category=row.category,
        description=(
            row.description
            if principal.role in {"operator", "reviewer", "admin"}
            else ""
        ),
        locale=row.locale,
        status=row.status,
        source_title=benefit.source_title if benefit else "",
        source_document_url=(
            (benefit.source_document_url or benefit.source_url) if benefit else ""
        ),
        created_at=row.created_at,
        resolved_at=row.resolved_at,
        resolved_by=row.resolved_by,
    )


def _provider_statuses(
    report: HealthReport, turn_events: list[TelemetryEvent]
) -> list[ProviderStatusOut]:
    openai_events = [event for event in turn_events if event.provider == "openai_whisper"]
    tts_events = [
        event for event in turn_events if event.safe_metadata.get("tts_provider") == "sarvam_bulbul"
    ]
    tts_hits = sum(bool(event.safe_metadata.get("tts_cache_hit")) for event in tts_events)
    budget: dict[str, Any] = {}
    try:
        budget = OpenAIBudgetLedger(
            settings.openai_budget_usd,
            settings.resolved_openai_budget_ledger_path,
        ).summary()
    except Exception as exc:
        log.warning("admin_openai_budget_unavailable", error=exc.__class__.__name__)
    return [
        ProviderStatusOut(
            name="openai",
            configured=settings.llm_enabled,
            health="configured" if settings.llm_enabled else "not configured",
            requests=int(budget.get("calls", len(openai_events))),
            failures=int(budget.get("failed_calls", 0)),
            budget_usd=_float_or_none(budget.get("budget_usd")),
            reserved_usd=_float_or_none(budget.get("reserved_usd")),
            observed_usd=_float_or_none(budget.get("observed_usd")),
            remaining_usd=_float_or_none(budget.get("remaining_usd")),
            controls_available=True,
            note="Budget ledger is a conservative reservation view, not a provider invoice.",
        ),
        ProviderStatusOut(
            name="sarvam_bulbul",
            configured=settings.tts_enabled,
            health="configured" if settings.tts_enabled else "not configured",
            requests=len(tts_events),
            failures=sum(event.outcome == "error" for event in tts_events),
            cache_hits=tts_hits,
            cache_misses=max(0, len(tts_events) - tts_hits),
            controls_available=True,
            note=(
                "Sarvam credit reconciliation is not available from the current "
                "provider contract; request and cache telemetry is shown."
            ),
        ),
        ProviderStatusOut(
            name="redis",
            configured=bool(settings.redis_url),
            health=report.cache,
            requests=0,
            failures=0 if report.cache == "redis" else 1 if settings.redis_url else 0,
            controls_available=True,
            note="Used for shared TTS cache and rate-limit state when available.",
        ),
        ProviderStatusOut(
            name="langfuse",
            configured=settings.tracing_enabled,
            health="configured" if settings.tracing_enabled else "disabled",
            requests=0,
            failures=0,
            controls_available=False,
            note="Trace export is optional and should be verified in the deployment project.",
        ),
        ProviderStatusOut(
            name="opentelemetry",
            configured=settings.otel_enabled,
            health="configured" if settings.otel_enabled else "disabled",
            requests=0,
            failures=0,
            note=(
                "OTLP traces/metrics are exported only when an endpoint or console "
                "exporter is configured."
            ),
        ),
    ]


def _provider_policy_outs(db: Session) -> list[ProviderPolicyOut]:
    rows = db.exec(
        select(ProviderPolicy).order_by(ProviderPolicy.provider, ProviderPolicy.scope)
    ).all()
    existing = {(row.provider, row.scope) for row in rows}
    result = [_provider_policy_out(row) for row in rows]
    now = datetime.now(UTC)
    for (provider, scope), default in DEFAULT_PROVIDER_POLICIES.items():
        if (provider, scope) in existing:
            continue
        result.append(
            ProviderPolicyOut(
                id=f"default:{provider}:{scope}",
                provider=provider,
                scope=scope,
                enabled=bool(default["enabled"]),
                primary_provider=str(default["primary_provider"]),
                fallback_provider=default.get("fallback_provider"),
                circuit_state=str(default["circuit_state"]),
                daily_budget_usd=None,
                monthly_budget_usd=None,
                override_expires_at=None,
                revision=0,
                config={},
                updated_by="system",
                updated_at=now,
            )
        )
    return result


def _provider_policy_out(row: ProviderPolicy) -> ProviderPolicyOut:
    return ProviderPolicyOut(
        id=row.id,
        provider=row.provider,
        scope=row.scope,
        enabled=row.enabled,
        primary_provider=row.primary_provider,
        fallback_provider=row.fallback_provider,
        circuit_state=row.circuit_state,
        daily_budget_usd=row.daily_budget_usd,
        monthly_budget_usd=row.monthly_budget_usd,
        override_expires_at=row.override_expires_at,
        revision=row.revision,
        config=dict(row.config or {}),
        updated_by=row.updated_by,
        updated_at=row.updated_at,
    )


def _provider_policy_snapshot(row: ProviderPolicy | None) -> dict[str, Any]:
    if row is None:
        return {}
    return {
        "provider": row.provider,
        "scope": row.scope,
        "enabled": row.enabled,
        "primary_provider": row.primary_provider,
        "fallback_provider": row.fallback_provider,
        "circuit_state": row.circuit_state,
        "daily_budget_usd": row.daily_budget_usd,
        "monthly_budget_usd": row.monthly_budget_usd,
        "override_expires_at": (
            row.override_expires_at.isoformat() if row.override_expires_at else None
        ),
        "revision": row.revision,
        "config": dict(row.config or {}),
    }


def _default_policy_snapshot(provider: str, scope: str) -> dict[str, Any]:
    default = DEFAULT_PROVIDER_POLICIES.get(
        (provider, scope), DEFAULT_PROVIDER_POLICIES.get((provider, "*"), {})
    )
    return {
        "provider": provider,
        "scope": scope,
        "enabled": bool(default.get("enabled", True)),
        "primary_provider": str(default.get("primary_provider", provider)),
        "fallback_provider": default.get("fallback_provider"),
        "circuit_state": str(default.get("circuit_state", "closed")),
        "daily_budget_usd": None,
        "monthly_budget_usd": None,
        "override_expires_at": None,
        "revision": 0,
        "config": {},
    }


def _apply_policy_snapshot(row: ProviderPolicy, snapshot: dict[str, Any]) -> None:
    row.enabled = bool(snapshot.get("enabled", True))
    row.primary_provider = str(snapshot.get("primary_provider", row.provider))
    fallback = snapshot.get("fallback_provider")
    row.fallback_provider = str(fallback) if fallback is not None else None
    row.circuit_state = str(snapshot.get("circuit_state", "closed"))
    row.daily_budget_usd = snapshot.get("daily_budget_usd")
    row.monthly_budget_usd = snapshot.get("monthly_budget_usd")
    raw_expiry = snapshot.get("override_expires_at")
    if isinstance(raw_expiry, str) and raw_expiry:
        row.override_expires_at = datetime.fromisoformat(raw_expiry)
    else:
        row.override_expires_at = None
    row.config = dict(snapshot.get("config") or {})


def _validate_policy_path(provider: str, scope: str) -> None:
    if not provider or len(provider) > 80 or not scope or len(scope) > 80:
        raise HTTPException(status_code=422, detail="Provider and scope are required and bounded")


def _validated_expiry(value: datetime | None, *, now: datetime) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    if value <= now:
        raise HTTPException(status_code=400, detail="Override expiry must be in the future")
    if value > now + timedelta(hours=24):
        raise HTTPException(status_code=400, detail="Override expiry cannot exceed 24 hours")
    return value


def _float_or_none(value: object) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
