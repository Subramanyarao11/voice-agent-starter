"""Shared, infrastructure-free contracts.

Nothing here may import a database driver, an HTTP client, or a model SDK.
That constraint is what lets the ingestion pipeline, the agent, the API, and
the tests all agree on the same shapes without dragging in each other's
dependencies.
"""

from sahaayak_contracts.agent import (
    AgentState,
    ConversationTurn,
    EscalationReason,
    MatchSummary,
    SlotValue,
    TurnRequest,
    TurnResponse,
)
from sahaayak_contracts.domain import (
    EDUCATION_RANK,
    Domain,
    EducationLevel,
    Gender,
    Intent,
    SocialCategory,
    VerificationStatus,
)
from sahaayak_contracts.eligibility import (
    CriterionOutcome,
    CriterionStatus,
    EligibilityCriteria,
    EligibilityMatchResult,
    MatchVerdict,
)
from sahaayak_contracts.slots import (
    MINIMUM_SLOTS,
    SLOT_REGISTRY,
    SlotKind,
    SlotName,
    SlotSpec,
    slots_for_domain,
)
from sahaayak_contracts.voice import (
    LanguageCatalog,
    LanguageProfile,
    SynthesisResult,
    TranscriptionResult,
)

__all__ = [
    "EDUCATION_RANK",
    "MINIMUM_SLOTS",
    "SLOT_REGISTRY",
    "AgentState",
    "ConversationTurn",
    "CriterionOutcome",
    "CriterionStatus",
    "Domain",
    "EducationLevel",
    "EligibilityCriteria",
    "EligibilityMatchResult",
    "EscalationReason",
    "Gender",
    "Intent",
    "LanguageCatalog",
    "LanguageProfile",
    "MatchSummary",
    "MatchVerdict",
    "SlotKind",
    "SlotName",
    "SlotSpec",
    "SlotValue",
    "SocialCategory",
    "VerificationStatus",
    "SynthesisResult",
    "TranscriptionResult",
    "TurnRequest",
    "TurnResponse",
    "slots_for_domain",
]
