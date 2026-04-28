#!/bin/bash
# PostgreSQL bootstrap — install if missing, init DB, create user/db, seed, then keep running

set -e

# Install PostgreSQL if not present
if ! /usr/lib/postgresql/15/bin/postgres --version &>/dev/null 2>&1; then
    echo "[pg-boot] Installing PostgreSQL 15..."
    apt-get update -qq
    apt-get install -y postgresql postgresql-contrib
    echo "[pg-boot] PostgreSQL installed."
fi

# Init data dir if missing
if [ ! -f /var/lib/postgresql/15/main/PG_VERSION ]; then
    echo "[pg-boot] Initialising data directory..."
    mkdir -p /var/lib/postgresql/15/main
    chown -R postgres:postgres /var/lib/postgresql
    sudo -u postgres /usr/lib/postgresql/15/bin/initdb -D /var/lib/postgresql/15/main
fi

# Remove stale PID / shared memory
rm -f /var/lib/postgresql/15/main/postmaster.pid
ipcrm --all shm 2>/dev/null || true

# Start postgres in background first
echo "[pg-boot] Starting PostgreSQL..."
sudo -u postgres /usr/lib/postgresql/15/bin/postgres \
    -D /var/lib/postgresql/15/main \
    -c config_file=/etc/postgresql/15/main/postgresql.conf &
PG_PID=$!

# Wait for it to be ready
for i in $(seq 1 30); do
    if sudo -u postgres /usr/lib/postgresql/15/bin/pg_isready -q 2>/dev/null; then
        echo "[pg-boot] PostgreSQL is ready."
        break
    fi
    sleep 1
done

# Create role + database (idempotent)
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='hsi_user'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE USER hsi_user WITH PASSWORD 'hsi_password123';"

sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='hsi_portal'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE DATABASE hsi_portal OWNER hsi_user;"

sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE hsi_portal TO hsi_user;" 2>/dev/null || true

echo "[pg-boot] DB setup complete. Running seed..."
cd /app/backend && /root/.venv/bin/python seed.py 2>&1 || echo "[pg-boot] Seed skipped or already done."

echo "[pg-boot] Setup complete. PostgreSQL running (PID $PG_PID)."
# Wait on the postgres process so supervisor tracks it
wait $PG_PID
