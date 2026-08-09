# Sahaayak security, abuse, and provider-budget controls

This is the deployment runbook for the public submission build. Sahaayak is a
bounded government-benefits, scholarships, jobs, eligibility, application, and
official-department assistant. It is not a general-purpose chatbot.

The controls below are deliberately layered. A guest can still use the demo
without creating an account, but no browser-controlled identifier can grant
access to another session, and no number of guest sessions can bypass the
shared provider budget.

## Threat model

The public surface must assume:

- a visitor can create arbitrary browser sessions and send concurrent requests;
- a visitor can rotate session tokens, user agents, and IP addresses;
- an attacker may send prompt-injection text or place instructions in retrieved
  documents;
- a provider request can time out after the provider has accepted it;
- the application may be scaled to multiple API workers;
- provider credentials, provider billing, Redis, and deployment identity are
  owned by the deployment and must not be exposed to the browser.

The application therefore uses server-owned guest tokens, IP and session
limits, Redis in production, persistent pre-request reservations, fixed scope
refusals, source citations, bounded request bodies, and provider-side account
limits. No single application control is treated as sufficient by itself.

## Guest and channel limits

The checked-in defaults are intentionally conservative. Short windows stop a
burst; daily windows stop a visitor from spreading the same abuse across the
day. The effective limit is the stricter session or IP decision.

| Surface | Per-session/sender | Per-IP/caller | Window |
| --- | ---: | ---: | --- |
| Create guest session | — | 10 | 60 seconds |
| Create guest session | — | 30 | 24 hours |
| Text turn | 20 | 60 | 60 seconds |
| Text turn | 100 | 300 | 24 hours |
| Voice upload turn | 3 | 10 | 60 seconds |
| Voice upload turn | 20 | 60 | 24 hours |
| RAG search/answer | 10 | 30 | 60 seconds |
| RAG search/answer | 30 | 90 | 24 hours |
| OIDC/BFF exchange | — | 10 | 60 seconds |
| OIDC/BFF exchange | — | 30 | 24 hours |
| Streaming voice socket | — | 10 | 60 seconds |
| WhatsApp inbound | 12 | — | 60 seconds |
| WhatsApp inbound | 60 | — | 24 hours |
| Telephony inbound turns | 12 | — | 60 seconds |
| Telephony inbound turns | 60 | — | 24 hours |

Streaming sockets also have a 180-second idle timeout, a five-minute maximum
lifetime, a ten-turn maximum, a 10 MiB audio limit, and a transcript size limit.
These are separate from the turn quotas because an idle WebSocket can consume
resources without producing a turn.

All browser limits are enforced before model or voice work. A rejected request
returns `429` with `Retry-After` and bounded `X-RateLimit-*` headers. A
production Redis failure returns `503` rather than silently falling back to a
process-local limiter. The in-memory limiter is only a development/test seam.

### Identity rules

- `POST /api/browser-sessions` creates the opaque session ID and one-time
  bearer token. Only a hash of the token is stored.
- Turn/session ownership comes from the bearer token, never from a caller ID or
  a client-supplied session ID.
- In production, the API is private behind the bundled Nginx service. Nginx
  overwrites `X-Sahaayak-Client-IP`; the API trusts that header only when
  `TRUST_PROXY_CLIENT_IP=true` is explicitly set by the production Compose
  file. It never trusts an arbitrary `X-Forwarded-For` supplied by a caller.
- WhatsApp and telephony workers use a salted hash of the provider identity and
  apply their own sender/caller quotas before transcription or agent work.

Keep `RATE_LIMIT_KEY_SALT` secret and rotate it only with a planned Redis-key
rollover. A rotation invalidates the usefulness of existing limiter keys.

## Provider budgets

### OpenAI

Every model-backed understanding, RAG search/answer, batch transcription, and
realtime transcription operation reserves a conservative amount in the shared
OpenAI ledger before the network call. The ledger is persistent, file-locked,
atomic, and fail-closed. A timeout or provider error keeps the reservation:
the provider may have processed the request, so the application cannot safely
return that allowance.

`OPENAI_BUDGET_USD` accepts a value from greater than zero through **10.00**;
the code rejects anything above 10.00. For a public submission, set it to
`5.0` unless the demo needs the full `10.0` allowance:

```dotenv
OPENAI_BUDGET_USD=5.0
OPENAI_BUDGET_LEDGER_PATH=/var/lib/sahaayak-usage/openai-budget.json
```

The existing ledger can only move downward: changing the configured value
cannot enlarge a previously recorded ledger allowance.

### Sarvam

Sarvam STT and TTS share one persistent reservation ledger. STT reserves a
fixed amount per request and TTS reserves by character before each sentence
chunk. TTS cache hits do not create a provider reservation. The same hard
application ceiling of **10.00** applies, and the recommended live setting is:

```dotenv
SARVAM_BUDGET_USD=5.0
SARVAM_BUDGET_LEDGER_PATH=/var/lib/sahaayak-usage/sarvam-budget.json
SARVAM_STT_REQUEST_RESERVATION_USD=0.10
SARVAM_TTS_RESERVATION_USD_PER_1000_CHARACTERS=0.10
```

Sarvam's credit contract is not a stable USD meter in the adapter, so the
Sarvam ledger is a conservative application reservation/credit proxy, not an
invoice. Set an actual provider account spending/credit limit as well. The
application cap cannot protect an account if another script or service uses
the same provider key outside Sahaayak.

### Multi-instance requirement

Production Compose mounts both ledgers at `/var/lib/sahaayak-usage` through the
durable `budgetdata` volume. This is safe for multiple workers on one Compose
host because the file lock serializes reservations. If API containers run on
multiple hosts, replace the file ledger with a shared durable budget service or
shared filesystem before scaling out; otherwise each host could have its own
allowance.

The admin provider cards show configured, reserved, observed, remaining, and
per-operation ledger values without exposing paths, keys, prompts, or raw
transcripts. A corrupt or unreadable ledger is an operational incident and
blocks the affected provider until it is restored from a trusted backup.

## Product-scope guardrails

The guardrail is implemented in `services/agent/src/sahaayak_agent/scope.py`
and runs before model-backed understanding and before hosted RAG search.

1. Prompt-injection patterns and unrelated requests such as code generation,
   jokes, weather, sports, stock/crypto, medical treatment, and legal
   representation are refused deterministically.
2. Supported benefit/job/application questions and structured answers to a
   pending slot continue through the graph.
3. An out-of-scope turn returns a fixed local-language redirect and does not
   call OpenAI, RAG, Sarvam, or the general web.
4. The understanding model is constrained to typed intent/slot JSON. It cannot
   answer the user, call tools, choose eligibility, or reveal system data.
5. RAG source excerpts are delimited as untrusted data. The answer prompt
   prohibits following document instructions, inventing rules, or calling a
   result an official eligibility decision.
6. RAG answers must contain valid `[Source N]` citations. If the model returns
   no valid citation, Sahaayak replaces it with a controlled no-citable-answer
   response.
7. Eligibility remains deterministic and source/status-aware; an LLM cannot
   publish a benefit, change a user profile, or override a matcher result.

These are safety boundaries, not a promise that natural-language classification
is perfect. Keep a deterministic regression suite and review new markers when
new product intents are added.

## HTTP and browser hardening

The API and Nginx add `nosniff`, clickjacking, referrer, permissions, and
cross-origin resource policy headers. Production adds HSTS. CORS accepts only
the configured `WEB_BASE_URL`; localhost origins are enabled only in
development/test. The Nginx CSP blocks frames, objects, forms to other
origins, and arbitrary scripts.

Request bodies are bounded at the route and proxy layers. Audio is discarded
after transcription, and telemetry/traces use redacted metadata rather than
raw audio, profile slots, or transcript content.

Admin static tokens are disabled by the production Compose file. Production
admin access must use OIDC with issuer, audience, JWKS, role, PKCE redirect,
HTTPS, and MFA settings. Keep provider keys and identity secrets in a secret
manager or deployment environment, never in the web bundle or repository.

## Launch checklist

Before exposing a public hostname:

- set `ENV=production` and a high-entropy `RATE_LIMIT_KEY_SALT`;
- run Redis and verify `/readyz` reports the shared cache/limiter posture;
- set `OPENAI_BUDGET_USD=5.0` and `SARVAM_BUDGET_USD=5.0` (or explicitly
  choose 10.0), with durable ledger paths;
- configure provider-dashboard spending/credit limits independently;
- use the production Compose file so static admin tokens are disabled and the
  ledger volume is mounted;
- configure HTTPS, the exact `WEB_BASE_URL`, OIDC redirect/logout URLs, and
  the trusted reverse-proxy path;
- keep Infobip, telephony, and messaging channels disabled until credentials,
  templates, consent, webhook verification, and delivery limits are tested;
- verify the admin provider cards show a readable ledger and remaining budget;
- run the offline abuse/guardrail suite before any real-key smoke test;
- run one small Kannada/Hindi/English voice test only after confirming the
  remaining ledger budget and cache posture.

## Verification commands

The following commands are offline and do not spend provider credits:

```bash
./.venv/bin/ruff check .
./.venv/bin/python -m pytest -q
```

The focused security coverage is:

```bash
./.venv/bin/python -m pytest -q \
  tests/test_provider_budget.py \
  tests/test_sarvam_budget.py \
  tests/test_scope_guardrails.py \
  tests/test_api.py
```

For a real deployment, inspect provider ledgers and limiter behavior through
Admin → System/Providers and repeat the HTTP test with two API workers behind
Nginx. Do not delete or reset a ledger to make another smoke test fit inside
the cap; create a new explicitly approved test environment instead.
