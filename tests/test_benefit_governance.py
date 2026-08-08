"""Benefit editing, immutable history, rollback, and freshness alert contracts."""

from datetime import UTC, date, datetime, timedelta

from sahaayak_common import Benefit, BenefitVersion, SourceFreshnessAlert, session_scope
from sahaayak_contracts import Domain, VerificationStatus


def _benefit(benefit_id: str, *, verified_date: date | None = None) -> Benefit:
    return Benefit(
        id=benefit_id,
        domain=Domain.SCHEME,
        name="Governance test benefit",
        state_code="KA",
        description="Original description",
        eligibility_initial={"age_min": 18},
        documents_required=["Identity document"],
        application_process="Apply on the official portal.",
        source_url="https://example.test/benefit",
        source_document_url="https://example.test/benefit",
        source_title="Official test source",
        last_verified_date=verified_date or date.today(),
        verification_status=VerificationStatus.HUMAN_VERIFIED,
        verified_by="seed-reviewer",
        verified_at=datetime.now(UTC),
        is_active=True,
    )


def _cleanup(benefit_id: str) -> None:
    with session_scope() as db:
        for alert in db.query(SourceFreshnessAlert).filter(
            SourceFreshnessAlert.benefit_id == benefit_id
        ).all():
            db.delete(alert)
        for version in db.query(BenefitVersion).filter(
            BenefitVersion.benefit_id == benefit_id
        ).all():
            db.delete(version)
        row = db.get(Benefit, benefit_id)
        if row is not None:
            db.delete(row)


def test_benefit_edit_history_review_and_rollback(client):
    benefit_id = "governance-edit-test"
    with session_scope() as db:
        db.add(_benefit(benefit_id))

    try:
        edited = client.put(
            f"/api/admin/benefits/{benefit_id}",
            json={
                "expected_revision": 0,
                "domain": "scheme",
                "name": "Edited governance benefit",
                "state_code": "KA",
                "category": "education",
                "description": "Edited description",
                "eligibility_initial": {"age_min": 21},
                "benefits_text": "Edited support",
                "documents_required": ["Identity document", "Income certificate"],
                "application_process": "Use the edited official application steps.",
                "source_url": "https://example.test/benefit-edited",
                "source_title": "Edited official source",
                "source_document_url": "https://example.test/benefit-edited",
                "source_excerpt": "Edited source evidence",
                "localized_summary": {"en": "Edited summary"},
                "reason": "Corrected the public source fields",
            },
        )
        assert edited.status_code == 200
        assert edited.json()["verification_status"] == "needs_review"
        assert edited.json()["is_active"] is False
        assert edited.json()["content_revision"] == 2

        versions = client.get(f"/api/admin/benefits/{benefit_id}/versions")
        assert versions.status_code == 200
        assert [row["action"] for row in versions.json()["versions"]] == ["edit", "baseline"]

        reviewed = client.post(
            f"/api/admin/benefits/{benefit_id}/review",
            json={
                "verification_status": "human_verified",
                "activate": True,
                "reason": "Checked the edited official source",
            },
        )
        assert reviewed.status_code == 200
        assert reviewed.json()["content_revision"] == 3
        assert reviewed.json()["is_active"] is True

        stale_update = client.put(
            f"/api/admin/benefits/{benefit_id}",
            json={
                "expected_revision": 2,
                "domain": "scheme",
                "name": "Should be rejected",
                "reason": "Stale browser edit",
            },
        )
        assert stale_update.status_code == 409

        second_edit = client.put(
            f"/api/admin/benefits/{benefit_id}",
            json={
                "expected_revision": 3,
                "domain": "scheme",
                "name": "Bad later edit",
                "state_code": "KA",
                "description": "This change should be rolled back",
                "eligibility_initial": {"age_min": 21},
                "source_url": "https://example.test/benefit-edited",
                "source_document_url": "https://example.test/benefit-edited",
                "reason": "Simulate a later content edit",
            },
        )
        assert second_edit.status_code == 200
        assert second_edit.json()["content_revision"] == 4

        rolled_back = client.post(
            f"/api/admin/benefits/{benefit_id}/rollback",
            json={"version": 3, "reason": "Restore the approved public version"},
        )
        assert rolled_back.status_code == 200
        assert rolled_back.json()["name"] == "Edited governance benefit"
        assert rolled_back.json()["verification_status"] == "human_verified"
        assert rolled_back.json()["is_active"] is True
        assert rolled_back.json()["content_revision"] == 5

        versions = client.get(f"/api/admin/benefits/{benefit_id}/versions").json()["versions"]
        assert versions[0]["action"] == "rollback"
        assert len(versions) == 5
    finally:
        _cleanup(benefit_id)


def test_source_freshness_alerts_are_deduplicated_and_resolved(client):
    benefit_id = "governance-freshness-test"
    old_date = date.today() - timedelta(days=120)
    with session_scope() as db:
        db.add(_benefit(benefit_id, verified_date=old_date))

    try:
        first = client.get("/api/admin/freshness?stale_days=90")
        assert first.status_code == 200
        alerts = [alert for alert in first.json()["alerts"] if alert["benefit_id"] == benefit_id]
        assert len(alerts) == 1
        assert alerts[0]["alert_type"] == "stale_source"

        second = client.get("/api/admin/freshness?stale_days=90")
        alerts_again = [
            alert for alert in second.json()["alerts"] if alert["benefit_id"] == benefit_id
        ]
        assert [alert["id"] for alert in alerts_again] == [alerts[0]["id"]]

        acknowledged = client.post(
            f"/api/admin/freshness/alerts/{alerts[0]['id']}",
            json={"status": "acknowledged", "reason": "Source refresh is scheduled"},
        )
        assert acknowledged.status_code == 200
        assert acknowledged.json()["status"] == "acknowledged"

        with session_scope() as db:
            row = db.get(Benefit, benefit_id)
            assert row is not None
            row.last_verified_date = date.today()
            db.add(row)

        resolved = client.get("/api/admin/freshness?stale_days=90")
        assert resolved.status_code == 200
        with session_scope() as db:
            alert = db.query(SourceFreshnessAlert).filter_by(
                benefit_id=benefit_id,
                alert_type="stale_source",
            ).one()
            assert alert.status == "resolved"
            assert alert.resolved_by == "freshness-scan"
    finally:
        _cleanup(benefit_id)
