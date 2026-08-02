"""Tests for the speech layer's pure parts.

No provider is called. What is worth testing here is the handling around them:
that a long reply is not truncated, that stitched audio is still playable, and
that the cache key is stable — the credit budget depends on the last one.
"""

from __future__ import annotations

import io
import wave

from sahaayak_agent.languages import get_profile
from sahaayak_agent.voice.sarvam_tts import (
    MAX_CHUNK_CHARACTERS,
    merge_wav,
    split_for_synthesis,
)
from sahaayak_agent.voice.service import cache_key


def make_wav(seconds: float = 0.1, framerate: int = 8000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(framerate)
        writer.writeframes(b"\x00\x00" * int(framerate * seconds))
    return buffer.getvalue()


def test_short_text_is_left_as_one_chunk():
    assert split_for_synthesis("How old are you?") == ["How old are you?"]


def test_long_text_is_split_rather_than_truncated():
    """Truncation would cut the caller off inside the part that matters."""
    text = " ".join(["This is a sentence about a scheme."] * 40)
    chunks = split_for_synthesis(text)

    assert len(chunks) > 1
    assert all(len(chunk) <= MAX_CHUNK_CHARACTERS for chunk in chunks)
    # Every word survives the split.
    assert sum(chunk.count("scheme") for chunk in chunks) == 40


def test_hindi_danda_is_treated_as_a_sentence_boundary():
    """Without it, Devanagari text never splits and always overflows."""
    sentence = "यह एक योजना है। " * 60
    chunks = split_for_synthesis(sentence)
    assert len(chunks) > 1
    assert all(len(chunk) <= MAX_CHUNK_CHARACTERS for chunk in chunks)


def test_an_oversized_single_sentence_still_gets_split():
    chunks = split_for_synthesis("x" * 1200)
    assert all(len(chunk) <= MAX_CHUNK_CHARACTERS for chunk in chunks)
    assert "".join(chunks) == "x" * 1200


def test_merged_audio_is_a_single_playable_stream():
    """Concatenating the bytes would embed a second RIFF header mid-audio."""
    one, two = make_wav(0.1), make_wav(0.2)
    merged = merge_wav([one, two])

    with wave.open(io.BytesIO(merged), "rb") as reader:
        assert reader.getnchannels() == 1
        assert reader.getframerate() == 8000
        assert reader.getnframes() == int(8000 * 0.1) + int(8000 * 0.2)


def test_merging_a_single_chunk_is_a_passthrough():
    audio = make_wav()
    assert merge_wav([audio]) == audio
    assert merge_wav([]) == b""


def test_cache_key_is_stable_for_identical_input():
    """Python's built-in hash is salted per process; a key built on it would
    miss on every restart, which is exactly what the cache exists to avoid."""
    profile = get_profile("kn")
    first = cache_key("ನಿಮ್ಮ ವಯಸ್ಸು ಎಷ್ಟು?", profile, "bulbul:v2")
    second = cache_key("ನಿಮ್ಮ ವಯಸ್ಸು ಎಷ್ಟು?", profile, "bulbul:v2")
    assert first == second
    assert first.startswith("tts:kn:")


def test_cache_key_changes_with_anything_that_changes_the_audio():
    kannada, hindi = get_profile("kn"), get_profile("hi")
    base = cache_key("hello", kannada, "bulbul:v2")

    assert cache_key("hello there", kannada, "bulbul:v2") != base
    assert cache_key("hello", hindi, "bulbul:v2") != base
    assert cache_key("hello", kannada, "bulbul:v1") != base


def test_language_profiles_carry_each_provider_locale_format():
    """Whisper wants "kn" and Sarvam wants "kn-IN"; conflating them breaks one."""
    profile = get_profile("kn")
    assert profile.resolved_stt_locale() == "kn"
    assert profile.resolved_tts_locale() == "kn-IN"


def test_an_unknown_language_falls_back_rather_than_failing():
    assert get_profile("zz").code == "en"
