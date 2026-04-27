# HSI Enterprise Portal — PRD

## Product Overview
HSI Employee Engagement Platform — converging current Enterprise Portal toward the full PRD scope (`HSI-PRD-EEP-2026-v1.0`). V1 is **web-only**; mobile apps deferred to backlog.

**Date Started:** 2025-02
**Status:** Sprint B complete (MFA + Redis rate-limit + DB-level domain CHECK + Postgres 16 in compose) · NPS/CSAT + Action Intelligence preserved as deep-dives under Customer pillar

---

## Architecture Decision Log

### ADR-001 — Backend stack: FastAPI (deviation from PRD §2.3 "Node + Express + Prisma")
**Date:** Feb 2026
**Decision:** Keep FastAPI + SQLAlchemy + PostgreSQL.
**Rationale:**
- Emergent platform's *verified* auth + AWS-SES integration playbooks are FastAPI-native. Going Node would mean writing security-critical auth code without a vetted playbook → measurably less secure, not more.
- ~3 weeks of rewrite cost avoided; team can ship features instead.
- All PRD non-functional requirements (bcrypt 12, JWT rotation, OTP MFA, rate limiting, audit log) are equally implementable in FastAPI.
**Trade-off:** Documented deviation from PRD literal stack. Stakeholder sign-off required at next review.

### ADR-002 — Mobile deferred (V1 web-only)
**Date:** Feb 2026
**Decision:** React Native employee + admin mobile apps move to backlog.
**Rationale:** Get web-only V1 to 500 pilot users first; learn before building mobile.

### ADR-003 — Existing pages preserved
**Date:** Feb 2026
**Decision:** NPS/CSAT (`/apps/nps-csat`) and Action Intelligence (`/apps/survey-builder`) pages retained as deep-dives under the Customer pillar in the new pillar-nav model.

---

## Architecture
- **Frontend:** React 19 + TailwindCSS + Shadcn UI + lucide-react
- **Backend:** FastAPI + SQLAlchemy 2.0 (Python 3.11)
- **Database:** PostgreSQL 15 (local dev) / 16 (production target) via SQLAlchemy
- **Auth:** JWT access (15 min) + opaque refresh (30 d, one-time-use rotation), bcrypt cost 12
- **Session store:** `sessions` table (DB-backed; Redis added in Sprint F for rate limiting)
- **Audit:** `audit_log` table — all auth + admin actions
- **Design:** Outfit + IBM Plex Sans fonts, #CC0000 primary red

---

## User Personas (PRD §3.3)
- **Super Admin:** Platform-wide; only super_admin can grant super_admin
- **Admin:** User approvals, role management, content CMS, notifications, audit log
- **Manager:** Team management, approvals, full app access
- **Employee:** Standard app access, dashboard, XP earning + tracking

---

## Core Requirements
1. JWT auth with email/password (Sprint A ✅) + email OTP MFA (Sprint B)
2. PostgreSQL — all data
3. Four roles: super_admin, admin, manager, employee
4. Domain lock (`@hitachi-systems.com` only) — enforced at API (Sprint A ✅) + DB CHECK (Sprint A.2)
5. HSI branding (Hitachi Systems India, red #CC0000)
6. Responsive enterprise dashboard

---

## Implemented (Phase 1 + Sprint A)

### Auth (Sprint A — hardened Feb 2026 · Sprint B — MFA & rate limiting)
- [x] User registration with role selection (employee | manager only — admins seeded)
- [x] **Domain restriction** at API + **DB-level CHECK constraint** (`@hitachi-systems.com` only)
- [x] **Pending-approval flow** — `is_active=False` until admin approves
- [x] **bcrypt cost 12**
- [x] **JWT access (15 min) + refresh (30 d) with one-time-use rotation**
- [x] **`sessions` table** with device/IP/UA tracking
- [x] **Account lockout** — 5 failed attempts → 15 min (HTTP 423)
- [x] **`audit_log` table** — every auth + admin action logged
- [x] **`super_admin` role**
- [x] `/auth/check-email`, `/auth/refresh`, `/auth/logout`, `/auth/logout-all`
- [x] `/admin/users/pending`, `/admin/users/:id/approve`, `/admin/users/:id/reject`
- [x] `/admin/audit-log`
- [x] **Email OTP MFA** (Sprint B) — 6-digit, SHA-256 hashed, 10 min TTL, 3 attempts max
- [x] **AWS SES integration** with branded HTML email + dev log-fallback
- [x] **`/auth/verify-otp`, `/auth/resend-otp`** endpoints
- [x] **`/auth/forgot-password`, `/auth/reset-password`** — OTP-driven, revokes all sessions
- [x] **Rate limiting** — 10 login/min/IP, 5 OTP/hr/email, 1 resend/30s, 5 verify/min, 5 reset/hr (Redis-backed with in-memory fallback)
- [x] **Redis service** in docker-compose (redis:7-alpine, AOF, 256MB LRU)
- [x] Frontend: 2-step login UX (inline OTP step, masked email, resend countdown), forgot-password page

### User Model Expansion
- [x] Added: `display_name`, `employee_id`, `practice`, `designation`, `art_tags[]`, `avatar_url`, `phone`, `date_of_birth`, `date_joined`, `is_verified`, `approved_by`, `approved_at`, `last_login_at`, `failed_attempts`, `locked_until`

### Home Dashboard (`/`)
- [x] Red hero header + quick stats
- [x] MY DASHBOARDS (5 metric cards)
- [x] MY APPS QUICK ACCESS (5 buttons)
- [x] ALL APPLICATIONS grid (9 apps)
- [x] RECENT ACTIVITY feed
- [x] MY SCORE gauge
- [x] UPCOMING events
- [x] PENDING ACTIONS
- [x] LEADERBOARD (live DB)
- [x] ANNOUNCEMENTS
- [ ] **Sprint C will replace** with PRD home (EDM carousel + quotes + activity grid + 4 pillar cards)

### Pages
- [x] /login — HSI branding · **2-step OTP login** when MFA enabled
- [x] /register — pending-approval flow + domain hint
- [x] /forgot-password — OTP-driven password reset
- [x] / — current Enterprise Portal home (will be replaced Sprint C)
- [x] /apps/:appId — 9 placeholder pages
- [x] /apps/nps-csat — NPS & CSAT (kept; will fold under Customer pillar)
- [x] /apps/survey-builder — Action Intelligence (kept; will fold under Customer pillar)
- [x] /admin — User management panel

---

## Seed Users (post Sprint A)

| Email | Password | Role |
|-------|----------|------|
| superadmin@hitachi-systems.com | SuperAdmin@123 | super_admin |
| admin@hitachi-systems.com | Admin@123 | admin |
| manager@hitachi-systems.com | Manager@123 | manager |
| employee@hitachi-systems.com | Employee@123 | employee |
| priya@hitachi-systems.com | Employee@123 | employee |
| kiran@hitachi-systems.com | Employee@123 | employee |
| ananya@hitachi-systems.com | Employee@123 | employee |

All 7 are pre-approved (`is_active=True`). New self-service registrations land in pending queue.

---

## Dashboard Data
- Stats, Activities, Announcements, Pending Actions, Upcoming: **MOCKED** (replaced in Sprint C+)
- Leaderboard: **LIVE** (queries PostgreSQL)
- Audit log: **LIVE**
- Pending users: **LIVE**

---

## Docker Production Deployment
- [x] `/app/docker-compose.yml` — db + backend + frontend + nginx
- [x] `/app/backend/Dockerfile` — multi-stage, non-root, healthcheck
- [x] `/app/backend/entrypoint.sh` — DB-wait + seed + uvicorn
- [x] `/app/frontend/Dockerfile` — multi-stage build → nginx serve, tolerates missing yarn.lock
- [x] `/app/docker/nginx/nginx.conf` — TLS 1.2/1.3, HTTP→HTTPS, rate-limit, security headers
- [x] `/app/docker/nginx/ssl/` — placeholder dir + README
- [x] `/app/.env.example` — full env template inc. AWS SES placeholders for Sprint B
- [x] `/app/setup.sh` — one-click deploy with preflight (hard-fail on missing certs, no self-signed)
- [x] Custom HTTP/HTTPS host ports via `${HTTP_PORT}` / `${HTTPS_PORT}`

---

## Prioritized Backlog (post Sprint B)

### P0 — Sprint C (Pillars + EDM + CMS + WebSocket)
- [ ] `pillars`, `pillar_icons`, `edm_slides`, `motivational_quotes` tables + admin CRUD
- [ ] Replace home `/` with PRD home: EDM carousel + quotes + activity grid + 4 pillar cards
- [ ] 4 pillar pages (Customer / Innovator / Employee / Shareholder) — hero + sub-EDM + 6-col icon grid
- [ ] Fold NPS/CSAT + Action Intelligence under Customer pillar
- [ ] WebSocket "Publish All" live-sync (≤5s)

### P1 — Sprint D (XP & Incentive Engine)
- [ ] `best_practices`, `replications`, `xp_ledger`, `incentive_calculations`, `tech_days`, `certifications`
- [ ] XP balance trigger + ART multipliers + INR rate config
- [ ] Quarterly payout state machine
- [ ] XP Detail + Incentive Statement modal panels

### P2 — Sprint E (Notifications + Auto-triggers)
- [ ] `notifications` + `user_notifications` tables
- [ ] Admin notification composer
- [ ] 7 auto-triggers + birthday `pg_cron` (50 XP)

### P2 — Sprint F (Hardening + Ops)
- [ ] pgBouncer transaction pooling
- [ ] Sentry + WAL backups
- [ ] TLS 1.3 only
- [ ] WCAG 2.1 AA audit
- [ ] 4 DB roles (`hsi_api`/`hsi_admin`/`hsi_readonly`/`hsi_migrate`) with SCRAM-SHA-256

### Deferred (Future)
- React Native mobile apps (employee + admin)
- MinIO file storage (when first feature needs it)
- Push notifications

---

## Out-of-Scope (V1)
- Mobile apps (RN) — deferred per ADR-002
- Node.js stack — superseded by ADR-001
- MinIO — deferred until needed

