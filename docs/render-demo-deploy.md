# Sahaayak Render Free demo (2–3 days)

Short public validation on [Render Free](https://render.com/docs/free). This is **not** the Oracle full-stack path in [free-deployment-guide.md](./free-deployment-guide.md).

**Local development is unchanged.** Keep using `make up` / `docker compose` and `infra/web/Dockerfile` + `nginx.conf` (same-origin `/api` proxy). Render uses `infra/web/Dockerfile.render` + `nginx.render.conf` only.

## What you get

```text
Internet
  -> sahaayak-web  (static SPA, free)
  -> sahaayak-api  (FastAPI, free)  --> OpenAI / Sarvam
       -> sahaayak-postgres (free, expires after 30 days)
       -> sahaayak-redis    (free Key Value)
```

Not included: Keycloak, workers, Prometheus, Caddy, custom domain.

Admin uses a **static token** (`ADMIN_STATIC_TOKENS_ENABLED=true`). Free instances are ~512 MB — too small for Keycloak.

Expect **30–60s cold starts** after ~15 minutes idle.

### Why benefits/languages looked empty, and what we do about it

| Topic | Why | What the demo deploy does |
| --- | --- | --- |
| **0 benefits** | Fresh Postgres has schema only. Pipeline output under `data/structured/` is **gitignored** and excluded from Docker, so it never reaches Render by itself. | Boot runs `scripts/render_demo_bootstrap.py`, which loads committed [`data/demo/benefits.jsonl`](../data/demo/benefits.jsonl) when the catalog is empty. |
| **Only en/hi/kn** | Product launch set. Other locales stay gated until release evidence + `ten_language_rollout`. | With `RENDER_DEMO_OPEN_CATALOG=true`, bootstrap activates all 11 languages and clears state targeting for the short public demo (not a production attestation). |
| **Keycloak / workers** | Free Render is ~512 MB and sleeps; Keycloak + workers do not fit the free Blueprint. | Static admin token only; workers omitted. Use Oracle/paid host for the full stack. |

Refresh `data/demo/benefits.jsonl` from a reviewed export before a formal evaluation if the corpus grows.

## Prerequisites

- Render account ([sign up](https://dashboard.render.com/register); free instances do not require a card)
- This repository on GitHub, connected to Render
- OpenAI + Sarvam keys and existing `OPENAI_VECTOR_STORE_ID` (do not re-ingest)
- A strong random admin token (generate locally; never commit it)

## Deploy

1. Push the branch that contains [`render.yaml`](../render.yaml) to GitHub.
2. In Render: **New → Blueprint** → select the repo → confirm `render.yaml`.
3. When prompted for secrets on `sahaayak-api`, set at least:

| Variable | Notes |
| --- | --- |
| `OPENAI_API_KEY` | Provider key |
| `OPENAI_VECTOR_STORE_ID` | Existing store id |
| `SARVAM_API_KEY` | Provider key (optional if you skip voice TTS) |
| `ADMIN_API_TOKEN` | Long random secret for `/admin` |

`RATE_LIMIT_KEY_SALT` is auto-generated. Budgets default to `$5`.

4. Create the Blueprint. Wait until Postgres, Redis, API, and Web are live.
5. Open the **API** URL: `https://sahaayak-api-….onrender.com/health` (first request may be slow).
6. Open the **Web** URL. If the UI cannot reach the API:
   - Confirm `sahaayak-web` has `VITE_API_BASE_URL` = the API’s `RENDER_EXTERNAL_URL`
   - **Manual Deploy → Clear build cache & deploy** on `sahaayak-web` (Vite bakes the API origin at build time)
7. On `sahaayak-api`, confirm `WEB_BASE_URL` equals the web service public URL (CORS). Redeploy the API if you changed it.

## Post-deploy checks

```bash
curl -fsS https://<api-host>/health
curl -fsS https://<api-host>/readyz
curl -I https://<web-host>/
```

Browser:

1. Create a guest session and complete one text eligibility flow.
2. Run one budgeted voice turn if Sarvam/OpenAI are configured.
3. Open `/admin`, paste `ADMIN_API_TOKEN`, confirm overview loads.

Optional seed (one-off Shell / local against the Render DB only if you know what you are doing):

```bash
# Prefer restoring a private dump or running reviewed seed scripts after migrate.
# Free-tier API boot runs scripts/render_api_start.sh (alembic then uvicorn).
```

## Local vs Render (do not mix)

| Concern | Local Compose | Render Free demo |
| --- | --- | --- |
| Web image | `infra/web/Dockerfile` | `infra/web/Dockerfile.render` |
| API routing | Nginx proxies `/api` → `api:8000` | Browser uses `VITE_API_BASE_URL` |
| `DATABASE_URL` | `postgresql+psycopg://…` in `.env` | Render `postgresql://…` (normalized in settings) |
| Admin auth | Keycloak overlay optional | Static token only |
| Config entrypoint | `docker-compose*.yml` | `render.yaml` |

`make up`, `make api`, and `npm run dev --workspace @sahaayak/web` keep working as before. Bare `postgresql://` URLs from managed hosts are rewritten to `postgresql+psycopg://` only when that scheme is present; local `postgresql+psycopg://` and SQLite are left alone.

## Tear down

After the demo (or when finished):

1. Render Dashboard → Blueprint / project → **Delete** all four resources (web, api, Postgres, Redis).
2. Rotate any admin token and provider keys you pasted into Render if they were shared.

Free Postgres expires after 30 days even if you forget; still delete promptly so secrets and hours do not linger.

## Honest limits

- No SLA; cold starts are normal on Free.
- Ephemeral disks: OpenAI/Sarvam budget ledgers under `/tmp` reset on redeploy.
- Not a government production deployment. For a fuller always-on pilot, use the Oracle guide instead.
