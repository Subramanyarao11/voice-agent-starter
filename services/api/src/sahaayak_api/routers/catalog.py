"""What this deployment currently serves: languages, states, and benefit counts.

The web demo reads these instead of hardcoding a language list, so adding a
language stays a data change end to end.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlmodel import Session, func, select

from sahaayak_common import (
    Benefit,
    DataImportRun,
    Language,
    State,
    get_session,
    language_rollout_enabled,
    state_rollout_enabled,
)
from sahaayak_contracts import Domain, VerificationStatus

router = APIRouter(prefix="/api", tags=["catalog"])


class LanguageOut(BaseModel):
    code: str
    name: str
    native_name: str
    is_active: bool


class StateOut(BaseModel):
    code: str
    name: str
    primary_language_code: str
    is_active: bool


class CoverageOut(BaseModel):
    """Benefit counts per state and domain.

    Useful in the demo for showing honestly how much data is loaded, rather
    than implying nationwide coverage the pipeline has not produced yet.
    """

    by_domain: dict[str, int]
    by_state: dict[str, int]
    total: int
    verified_total: int
    illustrative_total: int
    last_data_update: date | None = None


class BenefitDetailOut(BaseModel):
    """Public benefit details with enough provenance to make trust inspectable."""

    id: str
    domain: Domain
    name: str
    state_code: str | None
    category: str
    description: str
    benefits_text: str
    documents_required: list[str]
    application_process: str
    eligibility_initial: dict
    verification_status: VerificationStatus
    source_title: str
    source_document_url: str
    source_excerpt: str | None
    verified_at: datetime | None
    last_verified_date: date | None
    valid_from: date | None
    valid_until: date | None
    job_metadata: dict[str, Any] = {}


class PublicCatalogOut(BaseModel):
    benefits: list[BenefitDetailOut]
    generated_at: datetime
    schema_version: str = "public-reviewed-v1"


@router.get("/languages", response_model=list[LanguageOut])
def list_languages(db: Session = Depends(get_session)) -> list[LanguageOut]:
    rows = db.exec(select(Language).order_by(Language.code)).all()
    return [
        LanguageOut(
            code=row.code,
            name=row.name,
            native_name=row.native_name,
            is_active=(
                language_rollout_enabled(row.code)
                and row.is_active
            ),
        )
        for row in rows
    ]


@router.get("/states", response_model=list[StateOut])
def list_states(db: Session = Depends(get_session)) -> list[StateOut]:
    rows = db.exec(select(State).order_by(State.code)).all()
    return [
        StateOut(
            code=row.code,
            name=row.name,
            primary_language_code=row.primary_language_code,
            is_active=state_rollout_enabled(row.code),
        )
        for row in rows
    ]


@router.get("/coverage", response_model=CoverageOut)
def coverage(db: Session = Depends(get_session)) -> CoverageOut:
    # `str()` on a str-Enum yields "Domain.SCHOLARSHIP", not the wire value the
    # client expects, so the value is taken explicitly.
    active_filter = cast(Any, Benefit.is_active).is_(True)
    by_domain = {
        (domain.value if isinstance(domain, Domain) else str(domain)): count
        for domain, count in db.exec(
            select(Benefit.domain, func.count())
            .where(active_filter)
            .group_by(Benefit.domain)
        ).all()
    }
    by_state = {
        (state or "central"): count
        for state, count in db.exec(
            select(Benefit.state_code, func.count())
            .where(active_filter)
            .group_by(Benefit.state_code)
        ).all()
    }
    verified_total = db.exec(
        select(func.count())
        .select_from(Benefit)
        .where(active_filter, Benefit.verification_status == VerificationStatus.HUMAN_VERIFIED)
    ).one()
    illustrative_total = db.exec(
        select(func.count())
        .select_from(Benefit)
        .where(active_filter, Benefit.verification_status == VerificationStatus.ILLUSTRATIVE)
    ).one()

    latest_benefit_date = db.exec(
        select(func.max(Benefit.last_verified_date)).where(active_filter)
    ).one()
    latest_import = db.exec(select(func.max(DataImportRun.completed_at))).one()
    latest_import_date = latest_import.date() if latest_import else None
    dates = [value for value in (latest_benefit_date, latest_import_date) if value]

    return CoverageOut(
        by_domain=by_domain,
        by_state=by_state,
        total=sum(by_domain.values()),
        verified_total=int(verified_total or 0),
        illustrative_total=int(illustrative_total or 0),
        last_data_update=max(dates) if dates else None,
    )


@router.get("/benefits/{benefit_id}", response_model=BenefitDetailOut)
def benefit_detail(benefit_id: str, db: Session = Depends(get_session)) -> BenefitDetailOut:
    """Return one active benefit and its source/review metadata."""
    benefit = db.exec(
        select(Benefit).where(
            Benefit.id == benefit_id,
            cast(Any, Benefit.is_active).is_(True),
        )
    ).first()
    if benefit is None:
        raise HTTPException(status_code=404, detail="Benefit not found")

    return _benefit_detail_out(benefit)


@router.get("/public/catalog", response_model=PublicCatalogOut)
def public_catalog(
    response: Response,
    state_code: str | None = Query(default=None, min_length=2, max_length=16),
    limit: int = Query(default=40, ge=1, le=100),
    db: Session = Depends(get_session),
) -> PublicCatalogOut:
    """Serve a cacheable reviewed-only public projection for the PWA.

    This route intentionally has no session, profile, matcher, or ranking
    context. The service worker will cache it only when this marker and the
    reviewed response contract are both present.
    """
    normalized_state = state_code.strip().upper() if state_code else None
    query = select(Benefit).where(
        cast(Any, Benefit.is_active).is_(True),
        Benefit.verification_status == VerificationStatus.HUMAN_VERIFIED,
    )
    if normalized_state:
        query = query.where(
            (Benefit.state_code == normalized_state) | (Benefit.state_code.is_(None))
        )
    rows = db.exec(query.order_by(Benefit.last_verified_date.desc(), Benefit.id).limit(limit)).all()
    payload = PublicCatalogOut(
        benefits=[_benefit_detail_out(row) for row in rows],
        generated_at=datetime.now(UTC),
    )
    etag_source = json.dumps(payload.model_dump(mode="json"), sort_keys=True).encode("utf-8")
    response.headers["Cache-Control"] = "public, max-age=300, stale-while-revalidate=86400"
    response.headers["X-Sahaayak-Cache-Class"] = "public-reviewed-v1"
    response.headers["ETag"] = f'"{hashlib.sha256(etag_source).hexdigest()}"'
    return payload


@router.get("/public/benefits/{benefit_id}", response_model=BenefitDetailOut)
def public_benefit_detail(
    benefit_id: str,
    response: Response,
    db: Session = Depends(get_session),
) -> BenefitDetailOut:
    """Return one reviewed public benefit for safe offline detail caching."""
    benefit = db.exec(
        select(Benefit).where(
            Benefit.id == benefit_id,
            cast(Any, Benefit.is_active).is_(True),
            Benefit.verification_status == VerificationStatus.HUMAN_VERIFIED,
        )
    ).first()
    if benefit is None:
        raise HTTPException(status_code=404, detail="Benefit not found")
    result = _benefit_detail_out(benefit)
    response.headers["Cache-Control"] = "public, max-age=300, stale-while-revalidate=86400"
    response.headers["X-Sahaayak-Cache-Class"] = "public-reviewed-v1"
    etag_source = json.dumps(result.model_dump(mode="json"), sort_keys=True).encode("utf-8")
    response.headers["ETag"] = f'"{hashlib.sha256(etag_source).hexdigest()}"'
    return result


def _benefit_detail_out(benefit: Benefit) -> BenefitDetailOut:
    return BenefitDetailOut(
        id=benefit.id,
        domain=benefit.domain,
        name=benefit.name,
        state_code=benefit.state_code,
        category=benefit.category,
        description=benefit.description,
        benefits_text=benefit.benefits_text,
        documents_required=list(benefit.documents_required or []),
        application_process=benefit.application_process,
        eligibility_initial=dict(benefit.eligibility_initial or {}),
        verification_status=benefit.verification_status,
        source_title=benefit.source_title,
        source_document_url=benefit.source_document_url or benefit.source_url,
        source_excerpt=benefit.source_excerpt,
        verified_at=benefit.verified_at,
        last_verified_date=(
            benefit.last_verified_date
            if benefit.verification_status is VerificationStatus.HUMAN_VERIFIED
            else None
        ),
        valid_from=benefit.valid_from,
        valid_until=benefit.valid_until,
        job_metadata=dict(benefit.job_metadata or {}),
    )
