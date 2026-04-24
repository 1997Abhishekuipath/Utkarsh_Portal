# ─────────────────────────────────────────────────────────────────────────────
#  HSI Enterprise Portal — Backend Dockerfile (Production)
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.11-slim AS base

# Install libpq (runtime dep for psycopg2-binary)
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Install Python dependencies ───────────────────────────────────────────────
FROM base AS deps
COPY requirements.prod.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.prod.txt

# ── Final image ───────────────────────────────────────────────────────────────
FROM base AS runner
# Copy installed packages from deps stage
COPY --from=deps /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin

# Copy application source
COPY server.py seed.py entrypoint.sh ./
RUN chmod +x entrypoint.sh

# Create non-root user for security
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser \
    && chown -R appuser:appgroup /app
USER appuser

EXPOSE 8001

# Health check
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/api/')" || exit 1

CMD ["./entrypoint.sh"]
