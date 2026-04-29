# HSI Enterprise Portal — PRD

## Product Overview
HSI Employee Engagement Platform — converging current Enterprise Portal toward the full PRD scope (`HSI-PRD-EEP-2026-v1.0`). V1 is **web-only**; mobile apps deferred to backlog.

**Date Started:** 2025-02
**Status:** Sprint C complete (Pillars + EDM + CMS + WebSocket live-sync) · NPS/CSAT + Action Intelligence folded under Customer pillar

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
- [x] /login — HSI branding · 2-step OTP login when MFA enabled
- [x] /register — pending-approval flow + domain hint
- [x] /forgot-password — OTP-driven password reset
- [x] / — **PRD home** (EDM carousel + 4 pillar cards + motivational quote + activity grid + leaderboard sidebar) (Sprint C)
- [x] /pillar/:slug — **4 pillar pages** (Customer/Innovator/Employee/Shareholder) with hero + sub-EDM + 6-col icon grid (Sprint C)
- [x] /apps/:appId — placeholder pages
- [x] /apps/nps-csat — NPS & CSAT (folded under Customer pillar)
- [x] /apps/survey-builder — Action Intelligence (folded under Customer pillar)
- [x] /admin — User management panel
- [x] /admin/content — **Content management** (4 tabs: Pillars / Icons / EDM / Quotes + Publish All) (Sprint C)

### Sprint C — Content & Live Sync (Feb 2026)
- [x] 5 new tables: `pillars`, `pillar_icons`, `edm_slides`, `motivational_quotes`, `publish_history`
- [x] 16 admin CRUD endpoints (4 entity types × full GET/POST/PUT/DELETE) — all admin/super_admin gated, all audited
- [x] Public read endpoints: `GET /api/content/home`, `GET /api/content/pillars/:slug`
- [x] **WebSocket live-sync** at `/api/ws` — `services/ws.py` connection manager
- [x] `POST /api/admin/publish` broadcasts to all subscribers within milliseconds
- [x] Reusable components: `EdmCarousel`, `PillarCard`, `IconGrid`, `QuoteRibbon`, `TopBar`
- [x] `useLiveContent` hook with auto-reconnect (1s → 15s exponential backoff)
- [x] LIVE/OFFLINE indicator in red top bar
- [x] Seed: 4 pillars + 24 icons + 7 EDM slides + 5 quotes — idempotent

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

## Prioritized Backlog (post Sprint C)

### P0 — Sprint D (XP & Incentive Engine)
- [ ] `best_practices`, `replications`, `xp_ledger`, `incentive_calculations`, `tech_days`, `certifications`
- [ ] XP balance trigger + ART multipliers + INR rate config
- [ ] Quarterly payout state machine
- [ ] XP Detail + Incentive Statement modal panels
- [ ] Replace mock `/dashboard/stats` and `/dashboard/score` with live data from xp_ledger

### P1 — Sprint E (Notifications + Auto-triggers)
- [ ] `notifications` + `user_notifications` tables (replaces mock `/dashboard/announcements`)
- [ ] Admin notification composer with target by all/user/role/practice/department + urgent flag + deep links
- [ ] 7 auto-triggers (Birthday, Approved, Replication, Reminder, New Practice, Award, Announcement)
- [ ] Birthday `pg_cron` (50 XP)

### P2 — Sprint F (Hardening + Ops)
- [ ] pgBouncer transaction pooling
- [ ] Sentry + WAL backups
- [ ] TLS 1.3 only
- [ ] WCAG 2.1 AA audit
- [ ] 4 DB roles (`hsi_api`/`hsi_admin`/`hsi_readonly`/`hsi_migrate`) with SCRAM-SHA-256
- [ ] Multi-instance WebSocket via Redis pub/sub (current ws.py is single-instance only)

### Deferred (Future)
- React Native mobile apps (employee + admin)
- MinIO file storage (when first feature needs it — likely Sprint D for best-practice attachments)
- Push notifications (web push or mobile)

---

## Out-of-Scope (V1)
- Mobile apps (RN) — deferred per ADR-002
- Node.js stack — superseded by ADR-001
- MinIO — deferred until needed

---

## Changelog (Sprint D follow-ups — Apr 2026)

### `cancelled` terminal state for incentive_calculations
- New status `cancelled` joins existing enum `('draft','approved','paid','on_hold')`.
- DB CHECK constraint updated via idempotent migration in `_ensure_edm_tag_columns`.
- New endpoint: **`POST /api/admin/payout/calc/{calc_id}/cancel`** — accepts optional `reason` (audited). Rejects (409) if status is already `paid` or `cancelled`. Cancelled rows are excluded from approve / mark-paid sweeps.
- `hold` endpoint now also rejects `cancelled` rows with 409.
- `calcs` GET response counts dict now exposes all 5 buckets.

### Payroll-ref validation
- `^[A-Z0-9-]{3,40}$` regex enforced on `mark-paid` body — invalid input returns **400** with the pattern in the error detail. Auto-generated default `PAYROLL-{quarter}` (e.g. `PAYROLL-2026-Q2`) is also validated.

### Frontend modal pattern (replaces window.confirm)
- `AdminPayoutPage.jsx` ships an in-app `<Modal>` primitive — used for Approve, Mark Paid, and Cancel-calc flows. Every dialog has a `data-testid` and a danger variant for paid actions.
- Per-row Cancel button + reason capture textarea added.
- Status legend now shows 5 chips (draft, approved, paid, on_hold, cancelled).

### TopBar JWT fix
- `TopBar.jsx` notification bell + mark-read endpoints switched from `credentials: 'include'` (cookies) to `headers: { ...authHeader() }` (JWT). Eliminates the 2× 401s previously logged on first `/admin/console` load.

### Tests
- `/app/backend/tests/test_sprint_d_followups.py` — **10/10 passing**: payroll_ref invalid-format 400 (3 cases), valid-format persists, cancel happy-path + idempotency, hold-after-cancel 409, cancel-after-paid 409, counts include cancelled bucket, RBAC 403 for employee.

## Changelog (Sprint D continuation — Apr 2026)

### Payout state machine (`incentive_calculations.status`)
- **Transitions implemented**: `draft → approved → paid` with `on_hold` side-state.
- **Endpoints (admin/super_admin only, all audited)**:
  - `POST /api/admin/payout/{quarter}/approve` — bulk `draft → approved`; idempotent for paid/on_hold rows.
  - `POST /api/admin/payout/{quarter}/mark-paid` — bulk `approved → paid`, accepts optional `payroll_ref` + `payout_date`. Returns **409** if no approved rows.
  - `POST /api/admin/payout/calc/{calc_id}/hold` — single calc → `on_hold`. Returns **409** if status is `paid`.
  - `POST /api/admin/payout/calc/{calc_id}/resume` — single calc `on_hold → draft` (clears approved_*). Returns **409** otherwise.
  - `GET /api/admin/payout/{quarter}/calcs` — full list with status counts `{draft, approved, paid, on_hold}`.
- **Frontend (`/admin/payout`)**: status legend chips, per-row Hold/Resume buttons, Mark Paid bulk with payroll-ref input, gated on `hasApproved`. Fixed broken auth (was using cookie `credentials:'include'` → now uses JWT `authHeader()`).
- **Tests**: `/app/backend/tests/test_sprint_d_payout.py` — 12/12 passing (2 skipped when prior state already terminal). Covers state transitions, 409 guards, RBAC 403 for employees, and shape contracts.

### Mock dashboard endpoint replaced
- `GET /api/dashboard/upcoming` now serves **live** data: upcoming `tech_days` (future `conducted_on` within 60-day horizon) + computed quarterly payout date. No more hard-coded "Bajaj Finance" / "All For SPTS" placeholder rows.

## Changelog (Sprint H — Admin Console hardening · Apr 2026)
- [x] Admin Console (`/admin/console`) end-to-end edits now persist for **EDM Slides** (incl. `tag` / `tag_color`), **Quotes** (`text` / `source`), **Pillars** (incl. **description**, gradient, tagline), and **Pillar Icons** (name, lucide_icon, route, badge).
- [x] All 4 admin PUT endpoints use `exclude_unset=True` PATCH semantics — partial payloads no longer overwrite unspecified fields.
- [x] Added `description` column to `pillars` (raw-SQL idempotent migration in `_ensure_edm_tag_columns`) and included it in `_pillar_to_dict` so values rehydrate on reload.
- [x] Replaced fragile `setTimeout` reload hack in Icon Manager with `useCallback loadIcons(activePillar)` — Add App now appears immediately.
- [x] Added `data-testid` to admin sidebar nav, Add buttons, and Publish-All buttons for stable Playwright selectors.
- [x] Pillar pages now show a multi-card skeleton while loading (was a tiny single spinner).
- [x] Frontend QA: 12/13 admin-console flows passing (final iteration_5).

## Outstanding (P1)
- [ ] Add `data-testid` to per-row inputs in the admin console (badge buttons, individual edit fields).
- [ ] Investigate the 2× 401 console errors observed on first `/admin/console` load (likely a `useEffect` race or an unauthed widget firing pre-token).
- [ ] Sample seed data for Analytics charts so empty-state doesn't show "No data yet".
- [ ] Tooltips on Admin Quick Links.
- [ ] Refactor `server.py` (>3,400 lines) into `/app/backend/routes/` and `/app/backend/models/` once next major feature lands.
- [ ] Wrap admin save handlers with `if (!r.ok)` so failed PUTs surface a red "Save failed" toast instead of silent success.


## Changelog (VoC Intelligence Platform — Feb 2026)

### Phase 1 — Dashboard & Accounts (DONE)
- DB models: `VocAccountDB`, `VocSurveyDB`, `VocCampaignDB`, `VocResponseDB`, `VocSurveyTokenDB`.
- Seed: 6 enterprise accounts + ~85 demo responses across NPS/CSAT ranges.
- 6 endpoints: `/api/voc/dashboard/kpis`, `/trend`, `/verbatims`, `/pain-points`, `/csat-distribution`, `/strengths`, `/voc/accounts` CRUD.
- Frontend: `DashboardTab.jsx`, `AccountsTab.jsx` wired via `useVocDashboard.js`.

### Phase 2 — Survey Builder, Campaigns, Public Survey (DONE)
- Added `VocEmailLogDB` for delivery events (sent/opened/clicked/bounced).
- Endpoints: Survey CRUD (`/api/voc/surveys/*`), Campaign CRUD + `/send` (single-use token generation + optional AWS SES delivery), Public survey read/submit (`/api/voc/public/survey/:token`).
- Frontend: `SurveyBuilderTab.jsx`, `CampaignsTab.jsx`, public `SurveyResponsePage.jsx` wired via `App.js`.

### Phase 3 — AI Insights & Workflow (Backend DONE · Feb 2026)
- DB models: `VocAiInsightDB` (cached snapshot), `VocWorkflowTaskDB` (detractor follow-up tasks).
- Seed: 12 workflow tasks auto-created from detractor responses (NPS ≤ 6) assigned to Manager.
- **OpenRouter integration via `httpx.AsyncClient`** (direct, not emergentintegrations) — model: `anthropic/claude-sonnet-4`. Keys in `/app/backend/.env`: `OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL`, `OPENROUTER_MODEL`, `OPENROUTER_SITE_URL`, `OPENROUTER_SITE_NAME`.
- Endpoints:
  - `POST /api/voc/insights/generate` — aggregates last-N-days responses (default 90, optional account filter), prompts LLM for McKinsey SCR + themes + pain points + strengths + recommendations (P0/P1/P2) + risk accounts, persists snapshot.
  - `GET /api/voc/insights` — recent snapshots list.
  - `GET /api/voc/insights/{id}` — single snapshot fetch.
  - `GET /api/voc/workflow/tasks` — detractor task list with full response/account/assignee context; supports `?status=` and `?account_id=` filters.
  - `PATCH /api/voc/workflow/tasks/{id}` — status (`open|in_progress|resolved`), notes, reassign. Sets `resolved_at` automatically.
  - `GET /api/voc/workflow/stats` — counts by status for the kanban board.
- Verified e2e: generated insight on 60 responses (NPS 17, CSAT 4.08) returned 7 themes, 4 pain points, 4 P0/P1 recommendations.

## Outstanding — VoC Phase 3 (Frontend) & Phase 4
- [ ] P0: `AiInsightsTab.jsx` — "Generate Insights" CTA, period/account filters, render executive summary + theme chips + pain-points accordion + recommendations table.
- [ ] P0: `WorkflowTab.jsx` — kanban/list of detractor tasks with drag-to-status + resolution notes modal.
- [ ] P0: Wire both tabs into `NPSCsatPage.jsx`.
- [ ] P1: Phase 4 — RLS security layer, rate-limiting on `/voc/insights/generate`, DB indexes on `voc_responses(submitted_at)`, response caching for dashboard endpoints.
- [ ] P2: Refactor `/app/backend/server.py` (~5,140 lines) into `routes/` + `models/` once next feature lands.
