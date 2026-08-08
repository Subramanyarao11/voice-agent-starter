# Language release evidence

The product registers eight expansion locales, but it does not claim them as
supported until each locale has a complete, native-reviewed release packet:

`ta` Tamil · `te` Telugu · `mr` Marathi · `bn` Bengali · `gu` Gujarati · `ml`
Malayalam · `pa` Punjabi · `or` Odia.

## What belongs in a release packet

Prompt modules now exist for all eight expansion locales, alongside the
English, Hindi, and Kannada launch bundles. The new modules are explicitly
marked `machine_assisted`; they are translation drafts for review, not proof
of native approval. Each module must keep the same semantic keys as
`prompts/en.py`. Do not translate eligibility rules at request time. The
bundle should be reviewed against the official source-language content and
must preserve placeholders such as `{state}`, `{count}`, `{name}`, and
`{documents}`.

The reviewer then records one of `pending`, `approved`, or `rejected` for all
seven gates in **Admin → Languages**:

- native-speaker wording and respectful terminology;
- interface strings and accessibility labels;
- prompt-key completeness and safe interpolation;
- benefit/job content and source terminology;
- understanding fixtures for script, numbers, and code-switching;
- STT/TTS pronunciation and real voice evidence;
- keyboard, contrast, font/glyph, and mobile accessibility QA.

The review must include a durable evidence URL and notes. The admin endpoint
requires an explicit attestation, blocks prompt approval until the bundle is
installed, and only an admin can activate a fully approved locale. The
`ten_language_rollout` flag remains a separate reversible cohort control.

## Validation

Run the release check before asking an admin to activate a locale:

```bash
uv run python scripts/17_validate_language_release.py --code ta
uv run python scripts/17_validate_language_release.py --all
uv run python scripts/18_validate_language_ui.py
uv run python scripts/19_language_voice_smoke.py --languages kn,hi,en,ta,te,mr,bn,gu,ml,pa,or
```

The command is read-only and exits non-zero while any bundle, review evidence,
or activation gate is missing. It never changes the database or turns on a
feature flag. The expansion locales remain intentionally inactive because
native-speaker evidence, localized benefit content, and provider QA still need
to be supplied. The same Admin → Languages workflow can record evidence for
English, Hindi, and Kannada when their launch-language QA is refreshed. The
voice smoke command writes provider evidence to
`data/languages/evidence/language-voice-smoke-latest.json`; it does not mark a
locale approved or active.
