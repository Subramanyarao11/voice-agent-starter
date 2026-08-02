# Local-Language Voice Utility Agent — Technical Spec v2

BestPossible.AI Build Season 2026 · Build & submit window: Aug 1–10
**Idea:** [Local-Language Voice Utility Agents](https://bestpossible.ai/ideas/local-language-voice-utility-agents)
**Scope:** Schemes + Scholarships (myScheme data) as the production-quality core, Jobs as a lightweight curated add-on. Built extensible from day one to **5 languages × 5 states**, starting narrower and expanding without architecture changes.

---

## 1. Product Summary

A long-running voice agent that lets anyone — regardless of English literacy or typing comfort — discover and check eligibility for government schemes, scholarships, and jobs, by speaking in their own language over a phone call or app.

**Design principle:** language, state, and domain (schemes/scholarships/jobs) are all **configuration, not code**. Adding language #2 or state #2 should mean adding data and a config row, not rewriting the agent.

---

## 2. Stack (Python-first, matching your LangGraph course + FastAPI ecosystem)

| Layer | Choice | Why |
|---|---|---|
| Backend API | **FastAPI** | async-native, Pydantic-first, fast to build |
| Agent orchestration | **LangGraph (Python)** | mature docs, matches your course |
| Validation/typing | **Pydantic v2** everywhere — API schemas, agent state, DB models | one source of truth for shapes |
| DB | **PostgreSQL + SQLModel** | structured eligibility data, sessions, one schema definition |
| Cache/session state | **Redis** | active call/session state, fast lookups, cached TTS audio |
| STT | **OpenAI (Whisper / GPT-Realtime-Whisper)** | strong Indic language support, ample credits available |
| TTS | **Sarvam AI (Bulbul)** | native-quality Indic voice output — OpenAI's voices are English-centric, not worth the trust risk on vernacular output |
| LLM reasoning | **OpenAI (GPT-4/5 class)** | ample credits, used for agent reasoning nodes in LangGraph |
| Tracing | **Langfuse** | wraps every LangGraph node — shows judges a live reasoning trace, strong demo artifact |
| Logging | **structlog** | structured JSON logs across API |
| Deployment | **Docker + Railway/Render** | fast to deploy, no infra babysitting during the build window |
| Telephony (if pursued) | **Exotel** (India-focused) or browser-mic fallback demo | real phone line vs. lower-risk fallback — decide by day 4 |

No local model hosting, no GPU laptops — everything is a hosted API call, which keeps our infra genuinely simpler than a from-scratch ML pipeline.

---

## 3. Architecture

```
┌───────────────────────────────────────────────────────────┐
│                 User (phone call / browser demo)             │
└──────────────────────────────┬──────────────────────────────┘
                                │ voice
┌──────────────────────────────▼──────────────────────────────┐
│  Voice Provider Layer (abstracted interface)                   │
│  STTProvider  → OpenAIWhisperSTT (per-language config)          │
│  TTSProvider  → SarvamBulbulTTS  (per-language config)          │
│  (swap providers per-language later without touching the agent) │
└──────────────────────────────┬──────────────────────────────┘
                                │ text
┌──────────────────────────────▼──────────────────────────────┐
│  Agent Orchestration (LangGraph, Python)                       │
│  - Intent detection (scheme / scholarship / job / other)        │
│  - Slot-filling dialogue manager (language-agnostic)             │
│  - Eligibility reasoning node (queries structured DB)             │
│  - Response composer → localized text → TTS                        │
└──────┬───────────────────────────────────────────┬───────────┘
       │                                            │
┌──────▼─────────────────┐              ┌───────────▼───────────┐
│ Knowledge Base (Postgres) │              │ Session Memory            │
│ - schemes / scholarships /  │           │ - Postgres: user profile,   │
│   jobs, keyed by state +     │           │   history                    │
│   category + language          │         │ - Redis: active session,      │
│ - structured eligibility        │        │   cached TTS audio clips        │
└─────────────────────────────┘              └───────────────────────────┘
                                │
┌──────────────────────────────▼──────────────────────────────┐
│  Human Escalation Stub (queue/webhook to volunteer)              │
└───────────────────────────────────────────────────────────────┘
```

---

## 4. Data Model (multi-language, multi-state, multi-domain from day one)

```python
class Language(SQLModel, table=True):
    code: str  # "kn", "hi", "ta", "te", "mr"
    name: str
    stt_provider: str
    tts_provider: str
    tts_voice_id: str

class State(SQLModel, table=True):
    code: str  # "KA", "MH", "TN", ...
    name: str
    primary_language: str  # FK to Language.code

class Domain(str, Enum):
    SCHEME = "scheme"
    SCHOLARSHIP = "scholarship"
    JOB = "job"

class Benefit(SQLModel, table=True):
    id: str
    domain: Domain
    name: str
    state_code: str | None  # null = central/all-India
    category: str
    description: str
    eligibility_initial: dict  # structured JSON, see schema below
    eligibility_renewal: dict | None
    benefits_text: str
    documents_required: list[str]
    application_process: str
    source_url: str
    last_verified_date: date

class UserSession(SQLModel, table=True):
    id: str
    phone_or_session_id: str
    state_code: str
    language_code: str
    profile: dict  # collected slots: age, income, category, occupation, etc.
    open_tasks: list[dict]  # e.g. "submit income certificate"
    created_at: datetime
    last_contact_at: datetime
```

**Eligibility schema** (per Benefit, structured not free-text):
```json
{
  "age_min": 18, "age_max": 60,
  "max_annual_family_income_inr": 450000,
  "category": ["SC", "ST", "OBC", "EWS", "General"],
  "gender": null,
  "occupation": null,
  "education_level": ["UG", "PG"],
  "enrollment_mode": ["regular"],
  "exclusions": ["already receiving another scholarship"]
}
```

This one schema serves schemes, scholarships, and jobs (jobs just populate a narrower subset of fields — e.g. `education_level`, `location`, `experience_years`).

---

## 5. Extensibility: adding language/state/domain later

- **New language:** add a `Language` row + a voice-provider config (which STT/TTS to use for it) + translate the ~15-20 canned dialogue prompts (questions the agent asks). No agent logic changes — LangGraph nodes operate on structured slots, not raw language text.
- **New state:** add a `State` row + run the myScheme data pipeline filtered to that state's schemes. No code changes, just a new data ingestion run.
- **New domain (beyond schemes/scholarships/jobs):** as long as it fits the `Benefit` schema (something with eligibility + benefits + application process), it's a new `Domain` enum value and a data source — the agent's reasoning logic doesn't change.

**Starting scope for the submission (Aug 10):** 1-2 languages (Kannada + Hindi) × 1-2 states (Karnataka + one more) fully working end-to-end, with the schema/architecture demonstrably ready to scale to 5×5 — this is a stronger story than half-working across 5 languages.

---

## 6. Build Plan (Aug 1 – 10, ~9-10 days)

| Day | Focus |
|---|---|
| **1** | Repo scaffold (FastAPI + LangGraph + Postgres/SQLModel + Redis), download & filter myScheme data for state #1 |
| **2** | LLM-structure eligibility data into the schema above; spot-check ~20% for accuracy; load into Postgres |
| **3** | LangGraph agent: intent detection + slot-filling + eligibility-matching logic (text-only, no voice yet) |
| **4** | Voice provider layer: OpenAI Whisper (STT) + Sarvam Bulbul (TTS) behind the abstraction interface; decide telephony vs. browser-mic demo |
| **5** | Full voice loop working end-to-end in language #1 (Kannada); session memory (Postgres + Redis) |
| **6** | Add language #2 (Hindi) + state #2's data — proves the extensibility story; add Langfuse tracing |
| **7** | Human escalation stub; curate small jobs dataset; polish conversation quality with native-speaker testing |
| **8** | Deploy (Docker → Railway/Render); write submission screencast script |
| **9** | Record screencast (BestPossible.AI wants to see *how* you built it, not just the result); buffer for fixes |
| **10** | Submit by Aug 10 — early submission is explicitly rewarded per their process |

---

## 7. What BestPossible.AI Says They're Judging (from the Build Season page) — map this to your build

- **Consistency** → daily Discord updates as you build, not a last-day sprint
- **A working app** → deployed, real backend, works on phone/laptop — this is why Railway/Render deploy on day 8 matters, don't leave it to the last hour
- **Originality** → the multi-language/multi-state extensible architecture *is* your originality angle — most hackathon voice bots are single-language demos
- **Your workflow** → the Langfuse trace + screencast of your actual building process is your best asset here
- **Seriousness** → real government data (myScheme), structured eligibility (not guesswork RAG), honest scoping (jobs as phase-1) — all signal this

---

## 8. Risks & Honest Caveats

- **Sarvam credits are limited (71.55 remaining)** — cache repeated TTS phrases (questions, common responses) in Redis/blob storage instead of regenerating; reserve live synthesis budget for the actual demo/testing, not every dev iteration
- **OpenAI TTS is not a drop-in replacement for vernacular output** — keep it out of the TTS path; it's fine for STT and reasoning where English-language-model quality doesn't matter as much
- **Eligibility parsing accuracy** — spot-check, don't blind-trust the LLM structuring pass
- **Telephony vs. browser demo** — decide by day 4, don't let it eat into days 6-8
- **5×5 language/state claim** — don't overclaim live coverage; claim the *architecture* supports it and show 2×2 working, with the data pipeline demonstrably repeatable
