"""Infobip Calls API actions for the clip-based voice path.

This is Path C of the integration plan: answer, play a clip, capture a short
utterance, run the existing agent, play the reply. It is deliberately not the
streaming path — Sahaayak transcribes whole clips with Whisper and synthesizes
whole WAVs with Sarvam, and pretending that is a real-time media loop would
produce a call that stutters rather than a demo that works.

Outbound calling is not implemented and must not be. Everything here reacts to
a call the caller placed.
"""

from __future__ import annotations

import base64

from sahaayak_api.integrations.infobip.client import InfobipClient, get_infobip_client
from sahaayak_common import get_logger, settings

log = get_logger(__name__)

ANSWER_PATH = "/calls/1/calls/{call_id}/answer"
HANGUP_PATH = "/calls/1/calls/{call_id}/hangup"
PLAY_PATH = "/calls/1/calls/{call_id}/play"
CAPTURE_SPEECH_PATH = "/calls/1/calls/{call_id}/capture/speech"
FILES_PATH = "/calls/1/files"

# Ceilings enforced on our side rather than trusted to the provider. A stuck
# call costs money per minute and holds a channel that another caller needs.
MAX_CALL_SECONDS = 300
MAX_TURNS = 8
# How long to wait for the caller to say something before giving up on a turn.
CAPTURE_TIMEOUT_SECONDS = 10
CAPTURE_MAX_SILENCE_SECONDS = 3


class InfobipCallsProvider:
    """Thin action wrapper. The call's state machine lives in the worker."""

    name = "infobip_calls"

    def __init__(self, client: InfobipClient) -> None:
        self._client = client

    def available(self) -> bool:
        return bool(
            settings.infobip_channel_ready("voice") and self._client.config.configured
        )

    async def answer(self, call_id: str) -> bool:
        response = await self._client.post(
            ANSWER_PATH.format(call_id=call_id),
            {},
            operation="answer",
            channel="voice",
        )
        return response.ok

    async def hangup(self, call_id: str, *, reason: str = "normal") -> bool:
        response = await self._client.post(
            HANGUP_PATH.format(call_id=call_id),
            {"reason": reason},
            operation="hangup",
            channel="voice",
        )
        return response.ok

    async def upload_audio(self, audio: bytes, *, mime_type: str = "audio/wav") -> str:
        """Store a synthesized clip with the provider so it can be played.

        The Calls API plays a file it holds or a public URL. Uploading keeps
        the audio off any public URL of ours — a spoken eligibility answer must
        not be fetchable by anyone who guesses a link.
        """
        response = await self._client.post(
            FILES_PATH,
            {
                "contentType": mime_type,
                "data": base64.b64encode(audio).decode("ascii"),
            },
            operation="upload_audio",
            channel="voice",
        )
        if not response.ok:
            log.warning(
                "call_audio_upload_failed", error_class=response.error_class.value
            )
            return ""
        file_id = response.payload.get("fileId") or response.payload.get("id") or ""
        return str(file_id)

    async def play_file(self, call_id: str, file_id: str) -> bool:
        response = await self._client.post(
            PLAY_PATH.format(call_id=call_id),
            {"file": {"fileId": file_id}},
            operation="play",
            channel="voice",
        )
        return response.ok

    async def capture_speech(self, call_id: str, *, language: str) -> bool:
        """Ask the provider to record the caller's next utterance."""
        response = await self._client.post(
            CAPTURE_SPEECH_PATH.format(call_id=call_id),
            {
                "language": _capture_locale(language),
                "timeout": CAPTURE_TIMEOUT_SECONDS,
                "maxSilence": CAPTURE_MAX_SILENCE_SECONDS,
            },
            operation="capture_speech",
            channel="voice",
        )
        return response.ok


def _capture_locale(language_code: str) -> str:
    return {"en": "en-IN", "hi": "hi-IN", "kn": "kn-IN"}.get(language_code, "en-IN")


def build_calls_provider() -> InfobipCallsProvider | None:
    client = get_infobip_client()
    if client is None or not settings.infobip_channel_ready("voice"):
        return None
    provider = InfobipCallsProvider(client)
    return provider if provider.available() else None
