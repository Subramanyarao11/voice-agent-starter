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
  and reviewer publication decisions.
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
- Languages: interface, prompt, data, and voice readiness matrix.
- Audit log: workforce actions and safe before/after state, with a CSV export
  of the same redacted projection.
- System: migration, commit, environment, and redacted configuration posture.

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

## Quality and rollback operations

`GET /api/admin/freshness` groups loaded benefits and jobs by source dataset and
reports stale, expired, missing-source, and publication counts. The default
freshness threshold is 90 days and can be changed for an inspection request;
changing the threshold does not change any benefit row.

`make evaluate` runs the versioned, deterministic conversation suite without
provider calls and persists a redacted `EvaluationRun`. The admin quality page
shows pass/fail counts and language coverage; it does not treat a passing
conversation test as human verification of a benefit.

Feature-flag updates and provider-policy updates use append-only revisions.
Rollback writes a new revision containing the prior snapshot, so the audit log
can reconstruct who changed a rollout and why. Exported audit files contain
only the safe before/after projection and can be retained according to the
deployment audit-retention policy.
