"""The slots the agent collects, and the order it should ask for them.

Slots are the pivot that makes the agent language-agnostic. Speech in any
language is normalised into these typed values, every reasoning step operates
on them, and only the final response is rendered back into the caller's
language. Adding a language therefore never touches this file.
"""

from enum import Enum

from pydantic import BaseModel, Field

from sahaayak_contracts.domain import Domain, EducationLevel, Gender, SocialCategory


class SlotName(str, Enum):
    AGE = "age"
    GENDER = "gender"
    SOCIAL_CATEGORY = "social_category"
    ANNUAL_FAMILY_INCOME = "annual_family_income"
    EDUCATION_LEVEL = "education_level"
    OCCUPATION = "occupation"
    ENROLLMENT_MODE = "enrollment_mode"
    STATE_RESIDENCY = "state_residency"
    DISABILITY = "disability"
    EXPERIENCE_YEARS = "experience_years"
    LOCATION = "location"


class SlotKind(str, Enum):
    INTEGER = "integer"
    MONEY = "money"
    ENUM = "enum"
    BOOLEAN = "boolean"
    TEXT = "text"


class SlotSpec(BaseModel):
    """Everything the dialogue manager needs to ask for and validate one slot."""

    name: SlotName
    kind: SlotKind

    # Key into the per-language prompt catalog. The catalog holds the actual
    # question wording; this contract stays free of any natural language.
    prompt_key: str

    # Lower numbers are asked first. Ordered by how sharply the answer narrows
    # the candidate set, so a caller who hangs up early has still been asked
    # the questions that matter most.
    priority: int

    choices: list[str] | None = None
    domains: set[Domain] = Field(default_factory=lambda: set(Domain))

    def applies_to(self, domain: Domain) -> bool:
        return domain in self.domains


SLOT_REGISTRY: dict[SlotName, SlotSpec] = {
    spec.name: spec
    for spec in [
        SlotSpec(
            name=SlotName.AGE,
            kind=SlotKind.INTEGER,
            prompt_key="ask_age",
            priority=10,
        ),
        SlotSpec(
            name=SlotName.ANNUAL_FAMILY_INCOME,
            kind=SlotKind.MONEY,
            prompt_key="ask_income",
            priority=20,
            domains={Domain.SCHEME, Domain.SCHOLARSHIP},
        ),
        SlotSpec(
            name=SlotName.SOCIAL_CATEGORY,
            kind=SlotKind.ENUM,
            prompt_key="ask_social_category",
            priority=30,
            choices=[c.value for c in SocialCategory],
            domains={Domain.SCHEME, Domain.SCHOLARSHIP},
        ),
        SlotSpec(
            name=SlotName.EDUCATION_LEVEL,
            kind=SlotKind.ENUM,
            prompt_key="ask_education",
            priority=40,
            choices=[e.value for e in EducationLevel],
        ),
        SlotSpec(
            name=SlotName.GENDER,
            kind=SlotKind.ENUM,
            prompt_key="ask_gender",
            priority=50,
            choices=[g.value for g in Gender],
        ),
        SlotSpec(
            name=SlotName.OCCUPATION,
            kind=SlotKind.TEXT,
            prompt_key="ask_occupation",
            priority=60,
            domains={Domain.SCHEME, Domain.JOB},
        ),
        SlotSpec(
            name=SlotName.ENROLLMENT_MODE,
            kind=SlotKind.ENUM,
            prompt_key="ask_enrollment_mode",
            priority=70,
            choices=["regular", "distance", "correspondence", "not_studying"],
            domains={Domain.SCHOLARSHIP},
        ),
        SlotSpec(
            name=SlotName.DISABILITY,
            kind=SlotKind.BOOLEAN,
            prompt_key="ask_disability",
            priority=80,
        ),
        SlotSpec(
            name=SlotName.STATE_RESIDENCY,
            kind=SlotKind.BOOLEAN,
            prompt_key="ask_state_residency",
            priority=90,
        ),
        SlotSpec(
            name=SlotName.EXPERIENCE_YEARS,
            kind=SlotKind.INTEGER,
            prompt_key="ask_experience",
            priority=100,
            domains={Domain.JOB},
        ),
        SlotSpec(
            name=SlotName.LOCATION,
            kind=SlotKind.TEXT,
            prompt_key="ask_location",
            priority=110,
            domains={Domain.JOB},
        ),
    ]
}


def slots_for_domain(domain: Domain) -> list[SlotSpec]:
    """Every slot relevant to a domain, in the order the agent should ask."""
    return sorted(
        (spec for spec in SLOT_REGISTRY.values() if spec.applies_to(domain)),
        key=lambda spec: spec.priority,
    )


# The agent will not attempt a match before these are known: without them
# nearly every candidate comes back as "insufficient information", which is a
# worse caller experience than two more questions.
MINIMUM_SLOTS: dict[Domain, list[SlotName]] = {
    Domain.SCHEME: [SlotName.AGE, SlotName.ANNUAL_FAMILY_INCOME],
    Domain.SCHOLARSHIP: [
        SlotName.AGE,
        SlotName.ANNUAL_FAMILY_INCOME,
        SlotName.EDUCATION_LEVEL,
    ],
    Domain.JOB: [SlotName.AGE, SlotName.EDUCATION_LEVEL],
}
