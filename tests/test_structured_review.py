"""Tests for the machine-review safety boundary."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "structured_review",
    Path(__file__).parents[1] / "scripts" / "09_review_structured_benefits.py",
)
assert _SPEC and _SPEC.loader
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MODULE
_SPEC.loader.exec_module(_MODULE)
AutomatedReview = _MODULE.AutomatedReview
effective_decision = _MODULE.effective_decision


def review(*, audience: str = "individual", source_quality: str = "usable"):
    return AutomatedReview(
        decision="pass",
        audience=audience,
        source_quality=source_quality,
        rationale="The source supports the structured claims.",
    )


def test_institutional_rows_are_not_machine_approved():
    assert effective_decision(review(audience="institution")) == (
        "reject",
        "institutional_audience",
    )


def test_mixed_audience_rows_require_human_review():
    assert effective_decision(review(audience="mixed")) == (
        "needs_review",
        "ambiguous_audience",
    )


def test_noisy_source_rows_require_human_review():
    assert effective_decision(review(source_quality="noisy")) == (
        "needs_review",
        "source_quality_noisy",
    )
