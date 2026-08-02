# Sahaayak — Product and Implementation Roadmap

**Status:** implementation-ready roadmap
**Baseline date:** 2026-08-02
**Baseline commit:** `3dcb844` (`refactor: modernize web frontend architecture`)
**Inputs:** [`spec-v2.md`](./spec-v2.md),
[`continuation-spec.md`](./continuation-spec.md), the current repository, and the
local demo database
**Purpose:** define what must be built next, what can wait, and what “done” means
at product, frontend, backend/AI, data, infrastructure, security, and QA levels.

> The Aug 10 submission date below comes from `spec-v2.md`. The contest page was
> unavailable while this roadmap was prepared, so verify the final submission
> rules and deadline in the contest portal before recording or submitting.

---

## 1. Executive recommendation

The scaffold and browser demo are no longer the main risk. The next risk is
trust: the app currently demonstrates the interaction well, but it does not yet
have enough sourced, reviewed data or a live, measured voice path to support the
product claim.

Build the next layer in this order:

1. **Verified data and provenance** — replace illustrative rows with a reviewed
   Karnataka schemes/scholarships set and expose source/verification metadata.
2. **Actionable results** — show why a benefit matched, caveats, required
   documents, application steps, source, and verification date.
3. **Live voice reliability** — complete and measure Kannada voice end to end,
   then Hindi, including permissions, retries, caching, and provider failures.
4. **Privacy and API safety** — protect session and operator endpoints, rate-limit
   paid voice operations, establish consent, deletion, and retention behavior.
5. **Production persistence and deployment** — Alembic migrations, managed
   Postgres/Redis, production health checks, CI, backups, and a public deployment.
6. **Observability and quality evidence** — verified Langfuse traces, service
   metrics, versioned agent evaluations, native-speaker review, browser E2E
   tests, and a rehearsed demo.

Do not spend the core window on telephony, streaming voice, a large admin suite,
or all five languages until those six outcomes are complete.

---

## 2. Current implementation truth

### 2.1 What is working now

| Area | Current state | Evidence |
| --- | --- | --- |
| Web | Responsive React/Vite conversation UI with language/state controls, text turns, microphone capture, reset, match cards, turn inspector, and capability-aware controls | `apps/web/src` |
| Frontend architecture | Tailwind v4, shadcn-style primitives, TanStack Router/Query, Zustand, Zod, Motion, and `react-media-recorder` are integrated | `apps/web/package.json` |
| API | Catalog, coverage, text turn, voice turn, sessions, transcripts, reset, and escalation endpoints exist | `services/api/.../routers` |
| Agent | Language-agnostic LangGraph flow, rule-first understanding, optional LLM understanding, deterministic matching, adaptive follow-up questions, and escalation | `services/agent` |
| Language | English, Hindi, and Kannada prompt catalogs are active; Marathi, Tamil, and Telugu reference rows are inactive | prompt modules + local DB |
| State | Karnataka and Delhi are active; Maharashtra, Tamil Nadu, and Telangana are inactive | local DB |
| Data | Eight hand-entered illustrative benefits: 2 schemes, 5 scholarships, and 1 job | local SQLite DB |
| Voice code | OpenAI transcription, Sarvam synthesis, WAV chunk merge, and Redis/in-memory TTS caching exist | `services/agent/.../voice` |
| Persistence | SQLite fallback and Postgres-compatible SQLModel tables for benefits, sessions, transcripts, and escalation tickets | `packages/common` |
| Types | OpenAPI and generated TypeScript declarations are committed and consumed by the web app | `packages/api-types` |
| Verification | Ruff passes, 101 Python tests pass, TypeScript builds, and the primary browser text flow has been smoke-tested | `make check` + browser smoke |

### 2.2 What is still demonstration-only or unverified

- The eight loaded benefits are explicitly illustrative, not a reviewed production
  corpus.
- Live OpenAI STT and Sarvam TTS have code and offline tests, but no committed
  evidence of a complete Kannada/Hindi real-key conversation.
- Langfuse is wired conditionally, but a live trace and PII-redaction policy have
  not been verified.
- The web match cards do not expose application steps, documents, caveats, source
  links, or verification freshness.
- Browser history is not rehydrated from the durable transcript after reload.
- Session/transcript/reset endpoints trust a caller ID supplied by the client;
  escalation endpoints have no operator authentication.
- There is no rate limit around paid STT/TTS/model calls.
- Tables are created with `create_all`; there is no migration history.
- Docker Compose is development-oriented (`--reload`, bind mounts) and there is
  no production deployment manifest or CI workflow.
- There are no frontend unit, accessibility, or Playwright E2E tests.
- There is no documented retention period for income, caste/category, disability,
  transcript, or escalation data.

### 2.3 Product definition of done

#### Submission-quality core

The submission core is done when a user can:

1. Select Kannada or Hindi and Karnataka or Delhi.
2. Complete a text and a voice scholarship conversation.
3. Receive one or more results backed by reviewed source data.
4. Understand why each result is eligible, not eligible, or still uncertain.
5. See the source, last verified date, documents, and application steps.
6. Ask for a person and create a visible escalation ticket.
7. Delete their session data.

The team must also be able to show a production URL, a successful trace, a data
spot-check record, and a repeatable test run.

#### Production-beta core

Production beta additionally requires authenticated session access, operator
authorization, migrations, rate limits, backups, retention/deletion jobs,
monitoring/alerts, provider-cost controls, accessibility checks, and an incident
runbook.

---

## 3. Priority and sizing model

| Priority | Meaning |
| --- | --- |
| P0 | Required before presenting the product as a credible end-to-end system |
| P1 | Required for a safe, useful beta; can follow the submission if time is tight |
| P2 | Differentiating nice-to-have after core reliability and trust are established |
| P3 | Explicitly deferred because it adds scope without resolving the main risk |

| Size | Solo implementation estimate, excluding external reviews |
| --- | --- |
| S | Up to half a day |
| M | Roughly half to one day |
| L | One to two days |
| XL | More than two days or dependent on an external provider/reviewer |

Estimates assume the current codebase and do not include waiting for API keys,
native speakers, platform provisioning, or contest approval.

### 3.1 Cross-layer ownership matrix

| Package | Product | Frontend | Backend/AI | Data | Infrastructure/operations |
| --- | --- | --- | --- | --- | --- |
| P0-1 verified data | Trust labels and scope | Verification/freshness badges | Detail and coverage contracts | Ingestion, provenance, review | Pipeline job and artifact policy |
| P0-2 actionable results | Explanation and next action | Result route/drawer | Criterion/detail responses | Source, documents, dates | Contract monitoring |
| P0-3 live voice | Voice journey and fallback | Recorder/playback states | STT/TTS errors and retries | Prompt review fixtures | Redis, quotas, latency/cost metrics |
| P0-4 privacy/security | Consent, delete, retention | Session and consent UX | Tokens, authorization, limits | Retention/anonymization | CORS, secrets, audit logs |
| P0-5 production deploy | Availability promise | Production API configuration | Readiness/startup behavior | Alembic revisions | Railway/Render, Postgres, Redis, backups |
| P0-6 observability | Reliability and cost targets | Client error context | Traces and metrics | Freshness alerts | Dashboards, uptime, runbook |
| P0-7 web quality | Accessible low-bandwidth flow | Tests, a11y, performance | Stable fixtures/errors | — | CI browser jobs |
| P0-8 launch evidence | Demo and language quality | Scripted demo path | Trace/cache evidence | Review report | Staging rehearsal |
| P0-9 agent evaluation | Trust thresholds | Failure messaging | Intent/slot evals and fallback | Versioned eval set | Eval report in CI |

---

## 4. P0 implementation packages

## P0-1 — Verified benefit data and provenance

**Outcome:** Sahaayak answers from a small, trustworthy corpus rather than a
larger unverified one.
**Size:** XL
**Depends on:** OpenAI key for structuring, source availability, human reviewer

### Product decisions

- Submission target: **20–50 human-reviewed schemes/scholarships**, primarily
  Karnataka plus central benefits. Quality is more important than raw count.
- Keep jobs explicitly labeled as a lightweight curated add-on.
- Never display “eligible” as an official determination. Use language such as
  “likely eligible based on your answers” and surface unverifiable caveats.
- Every displayed benefit must have a source URL and verification status.

### Data and pipeline work

1. Run extraction and prefiltering for Karnataka education/welfare benefits.
2. Structure a pilot of 20 candidates before running a larger batch.
3. Review every extracted numeric limit in the pilot and at least 20% of the
   larger batch against source text.
4. Mark rows as `human_verified`, `needs_review`, `stale`, or `illustrative`.
5. Deactivate rows with missing source links, contradictory criteria, empty
   criteria, or unclear state scope.
6. Record an import manifest containing:
   - source collection/date;
   - source document count;
   - candidate and accepted row counts;
   - structuring model and prompt version;
   - failures/retries;
   - reviewer and review sample;
   - known limitations.
7. Preserve source text hashes so a later ingestion can identify changed
   documents without reprocessing everything.

### Backend and schema work

Add these fields to `Benefit` through a migration:

```text
verification_status: illustrative | machine_structured | human_verified | stale
source_title: string
source_document_url: string
source_excerpt: string | null
source_content_hash: string | null
verified_by: string | null
verified_at: datetime | null
valid_from: date | null
valid_until: date | null
```

Add a `DataImportRun` table:

```text
id, source_name, state_code, started_at, completed_at,
model_name, prompt_version, input_count, accepted_count,
failed_count, review_sample_size, manifest_json
```

Update the seed pipeline to be idempotent by benefit ID and source hash. It must
not silently replace a human-verified row with a new machine-only extraction.

### API work

- Extend `GET /api/coverage` with `verified_total`, `illustrative_total`, and
  `last_data_update`.
- Add `GET /api/benefits/{benefit_id}` for complete benefit details.
- Return verification status and last verified date with every match.
- Add an internal validation command that exits non-zero when active rows have
  no source, invalid criteria, an expired date, or an unsupported state/domain.

### Frontend work

- Display a clear `Verified`, `Needs review`, or `Illustrative demo` badge.
- Show “Data last updated …” near coverage.
- Hide or visually separate illustrative rows in production mode.
- Show the source name and external source link on result details.
- Add a short disclaimer explaining that Sahaayak provides guidance, not an
  official eligibility decision.

### Tests and acceptance

- [ ] At least 20 reviewed benefits are active and non-illustrative.
- [ ] Every active production benefit has a source URL and verification date.
- [ ] At least 20% of structured rows have a recorded manual review.
- [ ] Re-running the same import produces no duplicate rows.
- [ ] A changed source creates a review requirement instead of silently
      overwriting a verified record.
- [ ] Coverage distinguishes verified and illustrative data.
- [ ] Unit tests cover import idempotency and verification-state transitions.

---

## P0-2 — Explainable, actionable benefit results

**Outcome:** a result tells the user what to do next, not only that a match was
found.
**Size:** L
**Depends on:** P0-1 source and verification fields

### Product flow

For each top result, show:

1. Verdict: likely eligible, not eligible, or more information needed.
2. Confidence and the facts used.
3. Passed, failed, and unresolved criteria separately.
4. Caveats the system cannot verify.
5. Benefit summary and value.
6. Required documents.
7. Application steps and official source.
8. Verification date.
9. Actions: save, copy/share link, or ask for human help.

### Contract and backend work

Replace the flattened `reasons: string[]` response with a backward-compatible
structured explanation:

```json
{
  "criterion_outcomes": [
    {
      "slot": "annual_family_income",
      "status": "pass",
      "requirement": "Annual family income must be at most ₹4,50,000",
      "caller_value": "₹2,00,000"
    }
  ],
  "caveats": ["Must not receive another scholarship"],
  "verification_status": "human_verified",
  "last_verified_date": "2026-08-02"
}
```

Keep `reasons` for one release while the frontend moves to the new field. Add a
`BenefitDetailOut` response containing description, benefit text, documents,
application process, source, and dates.

### Frontend work

- Add a `/benefits/$benefitId` route or accessible result drawer.
- Make the top result prominent and keep lower-confidence results secondary.
- Use distinct sections for “Why it matches”, “What may still disqualify you”,
  “Documents”, and “How to apply”.
- Never encode verdict only through color; retain icon and text.
- Preserve the conversation while opening/closing details.
- Add print/copy support only after sensitive profile values are excluded from
  the shared payload.

### Tests and acceptance

- [ ] The top result exposes source, verification date, documents, and steps.
- [ ] Passed, failed, and unresolved outcomes render correctly.
- [ ] Caveats are never omitted from the detail view.
- [ ] Source links open safely with `rel="noopener noreferrer"`.
- [ ] A screen reader announces verdict and explanation in logical order.
- [ ] API contract tests and frontend component tests cover all verdict states.

---

## P0-3 — Live Kannada and Hindi voice reliability

**Outcome:** the clip-based voice loop works predictably in real conditions and
degrades to text without losing the answer.
**Size:** XL because provider verification is external
**Depends on:** OpenAI and Sarvam keys; Redis strongly recommended

### Frontend work

- Add explicit states for permission request, ready, recording, stopping,
  uploading, transcribing, answering, playback, and failure.
- Show recording duration and enforce the server limit before upload.
- Add cancel and retry controls.
- Explain how microphone audio is used before requesting permission.
- Preserve text mode when microphone permission is denied or STT is unavailable.
- Show a manual play control even when autoplay succeeds.
- Add a low-bandwidth error with an option to retry as text.
- Do not store audio blobs in Zustand/localStorage.

### Backend/provider work

- Validate supported MIME types and reject mislabeled uploads.
- Return a dedicated error code for empty transcription, provider timeout,
  unsupported language, and exhausted quota.
- Add bounded retries with jitter only for safe transient provider failures.
- Set separate connect/read/write timeouts and log provider latency.
- Pass request ID, provider, model, language, input bytes/characters, cache hit,
  and billed characters to metrics/traces without attaching raw audio.
- Prewarm Kannada and Hindi canned phrases and verify Redis cache hits.
- Add a response-size guard; large synthesized output should move to a
  binary/short-lived URL delivery path instead of unbounded base64 JSON.

### Conversation QA matrix

Test at minimum:

| Scenario | Kannada | Hindi | English/code-switch |
| --- | --- | --- | --- |
| Quiet-room intent | Required | Required | Required |
| Bare age and income answers | Required | Required | Required |
| Category and education | Required | Required | Required |
| Kannada/Hindi mixed with English numbers | Required | Required | Required |
| Permission denied | Required | Required | Required |
| Empty/noisy clip | Required | Required | Required |
| TTS unavailable after successful STT | Required | Required | Required |
| Cached repeat question | Required | Required | Required |

### Acceptance

- [ ] A full Kannada scholarship conversation completes by voice.
- [ ] A full Hindi conversation completes without graph or matcher forks.
- [ ] Second playback of canned prompts produces cache-hit evidence.
- [ ] Provider failure returns usable text or a clear retry path.
- [ ] Empty transcription re-asks the pending question rather than changing
      intent or advancing the conversation.
- [ ] P95 turn latency and per-turn provider cost are recorded for the demo run.
- [ ] Native speakers approve the core questions and top-result phrasing.

---

## P0-4 — Session privacy, authorization, and abuse controls

**Outcome:** one user cannot read/delete another user’s sensitive profile, and
paid endpoints cannot be abused anonymously.
**Size:** L for submission-safe minimum; XL for full beta
**Depends on:** a decision about browser identity and operator authentication

### Current risk

`caller_id` is client-controlled and is used directly to access sessions and
transcripts. Income, social category, disability, and conversation text are
sensitive. Operator escalation endpoints are also public. This must be treated
as a P0 production risk, not an admin polish item.

### Recommended browser session design

1. Add `POST /api/browser-sessions`.
2. The server creates an opaque random session ID and a separate access token.
3. Store only a hash of the access token in `UserSession`.
4. Return the token once and require it for session, transcript, turn, and delete
   operations.
5. Derive the browser session from the authenticated token; stop trusting a
   browser-supplied `caller_id` for authorization.
6. Prefer a secure, same-site, HTTP-only cookie when web/API deployment topology
   permits it; otherwise use a bearer token with a documented XSS tradeoff.
7. Telephony uses a separate trusted provider identity and verified webhook
   signature rather than browser tokens.

### Operator authorization

- Move escalation management under `/api/operator/*`.
- Require an operator role for list, claim, note, and resolve actions.
- Deny access by default and log every state transition.
- Do not return full caller profile unless the operator explicitly needs it.

### Consent, retention, and deletion

- Show a plain-language consent notice before the first sensitive question.
- Add `consent_at`, `retention_expires_at`, and `deleted_at`/anonymization policy.
- Define separate retention for active sessions, transcripts, escalation tickets,
  provider logs, and analytics.
- Make delete cascade or anonymize transcripts, tokens, open tasks, and escalation
  context consistently; add a test for this exact path.
- Redact transcripts, phone numbers, income, category, and disability from logs
  and third-party traces by default.

### Abuse and input controls

- Add per-IP and per-session limits for text turns; stricter limits for STT/TTS.
- Enforce maximum text length, audio duration/bytes, transcript limit, pagination
  limits, and concurrent provider calls.
- Tighten production CORS to exact configured origins; do not always allow
  localhost in production.
- Validate outbound source URLs and any future webhooks against an allowlist.
- Add secure headers and a Content Security Policy for the web app.

These controls directly address object-level authorization and unrestricted
resource-consumption risks described by the
[OWASP API Security Top 10](https://owasp.org/API-Security/editions/2023/en/0x11-t10/).

### Acceptance

- [ ] A session token cannot access another session by changing an ID.
- [ ] Anonymous callers cannot list or resolve escalation tickets.
- [ ] Voice rate limits prevent unbounded provider spending.
- [ ] Delete removes/anonymizes every configured data category.
- [ ] Production CORS contains no unconditional development origin.
- [ ] Logs and Langfuse traces contain no raw sensitive slot values by default.
- [ ] Security tests cover authorization, rate limits, oversized requests, and
      deletion cascades.

---

## P0-5 — Production database, migrations, and deployment

**Outcome:** a repeatable public deployment survives restarts and schema changes.

**Size:** L
**Depends on:** hosting decision and production secrets

### Database work

- Add Alembic and create an initial migration from the current SQLModel metadata.
- Replace production `create_all` with `alembic upgrade head` as a release step.
- Keep `create_all` only for isolated tests if useful.
- Add a CI check that the database is at migration head.
- Test migrations against Postgres, not only SQLite.
- Add connection retry/backoff during startup and configure pool sizing/timeouts.
- Define foreign-key deletion behavior explicitly for sessions, transcripts, and
  escalations.

[Alembic](https://alembic.sqlalchemy.org/en/latest/index.html) is the supported
migration tool for the SQLAlchemy stack already used here.

### Health and process work

- Split `/health/live` (process alive) from `/health/ready` (database reachable,
  required configuration valid).
- Keep optional STT/TTS/Langfuse capability flags informational.
- Read the platform-provided `PORT` value.
- Run Uvicorn without reload or source bind mounts.
- Add graceful shutdown and provider/client cleanup.
- Run the container as a non-root user and add a Docker health check.

### Recommended deployment topology

For the fastest spec-aligned path, use one Railway project:

```text
Public web service (Vite build served statically)
            |
            v
API service (infra/python/Dockerfile)
       |                    |
       v                    v
Managed Postgres       Managed Redis
       |
       +--> OpenAI / Sarvam / Langfuse over outbound TLS
```

Railway is the primary recommendation because its current official guidance
maps Compose applications to Dockerfile services and managed Postgres/Redis,
which closely matches this repository. See the
[Railway Compose deployment guide](https://docs.railway.com/guides/docker-compose)
and [health-check guide](https://docs.railway.com/deployments/healthchecks).
Render remains a valid fallback; its Docker deployment supports pre-deploy
migration commands and health checks.

### Environment and secrets

Create distinct local, staging, and production environments. At minimum:

| Variable/group | Local | Staging | Production |
| --- | --- | --- | --- |
| Database/Redis | SQLite or Compose | Managed | Managed + backups |
| Provider keys | Optional/dev | Restricted test key | Restricted prod key |
| CORS origin | localhost | staging web | production web only |
| Logs | human-readable | JSON | JSON + export |
| Langfuse | optional | enabled/redacted | enabled/redacted |
| Demo data | allowed/labeled | verified preferred | verified only |

Never expose provider keys to the Vite build. Configure spend limits and key
rotation in each provider account.

### Backups and recovery

- Enable daily Postgres backups before onboarding real users.
- Document restore steps and test one restore into staging.
- Treat Redis as reconstructable cache; Postgres remains the system of record.
- Do not rely on the container filesystem for SQLite, uploads, or generated
  artifacts in production.

### Acceptance

- [ ] A clean Postgres database reaches head via migrations and starts the API.
- [ ] Staging deploys from a clean checkout without manual shell edits.
- [ ] Readiness prevents traffic before migrations/database access are ready.
- [ ] Session state survives an API redeploy.
- [ ] TTS cache survives an API redeploy.
- [ ] Production web can call only the intended API origin.
- [ ] Backup and restore are documented and a staging restore is verified.

---

## P0-6 — Observability, cost, and operational evidence

**Outcome:** failures, latency, accuracy signals, and provider spend are visible
before a user reports them.
**Size:** M
**Depends on:** staging deployment and observability accounts

### Tracing

- Verify one real Langfuse trace containing graph-node spans for `understand`,
  `gather`, `match`, `choose_followup`, `assess_escalation`, and `compose`.
- Attach safe metadata: request ID, language, state, intent, slot names (not
  sensitive values), candidate count, verdict counts, latency, and provider.
- Add an explicit redaction layer before third-party trace export.
- Record trace links/screenshots for the build artifact.

### Service telemetry

Add OpenTelemetry-compatible traces and metrics for HTTP, database, Redis, and
provider boundaries. OpenTelemetry’s Python guidance supports application SDK
instrumentation and exporters; see the
[official instrumentation guide](https://opentelemetry.io/docs/languages/python/instrumentation/).

Minimum metrics:

```text
http_request_duration_seconds by route/status
turn_duration_seconds by text/voice/language
stt_duration_seconds and stt_error_total by provider
tts_duration_seconds, tts_error_total, tts_billed_characters_total
tts_cache_hit_total / tts_cache_miss_total
match_candidate_count and match_verdict_total
no_match_total and escalation_total by reason
active_session_total and turn_total
```

### Alerts and runbook

- Uptime alert: API unavailable or readiness failing.
- Error alert: voice/provider error rate over threshold.
- Cost alert: unexpected STT/TTS usage spike.
- Data alert: zero verified benefits or stale-data threshold crossed.
- Runbook: provider down, Redis down, database unavailable, bad deployment,
  key exhaustion, and accidental sensitive-data logging.

### Acceptance

- [ ] A text turn and voice turn can be followed by request ID across logs/traces.
- [ ] Dashboard shows latency, failures, cache hit rate, and escalation rate.
- [ ] Raw audio and sensitive slot values are absent from exported telemetry.
- [ ] At least one synthetic uptime monitor is active.
- [ ] A provider failure generates a useful alert without leaking credentials.

---

## P0-7 — Frontend quality, accessibility, and automated tests

**Outcome:** the primary flow is regression-tested, accessible, and performant
on low-end phones and unreliable networks.
**Size:** L
**Depends on:** stable result and session contracts

### Frontend architecture work

- Add a route-level error boundary and query error/retry states.
- Add lazy route imports for result/operator pages and split heavy vendor code;
  the current production build reports an approximately 835 KB main chunk.
- Self-host or system-fallback the fonts so the UI does not depend on Google
  Fonts during a demo or on constrained networks.
- Add query cancellation with `AbortSignal` when a route is left or a turn is
  explicitly cancelled.
- Hydrate transcript history from the server when a valid session resumes.
- Keep sensitive profile data out of persisted browser state.

### Accessibility and internationalization

- Target WCAG 2.2 AA for the primary text and voice flow, using the
  [W3C WCAG guidance](https://www.w3.org/WAI/standards-guidelines/wcag/).
- Verify keyboard-only operation, visible focus, 44px touch targets, contrast,
  reduced motion, live-region announcements, and screen-reader labels.
- Set the document language and script direction from the selected language.
- Test Kannada/Devanagari wrapping at 320px and 200% zoom.
- Do not put essential instructions only in placeholder text or audio.
- Add captions/transcript for every generated audio response.

### Test stack

- Vitest + React Testing Library for stores, hooks, validation, and components.
- MSW for API contract fixtures and error states.
- Playwright for text conversation, result detail, reset/delete, language switch,
  microphone-unavailable path, and responsive smoke.
- `axe` checks for critical route accessibility.

### Acceptance

- [ ] Required routes have error and loading states.
- [ ] Text flow, result detail, language switch, and delete pass in Playwright.
- [ ] Component tests cover every verdict and recorder state.
- [ ] No critical automated accessibility violations on the primary route.
- [ ] The primary flow is usable at 320px and keyboard-only.
- [ ] Production bundle is split or the size is justified with measured loading
      performance on a throttled mobile profile.

---

## P0-8 — Native-language QA and submission evidence

**Outcome:** the product claim is demonstrated honestly and repeatably.
**Size:** M plus external reviewer time
**Depends on:** P0-1 through P0-7 and P0-9 submission subset

### Language review

- Have Kannada and Hindi speakers review all canned prompts, verdict wording,
  caveats, and application instructions.
- Test respectful phrasing for caste/category, disability, gender, income, and
  failed eligibility.
- Record corrections in a review note with reviewer/date and affected prompt
  keys; do not rely on verbal approval only.

### Demo script

Record a deterministic demo path:

1. Show verified coverage and source freshness.
2. Complete a Kannada voice scholarship conversation.
3. Open the top result and show reasons, caveats, documents, source, and steps.
4. Switch to Hindi without changing graph code.
5. Ask for a person and show the escalation ticket.
6. Show Langfuse trace and TTS cache evidence.
7. Explain the honest scope: verified subset now, architecture for 5×5 later.

### Acceptance

- [ ] Native-language review note is committed without reviewer PII.
- [ ] Demo path passes twice on staging before recording.
- [ ] No illustrative benefit appears as verified during the recording.
- [ ] A fallback text-only demo is prepared in case provider audio fails.
- [ ] Final submission rules and deadline are confirmed on the contest portal.

---

## P0-9 — Agent understanding evaluation and guardrails

**Outcome:** multilingual understanding quality is measured, versioned, and
safe to fall back when the model is unavailable or uncertain.
**Size:** M
**Depends on:** final prompt wording and supported launch languages

### Evaluation dataset

Create a versioned, synthetic/redacted evaluation set with expected intent and
slots for:

- English, Kannada, and Hindi;
- code-switched utterances and English numerals inside Indic speech;
- volunteered multi-slot answers;
- bare answers to pending questions;
- negation, corrections, and changed answers;
- ambiguous amounts and out-of-range ages;
- greetings, unrelated requests, and explicit human requests;
- prompt-injection-like text that must remain caller content, not instructions;
- noisy/empty transcription artifacts.

Keep separate development and holdout sets. Do not copy real caller transcripts
into the repository without explicit consent and redaction.

### Backend/AI work

- Run the same evaluation against rules-only and LLM-enabled understanding.
- Measure intent accuracy, slot precision/recall, false slot rate, pending-answer
  accuracy, correction handling, and escalation behavior.
- Favor precision over recall for sensitive slots: a missing fact can be asked
  again; an invented income/category can produce a wrong eligibility verdict.
- Version the understanding prompt, model, evaluation set, and report together.
- Validate every model response through Pydantic and reject unknown slots/values.
- On model timeout, invalid output, or low confidence, fall back to rules or ask
  a clarifying question; never bypass deterministic eligibility matching.
- Add cost and latency to the report so a more accurate prompt is not accepted
  without understanding its call-time impact.

### Recommended launch thresholds

Set final thresholds after reviewing the dataset, with these starting targets:

```text
intent accuracy >= 90%
slot precision >= 95%
pending-answer accuracy >= 95%
invented sensitive slots = 0 on holdout set
explicit human request escalation = 100%
invalid model output causing a 5xx response = 0
```

### Acceptance

- [ ] A committed eval command produces a machine-readable and Markdown report.
- [ ] Rules-only and LLM-enabled results are reported separately.
- [ ] Holdout thresholds pass for Kannada, Hindi, and English launch flows.
- [ ] Every failed case is classified as data, prompt, parser, model, or expected
      ambiguity rather than patched as a one-off phrase.
- [ ] LLM failures degrade to clarification/rules without a server error.
- [ ] Final eligibility remains deterministic and explainable.

---

## 5. P1 beta packages

## P1-1 — Human escalation operator console

**Outcome:** escalation becomes a usable workflow instead of a database queue.
**Size:** L

### Implementation

- Add an authenticated `/operator/escalations` web route.
- Extend ticket states to `open`, `claimed`, `waiting_for_caller`, `resolved`, and
  `closed_unreachable`.
- Add `assignee_id`, `claimed_at`, `due_at`, `resolution_note`, and an immutable
  status event log.
- Add claim, release, note, and resolve APIs with optimistic concurrency.
- Filter by language, state, domain, reason, creation time, and SLA breach.
- Notify an operator through one configured webhook/email channel using an
  outbox/retry table; the database remains the source of truth.
- Minimize displayed sensitive context and audit every access.

### Acceptance

- [ ] Only operators can access the queue.
- [ ] Two operators cannot silently claim the same ticket.
- [ ] Notification failure does not lose the ticket.
- [ ] Every state change is auditable.

---

## P1-2 — Returning-user continuity and profile correction

**Outcome:** long-running assistance is visible and controllable by the user.
**Size:** L

### Implementation

- Hydrate transcript and matched benefits after authenticated session resume.
- Add a “What Sahaayak remembers” profile page.
- Allow correction/deletion of individual slots; invalidate affected matches.
- Ask for confirmation before reusing stale income, education, employment, or
  residence facts after a configured age.
- Implement `open_tasks`: document collection, application started, submitted,
  and follow-up due.
- Add saved benefits and an application checklist.

### Acceptance

- [ ] Reloading does not lose visible conversation history.
- [ ] Correcting income changes subsequent eligibility results.
- [ ] Stale facts are reconfirmed instead of silently reused.
- [ ] User can delete one fact or the entire session.

---

## P1-3 — Data review console and freshness automation

**Outcome:** new data can be reviewed, approved, and expired without editing
JSONL by hand.
**Size:** XL

### Implementation

- Build a reviewer-only queue comparing source excerpt and structured criteria.
- Support approve, reject, edit, request re-extraction, and deactivate actions.
- Highlight every numeric/category field and its source evidence.
- Schedule source freshness checks based on hash/date.
- Automatically mark expired job postings and expired schemes inactive.
- Add review sampling metrics and inter-reviewer disagreement tracking.
- Keep model/prompt lineage for every proposed revision.

### Acceptance

- [ ] No machine-structured revision becomes production-active without policy-
      compliant review.
- [ ] Reviewer edits are versioned and reversible.
- [ ] Stale/expired rows stop appearing in user results.

---

## P1-4 — CI/CD and release discipline

**Outcome:** every merge is buildable, testable, migratable, and deployable.
**Size:** M

### Implementation

- Add CI jobs for Ruff, mypy (initially non-blocking only if necessary), pytest,
  frontend typecheck/build/tests, OpenAPI drift, and Playwright smoke.
- Add a Postgres/Redis integration job.
- Fail when generated OpenAPI/types differ from committed files.
- Build the production container and run its readiness smoke.
- Run migration upgrade and downgrade/forward checks on a temporary database.
- Protect the production environment with manual approval and rollback notes.
- Generate a deployment summary with commit, migration revision, data revision,
  and smoke-test result.

### Acceptance

- [ ] A pull request cannot merge with failing required checks.
- [ ] Deployments identify both code and data versions.
- [ ] Previous application version can be restored without schema/data loss.

---

## P1-5 — Jobs as a real lightweight domain

**Outcome:** jobs stop being one illustrative row while remaining honestly
smaller than schemes/scholarships.
**Size:** L

### Implementation

- Curate 10–30 public job openings from authoritative sources.
- Add `published_at`, `application_deadline`, `employer`, `vacancy_count`, and
  `employment_type` to a job-specific detail payload or metadata field.
- Enforce automatic expiry and source verification.
- Tune minimum/follow-up slots for location, education, age, and experience.
- Add a jobs-specific result layout and deadline warning.

### Acceptance

- [ ] Every active job has a future deadline or explicit rolling status.
- [ ] Expired jobs never match.
- [ ] One job conversation reaches an explainable match and one honest no-match.

---

## P1-6 — Privacy-aware product analytics and feedback

**Outcome:** product decisions use behavior evidence without collecting sensitive
profile contents.
**Size:** M

### Events

Track only coarse events such as:

```text
session_started, language_selected, state_selected,
turn_completed, turn_failed, voice_permission_denied,
voice_turn_completed, result_opened, source_opened,
escalation_requested, session_deleted
```

Do not send transcript text, caller IDs, income, category, disability, or exact
profile values to analytics. Add a simple thumbs-up/down answer-quality control
with optional redacted feedback.

### Acceptance

- [ ] Analytics schema is reviewed for PII before enabling production export.
- [ ] Funnel reports show where users abandon the question flow.
- [ ] Users can opt out where required by the privacy policy.

---

## 6. P2 nice-to-have packages

## P2-1 — Telephony adapter

**Value:** reaches people without a smartphone/browser.
**Build after:** clip voice and operator handoff are stable.
**Size:** XL

### Implementation outline

- Add a provider-neutral `TelephonyProvider` interface.
- Implement Exotel inbound-call and media/status webhooks.
- Verify webhook signatures and replay protection.
- Map provider call ID to an authenticated Sahaayak session.
- Reuse the same `AgentRuntime`; telephony must not fork eligibility logic.
- Add DTMF fallback for language choice, yes/no, and repeat.
- Handle hang-up, silence, timeout, provider retry, and call recording consent.
- Track per-call duration/cost and delete provider recordings according to policy.

### Acceptance

- [ ] Inbound call completes the same scripted scholarship flow.
- [ ] Invalid/replayed webhook requests are rejected.
- [ ] Browser and phone produce equivalent structured results.

---

## P2-2 — Streaming voice and voice activity detection

**Value:** lower perceived latency and hands-free turn endings.
**Build after:** recorded-clip metrics show latency is the main usability problem.

**Size:** XL

### Implementation outline

- Evaluate browser VAD only after measuring false-stop behavior on noisy/mobile
  environments; retain a manual stop control.
- Move audio exchange to WebSocket/WebRTC with a short-lived authenticated token.
- Stream partial transcription but commit a turn only on final transcript.
- Start TTS at safe sentence boundaries after the deterministic result is final.
- Add interruption/barge-in handling and cancellation propagation.
- Maintain a clip-upload fallback for unsupported networks/browsers.

### Acceptance

- [ ] Median perceived response time improves materially over clip mode.
- [ ] False turn endings remain within an agreed threshold across test devices.
- [ ] Disconnects do not create duplicate turns or provider charges.

---

## P2-3 — Installable low-bandwidth PWA

**Value:** faster repeat access and better resilience on unstable connections.
**Size:** L

### Implementation outline

- Add a web manifest, service worker, icons, and install guidance.
- Cache the static shell and non-sensitive catalogs.
- Never cache authenticated API responses, transcripts, audio, or profile data by
  default.
- Detect offline state and preserve only an explicitly approved text draft.
- Retry idempotent catalog requests automatically; require confirmation before
  replaying a conversation turn.

### Acceptance

- [ ] App shell opens offline without exposing prior sensitive data.
- [ ] Reconnection does not submit duplicate turns.
- [ ] Cache policy is covered by automated tests.

---

## P2-4 — Reminders and document checklist

**Value:** moves from discovery to successful application completion.
**Size:** L

### Implementation outline

- Turn `open_tasks` into typed tasks with due date, status, source benefit, and
  reminder consent.
- Generate a checklist from required documents and application steps.
- Offer SMS/WhatsApp/email reminders only with explicit destination consent.
- Keep messages generic; do not include caste, income, disability, or detailed
  eligibility information.
- Add retry, opt-out, delivery status, and provider-cost limits.

### Acceptance

- [ ] User can create, complete, snooze, and delete tasks.
- [ ] No reminder is sent without consent.
- [ ] Messages contain no sensitive profile details.

---

## P2-5 — Safe sharing and assisted mode

**Value:** lets a caller involve family, a community worker, or a volunteer.
**Size:** M

### Implementation outline

- Generate a shareable benefit summary containing public benefit information
  only, never the user profile or verdict evidence.
- Add print/PDF and copy-link options using canonical benefit URLs.
- Add an assisted/kiosk mode with explicit consent, automatic session timeout,
  and prominent “clear this device” control.
- Support larger text and simplified language presets.

### Acceptance

- [ ] Shared content reveals no caller-specific data.
- [ ] Assisted sessions automatically clear on timeout/sign-out.

---

## P2-6 — Language/state expansion to 5×5

**Value:** fulfills the architecture’s scale story after the initial proof.
**Size:** XL per language/data combination

### Sequence per language/state

1. Add/activate language and state configuration.
2. Translate prompt catalog and have it reviewed by a native speaker.
3. Configure STT/TTS locale and voice.
4. Ingest and review state-specific data.
5. Add understanding fixtures for script, numbers, category, education, and
   common code-switch patterns.
6. Run the full text/voice/accessibility QA matrix.
7. Launch behind a feature flag and monitor no-match/escalation rates.

Do not activate a language merely because prompts compile; active means data,
voice, and review quality meet the launch bar.

---

## 7. Proposed target API and data model

### 7.1 User-facing endpoints

| Method | Path | Purpose | Priority |
| --- | --- | --- | --- |
| POST | `/api/browser-sessions` | Issue server-owned browser session/token | P0 |
| POST | `/api/turns` | Authenticated text turn | existing, harden P0 |
| POST | `/api/voice/turns` | Authenticated clip voice turn | existing, harden P0 |
| GET | `/api/me/session` | Current profile/conversation metadata | P1 |
| GET | `/api/me/transcript` | Current transcript with pagination | P1 |
| PATCH | `/api/me/profile` | Correct/delete selected slots | P1 |
| DELETE | `/api/me/session` | Delete/anonymize current session | P0 |
| GET | `/api/benefits/{id}` | Verified details and source | P0 |
| GET | `/api/coverage` | Verified/illustrative counts and freshness | existing, extend P0 |
| GET | `/health/live` | Process liveness | P0 |
| GET | `/health/ready` | Deployment readiness | P0 |

### 7.2 Operator endpoints

| Method | Path | Purpose | Priority |
| --- | --- | --- | --- |
| GET | `/api/operator/escalations` | Filtered queue | P1 |
| POST | `/api/operator/escalations/{id}/claim` | Atomic claim | P1 |
| POST | `/api/operator/escalations/{id}/notes` | Add audited note | P1 |
| POST | `/api/operator/escalations/{id}/resolve` | Resolve with outcome | P1 |
| GET | `/api/operator/data/reviews` | Pending data revisions | P1 |
| POST | `/api/operator/data/reviews/{id}/approve` | Publish reviewed revision | P1 |

### 7.3 Core schema additions

```text
Benefit
  + verification_status, source_title, source_document_url
  + source_excerpt, source_content_hash
  + verified_by, verified_at, valid_from, valid_until

DataImportRun (new)
  id, source_name, state_code, model_name, prompt_version
  counts, timestamps, manifest_json

UserSession
  + access_token_hash, consent_at, retention_expires_at
  + last_profile_confirmation_at

EscalationTicket
  + assignee_id, claimed_at, due_at, resolution_note

EscalationEvent (new)
  id, ticket_id, actor_id, event_type, metadata, created_at

OpenTask (P1, new)
  id, session_id, benefit_id, title, due_at, status, reminder_consent
```

Every schema change must be introduced through Alembic and reflected in
Pydantic contracts, OpenAPI, generated TypeScript types, Zod runtime schemas,
fixtures, and migration tests.

---

## 8. Test strategy and release gates

### 8.1 Test pyramid

| Layer | Required coverage |
| --- | --- |
| Pure unit | eligibility boundaries, parsing, ranking, prompt rendering, cache keys, redaction |
| Contract | every API response, error code, OpenAPI drift, generated TS/Zod compatibility |
| Component | result states, recorder states, consent, profile correction, operator queue |
| Integration | Postgres transactions/migrations, Redis cache, authorization, deletion cascade |
| Provider contract | recorded/mock OpenAI/Sarvam response shapes, timeout/error mapping |
| E2E | text flow, voice-degraded flow, result details, delete, operator escalation |
| Human QA | Kannada/Hindi voice, respectful wording, noisy audio, low-end Android browser |
| Non-functional | accessibility, bundle/load performance, rate limits, backup restore, basic load |

### 8.2 Required merge gate

```text
ruff -> mypy -> pytest -> migration check -> OpenAPI/type drift
     -> frontend typecheck -> frontend unit tests -> production build
     -> Playwright primary smoke -> container readiness smoke
```

### 8.3 Required release gate

- No active production benefit is illustrative or missing source metadata.
- Database is at migration head.
- Staging text and voice smoke pass.
- Error rate, latency, and provider quota are healthy.
- No high-severity dependency/security finding is unreviewed.
- Launch-language agent evaluation thresholds pass.
- Rollback and backup status are known.
- Native-language demo script passes.

---

## 9. Recommended execution sequence

### 9.1 Submission cut (derived from the Aug 10 date in the original spec)

| Day | Primary outcome | Parallel work |
| --- | --- | --- |
| 1 | Data pilot, review rubric, provenance schema | Alembic skeleton + session security design |
| 2 | 20+ reviewed benefits seeded | Benefit detail API/contract |
| 3 | Actionable result UI complete | Kannada voice provider smoke + TTS prewarm |
| 4 | Kannada voice E2E reliable | Hindi voice/language review |
| 5 | Staging deploy with Postgres/Redis/migrations | Langfuse + metrics + CI |
| 6 | Security minimum, Playwright, accessibility, native review | Agent eval + data/report cleanup |
| 7 | Full rehearsal and screencast | Fixes and fallback recording |
| 8 | Buffer and submit | No new features |

If time slips, cut P1/P2 work first. Do not cut source verification, honest
labels, deletion, or the fallback text path.

### 9.2 First beta after submission

1. Complete browser session authorization and operator authentication.
2. Finish retention/anonymization and rate limits.
3. Ship operator escalation console.
4. Add transcript hydration and profile correction.
5. Add data review/freshness console.
6. Harden CI/CD, backups, alerts, and Postgres/Redis integration tests.
7. Curate real jobs.

### 9.3 Expansion phase

1. Measure the beta funnel and abandonment reasons.
2. Add reminders/tasks if users reach results but do not apply.
3. Add telephony if browser access is the limiting factor.
4. Add streaming/VAD if clip latency is the limiting factor.
5. Expand languages/states one reviewed combination at a time.

---

## 10. Decision register

Resolve these before the associated package begins:

| ID | Decision | Recommendation | Needed by |
| --- | --- | --- | --- |
| D1 | Submission data count | 20–50 reviewed, not hundreds unreviewed | P0-1 |
| D2 | Result wording | “Likely eligible based on your answers” | P0-2 |
| D3 | Browser identity | Server-issued opaque token; HTTP-only cookie if topology permits | P0-4 |
| D4 | Operator identity | Managed auth with explicit operator role | P1-1 |
| D5 | Hosting | Railway primary; Render fallback | P0-5 |
| D6 | Web/API topology | Same parent domain if possible to simplify secure cookies/CORS | P0-4/P0-5 |
| D7 | Retention | Document periods per data category before beta | P0-4 |
| D8 | Telephony | Defer until browser voice is stable and measured | P2-1 |
| D9 | Streaming/VAD | Build only if measured clip latency justifies it | P2-2 |
| D10 | State #2 | Delhi to reuse Hindi; activate only with reviewed data | P0/P2 |

---

## 11. Explicit non-goals until the core is done

- Generic RAG over government PDFs at conversation time.
- An LLM making the final eligibility decision.
- Fully autonomous form submission or claims of official approval.
- Local GPU/model hosting.
- Five active languages with unreviewed prompts or no matching data.
- Nationwide coverage claims based on schema extensibility.
- Storing raw voice recordings by default.
- Building separate eligibility logic for browser, telephony, or each language.
- A large dashboard before the user result and escalation flows are reliable.

---

## 12. External implementation references

- [Alembic documentation](https://alembic.sqlalchemy.org/en/latest/index.html) —
  SQLAlchemy migration environment and revision workflow.
- [Railway Docker Compose deployment](https://docs.railway.com/guides/docker-compose)
  — mapping Dockerfile services to managed Postgres/Redis.
- [Railway health checks](https://docs.railway.com/deployments/healthchecks) —
  readiness behavior during deployments.
- [Render Docker deployment](https://render.com/docs/docker) — fallback platform
  with pre-deploy commands and health checks.
- [OpenTelemetry Python instrumentation](https://opentelemetry.io/docs/languages/python/instrumentation/)
  — traces, metrics, SDK initialization, and exporters.
- [OWASP API Security Top 10](https://owasp.org/API-Security/editions/2023/en/0x11-t10/)
  — object authorization, authentication, resource limits, and admin boundaries.
- [W3C WCAG 2 overview](https://www.w3.org/WAI/standards-guidelines/wcag/) —
  accessibility criteria for the web and voice/transcript experience.

---

## 13. Immediate next action

Start **P0-1 and the P0-5 Alembic skeleton in parallel**. P0-1 resolves the
largest product-trust gap; the migration skeleton prevents every subsequent
schema improvement from deepening the current `create_all` debt. Once the pilot
data shape is stable, implement P0-2, then complete P0-3 against the same verified
benefits.

The implementation session should begin with:

1. Add Alembic and an initial migration without changing runtime behavior.
2. Add benefit provenance/verification fields and `DataImportRun` migration.
3. Run the 20-row Karnataka ingestion pilot.
4. Review the pilot and publish a `docs/data-review-YYYY-MM-DD.md` report.
5. Extend benefit/match APIs and build the actionable result detail UI.
