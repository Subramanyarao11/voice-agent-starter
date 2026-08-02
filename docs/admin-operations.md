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

Roles are `observer`, `operator`, `reviewer`, and `admin`. Tokens are static
deployment secrets in this first slice; rotate them through the deployment
secret manager. The current token boundary is deliberately small. Production
must replace it with managed OIDC plus MFA/passkeys before exposing the console
publicly.

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
- Languages: interface, prompt, data, and voice readiness matrix.
- Audit log: workforce actions and safe before/after state.
- System: migration, commit, environment, and redacted configuration posture.

Provider policy mutation is intentionally read-only in this first slice. A safe
emergency switch needs managed workforce identity, MFA, an audited policy store,
expiry/rollback, and provider-specific budget controls; those are the next
security-hardening step rather than a hidden toggle in the dashboard.
