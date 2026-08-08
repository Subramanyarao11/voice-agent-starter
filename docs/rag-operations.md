# Hosted RAG operations

This repository uses one OpenAI-hosted Vector Store as the durable knowledge
base for the extracted myScheme corpus and official government-job source
documents. Docker may run the API and web application, but the knowledge base
is not stored in a container volume.
OpenAI's [Retrieval guide](https://developers.openai.com/api/docs/guides/retrieval)
and [File Search guide](https://developers.openai.com/api/docs/guides/tools-file-search)
describe the managed chunking, embedding, indexing, and search primitives used
here.

## Current corpus

- Input: `data/structured/raw_text.jsonl`, produced by the existing extraction
  pass.
- Raw records: 2,876.
- Exact-content-unique documents: 2,066.
- UPSC recruitment source documents: 3 (synced as a separate dataset).
- Current remote total: 2,069 documents (2,066 myScheme + 3 UPSC).
- UTF-8 source payload: 19,753,394 bytes (about 19.8 MB).
- Remote store: configured in `OPENAI_VECTOR_STORE_ID`; the local development
  ID is written to the ignored `data/rag/vector-store-manifest.json`.
- Source status: raw machine extraction, not human-verified eligibility data.

The sync uploads normalized `.txt` files with source ID, canonical source URL,
content hash, dataset, and verification metadata. OpenAI performs the vector
indexing; the application does not maintain a local embedding database.

## Initial sync and resuming

Copy `.env.example` to `.env` and configure `OPENAI_API_KEY`. The persistent
ledger is shared with the rest of the OpenAI pipeline and refuses reservations
that would cross the configured `$10` ceiling.

```bash
uv run python scripts/07_sync_openai_vector_store.py --dry-run
uv run python scripts/07_sync_openai_vector_store.py
```

The script is manifest-driven and resumable:

1. It reads the selected dataset JSONL and deduplicates by normalized content hash.
2. It uploads only hashes absent from the manifest.
3. It attaches uploaded files to the same Vector Store in bounded batches.
4. It writes the manifest after each upload and completed batch.

If a process or container stops, rerun the same command. Do not delete the
manifest or create a new store unless a deliberate re-index is intended. The
ignored `data/rag/source_text/` directory and manifest are local operational
artifacts; deploy the remote ID as a secret/configuration value instead of
committing them.

## Query and API smoke test

Run a real, budget-guarded query after indexing:

```bash
uv run python scripts/08_query_rag.py \
  "What support is available for students from low income families?"
```

The API exposes the same behavior:

- `POST /api/rag/search` — returns bounded source excerpts, relevance scores,
  source IDs, and URLs.
- `POST /api/rag/answer` — returns a concise answer plus the retrieved sources.

The shared dialogue graph also routes informational intents such as “tell me
about this benefit” and “how do I apply?” through the same answer path. This
means `/api/voice/turns` and `/api/voice/stream` follow `audio → STT → intent →
hosted RAG → source-aware response → TTS` when the hosted store is configured.
RAG answers
are requested in the caller's language; citation markers are kept in
`grounded_answer` and source cards, while `response_text` removes `[Source N]`
markers before synthesis so they are not read aloud.

Both endpoints fail closed with `503` when the API key/store is unavailable or
the budget ledger cannot reserve the operation. Set
`OPENAI_VECTOR_STORE_ID` in deployment environments; the local manifest
fallback is intended for development only.

## Safety boundary

RAG is an evidence and discovery feature, not the eligibility engine. Retrieved
text is explicitly treated as untrusted document data. Answers must cite the
retrieved sources, acknowledge that the corpus is machine-extracted, and avoid
inventing dates, amounts, eligibility rules, or application steps. The
structured matcher remains the only path that can return a scheme eligibility
verdict, and unreviewed machine-structured rows remain inactive.

## Cost and storage controls

- Uploads and indexing batches reserve fixed amounts before each provider call.
- Search reserves `$0.01`; answer generation uses the configured model and
  token cap under the same ledger.
- Failed requests keep their reservation so a retry cannot silently exceed the
  cap.
- `OPENAI_RAG_MAX_SOURCE_BYTES` blocks an unexpectedly large future corpus
  before upload.
- The current source payload is well below the hosted storage guard. Review
  OpenAI's current [Vector Store pricing and limits](https://developers.openai.com/api/docs/guides/retrieval)
  before expanding the corpus materially.

## Verification checklist

```bash
uv run python -m pytest -q
uv run ruff check .
uv lock --check
git diff --check
```

The first full-corpus smoke test completed successfully and returned relevant
schemes with source URLs and `[Source N]` citations. It does not establish that
the source extraction or the schemes' eligibility rules are correct; human
review remains a release gate for structured eligibility.
