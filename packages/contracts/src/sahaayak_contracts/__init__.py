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
from sahaayak_contracts.notifications import (
    EXTERNAL_CHANNELS,
    RETRYABLE_ERROR_CLASSES,
    TERMINAL_STATUSES,
    ConsentPurpose,
    ConsentStatus,
    DeliveryStatus,
    DeliveryStatusUpdate,
    InboundMessage,
    NotificationChannel,
    ProviderErrorClass,
    ProviderSendResult,
    VerificationStatusValue,
    status_rank,
    supersedes,
)
from sahaayak_contracts.retrieval import (
    RagAnswerResponse,
    RagSearchRequest,
    RagSearchResponse,
    RetrievedSource,
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
    "EXTERNAL_CHANNELS",
    "MINIMUM_SLOTS",
    "RETRYABLE_ERROR_CLASSES",
    "SLOT_REGISTRY",
    "TERMINAL_STATUSES",
    "AgentState",
    "ConsentPurpose",
    "ConsentStatus",
    "ConversationTurn",
    "CriterionOutcome",
    "CriterionStatus",
    "DeliveryStatus",
    "DeliveryStatusUpdate",
    "Domain",
    "EducationLevel",
    "EligibilityCriteria",
    "EligibilityMatchResult",
    "EscalationReason",
    "Gender",
    "InboundMessage",
    "Intent",
    "LanguageCatalog",
    "NotificationChannel",
    "ProviderErrorClass",
    "ProviderSendResult",
    "VerificationStatusValue",
    "status_rank",
    "supersedes",
    "LanguageProfile",
    "MatchSummary",
    "MatchVerdict",
    "RagAnswerResponse",
    "RagSearchRequest",
    "RagSearchResponse",
    "RetrievedSource",
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
