"""Model-backed understanding, used only where the rule extractor falls short.

The model's job is narrow on purpose: read one utterance and report the intent
and any slot values stated in it. It never decides eligibility and never
invents a value, because every downstream decision is arithmetic over what it
returns, and a hallucinated income becomes a confident wrong answer told to
someone who needed the money.
"""

from __future__ import annotations

import json

from sahaayak_agent.languages import ALL_PROFILES
from sahaayak_agent.tracing import start_span
from sahaayak_common import (
    BudgetReservation,
    OpenAIBudgetLedger,
    get_logger,
    settings,
)
from sahaayak_contracts import (
    EducationLevel,
    Gender,
    Intent,
    SlotName,
    SlotValue,
    SocialCategory,
)

log = get_logger(__name__)

_ALLOWED_SLOT_VALUES = {
    SlotName.SOCIAL_CATEGORY: [c.value for c in SocialCategory],
    SlotName.EDUCATION_LEVEL: [e.value for e in EducationLevel],
    SlotName.GENDER: [g.value for g in Gender],
    SlotName.ENROLLMENT_MODE: ["regular", "distance", "correspondence", "not_studying"],
}

_SUPPORTED_LANGUAGE_NAMES = ", ".join(
    f"{profile.name} ({profile.code})" for profile in ALL_PROFILES
)

SYSTEM_PROMPT = f"""You extract structured information from a single utterance \
spoken by a caller to an Indian government-benefits helpline.

The caller may speak any of these supported languages, and may mix them in one \
sentence: {_SUPPORTED_LANGUAGE_NAMES}. Understand the selected language and \
common English or Hindi code-switching without changing the caller's meaning.

Return strictly valid JSON:
{{
  "intent": one of {[i.value for i in Intent]},
  "slots": {{ ... }},
  "confidence": a number from 0 to 1
}}

Slot keys and their value types:
- "age": integer years
- "annual_family_income": integer rupees per year. Expand spoken magnitudes, so \
"do lakh" and "two lakh" both become 200000.
- "social_category": one of {_ALLOWED_SLOT_VALUES[SlotName.SOCIAL_CATEGORY]}
- "education_level": one of {_ALLOWED_SLOT_VALUES[SlotName.EDUCATION_LEVEL]}
- "gender": one of {_ALLOWED_SLOT_VALUES[SlotName.GENDER]}
- "occupation": short English noun, e.g. "farmer", "student"
- "enrollment_mode": one of {_ALLOWED_SLOT_VALUES[SlotName.ENROLLMENT_MODE]}
- "disability": boolean
- "state_residency": boolean
- "experience_years": integer years
- "location": city or district name

Rules that matter more than completeness:
- Include a slot ONLY if the caller stated it in this utterance. Omit everything else.
- Never guess a number. If the caller was vague, omit the slot.
- If the caller is answering a question you were told is pending, prefer \
interpreting the utterance as an answer to that question.
- Set a low confidence when the audio transcript looks garbled rather than \
guessing at what they meant."""


class LLMUnderstanding:
    def __init__(self, model: str | None = None) -> None:
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        self._model = model or settings.openai_reasoning_model
        self._budget = OpenAIBudgetLedger(
            settings.openai_budget_usd,
            settings.resolved_openai_budget_ledger_path,
        )

    async def extract(
        self,
        transcript: str,
        *,
        language_code: str,
        pending_slot: SlotName | None = None,
        known_slots: dict[SlotName, SlotValue] | None = None,
    ) -> tuple[Intent, dict[SlotName, SlotValue], float]:
        context = [f"Caller's language: {language_code}."]
        if pending_slot:
            context.append(f"You just asked the caller for: {pending_slot.value}.")
        if known_slots:
            already = ", ".join(f"{k.value}={v}" for k, v in known_slots.items())
            context.append(f"Already known (do not repeat unless restated): {already}.")

        user_content = f"{' '.join(context)}\n\nUtterance: {transcript}"
        reservation: BudgetReservation = self._budget.reserve_chat(
            model=self._model,
            input_characters=len(SYSTEM_PROMPT) + len(user_content),
            max_output_tokens=settings.openai_agent_max_output_tokens,
            operation="agent:understanding",
        )
        with start_span(
            "provider.openai.understanding",
            {
                "provider": "openai",
                "provider.model": self._model,
                "provider.language": language_code,
                "provider.pending_slot": pending_slot.value if pending_slot else "none",
            },
        ) as span:
            try:
                response = await self._client.chat.completions.create(
                    model=self._model,
                    response_format={"type": "json_object"},
                    temperature=0,
                    max_completion_tokens=settings.openai_agent_max_output_tokens,
                    n=1,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_content},
                    ],
                )
            except Exception as exc:
                self._budget.record_failure(reservation, exc)
                if span is not None:
                    span.record_exception(exc)
                    span.set_attribute("error.type", exc.__class__.__name__)
                raise
        self._budget.record_chat_response(reservation, response)

        content = response.choices[0].message.content or "{}"
        payload = json.loads(content)
        return (
            _coerce_intent(payload.get("intent")),
            _coerce_slots(payload.get("slots") or {}),
            float(payload.get("confidence", 0.5)),
        )


def _coerce_intent(value: object) -> Intent:
    try:
        return Intent(value)
    except ValueError:
        log.warning("llm_returned_unknown_intent", value=value)
        return Intent.UNKNOWN


def _coerce_slots(raw: dict) -> dict[SlotName, SlotValue]:
    """Keep only well-formed, in-vocabulary values.

    A model that returns "SC/ST" for a category or a string for an age is more
    useful discarded than coerced: the agent can ask again, but it cannot undo
    a wrongly recorded value.
    """
    slots: dict[SlotName, SlotValue] = {}
    for key, value in raw.items():
        if value is None:
            continue
        try:
            slot = SlotName(key)
        except ValueError:
            log.debug("llm_returned_unknown_slot", slot=key)
            continue

        allowed = _ALLOWED_SLOT_VALUES.get(slot)
        if allowed is not None:
            if value not in allowed:
                log.warning("llm_slot_value_out_of_vocabulary", slot=key, value=value)
                continue
            slots[slot] = value
        elif slot in {SlotName.AGE, SlotName.ANNUAL_FAMILY_INCOME, SlotName.EXPERIENCE_YEARS}:
            if isinstance(value, bool) or not isinstance(value, int | float):
                log.warning("llm_slot_value_not_numeric", slot=key, value=value)
                continue
            slots[slot] = int(value)
        elif slot in {SlotName.DISABILITY, SlotName.STATE_RESIDENCY}:
            if not isinstance(value, bool):
                continue
            slots[slot] = value
        else:
            slots[slot] = str(value)
    return slots
