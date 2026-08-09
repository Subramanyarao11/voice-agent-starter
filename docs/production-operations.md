# Production operations

This document describes the deployment and operations foundation.
It is intentionally explicit about which pieces are ready to run and which
still require deployment-owned credentials or policies.

For the complete public-abuse, provider-budget, and guardrail runbook, see
[security-operations.md](security-operations.md).

## Development with local Keycloak

Keycloak is the open-source OIDC provider for the workforce console. Citizens
remain anonymous guest users; only `/admin` uses workforce authentication.

```bash
cp apps/web/.env.example apps/web/.env
docker compose -f docker-compose.yml -f docker-compose.auth.yml up -d --build
```

Open `http://localhost:8080`, sign into the Keycloak admin console using the
bootstrap credentials from `.env`, select the `sahaayak` realm, and create an
operator user. Assign the `admin` or `observer` realm role. For the MFA gate,
configure OTP for the user and sign in at `http://localhost:5173/admin`.

The API validates the browser access token's issuer, audience, signature,
expiry, role, and MFA assurance. In the Docker profile the browser-visible
issuer is `http://localhost:8080/...`, while the API uses the internal
`http://keycloak:8080/...` discovery/JWKS URLs. This split is deliberate: the
token `iss` claim must stay the browser-visible issuer while the API still has
to reach the IdP over the Compose network.

The realm import is a bootstrap convenience. Do not use `start-dev`, default
passwords, or `sslRequired: NONE` for an internet-facing deployment.

## Production Compose

The production file removes API source bind mounts and reload mode, runs
multiple API workers, serves the built web app behind Nginx, and keeps Postgres
and Redis on private Compose networking. The web bind address is configurable;
Prometheus and Alertmanager bind to loopback by default so they are not public
administrative surfaces.

```bash
docker compose -f docker-compose.production.yml up -d --build
docker compose -f docker-compose.production.yml --profile workers up -d \
  notification-worker freshness-worker
docker compose -f docker-compose.production.yml --profile ops up -d \
  postgres-backup retention
```

Required production variables include `POSTGRES_PASSWORD`,
`RATE_LIMIT_KEY_SALT`, the admin authentication configuration, and all model
or provider secrets that the deployment intends to activate. Use a secret
manager rather than committing `.env`.

Before a release, open **Admin → System** and inspect **Release readiness
gates**. This is a local, secret-free preflight: `not_configured` means code
cannot safely attempt the integration, while `external_review` means the
settings exist but a deployment-owned check is still required. The latter
includes OIDC redirect/MFA login, Infobip sender/template/webhook delivery,
NCS authorization, Langfuse/OTel trace receipt, real microphone QA, and
authoritative directory approval.

The `workers` profile now defines the long-running `freshness-worker` and
`notification-worker`; both use the same immutable Python image as the API.
Run the scheduled freshness process alongside the API and notification worker.
Set `FRESHNESS_STALE_DAYS` and `FRESHNESS_SCAN_INTERVAL_SECONDS` explicitly in
the deployment environment. It writes only redacted source-freshness alerts;
reviewers still decide whether a source is refreshed or a benefit is
republished.

The production Keycloak overlay can be added after its hostname, TLS, and
client redirect URI have been changed from localhost:

```bash
docker compose \
  -f docker-compose.production.yml \
  -f docker-compose.auth.yml \
  up -d --build
```

For a public single-host deployment, `docker-compose.oracle.yml` adds Caddy automatic
HTTPS and overrides Keycloak with a production, reverse-proxy-aware start
command. It must be merged after both files above:

```bash
docker compose \
  -f docker-compose.production.yml \
  -f docker-compose.auth.yml \
  -f docker-compose.oracle.yml \
  --profile workers \
  --profile ops \
  up -d --build
```

Set `WEB_BIND_ADDRESS`, `KEYCLOAK_BIND_ADDRESS`,
`PROMETHEUS_BIND_ADDRESS`, and `ALERTMANAGER_BIND_ADDRESS` to `127.0.0.1`
for this topology. Only Caddy ports 80/443 should be internet-accessible. See
[free-deployment-guide.md](free-deployment-guide.md) for DNS, Keycloak client,
restore, smoke-test, backup, and rollback steps.

## Backups and restore

The `postgres-backup` service writes custom-format application dumps into the
named `pgbackups` volume. When the Keycloak overlay is enabled,
`keycloak-backup` does the same for the separate identity database. Both remove
files older than `BACKUP_RETENTION_DAYS`. Backups must still be copied to
independent durable storage; a Docker volume on the same host is not a
disaster-recovery plan.

```bash
docker compose -f docker-compose.production.yml --profile ops logs postgres-backup
docker compose -f docker-compose.production.yml --profile ops run --rm \
  --entrypoint pg_restore postgres-backup \
    --clean --if-exists \
    --dbname="postgresql://sahaayak@postgres:5432/sahaayak" \
    /backups/<file>.dump

docker compose \
  -f docker-compose.production.yml -f docker-compose.auth.yml \
  --profile ops logs keycloak-backup
docker compose \
  -f docker-compose.production.yml -f docker-compose.auth.yml \
  --profile ops run --rm --entrypoint pg_restore keycloak-backup \
    --clean --if-exists \
    --dbname="postgresql://keycloak@keycloak-db:5432/keycloak" \
    /backups/<keycloak-file>.dump
```

Use a separate restore database for this test in a real environment; the example
uses the Compose-internal `postgres` hostname and must not be run against the
production database without an explicit restore plan. Each backup service injects
its database password through `PGPASSWORD`.

## Retention and alerts

`scripts/11_retention.py` defaults to a dry run. It removes old transcript,
telemetry, non-open escalation, reminder, audit, and expired guest-session rows
according to the configured windows. Review the legal/support policy before
enabling the scheduled `retention` service.

Prometheus scrapes the privacy-safe `/metrics` endpoint. The checked-in rules
cover target down, database unavailable, and sustained 5xx spikes. The local
Alertmanager receiver is intentionally a no-op; replace it with the
deployment's email, PagerDuty, Slack, or webhook receiver before launch.

## Multi-instance limiter smoke test

The API limiter uses one atomic Redis Lua script, so independent workers share
the same sliding window. Run the smoke test against the Compose Redis service:

```bash
REDIS_URL=redis://localhost:6380/0 uv run python scripts/13_rate_limit_smoke.py
```

Before launch, repeat this at the HTTP layer with the actual reverse proxy and
worker count. Configure a trusted proxy chain before using forwarded client IP
headers; the current default intentionally trusts only the direct socket.

## Optional feature boundaries

- Ten-language rollout profiles are registered in the admin readiness matrix,
  but inactive until prompts, translated benefit content, STT/TTS evidence,
  and accessibility review exist.
- Saved benefits and in-app reminders are implemented for guest sessions.
  External SMS/email/WhatsApp delivery is not enabled without a verified
  contact/account channel.
- `/api/telephony/turns` is a signed, provider-neutral audio adapter. It is
  disabled by default and returns the same text/audio contract as the browser
  voice route.
- `evals/conversations.json` and `scripts/12_run_evaluations.py` provide a
  deterministic regression set that does not call OpenAI or Sarvam.
