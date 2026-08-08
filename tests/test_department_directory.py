"""Directory routing and review-gate tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sahaayak_common import DepartmentDirectoryEntry, resolve_escalation_route, session_scope
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
