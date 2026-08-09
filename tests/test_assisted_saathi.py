"""Contract tests for the consent-bound Assisted Saathi foundation."""

from sahaayak_common import AssistanceSession, session_scope


def _citizen(token: str = "test-citizen-saathi") -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_invitation_is_hashed_and_requires_citizen_consent(client) -> None:
    citizen_headers = _citizen()
    created = client.post(
        "/api/assistance/invitations",
        headers=citizen_headers,
        json={
            "purpose": "prepare_application",
            "data_categories": ["public_catalog", "application_requirements"],
            "locale": "kn",
        },
    )
    assert created.status_code == 201
    invitation = created.json()
    token = invitation["invitation_token"]

    with session_scope() as db:
        row = db.get(AssistanceSession, invitation["id"])
        assert row is not None
        assert row.invitation_token_hash != token
        assert len(row.invitation_token_hash or "") == 64
        assert row.status == "invited"

    before_redeem = client.get(
        f"/api/assistant/sessions/{invitation['id']}",
        headers={"X-Admin-Token": "test-admin-token"},
    )
    assert before_redeem.status_code == 404

    premature_consent = client.post(
        f"/api/assistance/invitations/{invitation['id']}/consent",
        headers=citizen_headers,
        json={"confirm": True},
    )
    assert premature_consent.status_code == 409

    redeemed = client.post(
        "/api/assistant/invitations/redeem",
        headers={"X-Admin-Token": "test-admin-token"},
        json={"invitation_token": token},
    )
    assert redeemed.status_code == 200
    assert redeemed.json()["status"] == "awaiting_citizen_consent"

    pending_projection = client.get(
        f"/api/assistant/sessions/{invitation['id']}",
        headers={"X-Admin-Token": "test-admin-token"},
    )
    assert pending_projection.status_code == 200
    assert pending_projection.json()["projection"] == {}

    consented = client.post(
        f"/api/assistance/invitations/{invitation['id']}/consent",
        headers=citizen_headers,
        json={"confirm": True, "locale": "kn"},
    )
    assert consented.status_code == 200
    assert consented.json()["status"] == "active"

    projection = client.get(
        f"/api/assistant/sessions/{invitation['id']}",
        headers={"X-Admin-Token": "test-admin-token"},
    )
    assert projection.status_code == 200
    assert projection.json()["projection"]["live_data_required"] is True
    assert "application_requirements" in projection.json()["projection"]["data_categories"]


def test_assistance_action_requires_confirmation_and_is_idempotent(client) -> None:
    citizen_headers = _citizen("test-citizen-saathi-actions")
    created = client.post(
        "/api/assistance/invitations",
        headers=citizen_headers,
        json={"purpose": "contact_department"},
    )
    assert created.status_code == 201
    invitation = created.json()
    token = invitation["invitation_token"]

    assert client.post(
        "/api/assistant/invitations/redeem",
        json={"invitation_token": token},
    ).status_code == 200
    assert client.post(
        f"/api/assistance/invitations/{invitation['id']}/consent",
        headers=citizen_headers,
        json={"confirm": True},
    ).status_code == 200

    draft = client.post(
        f"/api/assistant/sessions/{invitation['id']}/draft-actions",
        json={
            "action_key": "contact_department",
            "target_type": "department",
            "target_id": "directory-demo-ka-001",
            "preview_code": "department_review",
            "idempotency_key": "assist-action-contact-001",
        },
    )
    assert draft.status_code == 201
    action = draft.json()

    blocked = client.post(
        f"/api/assistant/sessions/{invitation['id']}/actions/{action['id']}/execute",
    )
    assert blocked.status_code == 409

    confirmed = client.post(
        f"/api/assistance/sessions/{invitation['id']}/actions/{action['id']}/confirm",
        headers=citizen_headers,
        json={"confirm": True},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["stage"] == "citizen_confirmed"

    executed = client.post(
        f"/api/assistant/sessions/{invitation['id']}/actions/{action['id']}/execute",
    )
    assert executed.status_code == 200
    assert executed.json()["stage"] == "executed"

    duplicate = client.post(
        f"/api/assistant/sessions/{invitation['id']}/draft-actions",
        json={
            "action_key": "contact_department",
            "target_type": "department",
            "target_id": "directory-demo-ka-001",
            "preview_code": "department_review",
            "idempotency_key": "assist-action-contact-001",
        },
    )
    assert duplicate.status_code == 201
    assert duplicate.json()["id"] == action["id"]

    receipt = client.post(
        f"/api/assistant/sessions/{invitation['id']}/complete",
    )
    assert receipt.status_code == 200
    assert receipt.json()["status"] == "completed"
    assert receipt.json()["actions"][0]["stage"] == "executed"


def test_revoke_stops_helper_projection(client) -> None:
    citizen_headers = _citizen("test-citizen-saathi-revoke")
    created = client.post(
        "/api/assistance/invitations",
        headers=citizen_headers,
        json={"purpose": "discover_benefits"},
    )
    invitation = created.json()
    assert client.post(
        "/api/assistant/invitations/redeem",
        json={"invitation_token": invitation["invitation_token"]},
    ).status_code == 200
    assert client.post(
        f"/api/assistance/invitations/{invitation['id']}/consent",
        headers=citizen_headers,
        json={"confirm": True},
    ).status_code == 200

    revoked = client.post(
        f"/api/assistance/sessions/{invitation['id']}/revoke",
        headers=citizen_headers,
    )
    assert revoked.status_code == 200
    assert revoked.json()["status"] == "revoked"

    helper_view = client.get(f"/api/assistant/sessions/{invitation['id']}")
    assert helper_view.status_code == 200
    assert helper_view.json()["status"] == "revoked"
    assert helper_view.json()["projection"] == {}

    action = client.post(
        f"/api/assistant/sessions/{invitation['id']}/draft-actions",
        json={
            "action_key": "review_public_benefit",
            "preview_code": "blocked_after_revoke",
            "idempotency_key": "assist-action-revoked-001",
        },
    )
    assert action.status_code == 409
