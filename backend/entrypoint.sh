#!/bin/sh
# Backend container entrypoint — waits for DB, runs seed, starts uvicorn.
set -e

# Extract host:port from DATABASE_URL for the readiness probe.
# DATABASE_URL format: postgresql://user:pass@host:port/db
_DB_HOST=$(echo "${DATABASE_URL:-pgbouncer:6432}" | sed 's|.*@||' | cut -d'/' -f1 | cut -d':' -f1)
_DB_PORT=$(echo "${DATABASE_URL:-pgbouncer:6432}" | sed 's|.*@||' | cut -d'/' -f1 | cut -d':' -f2)
_DB_PORT=${_DB_PORT:-6432}

echo "[entrypoint] Waiting for database at ${_DB_HOST}:${_DB_PORT} ..."
_retries=30
until python -c "
import socket, sys
s = socket.socket()
s.settimeout(2)
try:
    s.connect(('${_DB_HOST}', ${_DB_PORT}))
    s.close()
    sys.exit(0)
except Exception:
    sys.exit(1)
" 2>/dev/null; do
    _retries=$((_retries - 1))
    if [ "$_retries" -le 0 ]; then
        echo "[entrypoint] ERROR: Database not reachable after 30 attempts. Aborting."
        exit 1
    fi
    echo "[entrypoint] Database not ready — retrying in 2s (${_retries} attempts left)..."
    sleep 2
done
echo "[entrypoint] Database is reachable."

echo "[entrypoint] Running DB seed..."
python seed.py

echo "[entrypoint] Starting uvicorn on 0.0.0.0:8001 ..."
exec uvicorn server:app \
    --host 0.0.0.0 \
    --port 8001 \
    --workers "${UVICORN_WORKERS:-2}" \
    --log-level "${UVICORN_LOG_LEVEL:-info}" \
    --no-access-log
