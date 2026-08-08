"""The structured eligibility schema and the shape of a match decision.

This is the highest-stakes contract in the repository. Everything the agent
tells a caller about whether they qualify is derived from these fields, so
eligibility is parsed once into typed values at ingestion time and is never
re-interpreted from prose at conversation time.
"""

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field

from sahaayak_contracts.domain import (
    Domain,
    EducationLevel,
    Gender,
    SocialCategory,
    VerificationStatus,
)
from sahaayak_contracts.slots import SlotName


class EligibilityCriteria(BaseModel):
    """Machine-checkable conditions extracted from a benefit's source document.

    Every field is optional, and `None` means "the source document does not
    mention this" — materially different from "no restriction applies". A
    criterion that was never stated is simply not checked.
    """

    age_min: int | None = None
    age_max: int | None = None

    max_annual_family_income_inr: int | None = None

    category: list[SocialCategory] | None = None
    gender: Gender | None = None
    occupation: list[str] | None = None

    # An explicit list of acceptable levels, e.g. only UG and PG students.
    education_level: list[EducationLevel] | None = None
    # A floor, e.g. "Class 10 pass or above", checked by rank comparison.
    min_education_level: EducationLevel | None = None

    enrollment_mode: list[str] | None = None  # e.g. ["regular"], excluding correspondence
    state_residency_required: bool = False
    disability_required: bool = False

    # Job-shaped fields. Schemes leave these unset.
    min_experience_years: int | None = None
    locations: list[str] | None = None

    # Conditions that disqualify but are not machine-checkable, e.g. "already
    # receiving another scholarship". Surfaced to the caller as caveats rather
    # than silently dropped.
    exclusions: list[str] = Field(default_factory=list)


class CriterionStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"


class CriterionOutcome(BaseModel):
    """One criterion checked against one caller, kept in human-readable form.

    The agent reads these back to explain *why* a verdict was reached, which is
    the difference between a trustworthy answer and an oracle.
    """

    slot: SlotName
    status: CriterionStatus
    requirement: str  # "annual family income must be at most ₹4,50,000"
    caller_value: str | None = None  # "₹2,00,000"


class MatchVerdict(str, Enum):
    ELIGIBLE = "eligible"
    NOT_ELIGIBLE = "not_eligible"
    # At least one criterion could not be checked because a slot is unfilled.
    # The agent should ask for it rather than guess in either direction.
    INSUFFICIENT_INFO = "insufficient_info"


class EligibilityMatchResult(BaseModel):
    benefit_id: str
    benefit_name: str
    domain: Domain
    verdict: MatchVerdict
    outcomes: list[CriterionOutcome] = Field(default_factory=list)

    # Share of checked criteria that were actually resolvable. A verdict built
    # on mostly-unknown criteria is reported as low confidence, and anything
    # below the escalation threshold offers a human instead of a guess.
    confidence: float = 1.0

    # Caveats copied from `EligibilityCriteria.exclusions` — conditions a
    # machine cannot verify but the caller must know about.
    caveats: list[str] = Field(default_factory=list)

    # Provenance travels with the deterministic decision so every API match can
    # show whether it came from reviewed data or an illustrative row.
    verification_status: VerificationStatus = VerificationStatus.ILLUSTRATIVE
    source_title: str = ""
    source_document_url: str = ""
    verified_at: datetime | None = None
    last_verified_date: date | None = None

    # Present for job-domain results; empty for schemes and scholarships.
    # Values are source metadata, never caller profile data.
    job_metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)

    @property
    def passed(self) -> list[CriterionOutcome]:
        return [o for o in self.outcomes if o.status is CriterionStatus.PASS]

    @property
    def failed(self) -> list[CriterionOutcome]:
        return [o for o in self.outcomes if o.status is CriterionStatus.FAIL]

    @property
    def unresolved(self) -> list[CriterionOutcome]:
        return [o for o in self.outcomes if o.status is CriterionStatus.UNKNOWN]

    @property
    def blocking_slots(self) -> list[SlotName]:
        """Slots that, once filled, would turn this into a definite verdict."""
        return [o.slot for o in self.unresolved]
