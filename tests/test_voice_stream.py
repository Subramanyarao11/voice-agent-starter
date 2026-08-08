"""Offline protocol tests for the browser voice transport."""

from __future__ import annotations

import asyncio

from sahaayak_common import UserSession
from sahaayak_contracts import AgentState, Intent, SynthesisResult, TranscriptionResult


class FakeRuntime:
    def __init__(self) -> None:
        self.transcripts: list[str] = []

    async def run_turn(self, *, caller_id, transcript, language_code, state_code):
        self.transcripts.append(transcript)
        session = UserSession(
            id="ses_stream_runtime",
            phone_or_session_id=caller_id,
            state_code=state_code,
            language_code=language_code,
        )
        state = AgentState(
            session_id=session.id,
            state_code=state_code,
            language_code=language_code,
            transcript=transcript,
            response_text="First sentence. Second sentence.",
            intent=Intent.GREETING,
        )
        return session, state


class FakeVoice:
    tts_available = True

    def __init__(self) -> None:
        self.transcribed: list[bytes] = []
        self.spoken: list[str] = []

    async def transcribe(self, audio, *, language_code, filename):
        self.transcribed.append(audio)
        return TranscriptionResult(
            text="hello",
            language_code=language_code,
            provider="fake-stt",
        )

    async def speak(self, text, *, language_code):
        self.spoken.append(text)
        return SynthesisResult(
            audio=f"audio-{len(self.spoken)}".encode(),
            mime_type="audio/wav",
            provider="fake-tts",
        )


class SlowVoice(FakeVoice):
    async def speak(self, text, *, language_code):
        self.spoken.append(text)
        await asyncio.sleep(30)
        return SynthesisResult(audio=b"late", provider="slow-tts")


def _start_payload(session: dict) -> dict:
    return {
        "type": "start",
        "access_token": session["access_token"],
        "language_code": "kn",
        "state_code": "KA",
        "speak": True,
    }


def test_streaming_voice_sends_sentence_audio_and_turn_end(client, guest_session, monkeypatch):
    from sahaayak_api.routers import voice_stream

    fake_voice = FakeVoice()
    fake_runtime = FakeRuntime()
    monkeypatch.setattr(voice_stream, "get_runtime", lambda: fake_runtime)
    monkeypatch.setattr(voice_stream, "get_voice", lambda: fake_voice)
    session = guest_session(language_code="kn")

    with client.websocket_connect("/api/voice/stream") as socket:
        socket.send_json(_start_payload(session))
        assert socket.receive_json()["type"] == "ready"
        socket.send_bytes(b"chunk-one")
        socket.send_bytes(b"chunk-two")
        socket.send_json({"type": "end_turn"})
        assert socket.receive_json()["type"] == "transcript"
        socket.send_json({"type": "submit_transcript", "text": "hello from the caller"})

        events = []
        while True:
            event = socket.receive_json()
            events.append(event)
            if event["type"] == "turn_end":
                break

    assert fake_voice.transcribed == [b"chunk-onechunk-two"]
    assert fake_voice.spoken == ["First sentence.", "Second sentence."]
    assert fake_runtime.transcripts == ["hello from the caller"]
    assert [event["type"] for event in events] == [
        "transcript_accepted",
        "turn",
        "audio_chunk",
        "audio_chunk",
        "turn_end",
    ]
    assert events[0]["edited"] is True
    assert events[-1]["tts_chunks"] == 2


def test_streaming_voice_interrupt_cancels_in_flight_tts(client, guest_session, monkeypatch):
    from sahaayak_api.routers import voice_stream

    fake_voice = SlowVoice()
    monkeypatch.setattr(voice_stream, "get_runtime", lambda: FakeRuntime())
    monkeypatch.setattr(voice_stream, "get_voice", lambda: fake_voice)
    session = guest_session(language_code="kn")

    with client.websocket_connect("/api/voice/stream") as socket:
        socket.send_json(_start_payload(session))
        assert socket.receive_json()["type"] == "ready"
        socket.send_bytes(b"chunk")
        socket.send_json({"type": "end_turn"})
        assert socket.receive_json()["type"] == "transcript"
        socket.send_json({"type": "submit_transcript", "text": "hello"})
        assert socket.receive_json()["type"] == "transcript_accepted"
        assert socket.receive_json()["type"] == "turn"
        socket.send_json({"type": "interrupt"})
        assert socket.receive_json() == {"type": "interrupted"}

        socket.send_json({"type": "ping"})
        assert socket.receive_json() == {"type": "pong"}


def test_pcm_stream_fallback_is_wrapped_as_mono_wav():
    import io
    import wave

    from sahaayak_api.routers.voice_stream import _pcm16_to_wav

    payload = _pcm16_to_wav(b"\x00\x01" * 240, 24_000)
    with wave.open(io.BytesIO(payload), "rb") as reader:
        assert reader.getnchannels() == 1
        assert reader.getsampwidth() == 2
        assert reader.getframerate() == 24_000
        assert reader.readframes(240) == b"\x00\x01" * 240
