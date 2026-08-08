"""Admin boundary and platform-operations contract tests."""

from __future__ import annotations

from datetime import date

import pytest


def test_admin_rejects_an_invalid_workforce_token(client):
    response = client.get("/api/admin/overview", headers={"X-Admin-Token": "wrong-token"})
    assert response.status_code == 403


def test_admin_overview_and_conversations_are_aggregated_and_redacted(client, guest_session):
    session = guest_session()
    client.post(
        "/api/turns",
        json={
            "text": "I need a scholarship",
            "language_code": "en",
            "state_code": "KA",
        },
        headers=session["headers"],
    )

    overview = client.get("/api/admin/overview")
    assert overview.status_code == 200
    body = overview.json()
    assert body["traffic"]["turns"] >= 1
    assert "providers" in body
    assert session["access_token"] not in overview.text

    conversations = client.get("/api/admin/conversations")
    assert conversations.status_code == 200
    items = conversations.json()["items"]
    assert any(item["turn_count"] >= 1 for item in items)
    assert session["access_token"] not in conversations.text
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


def test_admin_provider_policy_update_and_rollback_is_audited(client):
    from sqlmodel import select

    from sahaayak_common import ProviderPolicy, ProviderPolicyRevision, session_scope

    policy_id = "policy:tts:kn"
    response = client.put(
        "/api/admin/provider-policies/tts/kn",
        json={
            "enabled": False,
            "primary_provider": "sarvam_bulbul",
            "fallback_provider": "text_only",
            "circuit_state": "open",
            "override_expires_at": "2099-01-01T00:00:00Z",
            "reason": "Pause the locale during a provider incident",
        },
    )
    assert response.status_code == 400
    # The policy contract deliberately rejects far-future expiry values.
    response = client.put(
        "/api/admin/provider-policies/tts/kn",
        json={
            "enabled": False,
            "primary_provider": "sarvam_bulbul",
            "fallback_provider": "text_only",
            "circuit_state": "open",
            "override_expires_at": "2030-01-01T00:00:00Z",
            "reason": "Pause the locale during a provider incident",
        },
    )
    assert response.status_code == 400

    from datetime import UTC, datetime, timedelta

    expires = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    response = client.put(
        "/api/admin/provider-policies/tts/kn",
        json={
            "enabled": False,
            "primary_provider": "sarvam_bulbul",
            "fallback_provider": "text_only",
            "circuit_state": "open",
            "override_expires_at": expires,
            "reason": "Pause the locale during a provider incident",
        },
    )
    assert response.status_code == 200
    assert response.json()["circuit_state"] == "open"

    rollback = client.post(
        "/api/admin/provider-policies/tts/kn/rollback",
        json={"reason": "Incident cleared; restore the previous route"},
    )
    assert rollback.status_code == 200
    assert rollback.json()["circuit_state"] == "closed"
    assert rollback.json()["enabled"] is True

    audit = client.get("/api/admin/audit-events?action=provider_policy.rollback")
    assert audit.status_code == 200
    assert any(event["target_id"] == policy_id for event in audit.json())

    with session_scope() as db:
        for revision in db.exec(
            select(ProviderPolicyRevision).where(
                ProviderPolicyRevision.policy_id == policy_id
            )
        ).all():
            db.delete(revision)
        row = db.get(ProviderPolicy, policy_id)
        if row is not None:
            db.delete(row)


def test_admin_language_release_gate_requires_bundle_and_attestation(client):
    languages = {row["code"]: row for row in client.get("/api/admin/languages").json()}
    assert languages["ta"]["native_speaker_status"] == "pending"
    assert languages["ta"]["active"] is False

    base_payload = {
        "native_speaker_status": "pending",
        "interface_status": "pending",
        "prompt_status": "pending",
        "content_status": "pending",
        "understanding_status": "pending",
        "voice_status": "pending",
        "accessibility_status": "pending",
        "evidence_url": "https://example.test/ta-review",
        "review_notes": "Native review packet is not complete yet",
    }
    missing_attestation = client.put(
        "/api/admin/languages/ta/review",
        json=base_payload,
    )
    assert missing_attestation.status_code == 400

    saved = client.put(
        "/api/admin/languages/ta/review",
        json={**base_payload, "attestation": True},
    )
    assert saved.status_code == 200
    assert saved.json()["rollout_status"] == "not ready"

    prompt_without_bundle = client.put(
        "/api/admin/languages/ta/review",
        json={
            **base_payload,
            "prompt_status": "approved",
            "attestation": True,
        },
    )
    assert prompt_without_bundle.status_code == 409


async def test_managed_oidc_token_requires_mfa_and_maps_role(monkeypatch):
    import json
    from datetime import UTC, datetime, timedelta

    import jwt
    from cryptography.hazmat.primitives.asymmetric import rsa

    from sahaayak_api import admin_auth
    from sahaayak_common import settings

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key()))
    public_jwk.update({"kid": "test-key", "use": "sig", "alg": "RS256"})

    async def fake_fetch_json(url: str) -> dict:
        if url.endswith("openid-configuration"):
            return {"issuer": "https://issuer.example", "jwks_uri": "https://issuer.example/keys"}
        return {"keys": [public_jwk]}

    monkeypatch.setattr(admin_auth, "_fetch_json", fake_fetch_json)
    monkeypatch.setattr(admin_auth, "_oidc_cache", None)
    monkeypatch.setattr(settings, "admin_oidc_issuer_url", "https://issuer.example")
    monkeypatch.setattr(settings, "admin_oidc_audience", "sahaayak-admin")
    monkeypatch.setattr(settings, "admin_oidc_required_amr", "mfa")
    monkeypatch.setattr(settings, "admin_oidc_required_acr", "")
    monkeypatch.setattr(settings, "admin_oidc_roles_claim", "roles")

    now = datetime.now(UTC)
    claims = {
        "iss": "https://issuer.example",
        "aud": "sahaayak-admin",
        "sub": "workforce-user-1",
        "iat": now,
        "exp": now + timedelta(minutes=5),
        "amr": ["pwd", "mfa"],
        "roles": ["reviewer"],
    }
    token = jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": "test-key"})
    principal = await admin_auth._validate_oidc_token(token)
    assert principal.actor_id == "oidc:workforce-user-1"
    assert principal.role == "reviewer"
    assert principal.mfa_verified is True

    no_mfa = dict(claims)
    no_mfa["amr"] = ["pwd"]
    no_mfa_token = jwt.encode(no_mfa, private_key, algorithm="RS256", headers={"kid": "test-key"})
    with pytest.raises(admin_auth._OIDCRejected) as error:
        await admin_auth._validate_oidc_token(no_mfa_token)
    assert error.value.http_status == 403
