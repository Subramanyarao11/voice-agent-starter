from __future__ import annotations

ADMIN = {"X-Admin-Token": "test-admin-token"}


def test_admin_quality_views_and_feature_flag_rollback(client):
    freshness = client.get("/api/admin/freshness", headers=ADMIN)
    assert freshness.status_code == 200
    assert freshness.json()["sources"]

    flags = client.get("/api/admin/feature-flags", headers=ADMIN)
    assert flags.status_code == 200
    assert any(flag["key"] == "infobip_reminders" for flag in flags.json()["flags"])

    updated = client.put(
        "/api/admin/feature-flags/infobip_reminders",
        headers=ADMIN,
        json={
            "enabled": True,
            "rollout_percentage": 25,
            "target_languages": ["kn"],
            "target_states": ["ka"],
            "reason": "Stage external reminders for a controlled test",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["enabled"] is True
    assert updated.json()["target_states"] == ["KA"]

    rolled_back = client.post(
        "/api/admin/feature-flags/infobip_reminders/rollback",
        headers=ADMIN,
        json={"reason": "Rollback the controlled reminder test"},
    )
    assert rolled_back.status_code == 200
    assert rolled_back.json()["enabled"] is False
    assert rolled_back.json()["rollout_percentage"] == 0

    csv_export = client.get("/api/admin/audit-events/export?format=csv", headers=ADMIN)
    assert csv_export.status_code == 200
    assert "text/csv" in csv_export.headers["content-type"]
    assert "feature_flag.update" in csv_export.text


def test_admin_evaluation_history_is_visible_and_guest_is_rejected(client):
    from datetime import UTC, datetime

    from sahaayak_common import EvaluationRun, session_scope

    with session_scope() as db:
        db.add(
            EvaluationRun(
                id="eval-admin-test",
                suite_name="conversation-regression",
                suite_version="fixture",
                passed=True,
                case_count=2,
                passed_count=2,
                failed_count=0,
                language_counts={"kn": 1, "hi": 1},
                report_json={"passed": True, "cases": []},
                started_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
            )
        )

    evaluations = client.get("/api/admin/evaluations", headers=ADMIN)
    assert evaluations.status_code == 200
    assert evaluations.json()[0]["suite_version"] == "fixture"

    guest = client.post("/api/browser-sessions", json={"language_code": "kn", "state_code": "KA"})
    assert guest.status_code == 201
    rejected = client.get(
        "/api/admin/freshness",
        headers={"Authorization": f"Bearer {guest.json()['access_token']}"},
    )
    assert rejected.status_code in {401, 403}
