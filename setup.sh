#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
#  HSI Enterprise Portal — One-Click Production Deployment Script
#  Usage:  ./setup.sh            # build + start everything
#          ./setup.sh down       # stop + remove containers
#          ./setup.sh logs       # tail all service logs
#          ./setup.sh status     # show running services
#          ./setup.sh restart    # restart all services
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Colors ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
log()  { echo -e "${BLUE}[setup]${NC} $*"; }
ok()   { echo -e "${GREEN}[ ok ]${NC} $*"; }
warn() { echo -e "${YELLOW}[warn]${NC} $*"; }
die()  { echo -e "${RED}[fail]${NC} $*" >&2; exit 1; }

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

ENV_FILE="$SCRIPT_DIR/.env"
ENV_EXAMPLE="$SCRIPT_DIR/.env.example"
SSL_DIR="$SCRIPT_DIR/docker/nginx/ssl"
SSL_CERT="$SSL_DIR/fullchain.pem"
SSL_KEY="$SSL_DIR/privkey.pem"

# ── Detect docker compose command (v2 plugin vs legacy v1 binary) ─────────────
detect_compose() {
    if docker compose version >/dev/null 2>&1; then
        COMPOSE="docker compose"
    elif command -v docker-compose >/dev/null 2>&1; then
        COMPOSE="docker-compose"
    else
        die "Neither 'docker compose' nor 'docker-compose' is installed. Install Docker Desktop or Docker Engine with the Compose plugin first."
    fi
    ok "Using: $COMPOSE"
}

# ── Preflight checks ──────────────────────────────────────────────────────────
preflight() {
    log "Running preflight checks..."

    # 1. docker daemon reachable
    command -v docker >/dev/null 2>&1 || die "Docker is not installed. See https://docs.docker.com/get-docker/"
    docker info >/dev/null 2>&1 || die "Docker daemon is not running or you lack permissions. Start Docker and try again."
    ok "Docker daemon reachable"

    # 2. compose
    detect_compose

    # 3. .env file
    if [[ ! -f "$ENV_FILE" ]]; then
        if [[ -f "$ENV_EXAMPLE" ]]; then
            warn ".env not found — copying .env.example → .env"
            cp "$ENV_EXAMPLE" "$ENV_FILE"
            die "Edit .env with your real values (DB password, JWT secret, admin creds, REACT_APP_BACKEND_URL), then re-run: ./setup.sh"
        else
            die ".env file is missing and no .env.example template found."
        fi
    fi
    ok ".env file found"

    # 4. Mandatory env vars present & non-default
    # shellcheck disable=SC1090
    set -a; source "$ENV_FILE"; set +a
    local missing=()
    for var in DB_NAME DB_USER DB_PASSWORD JWT_SECRET ADMIN_EMAIL ADMIN_PASSWORD REACT_APP_BACKEND_URL; do
        if [[ -z "${!var:-}" ]]; then
            missing+=("$var")
        fi
    done
    if [[ ${#missing[@]} -gt 0 ]]; then
        die "The following required env vars are empty in .env: ${missing[*]}"
    fi
    # Guard against leftover defaults
    if [[ "${JWT_SECRET}" == "change-me-to-a-random-32-char-string" ]]; then
        die "JWT_SECRET in .env is still the default placeholder. Generate a real one:  openssl rand -hex 32"
    fi
    if [[ "${DB_PASSWORD}" == "change-this-strong-db-password" ]]; then
        die "DB_PASSWORD in .env is still the default placeholder. Set a strong password."
    fi
    if [[ "${REACT_APP_BACKEND_URL}" == "https://portal.your-domain.com" ]]; then
        die "REACT_APP_BACKEND_URL in .env is still the default placeholder. Set it to your real HTTPS URL."
    fi
    ok "Environment variables validated"

    # 5. SSL certificates — hard-fail (per user decision: no self-signed fallback)
    mkdir -p "$SSL_DIR"
    if [[ ! -f "$SSL_CERT" || ! -f "$SSL_KEY" ]]; then
        echo ""
        warn "════════════════════════════════════════════════════════════════════"
        warn "  SSL certificate files are missing."
        warn "  Expected:"
        warn "    $SSL_CERT"
        warn "    $SSL_KEY"
        warn ""
        warn "  Deployment is ABORTED to avoid starting nginx in a broken state."
        warn ""
        warn "  To obtain certificates, see:"
        warn "    $SSL_DIR/README.md"
        warn "════════════════════════════════════════════════════════════════════"
        die "Add real SSL certs, then re-run: ./setup.sh"
    fi
    # basic readability
    [[ -r "$SSL_CERT" && -r "$SSL_KEY" ]] || die "SSL cert files exist but are not readable. Fix permissions."
    ok "SSL certificates found"

    log "Preflight complete."
}

# ── Commands ──────────────────────────────────────────────────────────────────
cmd_up() {
    preflight
    log "Building images (this may take a few minutes on first run)..."
    $COMPOSE build
    ok "Images built"

    log "Starting stack in detached mode..."
    $COMPOSE up -d
    ok "Stack started"

    log "Waiting for services to become healthy (up to 120s)..."
    local deadline=$(( $(date +%s) + 120 ))
    while (( $(date +%s) < deadline )); do
        if $COMPOSE ps --format json 2>/dev/null | grep -q '"Health":"healthy"' \
           || $COMPOSE ps | grep -qE '(healthy|running)'; then
            sleep 3
            local unhealthy
            unhealthy=$($COMPOSE ps | grep -Ec '(unhealthy|Exit|Restarting)' || true)
            if [[ "$unhealthy" -eq 0 ]]; then
                break
            fi
        fi
        sleep 3
    done

    echo ""
    $COMPOSE ps
    echo ""
    ok "──────────────────────────────────────────────────────────────────"
    ok "  HSI Enterprise Portal is up!"
    ok "  URL:       ${REACT_APP_BACKEND_URL}"
    ok "  Admin:     ${ADMIN_EMAIL}"
    ok "  Logs:      ./setup.sh logs"
    ok "  Stop:      ./setup.sh down"
    ok "──────────────────────────────────────────────────────────────────"
}

cmd_down() {
    detect_compose
    log "Stopping and removing containers..."
    $COMPOSE down
    ok "Stack stopped"
}

cmd_logs()    { detect_compose; $COMPOSE logs -f --tail=100; }
cmd_status()  { detect_compose; $COMPOSE ps; }
cmd_restart() { detect_compose; $COMPOSE restart; ok "Services restarted"; }

# ── Dispatch ──────────────────────────────────────────────────────────────────
case "${1:-up}" in
    up|"")   cmd_up ;;
    down)    cmd_down ;;
    logs)    cmd_logs ;;
    status)  cmd_status ;;
    restart) cmd_restart ;;
    -h|--help|help)
        cat <<EOF
HSI Enterprise Portal — deployment helper

Usage:
  ./setup.sh           Build & start the production stack (default)
  ./setup.sh down      Stop & remove containers (data volume preserved)
  ./setup.sh logs      Tail logs from all services
  ./setup.sh status    Show running services
  ./setup.sh restart   Restart all services
  ./setup.sh help      Show this help

Before first run:
  1. cp .env.example .env   &&  edit with real values
  2. Drop SSL certs in ./docker/nginx/ssl/  (fullchain.pem & privkey.pem)
  3. ./setup.sh
EOF
        ;;
    *) die "Unknown command: $1   (try: ./setup.sh help)" ;;
esac
