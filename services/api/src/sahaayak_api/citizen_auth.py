"""Separate citizen authentication seam for the household workspace.

Guest browser tokens are intentionally not upgraded into durable household
access. Production deployments must configure a citizen OIDC/BFF exchange;
the static token branch exists only for local/test fixtures and is disabled by
default.
"""

from __future__ import annotations

import asyncio
import hmac
import time
from dataclasses import dataclass
from typing import Any

import httpx
import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlmodel import Session, select

from sahaayak_common import (
    CitizenAccount,
    citizen_subject_hash,
    get_session,
    new_id,
    settings,
)


@dataclass(frozen=True)
class CitizenPrincipal:
    provider: str
    subject_hash: str


class _OIDCRejected(Exception):
    def __init__(self, detail: str, http_status: int = status.HTTP_401_UNAUTHORIZED) -> None:
        super().__init__(detail)
        self.detail = detail
        self.http_status = http_status


class _OIDCUnavailable(Exception):
    pass


@dataclass(frozen=True)
class _OIDCKeyCache:
    issuer: str
    jwks_url: str
    keys: dict[str, Any]
    expires_at: float


_OIDC_ALGORITHMS = {
    "RS256",
    "RS384",
    "RS512",
    "PS256",
    "PS384",
    "PS512",
    "ES256",
    "ES384",
    "ES512",
}
_oidc_cache: _OIDCKeyCache | None = None
_oidc_cache_lock = asyncio.Lock()


def _extract_token(request: Request) -> str:
    authorization = request.headers.get("Authorization", "")
    return authorization[7:].strip() if authorization.lower().startswith("bearer ") else ""


async def require_citizen(
    request: Request,
    _db: Session = Depends(get_session),
) -> CitizenPrincipal:
    token = _extract_token(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A citizen account bearer token is required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if settings.citizen_oidc_enabled:
        try:
            return await _validate_oidc_token(token)
        except _OIDCRejected as exc:
            headers = {"WWW-Authenticate": "Bearer"} if exc.http_status == 401 else None
            raise HTTPException(
                status_code=exc.http_status,
                detail=exc.detail,
                headers=headers,
            ) from exc
        except _OIDCUnavailable as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Citizen identity verification is temporarily unavailable",
            ) from exc

    if not (settings.citizen_static_tokens_enabled or settings.is_test):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Citizen authentication is not configured for this deployment",
        )
    configured = settings.citizen_api_token.strip()
    is_configured_token = bool(configured) and hmac.compare_digest(token, configured)
    # Test-only subject separation lets the suite prove account isolation
    # without introducing a second production authentication mechanism.
    is_test_subject_token = settings.is_test and token.startswith("test-citizen-")
    if not is_configured_token and not is_test_subject_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The citizen token is not valid for this deployment",
        )
    try:
        return CitizenPrincipal(
            provider="static-test",
            subject_hash=citizen_subject_hash(
                token if is_test_subject_token else "local-citizen"
            ),
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Citizen identity hashing is not configured on this deployment",
        ) from exc


async def _validate_oidc_token(token: str) -> CitizenPrincipal:
    issuer = settings.citizen_oidc_issuer_url.strip().rstrip("/")
    audience = settings.citizen_oidc_audience.strip()
    if not issuer or not audience:
        raise _OIDCUnavailable("Citizen OIDC issuer and audience must be configured")

    algorithms = _configured_algorithms()
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise _OIDCRejected("The citizen identity token is not valid") from exc
    algorithm = header.get("alg")
    key_id = header.get("kid")
    if algorithm not in algorithms or not isinstance(key_id, str) or not key_id:
        raise _OIDCRejected("The citizen identity token header is not accepted")

    key = await _oidc_key(key_id)
    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=algorithms,
            audience=audience,
            issuer=issuer,
            leeway=max(0, settings.citizen_oidc_clock_skew_seconds),
            options={"require": ["exp", "iat"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise _OIDCRejected("The citizen identity session has expired") from exc
    except jwt.PyJWTError as exc:
        raise _OIDCRejected("The citizen identity token claims are not valid") from exc

    subject = _claim_value(claims, settings.citizen_oidc_subject_claim)
    if not isinstance(subject, str) or not subject.strip():
        raise _OIDCRejected("The citizen identity token has no usable subject")
    if not _assurance_verified(claims):
        raise _OIDCRejected(
            "The citizen identity session does not meet the configured assurance policy",
            http_status=status.HTTP_403_FORBIDDEN,
        )
    if settings.citizen_oidc_require_email_verified and claims.get("email_verified") is not True:
        raise _OIDCRejected(
            "The citizen identity provider has not verified the account contact",
            http_status=status.HTTP_403_FORBIDDEN,
        )
    try:
        # Include the trusted issuer in the digest so equal subjects from two
        # identity providers cannot collide in the citizen projection table.
        subject_hash = citizen_subject_hash(f"{issuer}|{subject.strip()}")
    except RuntimeError as exc:
        raise _OIDCUnavailable("Citizen identity hashing is not configured") from exc
    return CitizenPrincipal(provider=issuer, subject_hash=subject_hash)


def _configured_algorithms() -> list[str]:
    algorithms = [item.strip() for item in settings.citizen_oidc_allowed_algorithms.split(",")]
    accepted = [item for item in algorithms if item in _OIDC_ALGORITHMS]
    if not accepted:
        raise _OIDCUnavailable("No supported citizen OIDC signing algorithm is configured")
    return accepted


async def _oidc_key(key_id: str) -> Any:
    cache = await _load_oidc_keys()
    if key_id in cache.keys:
        return cache.keys[key_id]
    cache = await _load_oidc_keys(force=True)
    if key_id not in cache.keys:
        raise _OIDCRejected("The citizen OIDC signing key is not recognized")
    return cache.keys[key_id]


async def _load_oidc_keys(*, force: bool = False) -> _OIDCKeyCache:
    global _oidc_cache
    now = time.monotonic()
    if not force and _oidc_cache is not None and _oidc_cache.expires_at > now:
        return _oidc_cache
    async with _oidc_cache_lock:
        now = time.monotonic()
        if not force and _oidc_cache is not None and _oidc_cache.expires_at > now:
            return _oidc_cache
        issuer = settings.citizen_oidc_issuer_url.strip().rstrip("/")
        if not issuer:
            raise _OIDCUnavailable("Citizen OIDC issuer is not configured")
        discovery_url = (
            settings.citizen_oidc_discovery_url.strip()
            or f"{issuer}/.well-known/openid-configuration"
        )
        discovery = await _fetch_json(discovery_url)
        discovered_issuer = discovery.get("issuer")
        if discovered_issuer and str(discovered_issuer).rstrip("/") != issuer:
            raise _OIDCUnavailable("Citizen OIDC discovery issuer does not match configuration")
        jwks_url = settings.citizen_oidc_jwks_url.strip() or str(discovery.get("jwks_uri", ""))
        if not jwks_url:
            raise _OIDCUnavailable("Citizen OIDC discovery did not provide a JWKS URL")
        document = await _fetch_json(jwks_url)
        raw_keys = document.get("keys")
        if not isinstance(raw_keys, list):
            raise _OIDCUnavailable("Citizen OIDC JWKS response has no keys")
        keys: dict[str, Any] = {}
        for item in raw_keys:
            if not isinstance(item, dict) or not isinstance(item.get("kid"), str):
                continue
            try:
                keys[item["kid"]] = jwt.PyJWK.from_dict(item).key
            except (TypeError, ValueError, jwt.PyJWTError):
                continue
        if not keys:
            raise _OIDCUnavailable("Citizen OIDC JWKS response contains no usable keys")
        _oidc_cache = _OIDCKeyCache(
            issuer=issuer,
            jwks_url=jwks_url,
            keys=keys,
            expires_at=time.monotonic()
            + max(30, settings.citizen_oidc_jwks_cache_seconds),
        )
        return _oidc_cache


async def _fetch_json(url: str) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=4.0, follow_redirects=False) as client:
            response = await client.get(url)
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise _OIDCUnavailable("Citizen OIDC metadata could not be loaded") from exc
    if not isinstance(payload, dict):
        raise _OIDCUnavailable("Citizen OIDC metadata has an invalid shape")
    return payload


def _claim_value(claims: dict[str, Any], path: str) -> Any:
    value: Any = claims
    for part in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _assurance_verified(claims: dict[str, Any]) -> bool:
    required_amr = settings.citizen_oidc_required_amr.strip()
    required_acr = settings.citizen_oidc_required_acr.strip()
    if not required_amr and not required_acr:
        return True
    raw_amr = claims.get("amr", [])
    amr = [raw_amr] if isinstance(raw_amr, str) else raw_amr if isinstance(raw_amr, list) else []
    acr = claims.get("acr")
    return (bool(required_amr) and required_amr in amr) or (
        bool(required_acr) and acr == required_acr
    )


def reset_oidc_cache() -> None:
    """Clear discovery/JWKS state between deployments and deterministic tests."""
    global _oidc_cache
    _oidc_cache = None


def get_or_create_citizen_account(
    db: Session,
    principal: CitizenPrincipal,
    *,
    preferred_language_code: str = "en",
) -> CitizenAccount:
    account = db.exec(
        select(CitizenAccount).where(
            CitizenAccount.provider_subject_hash == principal.subject_hash
        )
    ).first()
    if account is not None:
        return account
    account = CitizenAccount(
        id=new_id("citizen"),
        identity_provider=principal.provider,
        provider_subject_hash=principal.subject_hash,
        preferred_language_code=preferred_language_code,
    )
    db.add(account)
    db.flush()
    return account
