"""Security contract tests for production citizen bearer validation."""

import json
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa


@pytest.mark.asyncio
async def test_citizen_oidc_token_validates_issuer_audience_and_subject(monkeypatch) -> None:
    from sahaayak_api import citizen_auth
    from sahaayak_common import settings

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key()))
    public_jwk.update({"kid": "citizen-key", "use": "sig", "alg": "RS256"})

    async def fake_fetch_json(url: str) -> dict:
        if url.endswith("openid-configuration"):
            return {
                "issuer": "https://citizen.example",
                "jwks_uri": "https://citizen.example/keys",
            }
        return {"keys": [public_jwk]}

    monkeypatch.setattr(citizen_auth, "_fetch_json", fake_fetch_json)
    monkeypatch.setattr(settings, "citizen_oidc_issuer_url", "https://citizen.example")
    monkeypatch.setattr(settings, "citizen_oidc_audience", "sahaayak-citizen")
    monkeypatch.setattr(settings, "citizen_oidc_subject_claim", "sub")
    monkeypatch.setattr(settings, "citizen_oidc_required_amr", "")
    monkeypatch.setattr(settings, "citizen_oidc_required_acr", "")
    citizen_auth.reset_oidc_cache()

    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "iss": "https://citizen.example",
            "aud": "sahaayak-citizen",
            "sub": "citizen-42",
            "iat": now,
            "exp": now + timedelta(minutes=5),
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "citizen-key"},
    )

    principal = await citizen_auth._validate_oidc_token(token)

    assert principal.provider == "https://citizen.example"
    assert principal.subject_hash
    assert "citizen-42" not in principal.subject_hash


@pytest.mark.asyncio
async def test_citizen_oidc_assurance_and_claim_failures_are_rejected(monkeypatch) -> None:
    from sahaayak_api import citizen_auth
    from sahaayak_common import settings

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key()))
    public_jwk.update({"kid": "citizen-key", "use": "sig", "alg": "RS256"})

    async def fake_fetch_json(url: str) -> dict:
        return (
            {"issuer": "https://citizen.example", "jwks_uri": "https://citizen.example/keys"}
            if url.endswith("openid-configuration")
            else {"keys": [public_jwk]}
        )

    monkeypatch.setattr(citizen_auth, "_fetch_json", fake_fetch_json)
    monkeypatch.setattr(settings, "citizen_oidc_issuer_url", "https://citizen.example")
    monkeypatch.setattr(settings, "citizen_oidc_audience", "sahaayak-citizen")
    monkeypatch.setattr(settings, "citizen_oidc_required_amr", "otp")
    monkeypatch.setattr(settings, "citizen_oidc_required_acr", "")
    citizen_auth.reset_oidc_cache()

    now = datetime.now(UTC)
    base_claims = {
        "iss": "https://citizen.example",
        "aud": "sahaayak-citizen",
        "sub": "citizen-42",
        "iat": now,
        "exp": now + timedelta(minutes=5),
        "amr": ["pwd"],
    }
    token = jwt.encode(
        base_claims,
        private_key,
        algorithm="RS256",
        headers={"kid": "citizen-key"},
    )

    with pytest.raises(citizen_auth._OIDCRejected) as assurance_error:
        await citizen_auth._validate_oidc_token(token)
    assert assurance_error.value.http_status == 403

    wrong_audience = dict(base_claims, aud="another-client", amr=["otp"])
    wrong_token = jwt.encode(
        wrong_audience,
        private_key,
        algorithm="RS256",
        headers={"kid": "citizen-key"},
    )
    with pytest.raises(citizen_auth._OIDCRejected):
        await citizen_auth._validate_oidc_token(wrong_token)


def test_citizen_bff_exchange_sets_opaque_cookie_and_logout_revokes_it(client, monkeypatch) -> None:
    from sahaayak_api import citizen_auth
    from sahaayak_common import settings

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key()))
    public_jwk.update({"kid": "bff-key", "use": "sig", "alg": "RS256"})

    async def fake_fetch_json(url: str) -> dict:
        if url.endswith("openid-configuration"):
            return {
                "issuer": "https://citizen.example",
                "jwks_uri": "https://citizen.example/keys",
            }
        return {"keys": [public_jwk]}

    async def fake_token_request(form: dict[str, str]) -> dict:
        now = datetime.now(UTC)
        token = jwt.encode(
            {
                "iss": "https://citizen.example",
                "aud": "sahaayak-citizen",
                "sub": "bff-citizen-1",
                "iat": now,
                "exp": now + timedelta(minutes=5),
            },
            private_key,
            algorithm="RS256",
            headers={"kid": "bff-key"},
        )
        assert form["grant_type"] == "authorization_code"
        return {"access_token": token, "expires_in": 300}

    monkeypatch.setattr(citizen_auth, "_fetch_json", fake_fetch_json)
    monkeypatch.setattr(citizen_auth, "_token_request", fake_token_request)
    monkeypatch.setattr(settings, "citizen_oidc_bff_enabled", True)
    monkeypatch.setattr(settings, "citizen_oidc_client_id", "sahaayak-citizen-web")
    monkeypatch.setattr(settings, "citizen_oidc_redirect_uri", "http://localhost:5173/account/callback")
    monkeypatch.setattr(settings, "citizen_oidc_cookie_secure", False)
    monkeypatch.setattr(settings, "citizen_oidc_issuer_url", "https://citizen.example")
    monkeypatch.setattr(settings, "citizen_oidc_audience", "sahaayak-citizen")
    assert settings.citizen_auth_encryption_key
    citizen_auth.reset_oidc_cache()

    exchanged = client.post(
        "/api/citizen/auth/exchange",
        json={
            "code": "provider-code",
            "code_verifier": "v" * 43,
            "redirect_uri": "http://localhost:5173/account/callback",
        },
    )
    assert exchanged.status_code == 200, exchanged.text
    assert "sahaayak_citizen_session=" in exchanged.headers["set-cookie"]
    assert "HttpOnly" in exchanged.headers["set-cookie"]

    me = client.get("/api/citizen/me")
    assert me.status_code == 200
    assert me.json()["identity_provider"] == "https://citizen.example"

    logged_out = client.post("/api/citizen/auth/logout")
    assert logged_out.status_code == 204
    assert client.get("/api/citizen/me").status_code == 401
