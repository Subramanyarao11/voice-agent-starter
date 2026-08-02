"""Turning an utterance into an intent and typed slot values.

Rules run first and the model runs only when they come up short. That ordering
is a latency and cost decision as much as a correctness one: on a phone call,
most answers are a number or a yes, and those should not cost a round-trip to
a model.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from sahaayak_agent.understanding import rules
from sahaayak_common import get_logger, settings
from sahaayak_contracts import Intent, SlotName, SlotValue

log = get_logger(__name__)


class UnderstandingResult(BaseModel):
    intent: Intent = Intent.UNKNOWN
    slots: dict[SlotName, SlotValue] = Field(default_factory=dict)
    confidence: float = 1.0
    source: str = "rules"  # rules | llm | hybrid


class Understanding:
    """Rule-first understanding with an optional model fallback."""

    def __init__(self, llm=None) -> None:
        self._llm = llm

    @classmethod
    def build(cls) -> Understanding:
        if not settings.llm_enabled:
            log.info(
                "understanding_rules_only",
                reason="no OPENAI_API_KEY configured",
            )
            return cls(llm=None)
        from sahaayak_agent.understanding.llm import LLMUnderstanding

        return cls(llm=LLMUnderstanding())

    async def understand(
        self,
        transcript: str,
        *,
        language_code: str,
        pending_slot: SlotName | None = None,
        known_slots: dict[SlotName, SlotValue] | None = None,
    ) -> UnderstandingResult:
        transcript = transcript.strip()
        if not transcript:
            return UnderstandingResult(intent=Intent.UNKNOWN, confidence=0.0)

        result = self._understand_with_rules(
            transcript, pending_slot=pending_slot
        )
        if not self._needs_model(result, pending_slot):
            return result

        if self._llm is None:
            return result

        try:
            intent, slots, confidence = await self._llm.extract(
                transcript,
                language_code=language_code,
                pending_slot=pending_slot,
                known_slots=known_slots,
            )
        except Exception as exc:
            # A model outage must not end the call. The rule result is weaker
            # but still usable, and the caller simply gets asked again.
            log.warning("llm_understanding_failed", error=str(exc), exc_info=True)
            return result

        # Rules are trusted over the model where both spoke, since a regex that
        # matched "SC" is not going to have imagined it.
        merged = {**slots, **result.slots}
        return UnderstandingResult(
            intent=result.intent if result.intent is not Intent.UNKNOWN else intent,
            slots=merged,
            confidence=max(result.confidence, confidence) if merged else confidence,
            source="hybrid" if result.slots else "llm",
        )

    def _understand_with_rules(
        self, transcript: str, *, pending_slot: SlotName | None
    ) -> UnderstandingResult:
        slots: dict[SlotName, SlotValue] = dict(rules.extract_volunteered_slots(transcript))

        if pending_slot is not None and pending_slot not in slots:
            answer = rules.parse_slot(pending_slot, transcript)
            if answer is not None:
                slots[pending_slot] = answer

        intent = rules.detect_intent(transcript)
        confidence = 1.0 if (slots or intent is not Intent.UNKNOWN) else 0.0
        return UnderstandingResult(
            intent=intent, slots=slots, confidence=confidence, source="rules"
        )

    def _needs_model(
        self, result: UnderstandingResult, pending_slot: SlotName | None
    ) -> bool:
        """Escalate to the model when the rules left the turn unresolved.

        Free-text slots are always escalated when a model is available: a
        regex can confirm that a caller said "farmer", but only a model can
        turn "I look after my father's fields" into one.
        """
        if pending_slot is not None:
            if pending_slot not in result.slots:
                return True
            if pending_slot in {SlotName.OCCUPATION, SlotName.LOCATION}:
                return True
            return False
        return result.intent is Intent.UNKNOWN and not result.slots


__all__ = ["Understanding", "UnderstandingResult", "rules"]
