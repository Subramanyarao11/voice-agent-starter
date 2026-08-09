"""Fail-closed workforce authentication for the operations console.

Deployments can validate bearer tokens issued by a managed OIDC provider. The
OIDC path verifies issuer, audience, signature, expiry, and MFA assurance from
the provider's claims before mapping a bounded role claim to Sahaayak roles.
Static tokens remain available only as an explicit local/test seam.
"""

from __future__ import annotations

import asyncio
import hmac
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx
import jwt
from fastapi import Depends, HTTPException, Request, status

from sahaayak_common import get_logger, settings

log = get_logger(__name__)

ROLE_ORDER = {
    "observer": 10,
    "assistant": 20,
    "operator": 20,
    "reviewer": 20,
    "admin": 30,
}
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


@dataclass(frozen=True)
class AdminPrincipal:
    actor_id: str
    role: str
    organization_id: str | None = None
    auth_source: str = "static"
    mfa_verified: bool = False


@dataclass(frozen=True)
class _OIDCKeyCache:
    issuer: str
    jwks_url: str
    keys: dict[str, Any]
    expires_at: float


class _OIDCRejected(Exception):
    def __init__(self, detail: str, http_status: int = status.HTTP_401_UNAUTHORIZED) -> None:
        super().__init__(detail)
        self.detail = detail
        self.http_status = http_status


class _OIDCUnavailable(Exception):
    pass


_oidc_cache: _OIDCKeyCache | None = None
_oidc_cache_lock = asyncio.Lock()


def _configured_tokens() -> list[tuple[str, AdminPrincipal]]:
    configured: list[tuple[str, AdminPrincipal]] = []
    if settings.admin_api_token.strip():
        configured.append(
            (
                settings.admin_api_token.strip(),
                AdminPrincipal(actor_id="local-admin", role="admin", organization_id="local"),
            )
        )

    raw = settings.admin_tokens_json.strip()
    if not raw:
        return configured
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        log.error("admin_tokens_invalid_json", error=str(exc))
        return configured
    if not isinstance(payload, dict):
        log.error("admin_tokens_invalid_shape")
        return configured

    for token, descriptor in payload.items():
        if not isinstance(token, str) or not token.strip():
            continue
        role = "observer"
        actor_id = f"token-{len(configured) + 1}"
        organization_id = "local"
        if isinstance(descriptor, str):
            role = descriptor
        elif isinstance(descriptor, dict):
            role = str(descriptor.get("role", role))
            actor_id = str(descriptor.get("actor_id", actor_id))
            organization_id = str(descriptor.get("organization_id", organization_id))
        if role not in ROLE_ORDER:
            log.warning("admin_token_role_invalid", role=role, actor_id=actor_id)
            continue
        configured.append(
            (
                token,
                AdminPrincipal(
                    actor_id=actor_id,
                    role=role,
                    organization_id=organization_id[:160],
                ),
            )
        )
    return configured


def _extract_token(request: Request) -> str:
    authorization = request.headers.get("Authorization", "")
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return request.headers.get("X-Admin-Token", "").strip()


async def get_admin_principal(request: Request) -> AdminPrincipal:
    supplied = _extract_token(request)
    if settings.admin_oidc_enabled:
        if not supplied:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="An OIDC bearer token is required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        try:
            return await _validate_oidc_token(supplied)
        except _OIDCRejected as exc:
            headers = {"WWW-Authenticate": "Bearer"} if exc.http_status == 401 else None
            raise HTTPException(
                status_code=exc.http_status,
                detail=exc.detail,
                headers=headers,
            ) from exc
        except _OIDCUnavailable as exc:
            log.error("admin_oidc_unavailable", error=exc.__class__.__name__)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Managed admin authentication is temporarily unavailable",
            ) from exc

    if not settings.admin_static_tokens_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin authentication is not configured for this deployment",
        )
    configured = _configured_tokens()
    if not configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin authentication is not configured",
        )
    if not supplied:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="An admin bearer token is required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    for expected, principal in configured:
        if hmac.compare_digest(supplied, expected):
            return principal

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="The admin token is not valid for this deployment",
    )


async def _validate_oidc_token(token: str) -> AdminPrincipal:
    issuer = settings.admin_oidc_issuer_url.strip().rstrip("/")
    audience = settings.admin_oidc_audience.strip()
    if not issuer or not audience:
        raise _OIDCUnavailable("OIDC issuer and audience must be configured")

    algorithms = _configured_algorithms()
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise _OIDCRejected("The OIDC token is not valid") from exc
    algorithm = header.get("alg")
    key_id = header.get("kid")
    if algorithm not in algorithms or not isinstance(key_id, str) or not key_id:
        raise _OIDCRejected("The OIDC token header is not accepted")

    key = await _oidc_key(key_id)
    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=algorithms,
            audience=audience,
            issuer=issuer,
            leeway=max(0, settings.admin_oidc_clock_skew_seconds),
            options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise _OIDCRejected("The OIDC session has expired") from exc
    except jwt.PyJWTError as exc:
        raise _OIDCRejected("The OIDC token claims are not valid") from exc

    mfa_verified = _mfa_verified(claims)
    if not mfa_verified:
        raise _OIDCRejected(
            "Workforce access requires an MFA-assured OIDC session",
            http_status=status.HTTP_403_FORBIDDEN,
        )
    actor_claim = _claim_value(claims, settings.admin_oidc_actor_claim)
    if not isinstance(actor_claim, str) or not actor_claim.strip():
        raise _OIDCRejected("The OIDC token has no usable workforce subject")
    organization_claim = _claim_value(claims, settings.admin_oidc_org_claim)
    organization_id = (
        str(organization_claim).strip()[:160]
        if isinstance(organization_claim, (str, int)) and str(organization_claim).strip()
        else None
    )
    return AdminPrincipal(
        actor_id=f"oidc:{actor_claim.strip()[:120]}",
        role=_role_from_claims(claims),
        organization_id=organization_id,
        auth_source="oidc",
        mfa_verified=True,
    )


def _configured_algorithms() -> list[str]:
    algorithms = [item.strip() for item in settings.admin_oidc_allowed_algorithms.split(",")]
    accepted = [item for item in algorithms if item in _OIDC_ALGORITHMS]
    if not accepted:
        raise _OIDCUnavailable("No supported OIDC signing algorithm is configured")
    return accepted


async def _oidc_key(key_id: str) -> Any:
    cache = await _load_oidc_keys()
    if key_id in cache.keys:
        return cache.keys[key_id]
    cache = await _load_oidc_keys(force=True)
    if key_id not in cache.keys:
        raise _OIDCRejected("The OIDC signing key is not recognized")
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
        issuer = settings.admin_oidc_issuer_url.strip().rstrip("/")
        if not issuer:
            raise _OIDCUnavailable("OIDC issuer is not configured")
        discovery_url = (
            settings.admin_oidc_discovery_url.strip()
            or f"{issuer}/.well-known/openid-configuration"
        )
        discovery = await _fetch_json(discovery_url)
        discovered_issuer = discovery.get("issuer")
        if discovered_issuer and str(discovered_issuer).rstrip("/") != issuer:
            raise _OIDCUnavailable("OIDC discovery issuer does not match configuration")
        jwks_url = settings.admin_oidc_jwks_url.strip() or str(discovery.get("jwks_uri", ""))
        if not jwks_url:
            raise _OIDCUnavailable("OIDC discovery did not provide a JWKS URL")
        document = await _fetch_json(jwks_url)
        raw_keys = document.get("keys")
        if not isinstance(raw_keys, list):
            raise _OIDCUnavailable("OIDC JWKS response has no keys")
        keys: dict[str, Any] = {}
        for item in raw_keys:
            if not isinstance(item, dict) or not isinstance(item.get("kid"), str):
                continue
            try:
                keys[item["kid"]] = jwt.PyJWK.from_dict(item).key
            except (TypeError, ValueError, jwt.PyJWTError):
                continue
        if not keys:
            raise _OIDCUnavailable("OIDC JWKS response contains no usable keys")
        _oidc_cache = _OIDCKeyCache(
            issuer=issuer,
            jwks_url=jwks_url,
            keys=keys,
            expires_at=time.monotonic() + max(30, settings.admin_oidc_jwks_cache_seconds),
        )
        return _oidc_cache


async def _fetch_json(url: str) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=4.0, follow_redirects=False) as client:
            response = await client.get(url)
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise _OIDCUnavailable("OIDC metadata could not be loaded") from exc
    if not isinstance(payload, dict):
        raise _OIDCUnavailable("OIDC metadata has an invalid shape")
    return payload


def _claim_value(claims: dict[str, Any], path: str) -> Any:
    value: Any = claims
    for part in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _mfa_verified(claims: dict[str, Any]) -> bool:
    required_amr = settings.admin_oidc_required_amr.strip()
    required_acr = settings.admin_oidc_required_acr.strip()
    if not required_amr and not required_acr:
        return True
    raw_amr = claims.get("amr", [])
    amr = [raw_amr] if isinstance(raw_amr, str) else raw_amr if isinstance(raw_amr, list) else []
    acr = claims.get("acr")
    return (bool(required_amr) and required_amr in amr) or (
        bool(required_acr) and acr == required_acr
    )


def _role_from_claims(claims: dict[str, Any]) -> str:
    raw_roles = _claim_value(claims, settings.admin_oidc_roles_claim)
    # Keycloak's standard realm-role representation is nested under
    # `realm_access.roles`. A custom `roles` mapper remains supported for
    # other providers, but local Keycloak should work with the standard token
    # shape out of the box.
    if raw_roles is None:
        raw_roles = _claim_value(claims, "realm_access.roles")
    values = [raw_roles] if isinstance(raw_roles, str) else raw_roles
    if not isinstance(values, list):
        values = []
    valid_roles = [value for value in values if isinstance(value, str) and value in ROLE_ORDER]
    return max(valid_roles, key=ROLE_ORDER.get) if valid_roles else "observer"


def require_admin_role(*roles: str) -> Callable[..., Any]:
    """Create a FastAPI dependency requiring one of the supplied roles."""

    allowed = set(roles)

    async def dependency(
        principal: AdminPrincipal = Depends(get_admin_principal),
    ) -> AdminPrincipal:
        if principal.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This admin action requires a different role",
            )
        return principal

    return dependency
