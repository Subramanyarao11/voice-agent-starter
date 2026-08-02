"""Tests for the persistent, fail-closed OpenAI spending guard."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from sahaayak_common import BudgetError, BudgetExceeded, OpenAIBudgetLedger


def test_budget_rejects_a_ceiling_above_fifteen_dollars(tmp_path):
    with pytest.raises(BudgetError, match=r"cannot exceed \$15.00"):
        OpenAIBudgetLedger(15.01, tmp_path / "budget.json")


def test_reservations_persist_and_stop_before_the_cap(tmp_path):
    ledger_path = tmp_path / "budget.json"
    ledger = OpenAIBudgetLedger(10, ledger_path)

    reservation = ledger.reserve_fixed(
        model="gpt-4o-mini", cost_usd=6, operation="test:first"
    )
    ledger.record_chat_response(
        reservation,
        SimpleNamespace(
            usage=SimpleNamespace(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        ),
    )

    reloaded = OpenAIBudgetLedger(10, ledger_path)
    with pytest.raises(BudgetExceeded, match="budget cap reached"):
        reloaded.reserve_fixed(model="gpt-4o-mini", cost_usd=4.01, operation="test:second")

    summary = reloaded.summary()
    assert summary["budget_usd"] == "10.000000"
    assert summary["reserved_usd"] == "6.000000"
    assert summary["observed_usd"] == "0.000045"
    assert summary["remaining_usd"] == "4.000000"
    assert summary["completed_calls"] == 1


def test_failed_requests_keep_their_reservation(tmp_path):
    ledger = OpenAIBudgetLedger(1, tmp_path / "budget.json")
    reservation = ledger.reserve_fixed(
        model="gpt-4o-mini", cost_usd="0.75", operation="test:failed"
    )
    ledger.record_failure(reservation, TimeoutError("provider timeout"))

    summary = ledger.summary()
    assert summary["reserved_usd"] == "0.750000"
    assert summary["failed_calls"] == 1
    assert summary["remaining_usd"] == "0.250000"


def test_observed_usage_is_also_a_hard_boundary(tmp_path):
    ledger = OpenAIBudgetLedger(1, tmp_path / "budget.json")
    reservation = ledger.reserve_fixed(
        model="gpt-4o-mini", cost_usd="0.10", operation="test:underestimated"
    )
    # Simulate a provider price/usage surprise larger than the reservation.
    ledger.record_chat_response(
        reservation,
        SimpleNamespace(
            usage=SimpleNamespace(
                prompt_tokens=7_000_000,
                completion_tokens=0,
                total_tokens=7_000_000,
            )
        ),
    )

    with pytest.raises(BudgetExceeded, match="budget cap reached"):
        ledger.reserve_fixed(model="gpt-4o-mini", cost_usd="0.01", operation="test:blocked")

    assert ledger.summary()["remaining_usd"] == "0.000000"
