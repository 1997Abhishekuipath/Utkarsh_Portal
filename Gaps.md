# HSI Employee Engagement Platform — Gap Analysis

**Reference PRD:** `HSI-PRD-EEP-2026-v1.0` (HSI Employee Engagement Platform)
**Current Build:** HSI Enterprise Portal (single React + FastAPI web app)
**Last Updated:** Feb 2026 (post-Sprint A)

---

## Decisions Locked (ADRs)

| ADR | Decision | Rationale |
|---|---|---|
| **ADR-001** | Backend stays on **FastAPI** (deviates from PRD §2.3 "Node + Express + Prisma") | Emergent platform's verified auth + AWS-SES playbooks are FastAPI-only. Node rewrite without a vetted playbook is *less* secure than hardening FastAPI. Saves ~3 weeks. **Stakeholder sign-off pending.** |
| **ADR-002** | **Mobile deferred** to backlog | V1 web-only. Build for 500 pilot users on web, learn, then build mobile. |
| **ADR-003** | **NPS/CSAT + Action Intelligence preserved** | Existing pages fold under Customer pillar in Sprint C, not discarded. |

---

## TL;DR — Severity Snapshot (post Sprint C)

| Severity | Open | Closed (A+B+C) | Theme |
|---|---|---|---|
| 🔴 Critical | 2 (was 7) | **5 closed** | Auth foundation + MFA + content/CMS + EDM + 4 pillars + WebSocket live-sync. Remaining: XP engine, replications/best-practices/tech-days/certifications. |
| 🟠 High | 5 (was 9) | **4 closed** | bcrypt 12, audit log, sessions, refresh rotation, pending approval, super_admin, domain CHECK (DB+API), MFA, rate limiting, password reset, **WebSocket live-sync**. Remaining: pgBouncer, MinIO, 4 DB roles, Sentry, pg_cron, WAL. |
| 🟡 Medium | 9 (was 11) | **2 closed** | Admin CMS for pillars/icons/EDM/quotes shipped. Remaining: notifications, push composer, analytics dashboards, etc. |
| 🟢 Low | 5 | 0 | Branding, doc control. |

**Progress: ~32% of total PRD scope** (was ~18% post Sprint B, ~12% post Sprint A, ~5–8% baseline).

---

## Sprint C — DONE (Feb 2026)

**Goal:** Pillars + EDM + CMS + WebSocket live-sync. NPS/CSAT and Action Intelligence preserved as deep-dives under Customer pillar (per ADR-003).

| Item | Status | Notes |
|---|---|---|
| `pillars`, `pillar_icons`, `edm_slides`, `motivational_quotes`, `publish_history` schemas | ✅ | All 5 tables created via SQLAlchemy `create_all` with CHECK constraints (e.g. `chk_edm_scope`). |
| Public read endpoints | ✅ | `GET /api/content/home`, `GET /api/content/pillars/:slug` — auth-gated, returns scoped EDM + filters by published + by date window (`starts_at`/`ends_at`). |
| Admin CRUD endpoints (16 total) | ✅ | `/admin/pillars`, `/admin/pillar-icons`, `/admin/edm-slides`, `/admin/quotes` — full GET/POST/PUT/DELETE, all guarded by admin/super_admin role. |
| `POST /admin/publish` + `GET /admin/publish-history` | ✅ | Records to `publish_history` table, broadcasts to WS clients. Verified: publish with 1 connected subscriber → `subscribers_notified: 1`, payload `{type, scope, at, by, id}`. |
| WebSocket endpoint at `/api/ws` | ✅ | `services/ws.py` connection manager with thread-safe set + auto-clean of dead connections. Sends `hello` on connect, replies `pong` to `ping`, broadcasts publish events. **End-to-end verified**: subscribed client received broadcast within milliseconds of admin publish. |
| Replace home `/` with PRD home (EDM carousel + 4 pillar cards + quotes + activity grid) | ✅ | New `HomePage.jsx`. Layout: red top bar (with mini-stats + user menu) → home EDM carousel → THE FOUR PILLARS grid → motivational quote ribbon → activity panel + leaderboard/announcements/pending/upcoming sidebar. |
| 4 pillar pages with hero + sub-EDM + 6-col icon grid | ✅ | Single generic `PillarPage.jsx` driven by `:slug` param. Hero gradient swaps to pillar's brand colors. 6-col responsive icon grid (drops to 3-col / 2-col on smaller screens). |
| NPS/CSAT + Action Intelligence folded under Customer pillar | ✅ | Customer pillar's first 2 icons link to `/apps/nps-csat` (badge: `hot`) and `/apps/survey-builder` (badge: `new`) respectively. Existing pages preserved. |
| Live update — admin publish triggers re-fetch within ≤5s on home + pillar pages | ✅ | `useLiveContent` hook auto-reconnects with exponential backoff (1s → 15s); home re-fetches on `scope=all|home`, pillar re-fetches on `scope=all|<slug>`. **WS LIVE/OFFLINE indicator** in red top bar. |
| Admin Content Management UI | ✅ | New `AdminContentPage.jsx` at `/admin/content`. 4 tabs (Pillars / Icons / EDM / Quotes) with inline create+edit forms, filter dropdowns (icon-by-pillar, EDM-by-scope), and a `Publish All` button in the header. |
| Reusable components | ✅ | `EdmCarousel`, `PillarCard`, `IconGrid`, `QuoteRibbon`, `TopBar`, `useLiveContent` hook. |
| Seed data | ✅ | 4 pillars + 24 icons (6/pillar) + 7 EDM slides + 5 quotes — seeded idempotently via `_seed_content()` in `seed.py`. |

### Verified end-to-end
- ✅ `GET /api/content/home` → 4 pillars, 3 home EDM slides, 5 quotes
- ✅ `GET /api/content/pillars/customer` → Customer pillar with 6 icons, including NPS/CSAT and Action Intelligence as the first 2 entries
- ✅ `POST /api/admin/publish` → broadcast to all WS subscribers; payload includes scope, at, by, id; `subscribers_notified` count returned
- ✅ Home page: pillars-section selector visible, EDM carousel mounted, quotes ribbon mounted
- ✅ Pillar page: pillar-icon-grid-section selector visible, hero color matches pillar gradient
- ✅ Admin Content page: 4 tabs (`tab-pillars`, `tab-icons`, `tab-edm`, `tab-quotes`) all visible

---

## Sprint B — DONE (Feb 2026)

**Goal:** Email OTP MFA via AWS SES + Redis rate limiting + DB-level domain CHECK + Postgres 16.

| Item | Status | Notes |
|---|---|---|
| AWS SES email service (boto3) — graceful fallback to log-only when no creds | ✅ | `services/email.py`. Dev mode logs OTP to backend log (`[email][DEV-FALLBACK]…`); switches to real SES when AWS creds present. Branded HTML + plain-text email body. |
| `MFA_ENABLED` env flag — toggles 2-step login | ✅ | OFF by default in dev; ON in current pod for prod-parity testing. |
| `POST /auth/verify-otp` endpoint | ✅ | Hash-compares (SHA-256) the 6-digit code; max 3 attempts before invalidate. |
| `POST /auth/resend-otp` endpoint | ✅ | Rate-limited (5/hr, 1/30s). Generic response — never leaks user existence. |
| `POST /auth/forgot-password`, `POST /auth/reset-password` | ✅ | OTP-driven reset; **revokes all active sessions** on success (sec best practice). |
| Redis service in docker-compose | ✅ | redis:7-alpine, AOF persistence, 256MB LRU. Optional in dev (in-memory fallback). |
| Rate limiting — 10 login/min/IP, 5 OTP/hr/email, 1 resend/30s, 5 verify/min/email, 5 reset/hr/email | ✅ | `services/rate_limit.py` (Redis-backed; in-memory fallback). All limits verified with curl. |
| DB-level domain CHECK constraint on `users.email` | ✅ | `chk_user_email_domain CHECK (email ILIKE '%@hitachi-systems.com')` — verified rejects gmail at INSERT. Idempotent startup migration adds it to existing DBs. |
| Postgres 15 → 16 in `docker-compose.yml` | ✅ | `image: postgres:16-alpine`. Local dev pod stays on apt-installed 15. |
| Frontend: 2-step login UX + OTP entry + forgot-password flow | ✅ | `LoginPage.jsx` rewritten with inline OTP step (back button, resend countdown, masked email); new `ForgotPasswordPage.jsx`; `App.js` adds `/forgot-password` route; `super_admin` allowed alongside `admin` in `ProtectedRoute`. |

### Verified end-to-end (curl)
- ✅ MFA OFF → login returns access + refresh tokens directly (backward compat)
- ✅ MFA ON → step 1 returns `{requires_otp: true, otp_id, expires_in_sec}`, no tokens issued
- ✅ OTP visible in dev log; verify-otp returns tokens
- ✅ Wrong OTP returns remaining attempts (3 → 2 → 1 → 0); 4th wrong attempt invalidates the OTP
- ✅ Resend OTP rate-limited: 1 per 30s (HTTP 429)
- ✅ Forgot-password issues reset OTP; reset-password sets new pw + revokes all sessions
- ✅ Login with old password fails after reset (401)
- ✅ DB-level domain CHECK rejects `bad@gmail.com` at INSERT (psql: "violates check constraint")
- ✅ Login rate-limit: 11th request in a minute returns HTTP 429
- ✅ Frontend OTP UI renders after creds submission; back button returns to creds; forgot-password link visible

---



| Item | Status | File / Endpoint |
|---|---|---|
| Domain restriction (`@hitachi-systems.com` only) at API layer | ✅ | `server.py::validate_domain()`, env `ALLOWED_DOMAIN` |
| bcrypt cost factor **12** | ✅ | `server.py::hash_pw()`, env `BCRYPT_ROUNDS=12` |
| `super_admin` role added | ✅ | `users.role` CHECK constraint |
| `sessions` table + refresh-token rotation (one-time-use) | ✅ | `SessionDB`, `POST /api/auth/refresh` |
| Account lockout (5 fails → 15 min) | ✅ | `users.failed_attempts`, `locked_until` |
| Pending-admin-approval registration flow | ✅ | `users.is_active=False` default + approve/reject |
| `audit_log` table + auth/admin event logging | ✅ | `AuditLogDB`, `GET /api/admin/audit-log` |
| `otp_codes` table (schema only — Sprint B wires SMTP) | ✅ | `OtpCodeDB` |
| Expanded user model: `display_name`, `employee_id`, `practice`, `designation`, `art_tags[]`, `avatar_url`, `phone`, `date_of_birth`, `is_verified`, `approved_by/at`, `last_login_at` | ✅ | `UserDB` |
| New endpoints: `/auth/check-email`, `/auth/refresh`, `/auth/logout-all`, `/admin/users/pending`, `/admin/users/:id/approve`, `/admin/users/:id/reject`, `/admin/audit-log` | ✅ | `server.py` |
| Frontend: register handles pending-approval response; admin role removed from public registration; placeholder updated to `@hitachi-systems.com` | ✅ | `RegisterPage.jsx`, `AuthContext.js` |
| Seed users moved to `@hitachi-systems.com` (one-time legacy migration) | ✅ | `seed.py` |
| Test credentials updated | ✅ | `/app/memory/test_credentials.md` |

### Verified end-to-end (manual smoke)
- ✅ Domain rejection (gmail returns 400 "Email must end with @hitachi-systems.com")
- ✅ Login with new domain, returns access + 64-char opaque refresh
- ✅ Refresh rotates token; old refresh becomes invalid (one-time-use)
- ✅ New registration → `pending_approval: true`, no token issued
- ✅ Pending user blocked from login (HTTP 403 "Account pending admin approval")
- ✅ Admin sees newbie in pending queue
- ✅ Admin approval activates the account; user can immediately login
- ✅ 5 wrong passwords → 6th login (correct) returns HTTP 423 "Account locked until..."
- ✅ Audit log captures every event with actor email, action, status, IP, timestamp
- ✅ Backend restart preserves users + sessions

---

## Still Open — Critical (P0)

| # | PRD Requirement | Current State | Sprint |
|---|---|---|---|
| 1 | **XP ledger + ART multipliers + INR incentive engine + quarterly payout** | Single `xp_points` integer | **D** |
| 2 | **Best Practices / Replications / Tech Days / Certifications** workflows | None | **D** |

## Still Open — High (P1)

| # | Requirement | Current | Sprint |
|---|---|---|---|
| 1 | **pgBouncer** transaction pooling | Direct connections | F |
| 2 | **MinIO** for EDM images / attachments | None | C (when first upload feature lands) |
| 3 | **4 DB roles** (`hsi_api`/`hsi_admin`/`hsi_readonly`/`hsi_migrate`) with SCRAM-SHA-256 in `pg_hba.conf` | Single `hsi_user` superuser | F |
| 4 | **`pg_cron`** for birthday auto-credit | None | E |
| 5 | **7 auto-triggers** (Birthday, Approved, Replication, Reminder, New Practice, Award, Announcement) | None | E |
| 6 | **Sentry** monitoring | None | F |
| 7 | **WAL backup** (daily full + hourly archive) | None | F |

## Still Open — Medium (P2)

- All admin CMS surfaces (EDM editor, pillar manager, icon manager, quote editor, notification composer, publish history, analytics)
- `notifications` + `user_notifications` tables (replace mock `/dashboard/announcements`)
- `motivational_quotes`
- TLS 1.3 only (currently 1.2 + 1.3)
- WCAG 2.1 AA audit
- Postgres 15 → 16 image bump

## Still Open — Low (P3)

- Top-of-app product name still "HSI Enterprise Portal" (PRD: "HSI Employee Engagement Platform")
- Some PRD glossary terms not yet in UI (e.g. "EDM", "ART", pillar names)
- `last_login_at` not surfaced in profile UI yet

---

## Deferred (Backlog — post-V1)

| # | Item | Why deferred |
|---|---|---|
| 1 | **React Native mobile** (employee + admin) | ADR-002 — mobile deferred to backlog |
| 2 | Push notifications | Couples to mobile; web push deferred until pillar/notification surfaces ship |
| 3 | Offline support | Mobile-only requirement |

---

## Roadmap Re-alignment

| PRD Phase | PRD Weeks | Status |
|---|---|---|
| 0 — Foundation | 1–2 | ✅ Complete (Postgres, Docker compose, Dockerfiles, setup.sh, SSL, env) |
| 1 — Auth | 2–4 | 🟡 Sprint A done · OTP/SMTP/Redis = Sprint B |
| 2 — Employee Web | 4–7 | ⚠ Skeleton dashboard; full pillar/EDM stack = Sprint C |
| 3 — Mobile | 6–9 | ⏸ DEFERRED (ADR-002) |
| 4 — Admin Console | 8–11 | ⚠ Approvals/audit done; CMS = Sprint C; notifications = Sprint E |
| 5 — Incentive Engine | 10–13 | ❌ Sprint D |
| 6 — Intelligence | 12–16 | ❌ Sprint E |
| 7 — Hardening | 14–18 | ❌ Sprint F |

---

## Open Questions for Stakeholder

1. **AWS SES credentials** — please provide before Sprint B starts: AWS Region (recommend `ap-south-1` for India residency per PRD §10.7), IAM Access Key + Secret with `ses:SendEmail`, verified sender domain (`noreply@hitachi-systems.com` with DKIM CNAMEs in DNS), SES sandbox vs production status.
2. **Sign-off on ADR-001** (FastAPI deviation from PRD literal Node) — this is a written deviation we need stakeholder approval on.
3. **Pillar artwork** — gradients, icons, EDM slide content for Customer / Innovator / Employee / Shareholder pillars (Sprint C blocker).
4. **Existing 500 pilot users** — does HR have the list with `@hitachi-systems.com` emails ready for the approval queue? If yes, we can bulk-import via `/admin/users/pending` flow.
5. **Payroll integration** — push payouts to existing payroll system, or PDF/CSV export sufficient for Sprint D?

---

*Document prepared by E1 (Emergent agent) — Feb 2026, last updated post Sprint A.*
