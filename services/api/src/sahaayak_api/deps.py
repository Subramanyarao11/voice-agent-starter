"""Shared FastAPI dependencies.

The runtime is built once and reused. Constructing it per request would rebuild
the LangGraph and re-open provider clients on every turn, which on a phone call
is latency the caller hears.
"""

from __future__ import annotations

from functools import lru_cache

from sahaayak_agent import AgentRuntime
from sahaayak_agent.voice import VoiceService, get_voice_service


@lru_cache
def get_runtime() -> AgentRuntime:
    return AgentRuntime()


def get_voice() -> VoiceService:
    return get_voice_service()
