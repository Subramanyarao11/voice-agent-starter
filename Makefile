.DEFAULT_GOAL := help
.PHONY: help setup up down infra api web lint fmt test check types seed \
        pipeline extract prefilter structure spotcheck logs-api ps clean

help: ## Show every available target
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

setup: ## Install Python + JS dependencies and create .env from the template
	uv sync --all-groups
	@[ -d apps/web ] && npm install || true
	@[ -f .env ] || (cp .env.example .env && echo "Created .env — add OPENAI_API_KEY before running the agent.")

up: ## Start the full Docker stack (Postgres, Redis, API)
	docker compose up -d --build

down: ## Stop the Docker stack
	docker compose down

infra: ## Start only Postgres and Redis, for running services on the host
	docker compose up -d postgres redis

api: ## Run the API on the host with reload
	uv run uvicorn sahaayak_api.main:app --reload --port 8000

web: ## Run the browser-mic demo (http://localhost:5173)
	npm run dev --workspace @sahaayak/web

lint: ## Ruff check and mypy (mypy is advisory, not blocking)
	uv run ruff check .
	-uv run mypy packages services

fmt: ## Apply Ruff formatting and import ordering
	uv run ruff check --fix .
	uv run ruff format .

test: ## Run the Python test suite
	uv run pytest -q

check: ## Everything CI runs: lint, tests, and the JS build
	uv run ruff check .
	uv run pytest -q
	@[ -d apps/web ] && npm run build || true

types: ## Regenerate TypeScript API types from the running API's OpenAPI schema
	uv run python scripts/generate_api_types.py

seed: ## Load languages, states, and structured benefits into the database
	uv run python scripts/04_seed_db.py

pipeline: extract prefilter structure ## Run the full myScheme ingestion pipeline

extract: ## Step 1 — download myScheme PDFs and extract raw text
	uv run --group pipeline python scripts/01_download_and_extract.py

prefilter: ## Step 2 — keyword-narrow the corpus before spending LLM calls
	uv run python scripts/02_prefilter.py --state Karnataka --category education welfare

structure: ## Step 3 — LLM pass into the structured eligibility schema
	uv run python scripts/03_structure_with_llm.py --state-code KA

spotcheck: ## Step 5 — review structured rows against their source text
	uv run python scripts/05_spotcheck.py --n 20

logs-api: ## Tail API container logs
	docker compose logs -f api

ps: ## Compose service status
	docker compose ps

clean: ## Remove caches and build artifacts
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache .mypy_cache
