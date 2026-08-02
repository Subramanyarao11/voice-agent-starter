"""Synthesise and cache every canned phrase before a demo or a test session.

Sarvam credits are the tightest constraint in this build, and the same twenty
questions are asked in every single call. Warming them once turns synthesis
from a per-call cost into a one-off cost per phrase per language, and removes
the first-use pause from a recorded demo.

Usage:
    python scripts/prewarm_tts.py --languages kn hi
    python scripts/prewarm_tts.py --languages kn --dry-run
"""

from __future__ import annotations

import argparse
import asyncio

from sahaayak_agent.prompts import CATALOGS
from sahaayak_agent.voice import VoiceService
from sahaayak_common import configure_logging, settings

# Phrases with placeholders are skipped: their final text depends on the caller,
# so a cached version would be wrong for everyone else.
PLACEHOLDER_MARKERS = ("{", "}")


def cacheable_phrases(language_code: str) -> list[str]:
    return [
        text
        for text in CATALOGS.get(language_code, {}).values()
        if text and not any(marker in text for marker in PLACEHOLDER_MARKERS)
    ]


async def run(language_codes: list[str], dry_run: bool) -> None:
    configure_logging()

    total_characters = 0
    for code in language_codes:
        phrases = cacheable_phrases(code)
        characters = sum(len(p) for p in phrases)
        total_characters += characters
        print(f"{code}: {len(phrases)} phrases, {characters} characters")

    print(f"\nTotal: {total_characters} characters across {len(language_codes)} languages.")

    if dry_run:
        print("Dry run — nothing synthesised. Drop --dry-run to spend credits.")
        return

    if not settings.tts_enabled:
        raise SystemExit("SARVAM_API_KEY is not set, so there is nothing to warm.")

    service = VoiceService()
    for code in language_codes:
        warmed = await service.prewarm(cacheable_phrases(code), language_code=code)
        print(f"{code}: {warmed} newly synthesised, the rest were already cached.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--languages", nargs="+", default=["kn", "hi"])
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report how many characters would be billed without calling the API",
    )
    args = parser.parse_args()
    asyncio.run(run(args.languages, args.dry_run))


if __name__ == "__main__":
    main()
