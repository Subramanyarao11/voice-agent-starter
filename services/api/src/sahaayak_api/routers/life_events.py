"""Confirmed household life events and bounded Radar triggers."""

from __future__ import annotations

import json
import re
from datetime import UTC, date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from sahaayak_api.citizen_auth import (
    CitizenPrincipal,
    get_or_create_citizen_account,
    require_citizen,
)
from sahaayak_api.rate_limit import apply_rate_limit_headers, enforce_rate_limit
from sahaayak_api.routers.radar import (
    RadarRefreshRequest,
    _require_radar_enabled,
    recalculate_radar_snapshot,
)
from sahaayak_common import (
    CitizenAccount,
    Household,
    HouseholdConsentEvent,
    HouseholdMember,
    LifeEvent,
    ProfileDataEncryptionUnavailable,
    decrypt_profile_value,
    encrypt_profile_value,
    get_session,
    new_id,
    normalize_profile_value,
    profile_value_hash,
)
from sahaayak_contracts import Domain

router = APIRouter(prefix="/api", tags=["household life events"])

_EVENT_DEFINITIONS: dict[str, dict[str, object]] = {
    "moved_residence": {
        "domains": [Domain.SCHEME, Domain.SCHOLARSHIP, Domain.JOB],
        "attribute_keys": {"state_code", "district", "pincode"},
    },
    "started_education": {
        "domains": [Domain.SCHOLARSHIP, Domain.JOB],
        "attribute_keys": {"education_level"},
    },
    "lost_job": {
        "domains": [Domain.SCHEME, Domain.JOB],
        "attribute_keys": {"income_band"},
    },
    "marriage": {"domains": [Domain.SCHEME], "attribute_keys": set()},
    "birth_or_adoption": {
        "domains": [Domain.SCHEME, Domain.SCHOLARSHIP],
        "attribute_keys": set(),
    },
    "disability_assessed": {
        "domains": [Domain.SCHEME, Domain.SCHOLARSHIP, Domain.JOB],
        "attribute_keys": {"disability_status"},
    },
    "retirement": {"domains": [Domain.SCHEME, Domain.JOB], "attribute_keys": set()},
    "income_changed": {
        "domains": [Domain.SCHEME, Domain.SCHOLARSHIP, Domain.JOB],
        "attribute_keys": {"annual_household_income"},
    },
}
_ATTRIBUTE_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
_PRECISIONS = {"day", "month", "year", "unknown"}


class LifeEventCreate(BaseModel):
    household_member_id: str | None = Field(default=None, max_length=160)
    event_key: str = Field(min_length=3, max_length=80)
    occurred_on: date | None = None
    occurred_precision: Literal["day", "month", "year", "unknown"] = "unknown"
    attributes: dict[str, str] = Field(default_factory=dict, max_length=8)
    affected_domains: list[Domain] = Field(default_factory=list, max_length=3)
    confirm: bool = False


class LifeEventOut(BaseModel):
    id: str
    household_member_id: str | None
    event_key: str
    occurred_on: date | None
    occurred_precision: str
    attribute_keys: list[str]
    provenance: str
    status: str
    supersedes_event_id: str | None
    affected_domains: list[Domain]
    created_at: datetime
    updated_at: datetime


class LifeEventTriggerOut(BaseModel):
    event: LifeEventOut
    radar_recalculated: bool


@router.post(
    "/households/{household_id}/life-events",
    response_model=LifeEventTriggerOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_life_event(
    household_id: str,
    payload: LifeEventCreate,
    request: Request,
    response: Response,
    db: Session = Depends(get_session),
    principal: CitizenPrincipal = Depends(require_citizen),
) -> LifeEventTriggerOut:
    account = _account(db, principal)
    household = _owned_household(db, household_id, account.id)
    _require_matching_consent(db, account.id, household.id)
    _require_radar_enabled(account, household)
    decision = await enforce_rate_limit(request, session_id=account.id, bucket="life_event")
    apply_rate_limit_headers(response, decision)
    event, domains = _validated_event(db, household, payload)
    db.add(event)
    db.commit()
    recalculate_radar_snapshot(
        db,
        household,
        RadarRefreshRequest(
            member_id=event.household_member_id,
            domains=domains,
            limit_per_member=50,
        ),
        trigger_type="life_event",
        trigger_reference_hash=profile_value_hash(f"life-event|{event.id}"),
    )
    return LifeEventTriggerOut(event=_event_out(event), radar_recalculated=True)


@router.get("/households/{household_id}/life-events", response_model=list[LifeEventOut])
def list_life_events(
    household_id: str,
    member_id: str | None = None,
    db: Session = Depends(get_session),
    principal: CitizenPrincipal = Depends(require_citizen),
) -> list[LifeEventOut]:
    account = _account(db, principal)
    household = _owned_household(db, household_id, account.id)
    query = select(LifeEvent).where(
        LifeEvent.household_id == household.id,
        LifeEvent.status.in_(["active", "superseded", "removed"]),
    )
    if member_id:
        query = query.where(LifeEvent.household_member_id == member_id)
    rows = db.exec(query.order_by(LifeEvent.created_at.desc()).limit(100)).all()
    return [_event_out(row) for row in rows]


@router.patch(
    "/households/{household_id}/life-events/{event_id}",
    response_model=LifeEventTriggerOut,
)
async def correct_life_event(
    household_id: str,
    event_id: str,
    payload: LifeEventCreate,
    request: Request,
    response: Response,
    db: Session = Depends(get_session),
    principal: CitizenPrincipal = Depends(require_citizen),
) -> LifeEventTriggerOut:
    account = _account(db, principal)
    household = _owned_household(db, household_id, account.id)
    _require_matching_consent(db, account.id, household.id)
    _require_radar_enabled(account, household)
    decision = await enforce_rate_limit(request, session_id=account.id, bucket="life_event")
    apply_rate_limit_headers(response, decision)
    previous = db.exec(
        select(LifeEvent).where(
            LifeEvent.id == event_id,
            LifeEvent.household_id == household.id,
            LifeEvent.status == "active",
        )
    ).first()
    if previous is None:
        raise HTTPException(status_code=404, detail="Life event not found")
    previous.status = "superseded"
    previous.updated_at = datetime.now(UTC)
    event, domains = _validated_event(db, household, payload)
    event.supersedes_event_id = previous.id
    db.add(previous)
    db.add(event)
    db.commit()
    recalculate_radar_snapshot(
        db,
        household,
        RadarRefreshRequest(member_id=event.household_member_id, domains=domains),
        trigger_type="life_event_corrected",
        trigger_reference_hash=profile_value_hash(f"life-event|{event.id}"),
    )
    return LifeEventTriggerOut(event=_event_out(event), radar_recalculated=True)


@router.delete(
    "/households/{household_id}/life-events/{event_id}",
    response_model=LifeEventTriggerOut,
)
async def remove_life_event(
    household_id: str,
    event_id: str,
    request: Request,
    response: Response,
    db: Session = Depends(get_session),
    principal: CitizenPrincipal = Depends(require_citizen),
) -> LifeEventTriggerOut:
    account = _account(db, principal)
    household = _owned_household(db, household_id, account.id)
    _require_matching_consent(db, account.id, household.id)
    _require_radar_enabled(account, household)
    decision = await enforce_rate_limit(request, session_id=account.id, bucket="life_event")
    apply_rate_limit_headers(response, decision)
    event = db.exec(
        select(LifeEvent).where(
            LifeEvent.id == event_id,
            LifeEvent.household_id == household.id,
            LifeEvent.status == "active",
        )
    ).first()
    if event is None:
        raise HTTPException(status_code=404, detail="Life event not found")
    event.status = "removed"
    event.updated_at = datetime.now(UTC)
    db.add(event)
    db.commit()
    recalculate_radar_snapshot(
        db,
        household,
        RadarRefreshRequest(member_id=event.household_member_id, domains=_event_domains(event)),
        trigger_type="life_event_removed",
        trigger_reference_hash=profile_value_hash(f"life-event|{event.id}"),
    )
    return LifeEventTriggerOut(event=_event_out(event), radar_recalculated=True)


def _validated_event(
    db: Session,
    household: Household,
    payload: LifeEventCreate,
) -> tuple[LifeEvent, list[Domain]]:
    if not payload.confirm:
        raise HTTPException(status_code=400, detail="Citizen confirmation is required")
    definition = _EVENT_DEFINITIONS.get(payload.event_key.strip().lower())
    if definition is None:
        raise HTTPException(status_code=422, detail="This life-event type is not available")
    member_id = payload.household_member_id
    if member_id:
        _owned_member(db, household.id, member_id)
    if payload.occurred_precision not in _PRECISIONS:
        raise HTTPException(
            status_code=422,
            detail="The life-event date precision is not supported",
        )
    allowed_keys = definition["attribute_keys"]
    if not isinstance(allowed_keys, set) or any(
        not _ATTRIBUTE_KEY_RE.fullmatch(key) or key not in allowed_keys
        for key in payload.attributes
    ):
        raise HTTPException(status_code=422, detail="This life-event has an unsupported attribute")
    attributes: dict[str, str] = {}
    for key, value in payload.attributes.items():
        try:
            attributes[key] = normalize_profile_value(value)[:160]
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail="Life-event attributes are invalid",
            ) from exc
    configured_domains = [item for item in definition["domains"] if isinstance(item, Domain)]
    requested_domains = list(dict.fromkeys(payload.affected_domains))
    if requested_domains and any(item not in configured_domains for item in requested_domains):
        raise HTTPException(
            status_code=422,
            detail="The selected domain is not valid for this event",
        )
    domains = requested_domains or configured_domains
    serialized = json.dumps(attributes, sort_keys=True, separators=(",", ":"))
    try:
        encrypted = encrypt_profile_value(serialized) if attributes else None
        value_hash = profile_value_hash(serialized) if attributes else ""
    except (ProfileDataEncryptionUnavailable, ValueError) as exc:
        raise HTTPException(status_code=503, detail="Life-event storage is not configured") from exc
    now = datetime.now(UTC)
    return (
        LifeEvent(
            id=new_id("life-event"),
            household_id=household.id,
            household_member_id=member_id,
            event_key=payload.event_key.strip().lower(),
            occurred_on=payload.occurred_on,
            occurred_precision=payload.occurred_precision,
            attributes_ciphertext=encrypted,
            attributes_hash=value_hash,
            provenance="citizen_confirmed",
            confirmed_by="citizen",
            confirmed_at=now,
            affected_domains=[item.value for item in domains],
            created_at=now,
            updated_at=now,
        ),
        domains,
    )


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


def _owned_member(db: Session, household_id: str, member_id: str) -> HouseholdMember:
    row = db.exec(
        select(HouseholdMember).where(
            HouseholdMember.id == member_id,
            HouseholdMember.household_id == household_id,
            HouseholdMember.status == "active",
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Household member not found")
    return row


def _require_matching_consent(db: Session, account_id: str, household_id: str) -> None:
    consent = db.exec(
        select(HouseholdConsentEvent)
        .where(
            HouseholdConsentEvent.citizen_account_id == account_id,
            HouseholdConsentEvent.household_id == household_id,
            HouseholdConsentEvent.purpose == "benefit_matching",
        )
        .order_by(HouseholdConsentEvent.created_at.desc())
    ).first()
    if consent is None or consent.action != "granted":
        raise HTTPException(status_code=403, detail="Benefit-matching consent is required")


def _event_out(row: LifeEvent) -> LifeEventOut:
    return LifeEventOut(
        id=row.id,
        household_member_id=row.household_member_id,
        event_key=row.event_key,
        occurred_on=row.occurred_on,
        occurred_precision=row.occurred_precision,
        attribute_keys=sorted(_attribute_keys(row)),
        provenance=row.provenance,
        status=row.status,
        supersedes_event_id=row.supersedes_event_id,
        affected_domains=[Domain(value) for value in row.affected_domains],
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _attribute_keys(row: LifeEvent) -> set[str]:
    if not row.attributes_ciphertext:
        return set()
    try:
        attributes = json.loads(decrypt_profile_value(row.attributes_ciphertext))
    except (ProfileDataEncryptionUnavailable, ValueError, TypeError, json.JSONDecodeError):
        return set()
    return {key for key in attributes if isinstance(key, str) and _ATTRIBUTE_KEY_RE.fullmatch(key)}


def _event_domains(row: LifeEvent) -> list[Domain]:
    return [Domain(value) for value in row.affected_domains]
