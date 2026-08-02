"""Deterministic eligibility matching.

Nothing here calls a model. Eligibility is arithmetic and set membership over
values a language model already extracted at ingestion time, so the answer a
caller receives is reproducible and explainable rather than resampled on every
call. The only judgement left to a model is understanding what the caller said.

The three-way verdict matters more than it looks. Treating "the caller never
told us their income" the same as "the caller's income is too high" would
produce confident rejections built on missing data, which for someone who
actually qualifies for a scholarship is the worst failure this system can have.
"""

from __future__ import annotations

from sahaayak_contracts import (
    EDUCATION_RANK,
    SLOT_REGISTRY,
    CriterionOutcome,
    CriterionStatus,
    Domain,
    EducationLevel,
    EligibilityCriteria,
    EligibilityMatchResult,
    Gender,
    MatchVerdict,
    SlotName,
    SlotValue,
    SocialCategory,
)

Slots = dict[SlotName, SlotValue]

# A benefit whose source document yielded no checkable criteria is reported at
# this confidence. Formally everyone qualifies, but in practice it usually means
# the extraction pass failed, and quietly telling every caller they qualify is
# worse than routing the question to a human.
UNCONSTRAINED_CONFIDENCE = 0.4

# Conditions like "must not already receive another scholarship" cannot be
# verified from the collected slots, so an otherwise-clean match is held below
# certainty and the condition is read back to the caller as a caveat.
CAVEATED_CONFIDENCE = 0.85


def format_inr(amount: float | int) -> str:
    """Format in the Indian grouping convention, e.g. 450000 -> ₹4,50,000."""
    whole = int(round(amount))
    sign = "-" if whole < 0 else ""
    digits = str(abs(whole))
    if len(digits) <= 3:
        return f"{sign}₹{digits}"
    head, tail = digits[:-3], digits[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return f"{sign}₹{','.join(groups)},{tail}"


def _as_int(value: SlotValue | None) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_bool(value: SlotValue | None) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"yes", "true", "1"}:
            return True
        if lowered in {"no", "false", "0"}:
            return False
    return None


def _as_text(value: SlotValue | None) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip()
    return text or None


def _unknown(slot: SlotName, requirement: str) -> CriterionOutcome:
    return CriterionOutcome(slot=slot, status=CriterionStatus.UNKNOWN, requirement=requirement)


def _decide(
    slot: SlotName, requirement: str, passed: bool, caller_value: str
) -> CriterionOutcome:
    return CriterionOutcome(
        slot=slot,
        status=CriterionStatus.PASS if passed else CriterionStatus.FAIL,
        requirement=requirement,
        caller_value=caller_value,
    )


def _check_age(criteria: EligibilityCriteria, slots: Slots) -> CriterionOutcome | None:
    if criteria.age_min is None and criteria.age_max is None:
        return None

    if criteria.age_min is not None and criteria.age_max is not None:
        requirement = f"age between {criteria.age_min} and {criteria.age_max}"
    elif criteria.age_min is not None:
        requirement = f"age {criteria.age_min} or above"
    else:
        requirement = f"age {criteria.age_max} or below"

    age = _as_int(slots.get(SlotName.AGE))
    if age is None:
        return _unknown(SlotName.AGE, requirement)

    ok = (criteria.age_min is None or age >= criteria.age_min) and (
        criteria.age_max is None or age <= criteria.age_max
    )
    return _decide(SlotName.AGE, requirement, ok, f"{age}")


def _check_income(criteria: EligibilityCriteria, slots: Slots) -> CriterionOutcome | None:
    cap = criteria.max_annual_family_income_inr
    if cap is None:
        return None

    requirement = f"annual family income at most {format_inr(cap)}"
    income = _as_int(slots.get(SlotName.ANNUAL_FAMILY_INCOME))
    if income is None:
        return _unknown(SlotName.ANNUAL_FAMILY_INCOME, requirement)
    return _decide(SlotName.ANNUAL_FAMILY_INCOME, requirement, income <= cap, format_inr(income))


def _check_category(criteria: EligibilityCriteria, slots: Slots) -> CriterionOutcome | None:
    allowed = criteria.category
    if not allowed:
        return None

    requirement = f"category one of {', '.join(c.value for c in allowed)}"
    raw = _as_text(slots.get(SlotName.SOCIAL_CATEGORY))
    if raw is None:
        return _unknown(SlotName.SOCIAL_CATEGORY, requirement)

    try:
        category = SocialCategory(raw)
    except ValueError:
        return _unknown(SlotName.SOCIAL_CATEGORY, requirement)
    return _decide(SlotName.SOCIAL_CATEGORY, requirement, category in allowed, category.value)


def _check_gender(criteria: EligibilityCriteria, slots: Slots) -> CriterionOutcome | None:
    if criteria.gender is None:
        return None

    requirement = f"applicant must be {criteria.gender.value}"
    raw = _as_text(slots.get(SlotName.GENDER))
    if raw is None:
        return _unknown(SlotName.GENDER, requirement)

    try:
        gender = Gender(raw)
    except ValueError:
        return _unknown(SlotName.GENDER, requirement)
    return _decide(SlotName.GENDER, requirement, gender == criteria.gender, gender.value)


def _check_education(criteria: EligibilityCriteria, slots: Slots) -> CriterionOutcome | None:
    allowed = criteria.education_level
    floor = criteria.min_education_level
    if not allowed and floor is None:
        return None

    if allowed:
        requirement = f"studying at one of {', '.join(e.value for e in allowed)}"
    else:
        requirement = f"educated to {floor.value} or above"  # type: ignore[union-attr]

    raw = _as_text(slots.get(SlotName.EDUCATION_LEVEL))
    if raw is None:
        return _unknown(SlotName.EDUCATION_LEVEL, requirement)

    try:
        level = EducationLevel(raw)
    except ValueError:
        return _unknown(SlotName.EDUCATION_LEVEL, requirement)

    ok = level in allowed if allowed else EDUCATION_RANK[level] >= EDUCATION_RANK[floor]  # type: ignore[index]
    return _decide(SlotName.EDUCATION_LEVEL, requirement, ok, level.value)


def _check_occupation(criteria: EligibilityCriteria, slots: Slots) -> CriterionOutcome | None:
    allowed = criteria.occupation
    if not allowed:
        return None

    requirement = f"occupation one of {', '.join(allowed)}"
    raw = _as_text(slots.get(SlotName.OCCUPATION))
    if raw is None:
        return _unknown(SlotName.OCCUPATION, requirement)

    # Substring matching in both directions: source documents say "farmer"
    # while callers say "I do farming", and neither phrasing is canonical.
    lowered = raw.lower()
    ok = any(option.lower() in lowered or lowered in option.lower() for option in allowed)
    return _decide(SlotName.OCCUPATION, requirement, ok, raw)


def _check_enrollment(criteria: EligibilityCriteria, slots: Slots) -> CriterionOutcome | None:
    allowed = criteria.enrollment_mode
    if not allowed:
        return None

    requirement = f"enrolment mode one of {', '.join(allowed)}"
    raw = _as_text(slots.get(SlotName.ENROLLMENT_MODE))
    if raw is None:
        return _unknown(SlotName.ENROLLMENT_MODE, requirement)
    ok = raw.lower() in {option.lower() for option in allowed}
    return _decide(SlotName.ENROLLMENT_MODE, requirement, ok, raw)


def _check_residency(
    criteria: EligibilityCriteria, slots: Slots, benefit_state: str | None
) -> CriterionOutcome | None:
    if not criteria.state_residency_required:
        return None

    where = benefit_state or "the issuing state"
    requirement = f"must be a resident of {where}"
    resident = _as_bool(slots.get(SlotName.STATE_RESIDENCY))
    if resident is None:
        return _unknown(SlotName.STATE_RESIDENCY, requirement)
    return _decide(
        SlotName.STATE_RESIDENCY, requirement, resident, "resident" if resident else "not resident"
    )


def _check_disability(criteria: EligibilityCriteria, slots: Slots) -> CriterionOutcome | None:
    if not criteria.disability_required:
        return None

    requirement = "must have a certified disability"
    has = _as_bool(slots.get(SlotName.DISABILITY))
    if has is None:
        return _unknown(SlotName.DISABILITY, requirement)
    return _decide(SlotName.DISABILITY, requirement, has, "yes" if has else "no")


def _check_experience(criteria: EligibilityCriteria, slots: Slots) -> CriterionOutcome | None:
    required = criteria.min_experience_years
    if required is None:
        return None

    requirement = f"at least {required} years of experience"
    years = _as_int(slots.get(SlotName.EXPERIENCE_YEARS))
    if years is None:
        return _unknown(SlotName.EXPERIENCE_YEARS, requirement)
    return _decide(SlotName.EXPERIENCE_YEARS, requirement, years >= required, f"{years}")


def _check_location(criteria: EligibilityCriteria, slots: Slots) -> CriterionOutcome | None:
    allowed = criteria.locations
    if not allowed:
        return None

    requirement = f"located in one of {', '.join(allowed)}"
    raw = _as_text(slots.get(SlotName.LOCATION))
    if raw is None:
        return _unknown(SlotName.LOCATION, requirement)
    lowered = raw.lower()
    ok = any(option.lower() in lowered or lowered in option.lower() for option in allowed)
    return _decide(SlotName.LOCATION, requirement, ok, raw)


def evaluate(
    criteria: EligibilityCriteria,
    slots: Slots,
    *,
    benefit_id: str,
    benefit_name: str,
    domain: Domain,
    benefit_state: str | None = None,
) -> EligibilityMatchResult:
    """Check one benefit's criteria against one caller's collected slots."""
    checks = [
        _check_age(criteria, slots),
        _check_income(criteria, slots),
        _check_category(criteria, slots),
        _check_gender(criteria, slots),
        _check_education(criteria, slots),
        _check_occupation(criteria, slots),
        _check_enrollment(criteria, slots),
        _check_residency(criteria, slots, benefit_state),
        _check_disability(criteria, slots),
        _check_experience(criteria, slots),
        _check_location(criteria, slots),
    ]
    outcomes = [outcome for outcome in checks if outcome is not None]

    failed = [o for o in outcomes if o.status is CriterionStatus.FAIL]
    unknown = [o for o in outcomes if o.status is CriterionStatus.UNKNOWN]

    if failed:
        # One definite disqualification settles the question; the unresolved
        # criteria cannot rescue it, so this is a full-confidence "no".
        verdict = MatchVerdict.NOT_ELIGIBLE
        confidence = 1.0
    elif unknown:
        verdict = MatchVerdict.INSUFFICIENT_INFO
        confidence = round((len(outcomes) - len(unknown)) / len(outcomes), 2)
    elif not outcomes:
        verdict = MatchVerdict.ELIGIBLE
        confidence = UNCONSTRAINED_CONFIDENCE
    else:
        verdict = MatchVerdict.ELIGIBLE
        confidence = CAVEATED_CONFIDENCE if criteria.exclusions else 1.0

    return EligibilityMatchResult(
        benefit_id=benefit_id,
        benefit_name=benefit_name,
        domain=domain,
        verdict=verdict,
        outcomes=outcomes,
        confidence=confidence,
        caveats=list(criteria.exclusions),
    )


_VERDICT_ORDER = {
    MatchVerdict.ELIGIBLE: 0,
    MatchVerdict.INSUFFICIENT_INFO: 1,
    MatchVerdict.NOT_ELIGIBLE: 2,
}


def rank(results: list[EligibilityMatchResult]) -> list[EligibilityMatchResult]:
    """Order for reading aloud: confirmed matches first, rejections last."""
    return sorted(
        results,
        key=lambda r: (_VERDICT_ORDER[r.verdict], -r.confidence, r.benefit_name),
    )


def most_informative_slot(
    results: list[EligibilityMatchResult],
) -> tuple[SlotName, int] | None:
    """The unfilled slot that would resolve the most undecided candidates.

    Asking in this order means a caller who answers three questions has ruled
    the maximum number of options in or out, rather than working through a
    fixed questionnaire that may not apply to them.
    """
    tally: dict[SlotName, int] = {}
    for result in results:
        if result.verdict is not MatchVerdict.INSUFFICIENT_INFO:
            continue
        for slot in result.blocking_slots:
            tally[slot] = tally.get(slot, 0) + 1

    if not tally:
        return None
    # Ties break toward the registry's own asking order, so equally useful
    # questions are still posed in the sequence the slot registry considers
    # most natural.
    slot = min(tally, key=lambda s: (-tally[s], SLOT_REGISTRY[s].priority))
    return slot, tally[slot]
