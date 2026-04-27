#====================================================================================================
# START - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================
# (protocol unchanged — see prior iterations)
#====================================================================================================
# END - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================

user_problem_statement: "HSI Employee Engagement Platform — complete Sprint G. Scope (all 3 priority buckets agreed with user): MinIO object storage, 4 PostgreSQL roles with SCRAM-SHA-256, Admin Analytics dashboard, Payroll CSV/PDF export, WCAG 2.1 AA pass, Redis pub/sub for multi-instance WebSocket fan-out."

backend:
  - task: "Sprint G — MinIO object storage service (services/storage.py)"
    implemented: true
    working: "NA"
    file: "backend/services/storage.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
      - working: "NA"
        agent: "main"
        comment: "S3-compatible uploader with graceful local-disk fallback when MinIO is unavailable. Uploads land under /tmp/hsi_uploads in preview pod (no MinIO container here); in docker-compose the full MinIO service is wired. Bucket auto-created + public-read policy applied."

  - task: "Sprint G — POST /api/uploads authenticated multipart endpoint"
    implemented: true
    working: "NA"
    file: "backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
      - working: "NA"
        agent: "main"
        comment: "Accepts file + category (avatar|practice|edm|tech_day|cert|misc). Max 10 MB. Writes a FileAssetDB audit row. Verified with curl — returns {id,key,url,filename,size,content_type,storage}. /api/uploads-local StaticFiles mount serves files back when storage=local."

  - task: "Sprint G — FileAssetDB model + attachments column on best_practices"
    implemented: true
    working: "NA"
    file: "backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
      - working: "NA"
        agent: "main"
        comment: "New file_assets table. Idempotent migration adds attachments JSONB column to best_practices. PracticeSubmitReq now accepts attachments list; _bp_dict echoes them back."

  - task: "Sprint G — PATCH /api/users/me accepts avatar_url/phone/designation"
    implemented: true
    working: "NA"
    file: "backend/server.py"
    stuck_count: 0
    priority: "medium"
    needs_retesting: true
    status_history:
      - working: "NA"
        agent: "main"
        comment: "Added avatar_url, phone, designation to PatchMeReq and handler."

  - task: "Sprint G — Admin Analytics endpoints (5 new)"
    implemented: true
    working: "NA"
    file: "backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
      - working: "NA"
        agent: "main"
        comment: |
          Implemented 5 analytics endpoints, all guarded by admin/super_admin role:
            GET /api/admin/analytics/xp-trends?period=daily|weekly|monthly&buckets=12
            GET /api/admin/analytics/top-contributors?limit=10&quarter=YYYY-QN
            GET /api/admin/analytics/practice-funnel
            GET /api/admin/analytics/revenue
            GET /api/admin/analytics/notification-engagement
          All verified with curl — return JSON shapes required by frontend.

  - task: "Sprint G — Payroll payout endpoints (CSV + PDF)"
    implemented: true
    working: "NA"
    file: "backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
      - working: "NA"
        agent: "main"
        comment: |
          Endpoints (admin/super_admin only):
            GET  /api/admin/payout/quarters        — list quarters with data
            GET  /api/admin/payout/{quarter}        — per-user breakdown + total
            GET  /api/admin/payout/{quarter}/export.csv  — streams CSV
            GET  /api/admin/payout/{quarter}/export.pdf  — reportlab branded PDF
            POST /api/admin/payout/{quarter}/approve     — set incentive_calculations.status=approved
          CSV + PDF generation verified — PDF is 2.6 KB HSI-branded document with totals.

  - task: "Sprint G — Redis pub/sub wiring for multi-instance WS broadcast"
    implemented: true
    working: "NA"
    file: "backend/services/pubsub.py"
    stuck_count: 0
    priority: "medium"
    needs_retesting: true
    status_history:
      - working: "NA"
        agent: "main"
        comment: "services/pubsub.py — async Redis publisher + listener. Wired into /api/admin/publish (also publishes on channel 'hsi:broadcast') and started via FastAPI @on_event('startup'). Local-only broadcast still works when REDIS_URL is unset (preview pod fallback)."

  - task: "Sprint G — Root + health endpoints reflect Sprint G + storage mode"
    implemented: true
    working: "NA"
    file: "backend/server.py"
    stuck_count: 0
    priority: "low"
    needs_retesting: true
    status_history:
      - working: "NA"
        agent: "main"
        comment: "/api/ now returns sprint='G', storage_mode, minio_active. /api/health adds a 'storage' check."

  - task: "Sprint G — Infra: MinIO in docker-compose + 4 DB roles (hsi_api/admin/readonly/migrate) in init.sql"
    implemented: true
    working: "NA"
    file: "docker-compose.yml + scripts/init.sql"
    stuck_count: 0
    priority: "medium"
    needs_retesting: true
    status_history:
      - working: "NA"
        agent: "main"
        comment: "Added MinIO service (+ minio_data volume). init.sql now grants privileges on existing public schema to the 4 roles. Not testable in preview pod; smoke-tested by inspection."

frontend:
  - task: "Sprint G — Admin Analytics page (/admin/analytics)"
    implemented: true
    working: "NA"
    file: "frontend/src/pages/AdminAnalyticsPage.jsx"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
      - working: "NA"
        agent: "main"
        comment: "Recharts-based dashboard — 4 KPI cards + XP line trend (daily/weekly/monthly toggle) + practice funnel pie + notification engagement bar + PO revenue bar + top-contributors table. WCAG focus states and aria roles in place."

  - task: "Sprint G — Admin Payout page (/admin/payout) + CSV/PDF download"
    implemented: true
    working: "NA"
    file: "frontend/src/pages/AdminPayoutPage.jsx"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
      - working: "NA"
        agent: "main"
        comment: "Quarter selector, KPI strip, Export CSV, Export PDF, Approve Register, and full payout table with tfoot totals. All actions aria-labelled."

  - task: "Sprint G — Avatar upload on Profile page"
    implemented: true
    working: "NA"
    file: "frontend/src/pages/ProfilePage.jsx"
    stuck_count: 0
    priority: "medium"
    needs_retesting: true
    status_history:
      - working: "NA"
        agent: "main"
        comment: "Camera FAB on avatar → uploads via /api/uploads (category=avatar) → PATCH /api/users/me {avatar_url}. Adds phone + designation fields to editable form."

  - task: "Sprint G — Practice attachments upload in submit form"
    implemented: true
    working: "NA"
    file: "frontend/src/pages/PracticesPage.jsx"
    stuck_count: 0
    priority: "medium"
    needs_retesting: true
    status_history:
      - working: "NA"
        agent: "main"
        comment: "File picker + list + remove. Uses /api/uploads (category=practice). Attachments list is sent with POST /api/practices."

  - task: "Sprint G — WCAG 2.1 AA hardening"
    implemented: true
    working: "NA"
    file: "frontend/src/index.css + App.js + components/TopBar.jsx"
    stuck_count: 0
    priority: "medium"
    needs_retesting: true
    status_history:
      - working: "NA"
        agent: "main"
        comment: "Global skip-to-main-content link (visible on focus), default visible focus rings on all interactive elements via focus-visible, prefers-reduced-motion honoured. Bell + user-menu get aria-expanded/aria-haspopup + aria-label. Notification rows now buttons with role='menuitem'."

  - task: "Sprint G — Admin navigation links to Analytics + Payout"
    implemented: true
    working: "NA"
    file: "frontend/src/pages/AdminPage.jsx"
    stuck_count: 0
    priority: "low"
    needs_retesting: true
    status_history:
      - working: "NA"
        agent: "main"
        comment: "Added /admin/analytics and /admin/payout quick-links to the red Admin header bar."

metadata:
  created_by: "main_agent"
  version: "3.0"
  test_sequence: 3
  run_ui: false

test_plan:
  current_focus:
    - "Sprint G — POST /api/uploads authenticated multipart endpoint"
    - "Sprint G — Admin Analytics endpoints (5 new)"
    - "Sprint G — Payroll payout endpoints (CSV + PDF)"
    - "Sprint G — PATCH /api/users/me accepts avatar_url/phone/designation"
    - "Sprint G — Redis pub/sub wiring for multi-instance WS broadcast"
  stuck_tasks: []
  test_all: false
  test_priority: "high_first"

agent_communication:
  - agent: "main"
    message: |
      Sprint G implemented. Preview pod has no MinIO container, so storage falls back to
      /tmp/hsi_uploads (served by /api/uploads-local/*). Local curl tests already pass for:
        - GET /api/  → sprint='G', storage_mode='local'
        - GET /api/health → status=healthy, storage check present
        - GET /api/admin/analytics/xp-trends|top-contributors|practice-funnel|revenue|notification-engagement
        - GET /api/admin/payout/quarters / /{q} / /export.csv / /export.pdf
        - POST /api/uploads (multipart)

      Auth flow: admin@hitachi-systems.com / Admin@123 → OTP logged to backend stdout
      (search backend.out.log for "[email][DEV-FALLBACK]" and the 6-digit code).
      The preview env has MFA_ENABLED=true so the testing agent MUST grab the OTP from
      the backend log between /auth/login and /auth/verify-otp.

      Please validate the backend Sprint G endpoints end-to-end — all URIs above.
      Frontend regression is optional (we already smoke-tested login renders).
