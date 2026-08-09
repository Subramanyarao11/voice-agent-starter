"""Guest-to-citizen migration requires both server-owned session proofs."""

from sahaayak_common import SavedBenefit, UserSession, session_scope


def test_guest_saved_benefit_migration_is_previewed_confirmed_and_idempotent(
    client, guest_session
) -> None:
    guest = guest_session()
    citizen_headers = {"Authorization": "Bearer test-citizen-migration"}
    household_response = client.post(
        "/api/households",
        headers=citizen_headers,
        json={
            "label": "Migration household",
            "state_code": "KA",
            "include_self": True,
            "consent_persistence": True,
        },
    )
    assert household_response.status_code == 201, household_response.text
    household_id = household_response.json()["id"]

    saved = client.post(
        f"/api/sessions/{guest['session_id']}/saved-benefits",
        headers=guest["headers"],
        json={"benefit_id": "demo-csss-cus"},
    )
    assert saved.status_code == 201, saved.text
    saved_id = saved.json()["id"]

    preview = client.post(
        f"/api/sessions/{guest['session_id']}/migration/preview",
        headers={
            **citizen_headers,
            "X-Guest-Session-Token": guest["access_token"],
        },
        json={
            "saved_benefit_ids": [saved_id],
            "target_household_id": household_id,
            "idempotency_key": "migration-test-001",
        },
    )
    assert preview.status_code == 201, preview.text
    preview_body = preview.json()
    assert preview_body["status"] == "preview"
    assert preview_body["items"][0]["id"] == saved_id
    assert "access_token" not in preview.text

    committed = client.post(
        f"/api/sessions/{guest['session_id']}/migration?migration_id={preview_body['id']}",
        headers={
            **citizen_headers,
            "X-Guest-Session-Token": guest["access_token"],
        },
        json={"confirm": True},
    )
    assert committed.status_code == 200, committed.text
    assert committed.json()["status"] == "completed"
    assert committed.json()["source_deletion_status"] == "reowned"

    guest_saved = client.get(
        f"/api/sessions/{guest['session_id']}/saved-benefits",
        headers=guest["headers"],
    )
    assert guest_saved.status_code == 200
    assert guest_saved.json() == []

    with session_scope() as db:
        moved = db.get(SavedBenefit, saved_id)
        source = db.get(UserSession, guest["session_id"])
        assert moved is not None
        assert moved.session_id != guest["session_id"]
        assert moved.citizen_account_id is not None
        assert source is not None
        assert source.auth_mode == "guest"

    replay = client.post(
        f"/api/sessions/{guest['session_id']}/migration?migration_id={preview_body['id']}",
        headers={
            **citizen_headers,
            "X-Guest-Session-Token": guest["access_token"],
        },
        json={"confirm": True},
    )
    assert replay.status_code == 200
    assert replay.json()["status"] == "completed"


def test_guest_migration_rejects_missing_or_wrong_guest_proof(client, guest_session) -> None:
    guest = guest_session()
    citizen_headers = {"Authorization": "Bearer test-citizen-migration-proof"}
    household_response = client.post(
        "/api/households",
        headers=citizen_headers,
        json={"consent_persistence": True, "include_self": True},
    )
    assert household_response.status_code == 201
    saved = client.post(
        f"/api/sessions/{guest['session_id']}/saved-benefits",
        headers=guest["headers"],
        json={"benefit_id": "demo-csss-cus"},
    )
    assert saved.status_code == 201
    payload = {
        "saved_benefit_ids": [saved.json()["id"]],
        "target_household_id": household_response.json()["id"],
        "idempotency_key": "migration-proof-001",
    }
    missing = client.post(
        f"/api/sessions/{guest['session_id']}/migration/preview",
        headers=citizen_headers,
        json=payload,
    )
    assert missing.status_code == 401

    wrong = client.post(
        f"/api/sessions/{guest['session_id']}/migration/preview",
        headers={**citizen_headers, "X-Guest-Session-Token": "wrong-token"},
        json=payload,
    )
    assert wrong.status_code == 401
