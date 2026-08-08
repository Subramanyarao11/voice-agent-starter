"""Admin review surface for source-attested department routing."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from sahaayak_api.admin_auth import AdminPrincipal, require_admin_role
from sahaayak_api.telemetry import make_audit_event
from sahaayak_common import DepartmentDirectoryEntry, State, get_session, settings

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
    source_kind: str
    source_scope: str
    approval_status: str
    is_active: bool
    stale: bool
    priority: int
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
    before = {"approval_status": row.approval_status, "is_active": row.is_active}
    row.approval_status = "approved"
    row.is_active = True
    row.updated_at = datetime.now(UTC)
    db.add(row)
    db.add(
        make_audit_event(
            principal=principal,
            action="department_directory.approve",
            target_type="department_directory_entry",
            target_id=row.id,
            reason=payload.reason.strip(),
            safe_before=before,
            safe_after={"approval_status": row.approval_status, "is_active": row.is_active},
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
    before = {"approval_status": row.approval_status, "is_active": row.is_active}
    row.is_active = False
    row.approval_status = "rejected"
    row.updated_at = datetime.now(UTC)
    db.add(row)
    db.add(
        make_audit_event(
            principal=principal,
            action="department_directory.deactivate",
            target_type="department_directory_entry",
            target_id=row.id,
            reason=payload.reason.strip(),
            safe_before=before,
            safe_after={"approval_status": row.approval_status, "is_active": row.is_active},
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
        source_kind=str(metadata.get("source_kind") or "manual_import"),
        source_scope=str(metadata.get("source_scope") or "unspecified"),
        approval_status=row.approval_status,
        is_active=row.is_active,
        stale=_is_stale(row, current),
        priority=row.priority,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


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
