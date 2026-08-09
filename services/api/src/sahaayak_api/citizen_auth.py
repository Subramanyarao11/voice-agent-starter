"""Separate citizen authentication seam for the household workspace.

Guest browser tokens are intentionally not upgraded into durable household
access. Production deployments must configure a citizen OIDC/BFF exchange;
the static token branch exists only for local/test fixtures and is disabled by
default.
"""

from __future__ import annotations

import hmac
from dataclasses import dataclass

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
        # The deployment-specific PKCE/BFF callback belongs at the edge. The
        # API deliberately refuses to treat an unvalidated bearer as a subject.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Citizen OIDC validation is not configured in this API deployment",
        )

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
