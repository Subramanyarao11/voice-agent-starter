# Data review — 2026-08-02

## Scope

This is the first real-data ingestion pass for Sahaayak. It uses the
[`shrijayan/gov_myscheme`](https://huggingface.co/datasets/shrijayan/gov_myscheme)
Hugging Face corpus of myScheme PDF documents. The run was deliberately capped
before the paid structuring pilot was started.

| Stage | Result |
| --- | --- |
| Source documents discovered | 2,876 PDFs |
| Text extraction | 2,876/2,876 non-empty JSONL records |
| Coarse Karnataka education/welfare filter | 317 matching documents |
| Exact-content deduplication | 97 duplicates removed |
| Candidate documents | 220 |
| Structured pilot | 20 rows |
| Structuring failures | 0 |
| Structuring model | `gpt-4o` |
| Prompt version | `structured-benefit-v1` |

The raw PDFs, extracted text, candidate JSONL, pilot JSONL, SQLite database,
and usage ledger are local regenerable artifacts and are intentionally ignored
by Git.

## Budget and safety

The persistent ledger is configured with a `$10.00` ceiling. It refuses any
configured ceiling above `$15.00`, reserves a conservative upper bound before
each request, keeps failed-call reservations, and survives process restarts.

The 20-row pilot recorded:

- 20 completed calls;
- `$1.118400` reserved by the guard;
- `$0.241508` observed from provider-reported token usage;
- 0 failed or pending calls.

All OpenAI call sites currently share this ledger: structuring, localization,
agent understanding, and OpenAI transcription. No embedding calls were made.

## Review status

All 20 pilot rows are `machine_structured` and inactive. None is presented as a
production-ready benefit until a human reviewer checks the source document.
The local database therefore contains the existing eight illustrative active
rows plus the 20 inactive machine-structured pilot rows.

Spot-checks found plausible extractions, but also the expected risks from
scraped government-page PDFs:

- mojibake and navigation/UI text are present in the source extraction;
- the upstream corpus contains duplicate exports and some non-canonical file
  suffixes;
- six seeded pilot rows have no checkable eligibility criterion and need a
  source review;
- at least one row contains a conditional age exception that the current
  criteria schema cannot express precisely;
- state scope must be checked against the source. The pipeline now preserves
  only an explicitly extracted state code and does not use the prefilter's
  `--state-code` flag as evidence. Central or all-India rows remain `null`.

The source URL builder also canonicalizes duplicate suffixes and URL-encodes
the slug, so a filename such as `aaby copy` is not emitted as a malformed URL.

## Database validation

The enum-value compatibility migration was applied to SQLite before seeding.
The validation command passes with illustrative rows explicitly allowed:

```bash
DATABASE_URL=sqlite:////absolute/path/to/data/sahaayak.db \
  uv run python scripts/validate_benefits.py --allow-illustrative
```

Normal production validation should continue to reject active illustrative
rows. The pilot rows remain inactive by design.

## Decision on embeddings and RAG

Dataset acquisition, extraction, prefiltering, and the guarded structured-data
pilot are now complete. Embeddings and a generic PDF RAG path were not added:
the product spec explicitly requires structured eligibility data and names
blind RAG over PDFs at conversation time as a non-goal. A vector index must not
be allowed to turn an arbitrary retrieved sentence into an eligibility claim.

The safe follow-up is a search-only evidence index over reviewed source
excerpts, used to help an operator or caller open the relevant source passage.
It can be added after 20–50 rows are human-reviewed, with the structured
matcher remaining the only eligibility decision path.

## Required next gate

Before expanding beyond the pilot, a reviewer should verify every numeric
limit, exclusion, document requirement, application URL, and state scope. Only
then should rows move to `human_verified` and become active. Rows with
ambiguous conditions should remain inactive as `needs_review`.
