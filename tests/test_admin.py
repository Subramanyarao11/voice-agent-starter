"""Admin boundary and platform-operations contract tests."""

from __future__ import annotations

from datetime import date


def test_admin_rejects_an_invalid_workforce_token(client):
    response = client.get("/api/admin/overview", headers={"X-Admin-Token": "wrong-token"})
    assert response.status_code == 403


def test_admin_overview_and_conversations_are_aggregated_and_redacted(client):
    caller = "+919876543210"
    client.post(
        "/api/turns",
        json={
            "caller_id": caller,
            "text": "I need a scholarship",
            "language_code": "en",
            "state_code": "KA",
        },
    )

    overview = client.get("/api/admin/overview")
    assert overview.status_code == 200
    body = overview.json()
    assert body["traffic"]["turns"] >= 1
    assert "providers" in body
    assert caller not in overview.text

    conversations = client.get("/api/admin/conversations")
    assert conversations.status_code == 200
    items = conversations.json()["items"]
    assert any(item["turn_count"] >= 1 for item in items)
    assert caller not in conversations.text
    assert "profile" not in conversations.text

    events = client.get("/api/admin/telemetry/events?event_type=turn")
    assert events.status_code == 200
    assert any(event["route"] == "/api/turns" for event in events.json())


def test_admin_benefit_review_is_audited(client):
    from sahaayak_common import Benefit, session_scope
    from sahaayak_contracts import Domain

    benefit_id = "admin-review-test"
    with session_scope() as db:
        db.add(
            Benefit(
                id=benefit_id,
                domain=Domain.SCHEME,
                name="Admin review test",
                state_code="KA",
                source_document_url="https://example.test/admin-review",
                source_url="https://example.test/admin-review",
                last_verified_date=date.today(),
                is_active=False,
            )
        )

    try:
        response = client.post(
            f"/api/admin/benefits/{benefit_id}/review",
            json={
                "verification_status": "human_verified",
                "activate": True,
                "reason": "Reviewed against the source document",
            },
        )
        assert response.status_code == 200
        assert response.json()["verification_status"] == "human_verified"
        assert response.json()["is_active"] is True

        audit = client.get("/api/admin/audit-events?action=benefit.review")
        assert audit.status_code == 200
        assert any(event["target_id"] == benefit_id for event in audit.json())
    finally:
        with session_scope() as db:
            row = db.get(Benefit, benefit_id)
            if row is not None:
                db.delete(row)
