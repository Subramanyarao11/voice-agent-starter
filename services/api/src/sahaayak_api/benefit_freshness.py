"""Source freshness scanning and alert lifecycle."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlmodel import Session, select

from sahaayak_common import Benefit, DepartmentDirectoryEntry, SourceFreshnessAlert, new_id
from sahaayak_contracts import VerificationStatus


def dataset_for_benefit(row: Benefit) -> str:
    source_kind = str((row.job_metadata or {}).get("source_kind") or "")
    if row.domain.value == "job":
        return {
            "upsc_recruitment": "upsc_recruitment",
            "kpsc_recruitment_notification": "state_government_jobs",
            "ncs_government_jobs_api": "ncs_government_jobs",
        }.get(source_kind, "government_jobs_other")
    return "myscheme"


def scan_source_freshness(
    db: Session,
    *,
    stale_days: int = 90,
    now: datetime | None = None,
) -> list[SourceFreshnessAlert]:
    """Upsert current alerts and resolve alerts whose condition disappeared.

    Only active rows and human-verified rows generate row-level alerts. The
    machine-structured review queue is intentionally not allowed to flood the
    operational alert stream before publication.
    """
    now = now or datetime.now(UTC)
    cutoff = now.date() - timedelta(days=stale_days)
    rows = db.exec(select(Benefit)).all()
    alerts = db.exec(select(SourceFreshnessAlert)).all()
    by_key = {alert.alert_key: alert for alert in alerts}
    expected: dict[str, dict] = {}

    for row in rows:
        in_scope = row.is_active or row.verification_status is VerificationStatus.HUMAN_VERIFIED
        if not in_scope:
            continue
        dataset = dataset_for_benefit(row)
        source_url = row.source_document_url or row.source_url
        base_metadata = {
            "benefit_name": row.name[:240],
            "verification_status": (
                row.verification_status.value
                if isinstance(row.verification_status, VerificationStatus)
                else str(row.verification_status)
            ),
            "last_verified_date": row.last_verified_date.isoformat()
            if row.last_verified_date
            else None,
            "valid_until": row.valid_until.isoformat() if row.valid_until else None,
        }
        if not source_url:
            key = f"benefit:{row.id}:missing_source"
            expected[key] = {
                "benefit_id": row.id,
                "dataset": dataset,
                "alert_type": "missing_source",
                "severity": "critical" if row.is_active else "warning",
                "message": f"{row.name} has no official source URL.",
                "metadata": base_metadata,
            }
        elif row.last_verified_date is None or row.last_verified_date < cutoff:
            key = f"benefit:{row.id}:stale_source"
            expected[key] = {
                "benefit_id": row.id,
                "dataset": dataset,
                "alert_type": "stale_source",
                "severity": "critical" if row.is_active else "warning",
                "message": (
                    f"{row.name} has not been verified within the "
                    f"{stale_days}-day freshness window."
                ),
                "metadata": base_metadata,
            }
        if row.is_active and row.valid_until and row.valid_until < now.date():
            key = f"benefit:{row.id}:expired"
            expected[key] = {
                "benefit_id": row.id,
                "dataset": dataset,
                "alert_type": "expired",
                "severity": "critical",
                "message": f"{row.name} is active but its validity date has expired.",
                "metadata": base_metadata,
            }

    # Directory rows are a separate public-source dataset, but they use the
    # same deduplicated alert lifecycle. Pending/rejected rows stay out of the
    # operational alert stream because they are not eligible for routing.
    directory_rows = db.exec(
        select(DepartmentDirectoryEntry).where(
            DepartmentDirectoryEntry.approval_status == "approved",
            DepartmentDirectoryEntry.is_active.is_(True),
        )
    ).all()
    directory_cutoff = now - timedelta(days=stale_days)
    for row in directory_rows:
        metadata = {
            "directory_entry_id": row.id,
            "state_code": row.state_code,
            "district_name": row.district_name,
            "department_name": row.department_name[:240],
            "source_url": row.source_url,
            "source_last_verified": (
                row.source_last_verified.isoformat() if row.source_last_verified else None
            ),
        }
        if not row.source_url:
            key = f"directory:{row.id}:missing_source"
            expected[key] = {
                "benefit_id": None,
                "dataset": "department_directory",
                "alert_type": "missing_source",
                "severity": "critical",
                "message": f"{row.department_name} has no official directory source URL.",
                "metadata": metadata,
            }
        elif (
            row.source_last_verified is None
            or _aware(row.source_last_verified) < directory_cutoff
        ):
            key = f"directory:{row.id}:stale_source"
            expected[key] = {
                "benefit_id": None,
                "dataset": "department_directory",
                "alert_type": "stale_source",
                "severity": "critical",
                "message": (
                    f"{row.department_name} has not been checked within the "
                    f"{stale_days}-day directory freshness window."
                ),
                "metadata": metadata,
            }

    for key, payload in expected.items():
        alert = by_key.get(key)
        if alert is None:
            alert = SourceFreshnessAlert(
                id=new_id("fresh"),
                alert_key=key,
                benefit_id=payload["benefit_id"],
                dataset=payload["dataset"],
                alert_type=payload["alert_type"],
                severity=payload["severity"],
                status="open",
                message=payload["message"],
                first_seen_at=now,
                last_seen_at=now,
                safe_metadata=payload["metadata"],
            )
            db.add(alert)
            by_key[key] = alert
            continue
        alert.dataset = payload["dataset"]
        alert.alert_type = payload["alert_type"]
        alert.severity = payload["severity"]
        alert.message = payload["message"]
        alert.last_seen_at = now
        alert.safe_metadata = payload["metadata"]
        if alert.status == "resolved":
            alert.status = "open"
            alert.resolved_at = None
            alert.resolved_by = None

    for alert in alerts:
        if alert.alert_key not in expected and alert.status != "resolved":
            alert.status = "resolved"
            alert.resolved_at = now
            alert.resolved_by = "freshness-scan"

    db.flush()
    return db.exec(
        select(SourceFreshnessAlert)
        .where(SourceFreshnessAlert.status.in_(("open", "acknowledged")))
        .order_by(SourceFreshnessAlert.severity.desc(), SourceFreshnessAlert.last_seen_at.desc())
    ).all()


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
