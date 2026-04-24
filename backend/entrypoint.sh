#!/bin/sh
# Backend container entrypoint — waits for DB, runs seed, starts uvicorn.
set -e

echo "[entrypoint] Running DB seed..."
python seed.py

echo "[entrypoint] Starting uvicorn on 0.0.0.0:8001 ..."
exec uvicorn server:app \
    --host 0.0.0.0 \
    --port 8001 \
    --workers "${UVICORN_WORKERS:-2}" \
    --log-level "${UVICORN_LOG_LEVEL:-info}" \
    --no-access-log
