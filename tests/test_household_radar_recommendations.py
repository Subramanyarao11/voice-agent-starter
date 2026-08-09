"""Household Radar matching, provenance, and lifecycle contracts."""

from datetime import date

from sahaayak_common import (
    Benefit,
    MemberRecommendation,
    session_scope,
)
from sahaayak_contracts import Domain, MatchVerdict, VerificationStatus


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_radar_matches_current_facts_and_persists_redacted_evidence(client) -> None:
    headers = _headers("test-citizen-radar-recommendations")
    created = client.post(
        "/api/households",
        headers=headers,
        json={
            "state_code": "KA",
            "district": "Bengaluru Urban",
            "include_self": True,
            "consent_persistence": True,
            "consent_personalization": True,
        },
    )
    assert created.status_code == 201
    household_id = created.json()["id"]
    member = client.get(f"/api/households/{household_id}/members", headers=headers).json()[0]
    member_id = member["id"]

    income = client.put(
        f"/api/households/{household_id}/facts/annual_household_income",
        headers=headers,
        json={
            "value": "200000",
            "purposes": ["benefit_matching"],
            "confirm_purpose": True,
        },
    )
    assert income.status_code == 200
    age = client.put(
        f"/api/households/{household_id}/members/{member_id}/facts/age_band",
        headers=headers,
        json={
            "value": "adult",
            "purposes": ["benefit_matching"],
            "confirm_purpose": True,
        },
    )
    assert age.status_code == 200

    benefit_id = "radar-reviewed-benefit"
    with session_scope() as db:
        db.merge(
            Benefit(
                id=benefit_id,
                domain=Domain.SCHEME,
                name="Reviewed Karnataka Family Support",
                state_code="KA",
                description="A verified demo support benefit.",
                eligibility_initial={
                    "age_min": 18,
                    "age_max": 59,
                    "max_annual_family_income_inr": 300000,
                    "state_residency_required": True,
                },
                benefits_text="Support",
                documents_required=["Income certificate"],
                application_process="Use the official portal.",
                source_url="https://example.gov.in/radar-reviewed-benefit",
                source_title="Official family support notice",
                source_document_url="https://example.gov.in/radar-reviewed-benefit.pdf",
                source_excerpt="Verified criteria excerpt",
                verification_status=VerificationStatus.HUMAN_VERIFIED,
                verified_by="test-reviewer",
                verified_at=None,
                last_verified_date=date.today(),
                content_revision=1,
                is_active=True,
            )
        )

    refreshed = client.post(
        f"/api/households/{household_id}/radar/refresh",
        headers=headers,
        json={"member_id": member_id, "domains": ["scheme"]},
    )
    assert refreshed.status_code == 200, refreshed.text
    body = refreshed.json()
    assert body["recommendation_count"] >= 1
    recommendation = next(
        item for item in body["recommendations"] if item["benefit_id"] == benefit_id
    )
    assert recommendation["benefit_id"] == benefit_id
    assert recommendation["verdict"] == MatchVerdict.ELIGIBLE.value
    assert recommendation["source_url"].endswith(".pdf")
    assert "human_verified_source" in recommendation["reason_codes"]
    assert {item["fact_key"] for item in recommendation["criterion_evidence"]} >= {
        "age_band",
        "annual_household_income",
    }
    assert all("caller_value" not in item for item in recommendation["criterion_evidence"])
    assert {item["fact_key"] for item in recommendation["fact_use_evidence"]} == {
        "age_band",
        "annual_household_income",
    }

    with session_scope() as db:
        row = db.get(MemberRecommendation, recommendation["id"])
        assert row is not None
        assert row.verdict == MatchVerdict.ELIGIBLE.value
        assert all("200000" not in str(item) for item in row.criterion_evidence)
        assert all("adult" not in str(item) for item in row.criterion_evidence)

    viewed = client.post(
        f"/api/households/{household_id}/radar/{recommendation['id']}",
        headers=headers,
        json={"action": "view"},
    )
    assert viewed.status_code == 200
    assert viewed.json()["state"] == "viewed"

    dismissed = client.post(
        f"/api/households/{household_id}/radar/{recommendation['id']}",
        headers=headers,
        json={"action": "dismiss", "reason_code": "not_relevant"},
    )
    assert dismissed.status_code == 200
    assert dismissed.json()["state"] == "dismissed"

    hidden = client.get(f"/api/households/{household_id}/radar", headers=headers)
    assert hidden.status_code == 200
    assert all(
        item["benefit_id"] != benefit_id
        for item in hidden.json()["recommendations"]
    )
    visible = client.get(
        f"/api/households/{household_id}/radar?include_dismissed=true",
        headers=headers,
    )
    assert visible.status_code == 200
    assert visible.json()["recommendations"][0]["state"] == "dismissed"


def test_radar_keeps_missing_criteria_uncertain(client) -> None:
    headers = _headers("test-citizen-radar-uncertain")
    created = client.post(
        "/api/households",
        headers=headers,
        json={
            "state_code": "KA",
            "include_self": True,
            "consent_persistence": True,
            "consent_personalization": True,
        },
    )
    household_id = created.json()["id"]
    member_id = client.get(
        f"/api/households/{household_id}/members", headers=headers
    ).json()[0]["id"]
    age = client.put(
        f"/api/households/{household_id}/members/{member_id}/facts/age_band",
        headers=headers,
        json={
            "value": "adult",
            "purposes": ["benefit_matching"],
            "confirm_purpose": True,
        },
    )
    assert age.status_code == 200

    benefit_id = "radar-reviewed-income-gate"
    with session_scope() as db:
        db.merge(
            Benefit(
                id=benefit_id,
                domain=Domain.SCHEME,
                name="Reviewed Income Gate",
                state_code="KA",
                eligibility_initial={
                    "age_min": 18,
                    "age_max": 59,
                    "max_annual_family_income_inr": 300000,
                },
                source_url="https://example.gov.in/radar-income-gate",
                verification_status=VerificationStatus.HUMAN_VERIFIED,
                last_verified_date=date.today(),
                content_revision=1,
                is_active=True,
            )
        )

    refreshed = client.post(
        f"/api/households/{household_id}/radar/refresh",
        headers=headers,
        json={"member_id": member_id, "domains": ["scheme"]},
    )
    assert refreshed.status_code == 200
    matches = [
        row
        for row in refreshed.json()["recommendations"]
        if row["benefit_id"] == benefit_id
    ]
    assert len(matches) == 1
    assert matches[0]["verdict"] == MatchVerdict.INSUFFICIENT_INFO.value
    assert "missing_or_uncertain_criterion" in matches[0]["reason_codes"]
    income_evidence = next(
        item
        for item in matches[0]["criterion_evidence"]
        if item["fact_key"] == "annual_household_income"
    )
    assert income_evidence["status"] == "unknown"
    assert income_evidence["fact_state"] == "missing"
