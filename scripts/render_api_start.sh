#!/bin/sh
# Render Free start command. Avoid inline `sh -c '… && …'` in render.yaml —
# Render wraps dockerCommand in a way that treats the whole string as one name.
set -eu

cd /app
/app/.venv/bin/alembic upgrade head
exec /app/.venv/bin/uvicorn sahaayak_api.main:app --host 0.0.0.0 --port "${PORT:-8000}"
