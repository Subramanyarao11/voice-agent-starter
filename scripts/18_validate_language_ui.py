"""Validate script, font, accessibility, and mobile readiness signals.

This is a static preflight, not a substitute for a real browser and native
speaker. It catches regressions such as removing a script fallback font, the
document language binding, reduced-motion support, or the mobile minimum width.

Usage:
    uv run python scripts/18_validate_language_ui.py
    uv run python scripts/18_validate_language_ui.py --json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sahaayak_agent.languages import ALL_PROFILES
from sahaayak_agent.prompts import get_catalog

ROOT = Path(__file__).resolve().parents[1]
CSS_PATH = ROOT / "apps/web/src/index.css"
HOME_PATH = ROOT / "apps/web/src/routes/home.tsx"
UI_I18N_PATH = ROOT / "apps/web/src/lib/i18n.ts"
UI_PROVIDER_PATH = ROOT / "apps/web/src/features/i18n/ui-provider.tsx"

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

FONT_FALLBACKS = {
    "hi": "Noto Sans Devanagari",
    "mr": "Noto Sans Devanagari",
    "bn": "Noto Sans Bengali",
    "pa": "Noto Sans Gurmukhi",
    "gu": "Noto Sans Gujarati",
    "or": "Noto Sans Odia",
    "ta": "Noto Sans Tamil",
    "te": "Noto Sans Telugu",
    "kn": "Noto Sans Kannada",
    "ml": "Noto Sans Malayalam",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    css = CSS_PATH.read_text(encoding="utf-8")
    home = HOME_PATH.read_text(encoding="utf-8")
    ui_i18n = UI_I18N_PATH.read_text(encoding="utf-8")
    ui_provider = UI_PROVIDER_PATH.read_text(encoding="utf-8")
    checks: list[dict[str, object]] = []

    def check(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "passed": passed, "detail": detail})

    check("mobile_min_width", "min-width: 320px" in css, "body keeps a 320px layout floor")
    check(
        "horizontal_overflow_guard",
        "overflow-x: hidden" in css,
        "body clips accidental horizontal overflow",
    )
    check(
        "reduced_motion",
        "prefers-reduced-motion: reduce" in css,
        "CSS disables long transitions when the user requests reduced motion",
    )
    check("focus_visible", "focus-visible" in css, "keyboard focus styling remains present")
    check(
        "document_language_binding",
        "document.documentElement.lang" in ui_provider,
        "the selected locale updates the document language through the UI provider",
    )
    check(
        "main_landmark_label",
        'aria-labelledby="page-title"' in home,
        "the primary landmark has an accessible name",
    )
    check(
        "conversation_landmark_label",
        'aria-labelledby="conversation-title"' in home,
        "the conversation region has an accessible name",
    )

    profiles = {profile.code for profile in ALL_PROFILES}
    check(
        "catalog_profiles",
        profiles == {"en", "hi", "kn", "ta", "te", "mr", "bn", "gu", "ml", "pa", "or"},
        "all 11 language profiles are registered",
    )
    ui_locale_tokens = {f'"{code}"' for code in profiles}
    check(
        "ui_locale_catalog",
        all(token in ui_i18n for token in ui_locale_tokens)
        and "ENGLISH_COPY" in ui_i18n
        and "review_required" in ui_i18n,
        "the typed UI catalog covers every planned locale and marks drafts for review",
    )
    for code, (start, end) in SCRIPT_RANGES.items():
        greeting = get_catalog(code).render("greeting")
        check(
            f"script_{code}",
            any(start <= ord(character) <= end for character in greeting),
            f"{code} greeting contains its expected Unicode script",
        )
        fallback = FONT_FALLBACKS[code]
        check(
            f"font_{code}",
            fallback in css,
            f"CSS includes a fallback for {fallback}",
        )

    failures = [item for item in checks if not item["passed"]]
    report = {"passed": not failures, "checks": checks, "failures": failures}
    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for item in checks:
            print(f"{'PASS' if item['passed'] else 'FAIL'} {item['name']}: {item['detail']}")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
