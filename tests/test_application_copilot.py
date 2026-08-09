"""Application Completion and Status Copilot API contract tests."""

from sqlmodel import select

from sahaayak_common import (
    ApplicationCase,
    ApplicationFieldValue,
    ApplicationOutcomeFeedback,
    Benefit,
    session_scope,
)
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

    dashboard = client.get("/api/admin/applications/summary?hours=168")
    assert dashboard.status_code == 200
    assert dashboard.json()["total_cases"] >= 1
    assert dashboard.json()["cases_by_status"]["action_required"] >= 1

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


def test_application_snapshot_surfaces_current_benefit_changes(client, guest_session):
    _set_review_status("demo-ka-vidyasiri", VerificationStatus.HUMAN_VERIFIED)
    session = guest_session(language_code="en", state_code="KA")
    created = client.post(
        f"/api/sessions/{session['session_id']}/applications",
        json={"benefit_id": "demo-ka-vidyasiri"},
        headers=session["headers"],
    )
    assert created.status_code == 201
    application_id = created.json()["id"]

    with session_scope() as db:
        benefit = db.get(Benefit, "demo-ka-vidyasiri")
        assert benefit is not None
        benefit.documents_required = [*benefit.documents_required, "Updated residence proof"]
        benefit.content_revision += 1
        db.add(benefit)

    refreshed = client.get(
        f"/api/sessions/{session['session_id']}/applications/{application_id}",
        headers=session["headers"],
    )
    assert refreshed.status_code == 200
    changed = refreshed.json()
    assert changed["benefit_change_state"] == "action_required"
    assert "Required documents changed." in changed["benefit_change_items"]
    assert changed["current_benefit_revision"] == changed["benefit_revision"] + 1


def test_reviewed_application_fields_are_confirmed_encrypted_and_versioned(client, guest_session):
    _set_review_status("demo-csss-cus", VerificationStatus.HUMAN_VERIFIED)
    session = guest_session(language_code="en", state_code="KA")
    created = client.post(
        f"/api/sessions/{session['session_id']}/applications",
        json={"benefit_id": "demo-csss-cus"},
        headers=session["headers"],
    )
    assert created.status_code == 201
    application_id = created.json()["id"]

    definition = client.post(
        "/api/admin/benefits/demo-csss-cus/application-fields",
        json={
            "field_key": "annual_income",
            "label": {"en": "Annual family income"},
            "help_text": {"en": "Use the latest verified amount."},
            "data_type": "integer",
            "validation": {"min_length": 1},
            "required": True,
            "sensitivity": "confidential",
            "source_excerpt": "Applicant must provide annual family income.",
            "source_url": "https://scholarships.gov.in/official-notice",
            "reason": "Add the published income field for the application workspace.",
        },
    )
    assert definition.status_code == 201
    assert definition.json()["review_status"] == "pending"
    reviewed = client.post(
        "/api/admin/benefits/demo-csss-cus/application-fields/annual_income/review",
        json={"status": "approved", "reason": "Source and terminology checked."},
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["revision"] == 2

    fields = client.get(
        f"/api/sessions/{session['session_id']}/applications/{application_id}/fields",
        headers=session["headers"],
    )
    assert fields.status_code == 200
    assert fields.json()[0]["value"] is None

    saved = client.put(
        f"/api/sessions/{session['session_id']}/applications/{application_id}/fields/annual_income",
        json={"value": "250000"},
        headers=session["headers"],
    )
    assert saved.status_code == 200
    field_value = saved.json()[0]["value"]
    assert field_value["masked_value"] == "••••0000"
    assert field_value["revision"] == 1

    updated = client.put(
        f"/api/sessions/{session['session_id']}/applications/{application_id}/fields/annual_income",
        json={"value": "300000", "expected_revision": 1},
        headers=session["headers"],
    )
    assert updated.status_code == 200
    assert updated.json()[0]["value"]["revision"] == 2

    stale = client.put(
        f"/api/sessions/{session['session_id']}/applications/{application_id}/fields/annual_income",
        json={"value": "350000", "expected_revision": 1},
        headers=session["headers"],
    )
    assert stale.status_code == 409

    with session_scope() as db:
        value = db.exec(
            select(ApplicationFieldValue).where(
                ApplicationFieldValue.application_case_id == application_id
            )
        ).one()
        assert "250000" not in value.value_ciphertext
        assert "250000" not in value.masked_value


def test_application_requirements_and_terminal_outcome_are_separate_from_status(
    client, guest_session
):
    _set_review_status("demo-csss-cus", VerificationStatus.HUMAN_VERIFIED)
    session = guest_session(language_code="en", state_code="KA")
    created = client.post(
        f"/api/sessions/{session['session_id']}/applications",
        json={"benefit_id": "demo-csss-cus"},
        headers=session["headers"],
    )
    assert created.status_code == 201
    application_id = created.json()["id"]

    requirements = client.get(
        f"/api/sessions/{session['session_id']}/applications/{application_id}/requirements",
        headers=session["headers"],
    )
    assert requirements.status_code == 200
    requirement = requirements.json()[0]
    assert requirement["requirement_key"]
    assert requirement["status"] == "missing"

    not_applicable = client.post(
        f"/api/sessions/{session['session_id']}/applications/{application_id}/requirements/{requirement['requirement_key']}/status",
        json={"status": "not_applicable"},
        headers=session["headers"],
    )
    assert not_applicable.status_code == 400

    for next_status in ("submitted", "approved", "delivered"):
        status_response = client.post(
            f"/api/sessions/{session['session_id']}/applications/{application_id}/status-events",
            json={"status": next_status},
            headers=session["headers"],
        )
        assert status_response.status_code == 200

    outcome = client.post(
        f"/api/sessions/{session['session_id']}/applications/{application_id}/outcome",
        json={
            "outcome": "received",
            "reason_code": "confirmed_by_citizen",
            "free_text": "The scholarship was received in the bank account.",
            "satisfaction_score": 5,
            "consent_for_evaluation": True,
        },
        headers=session["headers"],
    )
    assert outcome.status_code == 200
    assert outcome.json()["outcome"] == "received"
    assert outcome.json()["has_comment"] is True

    with session_scope() as db:
        feedback = db.exec(
            select(ApplicationOutcomeFeedback).where(
                ApplicationOutcomeFeedback.application_case_id == application_id
            )
        ).one()
        assert "scholarship was received" not in (feedback.free_text_ciphertext or "")
