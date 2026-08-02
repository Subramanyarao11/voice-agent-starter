# Shared image for every Python service. The API and agent differ only by the
# command Compose gives them, so one build serves both.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Dependency layer first: only the manifests are copied, so editing source
# code does not invalidate the (slow) dependency resolution layer.
COPY pyproject.toml uv.lock ./
COPY alembic.ini ./
COPY migrations/ migrations/
COPY packages/contracts/pyproject.toml packages/contracts/
COPY packages/common/pyproject.toml packages/common/
COPY services/agent/pyproject.toml services/agent/
COPY services/api/pyproject.toml services/api/
RUN uv sync --frozen --no-install-workspace --no-dev

COPY packages/ packages/
COPY services/ services/
COPY scripts/ scripts/
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["uvicorn", "sahaayak_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
