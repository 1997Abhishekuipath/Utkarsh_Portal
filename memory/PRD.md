# Customer Management Portal - PRD

## Original Problem Statement
Build a modern enterprise-grade Customer Management Portal with a professional responsive UI and admin dashboard. Must support Authentication & Roles (Admin/Manager/Read-only), Customer/Product/License management modules, dashboard with KPIs and charts, expiry alerts (90/60/30 days color-coded), reports with CSV/PDF export, glassmorphism UI, light/dark themes, and look like enterprise SaaS (ServiceNow/Freshservice).

## User Choices (Feb 2026)
- Tech Stack: FastAPI + MongoDB (Python)
- Auth: JWT-based custom auth (admin/manager/viewer)
- Email Notifications: Skipped for MVP - in-app dashboard alerts only
- Sample Data: YES - realistic seeded demo data
- Theme: Both light & dark with toggle

## Architecture
- Backend: `/app/backend/server.py` - FastAPI single-file with /api routes, JWT in httpOnly cookies (samesite=none, secure=true), bcrypt password hashing, role guards (require_admin, require_manager)
- Database: MongoDB (`cmp_database`) - collections: users, customers, products, licenses, activity_logs, login_attempts, password_reset_tokens
- Frontend: React 19 + Tailwind + shadcn/ui, recharts for graphs, AuthContext + ThemeContext, axios with withCredentials
- Design: Crystal glassmorphism per `/app/design_guidelines.json` (Outfit + Inter, blue-600 primary)

## User Personas
- **Admin** — full access (CRUD on all + user management + activity logs)
- **Manager** — create/update on customers/products/licenses; cannot delete or manage users
- **Viewer** — read-only across all data

## Implemented (Iteration 1 - Feb 6, 2026)
- JWT auth with login/logout/me/refresh + brute-force protection (5 attempts/15min)
- Role-based RBAC across all entity routes
- 3 seeded users + 12 customers, 10 products, 45 licenses (mix of Active/Expiring Soon/Expired)
- Customers/Products/Licenses CRUD with search, filters, pagination
- Licenses auto-compute status from expiry_date (Active/Expiring Soon/Expired) with color-coded badges
- Dashboard with 6 KPI cards, 5 charts (revenue area, product pie, expiry line, vendor bar, growth bar), critical expiring list, top customers by revenue
- 6 Reports (monthly-expiry, customer-license, vendor, revenue, renewal, expired) with CSV + PDF export
- User management (admin) + activity logs / audit trail
- Notifications dropdown (90/60/30 day expiry alerts)
- Settings page with theme toggle, profile, security info
- Glassmorphism UI, light/dark theme toggle, responsive sidebar
- 33/33 backend tests passing, frontend smoke tested across all roles

## Backlog (P1)
- File upload for invoices/license docs (object storage)
- Email notifications (Resend/SendGrid)
- Partial update support for PUT endpoints
- Single-resource GET for products/licenses
- Renewal History tracking with versions
- Two-factor authentication
- Customer detail drawer view

## Backlog (P2)
- Bulk import (CSV upload for customers/licenses)
- Forecasting/AI insights on revenue
- Vendor portal access (limited share links)
- Custom dashboards per user
- Refactor server.py into routers/ subfolder
