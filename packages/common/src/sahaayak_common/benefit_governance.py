"""Public benefit versioning helpers shared by imports and admin workflows."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import func
from sqlmodel import Session, select

from sahaayak_common.ids import new_id
from sahaayak_common.models import Benefit, BenefitVersion
from sahaayak_contracts import Domain, EligibilityCriteria, VerificationStatus


def _date_value(value: date | None) -> str | None:
    return value.isoformat() if value else None


def _datetime_value(value: datetime | None) -> str | None:
    return value.astimezone(UTC).isoformat() if value else None


def benefit_snapshot(row: Benefit) -> dict[str, Any]:
    """Return a JSON-safe snapshot of all public/governance fields."""
    return {
        "id": row.id,
        "domain": row.domain.value if isinstance(row.domain, Domain) else str(row.domain),
        "name": row.name,
        "state_code": row.state_code,
        "category": row.category,
        "description": row.description,
        "eligibility_initial": dict(row.eligibility_initial or {}),
        "eligibility_renewal": (
            dict(row.eligibility_renewal) if row.eligibility_renewal is not None else None
        ),
        "benefits_text": row.benefits_text,
        "documents_required": list(row.documents_required or []),
        "application_process": row.application_process,
        "source_url": row.source_url,
        "last_verified_date": _date_value(row.last_verified_date),
        "verification_status": (
            row.verification_status.value
            if isinstance(row.verification_status, VerificationStatus)
            else str(row.verification_status)
        ),
        "source_title": row.source_title,
        "source_document_url": row.source_document_url,
        "source_excerpt": row.source_excerpt,
        "source_content_hash": row.source_content_hash,
        "automated_review": dict(row.automated_review or {}),
        "verified_by": row.verified_by,
        "verified_at": _datetime_value(row.verified_at),
        "valid_from": _date_value(row.valid_from),
        "valid_until": _date_value(row.valid_until),
        "localized_summary": dict(row.localized_summary or {}),
        "job_metadata": dict(row.job_metadata or {}) if row.job_metadata is not None else None,
        "is_active": row.is_active,
    }


def _parse_date(value: object) -> date | None:
    if isinstance(value, str) and value:
        return date.fromisoformat(value)
    return None


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def apply_benefit_snapshot(row: Benefit, snapshot: dict[str, Any]) -> None:
    """Restore a validated version snapshot onto the current ORM row."""
    row.domain = Domain(snapshot["domain"])
    row.name = str(snapshot["name"])
    row.state_code = snapshot.get("state_code")
    row.category = str(snapshot.get("category") or "")
    row.description = str(snapshot.get("description") or "")
    row.eligibility_initial = EligibilityCriteria.model_validate(
        snapshot.get("eligibility_initial") or {}
    ).model_dump(mode="json")
    renewal = snapshot.get("eligibility_renewal")
    row.eligibility_renewal = (
        EligibilityCriteria.model_validate(renewal).model_dump(mode="json")
        if renewal
        else None
    )
    row.benefits_text = str(snapshot.get("benefits_text") or "")
    row.documents_required = [str(value) for value in snapshot.get("documents_required") or []]
    row.application_process = str(snapshot.get("application_process") or "")
    row.source_url = str(snapshot.get("source_url") or "")
    row.last_verified_date = _parse_date(snapshot.get("last_verified_date")) or date.today()
    row.verification_status = VerificationStatus(snapshot["verification_status"])
    row.source_title = str(snapshot.get("source_title") or "")
    row.source_document_url = str(snapshot.get("source_document_url") or "")
    row.source_excerpt = snapshot.get("source_excerpt")
    row.source_content_hash = snapshot.get("source_content_hash")
    row.automated_review = dict(snapshot.get("automated_review") or {})
    row.verified_by = snapshot.get("verified_by")
    row.verified_at = _parse_datetime(snapshot.get("verified_at"))
    row.valid_from = _parse_date(snapshot.get("valid_from"))
    row.valid_until = _parse_date(snapshot.get("valid_until"))
    row.localized_summary = dict(snapshot.get("localized_summary") or {})
    job_metadata = snapshot.get("job_metadata")
    row.job_metadata = dict(job_metadata) if job_metadata is not None else None
    row.is_active = bool(snapshot.get("is_active", False))


def ensure_benefit_baseline(db: Session, row: Benefit) -> None:
    """Create the first snapshot before the first mutation of a legacy row."""
    latest = db.exec(
        select(BenefitVersion)
        .where(BenefitVersion.benefit_id == row.id)
        .order_by(BenefitVersion.version.desc())
        .limit(1)
    ).first()
    if latest is not None:
        row.content_revision = max(row.content_revision, latest.version)
        return
    if row.content_revision > 0:
        return
    row.content_revision = 1
    db.add(
        BenefitVersion(
            id=new_id("bver"),
            benefit_id=row.id,
            version=1,
            action="baseline",
            actor_id="system",
            actor_role="system",
            reason="Initial governance snapshot",
            snapshot=benefit_snapshot(row),
        )
    )


def ensure_benefit_baselines(db: Session) -> int:
    """Backfill one baseline snapshot for legacy rows without history."""
    rows = db.exec(select(Benefit).where(Benefit.content_revision == 0)).all()
    for row in rows:
        ensure_benefit_baseline(db, row)
    return len(rows)


def record_benefit_version(
    db: Session,
    row: Benefit,
    *,
    action: str,
    actor_id: str,
    actor_role: str,
    reason: str,
) -> BenefitVersion:
    """Append the current state as a new immutable version."""
    ensure_benefit_baseline(db, row)
    latest_revision = db.exec(
        select(func.max(BenefitVersion.version)).where(BenefitVersion.benefit_id == row.id)
    ).one()
    next_version = max(int(latest_revision or 0), row.content_revision) + 1
    row.content_revision = next_version
    version = BenefitVersion(
        id=new_id("bver"),
        benefit_id=row.id,
        version=next_version,
        action=action,
        actor_id=actor_id,
        actor_role=actor_role,
        reason=reason,
        snapshot=benefit_snapshot(row),
        created_at=datetime.now(UTC),
    )
    db.add(version)
    return version
