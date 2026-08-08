"""Admin review surface for source-attested department routing."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from sahaayak_api.admin_auth import AdminPrincipal, require_admin_role
from sahaayak_api.telemetry import make_audit_event
from sahaayak_common import (
    DepartmentDirectoryEntry,
    DepartmentDirectoryVersion,
    State,
    apply_directory_snapshot,
    directory_snapshot,
    get_session,
    record_directory_version,
    settings,
)

router = APIRouter(prefix="/api/admin/departments", tags=["admin"])


class DirectoryEntryOut(BaseModel):
    id: str
    entry_key: str
    state_code: str
    district_code: str
    district_name: str
    service_domain: str
    pincode: str
    pincode_prefix: str
    department_code: str
    department_name: str
    help_centre_name: str
    address: str
    phone: str
    email: str
    website_url: str
    source_name: str
    source_url: str
    source_record_id: str
    source_last_verified: datetime | None
    valid_until: date | None
    working_hours: str
    supported_languages: list[str]
    coverage_basis: str
    source_kind: str
    source_scope: str
    approval_status: str
    is_active: bool
    stale: bool
    priority: int
    content_revision: int
    created_at: datetime
    updated_at: datetime


class DirectoryCoverageOut(BaseModel):
    state_code: str
    state_name: str
    total: int
    approved: int
    active_approved: int
    pending: int
    stale: int
    districts: int


class DirectoryListOut(BaseModel):
    generated_at: datetime
    stale_after_days: int
    entries: list[DirectoryEntryOut]
    total: int
    status_counts: dict[str, int]
    source_counts: dict[str, int]
    stale_count: int
    active_approved_count: int
    coverage_by_state: list[DirectoryCoverageOut]


class DirectoryDecisionRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class DirectoryEditRequest(BaseModel):
    expected_revision: int | None = Field(default=None, ge=1)
    state_code: str = Field(min_length=2, max_length=16)
    district_code: str = Field(default="", max_length=80)
    district_name: str = Field(default="", max_length=120)
    service_domain: Literal["scheme", "scholarship", "job", "citizen_support"] = "citizen_support"
    pincode: str = Field(default="", max_length=6)
    pincode_prefix: str = Field(default="", max_length=5)
    department_code: str = Field(default="", max_length=120)
    department_name: str = Field(min_length=2, max_length=200)
    help_centre_name: str = Field(default="", max_length=200)
    address: str = Field(default="", max_length=500)
    phone: str = Field(default="", max_length=80)
    email: str = Field(default="", max_length=160)
    website_url: str = Field(default="", max_length=500)
    source_name: str = Field(min_length=2, max_length=160)
    source_url: str = Field(min_length=8, max_length=500)
    source_record_id: str = Field(default="", max_length=160)
    source_last_verified: datetime | None = None
    valid_until: date | None = None
    working_hours: str = Field(default="", max_length=500)
    supported_languages: list[str] = Field(default_factory=list, max_length=20)
    coverage_basis: str = Field(default="", max_length=120)
    priority: int = Field(default=100, ge=0, le=10_000)
    reason: str = Field(min_length=3, max_length=500)


class DirectoryVersionOut(BaseModel):
    id: str
    entry_id: str
    version: int
    action: str
    actor_id: str
    actor_role: str
    reason: str
    snapshot: dict[str, Any]
    created_at: datetime


class DirectoryVersionListOut(BaseModel):
    entry_id: str
    current_revision: int
    versions: list[DirectoryVersionOut]


class DirectoryRollbackRequest(BaseModel):
    version: int = Field(ge=1)
    reason: str = Field(min_length=3, max_length=500)


@router.get("", response_model=DirectoryListOut)
def list_directory_entries(
    status: Literal["pending", "approved", "rejected", "all"] = "all",
    state_code: str | None = None,
    district_name: str | None = None,
    limit: int = 200,
    db: Session = Depends(get_session),
    _principal: AdminPrincipal = Depends(
        require_admin_role("observer", "operator", "reviewer", "admin")
    ),
) -> DirectoryListOut:
    limit = max(1, min(limit, 500))
    statement = select(DepartmentDirectoryEntry)
    if status != "all":
        statement = statement.where(DepartmentDirectoryEntry.approval_status == status)
    if state_code:
        statement = statement.where(
            DepartmentDirectoryEntry.state_code == state_code.strip().upper()[:16]
        )
    if district_name:
        statement = statement.where(
            DepartmentDirectoryEntry.district_name == district_name.strip()[:120]
        )
    matching_rows = db.exec(
        statement.order_by(DepartmentDirectoryEntry.updated_at.desc())
    ).all()
    rows = matching_rows[:limit]
    all_rows = db.exec(select(DepartmentDirectoryEntry)).all()
    counts: dict[str, int] = {}
    source_counts: dict[str, int] = {}
    for row in all_rows:
        counts[row.approval_status] = counts.get(row.approval_status, 0) + 1
        source_name = row.source_name or "Unattributed source"
        source_counts[source_name] = source_counts.get(source_name, 0) + 1
    now = datetime.now(UTC)
    coverage = _coverage_by_state(all_rows, db=db, now=now)
    return DirectoryListOut(
        generated_at=now,
        stale_after_days=max(1, settings.department_directory_stale_days),
        entries=[_entry_out(row, now=now) for row in rows],
        total=len(matching_rows),
        status_counts=counts,
        source_counts=source_counts,
        stale_count=sum(_is_stale(row, now) for row in all_rows),
        active_approved_count=sum(
            row.approval_status == "approved" and row.is_active for row in all_rows
        ),
        coverage_by_state=coverage,
    )


@router.post("/{entry_id}/approve", response_model=DirectoryEntryOut)
def approve_directory_entry(
    entry_id: str,
    payload: DirectoryDecisionRequest,
    db: Session = Depends(get_session),
    principal: AdminPrincipal = Depends(require_admin_role("reviewer", "admin")),
) -> DirectoryEntryOut:
    row = _get_entry(db, entry_id)
    if not row.source_url or not row.source_name or row.source_last_verified is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "An entry needs a named source, source URL, and verification "
                "timestamp before approval"
            ),
        )
    if _is_stale(row, datetime.now(UTC)):
        raise HTTPException(
            status_code=409,
            detail=(
                "The source verification timestamp is stale; refresh the "
                "official directory first"
            ),
        )
    before = directory_snapshot(row)
    row.approval_status = "approved"
    row.is_active = True
    row.updated_at = datetime.now(UTC)
    record_directory_version(
        db,
        row,
        action="approve",
        actor_id=principal.actor_id,
        actor_role=principal.role,
        reason=payload.reason.strip(),
    )
    db.add(row)
    db.add(
        make_audit_event(
            principal=principal,
            action="department_directory.approve",
            target_type="department_directory_entry",
            target_id=row.id,
            reason=payload.reason.strip(),
            safe_before=before,
            safe_after={
                "approval_status": row.approval_status,
                "is_active": row.is_active,
                "content_revision": row.content_revision,
            },
        )
    )
    db.commit()
    db.refresh(row)
    return _entry_out(row)


@router.post("/{entry_id}/deactivate", response_model=DirectoryEntryOut)
def deactivate_directory_entry(
    entry_id: str,
    payload: DirectoryDecisionRequest,
    db: Session = Depends(get_session),
    principal: AdminPrincipal = Depends(require_admin_role("reviewer", "admin")),
) -> DirectoryEntryOut:
    row = _get_entry(db, entry_id)
    before = directory_snapshot(row)
    row.is_active = False
    row.approval_status = "rejected"
    row.updated_at = datetime.now(UTC)
    record_directory_version(
        db,
        row,
        action="deactivate",
        actor_id=principal.actor_id,
        actor_role=principal.role,
        reason=payload.reason.strip(),
    )
    db.add(row)
    db.add(
        make_audit_event(
            principal=principal,
            action="department_directory.deactivate",
            target_type="department_directory_entry",
            target_id=row.id,
            reason=payload.reason.strip(),
            safe_before=before,
            safe_after={
                "approval_status": row.approval_status,
                "is_active": row.is_active,
                "content_revision": row.content_revision,
            },
        )
    )
    db.commit()
    db.refresh(row)
    return _entry_out(row)


@router.patch("/{entry_id}", response_model=DirectoryEntryOut)
def edit_directory_entry(
    entry_id: str,
    payload: DirectoryEditRequest,
    db: Session = Depends(get_session),
    principal: AdminPrincipal = Depends(require_admin_role("reviewer", "admin")),
) -> DirectoryEntryOut:
    row = _get_entry(db, entry_id)
    if payload.expected_revision is not None and payload.expected_revision != row.content_revision:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Directory row changed since it was loaded; expected revision "
                f"{payload.expected_revision}, current revision {row.content_revision}"
            ),
        )
    _validate_edit_payload(payload)
    normalized_state = payload.state_code.strip().upper()
    if db.get(State, normalized_state) is None:
        raise HTTPException(status_code=422, detail="state_code must reference a configured state")
    before = directory_snapshot(row)
    fields = (
        "state_code",
        "district_code",
        "district_name",
        "service_domain",
        "pincode",
        "pincode_prefix",
        "department_code",
        "department_name",
        "help_centre_name",
        "address",
        "phone",
        "email",
        "website_url",
        "source_name",
        "source_url",
        "source_record_id",
        "source_last_verified",
        "valid_until",
        "working_hours",
        "supported_languages",
        "coverage_basis",
        "priority",
    )
    for field in fields:
        value = getattr(payload, field)
        if field == "state_code":
            value = normalized_state
        if isinstance(value, str):
            value = value.strip()
        setattr(row, field, value)
    # Any content edit is re-reviewable. This prevents a valid old approval
    # from silently covering a changed phone number or routing key.
    row.approval_status = "pending"
    row.is_active = False
    row.updated_at = datetime.now(UTC)
    record_directory_version(
        db,
        row,
        action="edit",
        actor_id=principal.actor_id,
        actor_role=principal.role,
        reason=payload.reason.strip(),
    )
    db.add(
        make_audit_event(
            principal=principal,
            action="department_directory.edit",
            target_type="department_directory_entry",
            target_id=row.id,
            reason=payload.reason.strip(),
            safe_before={
                "content_revision": row.content_revision - 1,
                "snapshot": before,
            },
            safe_after={
                "content_revision": row.content_revision,
                "snapshot": directory_snapshot(row),
            },
        )
    )
    db.commit()
    db.refresh(row)
    return _entry_out(row)


@router.get("/{entry_id}/versions", response_model=DirectoryVersionListOut)
def directory_versions(
    entry_id: str,
    db: Session = Depends(get_session),
    _principal: AdminPrincipal = Depends(
        require_admin_role("observer", "operator", "reviewer", "admin")
    ),
) -> DirectoryVersionListOut:
    row = _get_entry(db, entry_id)
    versions = db.exec(
        select(DepartmentDirectoryVersion)
        .where(DepartmentDirectoryVersion.entry_id == entry_id)
        .order_by(DepartmentDirectoryVersion.version.desc())
        .limit(100)
    ).all()
    return DirectoryVersionListOut(
        entry_id=entry_id,
        current_revision=row.content_revision,
        versions=[DirectoryVersionOut.model_validate(version.model_dump()) for version in versions],
    )


@router.post("/{entry_id}/rollback", response_model=DirectoryEntryOut)
def rollback_directory_entry(
    entry_id: str,
    payload: DirectoryRollbackRequest,
    db: Session = Depends(get_session),
    principal: AdminPrincipal = Depends(require_admin_role("admin")),
) -> DirectoryEntryOut:
    row = _get_entry(db, entry_id)
    target = db.exec(
        select(DepartmentDirectoryVersion).where(
            DepartmentDirectoryVersion.entry_id == entry_id,
            DepartmentDirectoryVersion.version == payload.version,
        )
    ).first()
    if target is None:
        raise HTTPException(status_code=404, detail="Directory version not found")
    if target.version == row.content_revision:
        raise HTTPException(status_code=400, detail="Directory row is already at that version")
    before = directory_snapshot(row)
    apply_directory_snapshot(row, dict(target.snapshot))
    # Restoring contact data must still pass a fresh human approval. A rollback
    # must not re-enable an old or now-stale office record by accident.
    row.approval_status = "pending"
    row.is_active = False
    row.updated_at = datetime.now(UTC)
    record_directory_version(
        db,
        row,
        action="rollback",
        actor_id=principal.actor_id,
        actor_role=principal.role,
        reason=payload.reason.strip(),
    )
    db.add(
        make_audit_event(
            principal=principal,
            action="department_directory.rollback",
            target_type="department_directory_entry",
            target_id=row.id,
            reason=payload.reason.strip(),
            safe_before={"content_revision": row.content_revision - 1, "snapshot": before},
            safe_after={
                "restored_version": target.version,
                "content_revision": row.content_revision,
                "approval_status": row.approval_status,
                "is_active": row.is_active,
            },
        )
    )
    db.commit()
    db.refresh(row)
    return _entry_out(row)


def _get_entry(db: Session, entry_id: str) -> DepartmentDirectoryEntry:
    row = db.get(DepartmentDirectoryEntry, entry_id)
    if row is None:
        raise HTTPException(status_code=404, detail="No such department directory entry")
    return row


def _is_stale(row: DepartmentDirectoryEntry, now: datetime) -> bool:
    if row.valid_until is not None and row.valid_until < now.date():
        return True
    if row.source_last_verified is None:
        return True
    verified_at = row.source_last_verified
    if verified_at.tzinfo is None:
        verified_at = verified_at.replace(tzinfo=UTC)
    return verified_at < now - timedelta(days=max(1, settings.department_directory_stale_days))


def _entry_out(row: DepartmentDirectoryEntry, *, now: datetime | None = None) -> DirectoryEntryOut:
    current = now or datetime.now(UTC)
    metadata = row.safe_metadata or {}
    return DirectoryEntryOut(
        id=row.id,
        entry_key=row.entry_key,
        state_code=row.state_code,
        district_code=row.district_code,
        district_name=row.district_name,
        service_domain=row.service_domain,
        pincode=row.pincode,
        pincode_prefix=row.pincode_prefix,
        department_code=row.department_code,
        department_name=row.department_name,
        help_centre_name=row.help_centre_name,
        address=row.address,
        phone=row.phone,
        email=row.email,
        website_url=row.website_url,
        source_name=row.source_name,
        source_url=row.source_url,
        source_record_id=row.source_record_id,
        source_last_verified=row.source_last_verified,
        valid_until=row.valid_until,
        working_hours=row.working_hours,
        supported_languages=list(row.supported_languages or []),
        coverage_basis=row.coverage_basis,
        source_kind=str(metadata.get("source_kind") or "manual_import"),
        source_scope=str(metadata.get("source_scope") or "unspecified"),
        approval_status=row.approval_status,
        is_active=row.is_active,
        stale=_is_stale(row, current),
        priority=row.priority,
        content_revision=row.content_revision,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _validate_edit_payload(payload: DirectoryEditRequest) -> None:
    if payload.pincode and (len(payload.pincode) != 6 or not payload.pincode.isdigit()):
        raise HTTPException(status_code=422, detail="pincode must be exactly six digits")
    if payload.pincode_prefix and (
        not payload.pincode_prefix.isdigit() or not 1 <= len(payload.pincode_prefix) <= 5
    ):
        raise HTTPException(
            status_code=422,
            detail="pincode_prefix must contain one to five digits",
        )
    for field_name in ("source_url", "website_url"):
        value = getattr(payload, field_name)
        if value and not value.startswith(("https://", "http://")):
            raise HTTPException(status_code=422, detail=f"{field_name} must be an http(s) URL")
    if payload.valid_until is not None and payload.valid_until < date.today():
        raise HTTPException(status_code=422, detail="valid_until cannot be in the past")


def _coverage_by_state(
    rows: list[DepartmentDirectoryEntry],
    *,
    db: Session,
    now: datetime,
) -> list[DirectoryCoverageOut]:
    state_names = {state.code: state.name for state in db.exec(select(State)).all()}
    grouped: dict[str, list[DepartmentDirectoryEntry]] = {}
    for row in rows:
        grouped.setdefault(row.state_code, []).append(row)

    coverage: list[DirectoryCoverageOut] = []
    for state_code, state_rows in grouped.items():
        coverage.append(
            DirectoryCoverageOut(
                state_code=state_code,
                state_name=state_names.get(state_code, state_code),
                total=len(state_rows),
                approved=sum(row.approval_status == "approved" for row in state_rows),
                active_approved=sum(
                    row.approval_status == "approved" and row.is_active for row in state_rows
                ),
                pending=sum(row.approval_status == "pending" for row in state_rows),
                stale=sum(_is_stale(row, now) for row in state_rows),
                districts=len({row.district_name for row in state_rows if row.district_name}),
            )
        )
    return sorted(coverage, key=lambda item: (-item.total, item.state_code))
