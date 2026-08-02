"""Tests for the eligibility matcher.

The distinction these mostly defend is between "fails a criterion" and "we
never asked". Collapsing the two would let the agent tell someone they do not
qualify on the basis of a question it never put to them.
"""

from __future__ import annotations

import pytest

from sahaayak_agent.matcher import (
    evaluate,
    format_inr,
    most_informative_slot,
    rank,
)
from sahaayak_contracts import (
    CriterionStatus,
    Domain,
    EligibilityCriteria,
    MatchVerdict,
    SlotName,
)


def check(criteria: EligibilityCriteria, slots: dict, **kwargs):
    return evaluate(
        criteria,
        slots,
        benefit_id=kwargs.get("benefit_id", "b1"),
        benefit_name=kwargs.get("benefit_name", "Test Benefit"),
        domain=kwargs.get("domain", Domain.SCHEME),
        benefit_state=kwargs.get("benefit_state"),
    )


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        (450000, "₹4,50,000"),
        (120, "₹120"),
        (12345678, "₹1,23,45,678"),
        (1000, "₹1,000"),
        (0, "₹0"),
    ],
)
def test_amounts_use_indian_grouping(amount, expected):
    assert format_inr(amount) == expected


def test_unstated_criteria_are_not_checked():
    """A field the source document never mentioned imposes no condition."""
    result = check(EligibilityCriteria(age_min=18), {SlotName.AGE: 20})
    assert result.verdict is MatchVerdict.ELIGIBLE
    assert len(result.outcomes) == 1


def test_missing_slot_is_undecided_not_a_rejection():
    result = check(
        EligibilityCriteria(max_annual_family_income_inr=450000), {}
    )
    assert result.verdict is MatchVerdict.INSUFFICIENT_INFO
    assert result.blocking_slots == [SlotName.ANNUAL_FAMILY_INCOME]


def test_definite_failure_is_full_confidence_despite_unknowns():
    """One disqualification settles it; the open questions cannot rescue it."""
    result = check(
        EligibilityCriteria(age_max=25, max_annual_family_income_inr=450000),
        {SlotName.AGE: 40},
    )
    assert result.verdict is MatchVerdict.NOT_ELIGIBLE
    assert result.confidence == 1.0


def test_income_cap_is_inclusive_at_the_boundary():
    criteria = EligibilityCriteria(max_annual_family_income_inr=450000)
    assert check(criteria, {SlotName.ANNUAL_FAMILY_INCOME: 450000}).verdict is (
        MatchVerdict.ELIGIBLE
    )
    assert check(criteria, {SlotName.ANNUAL_FAMILY_INCOME: 450001}).verdict is (
        MatchVerdict.NOT_ELIGIBLE
    )


def test_age_range_boundaries_are_inclusive():
    criteria = EligibilityCriteria(age_min=18, age_max=25)
    for age, verdict in [
        (17, MatchVerdict.NOT_ELIGIBLE),
        (18, MatchVerdict.ELIGIBLE),
        (25, MatchVerdict.ELIGIBLE),
        (26, MatchVerdict.NOT_ELIGIBLE),
    ]:
        assert check(criteria, {SlotName.AGE: age}).verdict is verdict, age


def test_education_floor_uses_rank_not_membership():
    criteria = EligibilityCriteria(min_education_level="class_10")
    assert check(criteria, {SlotName.EDUCATION_LEVEL: "UG"}).verdict is MatchVerdict.ELIGIBLE
    assert check(criteria, {SlotName.EDUCATION_LEVEL: "class_8"}).verdict is (
        MatchVerdict.NOT_ELIGIBLE
    )


def test_education_list_is_exact_membership():
    """A list means only those levels, so a PhD does not satisfy "UG or PG"."""
    criteria = EligibilityCriteria(education_level=["UG", "PG"])
    assert check(criteria, {SlotName.EDUCATION_LEVEL: "PG"}).verdict is MatchVerdict.ELIGIBLE
    assert check(criteria, {SlotName.EDUCATION_LEVEL: "PhD"}).verdict is (
        MatchVerdict.NOT_ELIGIBLE
    )


def test_out_of_vocabulary_slot_value_is_undecided():
    """A value the enum does not recognise must not be scored as a failure."""
    result = check(
        EligibilityCriteria(category=["SC"]), {SlotName.SOCIAL_CATEGORY: "not-a-category"}
    )
    assert result.verdict is MatchVerdict.INSUFFICIENT_INFO


def test_occupation_matches_across_phrasings():
    criteria = EligibilityCriteria(occupation=["farmer"])
    assert check(criteria, {SlotName.OCCUPATION: "I am a farmer"}).verdict is (
        MatchVerdict.ELIGIBLE
    )
    assert check(criteria, {SlotName.OCCUPATION: "software engineer"}).verdict is (
        MatchVerdict.NOT_ELIGIBLE
    )


def test_benefit_with_no_criteria_is_low_confidence():
    """Zero extracted conditions is far more likely a parse failure than a
    scheme that genuinely qualifies the entire population."""
    result = check(EligibilityCriteria(), {})
    assert result.verdict is MatchVerdict.ELIGIBLE
    assert result.confidence < 0.7


def test_unverifiable_exclusions_hold_confidence_below_certainty():
    result = check(
        EligibilityCriteria(age_min=18, exclusions=["already receiving another scholarship"]),
        {SlotName.AGE: 20},
    )
    assert result.verdict is MatchVerdict.ELIGIBLE
    assert result.confidence < 1.0
    assert result.caveats == ["already receiving another scholarship"]


def test_partial_information_lowers_confidence_proportionally():
    result = check(
        EligibilityCriteria(
            age_min=18, max_annual_family_income_inr=450000, category=["SC"]
        ),
        {SlotName.AGE: 20},
    )
    assert result.verdict is MatchVerdict.INSUFFICIENT_INFO
    assert result.confidence == pytest.approx(1 / 3, abs=0.01)


def test_outcomes_explain_both_sides_of_a_verdict():
    result = check(
        EligibilityCriteria(age_min=18, age_max=25, max_annual_family_income_inr=100000),
        {SlotName.AGE: 22, SlotName.ANNUAL_FAMILY_INCOME: 500000},
    )
    assert [o.status for o in result.outcomes] == [
        CriterionStatus.PASS,
        CriterionStatus.FAIL,
    ]
    assert "₹1,00,000" in result.failed[0].requirement
    assert result.failed[0].caller_value == "₹5,00,000"


def test_ranking_puts_confirmed_matches_first():
    eligible = check(EligibilityCriteria(age_min=18), {SlotName.AGE: 20}, benefit_name="Yes")
    rejected = check(EligibilityCriteria(age_min=30), {SlotName.AGE: 20}, benefit_name="No")
    undecided = check(EligibilityCriteria(age_min=18), {}, benefit_name="Maybe")

    assert [r.benefit_name for r in rank([rejected, undecided, eligible])] == [
        "Yes",
        "Maybe",
        "No",
    ]


def test_next_question_is_the_one_resolving_most_candidates():
    """Question choice is driven by how much it narrows the field, so a caller's
    effort goes where it changes the answer."""
    income_blocked = [
        check(
            EligibilityCriteria(max_annual_family_income_inr=cap),
            {},
            benefit_id=f"b{cap}",
        )
        for cap in (100000, 200000, 300000)
    ]
    age_blocked = [check(EligibilityCriteria(age_min=18), {}, benefit_id="age")]

    slot, resolves = most_informative_slot(income_blocked + age_blocked)
    assert slot is SlotName.ANNUAL_FAMILY_INCOME
    assert resolves == 3


def test_no_question_is_suggested_when_nothing_is_undecided():
    decided = check(EligibilityCriteria(age_min=18), {SlotName.AGE: 20})
    assert most_informative_slot([decided]) is None
