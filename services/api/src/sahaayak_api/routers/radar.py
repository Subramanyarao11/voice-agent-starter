"""Consent-bound Household Benefits Radar recommendations.

Radar is a stored snapshot, not a new eligibility oracle. It only evaluates
active, human-verified benefits against current, purpose-approved facts. The
matcher remains deterministic; persisted evidence omits raw profile values
and records which governed fact or household context was used.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlmodel import Session, or_, select

from sahaayak_agent import matcher, repository
from sahaayak_api.citizen_auth import (
    CitizenPrincipal,
    get_or_create_citizen_account,
    require_citizen,
)
from sahaayak_api.rate_limit import apply_rate_limit_headers, enforce_rate_limit
from sahaayak_common import (
    Benefit,
    CitizenAccount,
    Household,
    HouseholdMember,
    MemberRecommendation,
    ProfileDataEncryptionUnavailable,
    ProfileFact,
    ProfileFactDefinition,
    decrypt_profile_value,
    feature_flag_enabled,
    get_session,
    new_id,
    settings,
)
from sahaayak_contracts import (
    CriterionStatus,
    Domain,
    EligibilityMatchResult,
    MatchVerdict,
    SlotName,
    VerificationStatus,
)

router = APIRouter(prefix="/api", tags=["household radar"])

_RADAR_VERSION = "household-radar-v1"
_SLOT_TO_FACT_KEY = {
    SlotName.AGE: "age_band",
    SlotName.ANNUAL_FAMILY_INCOME: "annual_household_income",
    SlotName.EDUCATION_LEVEL: "education_level",
    SlotName.LOCATION: "district",
    SlotName.STATE_RESIDENCY: "state_code",
}
_EDUCATION_VALUE_MAP = {
    "none": "none",
    "primary": "primary",
    # The current household form deliberately treats an ambiguous secondary
    # answer as unknown rather than guessing whether it means class 8 or 10.
    "higher_secondary": "class_12",
    "graduate": "UG",
    "postgraduate": "PG",
    "vocational": "iti_diploma",
}


class RadarRefreshRequest(BaseModel):
    member_id: str | None = Field(default=None, max_length=160)
    domains: list[Domain] = Field(default_factory=lambda: list(Domain), max_length=3)
    limit_per_member: int = Field(default=50, ge=1, le=100)


class RadarActionRequest(BaseModel):
    action: Literal["view", "snooze", "dismiss"]
    snooze_until: datetime | None = None
    reason_code: str = Field(default="", max_length=80)


class CriterionEvidenceOut(BaseModel):
    slot: str
    status: str
    requirement: str
    fact_key: str = ""
    fact_state: str = "not_collected"
    evidence_source: str = ""


class RadarRecommendationOut(BaseModel):
    id: str
    household_member_id: str
    member_ordinal: str
    benefit_id: str
    benefit_name: str
    domain: Domain
    verdict: str
    confidence: float
    state: str
    reason_codes: list[str]
    criterion_evidence: list[CriterionEvidenceOut]
    fact_use_evidence: list[dict]
    source_title: str
    source_url: str
    source_last_verified_date: date | None
    valid_until: date | None
    benefit_revision: int
    matcher_rules_version: str
    computed_profile_version: str
    viewed_at: datetime | None
    snoozed_until: datetime | None
    dismissed_at: datetime | None
    updated_at: datetime


class RadarRefreshOut(BaseModel):
    household_id: str
    generated_at: datetime
    profile_version: str
    recommendation_count: int
    counts_by_verdict: dict[str, int]
    recommendations: list[RadarRecommendationOut]


class RadarListOut(BaseModel):
    household_id: str
    generated_at: datetime
    recommendations: list[RadarRecommendationOut]
    counts_by_state: dict[str, int]


@router.post(
    "/households/{household_id}/radar/refresh",
    response_model=RadarRefreshOut,
)
async def refresh_radar(
    household_id: str,
    payload: RadarRefreshRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_session),
    principal: CitizenPrincipal = Depends(require_citizen),
) -> RadarRefreshOut:
    account = _account(db, principal)
    household = _owned_household(db, household_id, account.id)
    _require_radar_enabled(account, household)
    decision = await enforce_rate_limit(request, session_id=account.id, bucket="radar")
    apply_rate_limit_headers(response, decision)

    members = _members(db, household, member_id=payload.member_id)
    candidates = _reviewed_candidates(
        db,
        state_code=household.state_code,
        domains=payload.domains,
        limit=payload.limit_per_member,
    )
    generated_at = datetime.now(UTC)
    all_recommendations: list[MemberRecommendation] = []
    verdict_counts: dict[str, int] = {}
    profile_versions: list[str] = []
    for member in members:
        profile = _profile_for_member(db, household, member)
        profile_versions.append(profile.version)
        for benefit in candidates:
            result = _evaluate(benefit, household, profile.slots)
            recommendation = _upsert_recommendation(
                db,
                household=household,
                member=member,
                benefit=benefit,
                result=result,
                profile=profile,
                generated_at=generated_at,
            )
            all_recommendations.append(recommendation)
            verdict_counts[result.verdict.value] = verdict_counts.get(result.verdict.value, 0) + 1

    db.commit()
    recommendations = _order_recommendations(all_recommendations)
    return RadarRefreshOut(
        household_id=household.id,
        generated_at=generated_at,
        profile_version=_combine_profile_versions(profile_versions),
        recommendation_count=len(recommendations),
        counts_by_verdict=verdict_counts,
        recommendations=[_recommendation_out(db, row) for row in recommendations],
    )


@router.get(
    "/households/{household_id}/radar",
    response_model=RadarListOut,
)
def list_radar(
    household_id: str,
    member_id: str | None = None,
    include_dismissed: bool = False,
    limit: int = 100,
    db: Session = Depends(get_session),
    principal: CitizenPrincipal = Depends(require_citizen),
) -> RadarListOut:
    account = _account(db, principal)
    household = _owned_household(db, household_id, account.id)
    _require_radar_enabled(account, household)
    members = _members(db, household, member_id=member_id)
    member_ids = [member.id for member in members]
    query = select(MemberRecommendation).where(
        MemberRecommendation.household_id == household.id,
        MemberRecommendation.household_member_id.in_(member_ids),
    )
    if not include_dismissed:
        query = query.where(MemberRecommendation.state != "dismissed")
    rows = db.exec(
        query.order_by(
            MemberRecommendation.deterministic_score.desc(),
            MemberRecommendation.updated_at.desc(),
        ).limit(max(1, min(limit, 200)))
    ).all()
    rows = _order_recommendations(rows)
    generated_at = max((row.last_generated_at for row in rows), default=datetime.now(UTC))
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.state] = counts.get(row.state, 0) + 1
    return RadarListOut(
        household_id=household.id,
        generated_at=generated_at,
        recommendations=[_recommendation_out(db, row) for row in rows],
        counts_by_state=counts,
    )


@router.post(
    "/households/{household_id}/radar/{recommendation_id}",
    response_model=RadarRecommendationOut,
)
def update_radar_recommendation(
    household_id: str,
    recommendation_id: str,
    payload: RadarActionRequest,
    db: Session = Depends(get_session),
    principal: CitizenPrincipal = Depends(require_citizen),
) -> RadarRecommendationOut:
    account = _account(db, principal)
    household = _owned_household(db, household_id, account.id)
    _require_radar_enabled(account, household)
    row = db.get(MemberRecommendation, recommendation_id)
    if row is None or row.household_id != household.id:
        raise HTTPException(status_code=404, detail="Radar recommendation not found")
    now = datetime.now(UTC)
    if payload.action == "view":
        row.state = "viewed"
        row.viewed_at = now
    elif payload.action == "dismiss":
        row.state = "dismissed"
        row.dismissed_at = now
        row.dismissal_reason_code = payload.reason_code.strip()[:80]
    else:
        if payload.snooze_until is None:
            raise HTTPException(status_code=422, detail="snooze_until is required")
        snooze_until = _as_utc(payload.snooze_until)
        if snooze_until <= now or snooze_until > now + timedelta(days=90):
            raise HTTPException(status_code=422, detail="snooze_until must be within 90 days")
        row.state = "snoozed"
        row.snoozed_until = snooze_until
    row.updated_at = now
    db.add(row)
    db.commit()
    db.refresh(row)
    return _recommendation_out(db, row)


class _ProfileSnapshot:
    def __init__(self) -> None:
        self.slots: dict[SlotName, str | int | bool] = {}
        self.fact_states: dict[str, str] = {}
        self.fact_versions: dict[str, int] = {}
        self.fact_use_evidence: list[dict] = []
        self.version = ""


def _account(db: Session, principal: CitizenPrincipal) -> CitizenAccount:
    account = get_or_create_citizen_account(db, principal)
    account.last_login_at = datetime.now(UTC)
    db.add(account)
    db.flush()
    return account


def _owned_household(db: Session, household_id: str, account_id: str) -> Household:
    row = db.exec(
        select(Household).where(
            Household.id == household_id,
            Household.owner_account_id == account_id,
            Household.status == "active",
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Household not found")
    return row


def _members(
    db: Session,
    household: Household,
    *,
    member_id: str | None,
) -> list[HouseholdMember]:
    if member_id:
        row = db.exec(
            select(HouseholdMember).where(
                HouseholdMember.id == member_id,
                HouseholdMember.household_id == household.id,
                HouseholdMember.status == "active",
            )
        ).first()
        if row is None:
            raise HTTPException(status_code=404, detail="Household member not found")
        return [row]
    return db.exec(
        select(HouseholdMember)
        .where(
            HouseholdMember.household_id == household.id,
            HouseholdMember.status == "active",
        )
        .order_by(HouseholdMember.safe_ordinal)
    ).all()


def _require_radar_enabled(account: CitizenAccount, household: Household) -> None:
    if not feature_flag_enabled(
        "household_radar",
        subject=account.id,
        state_code=household.state_code,
    ):
        raise HTTPException(status_code=404, detail="Household Radar is not enabled")


def _reviewed_candidates(
    db: Session,
    *,
    state_code: str | None,
    domains: list[Domain],
    limit: int,
) -> list[Benefit]:
    cutoff = date.today() - timedelta(days=max(1, settings.freshness_stale_days))
    state_filter = (
        or_(Benefit.state_code == state_code, Benefit.state_code.is_(None))
        if state_code
        else Benefit.state_code.is_(None)
    )
    return db.exec(
        select(Benefit)
        .where(
            Benefit.is_active.is_(True),
            Benefit.verification_status == VerificationStatus.HUMAN_VERIFIED,
            Benefit.domain.in_(domains),
            state_filter,
            or_(Benefit.valid_until.is_(None), Benefit.valid_until >= date.today()),
            Benefit.last_verified_date >= cutoff,
            Benefit.source_url != "",
        )
        .order_by(Benefit.name)
        .limit(max(1, min(limit, 100)))
    ).all()


def _profile_for_member(
    db: Session,
    household: Household,
    member: HouseholdMember,
) -> _ProfileSnapshot:
    snapshot = _ProfileSnapshot()
    if household.state_code:
        snapshot.fact_states["state_code"] = "context"
    definitions = db.exec(
        select(ProfileFactDefinition)
        .where(ProfileFactDefinition.review_status == "approved")
        .order_by(ProfileFactDefinition.fact_key, ProfileFactDefinition.version.desc())
    ).all()
    latest_definitions: dict[str, ProfileFactDefinition] = {}
    for definition in definitions:
        latest_definitions.setdefault(definition.fact_key, definition)

    facts = db.exec(
        select(ProfileFact).where(
            ProfileFact.household_id == household.id,
            ProfileFact.status == "current",
        )
    ).all()
    selected: dict[str, tuple[ProfileFact, ProfileFactDefinition]] = {}
    now = datetime.now(UTC)
    for fact in facts:
        definition = latest_definitions.get(fact.fact_key)
        if definition is None or "benefit_matching" not in fact.purposes:
            continue
        is_member_fact = fact.household_member_id == member.id
        is_household_fact = fact.household_member_id is None and definition.inheritance_allowed
        if not (is_member_fact or is_household_fact):
            continue
        state = (
            "stale"
            if _past(fact.reconfirm_after, now) or _past(fact.expires_at, now)
            else "current"
        )
        current = selected.get(fact.fact_key)
        if current is None or (is_member_fact and current[0].household_member_id is None):
            selected[fact.fact_key] = (fact, definition)
        snapshot.fact_states[fact.fact_key] = state

    # A member fact wins over an inherited household fact, and its effective
    # freshness must not depend on the database's row-return order.
    for fact_key, (fact, _definition) in selected.items():
        snapshot.fact_states[fact_key] = (
            "stale"
            if _past(fact.reconfirm_after, now) or _past(fact.expires_at, now)
            else "current"
        )

    for fact_key, definition in latest_definitions.items():
        if "benefit_matching" in definition.allowed_purposes and definition.matcher_slot:
            snapshot.fact_states.setdefault(fact_key, "missing")

    for fact_key, (fact, definition) in selected.items():
        if snapshot.fact_states.get(fact_key) != "current":
            continue
        try:
            value = decrypt_profile_value(fact.value_ciphertext)
        except (ProfileDataEncryptionUnavailable, ValueError):
            snapshot.fact_states[fact_key] = "unavailable"
            continue
        slot, converted = _fact_to_slot(fact_key, definition.matcher_slot, value)
        if slot is None or converted is None:
            snapshot.fact_states[fact_key] = "unsupported"
            continue
        snapshot.slots[slot] = converted
        snapshot.fact_versions[fact_key] = fact.revision
        snapshot.fact_use_evidence.append(
            {
                "fact_key": fact_key,
                "definition_version": definition.version,
                "fact_revision": fact.revision,
                "scope": "member" if fact.household_member_id else "household_inherited",
                "source": "citizen_confirmed",
            }
        )
    snapshot.version = _profile_version(household, member, snapshot.fact_versions)
    return snapshot


def _fact_to_slot(
    fact_key: str,
    matcher_slot: str | None,
    value: str,
) -> tuple[SlotName | None, str | int | bool | None]:
    slot_name = matcher_slot or fact_key
    if slot_name == "age_band":
        return SlotName.AGE, value if value in {"child", "youth", "adult", "senior"} else None
    if slot_name == "annual_household_income":
        try:
            return SlotName.ANNUAL_FAMILY_INCOME, int(value)
        except ValueError:
            return None, None
    if slot_name == "education_level":
        return SlotName.EDUCATION_LEVEL, _EDUCATION_VALUE_MAP.get(value)
    if slot_name == "district":
        return SlotName.LOCATION, value
    return None, None


def _evaluate(
    benefit: Benefit,
    household: Household,
    slots: dict[SlotName, str | int | bool],
) -> EligibilityMatchResult:
    benefit_slots = dict(slots)
    if benefit.state_code and household.state_code:
        benefit_slots[SlotName.STATE_RESIDENCY] = benefit.state_code == household.state_code
    return matcher.evaluate(
        repository.criteria_for(benefit),
        benefit_slots,
        benefit_id=benefit.id,
        benefit_name=benefit.name,
        domain=benefit.domain,
        benefit_state=benefit.state_code,
        verification_status=benefit.verification_status,
        source_title=benefit.source_title,
        source_document_url=benefit.source_document_url or benefit.source_url,
        verified_at=benefit.verified_at,
        last_verified_date=benefit.last_verified_date,
        job_metadata=benefit.job_metadata,
    )


def _upsert_recommendation(
    db: Session,
    *,
    household: Household,
    member: HouseholdMember,
    benefit: Benefit,
    result: EligibilityMatchResult,
    profile: _ProfileSnapshot,
    generated_at: datetime,
) -> MemberRecommendation:
    row = db.exec(
        select(MemberRecommendation).where(
            MemberRecommendation.household_member_id == member.id,
            MemberRecommendation.benefit_id == benefit.id,
            MemberRecommendation.benefit_revision == benefit.content_revision,
        )
    ).first()
    criterion_evidence = _criterion_evidence(result, profile.fact_states)
    reason_codes = _reason_codes(result, profile.fact_states)
    if row is None:
        row = MemberRecommendation(
            id=new_id("recommendation"),
            household_id=household.id,
            household_member_id=member.id,
            benefit_id=benefit.id,
            benefit_revision=benefit.content_revision,
            matcher_rules_version=_RADAR_VERSION,
            computed_profile_version=profile.version,
            verdict=result.verdict.value,
            state="new",
            deterministic_score=_score(result),
            reason_codes=reason_codes,
            criterion_evidence=criterion_evidence,
            fact_use_evidence=list(profile.fact_use_evidence),
            trigger_type="manual_refresh",
            trigger_reference_hash=_safe_hash(
                {"member": member.id, "benefit": benefit.id, "generated": generated_at.isoformat()}
            ),
            first_generated_at=generated_at,
            last_generated_at=generated_at,
            source_deadline=benefit.valid_until,
            source_last_verified_date=benefit.last_verified_date,
            created_at=generated_at,
            updated_at=generated_at,
        )
    else:
        row.computed_profile_version = profile.version
        row.verdict = result.verdict.value
        row.deterministic_score = _score(result)
        row.reason_codes = reason_codes
        row.criterion_evidence = criterion_evidence
        row.fact_use_evidence = list(profile.fact_use_evidence)
        row.last_generated_at = generated_at
        row.source_deadline = benefit.valid_until
        row.source_last_verified_date = benefit.last_verified_date
        row.updated_at = generated_at
        if (
            row.state == "snoozed"
            and row.snoozed_until is not None
            and _as_utc(row.snoozed_until) <= generated_at
        ):
            row.state = "new"
            row.snoozed_until = None
    db.add(row)
    return row


def _criterion_evidence(
    result: EligibilityMatchResult,
    fact_states: dict[str, str],
) -> list[dict]:
    evidence: list[dict] = []
    for outcome in result.outcomes:
        fact_key = _SLOT_TO_FACT_KEY.get(outcome.slot, "")
        default_state = "context" if outcome.slot is SlotName.STATE_RESIDENCY else "not_collected"
        state = fact_states.get(fact_key, default_state)
        source = "confirmed_profile_fact" if state == "current" else "missing_or_stale_profile_fact"
        if outcome.slot is SlotName.STATE_RESIDENCY and state == "context":
            source = "household_state_context"
        evidence.append(
            {
                "slot": outcome.slot.value,
                "status": outcome.status.value,
                "requirement": outcome.requirement,
                "fact_key": fact_key,
                "fact_state": state,
                "evidence_source": source,
            }
        )
    return evidence


def _reason_codes(result: EligibilityMatchResult, fact_states: dict[str, str]) -> list[str]:
    codes = []
    if result.verdict is MatchVerdict.ELIGIBLE:
        codes.append("criteria_passed")
    elif result.verdict is MatchVerdict.NOT_ELIGIBLE:
        codes.append("criterion_failed")
    else:
        codes.append("missing_or_uncertain_criterion")
    if any(state in {"stale", "unavailable", "unsupported"} for state in fact_states.values()):
        codes.append("profile_fact_needs_confirmation")
    if result.caveats:
        codes.append("source_caveat")
    codes.append("human_verified_source")
    return codes


def _score(result: EligibilityMatchResult) -> float:
    verdict_weight = {
        MatchVerdict.ELIGIBLE: 1.0,
        MatchVerdict.INSUFFICIENT_INFO: 0.5,
        MatchVerdict.NOT_ELIGIBLE: 0.0,
    }
    return round(verdict_weight[result.verdict] * result.confidence, 4)


def _recommendation_out(db: Session, row: MemberRecommendation) -> RadarRecommendationOut:
    benefit = db.get(Benefit, row.benefit_id)
    member = db.get(HouseholdMember, row.household_member_id)
    if benefit is None or member is None:
        raise HTTPException(status_code=404, detail="Radar recommendation is no longer available")
    return RadarRecommendationOut(
        id=row.id,
        household_member_id=row.household_member_id,
        member_ordinal=member.safe_ordinal,
        benefit_id=benefit.id,
        benefit_name=benefit.name,
        domain=benefit.domain,
        verdict=row.verdict,
        confidence=_confidence_from_evidence(row.criterion_evidence, row.verdict),
        state=row.state,
        reason_codes=list(row.reason_codes),
        criterion_evidence=[CriterionEvidenceOut(**item) for item in row.criterion_evidence],
        fact_use_evidence=list(row.fact_use_evidence),
        source_title=benefit.source_title,
        source_url=benefit.source_document_url or benefit.source_url,
        source_last_verified_date=row.source_last_verified_date,
        valid_until=row.source_deadline,
        benefit_revision=row.benefit_revision,
        matcher_rules_version=row.matcher_rules_version,
        computed_profile_version=row.computed_profile_version,
        viewed_at=row.viewed_at,
        snoozed_until=row.snoozed_until,
        dismissed_at=row.dismissed_at,
        updated_at=row.updated_at,
    )


def _confidence_from_evidence(evidence: list[dict], verdict: str) -> float:
    if not evidence:
        return 0.4 if verdict == MatchVerdict.ELIGIBLE.value else 0.0
    known = sum(item.get("status") != CriterionStatus.UNKNOWN.value for item in evidence)
    if verdict == MatchVerdict.INSUFFICIENT_INFO.value:
        return round(known / len(evidence), 2)
    return 1.0


def _order_recommendations(rows: list[MemberRecommendation]) -> list[MemberRecommendation]:
    verdict_order = {
        MatchVerdict.ELIGIBLE.value: 0,
        MatchVerdict.INSUFFICIENT_INFO.value: 1,
        MatchVerdict.NOT_ELIGIBLE.value: 2,
    }
    return sorted(
        rows,
        key=lambda row: (
            verdict_order.get(row.verdict, 3),
            -row.deterministic_score,
            row.member_id if hasattr(row, "member_id") else row.household_member_id,
        ),
    )


def _profile_version(
    household: Household,
    member: HouseholdMember,
    fact_versions: dict[str, int],
) -> str:
    return _safe_hash(
        {
            "policy": household.matching_policy_version,
            "household_revision": household.revision,
            "member": member.id,
            "member_revision": member.revision,
            "facts": sorted(fact_versions.items()),
        }
    )[:24]


def _combine_profile_versions(versions: list[str]) -> str:
    return _safe_hash({"members": sorted(versions)})[:24]


def _safe_hash(value: dict) -> str:
    encoded = repr(sorted(value.items())).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _past(value: datetime | None, now: datetime) -> bool:
    if value is None:
        return False
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value <= now


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)
