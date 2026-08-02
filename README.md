# Sahaayak

Sahaayak is a local-language utility agent for discovering government schemes,
scholarships, and a small curated set of jobs, then checking eligibility from
structured criteria instead of asking a model to guess from prose.

The current demo path is a browser conversation in Kannada, Hindi, or English.
It supports text immediately and microphone input when the optional OpenAI
Whisper and Sarvam Bulbul keys are configured.

## Current scope

The architecture is designed for five languages and five states. The working
demo catalog is intentionally narrower:

- Languages: Kannada (`kn`), Hindi (`hi`), and English (`en`)
- Active states in the catalog: Karnataka (`KA`) and Delhi (`DL`)
- Data: eight hand-entered illustrative benefits for local development
- Voice: OpenAI Whisper for speech-to-text, Sarvam Bulbul for speech output

The demo rows are not a claim of verified nationwide eligibility coverage. Run
the ingestion pipeline in `scripts/01_download_and_extract.py` through
`scripts/06_localize.py` before presenting sourced scheme data to callers.

## Repository map

| Path | Role |
| --- | --- |
| `apps/web` | Vite + React browser text/microphone demo |
| `packages/contracts` | Pydantic contracts for slots, eligibility, and API turns |
| `packages/common` | Settings, SQLModel tables, database, cache, and logging |
| `packages/api-types` | OpenAPI JSON and generated TypeScript types |
| `services/agent` | Language-agnostic LangGraph flow, matcher, prompts, and voice providers |
| `services/api` | FastAPI routes for catalog, turns, sessions, and escalation |
| `scripts` | Data ingestion, demo seed, localization, and type generation helpers |
| `tests` | Offline unit, dialogue, voice, and HTTP contract tests |
| `docs/spec-v2.md` | Product and architecture specification |
| `docs/continuation-spec.md` | Build status, acceptance criteria, and remaining work |
| `docs/implementation-roadmap.md` | Current required work, beta plan, and nice-to-have backlog by product/FE/BE/infra |

## Frontend architecture

The browser app is organized by feature rather than by one large component:

- Tailwind CSS v4 provides the design tokens and responsive utility styling;
  reusable shadcn-style primitives live under `apps/web/src/components/ui`.
- TanStack Router owns route composition and TanStack Query owns catalog,
  health, and conversation request state.
- Zustand persists only caller preferences and conversation state that belongs
  in the browser; Zod validates API payloads at the network boundary.
- `react-media-recorder` provides the microphone recording hook used by the
  voice flow. Audio replies use the browser audio element so playback stays
  lightweight and works with the API's optional TTS response.
- Motion provides reduced-motion-aware transitions for the hero, messages, and
  loading states.

Feature code is grouped under `apps/web/src/features`, shared hooks under
`apps/web/src/hooks`, and route composition under `apps/web/src/app`.

## Quick start: text demo

Prerequisites: Python 3.12 with `uv`, Node 20+ for the web app, and optionally
Docker for Postgres and Redis.

```bash
make setup
uv run python scripts/seed_demo.py --reset
```

In one terminal, start the API:

```bash
make api
```

In another terminal, start the browser demo:

```bash
make web
```

Open [http://localhost:5173](http://localhost:5173). Choose a language and
state, then try `I need a scholarship` or one of the suggested prompts. The
browser keeps a stable caller ID in `localStorage`, so the API remembers slots
between turns. The reset control deletes that caller's stored session.

No model keys are needed for text mode: the rule-based understanding path is
used when `OPENAI_API_KEY` is empty. `make setup` creates `.env` from
`.env.example`; leave the optional keys empty for an offline text demo.

## Voice mode

Add these to `.env`, then restart the API:

```dotenv
OPENAI_API_KEY=...
SARVAM_API_KEY=...
```

The web app records a browser microphone clip and sends it to
`POST /api/voice/turns`. The API uses the same agent graph as text mode and
returns text every time; when Sarvam is configured, it also returns playable
audio. TTS responses are cached so repeated canned questions do not spend a
new credit each time.

The health endpoint and the browser status line expose which optional pieces
are configured. Without `SARVAM_API_KEY`, text remains usable and the UI says
that voice output is unavailable.

## Useful commands

```bash
make test       # 101+ offline Python tests
make lint       # Ruff; mypy is advisory in the current scaffold
make check      # Python checks plus the web build when apps/web exists
make types      # regenerate packages/api-types from FastAPI OpenAPI
make seed       # load structured JSONL data into the database
make infra      # start Postgres and Redis with Docker Compose
make up         # start the complete Docker stack
make down       # stop the Docker stack
```

For a clean API type refresh after changing a FastAPI model:

```bash
make types
npm run typecheck --workspace @sahaayak/web
```

The API publishes Swagger at [http://localhost:8000/api/docs](http://localhost:8000/api/docs)
and its schema at [http://localhost:8000/api/openapi.json](http://localhost:8000/api/openapi.json).

## Data pipeline

The ingestion workflow is deliberately separate from the call-time agent:

```bash
make extract       # download PDFs and extract raw text
make prefilter     # narrow the corpus before spending LLM calls
make structure     # turn source text into EligibilityCriteria JSON
make spotcheck     # review structured rows against source text
make seed          # load reviewed rows
uv run python scripts/06_localize.py --languages kn hi
```

Pipeline outputs under `data/` are regenerable and ignored by Git. Do not
commit `.env`, SQLite databases, downloaded PDFs, or unreviewed structured
rows.

## Design boundaries

- Language, state, and domain are catalog/configuration values, not branches in
  the graph.
- Eligibility is evaluated by `services/agent/.../matcher.py` from structured
  JSON and explained through criterion outcomes.
- STT and TTS are separate provider interfaces; the graph only receives text
  and emits localized text.
- Missing facts produce another question; uncertainty or a caller request is
  recorded as a durable escalation ticket rather than turned into a guess.

Read the [initial product specification](docs/spec-v2.md) for the intended
architecture and the [continuation spec](docs/continuation-spec.md) for the
current build plan and acceptance checklist.
