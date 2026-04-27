#!/bin/sh
# ─────────────────────────────────────────────────────────────────────────────
#  HSI Employee Engagement Platform — PostgreSQL WAL Backup Script
#  Sprint F: Daily full base-backup + continuous WAL archiving.
#
#  Runs inside the `backup` service container (postgres:16-alpine image).
#  Environment: PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE — injected
#               from docker-compose.yml.
#
#  Output structure (inside /backup volume):
#    /backup/basebackup/YYYY-MM-DD/   — daily pg_basebackup snapshot
#    /backup/wal/                     — WAL segment files (via archive_command)
#    /backup/last_backup.log          — latest backup run log
# ─────────────────────────────────────────────────────────────────────────────
set -eu

BACKUP_ROOT="/backup"
WAL_DIR="${BACKUP_ROOT}/wal"
BASE_DIR="${BACKUP_ROOT}/basebackup"
LOG_FILE="${BACKUP_ROOT}/last_backup.log"
RETAIN_DAYS="${BACKUP_RETAIN_DAYS:-14}"   # keep 14 days of base backups

mkdir -p "${WAL_DIR}" "${BASE_DIR}"

log() { echo "[$(date -Iseconds)] $*" | tee -a "${LOG_FILE}"; }

run_base_backup() {
    DATE_DIR="${BASE_DIR}/$(date +%Y-%m-%d)"
    mkdir -p "${DATE_DIR}"
    log "Starting base backup → ${DATE_DIR}"
    pg_basebackup \
        -h "${PGHOST:-db}" \
        -p "${PGPORT:-5432}" \
        -U "${PGUSER:-hsi_user}" \
        -D "${DATE_DIR}" \
        --format=tar \
        --gzip \
        --checkpoint=fast \
        --wal-method=stream \
        --progress \
        --verbose \
        2>&1 | tee -a "${LOG_FILE}"
    log "Base backup complete: ${DATE_DIR}"
}

purge_old_backups() {
    log "Purging base backups older than ${RETAIN_DAYS} days…"
    find "${BASE_DIR}" -maxdepth 1 -type d -mtime "+${RETAIN_DAYS}" -exec rm -rf {} + 2>/dev/null || true
    log "Purge complete."
}

# ── Run initial backup on container start ─────────────────────────────────────
log "=== HSI EEP Backup Service started ==="
run_base_backup
purge_old_backups

# ── Schedule: daily base backup at 01:30 IST (20:00 UTC) ─────────────────────
# Add crontab entry for daily backup
(crontab -l 2>/dev/null; echo "0 20 * * * /backup.sh >> /backup/cron.log 2>&1") | sort -u | crontab -

log "=== Cron scheduled: daily base-backup at 01:30 IST (20:00 UTC) ==="
log "=== WAL segments archived to ${WAL_DIR} continuously ==="

# Keep the container alive (crond runs in background above via entrypoint)
exec tail -f "${LOG_FILE}"
