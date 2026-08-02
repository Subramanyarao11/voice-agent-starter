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
agent understanding, transcription, and the hosted RAG sync/query path. The
RAG sync completed with 2,066 file uploads and 10 fixed-cost indexing attempts.
After the live retrieval/answer smoke tests, the ledger reports `$2.276385`
reserved, `$0.242533` observed, and 2,100 calls (one failed initial
batch-shape request is retained as a failed reservation). Vector-store
operations expose no token usage to this ledger, so the fixed reservations
remain intentionally conservative.

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

The complete already-extracted corpus is now indexed in one persistent
OpenAI-hosted Vector Store. The sync read `data/structured/raw_text.jsonl`
without downloading PDFs or running the paid structuring pass again. The 2,876
raw records collapsed to 2,066 exact-content-unique text documents with an
estimated UTF-8 upload size of 19,753,394 bytes. The local ignored manifest
stores the remote ID, content hashes, uploaded file IDs, and batch status;
deployments should set the remote ID explicitly as `OPENAI_VECTOR_STORE_ID`.

OpenAI manages the vector-store chunking, embeddings, and indexing. The
application exposes `/api/rag/search` for evidence retrieval and
`/api/rag/answer` for a concise answer grounded in bounded excerpts with source
citations. The answer prompt treats source text as untrusted data and labels
the corpus as raw machine extraction, not human-verified eligibility truth.
See [`docs/rag-operations.md`](rag-operations.md) for the sync, resume, test,
and deployment procedure.

This does not change the eligibility boundary: RAG can help discover and
explain source material, but the structured matcher and reviewed benefit rows
remain the only path that may produce an eligibility result. A retrieved
sentence must never be converted into an official eligibility claim.

## Required next gate

Before expanding beyond the pilot, a reviewer should verify every numeric
limit, exclusion, document requirement, application URL, and state scope. Only
then should rows move to `human_verified` and become active. Rows with
ambiguous conditions should remain inactive as `needs_review`.
