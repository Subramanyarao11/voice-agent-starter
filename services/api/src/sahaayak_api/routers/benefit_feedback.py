"""Citizen reports about incorrect public benefit information."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from sahaayak_api.browser_auth import BrowserSessionPrincipal, require_browser_session
from sahaayak_api.rate_limit import apply_rate_limit_headers, enforce_rate_limit
from sahaayak_common import Benefit, BenefitIssueReport, get_session, new_id

router = APIRouter(prefix="/api/benefits", tags=["benefit feedback"])

IssueCategory = Literal["source", "eligibility", "deadline", "application", "other"]


class BenefitIssueReportRequest(BaseModel):
    category: IssueCategory
    description: str = Field(min_length=5, max_length=1000)


class BenefitIssueReportOut(BaseModel):
    id: str
    benefit_id: str
    category: str
    status: str
    created_at: datetime


@router.post(
    "/{benefit_id}/reports",
    response_model=BenefitIssueReportOut,
    status_code=status.HTTP_201_CREATED,
)
async def report_benefit_issue(
    benefit_id: str,
    payload: BenefitIssueReportRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_session),
    principal: BrowserSessionPrincipal = Depends(require_browser_session),
) -> BenefitIssueReportOut:
    decision = await enforce_rate_limit(
        request, session_id=principal.session_id, bucket="feedback"
    )
    apply_rate_limit_headers(response, decision)

    benefit = db.exec(
        select(Benefit).where(Benefit.id == benefit_id, Benefit.is_active.is_(True))
    ).first()
    if benefit is None:
        # Do not disclose whether an inactive/private row exists.
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Benefit not found")

    row = BenefitIssueReport(
        id=new_id("issue"),
        benefit_id=benefit.id,
        session_id=principal.session_id,
        category=payload.category,
        description=payload.description.strip(),
        locale=principal.language_code,
        safe_context={
            "domain": benefit.domain.value,
            "verification_status": benefit.verification_status.value,
            "source_title": benefit.source_title,
        },
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return BenefitIssueReportOut.model_validate(row.model_dump())
