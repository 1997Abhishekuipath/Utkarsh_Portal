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

## TL;DR — Severity Snapshot (post Sprint A)

| Severity | Open | Closed in Sprint A | Theme |
|---|---|---|---|
| 🔴 Critical | 5 (was 7) | **2 closed** | Auth foundation hardened (lockout, audit, sessions, super_admin, pending approval). Remaining: XP engine, content/CMS, EDM, pillar nav, replications. |
| 🟠 High | 7 (was 9) | **2 closed** | bcrypt 12, audit log, sessions, refresh rotation, pending-approval, super_admin, domain check (API) — **closed**. Remaining: pgBouncer, Redis, MinIO, WebSocket, DB-level role isolation. |
| 🟡 Medium | 11 | 0 | Content management surfaces — Sprint C/D. |
| 🟢 Low | 5 | 0 | Branding, doc control. |

**Progress: Phase 1 + Phase 0 + thin slice of Phase 2 → ~12% of total PRD scope. Up from ~5–8% before Sprint A.**

---

## Sprint A — DONE (Feb 2026)

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
| 1 | **Email OTP MFA** — 6-digit, SHA-256 hashed, 10 min TTL, max 3 attempts, sent via SMTP | `otp_codes` table ready, SMTP not wired | **B** — AWS SES integration + `/auth/verify-otp` endpoint |
| 2 | **Domain CHECK constraint at DB level** (PRD §4.4) | API-only check today | **B** — add CHECK constraint via Alembic migration |
| 3 | **Redis** for rate limiting (5 OTP/hr/email, 10 login/min/IP) | None | **B** |
| 4 | **EDM Carousel + Pillar nav + 4 pillar pages** (Customer/Innovator/Employee/Shareholder) | Generic dashboard | **C** |
| 5 | **XP ledger + ART multipliers + INR incentive engine + quarterly payout** | Single `xp_points` integer | **D** |
| 6 | **Best Practices / Replications / Tech Days / Certifications** workflows | None | **D** |
| 7 | **WebSocket live admin→app sync** (≤5s after Publish All) | None | **C** |

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
