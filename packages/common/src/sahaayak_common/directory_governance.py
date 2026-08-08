"""Immutable versioning helpers for source-attested department routes."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import func
from sqlmodel import Session, select

from sahaayak_common.ids import new_id
from sahaayak_common.models import DepartmentDirectoryEntry, DepartmentDirectoryVersion


def _datetime_value(value: datetime | None) -> str | None:
    return value.astimezone(UTC).isoformat() if value else None


def _date_value(value: date | None) -> str | None:
    return value.isoformat() if value else None


def directory_snapshot(row: DepartmentDirectoryEntry) -> dict[str, Any]:
    """Return all mutable routing/provenance/publication fields as JSON."""

    return {
        "entry_key": row.entry_key,
        "state_code": row.state_code,
        "district_code": row.district_code,
        "district_name": row.district_name,
        "service_domain": row.service_domain,
        "pincode": row.pincode,
        "pincode_prefix": row.pincode_prefix,
        "department_code": row.department_code,
        "department_name": row.department_name,
        "help_centre_name": row.help_centre_name,
        "address": row.address,
        "phone": row.phone,
        "email": row.email,
        "website_url": row.website_url,
        "source_name": row.source_name,
        "source_url": row.source_url,
        "source_record_id": row.source_record_id,
        "source_last_verified": _datetime_value(row.source_last_verified),
        "valid_until": _date_value(row.valid_until),
        "working_hours": row.working_hours,
        "supported_languages": list(row.supported_languages or []),
        "coverage_basis": row.coverage_basis,
        "approval_status": row.approval_status,
        "is_active": row.is_active,
        "priority": row.priority,
        "safe_metadata": dict(row.safe_metadata or {}),
    }


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _parse_date(value: object) -> date | None:
    if not isinstance(value, str) or not value:
        return None
    return date.fromisoformat(value)


def apply_directory_snapshot(row: DepartmentDirectoryEntry, snapshot: dict[str, Any]) -> None:
    """Restore a previously stored snapshot onto an ORM row."""

    mutable_fields = (
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
        "working_hours",
        "coverage_basis",
        "approval_status",
        "is_active",
        "priority",
    )
    for field in mutable_fields:
        if field in snapshot:
            setattr(row, field, snapshot[field])
    row.source_last_verified = _parse_datetime(snapshot.get("source_last_verified"))
    row.valid_until = _parse_date(snapshot.get("valid_until"))
    row.supported_languages = [str(value) for value in snapshot.get("supported_languages") or []]
    row.safe_metadata = dict(snapshot.get("safe_metadata") or {})


def ensure_directory_baseline(db: Session, row: DepartmentDirectoryEntry) -> None:
    """Create the first snapshot for a legacy row without history."""

    latest = db.exec(
        select(DepartmentDirectoryVersion)
        .where(DepartmentDirectoryVersion.entry_id == row.id)
        .order_by(DepartmentDirectoryVersion.version.desc())
        .limit(1)
    ).first()
    if latest is not None:
        row.content_revision = max(row.content_revision, latest.version)
        return
    if row.content_revision > 0:
        return
    row.content_revision = 1
    db.add(
        DepartmentDirectoryVersion(
            id=new_id("dirver"),
            entry_id=row.id,
            version=1,
            action="baseline",
            actor_id="system",
            actor_role="system",
            reason="Initial department-directory governance snapshot",
            snapshot=directory_snapshot(row),
        )
    )


def ensure_directory_baselines(db: Session) -> int:
    """Backfill history for rows created before directory versioning existed."""

    rows = db.exec(
        select(DepartmentDirectoryEntry).where(DepartmentDirectoryEntry.content_revision == 0)
    ).all()
    for row in rows:
        ensure_directory_baseline(db, row)
    return len(rows)


def record_directory_version(
    db: Session,
    row: DepartmentDirectoryEntry,
    *,
    action: str,
    actor_id: str,
    actor_role: str,
    reason: str,
) -> DepartmentDirectoryVersion:
    """Append the current state as the next immutable directory version."""

    ensure_directory_baseline(db, row)
    latest_revision = db.exec(
        select(func.max(DepartmentDirectoryVersion.version)).where(
            DepartmentDirectoryVersion.entry_id == row.id
        )
    ).one()
    next_version = max(int(latest_revision or 0), row.content_revision) + 1
    row.content_revision = next_version
    version = DepartmentDirectoryVersion(
        id=new_id("dirver"),
        entry_id=row.id,
        version=next_version,
        action=action,
        actor_id=actor_id,
        actor_role=actor_role,
        reason=reason,
        snapshot=directory_snapshot(row),
        created_at=datetime.now(UTC),
    )
    db.add(version)
    return version
