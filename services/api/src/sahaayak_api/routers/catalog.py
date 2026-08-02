"""What this deployment currently serves: languages, states, and benefit counts.

The web demo reads these instead of hardcoding a language list, so adding a
language stays a data change end to end.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session, func, select

from sahaayak_common import Benefit, Language, State, get_session

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


@router.get("/languages", response_model=list[LanguageOut])
def list_languages(db: Session = Depends(get_session)) -> list[LanguageOut]:
    rows = db.exec(select(Language).order_by(Language.code)).all()
    return [LanguageOut.model_validate(row.model_dump()) for row in rows]


@router.get("/states", response_model=list[StateOut])
def list_states(db: Session = Depends(get_session)) -> list[StateOut]:
    rows = db.exec(select(State).order_by(State.code)).all()
    return [StateOut.model_validate(row.model_dump()) for row in rows]


@router.get("/coverage", response_model=CoverageOut)
def coverage(db: Session = Depends(get_session)) -> CoverageOut:
    by_domain = {
        str(domain): count
        for domain, count in db.exec(
            select(Benefit.domain, func.count()).group_by(Benefit.domain)
        ).all()
    }
    by_state = {
        (state or "central"): count
        for state, count in db.exec(
            select(Benefit.state_code, func.count()).group_by(Benefit.state_code)
        ).all()
    }
    return CoverageOut(
        by_domain=by_domain, by_state=by_state, total=sum(by_domain.values())
    )
