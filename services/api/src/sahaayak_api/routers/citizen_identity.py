"""Browser-facing citizen OIDC/BFF exchange and logout endpoints."""

from __future__ import annotations

from datetime import UTC

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlmodel import Session

from sahaayak_api.citizen_auth import (
    _OIDCRejected,
    _OIDCUnavailable,
    exchange_oidc_code,
    revoke_bff_session,
)
from sahaayak_common import get_session, settings

router = APIRouter(prefix="/api/citizen/auth", tags=["citizen identity"])


class CitizenCodeExchange(BaseModel):
    code: str = Field(min_length=1, max_length=4_096)
    code_verifier: str = Field(min_length=43, max_length=256)
    redirect_uri: str = Field(min_length=1, max_length=2_000)


class CitizenBffSessionOut(BaseModel):
    authenticated: bool = True
    expires_at: str


@router.post("/exchange", response_model=CitizenBffSessionOut)
async def exchange(
    payload: CitizenCodeExchange,
    response: Response,
    db: Session = Depends(get_session),
) -> CitizenBffSessionOut:
    try:
        row, session_capability = await exchange_oidc_code(
            db,
            code=payload.code,
            code_verifier=payload.code_verifier,
            redirect_uri=payload.redirect_uri,
        )
    except _OIDCRejected as exc:
        raise HTTPException(status_code=exc.http_status, detail=exc.detail) from exc
    except _OIDCUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Citizen sign-in is not configured for this deployment",
        ) from exc
    response.set_cookie(
        key=settings.citizen_oidc_cookie_name,
        value=session_capability,
        max_age=max(300, settings.citizen_auth_session_ttl_days * 24 * 60 * 60),
        expires=max(300, settings.citizen_auth_session_ttl_days * 24 * 60 * 60),
        httponly=True,
        secure=settings.citizen_oidc_cookie_secure,
        samesite="lax",
        path="/",
    )
    return CitizenBffSessionOut(
        expires_at=row.access_token_expires_at.astimezone(UTC).isoformat(),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_session),
) -> None:
    session_capability = request.cookies.get(settings.citizen_oidc_cookie_name)
    if session_capability:
        revoke_bff_session(db, session_capability)
    response.delete_cookie(
        key=settings.citizen_oidc_cookie_name,
        secure=settings.citizen_oidc_cookie_secure,
        samesite="lax",
        path="/",
    )
