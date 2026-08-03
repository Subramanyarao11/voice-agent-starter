"""Inbound call lifecycle: answering, turn limits, and what is not stored.

The call state machine is driven directly with normalized events, so the flow
is tested without a provider. What matters here is that a call cannot run away
— on duration, on turns, or on cost — and that no audio survives it.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlmodel import Session

from sahaayak_api.integrations.infobip.calls import MAX_CALL_SECONDS, MAX_TURNS
from sahaayak_api.integrations.infobip.webhooks import parse_call_events
from sahaayak_api.workers import voice_call
from sahaayak_common import (
    CallSession,
    UserSession,
    channel_identity_hash,
    engine,
    new_id,
    settings,
)

CALLER = "+919876543210"
CALL_ID = "call-abc-123"


class FakeCalls:
    """Records the actions the state machine takes on a call."""

    name = "infobip_calls"

    def __init__(self, *, answer_ok: bool = True) -> None:
        self.answer_ok = answer_ok
        self.actions: list[tuple[str, str]] = []

    def available(self) -> bool:
        return True

    async def answer(self, call_id: str) -> bool:
        self.actions.append(("answer", call_id))
        return self.answer_ok

    async def hangup(self, call_id: str, *, reason: str = "normal") -> bool:
        self.actions.append(("hangup", reason))
        return True

    async def upload_audio(self, audio: bytes, *, mime_type: str = "audio/wav") -> str:
        self.actions.append(("upload", mime_type))
        return "file-1"

    async def play_file(self, call_id: str, file_id: str) -> bool:
        self.actions.append(("play", file_id))
        return True

    async def capture_speech(self, call_id: str, *, language: str) -> bool:
        self.actions.append(("capture", language))
        return True

    def did(self, action: str) -> bool:
        return any(name == action for name, _ in self.actions)


@pytest.fixture
def calls(monkeypatch, database, seeded):
    fake = FakeCalls()
    monkeypatch.setattr(voice_call, "build_calls_provider", lambda: fake)
    _wipe()
    yield fake
    _wipe()


def _wipe() -> None:
    with Session(engine) as db:
        for row in db.query(CallSession).all():
            db.delete(row)
        db.commit()


def read_call(call_id: str = CALL_ID) -> CallSession | None:
    with Session(engine) as db:
        return (
            db.query(CallSession)
            .filter_by(provider="infobip", provider_call_id=call_id)
            .first()
        )


def received() -> dict:
    return {"type": "CALL_RECEIVED", "call_id": CALL_ID, "from": CALLER}


def speech(text: str) -> dict:
    return {"type": "SPEECH_CAPTURED", "call_id": CALL_ID, "text": text}


# --- Event parsing --------------------------------------------------------


def test_a_call_received_event_is_normalized() -> None:
    events = parse_call_events(
        {
            "events": [
                {
                    "type": "CALL_RECEIVED",
                    "properties": {
                        "call": {
                            "id": CALL_ID,
                            "endpoint": {"phoneNumber": CALLER},
                        }
                    },
                }
            ]
        }
    )
    assert events[0]["type"] == "CALL_RECEIVED"
    assert events[0]["call_id"] == CALL_ID
    assert events[0]["from"] == CALLER


def test_a_single_event_payload_is_accepted() -> None:
    events = parse_call_events({"type": "CALL_FINISHED", "callId": CALL_ID})
    assert len(events) == 1


def test_events_without_a_call_id_are_dropped() -> None:
    assert parse_call_events({"events": [{"type": "CALL_RECEIVED"}]}) == []
    assert parse_call_events(None) == []


# --- Answering ------------------------------------------------------------


async def test_an_inbound_call_is_answered_greeted_and_listened_to(calls) -> None:
    await voice_call.handle_call_event(received())

    assert calls.did("answer")
    assert calls.did("capture")
    row = read_call()
    assert row is not None
    assert row.status == "answered"
    assert row.answered_at is not None


async def test_the_caller_number_is_stored_only_as_a_hash(calls) -> None:
    await voice_call.handle_call_event(received())

    row = read_call()
    assert row.hashed_caller_identity == channel_identity_hash("voice", CALLER)
    assert CALLER not in row.hashed_caller_identity
    assert "9876543210" not in row.hashed_caller_identity


async def test_a_repeated_call_received_does_not_answer_twice(calls) -> None:
    """Provider retries are common; a second answer would be a second charge."""
    await voice_call.handle_call_event(received())
    await voice_call.handle_call_event(received())

    assert [name for name, _ in calls.actions].count("answer") == 1


async def test_a_failed_answer_closes_the_call_record(calls) -> None:
    calls.answer_ok = False
    await voice_call.handle_call_event(received())

    row = read_call()
    assert row.status == "ended"
    assert row.end_reason == "answer_failed"


async def test_nothing_happens_when_voice_is_not_configured(monkeypatch, database) -> None:
    monkeypatch.setattr(voice_call, "build_calls_provider", lambda: None)
    await voice_call.handle_call_event(received())
    assert read_call() is None


# --- Turns ----------------------------------------------------------------


async def test_a_spoken_turn_runs_the_agent_and_replies(calls) -> None:
    await voice_call.handle_call_event(received())
    calls.actions.clear()

    await voice_call.handle_call_event(speech("I need a scholarship"))

    row = read_call()
    assert row.turn_count == 1
    assert row.session_id is not None
    # Listening resumes for the next turn.
    assert calls.did("capture")


async def test_an_empty_capture_reprompts_rather_than_hanging_up(calls) -> None:
    """Silence on a phone line reads as a dropped call."""
    await voice_call.handle_call_event(received())
    calls.actions.clear()

    await voice_call.handle_call_event(speech("   "))

    assert calls.did("capture")
    assert not calls.did("hangup")


async def test_a_call_ends_after_the_turn_ceiling(calls) -> None:
    await voice_call.handle_call_event(received())
    with Session(engine) as db:
        row = (
            db.query(CallSession).filter_by(provider_call_id=CALL_ID).first()
        )
        row.turn_count = MAX_TURNS
        db.add(row)
        db.commit()
    calls.actions.clear()

    await voice_call.handle_call_event(speech("one more question"))

    assert calls.did("hangup")
    assert read_call().end_reason == "max_turns"


async def test_a_call_ends_after_the_duration_ceiling(calls) -> None:
    """A stuck call bills per minute and holds a line someone else needs."""
    await voice_call.handle_call_event(received())
    with Session(engine) as db:
        row = db.query(CallSession).filter_by(provider_call_id=CALL_ID).first()
        row.started_at = datetime.now(UTC) - timedelta(seconds=MAX_CALL_SECONDS + 60)
        db.add(row)
        db.commit()
    calls.actions.clear()

    await voice_call.handle_call_event(speech("still here"))

    assert calls.did("hangup")
    assert read_call().end_reason == "max_duration"


async def test_a_turn_for_an_unknown_call_is_ignored(calls) -> None:
    await voice_call.handle_call_event(
        {"type": "SPEECH_CAPTURED", "call_id": "never-seen", "text": "hello"}
    )
    assert not calls.actions


# --- Ending ---------------------------------------------------------------


async def test_a_finished_event_closes_the_record_with_a_duration(calls) -> None:
    await voice_call.handle_call_event(received())
    await voice_call.handle_call_event(
        {"type": "CALL_FINISHED", "call_id": CALL_ID, "reason": "caller_hangup"}
    )

    row = read_call()
    assert row.status == "ended"
    assert row.end_reason == "caller_hangup"
    assert row.duration_seconds is not None


async def test_a_second_finished_event_does_not_rewrite_the_record(calls) -> None:
    await voice_call.handle_call_event(received())
    await voice_call.handle_call_event(
        {"type": "CALL_FINISHED", "call_id": CALL_ID, "reason": "caller_hangup"}
    )
    await voice_call.handle_call_event(
        {"type": "CALL_FINISHED", "call_id": CALL_ID, "reason": "something_else"}
    )

    assert read_call().end_reason == "caller_hangup"


# --- Privacy and identity -------------------------------------------------


async def test_the_call_record_holds_no_audio_or_transcript(calls) -> None:
    await voice_call.handle_call_event(received())
    await voice_call.handle_call_event(speech("my income is two lakh"))

    row = read_call()
    columns = set(row.model_dump())
    assert not columns & {"recording", "recording_url", "audio", "transcript"}
    assert "two lakh" not in str(row.model_dump())


async def test_a_telephony_session_cannot_satisfy_the_browser_dependency(
    calls, client
) -> None:
    """A caller ID is asserted by the network and proves nothing."""
    await voice_call.handle_call_event(received())
    await voice_call.handle_call_event(speech("I need a scholarship"))

    identity = channel_identity_hash("voice", CALLER)
    with Session(engine) as db:
        row = db.query(UserSession).filter_by(phone_or_session_id=identity).first()

    assert row.auth_mode == "telephony"
    assert row.access_token_hash is None
    response = client.get(
        f"/api/sessions/{row.id}/saved-benefits",
        headers={"Authorization": f"Bearer {identity}"},
    )
    assert response.status_code == 401


async def test_a_repeat_caller_resumes_one_conversation(calls) -> None:
    await voice_call.handle_call_event(received())
    await voice_call.handle_call_event(speech("I need a scholarship"))
    await voice_call.handle_call_event(
        {"type": "CALL_FINISHED", "call_id": CALL_ID, "reason": "caller_hangup"}
    )

    identity = channel_identity_hash("voice", CALLER)
    with Session(engine) as db:
        rows = db.query(UserSession).filter_by(phone_or_session_id=identity).all()
    assert len(rows) == 1


# --- Webhook route --------------------------------------------------------


def test_the_voice_webhook_requires_the_shared_secret(client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "infobip_webhook_auth_secret", "s3cret", raising=False)
    assert client.post("/api/webhooks/infobip/voice/events", json={}).status_code == 401


def test_the_voice_webhook_acknowledges_immediately(client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "infobip_webhook_auth_secret", "s3cret", raising=False)
    monkeypatch.setattr(voice_call, "build_calls_provider", lambda: None)

    response = client.post(
        "/api/webhooks/infobip/voice/events",
        json={"events": [{"type": "CALL_RECEIVED", "callId": new_id("c")}]},
        headers={"X-Infobip-Webhook-Secret": "s3cret"},
    )
    assert response.status_code == 200
    assert response.json()["processed"] == 1
