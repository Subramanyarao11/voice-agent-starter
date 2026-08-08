"""Runtime checks for the persisted rollout controls.

These tests intentionally cross the public session/catalog boundaries. A flag
that only changes an admin card is not a rollout control.
"""

from __future__ import annotations

from sqlmodel import Session, select

from sahaayak_common import FeatureFlag, engine


def _set_flag(key: str, *, enabled: bool, percentage: int, languages=None, states=None):
    with Session(engine) as db:
        row = db.exec(select(FeatureFlag).where(FeatureFlag.key == key)).one()
        before = (
            row.enabled,
            row.rollout_percentage,
            list(row.target_languages),
            list(row.target_states),
        )
        row.enabled = enabled
        row.rollout_percentage = percentage
        row.target_languages = list(languages or [])
        row.target_states = list(states or [])
        db.add(row)
        db.commit()
    return before


def _restore_flag(key: str, before) -> None:
    with Session(engine) as db:
        row = db.exec(select(FeatureFlag).where(FeatureFlag.key == key)).one()
        row.enabled, row.rollout_percentage, row.target_languages, row.target_states = before
        db.add(row)
        db.commit()


def test_language_and_state_flags_change_guest_session_resolution(client):
    language_before = _set_flag(
        "language_rollout", enabled=True, percentage=100, languages=["en"]
    )
    state_before = _set_flag(
        "state_rollout", enabled=True, percentage=100, states=["DL"]
    )
    try:
        response = client.post(
            "/api/browser-sessions",
            json={"language_code": "kn", "state_code": "KA"},
        )
        assert response.status_code == 201
        assert response.json()["language_code"] == "en"
        assert response.json()["state_code"] == "DL"
    finally:
        _restore_flag("language_rollout", language_before)
        _restore_flag("state_rollout", state_before)


def test_expansion_language_requires_release_gate_before_catalog_and_sessions(client):
    before = _set_flag(
        "ten_language_rollout", enabled=True, percentage=100, languages=["ta"]
    )
    try:
        languages = {row["code"]: row for row in client.get("/api/languages").json()}
        assert languages["ta"]["is_active"] is False

        response = client.post(
            "/api/browser-sessions",
            json={"language_code": "ta", "state_code": "DL"},
        )
        assert response.status_code == 201
        assert response.json()["language_code"] != "ta"
    finally:
        _restore_flag("ten_language_rollout", before)
