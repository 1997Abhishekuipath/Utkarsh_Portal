# HSI Enterprise Portal — Production Deployment

One-click Docker deploy on a Linux host. ~5 minutes from clone to live.

## Prerequisites

- Linux host (Ubuntu 22.04+ tested) — bare-metal or VM
- Docker Engine 24+ and the Compose v2 plugin (`docker compose version`)
- Open inbound TCP **80** and **443** (or your custom `HTTP_PORT`/`HTTPS_PORT`)
- A DNS A-record pointing to the host (e.g. `portal.your-company.com`)
- An SSL certificate for that domain (Let's Encrypt or corporate CA)
- An AWS SES sender (or any SMTP provider — see [Sprint B note](#email-mfa-aws-ses))

## Architecture

Five containers wired up by `docker-compose.yml`:

```
                ┌────── 80, 443 ──────┐
                │                     │
[ Internet ]──► nginx (TLS terminator, rate-limit, security headers)
                │   │
                │   ├──► /api/*    →  backend  (FastAPI + uvicorn, port 8001)
                │   ├──► /api/ws   →  backend  (WebSocket — Sprint C live-sync)
                │   └──► /*        →  frontend (nginx serving CRA build, port 80)
                │
                ├── backend ──► db    (PostgreSQL 16, persistent volume)
                ├── backend ──► redis (Redis 7, AOF, persistent volume)
                └── backend ──► AWS SES (OTP email delivery, optional)
```

Volumes: `postgres_data`, `redis_data` — persist across `./setup.sh down/up`.

## Quick start

```bash
# 1. Clone + cd
git clone <your-repo-url> hsi-portal && cd hsi-portal

# 2. Configure environment (REQUIRED — edit every value!)
cp .env.example .env
$EDITOR .env

# 3. Drop SSL certificates (REQUIRED — setup.sh refuses to start without them)
cp /etc/letsencrypt/live/portal.your-domain.com/fullchain.pem ./docker/nginx/ssl/
cp /etc/letsencrypt/live/portal.your-domain.com/privkey.pem   ./docker/nginx/ssl/
sudo chmod 600 ./docker/nginx/ssl/privkey.pem

# 4. Deploy
./setup.sh
```

You'll see a banner with the live URL and admin credentials. Done.

## Day-2 commands

```bash
./setup.sh status     # show running services
./setup.sh logs       # tail logs from all 5 services
./setup.sh restart    # restart the stack (keeps data volumes)
./setup.sh down       # stop & remove containers (keeps data volumes)
./setup.sh            # bring everything back up

# Re-seed users + content (idempotent — safe to run anytime)
docker compose exec backend python seed.py
```

## Email / MFA (AWS SES)

`MFA_ENABLED=true` enables email-based 2FA at login. Two modes:

| AWS creds set in `.env`? | Behaviour |
|:--:|---|
| ✅ Yes | OTP arrives in the user's inbox (real email via SES). |
| ❌ No  | OTP is **logged** to the backend container — see below. Useful for the first few days while waiting on SES production-access approval. |

```bash
# Read OTP from log when AWS creds are unset (dev fallback)
docker compose logs backend | grep DEV-FALLBACK | tail -1
```

### To switch SES on later

1. Create an IAM user with policy: `ses:SendEmail`, `ses:SendRawEmail`
2. Verify your sender domain in the SES console + add DKIM CNAMEs to DNS
3. Submit a "production access" request (default sandbox is 200 emails/day, verified recipients only)
4. Add the keys + region + verified sender email to `.env`:
   ```env
   AWS_REGION=ap-south-1
   AWS_ACCESS_KEY_ID=AKIA...
   AWS_SECRET_ACCESS_KEY=...
   SES_SENDER_EMAIL=noreply@hitachi-systems.com
   ```
5. `./setup.sh restart`  (no rebuild needed)

## SSL certificate management

### Let's Encrypt (free, public domains)

```bash
sudo certbot certonly --standalone -d portal.your-domain.com
sudo cp /etc/letsencrypt/live/portal.your-domain.com/fullchain.pem ./docker/nginx/ssl/
sudo cp /etc/letsencrypt/live/portal.your-domain.com/privkey.pem   ./docker/nginx/ssl/
sudo chown $USER:$USER ./docker/nginx/ssl/*.pem
sudo chmod 600 ./docker/nginx/ssl/privkey.pem
./setup.sh restart
```

Add a host crontab to renew every Sunday at 03:00:

```cron
0 3 * * 0 certbot renew --quiet \
  && cp /etc/letsencrypt/live/portal.your-domain.com/fullchain.pem /path/to/repo/docker/nginx/ssl/ \
  && cp /etc/letsencrypt/live/portal.your-domain.com/privkey.pem   /path/to/repo/docker/nginx/ssl/ \
  && cd /path/to/repo && docker compose exec nginx nginx -s reload
```

### Corporate / internal CA

Drop the chain + key into `./docker/nginx/ssl/` with the expected filenames (`fullchain.pem`, `privkey.pem`).

## Environment variable reference

See `.env.example` for the full list with comments. Key categories:

| Category | Variables |
|---|---|
| Database | `DB_NAME`, `DB_USER`, `DB_PASSWORD` |
| Auth secrets | `JWT_SECRET`, `JWT_REFRESH_SECRET` |
| Initial admin | `ADMIN_EMAIL`, `ADMIN_PASSWORD` |
| Auth policy | `ALLOWED_DOMAIN`, `BCRYPT_ROUNDS`, `ACCESS_TTL_MIN`, `REFRESH_TTL_DAY`, `LOCKOUT_FAILS`, `LOCKOUT_MIN` |
| MFA | `MFA_ENABLED`, `OTP_LENGTH`, `OTP_TTL_MIN`, `OTP_MAX_ATTEMPTS` |
| Redis | `REDIS_URL` |
| AWS SES | `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `SES_SENDER_EMAIL`, `SES_SENDER_NAME` |
| CORS | `CORS_ORIGINS` |
| Frontend | `REACT_APP_BACKEND_URL` |
| Nginx ports | `HTTP_PORT`, `HTTPS_PORT` |

## Troubleshooting

**Build fails with `"yarn.lock": not found`**
The lockfile isn't tracked in git. Either commit `frontend/yarn.lock` (recommended for reproducible builds) or just re-run — the Dockerfile tolerates a missing lockfile and falls back to `yarn install`.

**Build fails with `ImportError: No module named services`**
The backend Dockerfile must `COPY services/ ./services/`. Already fixed in the current Dockerfile, but verify if you forked an old version.

**`subscribers_notified: 0` after admin Publish All**
Either no client tabs are open, or your reverse proxy is stripping the `Upgrade` header. The shipped `docker/nginx/nginx.conf` handles this correctly via the `/api/ws` location block; if you're behind another proxy (Cloudflare, ALB, etc.) ensure WebSocket upgrades are allowed on `/api/ws`.

**`connection reset` / 502 on login**
Check `./setup.sh logs` for backend startup errors. The most common cause is missing env vars (`JWT_SECRET` left blank, etc.) — run preflight again with `./setup.sh`.

**Admin can't log in: "Account locked"**
You hit the brute-force lockout (5 failures → 15 min). Either wait 15 min or unlock via psql:
```bash
docker compose exec db psql -U hsi_user -d hsi_portal \
  -c "UPDATE users SET failed_attempts=0, locked_until=NULL WHERE email='admin@hitachi-systems.com';"
```

## Security checklist before going live

- [ ] `JWT_SECRET` and `JWT_REFRESH_SECRET` are 32+ random chars, different values
- [ ] `ADMIN_PASSWORD` is strong and only known to one person
- [ ] `DB_PASSWORD` is strong (used between containers but still — defense in depth)
- [ ] `MFA_ENABLED=true`
- [ ] AWS SES credentials configured + production access approved
- [ ] `REACT_APP_BACKEND_URL` is the **real** public HTTPS URL (no trailing slash)
- [ ] SSL cert is valid and not expiring in &lt;30 days
- [ ] Server firewall allows only 22 (SSH), 80, 443
- [ ] Backups: `docker volume` snapshots or `pg_dump` cron on host
- [ ] Monitoring: log shipping (e.g. journalctl → Loki) — Sentry coming in Sprint F

## Backups

```bash
# DB dump (run from the host)
docker compose exec db pg_dump -U hsi_user hsi_portal | gzip > hsi-$(date +%F).sql.gz

# Restore
gunzip < hsi-2026-02-15.sql.gz | docker compose exec -T db psql -U hsi_user -d hsi_portal
```

## Upgrading

```bash
git pull
./setup.sh down
docker compose build --no-cache backend frontend
./setup.sh
```

Database migrations are auto-applied at backend startup (idempotent CREATE TABLE / ALTER TABLE).
