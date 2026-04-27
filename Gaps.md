# HSI Employee Engagement Platform — Gap Analysis

**Reference PRD:** `HSI-PRD-EEP-2026-v1.0` (HSI Employee Engagement Platform)  
**Current Build:** HSI Enterprise Portal (single React + FastAPI web app)  
**Analysis Date:** Feb 2026

---

## TL;DR — Severity Snapshot

| Severity | Count | Theme |
|---|---|---|
| 🔴 Critical / blocker | 7 | Wrong product scope, missing 3 of 4 apps, no XP engine, no MFA, no domain lock, no incentive engine, missing core schema |
| 🟠 High | 9 | Tech-stack mismatch, no pgBouncer/Redis/MinIO/WebSocket, no audit log, no session tracking, no rate-limiting, no auto-triggers |
| 🟡 Medium | 11 | Missing pillar/EDM CMS, missing best-practices/replications/tech-days/certifications, no analytics, no email/OTP, no monitoring |
| 🟢 Low / cosmetic | 5 | Branding, role naming, document control, glossary terminology |

**Bottom line:** What's built is **~5–8% of the PRD scope**. The current app is a single web dashboard with mock data; the PRD specifies a 4-app suite with an end-to-end incentive economy. Treat the existing codebase as an early prototype of the **Employee Web Portal only**.

---

## 1. Product Scope — 🔴 Critical

| # | PRD Requirement | Current State | Gap | Severity |
|---|---|---|---|---|
| 1.1 | Four-app suite: Employee Mobile, Employee Web, Admin Mobile, Admin Web | Single React web app (Employee Web only) | **Mobile apps (RN) and Admin Mobile not built; Admin Web is a tiny user-list panel, not the full CMS console** | 🔴 |
| 1.2 | Cross-app live sync within 5s via WebSocket / Socket.io broadcast | None | No WebSocket layer at all | 🔴 |
| 1.3 | Domain-locked auth (`@hitachi-systems.com` only) | Open registration with any email | No domain check at API or DB level | 🔴 |
| 1.4 | XP economy + INR incentive engine (quarterly payout, ART multipliers, payroll export) | Single `xp_points` integer on user | No ledger, no calculations, no quarter logic, no payouts | 🔴 |
| 1.5 | Tech Days, Certifications, Best Practices, Replications workflows | Not implemented (mock activity feed only) | Entire incentive earning surface is missing | 🔴 |
| 1.6 | EDM (Electronic Direct Mail) carousel + 4 Pillars (Customer/Innovator/Employee/Shareholder) + pillar icons | Pillar concept absent; dashboard uses generic "Apps" grid | No pillar navigation or content model | 🔴 |
| 1.7 | Admin CMS: live publish to all apps, publish history, version log | Admin panel is just user list + role edit + delete | No content management at all | 🔴 |

---

## 2. Authentication & Security — 🔴 / 🟠

| # | PRD Requirement | Current State | Gap | Severity |
|---|---|---|---|---|
| 2.1 | **Email OTP MFA** — 6-digit, SHA-256 hashed, 10 min TTL, max 3 attempts, sent via SMTP | Single-factor login (email + password) | OTP system entirely missing; no SMTP/Nodemailer/email layer | 🔴 |
| 2.2 | **Domain CHECK constraint** on `app.users.email` for `@hitachi-systems.com` | No constraint | Add DB-level enforcement | 🔴 |
| 2.3 | **bcrypt cost factor 12** | bcrypt with default cost (10 in `bcrypt.gensalt()`) | Bump to 12 explicitly | 🟠 |
| 2.4 | **Refresh token rotation** + sessions table with device/IP tracking, 15min access / 30d refresh | Single 1-day JWT, no sessions, no refresh | Implement `sessions` table + token rotation | 🔴 |
| 2.5 | **Account lockout** — 5 failed attempts → 15 min lockout, tracked in `user_credentials.failed_attempts` | None | Add lockout logic + table | 🟠 |
| 2.6 | **Rate limiting** via Redis — 5 OTP/hour/email, 10 login/min/IP | None | Add Redis + slowapi/redis-py limiter | 🟠 |
| 2.7 | **DB user isolation** — `hsi_api`, `hsi_admin`, `hsi_readonly`, `hsi_migrate` with separate SCRAM-SHA-256 creds in `pg_hba.conf` | Single `hsi_user` superuser | Implement 4-role DB privilege model | 🟠 |
| 2.8 | **Audit log** (`app.audit_log`) — all auth events + XP changes immutable | None | Add audit_log table + API hooks | 🟠 |
| 2.9 | **Token revocation** on logout / password change | Stateless JWT — `/auth/logout` is a no-op | Refresh token rotation (item 2.4) covers this | 🟠 |
| 2.10 | **TLS 1.3 only** | nginx config allows TLS 1.2 + 1.3 | Restrict to TLS 1.3 only in `docker/nginx/nginx.conf` | 🟡 |
| 2.11 | User must be **approved** by admin before becoming `is_active` | `is_active=True` by default at registration | Add pending-approval flow + `approved_by` / `approved_at` | 🟠 |

---

## 3. Database Schema — 🔴

PRD specifies 17+ tables in the `app` schema. Current build has **1**: `users`.

| # | PRD Table | Current State | Gap | Severity |
|---|---|---|---|---|
| 3.1 | `app.users` | `users` (legacy) | Missing: `email_domain` (generated col), `display_name`, `employee_id`, `practice`, `designation`, `art_tags TEXT[]`, `avatar_url`, `phone`, `date_of_birth`, `date_joined`, `is_verified`, `approved_by`, `approved_at`, `last_login_at`, domain CHECK constraint, indexes | 🔴 |
| 3.2 | `app.user_credentials` | password_hash on user row | Split into separate table; add salt, must_change, failed_attempts, locked_until | 🟠 |
| 3.3 | `app.sessions` | Missing | Add — refresh tokens, device info, IP, expires_at | 🔴 |
| 3.4 | `app.otp_codes` | Missing | Add | 🔴 |
| 3.5 | `app.best_practices` | Missing | Add — full lifecycle (draft/pending/approved/rejected), TRL, difficulty, pillar, ART, attachments | 🔴 |
| 3.6 | `app.replications` | Missing | Add — PO upload, PO value INR, deal closed date, XP award, referral XP | 🔴 |
| 3.7 | `app.xp_ledger` | Missing (only `users.xp_points` total) | Add immutable append-only ledger with running balance trigger | 🔴 |
| 3.8 | `app.incentive_calculations` | Missing | Add — per-user-per-quarter INR breakdown + payout state machine | 🔴 |
| 3.9 | `app.edm_slides` | Missing | Add — scope (home/customer/innovator/employee/shareholder), gradient, schedule, position | 🔴 |
| 3.10 | `app.pillars` + `app.pillar_icons` | Missing | Add | 🔴 |
| 3.11 | `app.motivational_quotes` | Missing | Add | 🟡 |
| 3.12 | `app.notifications` + `app.user_notifications` | Mock data in `/dashboard/announcements` | Real schema with categories, target_type, urgent flag, deep links, read tracking | 🟠 |
| 3.13 | `app.tech_days` + `app.certifications` | Missing | Add | 🔴 |
| 3.14 | `app.audit_log` | Missing | Add | 🟠 |
| 3.15 | DB Triggers — `set_updated_at()`, `maintain_xp_balance()`, birthday `pg_cron` | None | Add — XP balance trigger is critical for ledger integrity | 🟠 |
| 3.16 | UTF8 / `en_IN.UTF-8` collation, schema `app` namespacing | Default `public` schema | Migrate tables under `app` schema with proper collation | 🟡 |

---

## 4. Tech Stack Mismatches — 🟠

| # | PRD Spec | Current State | Action |
|---|---|---|---|
| 4.1 | Backend: **Node.js 20 LTS + Express + Prisma** | FastAPI + Python + SQLAlchemy | **Tech-stack divergence** — either get PRD amended to bless the Python stack, or rewrite backend in Node. Recommendation: get amendment (Python is more productive here) |
| 4.2 | **PostgreSQL 16** | PostgreSQL 15-alpine in docker-compose | Bump image to `postgres:16-alpine` |
| 4.3 | **pgBouncer 1.22** transaction-mode pooling, max 500 clients | Direct connections via SQLAlchemy pool | Add pgBouncer service to docker-compose |
| 4.4 | **Redis 7** for sessions + rate limiting | None | Add Redis service + integrate (slowapi or redis-py) |
| 4.5 | **Socket.io 4.x** for live admin → app sync | None | Add WebSocket endpoint (FastAPI has native support) |
| 4.6 | **MinIO** for EDM images and attachments | None — no file uploads in app | Add MinIO + presigned URL flow |
| 4.7 | **Nodemailer + Hitachi SMTP** for OTP/email | None | Add SMTP layer (`fastapi-mail` or similar) |
| 4.8 | **Sentry** for error monitoring | None | Add Sentry SDK (sentry-sdk[fastapi]) |
| 4.9 | **React + Vite + TypeScript + Tailwind** for web | React + CRA + JavaScript + Tailwind | Migrate CRA → Vite, JS → TS (PRD compliance + DX gain) |
| 4.10 | **React Native 0.73+** mobile apps (iOS + Android single codebase) | None | Greenfield — 2 separate apps to build |

---

## 5. User Model & Roles — 🟠

| # | PRD | Current | Gap |
|---|---|---|---|
| 5.1 | 4 roles: `employee`, `manager`, `admin`, `super_admin` | 3 roles: `employee`, `manager`, `admin` | Add `super_admin` (only super_admin can create admins per PRD intent) |
| 5.2 | Pending approval workflow for new registrations | All registrations auto-active | Add `is_active=False` default + `/admin/users/pending` + approve/reject endpoints |
| 5.3 | Profile fields: `employee_id`, `practice`, `designation`, `art_tags`, `avatar_url`, `phone`, `date_of_birth` | Only `name`, `department` | Extend user model |

---

## 6. API Endpoints — 🟠

PRD lists ~36 endpoints across `/auth/*`, `/users/*`, `/xp/*`, `/practices`, `/replications`, `/incentive/*`, `/leaderboard`, `/notifications/*`, `/content/*`, `/tech-days`, `/certifications`, `/admin/*`. Current build has **12** endpoints, mostly mocked.

### Auth — `/auth/*`
| PRD Endpoint | Implemented? |
|---|---|
| POST `/auth/check-email` | ❌ |
| POST `/auth/login` (returns OTP challenge) | ⚠ Returns JWT directly (no OTP) |
| POST `/auth/verify-otp` | ❌ |
| POST `/auth/refresh` | ❌ |
| POST `/auth/logout` | ✅ (no-op) |
| POST `/auth/logout-all` | ❌ |
| POST `/auth/forgot-password` | ❌ |
| POST `/auth/reset-password` | ❌ |

### Employee Domain
| PRD | Implemented? |
|---|---|
| GET `/users/me` | ✅ as `/auth/me` |
| PUT `/users/me` | ❌ |
| GET `/xp/summary` | ❌ |
| GET `/xp/ledger` | ❌ |
| GET `/practices`, POST `/practices`, GET `/practices/:id` | ❌ |
| POST `/replications`, GET `/replications/mine` | ❌ |
| GET `/incentive/statement` | ❌ |
| GET `/leaderboard` | ✅ at `/dashboard/leaderboard` (DB-backed) |
| GET `/notifications`, PUT `/notifications/:id/read` | ❌ |
| GET `/content/home`, GET `/content/pillars` | ❌ |
| POST `/tech-days`, POST `/certifications` | ❌ |

### Admin Domain
| PRD | Implemented? |
|---|---|
| GET `/admin/users/pending`, POST `/admin/users/:id/approve`, `/reject` | ❌ |
| GET `/admin/users` | ✅ |
| PUT `/admin/edm-slides`, `/admin/pillars/:slug`, `/admin/pillars/:slug/icons`, `/admin/quotes` | ❌ |
| POST `/admin/notifications/send` | ❌ |
| PUT `/admin/triggers` | ❌ |
| POST `/admin/practices/:id/approve`, `/reject` | ❌ |
| GET `/admin/analytics/summary` | ❌ |
| POST `/admin/publish` | ❌ |

---

## 7. XP & Incentive Engine — 🔴 (entirely missing)

| # | PRD Requirement | Current | Gap |
|---|---|---|---|
| 7.1 | XP award matrix (Easy/Medium/Hard/Expert × Original/Replication/Tech Day/Certification) | None | Implement matrix in incentive engine |
| 7.2 | ART multipliers (×1.2 / ×1.0 / ×1.5) on XP credits | None | Apply at ledger insert time |
| 7.3 | Birthday auto-credit (50 XP) via `pg_cron` daily at 00:01 | None | Add `pg_cron` extension + schedule |
| 7.4 | Referral XP (25 XP to original author when practice replicated) | None | Add to replication approval flow |
| 7.5 | Seasonal bonus (Diwali ×2) admin-toggleable | None | Add admin setting + flag in ledger |
| 7.6 | INR conversion rates: Original ₹50/XP, Replication w/PO ₹75/XP, w/o PO ₹60/XP, Tech Day ₹19/XP | None | Configurable rates in `incentive_calculations` |
| 7.7 | Quarterly payout state machine: draft → approved → paid / on_hold + payroll_ref | None | Build admin payout flow |

---

## 8. Content Management (Admin Console) — 🔴

| # | PRD Feature | Current | Gap |
|---|---|---|---|
| 8.1 | Home EDM editor — live preview, add/remove/reorder, scheduled visibility | None | Greenfield UI |
| 8.2 | Pillar manager — name, tagline, gradient per pillar | None | Greenfield |
| 8.3 | Pillar icon manager — per-pillar tabs, HOT/NEW badges, position | None | Greenfield |
| 8.4 | Quote editor | None | Greenfield |
| 8.5 | Push notification composer — target by all/user/role/practice/department + urgent flag + deep link | None | Greenfield |
| 8.6 | 7 auto-trigger toggles (Birthday, Approved, Replication, Reminder, New Practice, Award, Announcement) | None | Greenfield |
| 8.7 | "Publish All" — single button writes timestamp + WebSocket broadcast → all apps refresh within 5s | None | Greenfield (depends on WS layer) |
| 8.8 | Publish history with version log + author + note | None | Greenfield |
| 8.9 | Engagement analytics (EDM CTR, notif open rates, activity bars) | None | Greenfield |

---

## 9. Employee-Facing Surfaces — 🔴

PRD §7.1–7.2 specify rich features that don't exist yet:

| Surface | Status |
|---|---|
| Splash with HITACHI branding + ART taglines (1.4s load) | ❌ |
| 4-step login wizard (role → email → OTP → success) | ❌ |
| Home: EDM Carousel + Motivational Quotes + Activity Grid + 4 Pillar Cards | ⚠ Partial — has activity grid + leaderboard, no EDM/quotes/pillars |
| XP Detail Panel with breakdown by source + level progress + MBB insight | ❌ (only static `/dashboard/score`) |
| Incentive Panel with Q breakdown + PO unlock CTA + Bain insight | ❌ |
| Profile page with avatar, XP ring, stats, menu links | ❌ |
| Pillar pages — hero + sub-EDM + 6-col icon grid per pillar | ❌ |
| In-app search across icon names | ❌ |
| Live update banner (within 5s of admin publish) | ❌ |
| Modal drill-downs for XP/Incentive/Practices/Leaderboard | ❌ |

---

## 10. Non-Functional Requirements — 🟠

| # | PRD Target | Current | Gap |
|---|---|---|---|
| 10.1 | API p95 < 200ms read endpoints | Not measured | Add APM (Sentry / OpenTelemetry) |
| 10.2 | DB query < 50ms indexed | No indexes beyond email | Add indexes from §3.3 |
| 10.3 | App initial load < 3s on 4G | CRA bundle, unmeasured | Migrate to Vite + bundle audit |
| 10.4 | 99.5% uptime | Single container, no HA | Add HA topology in deploy plan |
| 10.5 | 500 concurrent users → 5,000 via pgBouncer | Single connection pool | Add pgBouncer (item 4.3) |
| 10.6 | TLS 1.3 only | TLS 1.2 + 1.3 | Lock down nginx |
| 10.7 | Data residency (India on-prem) | Not enforced | Out of scope for code; deployment-time concern |
| 10.8 | WCAG 2.1 AA | Not audited | Add axe-core CI scan, fix violations |
| 10.9 | Daily full backup + hourly WAL archiving | None in docker-compose | Add `pg_basebackup` cron + WAL archive volume |
| 10.10 | Sentry integration | None | Add SDK to FastAPI + frontend |

---

## 11. Deployment Architecture — 🟠

PRD §9.1 specifies a **specific** docker-compose topology (Postgres + pgBouncer + Redis + API). Current `docker-compose.yml` has Postgres + backend + frontend + nginx — **missing pgBouncer, Redis, MinIO, Socket.io**.

### Action items
1. Add `pgbouncer` service (bitnami/pgbouncer:1.22)
2. Add `redis` service (redis:7-alpine)
3. Add `minio` service (minio/minio with bucket auto-create)
4. Add `socketio` server (or merge into FastAPI process)
5. Update `DATABASE_URL` to point at pgBouncer (port 6432)
6. Add `pg_hba.conf` mount with SCRAM-SHA-256 + 4-role privilege model
7. Add `init.sql` mount that creates the 4 DB roles + GRANTs from §3.2

---

## 12. Roadmap Alignment — 🟢

PRD prescribes 7 phases (Weeks 1–18). What's built maps to **Phase 0 + partial Phase 1 + thin slice of Phase 2**:

| PRD Phase | PRD Weeks | Current Status |
|---|---|---|
| 0 — Foundation (Postgres, pgBouncer, Redis, Docker) | 1–2 | ⚠ Postgres ✅, others ❌ |
| 1 — Auth (registration, login, OTP MFA, JWT, sessions, domain) | 2–4 | ⚠ Login + JWT ✅; OTP/sessions/domain ❌ |
| 2 — Employee Web (portal, pillar pages, EDM, quotes, XP display) | 4–7 | ⚠ Skeleton dashboard only |
| 3 — Mobile (RN, push, offline) | 6–9 | ❌ |
| 4 — Admin Console (CMS, approvals, notif composer, analytics) | 8–11 | ❌ (only user list) |
| 5 — Incentive Engine (ledger, ART, quarterly, payroll export) | 10–13 | ❌ |
| 6 — Intelligence (auto-triggers, birthday, leaderboard, pg_cron) | 12–16 | ⚠ Leaderboard only |
| 7 — Hardening (VAPT, load test, monitoring) | 14–18 | ❌ |

**Honest progress: ~5–8% of total scope.**

---

## 13. Branding / Naming — 🟢

| # | PRD | Current | Gap |
|---|---|---|---|
| 13.1 | Product name: **HSI Employee Engagement Platform** | "HSI Enterprise Portal" | Rename |
| 13.2 | Domain: `hsi-platform.hitachi-systems.com` | Not configured | Set in `.env.example` |
| 13.3 | Color: Hitachi red `#CC0000` | ✅ Used | OK |

---

## 14. What the Current Build IS Useful For

The work done so far is not wasted — it provides a solid foundation:

- ✅ React + Tailwind + Shadcn UI scaffolding (reusable for Employee Web Portal)
- ✅ FastAPI + SQLAlchemy + JWT skeleton (good base for migration)
- ✅ Docker production deployment with nginx + SSL placeholders + `setup.sh` (covers PRD §9 partially)
- ✅ Idempotent seeding pattern (transferable to PRD's expanded user model)
- ✅ Live PostgreSQL leaderboard query pattern (reusable)
- ✅ Existing dashboard UI (NPS/CSAT, Action Intelligence) — could repurpose components for pillar pages

---

## 15. Recommended Next Steps (Prioritised)

### Sprint 0 — Decision & Foundation (P0, 1 week)
1. **Confirm PRD scope** with stakeholder — is the full HSI EEP the target, or is the current "Enterprise Portal" a separate deliverable? Massive cost difference.
2. If full PRD: **decide stack** — Node/Express+Prisma (PRD literal) vs keep FastAPI+SQLAlchemy (faster, Python team).
3. Upgrade Postgres image 15 → 16; add pgBouncer + Redis services.
4. Migrate schema to `app` namespace + add domain CHECK + bcrypt cost 12.

### Sprint 1 — Auth Hardening (P0, 1–2 weeks)
5. Implement `user_credentials`, `sessions`, `otp_codes` tables.
6. Add domain validation (API + DB) + email OTP flow + SMTP.
7. Add account lockout + Redis rate limiting + audit_log.
8. Implement refresh token rotation.

### Sprint 2 — Content Model + Pillars (P1, 2 weeks)
9. Add `pillars`, `pillar_icons`, `edm_slides`, `motivational_quotes` tables + admin CRUD.
10. Build employee pillar pages (4 pillars × home + detail).
11. Add WebSocket layer for admin→client live publish.

### Sprint 3 — XP/Incentive Engine (P1, 2–3 weeks)
12. Add `best_practices`, `replications`, `xp_ledger`, `incentive_calculations`, `tech_days`, `certifications`.
13. Implement XP balance trigger + ART multipliers + INR rate config.
14. Build employee submit flows + admin approval/payout flows.

### Sprint 4 — Mobile (P2, 4+ weeks)
15. Bootstrap React Native app sharing API.
16. Push notifications.
17. Offline support.

### Sprint 5 — Hardening (P2, 2 weeks)
18. Sentry, WAL backup, VAPT, WCAG audit.

---

## 16. Open Questions for Stakeholder

1. Is the current "Enterprise Portal" (with NPS/CSAT + Action Intelligence pages) a **separate** product, or does it fold into the EEP as one of the pillar deep-dives?
2. Does the PRD's Node.js+Express+Prisma stack mandate apply, or is FastAPI acceptable as an equivalent?
3. Which 4 pillars' content (icons, EDM slides, quotes) is ready, and where is the source artwork?
4. Who provides the SMTP relay creds for OTP delivery? Hitachi internal or third-party (SendGrid/SES)?
5. Is there an existing payroll system to integrate with, or is PDF/CSV export sufficient for Q1 launch?
6. Is mobile **mandatory for v1** or can web-only ship first?
7. Does HR have a list of 500 Phase 1 users with `@hitachi-systems.com` emails ready for the approval queue?

---

*Document prepared by E1 (Emergent agent) — Feb 2026.*
