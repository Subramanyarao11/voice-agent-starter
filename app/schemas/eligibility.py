"""
Structured eligibility schema. This is the single most important file in the
repo — everything downstream (matching accuracy, voice reasoning, explainability)
depends on eligibility being parsed into these fields correctly, not left as
free text. See spec-v2 section 4 for the CSSS worked example this was built from.
"""

from pydantic import BaseModel, Field


class EligibilityCriteria(BaseModel):
    age_min: int | None = None
    age_max: int | None = None
    max_annual_family_income_inr: int | None = None
    category: list[str] | None = None  # ["SC", "ST", "OBC", "EWS", "General"]
    gender: str | None = None
    occupation: list[str] | None = None
    education_level: list[str] | None = None  # ["UG", "PG", "Class 10", ...]
    enrollment_mode: list[str] | None = None  # ["regular"], excludes correspondence
    state_residency_required: bool = False
    exclusions: list[str] = Field(default_factory=list)


class EligibilityMatchResult(BaseModel):
    """Returned to the agent's response-composer node — drives the
    'why you qualify / why you don't' explainability feature."""
    benefit_id: str
    is_eligible: bool
    matched_criteria: list[str]
    failed_criteria: list[str]
    confidence: float  # < 0.7 should trigger human-escalation offer
