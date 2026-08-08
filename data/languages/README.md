# Language release evidence

The product registers eight expansion locales, but it does not claim them as
supported until each locale has a complete, native-reviewed release packet:

`ta` Tamil · `te` Telugu · `mr` Marathi · `bn` Bengali · `gu` Gujarati · `ml`
Malayalam · `pa` Punjabi · `or` Odia.

## What belongs in a release packet

For each locale, add a prompt module at
`services/agent/src/sahaayak_agent/prompts/<code>.py` with the same semantic
keys as `prompts/en.py`. Do not translate eligibility rules at request time.
The bundle should be reviewed against the official source-language content and
should preserve placeholders such as `{state}`, `{count}`, `{name}`, and
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
```

The command is read-only and exits non-zero while any bundle, review evidence,
or activation gate is missing. It never changes the database or turns on a
feature flag. The eight locales are intentionally inactive in the current
working tree because native-speaker evidence and complete translations have
not been supplied.
