# HSI Enterprise Portal — PRD

## Product Overview
Hitachi Systems India (HSI) Enterprise Platform — a unified employee workspace with JWT auth, 9 enterprise apps, admin panel, and a comprehensive home dashboard.

**Date Started:** 2025-02  
**Status:** Phase 1 Complete (Home Page + Auth)

---

## Architecture
- **Frontend:** React 19 + TailwindCSS + lucide-react
- **Backend:** FastAPI (Python 3.11)
- **Database:** PostgreSQL 15 (local) via SQLAlchemy 2.0
- **Auth:** JWT (Bearer token stored in localStorage)
- **Design:** Outfit + IBM Plex Sans fonts, #CC0000 primary red

---

## User Personas
- **Admin:** Full access, user management, role changes
- **Manager:** Team management, approvals, full app access
- **Employee:** Standard app access, dashboard, XP tracking

---

## Core Requirements (Static)
1. JWT auth with email/password
2. PostgreSQL database
3. Three roles: Admin, Manager, Employee
4. HSI branding (Hitachi Systems India, red #CC0000)
5. Responsive enterprise dashboard

---

## Implemented (Phase 1)

### Auth
- [x] User registration with role selection
- [x] User login with JWT token
- [x] Token stored in localStorage
- [x] Protected routes
- [x] Auto-seeded users: admin, manager, employees (6 total)

### Home Dashboard (/):
- [x] Red hero header with greeting + quick stats
- [x] MY DASHBOARDS section (5 metric cards)
- [x] MY APPS QUICK ACCESS (5 buttons)
- [x] ALL APPLICATIONS grid (9 apps with colorful headers)
- [x] RECENT ACTIVITY feed with timestamps
- [x] MY SCORE circular gauge + breakdown
- [x] UPCOMING events
- [x] PENDING ACTIONS with Act buttons
- [x] ORGANISATION LEADERBOARD (real DB data)
- [x] ANNOUNCEMENTS section

### Pages
- [x] /login — Login page with HSI branding
- [x] /register — Register with role selection
- [x] / — Home dashboard
- [x] /apps/:appId — 9 original app placeholder pages
- [x] /apps/nps-csat — **Full NPS & CSAT page** (dark theme, charts, gauge)
- [x] /apps/survey-builder — Survey Builder placeholder
- [x] /apps/email-campaigns — Email Campaigns placeholder
- [x] /admin — Admin user management panel

### Admin Panel
- [x] User list table
- [x] Search + filter by role
- [x] Role change dropdown
- [x] Delete user (with confirmation)
- [x] Stats cards (total, admin, manager, employee count)

---

## Dashboard Data
- Stats, Activities, Announcements, Pending Actions, Upcoming: **MOCKED** (static from API)
- Leaderboard: **LIVE** (queries PostgreSQL)

---

## Seed Users
| Email | Password | Role |
|-------|----------|------|
| admin@hsi.com | Admin@123 | admin |
| manager@hsi.com | Manager@123 | manager |
| employee@hsi.com | Employee@123 | employee |
| priya@hsi.com | Employee@123 | employee |
| kiran@hsi.com | Employee@123 | employee |
| ananya@hsi.com | Employee@123 | employee |

---

## Prioritized Backlog

### P0 (Next — awaiting screenshots)
- [ ] Best Practices Repository full page
- [ ] Tech Days Manager full page
- [ ] CRM & Opportunity Pipeline full page
- [ ] Productivity Hub full page
- [ ] Workflow Automation page
- [ ] Access Rights Management page
- [ ] Visitor Management page
- [ ] Learning & Development page
- [ ] Analytics & Reports page (VOC Intelligence Platform shown in screenshot)

### P1 (After P0)
- [ ] Connect dashboard stats to real DB data
- [ ] Real activities feed from DB
- [ ] Notifications system
- [ ] User profile page
- [ ] Search functionality

### P2
- [ ] Export reports
- [ ] Email notifications
- [ ] Advanced analytics
- [ ] Mobile app
