# Sahaayak — Product and Implementation Roadmap

**Status:** implementation-ready roadmap
**Baseline date:** 2026-08-02
**Baseline commit:** `3dcb844` (`refactor: modernize web frontend architecture`)
**Inputs:** [`spec-v2.md`](./spec-v2.md),
[`continuation-spec.md`](./continuation-spec.md), the current repository, and the
local demo database
**Purpose:** define what must be built next, what can wait, and what “done” means
at product, frontend, backend/AI, data, infrastructure, security, and QA levels.

> **Implementation update (2026-08-02):** Server-owned anonymous browser
> sessions, Redis sliding-window limits, OIDC/MFA validation, redacted
> Langfuse/OpenTelemetry instrumentation, audited provider-policy expiry, and
> rollback are now implemented in the working tree. The remaining production
> evidence is a real managed-IdP/collector/Langfuse deployment smoke and full
> browser QA; static admin tokens are retained only as a local/test seam.

> The Aug 10 submission date below comes from `spec-v2.md`. The contest page was
> unavailable while this roadmap was prepared, so verify the final submission
> rules and deadline in the contest portal before recording or submitting.

> **Implementation update (2026-08-08):** The working tree now includes the
> real source-text ingestion path for UPSC, Karnataka KPSC, and an authorized
> NCS API adapter; persistent OpenAI-hosted RAG dataset selection; incorrect
> information reporting; benefit comparison; operator claims/notes/SLA/routing;
> browser streaming voice with VAD/interruption and clip fallback; consent-
> gated Infobip reminder delivery; and an expanded admin control center with
> messaging cost, data freshness, persisted evaluations, feature-flag rollout,
> audit export, provider/flag rollback, deployment/version comparison, and
> dry-run provider-failure simulations. Docker migration head is
> `20260808_0016`. The remaining gates are external: human publication review,
> authorized NCS credentials, real Infobip sender approvals/keys, live voice
> evidence, managed IdP production registration, telemetry collector/Langfuse
> verification, and full browser/accessibility QA.

> **Implementation update (2026-08-09):** The browser voice path now supports
> 24 kHz PCM worklet capture, bounded WebSocket frames, an opt-in OpenAI
> Realtime transcription bridge, streamed transcript deltas, and an explicit
> transcript review/edit step before the reasoning graph runs. Batch
> MediaRecorder/WAV fallback remains the default until a budgeted real-key voice
> test approves the realtime path.

> The same slice adds a source-attested department-directory import/review
> workflow. Runtime routing prefers approved fresh exact-pincode, prefix, or
> district entries and retains their source provenance on escalation tickets;
> no directory rows are bundled or activated without review.

> **Implementation update (2026-08-09, continued):** Benefit editing/version
> history/rollback, task and document tracking, criterion-level evidence,
> runtime language/state/provider/reminder flags, deployment comparison and
> provider-failure drills, transcript review/editing, streaming PCM capture,
> and the department-directory release gate are covered by code and tests.
> The eight expansion locales now have an audited native-review release gate
> and a read-only validation command; they remain inactive until complete
> prompt bundles, native-speaker evidence, voice/accessibility evidence, and an
> explicit admin activation are present.

> **Implementation update (2026-08-09, freshness):** Source freshness now has a
> dedicated scheduled worker in Docker. It persists the same deduplicated,
> admin-visible alerts as the manual scan, records aggregate worker telemetry,
> and never publishes or changes review-gated rows.

> **Implementation update (2026-08-09, operations):** OpenAI budget summaries
> now retain safe operation-level reservation/observed breakdowns, provider
> cards show voice activity by language, and deterministic evaluation runs
> persist bounded latency and per-language pass-rate rollups. Sarvam billing
> remains explicitly unreconciled until the provider exposes a usable usage
> contract.

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
7. **Inclusive citizen experience** — a UX4G/GIGW-informed visual system,
   predictable navigation, WCAG 2.2 AA behavior, and a reviewed localization
   pipeline that can expand from Kannada/Hindi to ten Indian languages.

The remaining work is now evidence and deployment hardening: human publication
review, real provider smoke tests, production identity/telemetry configuration,
and browser/accessibility QA. The streaming voice and operational admin
foundations are already implemented, so later work should focus on release
gates rather than recreating those boundaries.

### 1.1 Approved scope expansion beyond the initial spec

The initial spec describes an eventual five-language-by-five-state story. The
product target is now broader and more explicit:

- English remains the fallback interface language.
- Ten Indian-language interfaces are the expansion target: Hindi, Kannada,
  Tamil, Telugu, Marathi, Bengali, Gujarati, Malayalam, Punjabi, and Odia.
- Kannada and Hindi remain the launch-quality voice languages. A locale is not
  advertised as supported until its interface, content, understanding, voice,
  and accessibility QA pass the relevant release gate.
- Citizen browsing and benefit discovery remain usable without an account.
  Authentication is introduced when a user saves, synchronizes, or manages
  sensitive persistent information.
- The operator console grows into a role-protected admin control center for
  provider health/cost, data quality, traces, evaluations, audit history, and
  feature flags.
- Sarvam remains the preferred TTS provider for Indic speech where its quality
  is approved; OpenAI becomes a budget-aware fallback, with text always
  available as the final fallback.
- The visual language follows Indian public-service design conventions without
  using the State Emblem, a “Government of India” masthead, official seals, or
  language that implies government ownership or endorsement unless Sahaayak is
  formally authorized to do so.

---

## 2. Current implementation truth

### 2.1 What is working now

| Area | Current state | Evidence |
| --- | --- | --- |
| Web | Responsive React/Vite conversation UI with language/state controls, text turns, microphone capture, reset, match cards, turn inspector, and capability-aware controls | `apps/web/src` |
| Frontend architecture | Tailwind v4, shadcn-style primitives, TanStack Router/Query, Zustand, Zod, Motion, and `react-media-recorder` are integrated | `apps/web/package.json` |
| API | Catalog, coverage, text turn, voice turn, sessions, transcripts, reset, and escalation endpoints exist | `services/api/.../routers` |
| Agent | Language-agnostic LangGraph flow, rule-first understanding, optional LLM understanding, deterministic matching, adaptive follow-up questions, and escalation | `services/agent` |
| Language | All ten Indian-language prompt bundles plus English are installed; English, Hindi, and Kannada are active, while the eight expansion locales remain machine-assisted, review-gated, and inactive | prompt modules + language readiness review + voice smoke evidence |
| State | Karnataka and Delhi are active; Maharashtra, Tamil Nadu, and Telangana are inactive | local DB |
| Data | The source-backed myScheme pipeline remains the eligibility corpus; official UPSC and KPSC adapters produce inactive review-gated job rows, and an authorized NCS API adapter is ready | local DB + `scripts/ingest_*_jobs.py` |
| Voice code | OpenAI Whisper batch fallback, opt-in OpenAI Realtime PCM transcription, Sarvam Bulbul synthesis, sentence-level audio chunks, browser VAD/interruption, transcript review/editing, WAV clip fallback, and Redis/in-memory TTS caching exist | `services/agent/.../voice`, `services/api/.../routers/voice_stream.py`, `apps/web/src/hooks/use-streaming-voice.ts` |
| Persistence | SQLite fallback and Postgres-compatible SQLModel tables for benefits, sessions, transcripts, and escalation tickets | `packages/common` |
| Types | OpenAPI and generated TypeScript declarations are committed and consumed by the web app | `packages/api-types` |
| Verification | Ruff passes, 513 Python tests pass, the web production build passes, Docker migration head is `20260809_0018`, and the governance/voice/directory/language controls have offline tests | `make check` + Docker smoke |

### 2.2 What is still demonstration-only or unverified

- The eight loaded benefits are explicitly illustrative, not a reviewed production
  corpus.
- Live OpenAI STT and Sarvam TTS have code and offline tests, but no committed
  evidence of a complete Kannada/Hindi real-key conversation.
- Langfuse/OpenTelemetry export is wired conditionally with an explicit
  redaction layer; a real external collector/Langfuse trace still needs a
  deployment smoke and screenshot/evidence artifact.
- A dedicated `/benefits/$benefitId` detail route now exposes application steps,
  documents, caveats, source links, verification status, freshness, job metadata,
  and the latest match explanation. Incorrect-information reporting and
  comparison flows are implemented; human review remains required before
  machine-structured rows can be published.
- Browser history is not rehydrated from the durable transcript after reload.
- Browser session, turn, RAG, transcript, and reset ownership now use a
  server-issued bearer token; telephony identity and operator escalation
  workflow still need their separate production integration.
- Redis-backed per-session/per-IP limits now protect text, voice, RAG, and guest
  session creation; a real multi-instance load test remains.
- Alembic migration history now includes the security/observability schema;
  Postgres migration and restore verification remain deployment work.
- Docker Compose is development-oriented (`--reload`, bind mounts) and there is
  no production deployment manifest or CI workflow.
- There are no frontend unit, accessibility, or Playwright E2E tests.
- There is no documented retention period for income, caste/category, disability,
  transcript, or escalation data.
- Citizen UI strings are embedded in components/prompt modules rather than a
  typed ten-language localization workflow; only English, Hindi, and Kannada
  prompt catalogs are active.
- The current dark green/lime visual system and Manrope/DM Mono font setup do not
  yet follow the proposed UX4G/GIGW-informed public-service direction or provide
  deliberate font loading for all target Indic scripts.
- Citizen account linking remains out of scope for the guest-first beta. The
  admin shell, RBAC boundary, OIDC/MFA claim validation, immutable audit log,
  messaging cost view, freshness/evaluation view, feature-flag rollout and
  rollback, audit export, provider rollback, runtime flag enforcement,
  deployment/version comparison, and dry-run provider-failure simulations are
  implemented; managed IdP
  provisioning and browser redirect UX remain deployment-specific.
- Runtime rollout gates now cover core/expansion languages, state availability,
  government-job matching, streaming voice, STT/TTS/RAG provider kill
  switches, and Infobip reminder creation/dispatch. Public catalogs expose
  rollout posture while guest sessions receive a stable cohort assignment.
- Provider routing policies now have admin-only, audited, expiring overrides
  and rollback. Native-speaker quality gates and a separately tested OpenAI
  audio fallback remain required before advertising voice fallback coverage.
- Department routing now has an import format, stale-source gate, admin review
  page, and provenance fields on escalation tickets. Until official rows are
  imported and approved, the state/domain route remains intentionally visible
  as a fallback.
- Expansion-language readiness now has seven review dimensions, evidence URL,
  attestation, reviewer/timestamp, audited activation, and a bundle/review
  validator at `scripts/17_validate_language_release.py`. The prompt loader
  now has complete bundles for all ten Indian-language locales plus English;
  the eight new bundles are explicitly machine-assisted drafts until a native
  reviewer approves them. `scripts/18_validate_language_ui.py` covers
  script/font/accessibility/mobile signals, while
  `scripts/19_language_voice_smoke.py` records a Sarvam-TTS-to-STT round trip
  without activating a locale.

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
runbook. Citizen discovery remains guest-accessible; “authenticated” here means
server-owned session authorization and optional account persistence, not a
mandatory login wall. Beta also requires the citizen design-system shell,
Kannada/Hindi/English localization catalogs, workforce MFA/RBAC, and a minimal
admin overview for provider, cost, data-freshness, and audit visibility.

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
| P0-10 citizen design/i18n | Familiarity and easy navigation | Design tokens, routes, locale bundles | Locale contracts and prompt keys | Reviewed translations | Font assets, locale CI, visual/a11y tests |
| P1-7 admin control center | Operational transparency | Separate admin shell and dashboards | Aggregates, RBAC, audit APIs | Quality/provider history | SLOs, alerts, cost controls |
| P1-8 department directory | Correct human handoff | Directory review/provenance UI | Pincode/district match with safe fallback | Official source exports and freshness | Import/review runbook and routing audits |
| P1-9 language release gate | Safe ten-language expansion | Review matrix, evidence, activation controls | Prompt-bundle discovery and rollout enforcement | Native/content/voice/accessibility evidence | Locale validation and staged rollback |

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
4. Run the source-grounded machine review, recording field-level findings in
   `automated_review`; this never activates a row.
5. Mark rows as `human_verified`, `needs_review`, `stale`, or `illustrative`
   through the future operator review workflow.
6. Deactivate rows with missing source links, contradictory criteria, empty
   criteria, or unclear state scope.
7. Record an import manifest containing:
   - source collection/date;
   - source document count;
   - candidate and accepted row counts;
   - structuring model and prompt version;
   - failures/retries;
   - reviewer and review sample;
   - known limitations.
8. Preserve source text hashes so a later ingestion can identify changed
   documents without reprocessing everything.

### Backend and schema work

Add these fields to `Benefit` through a migration:

```text
verification_status: illustrative | machine_structured | machine_reviewed | needs_review | human_verified | stale
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
- `GET /api/benefits/{benefit_id}` now returns complete benefit/job details and
  provenance; extend it only when new detail fields are introduced.
- Return verification status and last verified date with every match.
- Add an internal validation command that exits non-zero when active rows have
  no source, invalid criteria, an expired date, or an unsupported state/domain.

### Frontend work

The transport and review foundation is now implemented. The remaining P0 work
is measured provider QA and polish, not another client-controlled transcript
submission path.

- Display a clear `Verified`, `Needs review`, or `Illustrative demo` badge.
- Show “Data last updated …” near coverage.
- Hide or visually separate illustrative rows in production mode.
- Show the source name, external source link, verification status, and freshness
  on the dedicated result detail route. Add incorrect-information reporting and
  comparison actions in the next slice.
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

- [x] The dedicated result detail route exposes source, verification date,
      documents, and steps.
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

- Implemented: connecting, listening, reviewing, processing, speaking, and
  failure states with keyboard-accessible transcript review.
- Keep provider-ready and permission-request copy distinct in browser QA.
- Show recording duration and enforce the server limit before upload.
- Implemented: cancel/interrupt controls and a retry path through a fresh voice
  turn; verify the copy and timing on real devices.
- Explain how microphone audio is used before requesting permission.
- Preserve text mode when microphone permission is denied or STT is unavailable.
- Show a manual play control even when autoplay succeeds.
- Implemented: clip fallback for browsers without AudioWorklet/realtime support
  and text remains available; verify low-bandwidth messaging in browser QA.
- Do not store audio blobs in Zustand/localStorage.

### Backend/provider work

- Implemented: explicit `container`/`pcm16` framing, 24 kHz validation, byte and
  container-chunk caps, and WAV wrapping for PCM batch fallback.
- Return a dedicated error code for empty transcription, provider timeout,
  unsupported language, and exhausted quota.
- Add bounded retries with jitter only for safe transient provider failures;
  realtime sessions currently fail closed to the existing buffered path before
  the turn is committed.
- Set separate connect/read/write timeouts and log provider latency.
- Pass request ID, provider, model, language, input bytes/characters, cache hit,
  and billed characters to metrics/traces without attaching raw audio.
- Prewarm Kannada and Hindi canned phrases and verify Redis cache hits.
- Add a response-size guard; large synthesized output should move to a
  binary/short-lived URL delivery path instead of unbounded base64 JSON.

### Budget-aware TTS provider policy

Implement TTS behind a provider-neutral router rather than calling Sarvam
directly from conversation code. The default resolution order is:

```text
reviewed cached/prerecorded prompt
  -> Sarvam TTS (primary for approved Indic locales)
  -> OpenAI gpt-4o-mini-tts (quality-approved locale fallback)
  -> text response with transcript (always available)
```

- Keep STT and TTS policies independent. Existing OpenAI transcription can
  remain the STT path while this policy controls synthesized output only.
- Switch away from Sarvam on quota exhaustion, an open circuit breaker,
  configured daily/monthly budget threshold, repeated timeout/5xx response, or
  an explicit operator override. Do not switch providers merely because one
  request is slow.
- Configure provider order per locale. OpenAI documents multilingual TTS
  support, including Hindi, Kannada, Marathi, Tamil, and Urdu, but also states
  that its built-in voices are optimized for English. Therefore a native-speaker
  quality check is mandatory before enabling OpenAI fallback for each Indian
  language; an unapproved locale falls directly to text.
- Show a non-alarming “Using a fallback voice” status when the audible voice or
  accent changes. Never silently reduce language quality.
- Disclose that the voice is AI-generated before first playback, as required by
  OpenAI's usage policy.
- Cache audio by normalized text, locale, provider, model, voice, format, and
  prompt revision. Pre-generate fixed prompts and use WAV/PCM for low-latency
  playback where the measured bandwidth tradeoff is acceptable.
- Store `VoiceProviderPolicy` in reviewed configuration, not scattered
  environment conditionals. Include locale, provider order, enabled voices,
  quality-review status, low-credit threshold, daily/monthly budget, circuit
  state, and last operator change.
- Reconcile estimated usage against provider billing and expose remaining
  configured budget, fallback count, cache savings, and failure reason to admin.
- Keep keys server-side, rotate them independently, and never expose provider
  credentials or raw audio in client diagnostics.

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
- [ ] Sarvam quota/429 and outage tests fail over without losing the text answer.
- [ ] OpenAI TTS is enabled only for locale/voice combinations with a recorded
      native-speaker quality approval.
- [ ] Users receive AI-voice disclosure and can always read the same transcript.

---

## P0-4 — Session privacy, authorization, and abuse controls

**Outcome:** one user cannot read/delete another user’s sensitive profile, and
paid endpoints cannot be abused anonymously.
**Size:** L for submission-safe minimum; XL for full beta
**Depends on:** a decision about browser identity and operator authentication

### Current risk

At the roadmap baseline, `caller_id` was client-controlled and operator
escalation endpoints were public. The browser path now uses a server-issued
hashed bearer token, and escalation reads/resolution require an authorized
workforce role. Income, social category, disability, and conversation text
remain sensitive; telephony webhook identity, retention/deletion jobs, and a
multi-instance abuse/load test remain production gates.

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

### Citizen and workforce authentication model

- Keep anonymous discovery as the default. Do not put a login wall before the
  first question, coverage page, benefit detail, or help/privacy content.
- Offer optional citizen authentication only for saved benefits, cross-device
  continuity, reminders, and durable profile management. Support a low-friction
  phone/email OTP or passkey path; never require a password a user may struggle
  to recover on a shared device.
- Link an anonymous browser session to an account only after explicit consent,
  with a preview of the data that will be retained.
- Use managed OIDC/OAuth where practical. Validate issuer, audience, signature,
  expiry, nonce/state, and redirect allowlists server-side.
- Require MFA or passkeys for workforce accounts. Define `admin`, `operator`,
  `reviewer`, and read-only `observer/auditor` roles with deny-by-default
  permissions; do not treat possession of an admin URL as authorization.
- Use short-lived workforce sessions, secure cookie settings, CSRF protection
  where cookies authenticate mutations, device/session revocation, and a forced
  re-authentication step for provider-policy or role changes.
- Audit sign-in, failed sign-in, role changes, sensitive record views, exports,
  provider overrides, and feature-flag changes. Never put tokens or sensitive
  profile values in the audit payload.
- Provide an accessible sign-in/recovery experience with clear errors, generous
  OTP expiry, resend throttling, and no CAPTCHA-only path.

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
- [ ] Benefit discovery and the first conversation work without account creation.
- [ ] Workforce routes require the correct role and MFA/passkey assurance.
- [ ] Account linking shows and records explicit retention consent.
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
| Identity | local test issuer | managed test tenant | managed tenant + MFA |
| Provider budgets | low dev caps | test caps + alerts | approved caps + circuit/fallback policy |
| Locale/font assets | local bundles | immutable CDN/origin assets | immutable CDN/origin assets + monitoring |
| Demo data | allowed/labeled | verified preferred | verified only |

Never expose provider keys to the Vite build. Configure spend limits and key
rotation in each provider account. Environment variables bootstrap secret IDs
and safe defaults; mutable per-locale routing/budget policy belongs in audited
configuration with a database revision, not ad hoc environment flags.

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
tts_provider_fallback_total by from/to/locale/reason
provider_budget_used and provider_budget_remaining by provider/period
match_candidate_count and match_verdict_total
no_match_total and escalation_total by reason
active_session_total and turn_total
```

### Alerts and runbook

- Uptime alert: API unavailable or readiness failing.
- Error alert: voice/provider error rate over threshold.
- Cost alert: unexpected STT/TTS usage spike.
- Budget alert: Sarvam/OpenAI reaches 50%, 75%, 90%, or 100% of the configured
  period budget, or remaining quota cannot be fetched/reconciled.
- Fallback alert: provider switch rate exceeds the normal baseline for a locale.
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
- Verify keyboard-only operation, skip links, semantic landmarks, logical heading
  order, visible focus, 44px minimum targets (48px for primary touch controls),
  contrast, reduced motion, live-region announcements, and screen-reader labels.
- Set the document language and script direction from the selected language.
- Test Kannada/Devanagari wrapping at 320px and 200% zoom.
- Do not put essential instructions only in placeholder text or audio.
- Add captions/transcript for every generated audio response.
- Keep icons paired with text in primary navigation and never use color, motion,
  audio, or shape as the only carrier of meaning.
- Keep focus stable when a message arrives, announce it without stealing focus,
  and provide pause/replay controls for audio.
- Make text sizing, high contrast, and reduced motion real design-system modes;
  do not rely on an accessibility overlay as a substitute for semantic HTML.
- Publish an accessibility/help page describing keyboard use, microphone
  alternatives, known limitations, and a contact/escalation route.

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
- [ ] The primary flow remains understandable at 200% zoom, high contrast, and
      with animation disabled.
- [ ] Navigation order and labels are consistent across every citizen route.
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
7. Explain the honest scope: verified subset now, ten-language UI target and
   state-by-state data expansion later.

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

## P0-10 — Citizen design system, navigation, and localization foundation

**Outcome:** the app feels familiar to users of Indian public-service websites,
is easy to navigate regardless of digital confidence, and can add reviewed
languages without duplicating components or business logic.
**Size:** L for the foundation and Kannada/Hindi migration; XL for all ten
language packs and their human review
**Depends on:** stable citizen routes, content ownership, and native-language
reviewers

This package uses the Government of India's UX4G foundations and GIGW guidance
as design references. It adopts familiar patterns, clarity, and accessibility;
it does **not** copy government identity or imply that Sahaayak is an official
government website.

### Visual direction and trust rules

Replace the current dark green, acid-lime, and orange presentation with a light,
calm public-service theme. Do not paint the interface as a tricolor. Navy/indigo
is the structural color, saffron is a restrained accent, and green is reserved
for positive status. Proposed semantic tokens are a Sahaayak palette inspired by
public-service conventions, not claimed UX4G token values:

| Token | Proposed value | Use |
| --- | --- | --- |
| `--color-brand-900` | `#12345B` | Header, high-emphasis surfaces |
| `--color-brand-700` | `#1E4E85` | Primary controls and links |
| `--color-brand-600` | `#245FAE` | Hover/interactive emphasis |
| `--color-accent-saffron` | `#C65D00` | Small highlights, active markers |
| `--color-success-700` | `#147A3E` | Verified/success status only |
| `--color-warning-700` | `#8A4B00` | Stale data, caution, uncertainty |
| `--color-danger-700` | `#B42318` | Errors and destructive actions |
| `--color-info-700` | `#175CD3` | Informational status and focus |
| `--color-text` | `#17202A` | Default text |
| `--color-text-muted` | `#475467` | Secondary text |
| `--color-border` | `#D0D5DD` | Borders and dividers |
| `--color-surface` | `#FFFFFF` | Primary surface |
| `--color-surface-subtle` | `#F6F8FB` | Page/background grouping |
| `--color-focus` | `#0B57D0` | 3px visible focus ring |

- Map these semantic variables into Tailwind v4 `@theme` and the shadcn
  component variables. Components consume roles such as `primary`, `surface`,
  `success`, and `focus`; they do not hard-code palette hex values.
- Verify every final foreground/background pair in automated contrast tests;
  token names and roles are fixed, but hex values may be adjusted to pass AA/AAA
  targets and user testing.
- Use white space, borders, and typography before elevation. Keep shadows subtle
  and avoid glassmorphism, neon treatments, and animation-heavy decoration.
- Use saffron in less than roughly 10% of a typical screen and never as the only
  status indicator. Use green only for semantic success/verification, not for
  generic branding.
- Show source organization, last-verified date, coverage label, privacy/help,
  and “independent guidance—not an official eligibility decision” in predictable
  locations. Trust should come from provenance rather than official-looking
  seals.
- Never use the State Emblem of India, ministry marks, an `india.gov.in`-style
  masthead, or “Government of India” ownership language without written
  authorization. A future government partnership gets a separate legal/brand
  review before adding co-branding.

### Typography, icons, spacing, and motion

- Follow the UX4G typography approach: `Noto Sans` for UI and
  `Noto Sans Display` only for large display headings. Load script-specific Noto
  Sans subsets for Devanagari, Kannada, Tamil, Telugu, Bengali, Gujarati,
  Malayalam, Gurmukhi, and Odia as the selected locale requires.
- Map the selected script font through a token such as `--font-locale` and use a
  resilient stack like `var(--font-locale), "Noto Sans", system-ui, sans-serif`;
  do not rely on a remote Google Fonts request. Self-host versioned WOFF2 subsets
  with `font-display: swap` and preload only the active locale's critical subset.
- Limit weights to 400, 500, 600, and 700. Use 16/24px as the default body size,
  14/20px only for helper text, and 12/16px only for non-essential captions.
  Suggested headings are 40/44, 32/36, 28/32, 24/28, 20/24, and 16/20.
- Use a base-4 spacing scale and a responsive grid. Keep readable text near
  65–75 characters per line; do not force Indic text into narrow fixed-height
  cards or truncate critical labels.
- Use Lucide icons consistently, paired with visible labels for primary actions.
  Do not introduce decorative government emblems or unrelated illustration
  styles.
- Motion remains functional and restrained: 120–240ms transitions, no parallax,
  no blocking intro animation, no repeated pulsing, and complete support for
  `prefers-reduced-motion`. Audio/recording state must remain understandable with
  motion disabled.

### Citizen information architecture and navigation

Use one predictable citizen shell, separate from `/admin`:

```text
/
├── /conversation
├── /benefits/$benefitId
├── /saved                 (authentication requested only when needed)
├── /profile               (optional authenticated persistence)
├── /help
├── /accessibility
├── /transparency
└── /privacy

/admin/*                   (separate workforce shell and authorization)
```

- The first screen presents two obvious equal-status actions: “Speak” and
  “Type”, followed by language selection and a short privacy explanation.
- Desktop header: Sahaayak identity, language, accessibility, help, and optional
  sign-in; put privacy, transparency, and provenance links in a consistent
  footer. Mobile bottom navigation: at most Home, Conversation, Saved, and Help.
- Keep the citizen hierarchy no more than two levels for normal tasks. Use a
  back action and breadcrumb on benefit detail; preserve conversation state.
- Keep controls in the same position across languages. Use plain, task-based
  labels (“Find benefits”, “Listen again”, “Talk to a person”) rather than
  internal terms such as “agent”, “turn”, “intent”, or “escalation”.
- Provide multiple paths to critical actions: header/help, contextual link, and
  voice/text command where relevant. Never hide delete, privacy, human help, or
  language change inside an unlabeled menu.
- Use progressive disclosure: ask one question at a time, explain why sensitive
  information is requested, preserve entered answers, and show a short progress
  cue without promising an exact number of remaining questions.
- Test the shell with keyboard, screen reader, switch/voice control, low-end
  Android, 320px width, 200% zoom, slow network, and a first-time low-literacy
  usability cohort.

### Ten-language localization architecture

English is the fallback, not part of the ten-language commitment. Use these
stable locale identifiers:

| Rollout | Language | Locale |
| --- | --- | --- |
| Launch | Kannada | `kn-IN` |
| Launch | Hindi | `hi-IN` |
| Wave 2 | Tamil | `ta-IN` |
| Wave 2 | Telugu | `te-IN` |
| Wave 2 | Marathi | `mr-IN` |
| Wave 2 | Bengali | `bn-IN` |
| Wave 3 | Gujarati | `gu-IN` |
| Wave 3 | Malayalam | `ml-IN` |
| Wave 3 | Punjabi | `pa-IN` |
| Wave 3 | Odia | `od-IN` for Sarvam; `or` for the application/Whisper code |
| Fallback | English | `en-IN` |

- Standardize the web app on `i18next` + `react-i18next` with ICU support for
  plurals, interpolation, and locale-aware formatting. Use typed semantic keys,
  namespaces per feature, lazy locale chunks, and a missing-key failure in CI.
- Initialize localization once at the app root; route metadata, validation,
  toasts, dialogs, empty states, and accessibility labels use the same catalog.
  No user-visible English literal remains embedded in a feature component.
- Separate interface locale from benefit geography. A Bengali-speaking user can
  search Karnataka data; a translated interface must never imply that benefits
  for every state are available.
- Use a fallback chain of selected locale -> `en-IN` -> visible safe key/error.
  Persist the user's explicit selection; browser language detection may suggest
  but must not override it.
- Set `<html lang>` from the active locale. Make layout tokens direction-aware
  now (`inline-start`/`inline-end`) so a future Urdu/RTL pack does not require a
  rewrite, even though the initial ten are left-to-right.
- Keep UI strings, backend validation/error messages, agent prompts, benefit
  summaries, and TTS phrases in separate versioned catalogs with shared semantic
  IDs. Never send an English backend error directly into a localized screen.
- Do not machine-translate eligibility criteria, caveats, application steps, or
  legal/policy text at request time. Translate from the reviewed source, keep
  reviewer/date/version metadata, and display English fallback explicitly when
  a reviewed translation is unavailable.
- Format dates, numbers, and currency with `Intl`; store canonical numbers and
  ISO dates, never locale-formatted values, in APIs and the database.
- Define a translation state machine of `draft`, `machine_assisted`, `reviewed`,
  `approved`, `active`, and `superseded`. Only `active` content is user-facing.
- Add pseudo-localization, long-string, missing-glyph, mixed-script, English
  numeral, and code-switch tests. Screenshot every critical route in each active
  script at mobile and desktop sizes.

### Backend, data, and infrastructure work

- Return stable machine-readable error codes and localized message parameters;
  let the client catalog render UI errors. Server-rendered/voice-only responses
  use the matching reviewed backend catalog.
- Add locale to session, transcript, trace, content revision, and provider-policy
  records. Normalize locale aliases at the API boundary.
- Expose a versioned coverage endpoint reporting, per locale and state, whether
  UI, prompts, data translation, understanding, STT, TTS, and native review are
  `unsupported`, `preview`, or `active`.
- Generate translation completeness and stale-source reports in CI. Block
  activation when required keys, fonts, reviewed content, provider policy, or
  accessibility screenshots are missing.
- Serve locale/font assets from the same CDN/origin with immutable hashes and a
  small English fallback bundle. Monitor missing translation keys and font load
  failures without logging user text.
- Keep language rollout behind feature flags. Roll back one locale independently
  without taking the whole application offline.

### Acceptance

- [ ] The citizen shell follows the proposed semantic tokens and no longer uses
      the current dark green/lime visual treatment.
- [ ] Primary routes are navigable by keyboard, screen reader, and touch with
      consistent labels and no more than two normal hierarchy levels.
- [ ] Typography renders every active script without missing glyphs, clipping,
      or critical layout shift at 320px and 200% zoom.
- [ ] Kannada, Hindi, and English have complete typed UI catalogs with no
      production missing-key fallback.
- [ ] Locale and state are independently selectable and coverage is represented
      honestly.
- [ ] A locale cannot become active without translation, voice, content,
      accessibility, and native-review evidence.
- [ ] Sahaayak displays its independent status and uses no restricted government
      identity asset or implied endorsement.

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
- Keep an immutable public-content snapshot for every edit/review/rollback;
  require an expected revision on browser edits and restrict rollback to admin.
- Highlight every numeric/category field and its source evidence.
- Schedule source freshness checks based on hash/date and persist deduplicated,
  acknowledgeable alerts for active or human-verified rows.
- Automatically mark expired job postings and expired schemes inactive.
- Add review sampling metrics and inter-reviewer disagreement tracking.
- Keep model/prompt lineage for every proposed revision.
- Materialize private document/application tasks from a saved benefit and keep
  progress separate from official application status.

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

- Import current UPSC recruitment advertisements from the official index into a
  machine-structured, inactive review queue. A second NCS adapter needs an API
  key and confirmed terms/fields.
- Store `published_at`, `application_deadline`, `employer`, `vacancy_count`, and
  `employment_type` in job metadata and render a job-specific detail view.
- Enforce automatic expiry and source verification; publication still requires
  an authorised human reviewer.
- Tune minimum/follow-up slots for location, education, age, and experience.
- Add a jobs-specific result layout and deadline warning.

### Acceptance

- [x] Expired jobs are excluded by the deterministic matcher.
- [ ] Every published job has a future deadline or explicit rolling status.
- [ ] At least 10–30 jobs are human-reviewed and published from authoritative
      sources.
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

## P1-7 — Admin control center and operational transparency

**Outcome:** authorized staff can understand what the system did, why it did it,
what it costs, where quality is degrading, and who changed production behavior
without querying the database or exposing citizen data.
**Size:** XL
**Depends on:** workforce authentication/RBAC, P0 telemetry, provider policy,
data revisions, and immutable audit events

The admin control center is separate from the citizen interface and uses its own
`/admin` shell. The escalation queue in P1-1 becomes one module, not the entire
admin product.

### Admin navigation and screens

```text
/admin
├── /overview
├── /conversations       (redacted metadata by default)
├── /escalations
├── /benefits            (coverage, freshness, review queue)
├── /languages           (catalog/voice/QA readiness)
├── /providers           (health, spend, fallback policy)
├── /evaluations         (agent and native-language reports)
├── /traces              (safe trace links and failure drill-down)
├── /system              (deployments, SLOs, incidents, feature flags)
├── /audit-log
└── /settings            (role-restricted)
```

- Overview shows uptime/SLO status, p50/p95 turn latency, 4xx/5xx/error rate,
  active sessions, no-match/escalation rate, verified/stale benefit counts,
  language mix, STT/TTS health, provider fallback rate, cache hit rate, and
  current/forecast provider spend.
- Every card links to a filtered detail view, names its time window and data
  freshness, and clearly distinguishes “no data” from zero.
- Conversation drill-down starts with request ID, locale, state, step, timings,
  provider/model/prompt/data revisions, and redacted error metadata. Raw
  transcript or sensitive profile access requires a stronger role, stated
  reason, and audited action; it is never shown on overview dashboards.
- Provider controls expose policy per locale, circuit state, estimated budget,
  quota/credit status when provider APIs support it, fallback reasons, voice QA
  approval, and cache savings. Manual override requires confirmation, reason,
  re-authentication, audit entry, and optional expiry.
- Language readiness shows interface completeness, prompt review, data
  translation, understanding evaluation, STT/TTS approval, font/visual checks,
  and rollout status as separate dimensions.
- Data views expose source, last verified date, reviewer/revision history,
  expiry, ingestion failures, and rollback—not just row counts.
- System view records deployment commit, migration revision, data revision,
  prompt/model versions, active flags, incidents, backup age, and last restore
  test.
- Use tables for comparison, sparklines only where a trend matters, plain-language
  labels, keyboard-accessible filters, shareable URLs, CSV export of already
  redacted data, and accessible empty/loading/error states.
- Use a TanStack Router protected admin layout, TanStack Query for all server
  aggregates and mutations, URL search parameters for shareable filters, and
  Zustand only for ephemeral display preferences. A frontend route guard improves
  UX but never replaces API authorization.

### Backend and data work

- Build read-optimized aggregate endpoints; do not make the browser join raw
  operational tables or depend directly on vendor dashboard APIs.
- Introduce `AuditEvent`, `DeploymentRevision`, `VoiceProviderPolicy`,
  `ProviderUsageDaily`, `LocaleReadiness`, and `FeatureFlagRevision` records with
  actor, reason, before/after, request ID, and timestamp where applicable.
- Use append-only audit semantics with retention and integrity monitoring.
  Corrections are new events, not edits to historical events.
- Create scheduled rollups for latency, errors, spend, language, results, and
  data freshness. Keep metric dimensions bounded; request IDs belong in traces,
  not metric labels.
- Proxy links into Langfuse or other vendor tools through authorization-aware
  metadata. Never embed an unrestricted vendor API key in the web client.
- Add cursor pagination, bounded date ranges, server-side filtering, export size
  limits, and background jobs for large reports.
- Return explicit `data_fresh_at`, partial-data, and upstream-unavailable fields
  so dashboards never imply false certainty.

### Security, privacy, and operational controls

- Enforce role/action permissions server-side: observers read aggregate health;
  operators handle escalations; reviewers manage content; admins manage roles,
  provider policies, and flags. UI hiding is not an access control.
- Require MFA/passkey assurance and short sessions; apply IP/device controls only
  where they do not create an inaccessible recovery path.
- Redact by default, apply least privilege, require a reason for sensitive
  access/export, watermark exports, and alert on unusual access patterns.
- Make destructive/high-risk controls two-step and reversible where possible.
  Provider overrides and flags have an expiry/rollback path; role removal takes
  effect immediately.
- Publish a separate public transparency page containing non-sensitive coverage,
  source/freshness methodology, known limitations, AI/voice disclosure, language
  status, privacy/retention summary, and incident contact. Do not publish internal
  traces, costs, vulnerabilities, or identifiable usage.

### Acceptance

- [ ] Each role sees and can call only its authorized modules/actions.
- [ ] An operator can follow a failed turn by request ID across safe app,
      provider, trace, prompt, model, and data-revision metadata.
- [ ] Provider budget/fallback status is visible and an audited emergency switch
      can be safely applied and automatically expired.
- [ ] Dashboard totals reconcile with source metrics and state their freshness.
- [ ] Sensitive transcript/profile data is absent by default and every elevated
      view/export is reasoned and audited.
- [ ] The public transparency page explains coverage, provenance, AI voice,
      limitations, and last update in all active interface languages.

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

## P2-2 — Streaming voice hardening and voice activity detection

**Value:** lower perceived latency and hands-free turn endings.
**Status:** transport foundation implemented; real-key QA and production
hardening remain.

**Size:** M for the remaining hardening after the current voice slice

### Implementation outline

- Evaluate browser VAD only after measuring false-stop behavior on noisy/mobile
  environments; retain a manual stop control.
- Implemented: WebSocket PCM frames with a server-owned guest token, local VAD,
  partial transcript deltas through the opt-in Realtime provider, final
  transcript acceptance, sentence-level TTS chunks, interruption propagation,
  and MediaRecorder/WAV fallback.
- Remaining: real Kannada/Hindi latency and accuracy evidence, disconnect/retry
  drills, browser compatibility QA, and provider billing reconciliation.

### Acceptance

- [ ] Median perceived response time improves materially over clip mode.
- [ ] False turn endings remain within an agreed threshold across test devices.
- [ ] Disconnects do not create duplicate turns or provider charges.
- [x] A transcript cannot reach the matcher/RAG graph until the caller accepts
      or edits it.

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

## P2-6 — Ten-language and state-by-state expansion

**Value:** makes the citizen interface usable across ten Indian languages while
expanding verified benefit coverage honestly, one geography at a time.
**Size:** XL per language/content/data combination

The interface-language target and benefit-geography target are independent.
Completing ten UI language packs does not create ten-state benefit coverage, and
the product must never present them as equivalent.

### Sequence per language/state

1. Complete and review the interface locale independently of geography.
2. Translate the prompt and benefit-content catalogs; record native review.
3. Configure STT/TTS locale, primary/fallback providers, and voice quality gate.
4. Ingest and review state-specific data without blocking use of the locale for
   already-supported geographies.
5. Add understanding fixtures for script, numbers, category, education, and
   common code-switch patterns.
6. Run translation completeness, font/glyph, text/voice, accessibility, visual,
   and low-bandwidth QA.
7. Launch the locale and each new state behind independent feature flags; monitor
   no-match, fallback, abandonment, and escalation rates.

Roll out in the waves defined by P0-10: Kannada/Hindi, then
Tamil/Telugu/Marathi/Bengali, then Gujarati/Malayalam/Punjabi/Odia. English
remains the safe fallback throughout.

Do not activate a language merely because prompts compile; active means data,
content, understanding, voice (or an explicitly disclosed text-only mode), fonts,
accessibility, and review quality meet the launch bar.

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
| GET | `/api/locales` | Locale/state/UI/voice/content readiness matrix | P0 |
| GET | `/api/transparency` | Public non-sensitive coverage/methodology snapshot | P1 |
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
| GET | `/api/admin/overview` | Bounded operational and quality aggregates | P1 |
| GET | `/api/admin/providers` | Health, spend, fallback, and locale policy | P1 |
| PATCH | `/api/admin/providers/{provider}/policies/{locale}` | Audited provider policy change | P1 |
| GET | `/api/admin/languages` | Translation/voice/data/QA readiness | P1 |
| GET | `/api/admin/audit-events` | Filtered immutable audit history | P1 |
| GET | `/api/admin/system/revisions` | Deploy, migration, data, prompt/model versions | P1 |

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

VoiceProviderPolicy (new)
  locale, provider_order, voice_by_provider, quality_status
  low_credit_threshold, daily_budget, monthly_budget, circuit_state
  changed_by, change_reason, expires_at, updated_at

TranslationRevision (new)
  locale, namespace, source_locale, source_revision, status
  content_hash, reviewed_by, reviewed_at, activated_at

LocaleReadiness (new)
  locale, interface_status, prompt_status, content_status
  understanding_status, stt_status, tts_status, accessibility_status
  evidence_links, activated_at

AuditEvent (new, append-only)
  actor_id, actor_role, action, target_type, target_id
  reason, safe_before, safe_after, request_id, created_at

ProviderUsageDaily (new)
  provider, date, requests, input_units, output_units
  estimated_cost, reconciled_cost, fallback_count, cache_saved_units

DeploymentRevision (new)
  commit_sha, migration_revision, data_revision
  prompt_versions, model_versions, deployed_by, deployed_at
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
| Contract | every API response, localized error code, OpenAPI drift, generated TS/Zod compatibility |
| Component | result states, recorder states, consent, locale switch, profile correction, admin/operator UI |
| Integration | Postgres transactions/migrations, Redis cache, authorization, deletion cascade |
| Provider contract | recorded/mock OpenAI/Sarvam shapes, quota/timeout mapping, circuit/fallback policy |
| E2E | text flow, voice/fallback flow, result details, locale/state switch, delete, admin/operator authorization |
| Localization/visual | typed-key completeness, pseudo-locale, script fonts/glyphs, screenshots by active locale |
| Human QA | native-language content/voice, respectful wording, noisy audio, low-literacy and low-end Android use |
| Non-functional | WCAG/contrast/zoom/reduced-motion, bundle/load performance, rate limits, backup restore, basic load |

### 8.2 Required merge gate

```text
ruff -> mypy -> pytest -> migration check -> OpenAPI/type drift
     -> frontend typecheck -> frontend unit tests -> production build
     -> locale/font/contrast checks -> Playwright primary smoke
     -> container readiness smoke
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
- Every advertised locale has current content, voice/text fallback, font,
  accessibility, and native-review evidence.
- Provider budgets and fallback policy are healthy, reconciled, and visible.

---

## 9. Recommended execution sequence

### 9.1 Submission cut (derived from the Aug 10 date in the original spec)

| Day | Primary outcome | Parallel work |
| --- | --- | --- |
| 1 | Data pilot, review rubric, provenance schema | Alembic + session/auth and UX4G token design |
| 2 | 20+ reviewed benefits seeded | Benefit detail contract + citizen navigation shell |
| 3 | Actionable result UI complete | Kannada voice smoke, TTS prewarm/provider router |
| 4 | Kannada voice E2E reliable | Hindi review + Kannada/Hindi i18n catalog migration |
| 5 | Staging deploy with Postgres/Redis/migrations | Langfuse + metrics + CI |
| 6 | Security minimum, Playwright, accessibility, native review | Agent eval + palette/font/locale QA |
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
6. Ship the admin overview, provider/cost, language-readiness, and audit modules.
7. Harden CI/CD, backups, alerts, and Postgres/Redis integration tests.
8. Curate real jobs.

### 9.3 Expansion phase

1. Measure the beta funnel and abandonment reasons.
2. Add reminders/tasks if users reach results but do not apply.
3. Add telephony if browser access is the limiting factor.
4. Add streaming/VAD if clip latency is the limiting factor.
5. Expand the interface to ten Indian languages in reviewed waves and add state
   datasets independently, one verified geography at a time.

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
| D11 | Citizen visual direction | UX4G/GIGW-informed light public-service theme; no government identity assets | P0-10 |
| D12 | UI localization stack | `i18next` + `react-i18next` + ICU; typed semantic keys and lazy locale chunks | P0-10 |
| D13 | Ten-language rollout | KN/HI, then TA/TE/MR/BN, then GU/ML/PA/OR; English fallback | P0-10/P2-6 |
| D14 | Citizen authentication | Guest-first; optional OTP/passkey account for persistence | P0-4/P1-2 |
| D15 | Workforce authentication | Managed OIDC, MFA/passkey, strict admin/operator/reviewer/observer roles | P0-4/P1-7 |
| D16 | TTS routing | Cache -> Sarvam -> quality-approved OpenAI -> text | P0-3 |
| D17 | Admin scope | Separate role-protected control center; redacted-by-default drill-down | P1-7 |

---

## 11. Explicit non-goals until the core is done

- Generic/unbounded RAG that replaces structured eligibility; source-grounded
  evidence retrieval is allowed when it preserves provenance and uncertainty.
- An LLM making the final eligibility decision.
- Fully autonomous form submission or claims of official approval.
- Local GPU/model hosting.
- Ten active languages with unreviewed UI/content, missing glyphs, or no honest
  coverage/voice status.
- Nationwide coverage claims based on schema extensibility.
- Storing raw voice recordings by default.
- Building separate eligibility logic for browser, telephony, or each language.
- A large admin dashboard before the user result, provider telemetry, secure
  workforce boundary, and escalation flows are reliable.

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
- [UX4G foundations](https://www.ux4g.gov.in/foundations?lang=en) — official
  Government of India design-system foundations for color, typography, spacing,
  content, and accessibility.
- [UX4G color](https://www.ux4g.gov.in/foundations/color) and
  [typography](https://www.ux4g.gov.in/foundations/typography) — semantic color
  roles and the Noto Sans-based public-service typography approach.
- [GIGW guidelines](https://guidelines.india.gov.in/guidelines/) and
  [quick tips](https://guidelines.india.gov.in/quick-tips/) — government website
  accessibility, consistent multilingual content, ownership, and citizen-focused
  content guidance.
- [react-i18next documentation](https://react.i18next.com/) and
  [ICU integration](https://react.i18next.com/misc/using-with-icu-format) — React
  localization, lazy language resources, interpolation, and ICU message support.
- [OpenAI text-to-speech guide](https://developers.openai.com/api/docs/guides/text-to-speech)
  — `gpt-4o-mini-tts`, streaming/formats, multilingual support, English-optimized
  voice caveat, and required AI-voice disclosure.

---

## 13. Immediate next action

Start **P0-1 and the P0-5 Alembic skeleton in parallel**, while a frontend track
defines the P0-10 semantic tokens, Noto font loading, citizen route shell, and
typed Kannada/Hindi/English catalog. P0-1 resolves the largest product-trust gap;
the migration skeleton prevents every subsequent schema improvement from
deepening the current `create_all` debt; and the small design/i18n foundation
prevents new result/auth screens from being built twice. Once the pilot data
shape is stable, implement P0-2, then complete the P0-3 provider router and live
voice path against the same verified benefits.

The implementation session should begin with:

1. Add Alembic and an initial migration without changing runtime behavior.
2. Add benefit provenance/verification fields and `DataImportRun` migration.
3. Run the 20-row Karnataka ingestion pilot.
4. Review the pilot and publish a `docs/data-review-YYYY-MM-DD.md` report.
5. Add the UX4G-informed semantic color/typography tokens, citizen navigation
   shell, and typed `en-IN`/`kn-IN`/`hi-IN` locale catalogs.
6. Extend benefit/match APIs and build the actionable result detail UI with those
   shared tokens and localized semantic keys.
7. Introduce the provider-neutral TTS policy and prove Sarvam -> approved OpenAI
   -> text fallback with cost/failure telemetry.
