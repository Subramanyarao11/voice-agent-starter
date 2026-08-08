"""Reading benefits out of the database for the matcher.

Candidate selection is deliberately broad — narrow by domain and geography,
then let the deterministic matcher do the actual reasoning. Filtering in SQL on
eligibility would push judgement into a query where it cannot be explained back
to the caller.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, ValidationError
from sqlmodel import Session, or_, select

from sahaayak_common import Benefit, get_logger
from sahaayak_contracts import Domain, EligibilityCriteria

log = get_logger(__name__)

# A cap on how many benefits one turn evaluates. Matching is cheap, but an
# unbounded scan on a growing corpus would eventually be felt on a live call.
MAX_CANDIDATES = 400


def load_candidates(
    session: Session,
    *,
    domain: Domain,
    state_code: str | None,
    limit: int = MAX_CANDIDATES,
) -> list[Benefit]:
    """Benefits in this domain that could apply to a caller in this state.

    Central schemes have a NULL state and apply everywhere, so they are always
    included alongside the state's own.
    """
    statement = select(Benefit).where(
        Benefit.domain == domain,
        Benefit.is_active.is_(True),
        # A posting whose application window has closed must not remain a
        # match merely because an operator forgot to flip is_active. Schemes
        # without an expiry keep the NULL branch.
        or_(Benefit.valid_until.is_(None), Benefit.valid_until >= date.today()),
    )
    if state_code:
        statement = statement.where(
            or_(Benefit.state_code == state_code, Benefit.state_code.is_(None))
        )
    else:
        statement = statement.where(Benefit.state_code.is_(None))
    return list(session.exec(statement.limit(limit)).all())


def criteria_for(benefit: Benefit) -> EligibilityCriteria:
    """Parse a benefit's stored eligibility into the typed schema.

    Malformed stored criteria yield empty criteria rather than an exception:
    one bad ingestion row should not take down a call. The row still surfaces,
    but with no checkable criteria it lands at low confidence and is routed to
    a human, which is the correct outcome for data we cannot trust.
    """
    raw = benefit.eligibility_initial or {}
    try:
        return EligibilityCriteria.model_validate(raw)
    except ValidationError as exc:
        log.warning(
            "unparseable_eligibility_criteria",
            benefit_id=benefit.id,
            errors=exc.error_count(),
        )
        return EligibilityCriteria()


def summary_for(benefit: Benefit, language_code: str) -> str:
    """The voice-ready blurb, preferring a pre-translated one.

    Translating during a call would add a model round-trip to every result, so
    anything not translated at ingestion falls back to the English description.
    """
    localized = benefit.localized_summary or {}
    return localized.get(language_code) or benefit.description or benefit.benefits_text


class BenefitBrief(BaseModel):
    """The fields the response composer needs, detached from the ORM.

    Returned instead of a `Benefit` row because the composer runs after its
    session has closed, and a detached row raises on first attribute access
    rather than returning what it already loaded.
    """

    id: str
    name: str
    summary: str = ""
    application_process: str = ""
    documents_required: list[str] = Field(default_factory=list)
    source_url: str = ""


def load_briefs(
    session: Session, benefit_ids: list[str], language_code: str
) -> dict[str, BenefitBrief]:
    briefs: dict[str, BenefitBrief] = {}
    for benefit_id in benefit_ids:
        benefit = session.get(Benefit, benefit_id)
        if benefit is None:
            continue
        briefs[benefit_id] = BenefitBrief(
            id=benefit.id,
            name=benefit.name,
            summary=summary_for(benefit, language_code),
            application_process=benefit.application_process,
            documents_required=list(benefit.documents_required or []),
            source_url=benefit.source_url,
        )
    return briefs
