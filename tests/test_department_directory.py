"""Directory routing and review-gate tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from importlib import import_module

from sqlmodel import select

from sahaayak_common import (
    DepartmentDirectoryEntry,
    SourceFreshnessAlert,
    resolve_escalation_route,
    session_scope,
)
from sahaayak_contracts import Domain, SlotName


def _entry(entry_id: str, *, verified_at: datetime) -> DepartmentDirectoryEntry:
    return DepartmentDirectoryEntry(
        id=entry_id,
        entry_key=entry_id,
        state_code="KA",
        district_name="Bengaluru Urban",
        service_domain="scheme",
        pincode="560001",
        department_name="Bengaluru Urban Social Welfare Office",
        source_name="Bengaluru Urban district portal",
        source_url="https://bengaluruurban.nic.in/",
        source_last_verified=verified_at,
        approval_status="approved",
        is_active=True,
    )


def test_directory_prefers_exact_pincode_and_rejects_stale_source():
    entry_id = "directory-test-exact"
    with session_scope() as db:
        db.add(_entry(entry_id, verified_at=datetime.now(UTC)))
        route = resolve_escalation_route(
            state_code="KA",
            domain=Domain.SCHEME,
            slots={SlotName.LOCATION: "560001"},
            db=db,
        )
        assert route.routing_source == "authoritative_directory"
        assert route.directory_entry_id == entry_id
        assert route.source_url.startswith("https://")

        row = db.get(DepartmentDirectoryEntry, entry_id)
        assert row is not None
        row.source_last_verified = datetime.now(UTC) - timedelta(days=365)
        db.add(row)
        stale_route = resolve_escalation_route(
            state_code="KA",
            domain=Domain.SCHEME,
            slots={SlotName.LOCATION: "560001"},
            db=db,
        )
        assert stale_route.routing_source == "state_domain_fallback"

    with session_scope() as db:
        row = db.get(DepartmentDirectoryEntry, entry_id)
        if row is not None:
            db.delete(row)


def test_statewide_directory_row_is_a_safe_last_directory_match():
    entry_id = "directory-test-statewide"
    with session_scope() as db:
        db.add(
            DepartmentDirectoryEntry(
                id=entry_id,
                entry_key=entry_id,
                state_code="KA",
                district_name="",
                service_domain="citizen_support",
                department_name="Karnataka Social Welfare Department",
                source_name="India.gov.in Integrated Government Online Directory",
                source_url="https://www.india.gov.in/directory/contact-directory/state-uts/ka",
                source_last_verified=datetime.now(UTC),
                approval_status="approved",
                is_active=True,
            )
        )
        route = resolve_escalation_route(
            state_code="KA",
            domain=Domain.SCHEME,
            slots={SlotName.LOCATION: "Mysuru"},
            db=db,
        )
        assert route.routing_source == "authoritative_directory"
        assert route.directory_entry_id == entry_id

    with session_scope() as db:
        row = db.get(DepartmentDirectoryEntry, entry_id)
        if row is not None:
            db.delete(row)


def test_unchanged_source_refresh_keeps_directory_approval():
    importer = import_module("scripts.16_import_department_directory")
    row = _entry("directory-test-refresh", verified_at=datetime.now(UTC))
    row.approval_status = "approved"
    row.is_active = True
    raw = {
        "state_code": "KA",
        "district_name": "Bengaluru Urban",
        "service_domain": "scheme",
        "pincode": "560001",
        "department_name": row.department_name,
        "source_name": row.source_name,
        "source_url": row.source_url,
        "source_last_verified": (datetime.now(UTC) + timedelta(minutes=1)).isoformat(),
        "safe_metadata": {"source_snapshot_hash": "same-source"},
    }
    row.safe_metadata = {"source_snapshot_hash": "same-source"}
    data = importer._normalise(raw, index=1)
    assert importer._update_row(row, data) is False
    assert row.approval_status == "approved"
    assert row.is_active is True


def test_admin_directory_approval_and_deactivation_are_audited(client):
    entry_id = "directory-test-admin"
    with session_scope() as db:
        db.add(
            DepartmentDirectoryEntry(
                id=entry_id,
                entry_key=entry_id,
                state_code="KA",
                district_name="Mysuru",
                service_domain="citizen_support",
                pincode_prefix="570",
                department_name="Mysuru Citizen Support Office",
                source_name="Mysuru district portal",
                source_url="https://mysuru.nic.in/",
                source_last_verified=datetime.now(UTC),
                approval_status="pending",
                is_active=False,
            )
        )

    try:
        pending = client.get("/api/admin/departments?status=pending")
        assert pending.status_code == 200
        assert any(item["id"] == entry_id for item in pending.json()["entries"])
        assert "coverage_by_state" in pending.json()
        assert "source_counts" in pending.json()

        approved = client.post(
            f"/api/admin/departments/{entry_id}/approve",
            json={"reason": "Verified the current official district directory"},
        )
        assert approved.status_code == 200
        assert approved.json()["approval_status"] == "approved"
        assert approved.json()["is_active"] is True

        deactivated = client.post(
            f"/api/admin/departments/{entry_id}/deactivate",
            json={"reason": "Remove while the department source is being refreshed"},
        )
        assert deactivated.status_code == 200
        assert deactivated.json()["is_active"] is False
    finally:
        with session_scope() as db:
            row = db.get(DepartmentDirectoryEntry, entry_id)
            if row is not None:
                db.delete(row)


def test_directory_freshness_alerts_are_scanned_with_other_sources(client):
    entry_id = "directory-test-stale-alert"
    with session_scope() as db:
        db.add(
            DepartmentDirectoryEntry(
                id=entry_id,
                entry_key=entry_id,
                state_code="KA",
                district_name="Mysuru",
                service_domain="citizen_support",
                department_name="Mysuru Citizen Support Office",
                source_name="Mysuru district portal",
                source_url="https://mysuru.nic.in/",
                source_last_verified=datetime.now(UTC) - timedelta(days=400),
                approval_status="approved",
                is_active=True,
            )
        )

    try:
        response = client.get("/api/admin/freshness?stale_days=90")
        assert response.status_code == 200
        assert any(
            alert["dataset"] == "department_directory"
            and alert["safe_metadata"]["directory_entry_id"] == entry_id
            for alert in response.json()["alerts"]
        )
    finally:
        with session_scope() as db:
            row = db.get(DepartmentDirectoryEntry, entry_id)
            if row is not None:
                db.delete(row)
            for alert in db.exec(select(SourceFreshnessAlert)).all():
                if alert.safe_metadata.get("directory_entry_id") == entry_id:
                    db.delete(alert)
