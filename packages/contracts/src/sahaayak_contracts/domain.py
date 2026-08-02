"""Enumerations that classify what the agent is talking about.

`Domain` is deliberately open to extension: anything with eligibility rules,
a benefit, and an application process fits the same `Benefit` record, so a new
domain is a new enum member plus a data source, not new reasoning code.
"""

from enum import Enum


class Domain(str, Enum):
    SCHEME = "scheme"
    SCHOLARSHIP = "scholarship"
    JOB = "job"


class VerificationStatus(str, Enum):
    """How much human review a benefit row has received.

    These values are deliberately data rather than Python branches: a new
    source row can move through the review lifecycle without changing matcher
    logic. Only ``human_verified`` rows are production-ready.
    """

    ILLUSTRATIVE = "illustrative"
    MACHINE_STRUCTURED = "machine_structured"
    NEEDS_REVIEW = "needs_review"
    HUMAN_VERIFIED = "human_verified"
    STALE = "stale"


class Intent(str, Enum):
    """What the caller wants on this turn.

    Separate from `Domain` because several intents are conversational rather
    than a request for benefits.
    """

    FIND_SCHEME = "find_scheme"
    FIND_SCHOLARSHIP = "find_scholarship"
    FIND_JOB = "find_job"
    ASK_ABOUT_BENEFIT = "ask_about_benefit"
    ASK_HOW_TO_APPLY = "ask_how_to_apply"
    PROVIDE_INFO = "provide_info"
    REQUEST_HUMAN = "request_human"
    GREETING = "greeting"
    UNKNOWN = "unknown"

    @property
    def domain(self) -> Domain | None:
        """The benefit domain this intent searches, if it searches at all."""
        return _INTENT_TO_DOMAIN.get(self)


_INTENT_TO_DOMAIN: dict[Intent, Domain] = {
    Intent.FIND_SCHEME: Domain.SCHEME,
    Intent.FIND_SCHOLARSHIP: Domain.SCHOLARSHIP,
    Intent.FIND_JOB: Domain.JOB,
}


class SocialCategory(str, Enum):
    SC = "SC"
    ST = "ST"
    OBC = "OBC"
    EWS = "EWS"
    GENERAL = "General"


class Gender(str, Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class EducationLevel(str, Enum):
    NONE = "none"
    PRIMARY = "primary"
    CLASS_8 = "class_8"
    CLASS_10 = "class_10"
    CLASS_12 = "class_12"
    ITI_DIPLOMA = "iti_diploma"
    UG = "UG"
    PG = "PG"
    PHD = "PhD"


# Ordered weakest to strongest so "requires at least Class 10" can be checked
# as a comparison rather than a set membership test.
EDUCATION_RANK: dict[EducationLevel, int] = {
    level: rank for rank, level in enumerate(EducationLevel)
}
