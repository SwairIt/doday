#!/bin/sh
# Production entrypoint: run alembic migrations, then start uvicorn.
# Used by both Dockerfile (CMD) and the systemd unit (ExecStart wrapper).
set -e

# `uvicorn` and `alembic` come from the venv; assume PATH is set in container.
echo "[start.sh] Running database migrations…"
alembic upgrade head

WORKERS="${UVICORN_WORKERS:-2}"
HOST="${UVICORN_HOST:-0.0.0.0}"
PORT="${UVICORN_PORT:-9100}"

echo "[start.sh] Starting uvicorn on ${HOST}:${PORT} with ${WORKERS} workers…"
exec uvicorn app.main:app \
    --host "${HOST}" \
    --port "${PORT}" \
    --workers "${WORKERS}" \
    --proxy-headers \
    --forwarded-allow-ips='*' \
    --no-server-header \
    --access-log
