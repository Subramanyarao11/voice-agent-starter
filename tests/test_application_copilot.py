"""Application Completion and Status Copilot API contract tests."""

from sahaayak_common import ApplicationCase, Benefit, session_scope
from sahaayak_contracts import VerificationStatus


def _set_review_status(benefit_id: str, verification_status: VerificationStatus) -> None:
    with session_scope() as db:
        benefit = db.get(Benefit, benefit_id)
        assert benefit is not None
        benefit.verification_status = verification_status
        db.add(benefit)


def test_application_case_materializes_checklist_and_records_safe_status(client, guest_session):
    _set_review_status("demo-csss-cus", VerificationStatus.HUMAN_VERIFIED)
    session = guest_session(language_code="en", state_code="KA")

    created = client.post(
        f"/api/sessions/{session['session_id']}/applications",
        json={"benefit_id": "demo-csss-cus", "application_channel": "official_portal"},
        headers=session["headers"],
    )
    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "draft"
    assert body["status_provenance"] == "system_derived"
    assert body["readiness_state"] == "not_ready"
    assert len(body["tasks"]) >= 2
    assert [event["status"] for event in body["status_events"]] == ["draft"]

    pack = client.post(
        f"/api/sessions/{session['session_id']}/applications/{body['id']}/packs/preview",
        headers=session["headers"],
    )
    assert pack.status_code == 200
    assert pack.headers["cache-control"] == "no-store, private"
    assert "Central Sector Scheme" in pack.json()["html"]
    assert pack.json()["content_sha256"]

    # Completing tasks works even when the citizen started from a benefit
    # detail page rather than saving the benefit first.
    for task in body["tasks"]:
        completed = client.post(
            f"/api/sessions/{session['session_id']}/tasks/{task['id']}",
            json={"status": "completed"},
            headers=session["headers"],
        )
        assert completed.status_code == 200

    submitted = client.post(
        f"/api/sessions/{session['session_id']}/applications/{body['id']}/status-events",
        json={
            "status": "submitted",
            "submission_date": "2026-08-09",
            "external_reference": " NSP / ACK-1234 ",
            "reason_code": "portal_submission",
        },
        headers=session["headers"],
    )
    assert submitted.status_code == 200
    updated = submitted.json()
    assert updated["status"] == "submitted"
    assert updated["status_provenance"] == "citizen_reported"
    assert updated["readiness_state"] == "ready"
    assert updated["external_reference_masked"] == "••••1234"
    assert updated["status_events"][-1]["external_reference_masked"] == "••••1234"

    action_required = client.post(
        f"/api/sessions/{session['session_id']}/applications/{body['id']}/status-events",
        json={"status": "action_required", "reason_code": "missing_document"},
        headers=session["headers"],
    )
    assert action_required.status_code == 200
    reminders = client.get(
        f"/api/sessions/{session['session_id']}/reminders",
        headers=session["headers"],
    )
    assert reminders.status_code == 200
    assert any(
        reminder["application_case_id"] == body["id"]
        and reminder["channel"] == "in_app"
        for reminder in reminders.json()
    )

    with session_scope() as db:
        case = db.get(ApplicationCase, body["id"])
        assert case is not None
        assert case.external_reference_ciphertext
        assert "ACK-1234" not in case.external_reference_ciphertext

    # Repeating the create call is safe and does not create a second journey.
    repeated = client.post(
        f"/api/sessions/{session['session_id']}/applications",
        json={"benefit_id": "demo-csss-cus"},
        headers=session["headers"],
    )
    assert repeated.status_code == 200
    assert repeated.json()["id"] == body["id"]


def test_application_start_requires_human_review_and_is_private(client, guest_session):
    _set_review_status("demo-pm-kisan", VerificationStatus.ILLUSTRATIVE)
    first = guest_session(language_code="en", state_code="KA")
    second = guest_session(language_code="en", state_code="KA")

    blocked = client.post(
        f"/api/sessions/{first['session_id']}/applications",
        json={"benefit_id": "demo-pm-kisan"},
        headers=first["headers"],
    )
    assert blocked.status_code == 409
    assert "human publication review" in blocked.json()["detail"]

    _set_review_status("demo-pm-kisan", VerificationStatus.HUMAN_VERIFIED)
    created = client.post(
        f"/api/sessions/{first['session_id']}/applications",
        json={"benefit_id": "demo-pm-kisan"},
        headers=first["headers"],
    )
    assert created.status_code == 201

    cross_session = client.get(
        f"/api/sessions/{second['session_id']}/applications/{created.json()['id']}",
        headers=second["headers"],
    )
    assert cross_session.status_code == 404
