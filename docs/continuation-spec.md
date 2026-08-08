# Sahaayak — Continuation Spec (post-scaffold)

**Product:** Local-Language Voice Utility Agent  
**Codename / package namespace:** `sahaayak`  
**Parent product spec:** [`docs/spec-v2.md`](./spec-v2.md)  
**Repo layout model:** [daastaanAI monorepo](https://github.com/Subramanyarao11/daastaanAI)  
**Audience for this doc:** you (human reviewer) + any later agent session picking up the work  
**Status of this doc:** written against git `main` after commit `217aca8` (test suite). Uncommitted stubs for npm/api-types may exist; see §3.1.

> **2026-08-02 status note:** WP-0 and WP-1 are now complete, including the
> generated API types and the refactored browser demo. Use
> [`implementation-roadmap.md`](./implementation-roadmap.md) for the current
> required-vs-nice-to-have plan; this continuation spec remains useful as the
> historical scaffold checklist.

> **2026-08-09 status note:** The working tree now includes benefit governance,
> application tasks, criterion evidence, runtime rollout enforcement,
> deployment/provider operations, streaming transcript review, source-attested
> department routing, and an audited language release gate. Prompt bundles and
> provider smoke checks now cover all ten Indian-language locales plus English;
> the eight new bundles remain machine-assisted drafts and the expansion
> languages remain intentionally inactive until native-speaker evidence,
> localized content, and admin approval are supplied.

---

## 0. How to use this document

1. Read §1–§2 to confirm the *current* baseline is what you think it is.
2. Walk §3 (verification checklist) on your machine — tick what actually works.
3. Treat §4–§8 as the remaining build plan. Do not start Day-plan items that fail the prerequisites listed under them.
4. Prefer small commits (as already practiced). Do not commit `.env`, `data/*.db`, PDFs, or `data/structured/*` pipeline outputs.

This file does **not** replace `spec-v2.md`. It freezes *where we are* and *what is left*, with acceptance criteria you can verify.

---

## 1. Product intent (unchanged from v2)

A long-running voice agent that lets callers discover / check eligibility for government **schemes**, **scholarships**, and (lightweight) **jobs** by speaking in their own language.

**Non-negotiable design rules (already encoded in code):**

| Rule | Implementation location |
|---|---|
| Language / state / domain are configuration, not code branches | `Language` / `State` / `Domain` rows + prompt catalogs |
| Final eligibility is structured JSON; source-grounded RAG is evidence only | `EligibilityCriteria` + `matcher.py` + `routers/rag.py` |
| Agent graph is language-agnostic | slots in → reasoning → localized prompts out |
| STT ≠ TTS provider (OpenAI Whisper in, Sarvam Bulbul out) | `services/agent/.../voice/` |
| Cache TTS aggressively (Sarvam credits are limited) | `VoiceService.speak` + Redis/memory cache |
| Escalate instead of guessing | `nodes/escalate.py` + `EscalationTicket` |

**Submission scope target (from v2):** 1–2 languages (Kannada + Hindi) × 1–2 states (Karnataka + one more) working end-to-end, with architecture demonstrably ready for 5×5. Do **not** claim live 5×5 coverage.

---

## 2. What is already done

### 2.1 Git history (baseline commits)

| Commit | What it established |
|---|---|
| `5df9cc5` | Original flat starter (FastAPI stubs + myScheme scripts) |
| `353b1b9` | uv workspace root, Makefile, Compose, shared Dockerfile, `.env.example` |
| `4dbad41` | `packages/contracts` — slots, eligibility, agent/voice contracts |
| `b5189c4` | `packages/common` — settings, models, DB, cache, logging, IDs |
| `6d6e08a` | `services/agent` — graph, matcher, understanding, voice, prompts |
| `3357a8a` | `services/api` — FastAPI surface; removed flat `app/` |
| `aec86b4` | Pipeline scripts ported + demo seed / localize / prewarm |
| `217aca8` | Test suite (~101 tests) |

### 2.2 Monorepo layout (current)

```
sahaayak/
├── apps/                    # NOT CREATED YET (browser demo pending)
├── packages/
│   ├── contracts/           # DONE — sahaayak_contracts
│   ├── common/              # DONE — sahaayak_common
│   └── api-types/           # PARTIAL — package.json only (no generated OpenAPI/TS yet)
├── services/
│   ├── agent/               # DONE — LangGraph + matcher + voice
│   └── api/                 # DONE — FastAPI entrypoint
├── scripts/                 # DONE — pipeline 01–06 + ops helpers
├── tests/                   # DONE — pytest suite
├── infra/python/Dockerfile  # DONE — shared image
├── docs/
│   ├── spec-v2.md           # original product/architecture spec
│   └── continuation-spec.md # THIS FILE
├── docker-compose.yml
├── Makefile
├── pyproject.toml           # uv workspace
├── package.json             # PARTIAL — npm workspaces stub (uncommitted when this was written)
├── .env.example
└── .python-version          # 3.12
```

### 2.3 Backend capabilities that exist today

**API (`sahaayak_api`, default `:8000`):**

| Method | Path | Purpose | Status |
|---|---|---|---|
| GET | `/health` | Liveness + capability flags | Working |
| GET | `/api/docs` | Swagger UI | Working |
| GET | `/api/openapi.json` | OpenAPI schema | Working |
| GET | `/api/languages` | Language catalog from DB | Working |
| GET | `/api/states` | State catalog from DB | Working |
| GET | `/api/coverage` | Benefit counts by domain/state | Working |
| POST | `/api/turns` | Text turn (`TurnRequest` → `TurnResponse`) | Working (text) |
| POST | `/api/voice/turns` | Audio turn (multipart) | Code present; returns **503** without keys |
| GET | `/api/sessions/{caller_id}` | Durable session / profile | Working |
| GET | `/api/sessions/{caller_id}/transcript` | Turn log | Working |
| DELETE | `/api/sessions/{caller_id}` | Reset session (demo / privacy) | Working |
| GET | `/api/escalations` | Open escalation tickets | Working |
| POST | `/api/escalations/{id}/resolve` | Resolve ticket | Working |

**Agent graph (LangGraph):**

```
understand → gather → (match → choose_followup)? → assess_escalation → compose
```

- Rule-first understanding (works offline with no `OPENAI_API_KEY`)
- Optional LLM understanding when key present
- Deterministic eligibility matcher with pass/fail/unknown outcomes
- Prompt catalogs: `en`, `hi`, `kn`
- Session memory: `UserSession.profile` + `conversation_state` (pending slot survives turns)
- Escalation tickets written on low confidence / no matches / caller request / repeated misunderstanding

**Voice layer (implemented, not fully exercised live):**

- `OpenAIWhisperSTT`
- Opt-in OpenAI Realtime PCM transcription with streamed transcript deltas
- Browser WebSocket PCM capture with local VAD, interruption, and a bounded
  MediaRecorder/WAV fallback
- Caller transcript review/edit before the reasoning graph runs
- `SarvamBulbulTTS` (chunk + merge WAV)
- Cache-first `VoiceService` (SHA-256 keys, Redis or in-memory)

**Data pipeline scripts (implemented, not yet run against full corpus in this session):**

| Script | Role |
|---|---|
| `01_download_and_extract.py` | HF PDFs → `raw_text.jsonl` |
| `02_prefilter.py` | Keyword narrow to candidates |
| `03_structure_with_llm.py` | LLM → `EligibilityCriteria` JSONL |
| `04_seed_db.py` | Load into `Benefit` table |
| `05_spotcheck.py` | Side-by-side QA helper |
| `06_localize.py` | Pre-translate `localized_summary` |
| `seed_demo.py` | Hand-entered illustrative benefits (dev only) |
| `prewarm_tts.py` | Cache canned phrases before demo |
| `generate_api_types.py` | OpenAPI → TypeScript types |

### 2.4 Explicitly *not* done yet

- `apps/web` browser-mic demo (Vite/React)
- Regenerated/committed `packages/api-types` OpenAPI + `.d.ts`
- README rewrite for the monorepo
- Real myScheme ingestion for Karnataka (or any state) into Postgres
- Live STT/TTS E2E with real keys (only unit/integration offline tests so far)
- Langfuse spans verified in a live project (decorator wired; needs keys + smoke)
- Jobs curated dataset beyond one demo row
- Native-speaker polish of `hi` / `kn` prompts
- Deploy (Railway/Render) + production env
- Telephony (Exotel) — **decision still open**; browser-mic is the default risk-reduction path
- Screencast / submission package

---

## 3. Verification checklist (do this before trusting the baseline)

Run these yourself. Mark PASS / FAIL.

### 3.1 Tooling

- [ ] Python **3.12** available (`uv python list` or `cat .python-version`)
- [ ] `uv --version` works
- [ ] Node **20+** available if you will build the web app
- [ ] Docker Desktop available if you want Postgres/Redis locally (optional for text-mode; required for production-like stack)
- [ ] Git identity set (already used for prior commits)

### 3.2 Install + tests

```bash
make setup          # uv sync --all-groups; creates .env from example if missing
make test           # expect ~101 passed
make lint           # ruff clean on packages/services/scripts/tests
```

- [ ] `make setup` succeeds
- [ ] `make test` → all green
- [ ] `make lint` → clean (or only known advisories)

### 3.3 Text API smoke (no API keys required)

```bash
cp .env.example .env   # if needed; leave OPENAI/SARVAM empty for offline text mode
uv run python scripts/seed_demo.py
make api               # uvicorn on :8000
```

Then:

- [ ] `GET http://localhost:8000/health` → `status: ok`, languages include `kn`/`hi`/`en`
- [ ] `GET /api/coverage` → `total > 0` after demo seed
- [ ] `POST /api/turns` with body:

```json
{
  "caller_id": "+919999900001",
  "text": "I need a scholarship",
  "language_code": "en",
  "state_code": "KA"
}
```

→ response asks for age (`pending_slot: "age"`)

- [ ] Continue turns: `"22"` → `"2 lakh"` → `"regular degree college"` → `"SC"` → residency yes → eventually eligible matches for demo scholarships
- [ ] Same flow in `language_code: "kn"` and `"hi"` returns localized questions
- [ ] `GET /api/sessions/+919999900001` shows stored profile
- [ ] `DELETE /api/sessions/+919999900001` clears it

### 3.4 Optional infra smoke

```bash
make infra   # postgres + redis via Compose (needs Docker)
# set DATABASE_URL + REDIS_URL in .env to Compose values
make api
```

- [ ] Health shows `database: ok` and `cache: redis` (not memory)
- [ ] Session survives API process restart (Postgres)

### 3.5 Known intentional degradations

| Condition | Expected behaviour |
|---|---|
| No `OPENAI_API_KEY` | Rules-only understanding; text dialogue still works |
| No `SARVAM_API_KEY` | `/api/voice/turns` → 503; text path fine |
| No Redis | In-memory cache; TTS cache lost on restart |
| No Postgres / empty `DATABASE_URL` | SQLite at `data/sahaayak.db` |
| Demo benefits only | Do **not** present as sourced myScheme truth |

---

## 4. Remaining work packages (detailed)

Each package has: goal, prerequisites, concrete tasks, acceptance criteria, and suggested commit granularity.

---

### WP-0 — Close the scaffold gap (short, do first)

**Goal:** Leave no half-committed monorepo stubs; README matches reality.

**Tasks:**

1. Commit or complete:
   - root `package.json` (npm workspaces)
   - `packages/api-types/` (after generating types, or commit stub + generate later)
2. Rewrite root `README.md`:
   - product one-liner
   - monorepo layout table
   - `make setup` / `make api` / `make test` / pipeline commands
   - honesty about demo vs sourced data
3. Ensure `.gitignore` still excludes `.env`, `data/*.db`, PDF caches, `node_modules`, `dist`

**Acceptance:**

- [ ] `git status` clean for intentional scaffold files
- [ ] A new contributor can run text demo from README alone
- [ ] README links to `docs/spec-v2.md` + this continuation spec

**Suggested commits:** `docs: rewrite README for monorepo` · `chore: add npm workspace stubs`

---

### WP-1 — Browser-mic web demo (`apps/web`)

**Goal:** One composition UI that talks to the API — text first, then mic — proving laptop demo without telephony.

**Prerequisites:** WP-0 README not required; API from §3.3 must work.

**Stack (align with daastaanAI, keep thin):**

- Vite + React + TypeScript
- Workspace package `@sahaayak/web`
- Types from `@sahaayak/api-types` (generate via `make types`)
- Proxy `/api` → `http://localhost:8000` in Vite config

**UI requirements (functional, not marketing polish yet):**

1. Language picker fed from `GET /api/languages` (active only)
2. State picker fed from `GET /api/states` (active only)
3. Stable `caller_id` in `localStorage` (browser session identity)
4. Text chat panel calling `POST /api/turns`
5. Mic capture → `POST /api/voice/turns` (multipart: `audio`, `caller_id`, `language_code`, `state_code`, `speak`)
6. Play returned `audio_base64` when present; always show `response_text`
7. Show last turn’s slots / pending slot / escalation flag (debug strip OK for build season)
8. “Reset session” → `DELETE /api/sessions/{caller_id}`
9. Coverage badge from `GET /api/coverage` so demo does not overclaim empty DB

**Design constraints (from user frontend rules — apply when polishing):**

- One composition first viewport (not a dashboard)
- Brand name **Sahaayak** as hero-level signal
- Avoid purple-on-white / cream-serif-terracotta AI defaults
- Prefer text+voice utility aesthetic over generic SaaS cards

**Acceptance:**

- [ ] `npm run dev --workspace @sahaayak/web` serves on `:5173`
- [ ] Full text scholarship flow works from UI against demo seed
- [ ] With keys: mic → STT → agent → TTS playback works in Kannada
- [ ] Without TTS key: text still works; UI shows clear “voice unavailable”
- [ ] `make types` regenerates TS types that compile

**Suggested commits:** scaffold Vite app → wire text chat → wire mic → polish

**Decision to lock here:** **Browser-mic is the Day-4/5 demo path.** Telephony (Exotel) stays optional stretch (WP-7).

---

### WP-2 — Real myScheme data for state #1 (Karnataka)

**Goal:** Replace demo fiction with sourced, spot-checked structured benefits.

**Prerequisites:** `OPENAI_API_KEY` with budget for structuring (`gpt-4o` recommended for step 03).

**Tasks:**

1. `make extract` — download + OCR/extract (the corpus currently contains
   2,876 PDFs; slow, disk-heavy)
2. Prefilter narrow for first cut:

   ```bash
   uv run python scripts/02_prefilter.py --state Karnataka --category education welfare
   ```

   Target ballpark: **80–150 candidates**, not all 2,876.

3. Structure (start limited, then resume):

   ```bash
   uv run python scripts/03_structure_with_llm.py --state-code KA --limit 20
   # review failures, then:
   uv run python scripts/03_structure_with_llm.py --state-code KA --resume
   ```

4. Spot-check **≥20%** of structured rows:

   ```bash
   uv run python scripts/05_spotcheck.py --n 20 --seed 42
   ```

   Checklist per row (from v2 + script docstring):
   - [ ] Every number (age, income) appears in source text
   - [ ] Categories not invented
   - [ ] `state_code` correct (or null if genuinely central)
   - [ ] Exclusions not dropped

5. Fix bad rows by hand in `benefits.jsonl` or re-structure those IDs
6. Seed: `make seed` / `uv run python scripts/04_seed_db.py`
7. Localize summaries: `uv run python scripts/06_localize.py --languages kn hi`
8. Re-run dialogue tests + a manual Kannada/Hindi scholarship conversation against real rows

**Current data pass (2026-08-02):** all 2,876 PDFs were extracted; the
Karnataka education/welfare filter produced 317 matches, reduced to 220 unique
candidate documents after exact-content deduplication, and a guarded 20-row
`gpt-4o` structuring pilot completed with zero failed calls. The pilot rows are
`machine_reviewed` or `needs_review` and inactive pending human review. The
automated review stores field-level evidence in `automated_review`; it does not
set `verified_by`, `verified_at`, or `is_active`. See
[`docs/data-review-2026-08-02.md`](data-review-2026-08-02.md).

**Hosted RAG addendum (2026-08-02):** the complete extracted corpus is also
available through a persistent OpenAI Vector Store for source discovery and
grounded explanations. Informational turns in both text and voice now use this
path when configured; the voice response is rendered in the caller's language
and source markers are returned separately for clients. This evidence path is
independent of the Karnataka structured-data pilot and must not be used as the
final eligibility authority. See [`docs/rag-operations.md`](rag-operations.md).

**Do not commit:** `data/raw_pdfs*`, `data/structured/*.jsonl` (large / regenerable). Commit only pipeline code + a short `docs/data-notes.md` with counts, date, and spot-check summary if useful for submission narrative.

**Acceptance:**

- [ ] Postgres/SQLite `Benefit` count for scholarships/schemes ≫ demo’s 6
- [ ] Spot-check log exists (even a markdown note) with % reviewed and known failure modes
- [ ] Agent returns real scheme names with plausible eligibility reasons
- [ ] Unconstrained rows (no checkable criteria) investigated or deactivated

**Suggested commits:** data-notes only; no binary dumps

---

### WP-3 — Live voice loop (language #1: Kannada)

**Goal:** End-to-end audio conversation in Kannada with cached TTS.

**Prerequisites:** WP-1 UI (or curl/multipart), `OPENAI_API_KEY`, `SARVAM_API_KEY`, Redis preferred.

**Tasks:**

1. Fill `.env` keys; confirm `/health` shows `speech_to_text: true`, `text_to_speech: true`
2. Dry-run credit estimate: `uv run python scripts/prewarm_tts.py --languages kn --dry-run`
3. Prewarm canned phrases: `uv run python scripts/prewarm_tts.py --languages kn`
4. Manual mic tests (quiet room):
   - greeting / ask intent
   - age / income / category answers in Kannada and code-switched Kannada-English
   - eligibility result playback
5. Confirm TTS cache hits on second run of same canned questions (logs: `tts_cache_hit`)
6. Confirm long answers are not truncated (sentence chunking already in Sarvam client)
7. Optionally enable `OPENAI_REALTIME_STT_ENABLED=true` for a tightly bounded
   real-key staging test; the default remains batch Whisper for cost control.

**Acceptance:**

- [ ] One full scholarship conversation completed by voice in Kannada
- [ ] Canned questions show cache hits after prewarm
- [ ] Sarvam credit burn logged / estimated; no regen loops in dev
- [ ] Failure modes: STT empty → “didn’t understand” + re-ask pending slot
- [ ] Realtime transcript deltas, caller edits, and sentence-level audio are
      captured as repeatable browser evidence

**Suggested commits:** only code fixes found during live testing (e.g. Sarvam field quirks)

---

### WP-4 — Language #2 (Hindi) + optional state #2

**Goal:** Prove extensibility: same code, new data/config.

**Language #2 tasks:**

1. Prewarm Hindi TTS: `prewarm_tts.py --languages hi`
2. Native-speaker review of `services/agent/.../prompts/hi.py` (and kn in same pass)
3. Live Hindi voice conversation (scholarship)
4. Confirm adding language did **not** require graph changes

**State #2 tasks (pick one with a primary language you can serve):**

| Candidate | Code | Primary language | Notes |
|---|---|---|---|
| Delhi | `DL` | Hindi | Reuses Hindi prompts; good for 2×2 story |
| Maharashtra | `MH` | Marathi | Needs Marathi prompt catalog first — heavier |
| Tamil Nadu | `TN` | Tamil | Needs Tamil prompts — heavier |

Recommended for submission: **Karnataka (kn) + Delhi or central schemes via Hindi**.

Pipeline for state #2:

```bash
uv run python scripts/02_prefilter.py --state <Name> --category education welfare
uv run python scripts/03_structure_with_llm.py --state-code <CODE> --resume
# spotcheck → seed → localize
```

**Acceptance:**

- [ ] Hindi E2E voice or text works without code forks
- [ ] Second state’s benefits appear in `/api/coverage` under that state code
- [ ] README/demo UI can switch language+state and get different candidate pools

---

### WP-5 — Langfuse tracing (demo artifact)

**Goal:** Judges can see a live reasoning trace for a turn.

**Prerequisites:** Langfuse project keys in `.env`.

**Tasks:**

1. Set `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`
2. Confirm `/health` `tracing: true`
3. Run a multi-turn conversation; verify spans for: `understand`, `gather`, `match`, `choose_followup`, `assess_escalation`, `compose`
4. Capture 1–2 screenshots / public trace URLs for screencast
5. Fix decorator/API drift if Langfuse SDK version differs (v2/v3 handled loosely in `tracing.py` — verify both)

**Acceptance:**

- [ ] One complete turn visible as nested spans in Langfuse UI
- [ ] Trace shows slots / match counts (via logs or span metadata — enrich if currently too bare)

**Stretch:** add structured input/output to spans (transcript, pending_slot, match verdicts) without logging PII beyond what submission allows.

---

### WP-6 — Escalation + jobs polish

**Goal:** Human handoff is real enough for demo; jobs exist as a thin curated add-on.

**Escalation tasks:**

1. Demo path: force “talk to a person” → ticket appears in `GET /api/escalations`
2. Optional admin-ish page in web OR document Swagger-only volunteer queue
3. Optional webhook stub (env `ESCALATION_WEBHOOK_URL`) — **not required** if DB queue is shown

**Jobs tasks:**

1. Curate a **small** set (10–30) of real/public job postings fitting `Benefit` + job-shaped eligibility fields
2. Prefer state-scoped (KA) + education/experience slots already in matcher
3. Seed via JSONL + `04_seed_db.py` or extend `seed_demo.py` carefully labeled
4. Ensure intent `FIND_JOB` path asks job-relevant minimum slots

**Acceptance:**

- [ ] Escalation ticket created + resolvable in API
- [ ] At least one jobs conversation reaches a match or honest no-match + escalate
- [ ] Jobs clearly framed as lightweight add-on in README/demo copy

---

### WP-7 — Deploy + submission package

**Goal:** Working public URL + evidence of build process.

**Deploy tasks:**

1. Choose Railway **or** Render (not both unless needed)
2. Provision Postgres + Redis
3. Set env vars from `.env.example`
4. Deploy API image from `infra/python/Dockerfile` (or platform buildpack + `uv`)
5. Deploy web static build with `WEB_BASE_URL` / API CORS updated
6. Smoke production: health, text turn, voice turn
7. Confirm CORS allows the deployed web origin only (tighten from localhost)

**Submission artifacts:**

1. Screencast script (how you built it, not only the result)
2. Record: architecture → data pipeline spot-check → Langfuse → Kannada voice → Hindi switch
3. Discord daily notes (consistency criterion)
4. Honest scope statement: 2×2 working, architecture for 5×5, jobs phase-1

**Acceptance:**

- [ ] Public URL returns `/health` ok
- [ ] Demo works without localhost
- [ ] Screencast ≤ preferred contest length (check BestPossible.AI rules when recording)
- [ ] Submit before Aug 10; earlier is better per v2

---

### WP-8 — Stretch / explicit non-goals for build window

**Do if time remains:**

- Exotel telephony webhook → same `/api/voice/turns`
- Streaming STT (GPT-Realtime-Whisper)
- Alembic migrations (replace `create_all`)
- Admin app (`apps/admin`) — **not required** for submission
- Full 5 languages of prompts (ta/te/mr modules)

**Do not do in this window:**

- Local model hosting / GPU
- OpenAI TTS for vernacular output
- Unbounded RAG as the final eligibility authority (source-grounded evidence retrieval is allowed)
- Claiming unverified eligibility accuracy

---

## 5. Recommended execution order (mapped to v2 days)

Assuming scaffold is “Day 1–3 largely done in code form”:

| Order | Package | Maps to v2 day | Depends on |
|---|---|---|---|
| 1 | WP-0 scaffold closeout | Day 1 cleanup | — |
| 2 | WP-1 web text UI | Day 4–5 demo path | API |
| 3 | WP-2 myScheme KA data | Day 1–2 (data) | OpenAI key |
| 4 | WP-3 Kannada voice E2E | Day 4–5 | Keys + Redis + WP-1 |
| 5 | WP-4 Hindi + optional state #2 | Day 6 | WP-2/3 |
| 6 | WP-5 Langfuse | Day 6 | Keys |
| 7 | WP-6 escalation + jobs | Day 7 | WP-2 |
| 8 | WP-7 deploy + screencast | Day 8–10 | Everything above |

**Parallelizable:** WP-2 data pipeline can run while WP-1 UI is built. WP-5 can be enabled early once keys exist.

---

## 6. Environment & secrets matrix

| Variable | Required for text demo | Required for voice | Required for pipeline | Notes |
|---|---|---|---|---|
| `DATABASE_URL` | No (SQLite) | Preferred Postgres | Preferred | Compose default in `.env.example` |
| `REDIS_URL` | No | Strongly preferred | No | TTS cache durability |
| `OPENAI_API_KEY` | No (rules mode) | Yes (STT) | Yes (03/06) | Also improves understanding |
| `SARVAM_API_KEY` | No | Yes | No | Credits scarce — prewarm |
| `LANGFUSE_*` | No | No | No | Demo artifact |
| `DEFAULT_LANGUAGE` | Default `kn` | — | — | |
| `DEFAULT_STATE` | Default `KA` | — | — | |
| `WEB_BASE_URL` | For CORS | — | — | Update on deploy |

Never commit populated `.env`.

---

## 7. Architecture quick reference (for reviewers)

```
Browser / phone
    │
    ▼
Voice layer (STT OpenAI · TTS Sarvam)     ← WP-3 live verification
    │ text
    ▼
LangGraph agent (services/agent)          ← DONE (text verified offline)
    ├─ understand (rules → optional LLM)
    ├─ gather minimum slots
    ├─ match (deterministic)
    ├─ choose next question
    ├─ escalate?
    └─ compose (prompt catalog)
    │
    ├─ Postgres: benefits, sessions, tickets
    └─ Redis: TTS cache, optional session hot state
```

**Key files to read before changing behaviour:**

| Concern | File |
|---|---|
| Eligibility math | `services/agent/src/sahaayak_agent/matcher.py` |
| Slot questions / order | `packages/contracts/src/sahaayak_contracts/slots.py` |
| Dialogue routing | `services/agent/src/sahaayak_agent/graph.py` |
| Session persistence | `services/agent/src/sahaayak_agent/runtime.py` |
| Phrases | `services/agent/src/sahaayak_agent/prompts/{en,hi,kn}.py` |
| HTTP surface | `services/api/src/sahaayak_api/routers/*.py` |
| Product rules | `docs/spec-v2.md` |

---

## 8. Quality bar (do not regress)

Before any “done” claim on a WP:

1. `make test` green  
2. `make lint` green  
3. Manual smoke of the path you changed  
4. No secrets / PDF dumps in git  
5. Prefer explaining eligibility (`CriterionOutcome`) over opaque LLM answers  
6. Prefer escalate over inventing eligibility  

---

## 9. Open decisions for you to confirm

Record your choices here when reviewing:

| # | Decision | Options | Recommendation | Your choice |
|---|---|---|---|---|
| D1 | Demo channel | Browser-mic vs Exotel | Browser-mic for Aug 10 | |
| D2 | State #2 | DL / MH / TN / TS / none | DL (Hindi reuse) | |
| D3 | Hosting | Railway vs Render | Whichever you already know | |
| D4 | Commit npm stubs now vs with web app | now / with WP-1 | With WP-1 is fine | |
| D5 | Ingest scope first cut | education+welfare only vs broader | education+welfare | |
| D6 | Jobs source | hand-curated CSV vs scrape | Hand-curated 10–30 | |

---

## 10. Immediate next actions (when you say “continue”)

In order:

1. You finish §3 verification checklist and fill §9 decisions.  
2. Agent/human implements **WP-0 + WP-1** (README + browser demo).  
3. In parallel or next: **WP-2** with your OpenAI key (real KA data).  
4. Then **WP-3** voice with Sarvam (prewarm first).  

If you want the next coding session to start without re-discovery, say:  
**“Continue from WP-0/WP-1 in continuation-spec.md”**.

---

## 11. Appendix — API contract sketches (for web implementers)

### POST `/api/turns`

Request:

```json
{
  "caller_id": "string",
  "text": "string",
  "language_code": "kn|hi|en|null",
  "state_code": "KA|null"
}
```

Response (fields used by UI):

```json
{
  "session_id": "ses_...",
  "transcript": "...",
  "response_text": "...",
  "intent": "find_scholarship",
  "slots": { "age": 22 },
  "pending_slot": "annual_family_income",
  "matches": [
    {
      "benefit_id": "...",
      "benefit_name": "...",
      "domain": "scholarship",
      "verdict": "eligible",
      "confidence": 1.0,
      "reasons": ["..."]
    }
  ],
  "needs_escalation": false,
  "escalation_reason": null,
  "audio_base64": null,
  "audio_mime_type": null
}
```

### POST `/api/voice/turns` (multipart)

Fields: `audio` (file), `caller_id`, `language_code`, `state_code`, `speak` (bool, default true).  
Same JSON response; `audio_base64` set when TTS succeeds.

---

## 12. Appendix — Make targets reference

| Target | Purpose |
|---|---|
| `make setup` | Install Python (+ npm if web exists), create `.env` |
| `make api` | Run API with reload |
| `make web` | Run Vite demo (after WP-1) |
| `make test` / `make lint` / `make check` | Quality gates |
| `make infra` / `make up` / `make down` | Docker services |
| `make extract` / `prefilter` / `structure` / `seed` / `spotcheck` | Pipeline |
| `make types` | Regenerate OpenAPI → TS |

---

*End of continuation spec. Parent truth for product/architecture remains `docs/spec-v2.md`.*
