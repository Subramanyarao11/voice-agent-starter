# Sahaayak — Team Handoff and Conversation Context

**Last updated:** 2026-08-03  
**Repository:** voice-agent-starter  
**Current branch:** main  
**Current commit:** b7a89a7 — feat: productionize platform and add optional product foundations  
**GitHub remote:** private repository at Subramanyarao11/voice-agent-starter

This document consolidates the product decisions, architecture, implementation
status, open work, costs, provider options, and operational expectations discussed
so far. It is intended as a handoff for a teammate. It does not contain API keys
or other secrets. Never copy local .env values into a ticket, chat, or commit.

## 1. Executive summary

Sahaayak is a voice-first, local-language public-service assistant. A person
should be able to speak naturally in an Indian language, describe their situation,
and receive a clear explanation of potentially relevant government schemes,
scholarships, and eventually lightweight job opportunities.

The system must be useful to people who may have limited English literacy,
limited typing ability, low bandwidth, or difficulty navigating complex official
websites. The product should guide people toward official sources and next steps,
not pretend to issue a government eligibility decision.

The important architectural boundary is:

~~~text
Structured, verified eligibility data -> eligibility matcher -> likely eligibility result
OpenAI-hosted RAG corpus          -> evidence, explanation, source discovery only
~~~

RAG must not become an unbounded authority for final eligibility. The matcher
uses structured criteria and can return pass, fail, or unknown. The user-facing
wording should remain cautious, for example: “You may be eligible based on the
answers provided. Please verify the official requirements.”

## 2. Product vision and initial scope

### Primary experience

1. A citizen selects a language and state, or accepts sensible defaults.
2. The citizen can type or speak a question.
3. The agent identifies intent and gathers structured slots such as age,
   income, state, category, disability, education, and employment status.
4. The matcher evaluates structured criteria.
5. RAG retrieves source-grounded explanations and citations when the citizen asks
   what a benefit means or how to apply.
6. The response is shown as readable text and, when voice is enabled, synthesized
   in the selected language.
7. The user sees source URLs, source organization, dates, uncertainty, and the
   next action rather than only a bare “matched/not matched” answer.
8. Low-confidence, no-match, or user-requested cases can be escalated to an
   operator in the future.

### Launch-quality languages

Kannada is the first voice language. Hindi is the second. English is the
development and fallback language.

The long-term direction is ten Indian local languages, but a language must not be
advertised as fully supported until its interface strings, prompts, content,
understanding, STT, TTS or clearly disclosed text fallback, fonts, and accessibility
behavior have been checked.

### Scope boundaries

- Schemes and scholarships are the first serious domains.
- Jobs are a later, lightweight domain with explicit deadlines or rolling status.
- Citizen discovery is guest-accessible; a citizen login is not required for the
  initial beta.
- Admin/operator access is authenticated and role-controlled.
- Telephony is a later adapter over the same agent runtime; it must not create a
  separate eligibility implementation.
- Raw voice recordings should not be retained by default.
- The product must clearly state that it is independent guidance, not an official
  government eligibility decision.

## 3. Decisions made during the conversation

### Technology and frontend

The frontend was requested to be refactored toward conventional, maintainable
React practices using:

- React with Vite and TypeScript.
- Tailwind CSS.
- shadcn/ui and Radix primitives for accessible components.
- motion for restrained interaction and state animations.
- TanStack Query for server state and API caching.
- TanStack Router for typed routing.
- Zustand for local UI/session state.
- Zod for runtime validation and typed boundaries.
- react-media-recorder and browser media APIs for the microphone flow.
- Lucide icons.

The current web package contains these dependencies. The UI should remain calm,
readable, keyboard-friendly, and useful on low-end devices; animation must never
be required to understand status or operate the app.

### Data and RAG

- Do not use hardcoded demo benefits as the product knowledge base.
- Use the existing extracted corpus and avoid repeatedly downloading it.
- Use one OpenAI-hosted Vector Store as the durable RAG knowledge base so the
  knowledge is not lost when Docker containers are removed.
- Docker remains appropriate for the API, web app, Postgres, Redis, Keycloak,
  monitoring, and other infrastructure.
- Keep an ingestion manifest and resume uploads rather than creating a new vector
  store on every run.
- Keep OpenAI usage behind a persistent budget ledger. The current checked-in
  example sets OPENAI_BUDGET_USD=10.0; the guard is designed to reject values
  above the approved $15 ceiling. This should be re-confirmed before any larger
  ingestion or evaluation run.

### Voice providers

- Sarvam is the preferred Indic TTS provider because native-language voice quality
  and trust matter.
- The current implemented STT adapter is OpenAI transcription.
- The current implemented TTS adapter is Sarvam Bulbul with caching and WAV
  chunk/merge support.
- OpenAI is a fallback for reasoning and only for voice combinations that pass a
  language-quality review. It is not automatically safe to use OpenAI TTS for
  every Indian language.
- Provider routing, budgets, circuit state, fallback reasons, and emergency
  switches must be visible to authorized admins.
- A live Kannada test must prove the complete path:

  ~~~text
  Kannada audio -> STT -> intent/slot extraction -> matcher or RAG -> response -> Sarvam TTS
  ~~~

  The provider credits discussed in the telephony section do not cover Sarvam or
  OpenAI model usage.

### Authentication model

- Citizens use anonymous guest sessions by default.
- The server issues an opaque session ID and one-time bearer token; changing a
  caller-controlled ID must not grant access to another session.
- Admins/operators use workforce authentication with OIDC and MFA in production.
- Local development can use Dockerized Keycloak.
- Production still needs a real identity-provider hostname, HTTPS, client
  registration, redirect/logout URLs, issuer, audience, JWKS, roles, and MFA
  policy.

### Telephony

The first telephony version should be:

- inbound calls only;
- one authorized Indian virtual number;
- an authorized Indian carrier/SIP trunk;
- self-hosted Jambonz or an equivalent SIP/media layer;
- Sahaayak handling STT -> matcher/RAG -> TTS;
- no outbound campaign calling until legal/compliance review.

Open-source software can provide the PBX/media/orchestration layer, but it cannot
provide an Indian mobile number, PSTN access, or carrier authorization. Those
remain paid and regulated dependencies.

### Notifications

The product should use a provider abstraction instead of embedding one vendor in
reminder logic:

~~~text
NotificationProvider
  ├── in_app
  ├── email
  ├── sms
  └── whatsapp
~~~

In-app saved benefits and reminders are already implemented. External email, SMS,
and WhatsApp delivery should only be enabled after a verified contact channel,
explicit consent, opt-out handling, delivery status, retries, and cost limits are
implemented.

## 4. Current architecture

~~~mermaid
flowchart LR
    Citizen["Citizen: browser, microphone, later phone"] --> Web["React web app<br/>Tailwind + shadcn + TanStack"]
    Web --> API["FastAPI API"]
    API --> Session["Guest session tokens<br/>Redis rate limits"]
    API --> Agent["LangGraph agent runtime"]
    Agent --> Understand["Rule-first / optional LLM understanding"]
    Understand --> Gather["Structured slot gathering"]
    Gather --> Matcher["Deterministic eligibility matcher"]
    Agent --> RAG["OpenAI-hosted Vector Store<br/>source evidence only"]
    Matcher --> Compose["Localized response composer"]
    RAG --> Compose
    Compose --> TTS["Sarvam TTS<br/>OpenAI fallback by policy"]
    Web --> Audio["Audio playback and transcript"]
    TTS --> Audio
    API --> DB["Postgres / SQLite development fallback"]
    API --> Redis["Redis"]
    API --> Admin["Admin control center"]
    Admin --> OIDC["Keycloak locally / managed OIDC in production"]
    API --> Obs["Redacted Langfuse + OpenTelemetry"]
    Telephony["Future Jambonz / SIP carrier adapter"] --> API
    API --> Notify["Future notification provider adapters"]
~~~

### Repository layout

~~~text
apps/web/                  React browser experience
packages/contracts/        Shared domain, eligibility, agent, voice contracts
packages/common/           Settings, models, database, cache, IDs, policies
packages/api-types/        Generated/API boundary types
services/agent/            LangGraph, matcher, understanding, retrieval, voice
services/api/              FastAPI routes, auth, rate limits, telemetry, admin
scripts/                   Ingestion, review, RAG sync/query, retention, evals
infra/                     Docker/shared runtime assets
docs/                      Specification, roadmap, operations, handoff documents
~~~

## 5. Implementation status

The distinction below is important: “implemented” means code and tests/scaffolding
exist. It does not mean the deployment-specific credentials, live providers,
native-language review, or production evidence are complete.

### Implemented in the working tree

- FastAPI service with health, OpenAPI, catalog, coverage, text turn, voice turn,
  session, transcript, reset, escalation, RAG, saved-benefit, reminder, admin,
  and telephony-seam routes.
- LangGraph flow:

  ~~~text
  understand -> gather -> match/choose follow-up -> assess escalation -> compose
  ~~~

- Rule-first understanding that works without an OpenAI key, with optional LLM
  understanding when configured.
- Deterministic eligibility matching with pass/fail/unknown outcomes.
- Session memory with pending slots surviving across turns.
- Kannada, Hindi, and English prompt catalogs.
- OpenAI transcription adapter.
- Sarvam Bulbul TTS adapter with cache-first behavior, Redis/in-memory cache, and
  WAV chunk merging.
- Existing data extraction, prefiltering, LLM structuring, database seed,
  spot-check, localization, TTS prewarm, and evaluation scripts.
- OpenAI-hosted Vector Store synchronization and query/answer routes.
- RAG source excerpts, source IDs, relevance information, canonical URLs, and
  citation markers.
- Voice RAG path: audio -> STT -> intent -> hosted RAG -> source-aware response ->
  TTS when the hosted store and providers are configured.
- Source/citation UI and accessible evidence components.
- Browser guest sessions with server-issued bearer tokens and server-derived
  ownership.
- Redis atomic sliding-window rate limiting with IP and session ceilings.
- Admin control center covering operations, conversations, telemetry, escalations,
  benefits/review, providers, languages, audit, system posture, and provenance.
- Admin roles: observer, operator, reviewer, and admin.
- Local static admin token seam for development and OIDC/MFA claim validation for
  the production path.
- Keycloak Docker overlay for local workforce authentication.
- Provider policy controls with expiry, audit history, revisioning, circuit state,
  and rollback.
- Redacted Langfuse and OpenTelemetry instrumentation that is conditional on
  configured endpoints/keys.
- Production Compose topology with multiple API workers, Nginx-built web app,
  Postgres, Redis, Prometheus, Alertmanager, backups, and retention services.
- Guest saved benefits and in-app reminders.
- Provider-neutral, signed /api/telephony/turns audio adapter, disabled by
  default.

### Implemented but still requiring external or live validation

- Full-corpus OpenAI Vector Store sync and a real guarded RAG query have been
  completed at the code/operations level, but source correctness is not the same
  as eligibility correctness.
- Sarvam API access is configured locally by the user, but a recorded, repeatable
  Kannada STT/RAG/TTS test is still required before calling voice production-ready.
- OpenAI fallback must be tested only within the approved budget and with a
  language-quality decision for each fallback voice.
- Admin OIDC validation is implemented, but a deployment-owned IdP redirect flow
  is not complete.
- Langfuse/OpenTelemetry exporters are wired, but a real external collector and
  Langfuse project trace must still be verified.
- Redis limiter logic has a local smoke test; HTTP-level testing through the real
  reverse proxy and multiple workers is still required.
- Backup/restore, alert delivery, retention policy, and multi-instance evidence
  need a staging deployment rather than only Compose files.

### Not complete yet

- Human verification and publication of 20–50 active, source-checked benefits.
- Full Kannada and Hindi multi-turn browser/microphone QA.
- Full WCAG 2.2 AA and low-end-device/browser accessibility QA.
- Production IdP configuration: real users, roles, OTP/MFA, hostname, TLS,
  redirect URI, logout URI, issuer, audience, JWKS, and role claims.
- Production Langfuse and OpenTelemetry endpoint/secret configuration.
- Jambonz-specific adapter, authorized Indian SIP trunk, Indian number, and
  inbound telephony test.
- External SMS, WhatsApp, and email provider adapters.
- Full reviewed translations and voice validation for the eight additional
  languages.
- Complete deployment-specific backup destination, incident alert receiver,
  retention/legal policy, and disaster-recovery rehearsal.
- Full multi-turn/browser QA and a final native-speaker review.

## 6. RAG and data status

### Corpus facts

The current hosted RAG operations document records:

- 2,876 raw extracted records.
- 2,066 exact-content-unique documents.
- About 19.8 MB of UTF-8 source payload.
- Input file: data/structured/raw_text.jsonl.
- Remote store ID: supplied through OPENAI_VECTOR_STORE_ID.
- Local manifest: ignored operational file under data/rag/.

The corpus was machine-extracted from government-scheme material. It is not
automatically safe to use as final eligibility data.

### Why human verification is still required

An LLM can help extract criteria, normalize fields, detect missing values, compare
records, and flag likely errors. It cannot by itself establish that every benefit
is currently active, legally applicable, complete, correctly translated, or safe
to present as an eligibility decision.

For each of the first 20–50 benefits, a reviewer should check:

1. The official source URL and organization.
2. That the scheme is active and not expired or superseded.
3. Eligibility criteria, exclusions, income limits, age limits, and geography.
4. Benefit amount or support description.
5. Application route, required documents, and deadline/rolling status.
6. Whether the structured representation matches the source.
7. Whether the localized summary is faithful and understandable.
8. A verification date and reviewer decision.

Only rows marked human_verified should be published as active eligibility rows.
Machine-structured rows remain inactive or informational until reviewed.

### RAG safety behavior

- RAG answers must cite retrieved sources and use cautious language.
- Retrieved documents are untrusted document data, not instructions to the agent.
- The answer path must not invent dates, amounts, criteria, or application steps.
- The matcher remains the only component allowed to return a structured eligibility
  verdict.
- Voice synthesis removes citation markers from audible text while keeping source
  cards and citation markers visible in the UI.
- Search and answer operations are budget-reserved and fail closed if the key,
  store, or budget ledger is unavailable.

### Relevant commands

~~~bash
uv run python scripts/07_sync_openai_vector_store.py --dry-run
uv run python scripts/07_sync_openai_vector_store.py
uv run python scripts/08_query_rag.py \
  "What support is available for students from low income families?"
~~~

Do not delete the manifest or create a new Vector Store unless a deliberate
re-index is intended.

## 7. Voice and telephony plan

### Current browser voice path

The current clip-based voice implementation is:

~~~text
Browser microphone
  -> multipart /api/voice/turns
  -> OpenAI transcription
  -> intent and slot extraction
  -> structured matcher or hosted RAG
  -> localized response
  -> Sarvam Bulbul TTS
  -> browser playback
~~~

The live acceptance test should include a complete Kannada scholarship
conversation, empty/noisy audio handling, pending-slot follow-up, interruption or
retry behavior, source display, and an equivalent short Hindi flow.

### Telephony plan

Jambonz is a candidate open-source voice/SIP orchestration layer. A carrier or SIP
trunk is still needed to provide the Indian number and PSTN access. The current
generic signed endpoint is a seam, not a finished Jambonz integration.

Recommended first version:

~~~text
Indian caller
  -> authorized carrier/SIP trunk
  -> Jambonz/media layer
  -> Sahaayak voice runtime
  -> Sarvam/OpenAI STT/TTS policy
  -> caller
~~~

Start inbound-only with one number. Avoid outbound campaign calls until consent,
telecom authorization, DLT/notification rules, opt-out behavior, and provider
policies have been reviewed. Open-source telephony software does not eliminate
carrier minute/number charges or Indian telecom obligations.

### Telephony cost reference

As one published reference, Plivo lists an Indian local number at approximately
₹250/month and inbound local calls at approximately ₹0.60/minute. A carrier/SIP
quote may differ and may include KYC, setup, minimum commitments, GST, concurrency,
or streaming fees.

For an early pilot, a reasonable planning envelope is approximately ₹5,000–₹20,000
per month before AI usage, depending on infrastructure and call volume. Production
HA, backups, monitoring, and higher concurrency will cost more.

## 8. SMS, WhatsApp, and email provider options

There is no genuinely free production provider. Trial credits are for development
and verified test recipients; carrier, Meta, email-deliverability, AI, and
infrastructure charges apply after the trial.

### Best current trial options

| Provider | Current trial information | Assessment for Sahaayak |
| --- | --- | --- |
| **Infobip** | 60-day trial; 15 SMS, 15 voice calls, 100 email, 100 WhatsApp messages; no card required; verified-recipient limits | Best all-channel sandbox to test adapters and a small India voice flow |
| **Twilio** | 30-day trial; 100 SMS, 100 WhatsApp, 75 voice minutes, 3,000 emails; no card; verified recipients and predefined content | Best developer experience and bidirectional voice streaming; confirm Indian inbound number availability |
| **Exotel** | Current pricing page advertises a 7-day trial and ₹500 call/SMS usage; Indian virtual-number flow; voice streaming is separate | Best India-first PSTN/number test, but not a complete email provider |
| **MSG91** | Advertises SMS, WhatsApp, email, and voice; demo mode exists, but documentation says there is no voice trial number | Good India multichannel candidate after KYC/payment; not suitable for a free voice test |
| **Plivo** | $10 trial credits and strong voice/SIP/audio-streaming options; India plan limits SMS/WhatsApp self-service availability | Useful for voice experiments, not the all-channel India choice |

Recommended evaluation sequence:

1. Use Infobip for a controlled all-channel smoke test.
2. Use Exotel if a real Indian inbound virtual number is needed for the first
   telephony test.
3. Keep the application’s notification and telephony interfaces provider-neutral.
4. Do not make a production commitment until Indian number provisioning, SIP or
   WebSocket media behavior, KYC, DLT, WhatsApp onboarding, and pricing are
   confirmed in writing.

The free CPaaS credits do not include Sarvam STT/TTS, OpenAI reasoning, OpenAI
transcription, hosting, backups, or monitoring.

## 9. Authentication, privacy, and abuse controls

### Citizen guest sessions

Citizens should not be forced to create an account for initial discovery. The
current design issues a server-generated opaque session ID and one-time bearer
token. Only a hash of the token is stored. Session ownership is derived from the
server-side token, not from a browser-supplied caller ID.

Current default one-minute limits are:

- 20 text turns per session.
- 3 voice turns per session.
- 10 RAG requests per session.
- 60 text, 10 voice, and 30 RAG requests per IP.
- 10 guest-session creations per IP.

Redis is the shared limiter in deployed environments. Production fails closed
with 503 if the shared limiter is unavailable; the in-process limiter is only a
development/test fallback. A 429 includes retry and bounded rate-limit headers.

### Workforce/admin authentication

Local development:

- Dockerized Keycloak.
- Local realm and test users.
- Static admin tokens may be used only as a local/test seam.

Production:

- Managed or properly deployed OIDC provider.
- MFA/OTP or passkey assurance.
- Exact issuer, audience, signature/JWKS, expiry, clock skew, and role validation.
- Roles: observer, operator, reviewer, admin.
- Actor ID derived from the token subject, never from browser input or email.
- Static admin tokens rejected when OIDC is enabled.

The remaining deployment-specific work is to create real Keycloak or managed-IdP
users, configure roles and MFA, provision a hostname and HTTPS, register the
browser client, and set the production redirect and logout URLs.

### Sensitive information

The system can process income, caste/category, disability, education, location,
voice, and transcript data. Therefore:

- Do not log raw caller IDs, audio, transcripts, or sensitive slots by default.
- Hash or pseudonymize identifiers.
- Keep retention periods explicit and configurable.
- Provide session reset/deletion behavior.
- Avoid sending sensitive values to Langfuse or OpenTelemetry exporters.
- Record workforce actions in the append-only audit log.
- Keep all provider keys in deployment secrets, not source control.

## 10. Admin control center

The admin panel is intentionally broader than benefit review. It is an operational
transparency and control center.

Planned/current modules include:

- Overview: uptime/SLO posture, traffic, p50/p95 latency, errors, active sessions,
  quality, corpus verification, escalations, and provider posture.
- Conversations: safe lifecycle metadata and hashed session keys, not raw data by
  default.
- Telemetry: request/turn events correlated by request ID.
- Escalations: operator queue and audited resolution.
- Benefits/review: source evidence, machine-review findings, review decisions,
  publication state, and import history.
- Providers: OpenAI budget ledger, Sarvam telemetry/cache, provider health,
  routing policy, circuit state, and fallback posture.
- Languages: interface, prompt, content, understanding, STT/TTS, and QA readiness.
- Audit log: immutable workforce actions and safe before/after state.
- System: migrations, commit, environment, and redacted configuration posture.

Provider policy changes require a reason, expiry, revision, audit event, and safe
rollback. The admin UI can control policy, but it must not claim that an
unconfigured provider is healthy.

## 11. Accessibility, localization, and visual design

### Accessibility goals

Target WCAG 2.2 AA for the primary text and voice flow. The app should support:

- keyboard navigation and visible focus;
- screen readers and semantic landmarks;
- large readable text and high contrast;
- captions/transcripts for every voice response;
- a text alternative when microphone permission fails;
- reduced-motion behavior;
- clear error/retry states;
- low-end Android and slow-network behavior;
- voice-control and switch-control navigation where practical;
- no color-only status indicators.

### Public-service visual direction

The design may be inspired by familiar Indian public-service patterns, but must not
imitate official government branding or imply government ownership.

Proposed semantic palette:

| Token | Value | Use |
| --- | --- | --- |
| Brand navy | #12345B | Header/high-emphasis surfaces |
| Brand blue | #1E4E85 | Primary controls and links |
| Interactive blue | #245FAE | Hover/interactive emphasis |
| Restrained saffron | #C65D00 | Small highlights/active markers |
| Success green | #147A3E | Verified/success only |
| Warning brown | #8A4B00 | Stale data/uncertainty |
| Danger red | #B42318 | Errors/destructive actions |
| Info blue | #175CD3 | Information/focus |
| Text | #17202A | Main text |
| Muted text | #475467 | Secondary text |
| Border | #D0D5DD | Dividers |
| Surface | #FFFFFF | Main surface |
| Subtle surface | #F6F8FB | Background grouping |
| Focus | #0B57D0 | Visible focus ring |

Use semantic variables rather than hard-coded hex values in components. Use
Noto Sans and script-specific Noto Sans subsets for Kannada, Devanagari, Tamil,
Telugu, Bengali, Gujarati, Malayalam, Gurmukhi, and Odia. Self-host versioned
font assets rather than depending on a remote font request.

Use navy/indigo as the structural color, saffron sparingly, and green only for
positive status. Do not use the State Emblem of India, ministry marks,
india.gov.in-style mastheads, or “Government of India” ownership language without
written authorization.

## 12. Operations and deployment

### Local development

The project supports Docker Compose for local infrastructure. Keycloak is provided
as a local OIDC overlay. Production must not use start-dev, default passwords,
plain HTTP, or sslRequired: NONE on an internet-facing deployment.

Typical local setup:

~~~bash
cp .env.example .env
cp apps/web/.env.example apps/web/.env

docker compose up -d --build
docker compose -f docker-compose.yml -f docker-compose.auth.yml up -d --build
~~~

### Verification commands

~~~bash
uv run pytest -q
uv run ruff check .
uv lock --check
git diff --check
npm run typecheck --workspace @sahaayak/web
npm run build --workspace @sahaayak/web
~~~

### Production foundations already present

- API workers without source bind mounts/reload mode.
- Built web app behind Nginx.
- Private Postgres and Redis Compose networking.
- Prometheus and Alertmanager entry points.
- Postgres and Keycloak backup services.
- Retention script/service for transcript, telemetry, escalation, reminder, audit,
  and expired guest-session records.
- Redis-based multi-instance limiter implementation.

### Production work still required

- Real hostname and TLS certificate.
- Managed OIDC/Keycloak deployment and client registration.
- Independent durable backup storage, restore rehearsal, and documented RPO/RTO.
- Real alert receiver such as email, Slack, PagerDuty, or webhook.
- Legal/privacy-approved retention periods.
- Real Langfuse and OTLP collector endpoints/secrets.
- Reverse-proxy/multiple-worker rate-limit test.
- Deployment smoke test for health, text, voice, deletion, admin authorization,
  and rollback.

## 13. Recommended next build order

### P0 — Required before calling the beta trustworthy

1. Human-review and publish 20–50 benefits with source URLs, dates, criteria,
   application steps, and human_verified status.
2. Complete actionable result/source pages and accessibility QA.
3. Run one tightly budgeted real Kannada voice test, then a short Hindi test.
4. Verify guest-token ownership and Redis rate limits through the HTTP/reverse-proxy
   path with multiple workers.
5. Configure a real OIDC/MFA deployment flow and remove static admin-token use
   from anything public.
6. Configure Langfuse/OpenTelemetry and verify one redacted real trace end to end.
7. Finish backups, restore, retention, alerts, and staging deployment evidence.

### P1 — Beta operations and product depth

1. Finish the admin control center wiring and operational dashboards.
2. Add the benefit review/freshness workflow and reviewer publication controls.
3. Add human escalation/operator console.
4. Add profile correction and returning-user continuity only with explicit consent.
5. Add privacy-aware product analytics and feedback.
6. Harden CI/CD, migrations, backups, and release gates.
7. Add jobs only with accurate deadlines or rolling-status semantics.

### P2 — Optional enhancements after the core is stable

1. Jambonz/carrier telephony adapter and inbound Indian number.
2. Streaming voice, VAD, interruption handling, and lower-latency media transport.
3. Ten-language rollout in reviewed waves.
4. External SMS, WhatsApp, and email reminders.
5. Installable low-bandwidth PWA.
6. Safe sharing and assisted mode for family/community workers.
7. Saved-benefit task checklists, reminders, opt-outs, delivery status, and retries.

## 14. Acceptance gates

Before release, all of the following should be true:

- The primary text and voice flows work without exposing provider secrets.
- At least 20–50 benefits are human-verified and only approved active rows are
  used for final eligibility matching.
- Every displayed result has provenance, a last-verified date, uncertainty wording,
  and an actionable next step.
- Kannada voice completes a multi-turn scholarship flow; Hindi has a short tested
  flow; transcript and text fallback remain available.
- Guest sessions cannot be crossed by changing a client-controlled ID.
- Rate limits are shared across instances and fail safely if Redis is unavailable.
- Admin routes require validated workforce identity and roles.
- Sensitive fields are redacted from logs and traces by default.
- One real redacted Langfuse/OTel trace is visible in staging.
- Backups, restore, retention, alerts, and rollback have evidence.
- Accessibility and native-language QA have been performed, not just automated.
- Provider fallback is explicit, budgeted, auditable, and quality-reviewed.

## 15. Useful documentation in this repository

- docs/spec-v2.md — original product and architecture spec.
- docs/continuation-spec.md — post-scaffold continuation notes and API/implementation
  history.
- docs/implementation-roadmap.md — current product/engineering roadmap and P0/P1/P2
  work packages.
- docs/rag-operations.md — hosted Vector Store ingestion, querying, safety boundary,
  and budget controls.
- docs/admin-operations.md — admin surface, guest auth, rate limits, tracing, and
  provider policy controls.
- docs/production-operations.md — Keycloak, Compose production setup, backups,
  retention, alerts, and limiter smoke tests.
- docs/data-review-2026-08-02.md — data review findings and structured-benefit review
  context.
- docs/infobip-integration-plan.md — detailed Infobip plan for SMS, WhatsApp,
  email, voice transport, reminders, webhooks, consent, admin, and rollout.

## 16. External references discussed

- [Jambonz overview](https://docs.jambonz.org/guides/get-started/jambonz-overview)
- [DoT Enterprise Communication Service authorization](https://eservices.dot.gov.in/enterprise-communication-service-authorisation)
- [TRAI advice for telemarketers](https://trai.gov.in/advice-telemarketers)
- [Infobip free trial](https://www.infobip.com/docs/essentials/getting-started/free-trial)
- [Infobip voice trial](https://www.infobip.com/docs/voice-and-video/getting-started)
- [Infobip SIP trunking](https://www.infobip.com/docs/voice-and-video/sip-trunking)
- [Twilio trial account](https://www.twilio.com/docs/usage/trials)
- [Twilio Media Streams](https://www.twilio.com/docs/voice/media-streams)
- [Twilio India voice pricing](https://www.twilio.com/en-us/voice/pricing/in)
- [Exotel pricing and trial](https://exotel.com/pricing/business-phone-system/)
- [MSG91 channel overview](https://msg91.com/in)
- [MSG91 service deductions and trial limitations](https://msg91.com/help/msg91-common-faq-s)
- [Plivo plans and free credits](https://www.plivo.com/docs/faq/account/plans)
- [Jasmin open-source SMS Gateway](https://docs.jasminsms.com/en/latest/)
- [Postal open-source mail server](https://github.com/postalserver/postal)
- [listmonk self-hosted mailing list manager](https://listmonk.app/docs/)

## 17. Handoff checklist for the teammate

- Read this file and docs/implementation-roadmap.md first.
- Confirm the actual current commit and clean working tree before making changes.
- Never commit .env, API keys, provider secrets, or raw voice/transcript data.
- Treat machine-extracted benefits as inactive until human review is recorded.
- Keep eligibility logic shared across browser, future telephony, and languages.
- Keep external providers behind adapters and policy controls.
- Preserve the $10–$15 OpenAI test/ingestion ceiling unless explicitly changed.
- Add tests and update the roadmap when a work package changes status.
- Record live-provider evidence, native-language QA, and deployment assumptions in
  a dated operations or review document.
