# ─────────────────────────────────────────────────────────────────────────────
#  HSI Enterprise Portal — Frontend Dockerfile (Production)
#  Multi-stage: Node build → Nginx serve
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1: Build React app ──────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package manifests first (for Docker layer caching)
# yarn.lock* uses a wildcard so the build still works if the lockfile is
# missing from the repo (BuildKit allows zero matches for a glob).
COPY package.json ./
COPY yarn.lock* ./

# Install all dependencies (including devDeps needed for build)
# Use --frozen-lockfile when yarn.lock is present (reproducible build),
# otherwise fall back to a regular install with a warning.
RUN if [ -f yarn.lock ]; then \
      echo "Using yarn.lock — reproducible install" && \
      yarn install --frozen-lockfile --network-timeout 300000; \
    else \
      echo "WARNING: yarn.lock missing — running 'yarn install' (not reproducible). Commit frontend/yarn.lock for deterministic builds." && \
      yarn install --network-timeout 300000; \
    fi \
    && yarn cache clean

# Copy remaining source files
COPY . .

# Build-time environment variable — baked into the JS bundle by CRA/CRACO
ARG REACT_APP_BACKEND_URL=https://your-domain.com
ENV REACT_APP_BACKEND_URL=$REACT_APP_BACKEND_URL

# Disable CI=true warnings-as-errors for cleaner Docker builds
ENV CI=false

# Build production bundle (uses craco build from package.json scripts)
RUN yarn build

# ── Stage 2: Serve static files with Nginx ────────────────────────────────────
FROM nginx:1.25-alpine AS runner

# Remove default nginx config
RUN rm /etc/nginx/conf.d/default.conf

# Copy SPA nginx config
COPY nginx-app.conf /etc/nginx/conf.d/default.conf

# Copy built static files from builder stage
COPY --from=builder /app/build /usr/share/nginx/html

# Non-root user for security
RUN chown -R nginx:nginx /usr/share/nginx/html \
    && chmod -R 755 /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD ["sh", "-c", "test -f /usr/share/nginx/html/index.html || exit 1"]

CMD ["nginx", "-g", "daemon off;"]
