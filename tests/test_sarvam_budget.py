"""Sarvam adapters must stop before a provider request can exceed the cap."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_sarvam_stt_budget_blocks_before_network(monkeypatch, tmp_path):
    from sahaayak_agent.languages import get_profile
    from sahaayak_agent.voice.base import VoiceUnavailable
    from sahaayak_agent.voice.sarvam_stt import SarvamSaarasSTT
    from sahaayak_common import settings

    monkeypatch.setattr(settings, "sarvam_api_key", "configured-for-test")
    monkeypatch.setattr(settings, "sarvam_budget_usd", 0.01)
    monkeypatch.setattr(settings, "sarvam_stt_request_reservation_usd", 0.10)
    monkeypatch.setattr(settings, "sarvam_budget_ledger_path", str(tmp_path / "sarvam.json"))

    provider = SarvamSaarasSTT()
    with pytest.raises(VoiceUnavailable, match="budget cap"):
        await provider.transcribe(b"fake-audio", profile=get_profile("kn"))


@pytest.mark.asyncio
async def test_sarvam_tts_budget_blocks_before_network(monkeypatch, tmp_path):
    from sahaayak_agent.languages import get_profile
    from sahaayak_agent.voice.base import VoiceUnavailable
    from sahaayak_agent.voice.sarvam_tts import SarvamBulbulTTS
    from sahaayak_common import settings

    monkeypatch.setattr(settings, "sarvam_api_key", "configured-for-test")
    monkeypatch.setattr(settings, "sarvam_budget_usd", 0.01)
    monkeypatch.setattr(settings, "sarvam_tts_reservation_usd_per_1000_characters", 3.0)
    monkeypatch.setattr(settings, "sarvam_budget_ledger_path", str(tmp_path / "sarvam.json"))

    provider = SarvamBulbulTTS()
    with pytest.raises(VoiceUnavailable, match="budget cap"):
        await provider.synthesize("hello", profile=get_profile("en"))
