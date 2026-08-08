"""Run a short, budget-aware Sarvam TTS → OpenAI STT language smoke test.

One short prompt is synthesized per locale and sent back through transcription.
The result is written as a redacted evidence artifact that an admin can attach
in Admin → Languages. This command never updates language activation or flags.

Usage:
    uv run python scripts/19_language_voice_smoke.py --dry-run
    uv run python scripts/19_language_voice_smoke.py
    uv run python scripts/19_language_voice_smoke.py --languages kn,hi,en
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import time
import unicodedata
from datetime import UTC, datetime
from difflib import SequenceMatcher
from pathlib import Path

from sahaayak_agent.languages import ALL_PROFILES, get_profile
from sahaayak_agent.prompts import get_catalog
from sahaayak_agent.voice.base import VoiceUnavailable
from sahaayak_agent.voice.service import VoiceService
from sahaayak_common import OpenAIBudgetLedger, settings

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data/languages/evidence/language-voice-smoke-latest.json"
DEFAULT_CODES = [profile.code for profile in ALL_PROFILES]
SCRIPT_RANGES = {
    "hi": (0x0900, 0x097F),
    "mr": (0x0900, 0x097F),
    "bn": (0x0980, 0x09FF),
    "pa": (0x0A00, 0x0A7F),
    "gu": (0x0A80, 0x0AFF),
    "or": (0x0B00, 0x0B7F),
    "ta": (0x0B80, 0x0BFF),
    "te": (0x0C00, 0x0C7F),
    "kn": (0x0C80, 0x0CFF),
    "ml": (0x0D00, 0x0D7F),
}


def parse_codes(raw: str | None) -> list[str]:
    codes = DEFAULT_CODES if not raw else [part.strip().lower() for part in raw.split(",")]
    known = {profile.code for profile in ALL_PROFILES}
    unknown = sorted(set(codes) - known)
    if unknown:
        raise ValueError(f"unknown language code(s): {', '.join(unknown)}")
    return list(dict.fromkeys(codes))


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return "".join(
        character
        for character in normalized
        if unicodedata.category(character)[0] in {"L", "M", "N"}
    )


def has_expected_script(code: str, value: str) -> bool:
    if code == "en":
        return any("a" <= character.casefold() <= "z" for character in value)
    start, end = SCRIPT_RANGES[code]
    return any(start <= ord(character) <= end for character in value)


def safe_error(exc: BaseException) -> str:
    message = re.sub(r"(?:sk|sess)-[A-Za-z0-9_-]+", "[redacted]", str(exc))
    return f"{exc.__class__.__name__}: {message[:500]}"


async def run_smoke(codes: list[str], phrase_key: str) -> list[dict[str, object]]:
    service = VoiceService()
    results: list[dict[str, object]] = []
    for code in codes:
        profile = get_profile(code)
        phrase = get_catalog(code).render(phrase_key)
        result: dict[str, object] = {
            "language_code": code,
            "language": profile.name,
            "native_name": profile.native_name,
            "stt_locale": profile.resolved_stt_locale(),
            "tts_locale": profile.resolved_tts_locale(),
            "phrase_key": phrase_key,
            "phrase_characters": len(phrase),
            "phrase": phrase,
            "passed": False,
        }
        started = time.perf_counter()
        try:
            synthesis = await service.speak(
                phrase,
                language_code=code,
                subject=f"language-voice-smoke:{code}",
            )
            result.update(
                {
                    "tts_provider": synthesis.provider,
                    "tts_cached": synthesis.cached,
                    "tts_billed_characters": synthesis.billed_characters,
                    "audio_bytes": len(synthesis.audio),
                }
            )
            if not synthesis.audio:
                raise VoiceUnavailable("TTS returned empty audio")

            transcription = await service.transcribe(
                synthesis.audio,
                language_code=code,
                filename=f"language-smoke-{code}.wav",
                subject=f"language-voice-smoke:{code}",
            )
            transcript = transcription.text.strip()
            similarity = SequenceMatcher(
                None, normalize_text(phrase), normalize_text(transcript)
            ).ratio()
            result.update(
                {
                    "stt_provider": transcription.provider,
                    "transcript": transcript,
                    "transcript_characters": len(transcript),
                    "script_detected": has_expected_script(code, transcript),
                    "text_similarity": round(similarity, 3),
                    "passed": bool(transcript)
                    and has_expected_script(code, transcript)
                    and similarity >= 0.35,
                }
            )
        except Exception as exc:  # provider failures are recorded per locale
            result["error"] = safe_error(exc)
        result["latency_ms"] = round((time.perf_counter() - started) * 1000)
        results.append(result)
        status = "PASS" if result["passed"] else "FAIL"
        print(
            f"{status} {code} {profile.name}: "
            f"{result.get('error', result.get('transcript', ''))}"
        )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--languages", help="comma-separated locale codes; defaults to all 11")
    parser.add_argument("--phrase-key", default="ask_age", choices=("ask_age", "greeting"))
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    try:
        codes = parse_codes(args.languages)
    except ValueError as exc:
        parser.error(str(exc))

    ledger = OpenAIBudgetLedger(
        settings.openai_budget_usd,
        settings.resolved_openai_budget_ledger_path,
    )
    budget_before = ledger.summary()
    planned_stt_reservation = len(codes) * settings.openai_transcription_reservation_usd
    if not args.dry_run and planned_stt_reservation > float(budget_before["remaining_usd"]):
        parser.error(
            f"safe preflight stopped: {len(codes)} STT calls reserve "
            f"${planned_stt_reservation:.2f}, but only ${budget_before['remaining_usd']} remains"
        )

    if args.dry_run:
        report_results = []
        for code in codes:
            profile = get_profile(code)
            phrase = get_catalog(code).render(args.phrase_key)
            print(
                f"DRY-RUN {code} {profile.name}: "
                f"{profile.resolved_tts_locale()} → {profile.resolved_stt_locale()} "
                f"({len(phrase)} chars)"
            )
    else:
        report_results = asyncio.run(run_smoke(codes, args.phrase_key))

    budget_after = ledger.summary()
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "phrase_key": args.phrase_key,
        "languages": codes,
        "dry_run": args.dry_run,
        "budget_before": {
            key: budget_before[key]
            for key in ("budget_usd", "reserved_usd", "observed_usd", "remaining_usd")
        },
        "budget_after": {
            key: budget_after[key]
            for key in ("budget_usd", "reserved_usd", "observed_usd", "remaining_usd")
        },
        "results": report_results,
        "passed": args.dry_run or all(result["passed"] for result in report_results),
        "note": (
            "Automated provider evidence only; attach native-speaker and browser QA evidence "
            "before Admin → Languages approval."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Evidence report: {args.output}")
    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
