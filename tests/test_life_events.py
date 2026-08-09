"""Citizen-confirmed lifecycle events trigger the governed Radar matcher."""


def _headers(token: str = "test-citizen-life-events") -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_life_event_is_encrypted_redacted_and_recalculates_radar(client) -> None:
    headers = _headers()
    household = client.post(
        "/api/households",
        headers=headers,
        json={
            "label": "Life event test",
            "state_code": "KA",
            "include_self": True,
            "consent_persistence": True,
            "consent_personalization": True,
        },
    )
    assert household.status_code == 201
    household_id = household.json()["id"]
    member_id = client.get(
        f"/api/households/{household_id}/members", headers=headers
    ).json()[0]["id"]

    created = client.post(
        f"/api/households/{household_id}/life-events",
        headers=headers,
        json={
            "household_member_id": member_id,
            "event_key": "started_education",
            "occurred_precision": "month",
            "attributes": {"education_level": "higher_secondary"},
            "confirm": True,
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["radar_recalculated"] is True
    assert body["event"]["event_key"] == "started_education"
    assert body["event"]["attribute_keys"] == ["education_level"]
    assert "higher_secondary" not in created.text

    listed = client.get(
        f"/api/households/{household_id}/life-events", headers=headers
    )
    assert listed.status_code == 200
    assert listed.json()[0]["status"] == "active"

    corrected = client.patch(
        f"/api/households/{household_id}/life-events/{body['event']['id']}",
        headers=headers,
        json={
            "household_member_id": member_id,
            "event_key": "lost_job",
            "attributes": {"income_band": "low"},
            "confirm": True,
        },
    )
    assert corrected.status_code == 200, corrected.text
    corrected_body = corrected.json()
    assert corrected_body["event"]["supersedes_event_id"] == body["event"]["id"]
    assert corrected_body["event"]["attribute_keys"] == ["income_band"]

    removed = client.delete(
        f"/api/households/{household_id}/life-events/{corrected_body['event']['id']}",
        headers=headers,
    )
    assert removed.status_code == 200, removed.text
    assert removed.json()["event"]["status"] == "removed"


def test_life_event_requires_matching_consent(client) -> None:
    headers = _headers("test-citizen-life-event-no-consent")
    household = client.post(
        "/api/households",
        headers=headers,
        json={"state_code": "KA", "include_self": True, "consent_persistence": True},
    )
    assert household.status_code == 201
    household_id = household.json()["id"]
    member_id = client.get(
        f"/api/households/{household_id}/members", headers=headers
    ).json()[0]["id"]
    response = client.post(
        f"/api/households/{household_id}/life-events",
        headers=headers,
        json={
            "household_member_id": member_id,
            "event_key": "marriage",
            "confirm": True,
        },
    )
    assert response.status_code == 403
