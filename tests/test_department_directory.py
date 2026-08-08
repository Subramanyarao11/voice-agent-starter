"""Directory routing and review-gate tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from importlib import import_module

from sqlmodel import select

from sahaayak_common import (
    DepartmentDirectoryEntry,
    DepartmentDirectoryVersion,
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


def test_directory_expiry_disables_routing_and_creates_alert(client):
    entry_id = "directory-test-expired"
    with session_scope() as db:
        db.add(
            DepartmentDirectoryEntry(
                id=entry_id,
                entry_key=entry_id,
                state_code="KA",
                district_name="Mysuru",
                service_domain="citizen_support",
                pincode="570011",
                department_name="Expired Mysuru office",
                source_name="Mysuru district portal",
                source_url="https://mysore.nic.in/en/",
                source_last_verified=datetime.now(UTC),
                valid_until=datetime.now(UTC).date() - timedelta(days=1),
                approval_status="approved",
                is_active=True,
            )
        )

    try:
        with session_scope() as db:
            route = resolve_escalation_route(
                state_code="KA",
                domain=Domain.SCHEME,
                slots={SlotName.LOCATION: "570011"},
                db=db,
            )
            assert route.routing_source == "state_domain_fallback"

        response = client.get("/api/admin/freshness?stale_days=90")
        assert response.status_code == 200
        assert any(
            alert["dataset"] == "department_directory"
            and alert["alert_type"] == "expired"
            and alert["safe_metadata"]["directory_entry_id"] == entry_id
            for alert in response.json()["alerts"]
        )
        directory_report = next(
            report
            for report in response.json()["sources"]
            if report["dataset"] == "department_directory"
        )
        assert directory_report["expired_rows"] >= 1
    finally:
        with session_scope() as db:
            row = db.get(DepartmentDirectoryEntry, entry_id)
            if row is not None:
                db.delete(row)
            for alert in db.exec(select(SourceFreshnessAlert)).all():
                if alert.safe_metadata.get("directory_entry_id") == entry_id:
                    db.delete(alert)


def test_directory_demo_pack_has_two_districts_and_enriched_official_fields():
    import json
    from pathlib import Path

    payload = json.loads(
        (
            Path(__file__).parents[1]
            / "data"
            / "directory"
            / "demo"
            / "ka-two-districts.json"
        ).read_text(encoding="utf-8")
    )
    entries = payload["entries"]
    assert {entry["district_name"] for entry in entries} == {"Bengaluru Urban", "Mysuru"}
    assert len(entries) == 4
    for entry in entries:
        assert entry["source_url"].startswith("https://")
        assert entry["address"]
        assert entry["phone"]
        assert entry["email"]
        assert entry["working_hours"]
        assert entry["supported_languages"]
        assert entry["coverage_basis"] == "exact_pincode"
        assert entry["safe_metadata"]["demo_pack"] == "ka-two-districts-v1"


def test_directory_has_five_routing_scenarios_with_safe_fallbacks():
    now = datetime.now(UTC)
    entries = [
        _entry("directory-demo-exact", verified_at=now),
        DepartmentDirectoryEntry(
            id="directory-demo-prefix",
            entry_key="directory-demo-prefix",
            state_code="KA",
            district_name="Mysuru",
            service_domain="scheme",
            pincode_prefix="570",
            department_name="Mysuru prefix office",
            source_name="Mysuru district portal",
            source_url="https://mysore.nic.in/en/",
            source_last_verified=now,
            approval_status="approved",
            is_active=True,
        ),
        DepartmentDirectoryEntry(
            id="directory-demo-district",
            entry_key="directory-demo-district",
            state_code="KA",
            district_name="Mysuru",
            service_domain="scheme",
            department_name="Mysuru district office",
            source_name="Mysuru district portal",
            source_url="https://mysore.nic.in/en/",
            source_last_verified=now,
            approval_status="approved",
            is_active=True,
            priority=20,
        ),
        DepartmentDirectoryEntry(
            id="directory-demo-stale",
            entry_key="directory-demo-stale",
            state_code="KA",
            district_name="Bengaluru Urban",
            service_domain="scheme",
            pincode="560888",
            department_name="Stale Bengaluru office",
            source_name="Bengaluru Urban district portal",
            source_url="https://bengaluruurban.nic.in/en/",
            source_last_verified=now - timedelta(days=365),
            approval_status="approved",
            is_active=True,
        ),
        DepartmentDirectoryEntry(
            id="directory-demo-pending",
            entry_key="directory-demo-pending",
            state_code="KA",
            district_name="Bengaluru Urban",
            service_domain="scheme",
            pincode="560777",
            department_name="Pending Bengaluru office",
            source_name="Bengaluru Urban district portal",
            source_url="https://bengaluruurban.nic.in/en/",
            source_last_verified=now,
            approval_status="pending",
            is_active=False,
        ),
    ]
    with session_scope() as db:
        for entry in entries:
            db.add(entry)
        assert resolve_escalation_route(
            state_code="KA",
            domain=Domain.SCHEME,
            slots={SlotName.LOCATION: "560001"},
            db=db,
        ).directory_entry_id == "directory-demo-exact"
        assert resolve_escalation_route(
            state_code="KA",
            domain=Domain.SCHEME,
            slots={SlotName.LOCATION: "570123"},
            db=db,
        ).directory_entry_id == "directory-demo-prefix"
        assert resolve_escalation_route(
            state_code="KA",
            domain=Domain.SCHEME,
            slots={SlotName.LOCATION: "Mysuru"},
            db=db,
        ).directory_entry_id == "directory-demo-district"
        assert resolve_escalation_route(
            state_code="KA",
            domain=Domain.SCHEME,
            slots={SlotName.LOCATION: "560888"},
            db=db,
        ).routing_source == "state_domain_fallback"
        assert resolve_escalation_route(
            state_code="KA",
            domain=Domain.SCHEME,
            slots={SlotName.LOCATION: "560777"},
            db=db,
        ).routing_source == "state_domain_fallback"
        for entry in entries:
            db.delete(entry)


def test_admin_directory_edit_version_and_rollback_flow(client):
    entry_id = "directory-test-governance"
    now = datetime.now(UTC)
    with session_scope() as db:
        db.add(
            DepartmentDirectoryEntry(
                id=entry_id,
                entry_key=entry_id,
                state_code="KA",
                district_name="Bengaluru Urban",
                service_domain="citizen_support",
                pincode="560009",
                department_name="Demo Bengaluru office",
                address="Original official address",
                phone="080-11111111",
                source_name="Bengaluru Urban district portal",
                source_url="https://bengaluruurban.nic.in/en/contact-us/",
                source_last_verified=now,
                approval_status="pending",
                is_active=False,
            )
        )

    def cleanup() -> None:
        with session_scope() as db:
            for version in db.exec(
                select(DepartmentDirectoryVersion).where(
                    DepartmentDirectoryVersion.entry_id == entry_id
                )
            ).all():
                db.delete(version)
            row = db.get(DepartmentDirectoryEntry, entry_id)
            if row is not None:
                db.delete(row)

    try:
        approved = client.post(
            f"/api/admin/departments/{entry_id}/approve",
            json={"reason": "Verified the official district source"},
        )
        assert approved.status_code == 200
        current = approved.json()
        assert current["content_revision"] >= 2

        edited = client.patch(
            f"/api/admin/departments/{entry_id}",
            json={
                "expected_revision": current["content_revision"],
                "state_code": "KA",
                "district_code": "BLURU",
                "district_name": "Bengaluru Urban",
                "service_domain": "citizen_support",
                "pincode": "560009",
                "pincode_prefix": "",
                "department_code": "DC-KA-BLRU",
                "department_name": "Edited Demo Bengaluru Office",
                "help_centre_name": "Demo help centre",
                "address": "Edited official address",
                "phone": "080-22211292",
                "email": "dcurban@nic.in",
                "website_url": "https://bengaluruurban.nic.in",
                "source_name": "Bengaluru Urban district portal",
                "source_url": "https://bengaluruurban.nic.in/en/contact-us/",
                "source_record_id": "contact-us",
                "source_last_verified": now.isoformat(),
                "valid_until": None,
                "working_hours": "Not published",
                "supported_languages": ["en"],
                "coverage_basis": "exact_pincode",
                "priority": 10,
                "reason": "Corrected the office contact details",
            },
        )
        assert edited.status_code == 200
        assert edited.json()["approval_status"] == "pending"
        edit_revision = edited.json()["content_revision"]

        history = client.get(f"/api/admin/departments/{entry_id}/versions")
        assert history.status_code == 200
        assert {version["action"] for version in history.json()["versions"]} >= {
            "baseline",
            "approve",
            "edit",
        }

        rollback = client.post(
            f"/api/admin/departments/{entry_id}/rollback",
            json={"version": 2, "reason": "Restore the last approved contact record"},
        )
        assert rollback.status_code == 200
        assert rollback.json()["content_revision"] > edit_revision
        assert rollback.json()["approval_status"] == "pending"
        assert rollback.json()["is_active"] is False

        reapproved = client.post(
            f"/api/admin/departments/{entry_id}/approve",
            json={"reason": "Re-approved the restored official contact record"},
        )
        assert reapproved.status_code == 200
        deactivated = client.post(
            f"/api/admin/departments/{entry_id}/deactivate",
            json={"reason": "Deactivate after the rollback demonstration"},
        )
        assert deactivated.status_code == 200
        assert deactivated.json()["is_active"] is False
    finally:
        cleanup()
