# ─────────────────────────────────────────────────────────────────────────────
#  HSI Enterprise Portal — Frontend Dockerfile (Production)
#  Multi-stage: Node build → Nginx serve
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1: Build React app ──────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package manifests first (for Docker layer caching)
COPY package.json yarn.lock ./

# Install all dependencies (including devDeps needed for build)
# --frozen-lockfile ensures exact versions from yarn.lock
# --network-timeout handles slow package downloads
RUN yarn install --frozen-lockfile --network-timeout 300000 \
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

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://localhost:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
