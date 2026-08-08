.DEFAULT_GOAL := help
.PHONY: help setup up down infra api web lint fmt test check types seed validate-data migrate \
pipeline extract prefilter structure spotcheck jobs jobs-state jobs-ncs evaluate retention rate-limit-smoke \
notifications notifications-dry-run freshness-scan language-release-check language-ui-check \
language-voice-smoke freshness-worker directory-india-gov directory-demo logs-api ps clean

help: ## Show every available target
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

setup: ## Install Python + JS dependencies and create .env from the template
	uv sync --all-groups
	@if [ -d apps/web ]; then npm install; fi
	@[ -f .env ] || (cp .env.example .env && echo "Created .env — add OPENAI_API_KEY before running the agent.")

up: ## Start the full Docker stack (Postgres, Redis, API)
	docker compose up -d --build

down: ## Stop the Docker stack
	docker compose down

infra: ## Start only Postgres and Redis, for running services on the host
	docker compose up -d postgres redis

api: ## Run the API on the host with reload
	uv run python -m uvicorn sahaayak_api.main:app --reload --port 8000

web: ## Run the browser-mic demo (http://localhost:5173)
	npm run dev --workspace @sahaayak/web

lint: ## Ruff check and mypy (mypy is advisory, not blocking)
	uv run ruff check .
	-uv run mypy packages services

fmt: ## Apply Ruff formatting and import ordering
	uv run ruff check --fix .
	uv run ruff format .

test: ## Run the Python test suite
	uv run python -m pytest -q

check: ## Everything CI runs: lint, tests, and the JS build
	uv run ruff check .
	uv run python -m pytest -q
	@if [ -d apps/web ]; then npm run build; fi

types: ## Regenerate TypeScript API types from the running API's OpenAPI schema
	uv run python scripts/generate_api_types.py

seed: ## Load languages, states, and structured benefits into the database
	uv run python scripts/04_seed_db.py

validate-data: ## Reject active benefit rows without source/review evidence
	uv run python scripts/validate_benefits.py

evaluate: ## Run deterministic conversation regression cases without provider calls
	uv run python scripts/12_run_evaluations.py --seed-demo

retention: ## Preview privacy retention deletions; add --execute explicitly to apply
	uv run python scripts/11_retention.py

rate-limit-smoke: ## Verify two Redis limiter instances share one atomic window
	uv run python scripts/13_rate_limit_smoke.py

notifications: ## Dispatch one batch of due external-channel reminders
	uv run python scripts/14_run_notification_worker.py

notifications-dry-run: ## Show which reminders are due without sending anything
	uv run python scripts/14_run_notification_worker.py --dry-run

freshness-scan: ## Scan active sources and persist deduplicated freshness alerts
	uv run python scripts/15_scan_source_freshness.py

freshness-worker: ## Run one scheduled source-freshness scan
	uv run python scripts/20_run_freshness_worker.py

language-release-check: ## Validate a locale's prompt bundle and review evidence
	uv run python scripts/17_validate_language_release.py --all

language-ui-check: ## Validate script, font, accessibility, and mobile readiness signals
	uv run python scripts/18_validate_language_ui.py

language-voice-smoke: ## Run the budget-capped multilingual Sarvam/OpenAI voice round trip
	uv run python scripts/19_language_voice_smoke.py

migrate: ## Apply all Alembic migrations to the configured database
	uv run python -m alembic upgrade head

pipeline: extract prefilter structure ## Run the full myScheme ingestion pipeline

directory-india-gov: ## Fetch official India.gov department/district directory rows into a pending snapshot
	uv run python scripts/21_ingest_india_gov_directory.py --all-states

directory-demo: ## Import the source-attested Karnataka two-district demo pack as pending rows
	DATABASE_URL="$${DATABASE_URL:-postgresql+psycopg://sahaayak:sahaayak@localhost:5433/sahaayak}" REDIS_URL="" ENV=development uv run python scripts/16_import_department_directory.py --file data/directory/demo/ka-two-districts.json

extract: ## Step 1 — download myScheme PDFs and extract raw text
	uv run --group pipeline python scripts/01_download_and_extract.py

prefilter: ## Step 2 — keyword-narrow the corpus before spending LLM calls
	uv run python scripts/02_prefilter.py --state Karnataka --category education welfare

structure: ## Step 3 — LLM pass into the structured eligibility schema
	uv run python scripts/03_structure_with_llm.py --state-code KA

spotcheck: ## Step 5 — review structured rows against their source text
	uv run python scripts/05_spotcheck.py --n 20

jobs: ## Import current UPSC postings into the inactive job review queue
	uv run --group pipeline python scripts/ingest_upsc_jobs.py --dry-run

jobs-state: ## Preview official Karnataka state recruitment notifications
	uv run --group pipeline python scripts/ingest_state_jobs.py --state-code KA --dry-run

jobs-ncs: ## Import NCS Government jobs (requires an authorized NCS API endpoint)
	uv run --group pipeline python scripts/ingest_ncs_jobs.py --dry-run

logs-api: ## Tail API container logs
	docker compose logs -f api

ps: ## Compose service status
	docker compose ps

clean: ## Remove caches and build artifacts
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache .mypy_cache
