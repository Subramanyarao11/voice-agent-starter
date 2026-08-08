# Streaming voice operations

The browser voice path now supports a low-latency turn transport at
`/api/voice/stream`. It is an optimization over the existing clip endpoint,
not a second conversation engine: both paths use the same guest token, agent
graph, hosted RAG, provider policy, and text fallback.

## Browser protocol

The client opens a WebSocket and sends a JSON start frame first:

```json
{
  "type": "start",
  "access_token": "server-issued-guest-token",
  "language_code": "kn",
  "state_code": "KA",
  "mime_type": "audio/webm;codecs=opus",
  "speak": true
}
```

It then sends short `MediaRecorder` binary chunks. Local browser VAD ends the
utterance after sustained silence, or the user can send `{ "type":
"end_turn" }` after stopping. The server emits, in order:

1. `ready`
2. `transcript`
3. `turn` containing the normal source-aware response
4. zero or more `audio_chunk` events, one per sentence
5. `turn_end`

The client may send `{ "type": "interrupt" }` while transcription, RAG, or
TTS is in progress. The active task is cancelled and queued audio is discarded
so a caller can speak again. `{ "type": "ping" }` is available for a client
keepalive check.

## Current boundaries

- VAD is client-side and uses an RMS threshold; it is a turn-end detector, not
  a claim of speaker diarization or noisy-environment accuracy.
- OpenAI Whisper currently transcribes one completed utterance. The server
  buffers the current turn and does not claim incremental STT.
- TTS starts sentence by sentence, so first audio can arrive before the full
  answer is synthesized. Audio is not persisted by default.
- If a provider fails, text and citations still arrive. The existing clip
  upload path remains the compatibility fallback for browsers without
  WebSocket, MediaRecorder, or microphone support.
- Browser autoplay can block streamed audio. The transcript and answer remain
  available in the UI; the user must grant playback permission or use the
  existing answer audio control when available.

## Security and limits

- The start frame must contain a server-issued guest bearer token. The server
  resolves the token to the session and never accepts a caller ID from the
  browser.
- Voice turns consume the shared Redis-backed `voice` rate-limit bucket. The
  limiter is fail-closed outside development when Redis is unavailable.
- The server caps a turn at 10 MiB, 480 chunks, or 90 seconds. No raw audio is
  written to the database or object storage by this transport.
- Deploy behind HTTPS so the browser can use `wss://`; `localhost` remains
  suitable for development.

## Verification

Offline protocol coverage is in `tests/test_voice_stream.py` and verifies
sentence-level audio events plus cancellation during TTS. A real Kannada and
Hindi test still needs to be run with the configured provider keys and recorded
with transcript accuracy, first-audio latency, total latency, citation
correctness, and playback quality. That human/provider test is a release gate,
not something the offline protocol test can establish.
