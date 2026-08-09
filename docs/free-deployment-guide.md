# Sahaayak free deployment guide

**Decision date:** 2026-08-09  
**Target:** a public, budget-capped validation environment—not a government production SLA

## 1. Recommendation

Deploy the complete stack on one **Oracle Cloud Always Free Ampere A1 VM** and
run the checked-in Docker Compose stack behind Caddy:

```text
Internet
  -> Caddy (automatic HTTPS)
      -> React/Nginx web -> FastAPI
      -> Keycloak
  -> private Docker network
      -> PostgreSQL + Redis + workers + monitoring + backups
  -> hosted providers
      -> OpenAI Vector Store/STT + Sarvam TTS
```

This is the only reviewed no-monthly-charge option that can keep this complete
topology together. Oracle currently documents an Always Free Arm allowance of
2 OCPUs and 12 GB memory, plus Always Free block storage. The offer has no fixed
expiry, but capacity can be unavailable and Oracle may reclaim an instance it
classifies as idle. Account creation commonly requires phone and card
verification. Read the current [Oracle Free Tier terms and limits](https://docs.oracle.com/iaas/Content/FreeTier/freetier.htm)
and [Always Free resource details](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)
before provisioning.

Use **Northflank Sandbox** as the managed fallback. It currently advertises two
always-on free services, one free database, and two free cron jobs. That is a
good fit for the web/API and workers, but it is not enough by itself for the
web, API, Keycloak, PostgreSQL, and Redis topology. A Northflank deployment
therefore needs a split stack such as Cloudflare Pages, Neon PostgreSQL,
Upstash Redis, and either an external OIDC service or a separately hosted
Keycloak. See [Northflank pricing](https://northflank.com/pricing).

## 2. Why the other free choices are weaker

| Option | Current free shape | Fit for Sahaayak |
| --- | --- | --- |
| Oracle Cloud Always Free | Persistent Arm VM, currently up to 2 OCPUs/12 GB for Always Free tenancies; Always Free block storage | **Recommended full-stack validation environment.** Enough room for Docker Compose and Keycloak, but self-managed and subject to capacity/idle-reclamation policy. |
| Northflank Sandbox | 2 always-on services, 1 database, 2 cron jobs | **Managed fallback.** Good UX and no sleeping, but requires external Redis/data/auth services or a reduced deployment. |
| Cloudflare Pages | 500 builds/month and 100 custom domains on Free | Excellent static React host, but it cannot run FastAPI, PostgreSQL, Redis, workers, or Keycloak. |
| Google Cloud Run | Free request/CPU/memory allowances with an active billing account | Viable for a stateless API, but the complete stack still needs managed data/auth services; WebSockets have a maximum request duration and reconnect requirement. |
| Koyeb Free | 0.1 vCPU, 512 MB, one web service; no free worker or volume; forced scale-to-zero | Too small for this API/agent topology and unsuitable for persistent Keycloak/workers. Its free PostgreSQL allowance is also limited. |
| Neon + Upstash | Free PostgreSQL and Redis quotas | Useful data services for a split deployment, not an application host. |

References: [Cloudflare Pages limits](https://developers.cloudflare.com/pages/platform/limits/),
[Cloud Run pricing](https://cloud.google.com/run/pricing),
[Cloud Run WebSockets](https://cloud.google.com/run/docs/triggering/websockets),
[Koyeb instance limits](https://www.koyeb.com/docs/reference/instances),
[Koyeb pricing FAQ](https://www.koyeb.com/docs/faqs/pricing),
[Neon pricing](https://neon.com/pricing), and
[Upstash Redis pricing](https://upstash.com/pricing/redis).

Free offers change. Recheck these official pages immediately before creating
an account or entering a payment method.

## 3. What the checked-in deployment adds

The deployment uses three Compose files:

- `docker-compose.production.yml` builds the immutable web/API images, runs
  PostgreSQL, Redis, monitoring, optional workers, retention, and backups.
- `docker-compose.auth.yml` adds Keycloak and its separate PostgreSQL database.
- `docker-compose.oracle.yml` adds Caddy and changes Keycloak from development
  mode to a reverse-proxy-aware production start command.

The Caddy configuration is in `infra/caddy/Caddyfile`. A valid public hostname
automatically enables certificate management and HTTP-to-HTTPS redirection;
see [Caddy automatic HTTPS](https://caddyserver.com/docs/automatic-https).
Keycloak remains HTTP-only on the private Docker network and publishes an HTTPS
issuer through Caddy. This follows Keycloak's documented
[reverse-proxy hostname model](https://www.keycloak.org/server/hostname) and
avoids its insecure `start-dev` mode for the public deployment.

## 4. Required ownership before deployment

Prepare these items first:

- an Oracle Cloud account and an available Always Free Ampere shape;
- one domain with two DNS names, for example `sahaayak.example.org` and
  `auth.sahaayak.example.org`;
- SSH access to the VM;
- the private GitHub repository deploy key or another safe way to copy the
  repository;
- the current PostgreSQL application backup, transferred privately;
- OpenAI and Sarvam keys with provider-side spending controls where available;
- the existing OpenAI Vector Store ID—do **not** ingest the corpus again;
- a real email address for ACME certificate notifications.

Do not copy `.env` into Git, a presentation, an issue, or a chat. The deployment
host should be the only place containing the production `.env`.

## 5. Provision the Oracle VM

1. Create a VCN with internet connectivity.
2. Create an Ubuntu 24.04 Arm instance using `VM.Standard.A1.Flex`.
3. Select **2 OCPUs and 12 GB RAM**, staying inside the currently documented
   Always Free tenancy allowance.
4. Allocate 80–100 GB of boot volume. Oracle documents up to 200 GB total
   Always Free block-volume capacity; leave room for backups.
5. Add a reserved public IP so DNS does not change after a restart.
6. In the Network Security Group, allow:
   - TCP 22 from your own current IP only;
   - TCP 80 from `0.0.0.0/0` and `::/0`;
   - TCP 443 from `0.0.0.0/0` and `::/0`;
   - UDP 443 if HTTP/3 is desired.
7. Do not expose 5432, 6379, 8000, 8080, 9090, or 9093 publicly.

Oracle's [instance creation guide](https://docs.oracle.com/en-us/iaas/Content/Compute/Tasks/launchinginstance.htm)
covers VCN, SSH-key, and instance creation. If the console reports no A1 host
capacity, try another availability domain or retry later; do not accidentally
select a paid shape.

## 6. Point DNS at the VM

Create two `A` records using the reserved public IP:

```text
sahaayak.example.org       -> <VM_PUBLIC_IP>
auth.sahaayak.example.org  -> <VM_PUBLIC_IP>
```

Wait until both names resolve from an external network:

```bash
dig +short sahaayak.example.org
dig +short auth.sahaayak.example.org
```

Caddy cannot obtain public certificates until DNS points to the VM and ports
80/443 are reachable.

## 7. Install the host runtime

SSH into the VM, update it, install Git, and install Docker Engine using
Docker's current [Ubuntu installation instructions](https://docs.docker.com/engine/install/ubuntu/).
Then enable Docker and allow the deployment user to invoke it:

```bash
sudo apt-get update
sudo apt-get install -y git ca-certificates curl
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
```

Log out and back in after changing Docker group membership. Verify the Arm
architecture and Compose plugin:

```bash
uname -m
docker version
docker compose version
```

`uname -m` should report `aarch64`. All images used by this stack are selected
from official multi-architecture image families, but the first build is still
an explicit deployment test.

## 8. Clone and configure

```bash
git clone git@github.com:Subramanyarao11/voice-agent-starter.git
cd voice-agent-starter
cp .env.example .env
chmod 600 .env
```

Set at least the following values in `.env`:

```dotenv
ENV=production
LOG_JSON=true

SAHAAYAK_DOMAIN=sahaayak.example.org
AUTH_DOMAIN=auth.sahaayak.example.org
ACME_EMAIL=ops@example.org
WEB_BASE_URL=https://sahaayak.example.org

WEB_BIND_ADDRESS=127.0.0.1
KEYCLOAK_BIND_ADDRESS=127.0.0.1
PROMETHEUS_BIND_ADDRESS=127.0.0.1
ALERTMANAGER_BIND_ADDRESS=127.0.0.1

POSTGRES_PASSWORD=<random-long-secret>
KEYCLOAK_ADMIN_USERNAME=<non-default-bootstrap-name>
KEYCLOAK_ADMIN_PASSWORD=<random-long-secret>
KEYCLOAK_DB_PASSWORD=<different-random-long-secret>
RATE_LIMIT_KEY_SALT=<random-hex-secret>

ADMIN_STATIC_TOKENS_ENABLED=false
ADMIN_OIDC_ENABLED=true
ADMIN_OIDC_ISSUER_URL=https://auth.sahaayak.example.org/realms/sahaayak
ADMIN_OIDC_DISCOVERY_URL=http://keycloak:8080/realms/sahaayak/.well-known/openid-configuration
ADMIN_OIDC_JWKS_URL=http://keycloak:8080/realms/sahaayak/protocol/openid-connect/certs
ADMIN_OIDC_AUDIENCE=sahaayak-admin
ADMIN_OIDC_REQUIRED_AMR=otp

VITE_ADMIN_OIDC_ISSUER=https://auth.sahaayak.example.org/realms/sahaayak
VITE_ADMIN_OIDC_CLIENT_ID=sahaayak-admin
VITE_ADMIN_OIDC_REDIRECT_URI=https://sahaayak.example.org/admin/callback
VITE_ADMIN_OIDC_SCOPE=openid profile email
VITE_ADMIN_ALLOW_MANUAL_TOKEN=false

OPENAI_API_KEY=<secret>
OPENAI_VECTOR_STORE_ID=<existing-store-id>
OPENAI_BUDGET_USD=5.0
OPENAI_BUDGET_LEDGER_PATH=/var/lib/sahaayak-usage/openai-budget.json

SARVAM_API_KEY=<secret>
SARVAM_BUDGET_USD=5.0
SARVAM_BUDGET_LEDGER_PATH=/var/lib/sahaayak-usage/sarvam-budget.json
```

Generate independent random values rather than reusing passwords:

```bash
openssl rand -hex 32
openssl rand -base64 36
```

Also set the encryption/hash keys required by any enabled citizen profile,
application, messaging, or contact feature. Leave Infobip, NCS, telephony,
citizen OIDC, Langfuse, and OTLP settings disabled/empty until their external
configuration is complete. The admin **System** page will display the remaining
release gates honestly.

## 9. Validate the merged deployment before starting it

Use the same file order for every command:

```bash
export SAHAAYAK_COMPOSE="docker compose -f docker-compose.production.yml -f docker-compose.auth.yml -f docker-compose.oracle.yml"
$SAHAAYAK_COMPOSE config --quiet
$SAHAAYAK_COMPOSE config > /tmp/sahaayak-compose-rendered.yml
```

Review the rendered file without publishing it. Confirm that:

- no secret has accidentally become blank;
- public ports are limited to 80/443;
- host-bound web, Keycloak, Prometheus, and Alertmanager ports use
  `127.0.0.1`;
- the OIDC issuer is the public HTTPS auth hostname;
- the discovery/JWKS URLs use the internal `keycloak:8080` hostname;
- OpenAI and Sarvam budget caps are `5.0` or lower.

The shell variable above is only a convenience for the current SSH session.
If it causes quoting trouble, repeat the three `-f` arguments directly.

## 10. Restore the prepared application database

The hosted vector knowledge base persists independently, so deployment does
not require another embedding/ingestion run. Transfer the existing PostgreSQL
backup over SSH instead:

```bash
scp /path/to/sahaayak-postgres-<timestamp>.dump \
  ubuntu@<VM_PUBLIC_IP>:/tmp/sahaayak-restore.dump
```

Start only the stateful dependencies:

```bash
$SAHAAYAK_COMPOSE up -d postgres redis keycloak-db keycloak
$SAHAAYAK_COMPOSE ps
```

Copy and restore the application dump:

```bash
$SAHAAYAK_COMPOSE cp /tmp/sahaayak-restore.dump postgres:/tmp/sahaayak-restore.dump
$SAHAAYAK_COMPOSE exec -T postgres \
  pg_restore --clean --if-exists --no-owner \
  -U sahaayak -d sahaayak /tmp/sahaayak-restore.dump
```

This is destructive to the target `sahaayak` database. Run it only on the new
host, before public traffic, and retain the source backup off-host.

Apply repository migrations after the restore:

```bash
$SAHAAYAK_COMPOSE run --rm api python -m alembic upgrade head
```

If no backup is available, run migrations and the reviewed seed/import commands
instead. Do not publish machine-reviewed eligibility rows merely to make the
catalog look larger.

## 11. Start the complete stack

```bash
$SAHAAYAK_COMPOSE \
  --profile workers \
  --profile ops \
  up -d --build
```

`workers` starts notification and source-freshness workers. `ops` starts
retention and local database-backup services. External notification channels
remain dormant unless explicitly enabled.

Inspect startup state:

```bash
$SAHAAYAK_COMPOSE ps
$SAHAAYAK_COMPOSE logs --tail=150 api web caddy keycloak
```

The first Arm build can take several minutes. A failing service should be fixed
before public validation; repeated restarts are not a readiness signal.

## 12. Configure Keycloak for the public hostname

The checked-in realm file is intentionally local-only. After first startup:

1. Open `https://auth.sahaayak.example.org/admin/`.
2. Sign in with the bootstrap credentials and select the `sahaayak` realm.
3. Open **Clients → sahaayak-admin**.
4. Set **Valid redirect URIs** to exactly
   `https://sahaayak.example.org/admin/callback`.
5. Set **Valid post logout redirect URIs** to
   `https://sahaayak.example.org/*`.
6. Set **Web origins** to `https://sahaayak.example.org`.
7. Keep the client public, Authorization Code flow enabled, Direct Access
   Grants disabled, and PKCE method `S256`.
8. In realm SSL settings, require SSL for external requests.
9. Create named users—do not use the bootstrap account for routine access.
10. Assign only the needed realm role: `observer`, `operator`, `reviewer`, or
    `admin`.
11. Require and enroll OTP for every workforce user.
12. Sign out of the bootstrap account and test a fresh `/admin` login.

The API rejects an invalid issuer, audience, signature, expiry, role, or
required authentication method. If login loops, compare the token's `iss`
value with `ADMIN_OIDC_ISSUER_URL` before changing any validation rule.

## 13. End-to-end deployment smoke test

From outside the VM:

```bash
curl -fsS https://sahaayak.example.org/health
curl -I https://sahaayak.example.org/
curl -I https://auth.sahaayak.example.org/realms/sahaayak/.well-known/openid-configuration
```

From the VM:

```bash
$SAHAAYAK_COMPOSE exec -T api python -c \
  "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/readyz').read().decode())"
$SAHAAYAK_COMPOSE exec -T redis redis-cli ping
$SAHAAYAK_COMPOSE exec -T postgres pg_isready -U sahaayak -d sahaayak
```

Then perform one browser pass:

- create a guest session;
- complete one text eligibility flow;
- open a result and its official source;
- save it, compare it, and create an application checklist;
- run exactly one budgeted voice turn;
- clear the conversation and confirm saved work remains;
- sign into `/admin` with OTP;
- inspect overview, benefits, directory, escalations, providers, flags,
  languages, audit, and system readiness;
- sign out and verify the admin page is protected.

Record the smoke-test result, deployed commit, migration version, provider
budgets, and any intentionally disabled release gates as release evidence.

## 14. Backups and restart safety

Named Docker volumes preserve PostgreSQL, Redis AOF, Keycloak, Caddy
certificates, provider budget ledgers, Prometheus, Alertmanager, and local dump
files across `docker compose down` and VM restarts. Do not use `down -v`.

List the volumes before maintenance:

```bash
$SAHAAYAK_COMPOSE ps
docker volume ls --filter name=sahaayak
```

Check the local backup jobs:

```bash
$SAHAAYAK_COMPOSE --profile ops logs --tail=100 postgres-backup keycloak-backup
```

Copy encrypted backups to a different account or storage system. A named volume
on the same VM protects against container replacement, not VM or account loss.
Test restoration into a separate database before calling the backup policy
complete.

## 15. Updates and rollback

Before updating:

```bash
git fetch origin
git status --short
$SAHAAYAK_COMPOSE exec -T postgres \
  pg_dump --format=custom --username=sahaayak --dbname=sahaayak \
  > /tmp/sahaayak-predeploy.dump
test -s /tmp/sahaayak-predeploy.dump
```

Record the current commit, create/verify a fresh database dump, then deploy the
intended commit:

```bash
git rev-parse HEAD
git pull --ff-only
$SAHAAYAK_COMPOSE run --rm api python -m alembic upgrade head
$SAHAAYAK_COMPOSE --profile workers --profile ops up -d --build
```

Application rollback means checking out a known-good commit and rebuilding.
Database rollback is a separate, deliberate restore operation; never run a
downgrade or restore against public traffic without a tested plan. The admin
deployment comparison view records application/schema differences but does not
replace infrastructure rollback.

## 16. Security and cost checklist

Before sharing the URL:

- [ ] DNS and TLS work for both public names.
- [ ] Only ports 80/443 are internet-accessible; SSH is source-IP restricted.
- [ ] `.env` is mode `600`, absent from Git, and not present in build logs.
- [ ] Static admin tokens are disabled; Keycloak OIDC + OTP is verified.
- [ ] Guest session tokens and Redis-backed fail-closed rate limits are active.
- [ ] OpenAI and Sarvam code-level ledgers are set to `$5` or less for the pilot.
- [ ] Provider-account alerts/limits are configured separately where supported.
- [ ] Infobip, NCS, and telephony remain disabled unless real credentials and
      approvals have been tested.
- [ ] Logs/traces do not contain income, caste, disability, phone numbers,
      voice audio, bearer tokens, or raw profile data.
- [ ] Raw microphone recordings are not retained.
- [ ] Only human-approved benefit rows are active for eligibility decisions.
- [ ] The public disclaimer says Sahaayak offers guidance and links to official
      sources; it does not issue a government decision.
- [ ] The database backup exists both on-host and off-host.
- [ ] The validation operator has a text fallback if a live speech/provider call fails.

The application budget ledger is a defense-in-depth cap, not a replacement for
provider billing alerts, key rotation, account restrictions, and monitoring.

## 17. Northflank managed fallback

If Oracle A1 capacity is unavailable, use this reduced split topology:

```text
Cloudflare Pages       -> React/PWA static build
Northflank service 1   -> FastAPI container
Northflank service 2   -> Keycloak container (only if free memory is sufficient)
Northflank jobs        -> notification + freshness scheduled runs
Neon                   -> application PostgreSQL
Upstash                -> TLS Redis rate limiting/cache
Northflank DB or Neon  -> Keycloak PostgreSQL
```

Important consequences:

- build `VITE_API_BASE_URL` with the public API origin;
- configure explicit API CORS for only the Pages/custom domain;
- use `rediss://` for Upstash and a pooled PostgreSQL URL for Neon;
- run migrations as a Northflank job before releasing the API;
- make WebSocket reconnect behavior part of the smoke test;
- verify the free Keycloak service has enough memory before relying on it;
- keep a second off-platform database backup;
- do not describe this as a single-provider deployment.

If Keycloak cannot fit, publish only the citizen application and keep `/admin`
unreachable until a proper OIDC deployment exists. Do not weaken the admin
gate or enable a public manual token just to fit a free quota.

## 18. Honest availability statement

The recommended environment is **pilot infrastructure**, not a free production
guarantee. Free tiers have no Sahaayak-controlled SLA, can change,
and may reclaim or suspend resources. A real public-service launch requires
paid capacity, managed backups, tested disaster recovery, on-call ownership,
privacy/legal review, accessibility evidence, provider contracts, and verified
benefit/directory data.
