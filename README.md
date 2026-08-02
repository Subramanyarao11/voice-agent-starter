# Local-Language Voice Utility Agent — Starter

BestPossible.AI Build Season 2026. See `spec-v2.md` for full product/architecture spec.
This is a working skeleton — routes, models, and the agent graph are wired together,
but several nodes are stubbed with `# TODO` markers where real logic goes.

## Setup

```bash
# 1. Start Postgres + Redis
docker compose up -d

# 2. Install deps (using uv, or swap for pip/poetry)
uv venv && source .venv/bin/activate
uv pip install -e .

# 3. Configure environment
cp .env.example .env
# fill in OPENAI_API_KEY, SARVAM_API_KEY, LANGFUSE_* keys

# 4. Run
uvicorn app.main:app --reload
```

Check `http://localhost:8000/health` — should return `{"status": "ok"}`.
Check `http://localhost:8000/docs` for the auto-generated FastAPI/Swagger UI —
useful for testing `/sessions/` and `/voice/turn/{session_id}` by hand before
wiring up real telephony or a browser mic.

## What's stubbed vs. what's wired

**Wired (structure works, ready to build on):**
- FastAPI app + routers + Postgres/Redis connections
- `Language` / `State` / `Benefit` / `UserSession` tables (SQLModel)
- LangGraph graph shape: `detect_intent → slot_filling → eligibility_match → compose_response`
- Voice provider abstraction (OpenAI STT, Sarvam TTS) with a cache-first `get_or_synthesize`

**Stubbed — this is the actual build work (`# TODO` in each file):**
- `app/agents/graph.py` — the 4 node functions are empty; this is your LangGraph/prompt-engineering work
- `app/services/voice.py` — `SarvamBulbulTTS.synthesize` response parsing needs confirming against current Sarvam API docs
- Data pipeline (not scaffolded here) — downloading myScheme, filtering to state #1, running the LLM eligibility-structuring pass into the `EligibilityCriteria` schema, loading into `Benefit` rows

## Data pipeline (scripts/)

The myScheme HF dataset (`shrijayan/gov_myscheme`) is actually **723 raw PDFs**,
not clean CSV/JSON as its own README claims — confirmed by browsing the repo
contents directly. There's also no structured "state" field; state applicability
just appears inside each scheme's text. So the pipeline is 4 steps:

```bash
# 1. Download all 723 PDFs and extract raw text
python scripts/01_download_and_extract.py

# 2. Cheap keyword pre-filter — narrow ~723 down to a candidate list BEFORE
#    spending LLM calls (adjust --state / --category to your first scope)
python scripts/02_prefilter.py --state Karnataka --category education welfare

# 3. LLM structuring pass — the accuracy-critical step. Turns each candidate's
#    free text into the EligibilityCriteria schema. Uses gpt-4o (not mini) —
#    this is worth the extra cost given it's the whole product's trust surface.
python scripts/03_structure_with_llm.py --state-code KA

# 4. Load structured schemes into the Benefit table
python scripts/04_seed_db.py

# 5. Spot-check N random rows against their source text side-by-side
python scripts/05_spotcheck.py --n 20
python scripts/05_spotcheck.py --id csss-cus   # or check one specific scheme
```

**Before trusting the output:** spot-check ~20% of `data/structured/benefits.jsonl`
against the original PDFs in `data/raw_pdfs_hf_cache/`. This is not optional —
it's the difference between a demo that gives correct eligibility answers and
one that quietly doesn't.

## Day 1 checklist

1. `docker compose up -d`, confirm app boots and `/health` responds
2. Run the 4-step data pipeline above for state #1 + 1-2 categories (start narrow — 80-150 schemes, not all 723)
3. Spot-check ~20% of the structured output against source PDFs
4. Fill in `detect_intent` and `slot_filling` in `app/agents/graph.py` — get a **text-only** conversation working via `/docs` before touching voice at all
5. Once text-only slot-filling + eligibility_match works end-to-end, move to Day 4 in the spec: wire real STT/TTS

## Repo layout

```
app/
├── main.py              # FastAPI app entrypoint
├── core/
│   ├── config.py        # env var settings
│   └── db.py            # Postgres engine/session
├── models/core.py        # SQLModel tables: Language, State, Benefit, UserSession
├── schemas/eligibility.py # EligibilityCriteria, EligibilityMatchResult
├── agents/graph.py        # LangGraph agent (STUBBED nodes)
├── services/voice.py       # STT/TTS provider abstraction
└── routers/
    ├── session.py         # create/resume a UserSession
    └── voice.py            # main turn endpoint: audio in -> agent -> response out
```
