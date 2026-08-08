# Sahaayak admin operations

The admin surface is a separate `/admin` workforce console. It is an operations
control center, not only a benefit-review page: overview health, redacted
conversations, telemetry, escalations, corpus provenance, provider posture,
language readiness, audit history, import manifests, and system revisions are
all separate modules.

## Local access

Set a local-only token before starting the API and web app:

```bash
export ADMIN_API_TOKEN='use-a-long-random-local-value'
make api
npm run dev
```

Open `/admin/overview` and enter that token. The browser keeps it in
`sessionStorage`, not `localStorage`; the API accepts it only as a bearer token
or `X-Admin-Token` header.

For multiple least-privilege local/staging identities, use JSON configuration:

```bash
export ADMIN_TOKENS_JSON='{"read-only":{"role":"observer","actor_id":"ops-readonly"},"reviewer-secret":{"role":"reviewer","actor_id":"content-reviewer"}}'
```

Roles are `observer`, `operator`, `reviewer`, and `admin`. Static tokens are a
local/test seam. Production should use the managed OIDC path below before
exposing the console publicly.

## Privacy boundary

Overview, conversation, and telemetry views are redacted by default. They do
not return raw caller IDs, transcripts, audio, or sensitive profile slots.
Telemetry stores request route, status, bounded latency, provider, locale/state,
outcome, and a small primitive metadata map. Review decisions and escalation
resolution are written to the append-only `audit_event` table in the same
transaction as the state change.

## Modules

- Overview: request volume, p50/p95 latency, errors, active sessions, quality,
  corpus verification, escalations, and provider posture.
- Conversations: hashed session keys and safe lifecycle metadata.
- Telemetry: request/turn events with request-ID correlation.
- Escalations: operator queue and audited resolution.
- Benefits & review: machine-review findings, source excerpts, import history,
  full public-content editing, immutable versions, reviewer publication
  decisions, and admin-only rollback to a prior approved snapshot.
- Providers: OpenAI budget ledger, Sarvam request/cache telemetry, Redis state,
  and Langfuse configuration.
- Messaging: Infobip channel readiness, consent/contact counts, accepted versus
  delivered/failed/stale callbacks, spend by channel/provider/language, and
  daily/monthly budget posture. This page is an observability surface; it does
  not enable a paid channel by itself.
- Data & evals: freshness by corpus/source, active versus inactive rows,
  human-verification counts, expiry/missing-source warnings, and persisted
  deterministic evaluation runs.
- Feature flags: audited enablement, deterministic percentage rollout, optional
  language/state targeting, and admin-only rollback. A flag is a rollout
  control, not a substitute for provider credentials or content review.
- Languages: interface, prompt, data, voice, native-review, and accessibility
  readiness matrix. Expansion locales require an evidence URL, reviewer
  attestation, complete prompt bundle, all seven approved gates, and explicit
  admin activation before they can reach callers.
- Audit log: workforce actions and safe before/after state, with a CSV export
  of the same redacted projection.
- System: migration, commit, environment, redacted configuration posture, and
  recorded deployment/version comparison.

## Managed workforce authentication

For production, configure a managed OIDC application and set
`ADMIN_OIDC_ENABLED=true`. The API validates the JWT issuer, audience, expiry,
signature, and JWKS key; it also requires the configured MFA assurance in
`amr` or `acr`. The role claim must contain one of `observer`, `operator`,
`reviewer`, or `admin`; missing/unknown roles are reduced to read-only
`observer`. The actor ID is derived from the configured subject claim, never an
email address or a browser-provided value.

When OIDC is enabled, static admin tokens are rejected. Keep
`ADMIN_STATIC_TOKENS_ENABLED=true` only for local/test deployments. The browser
console accepts the short-lived OIDC bearer token issued by the identity
provider; the identity provider remains responsible for login, recovery,
device policy, and MFA enrollment.

## Guest sessions and rate limits

The citizen flow does not require a login. `POST /api/browser-sessions` issues
an opaque session ID and a one-time bearer token; only the token hash is stored.
Turn, RAG, transcript, and reset routes derive ownership from that server-side
token, so changing a session ID cannot cross the authorization boundary.

Redis provides an atomic sliding-window limiter in deployed environments. The
default one-minute limits are 20 text turns and 3 voice turns per session, 10
RAG requests per session, plus IP ceilings of 60/10/30 respectively and 10
guest-session creations per IP. A 429 includes `Retry-After` and bounded
`X-RateLimit-*` headers. Production fails closed with 503 if the shared Redis
limiter is unavailable; the in-process limiter is for development/test only.
Keep `RATE_LIMIT_KEY_SALT` secret because raw IP addresses are never used as
Redis keys.

## Citizen application checklists

Saving a benefit materializes private `ApplicationTask` rows from the current
source-backed document list and application instructions. Tasks are scoped to
the server-owned guest session, never appear in admin aggregates, and support
`pending`, `completed`, and `skipped` states. Re-opening a saved benefit is
idempotent: it adds newly introduced source tasks without resetting completed
progress. Removing the saved benefit also removes its private checklist.

The browser uses `GET /api/sessions/{session_id}/tasks` and
`POST /api/sessions/{session_id}/tasks/{task_id}`. Completion is a personal
planning marker and must not be presented as an official submission or proof
that a document has been accepted by a department.

## Langfuse and OpenTelemetry

Langfuse receives a redacted conversation root and graph-node spans only when
both Langfuse keys are configured. OpenTelemetry exports HTTP, provider, SQL,
Redis, turn, and bounded metric signals through OTLP HTTP when an endpoint is
configured. Inputs, outputs, audio, transcripts, and sensitive slot values are
not passed to either exporter by the application tracing helpers. Admin
telemetry stores only the trace ID and an optional provider trace URL, allowing
an authorized operator to pivot from a request ID without embedding vendor
credentials in the web client.

Configure `OTEL_EXPORTER_OTLP_ENDPOINT` (or explicit trace/metric endpoints),
`OTEL_EXPORTER_OTLP_HEADERS`, and `OTEL_SAMPLE_RATIO` for a collector. Verify a
real trace in the Langfuse project and collector before calling deployment
observability complete; local tests intentionally run with exporters disabled.

## Provider policy controls

`/admin/providers` displays provider health, spend posture, current routing
policies, circuit state, and effective scope. Only the `admin` role can save a
policy. Every change requires a reason and writes the current/next snapshot to
the append-only revision and audit tables. Disabling a provider or opening a
circuit requires an expiry no more than 24 hours in the future. A rollback
creates another audited revision; it never edits history. Expired overrides
fall back to the built-in safe policy in the runtime.

The policy store controls routing and availability; it does not create a
provider implementation or claim that an unconfigured provider is healthy. If
the primary provider is unavailable, the existing text/rules fallback remains
the only safe fallback until a separately tested provider adapter is enabled.

`/admin/providers` also includes provider failure drills for STT, TTS, RAG, and
external reminder channels. These are dry-run projections: they show the
effective feature flag, provider policy, circuit state, configuration gate, and
documented user/operator fallback, but never call a provider, send a message,
or mutate policy. Execute an actual failure drill only in staging with provider
mocks and an explicit change ticket.

`/admin/system` records a redacted `DeploymentRevision` at API startup. The
comparison view diffs the current release against the preceding snapshot using
application/image identifiers, migration and data revisions, prompt/model
versions, active flags, and capability posture. Set `SAHAAYAK_VERSION`,
`GIT_COMMIT_SHA` (or `IMAGE_DIGEST`), and `PROMPT_VERSION` in a deployment so
code releases are distinguishable; no secrets or source contents are stored.

## Quality and rollback operations

`GET /api/admin/freshness` groups loaded benefits and jobs by source dataset and
reports stale, expired, missing-source, and publication counts. It also runs a
deduplicated scan for active/human-verified rows and returns actionable
freshness alerts. The default freshness threshold is 90 days and can be changed
for an inspection request; changing the threshold does not change any benefit
row. `POST /api/admin/freshness/scan` is intended for a scheduler, and
`GET/POST /api/admin/freshness/alerts` lists and acknowledges/resolves alerts.

`PUT /api/admin/benefits/{benefit_id}` replaces the public benefit fields and
always deactivates the row, clears machine-review evidence, and returns it to
`needs_review`. `GET /api/admin/benefits/{benefit_id}/versions` exposes the
immutable snapshot history. `POST /api/admin/benefits/{benefit_id}/rollback`
is admin-only, restores a selected snapshot, and records the rollback as a new
version rather than deleting history. An expected content revision prevents a
stale browser edit from overwriting a newer reviewer action.

`make evaluate` runs the versioned, deterministic conversation suite without
provider calls and persists a redacted `EvaluationRun`. The admin quality page
shows pass/fail counts and language coverage; it does not treat a passing
conversation test as human verification of a benefit.

Feature-flag updates and provider-policy updates use append-only revisions.
Rollback writes a new revision containing the prior snapshot, so the audit log
can reconstruct who changed a rollout and why. Exported audit files contain
only the safe before/after projection and can be retained according to the
deployment audit-retention policy.

The runtime consumes these controls at the boundary that matters, not only in
the admin UI:

- `language_rollout` controls the three launch languages; `ten_language_rollout`
  controls the eight expansion profiles and their deterministic cohort bucket.
- `state_rollout` controls which state rows can create a guest session. Its
  default target list is Karnataka and Delhi; adding a state requires an
  explicit target update.
- `government_jobs` gates job matching for a session, so an unreviewed job
  rollout can be stopped without disabling schemes or scholarships.
- `provider_stt`, `provider_tts`, and `provider_rag` are provider kill
  switches evaluated with the caller's session, language, and state.
- `voice_streaming` gates the WebSocket voice transport.
- `infobip_reminders` is checked when external channel availability is shown,
  when a reminder is created, and again by the worker before sending. In-app
  reminders remain available while the external cohort is paused.

Changing a flag therefore affects new requests and queued work consistently;
the provider-policy and credential gates remain in force as a second safety
layer for paid or sensitive integrations.

## Expansion-language release gate

The eight expansion profiles are registered so product, data, and admin views
can plan them, but they are not advertised as active by default. Add the
reviewed prompt module for the locale, then run:

```bash
uv run python scripts/17_validate_language_release.py --code ta
```

In **Admin → Languages**, a reviewer records the seven gate decisions and
evidence URL. The API rejects prompt approval when the bundle is absent,
requires an explicit attestation, and permits activation only to an admin once
all gates are approved. `ten_language_rollout` remains an independent,
reversible cohort flag. Validate all expansion locales with
`make language-release-check`; it is read-only and exits non-zero until the
external native-speaker and voice/accessibility evidence exists.
