"""Tests for the shared Sarvam-style provider reservation ledger."""

from __future__ import annotations

import json

import pytest

from sahaayak_common import (
    ProviderBudgetError,
    ProviderBudgetExceeded,
    ProviderBudgetLedger,
)


def test_provider_budget_rejects_more_than_ten_dollars(tmp_path):
    with pytest.raises(ProviderBudgetError, match=r"cannot exceed \$10.00"):
        ProviderBudgetLedger("sarvam", 10.01, tmp_path / "sarvam.json")


def test_provider_budget_reservations_persist_and_block(tmp_path):
    path = tmp_path / "sarvam.json"
    ledger = ProviderBudgetLedger("sarvam", 1, path)
    reservation = ledger.reserve_fixed(
        model="bulbul:v2", cost_usd="0.75", operation="voice:synthesis:kn"
    )
    ledger.record_completion(reservation, metadata={"characters": 42})

    reloaded = ProviderBudgetLedger("sarvam", 1, path)
    with pytest.raises(ProviderBudgetExceeded, match="budget cap reached"):
        reloaded.reserve_fixed(
            model="saaras:v3", cost_usd="0.26", operation="voice:transcription:kn"
        )

    summary = reloaded.summary()
    assert summary["provider"] == "sarvam"
    assert summary["reserved_usd"] == "0.750000"
    assert summary["remaining_usd"] == "0.250000"
    assert summary["completed_calls"] == 1


def test_provider_budget_fails_closed_on_corrupt_ledger(tmp_path):
    path = tmp_path / "sarvam.json"
    path.write_text(json.dumps({"version": 999}), encoding="utf-8")
    ledger = ProviderBudgetLedger("sarvam", 1, path)
    with pytest.raises(ProviderBudgetError, match="Unsupported"):
        ledger.reserve_fixed(model="bulbul:v2", cost_usd="0.01", operation="test")

