"""Household Radar Phase 0/1 privacy and ownership tests."""

from sqlmodel import select

from sahaayak_common import (
    HouseholdConsentEvent,
    ProfileFact,
    ProfileFactRevision,
    session_scope,
)


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_household_setup_requires_consent_and_keeps_profile_values_private(client):
    unauthenticated = client.get("/api/citizen/me")
    assert unauthenticated.status_code == 401

    headers = _headers("test-citizen-radar-owner")
    missing_consent = client.post(
        "/api/households",
        json={"label": "Rao family", "consent_persistence": False},
        headers=headers,
    )
    assert missing_consent.status_code == 400

    created = client.post(
        "/api/households",
        json={
            "label": "Rao family",
            "state_code": "KA",
            "district": "Bengaluru Urban",
            "pincode": "560001",
            "include_self": True,
            "consent_persistence": True,
            "consent_personalization": True,
        },
        headers=headers,
    )
    assert created.status_code == 201
    household = created.json()
    household_id = household["id"]
    assert household["label"] != "Rao family"
    assert household["pincode"] == "••••01"
    assert household["member_count"] == 1

    me = client.get("/api/citizen/me", headers=headers)
    assert me.status_code == 200
    assert household_id in me.json()["household_ids"]

    members = client.get(f"/api/households/{household_id}/members", headers=headers)
    assert members.status_code == 200
    self_member = members.json()[0]
    assert self_member["alias"] != "Me"
    assert self_member["relationship_category"] == "self"

    missing_authority = client.post(
        f"/api/households/{household_id}/members",
        json={
            "alias": "Parent one",
            "relationship_category": "parent",
            "age_class": "senior",
            "consent_member_management": True,
            "authority_confirmed": False,
        },
        headers=headers,
    )
    assert missing_authority.status_code == 400

    added = client.post(
        f"/api/households/{household_id}/members",
        json={
            "alias": "Parent one",
            "relationship_category": "parent",
            "age_class": "senior",
            "consent_member_management": True,
            "authority_confirmed": True,
        },
        headers=headers,
    )
    assert added.status_code == 201
    parent_id = added.json()["id"]
    assert added.json()["alias"] != "Parent one"
    assert added.json()["authority_status"] == "confirmed"

    household_fact = client.put(
        f"/api/households/{household_id}/facts/district",
        json={
            "value": "Bengaluru Urban",
            "purposes": ["routing", "benefit_matching"],
            "confirm_purpose": True,
        },
        headers=headers,
    )
    assert household_fact.status_code == 200
    assert household_fact.json()["state"] == "current"
    assert household_fact.json()["masked_value"] != "Bengaluru Urban"

    invalid_purpose = client.put(
        f"/api/households/{household_id}/facts/district",
        json={
            "value": "Bengaluru Urban",
            "purposes": ["telemetry"],
            "confirm_purpose": True,
        },
        headers=headers,
    )
    assert invalid_purpose.status_code == 422

    member_fact = client.put(
        f"/api/households/{household_id}/members/{parent_id}/facts/age_band",
        json={
            "value": "senior",
            "purposes": ["benefit_matching"],
            "confirm_purpose": True,
        },
        headers=headers,
    )
    assert member_fact.status_code == 200
    assert member_fact.json()["masked_value"] != "senior"
    current_revision = member_fact.json()["revision"]

    changed = client.put(
        f"/api/households/{household_id}/members/{parent_id}/facts/age_band",
        json={
            "value": "adult",
            "purposes": ["benefit_matching"],
            "confirm_purpose": True,
            "expected_revision": current_revision,
        },
        headers=headers,
    )
    assert changed.status_code == 200
    assert changed.json()["revision"] == current_revision + 1

    conflict = client.put(
        f"/api/households/{household_id}/members/{parent_id}/facts/age_band",
        json={
            "value": "youth",
            "purposes": ["benefit_matching"],
            "confirm_purpose": True,
            "expected_revision": current_revision,
        },
        headers=headers,
    )
    assert conflict.status_code == 409

    history = client.get(
        f"/api/households/{household_id}/members/{parent_id}/facts/age_band/history",
        headers=headers,
    )
    assert history.status_code == 200
    assert [row["action"] for row in history.json()] == ["created", "updated"]
    assert all("senior" not in row["after_masked_value"] for row in history.json())

    deleted = client.delete(
        f"/api/households/{household_id}/members/{parent_id}/facts/age_band",
        headers=headers,
    )
    assert deleted.status_code == 204
    retained_history = client.get(
        f"/api/households/{household_id}/members/{parent_id}/facts/age_band/history",
        headers=headers,
    )
    assert retained_history.status_code == 200
    assert retained_history.json()[-1]["action"] == "deleted"

    with session_scope() as db:
        fact = db.exec(
            select(ProfileFact).where(
                ProfileFact.household_id == household_id,
                ProfileFact.household_member_id == parent_id,
            )
        ).one()
        assert fact.value_ciphertext == ""
        assert fact.value_hash == ""
        assert fact.masked_value == ""
        revisions = db.exec(
            select(ProfileFactRevision).where(ProfileFactRevision.profile_fact_id == fact.id)
        ).all()
        consents = db.exec(
            select(HouseholdConsentEvent).where(
                HouseholdConsentEvent.household_id == household_id
            )
        ).all()
        assert len(revisions) == 3
        assert any(event.purpose == "benefit_matching" for event in consents)

    requested = client.delete(f"/api/households/{household_id}", headers=headers)
    assert requested.status_code == 200
    assert requested.json()["status"] == "pending_deletion"


def test_household_accounts_are_isolated_and_dependant_gate_is_explicit(client):
    owner_a = _headers("test-citizen-radar-a")
    owner_b = _headers("test-citizen-radar-b")
    created = client.post(
        "/api/households",
        json={"consent_persistence": True, "include_self": True},
        headers=owner_a,
    )
    assert created.status_code == 201
    household_id = created.json()["id"]

    cross_account = client.get(f"/api/households/{household_id}", headers=owner_b)
    assert cross_account.status_code == 404

    child = client.post(
        f"/api/households/{household_id}/members",
        json={
            "alias": "Child",
            "relationship_category": "child",
            "age_class": "child",
            "authority_confirmed": True,
            "consent_member_management": True,
        },
        headers=owner_a,
    )
    assert child.status_code == 409

    deleted = client.delete(f"/api/households/{household_id}", headers=owner_a)
    assert deleted.status_code == 200
