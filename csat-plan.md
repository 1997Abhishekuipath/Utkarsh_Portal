# HSI VoC Intelligence Platform — Implementation Plan
> **PRD Version:** v1.0 — April 2026  
> **Target App:** https://optimistic-chaplygin-3.preview.emergentagent.com/apps/nps-csat  
> **Stack:** React 18 · FastAPI (Python) · PostgreSQL 16 · Redis  
> **Classification:** Internal — Project VOICE  

---

## Current State

The `/apps/nps-csat` page is a **fully static UI** — all data is hardcoded in the component.
No backend integration, no real data, no authentication scoping, no CRUD.

The parent HSI platform already provides:
- ✅ PostgreSQL 16 + pgBouncer connection pooling
- ✅ JWT auth (access + refresh tokens) with MFA/OTP
- ✅ Role system: `super_admin`, `admin`, `manager`, `employee`
- ✅ Redis (optional, in-memory fallback active)
- ✅ FastAPI backend on port 8001 with `/api` prefix routing
- ✅ React 18 + Tailwind CSS + Recharts frontend

---

## Stack Adaptation (PRD → Existing Stack)

| PRD Spec | Actual Stack | Notes |
|----------|-------------|-------|
| Node.js + Express | FastAPI (Python) | All API endpoints in `server.py` |
| `jsonwebtoken` (Node) | `PyJWT` (Python) | Already implemented |
| `node-postgres (pg)` | `SQLAlchemy 2.0 + psycopg2` | Already implemented |
| React + Vite | React 18 + CRA / craco | Already running |
| `bcrypt` (Node) | `bcrypt` (Python) | Already implemented |
| `BullMQ` email queue | FastAPI BackgroundTasks + Redis | Simpler, fits existing pattern |
| Anthropic claude-sonnet-4 | `emergentintegrations` Anthropic | Use existing Emergent LLM key |

---

## Database Schema — New Tables Required

All tables use UUID primary keys, `created_at`/`updated_at`, soft-delete via `deleted_at`.

### Phase 1 Tables

```sql
-- Accounts (customer accounts managed by AMs)
CREATE TABLE voc_accounts (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_name     VARCHAR(200) NOT NULL,
  industry         VARCHAR(80),
  account_manager_id UUID REFERENCES users(id),
  practice         VARCHAR(50),        -- cybersecurity/cloud/data-centre/observability
  latest_nps       SMALLINT CHECK (latest_nps BETWEEN -100 AND 100),
  latest_csat      NUMERIC(5,2) CHECK (latest_csat BETWEEN 0 AND 100),
  rag_status       VARCHAR(10) CHECK (rag_status IN ('green','amber','red')),
  total_responses  INTEGER DEFAULT 0,
  created_at       TIMESTAMPTZ DEFAULT NOW(),
  updated_at       TIMESTAMPTZ DEFAULT NOW(),
  deleted_at       TIMESTAMPTZ
);

-- Survey definitions
CREATE TABLE voc_surveys (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  survey_type      VARCHAR(20) CHECK (survey_type IN ('nps','csat','ces','combined')),
  title            VARCHAR(200) NOT NULL,
  main_question    TEXT NOT NULL,
  followup_question TEXT,
  practice         VARCHAR(50),
  thank_you_msg    TEXT,
  version          INTEGER DEFAULT 1,
  created_by       UUID REFERENCES users(id),
  created_at       TIMESTAMPTZ DEFAULT NOW(),
  updated_at       TIMESTAMPTZ DEFAULT NOW(),
  deleted_at       TIMESTAMPTZ
);

-- Email campaigns
CREATE TABLE voc_campaigns (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name             VARCHAR(200) NOT NULL,
  survey_id        UUID REFERENCES voc_surveys(id),
  account_id       UUID REFERENCES voc_accounts(id),
  subject          VARCHAR(300),
  body_html        TEXT,
  status           VARCHAR(20) CHECK (status IN ('draft','scheduled','sending','active','closed')),
  send_at          TIMESTAMPTZ,
  sent_count       INTEGER DEFAULT 0,
  open_count       INTEGER DEFAULT 0,
  click_count      INTEGER DEFAULT 0,
  response_count   INTEGER DEFAULT 0,
  created_by       UUID REFERENCES users(id),
  created_at       TIMESTAMPTZ DEFAULT NOW(),
  updated_at       TIMESTAMPTZ DEFAULT NOW()
);

-- Survey tokens (single-use per respondent)
CREATE TABLE voc_survey_tokens (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  token            VARCHAR(128) UNIQUE NOT NULL,
  campaign_id      UUID REFERENCES voc_campaigns(id),
  account_id       UUID REFERENCES voc_accounts(id),
  respondent_email VARCHAR(255) NOT NULL,
  used             BOOLEAN DEFAULT FALSE,
  used_at          TIMESTAMPTZ,
  expires_at       TIMESTAMPTZ NOT NULL,
  created_at       TIMESTAMPTZ DEFAULT NOW()
);

-- Survey responses
CREATE TABLE voc_responses (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  campaign_id      UUID REFERENCES voc_campaigns(id),
  account_id       UUID REFERENCES voc_accounts(id),
  token_id         UUID REFERENCES voc_survey_tokens(id),
  respondent_email VARCHAR(255) NOT NULL,
  nps_score        SMALLINT CHECK (nps_score BETWEEN 0 AND 10),
  csat_score       SMALLINT CHECK (csat_score BETWEEN 1 AND 5),
  ces_score        SMALLINT CHECK (ces_score BETWEEN 1 AND 7),
  verbatim         TEXT,
  sentiment        VARCHAR(15) CHECK (sentiment IN ('promoter','passive','detractor','neutral')),
  pain_tags        TEXT[],
  submitted_at     TIMESTAMPTZ DEFAULT NOW()
);
```

### Phase 2 Tables

```sql
-- AI-generated insights
CREATE TABLE voc_ai_insights (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  insight_type     VARCHAR(30),   -- 'scr_hypothesis','bcg_matrix','action_plan','strengths'
  payload          JSONB NOT NULL,
  input_hash       VARCHAR(64),   -- SHA-256 of input corpus for cache invalidation
  generated_at     TIMESTAMPTZ DEFAULT NOW(),
  generated_by     UUID REFERENCES users(id)
);

-- Workflow tasks (detractor close-loop)
CREATE TABLE voc_workflow_tasks (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  response_id      UUID REFERENCES voc_responses(id),
  account_id       UUID REFERENCES voc_accounts(id),
  assignee_id      UUID REFERENCES users(id),
  status           VARCHAR(20) CHECK (status IN ('open','in_progress','resolved','escalated')),
  sla_deadline     TIMESTAMPTZ,
  resolution_notes TEXT,
  created_at       TIMESTAMPTZ DEFAULT NOW(),
  updated_at       TIMESTAMPTZ DEFAULT NOW()
);

-- Email delivery log
CREATE TABLE voc_email_logs (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  campaign_id      UUID REFERENCES voc_campaigns(id),
  recipient_email  VARCHAR(255) NOT NULL,
  event_type       VARCHAR(20) CHECK (event_type IN ('sent','opened','clicked','bounced','unsubscribed')),
  occurred_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Suppression list
CREATE TABLE voc_suppression_list (
  email            VARCHAR(255) PRIMARY KEY,
  reason           VARCHAR(50),
  created_at       TIMESTAMPTZ DEFAULT NOW()
);
```

---

## API Endpoints — Backend (FastAPI)

All endpoints prefixed `/api/voc/` to namespace from existing HSI API.

### Phase 1 — Dashboard + Accounts

```
GET  /api/voc/dashboard/kpis          → NPS, CSAT, CES, response rate, promoter %
GET  /api/voc/dashboard/trend         → 12-month time series
GET  /api/voc/dashboard/verbatims     → Recent verbatims with sentiment
GET  /api/voc/dashboard/pain-points   → Ranked pain point list
GET  /api/voc/accounts                → Paginated account list with RAG status
POST /api/voc/accounts                → Create new account
GET  /api/voc/accounts/:id            → Account detail + history
PUT  /api/voc/accounts/:id            → Update account
```

### Phase 2 — Survey + Campaigns

```
GET  /api/voc/surveys                 → List surveys
POST /api/voc/surveys                 → Create survey
PUT  /api/voc/surveys/:id             → Update survey (auto-increments version)
GET  /api/voc/campaigns               → List campaigns
POST /api/voc/campaigns               → Create campaign
POST /api/voc/campaigns/:id/send      → Trigger send (creates tokens + emails)
GET  /api/voc/campaigns/:id/stats     → Open/click/response rates

GET  /s/:token                        → Public survey page (no auth required)
POST /s/:token                        → Submit response (no auth required)
```

### Phase 3 — AI Insights + Workflow

```
POST /api/voc/insights/generate       → Trigger Claude AI analysis
GET  /api/voc/insights/latest         → Return cached latest insights
GET  /api/voc/workflow/tasks          → List open detractor tasks
POST /api/voc/workflow/tasks/:id/resolve → Resolve detractor task
GET  /api/voc/workflow/benchmark      → HSI vs industry benchmarks
```

---

## Module Build Plan

### Phase 1 — Dashboard (Live Data) + Account Intelligence
**Timeline: 1–2 weeks**

#### Backend Tasks
- [ ] Create `voc_*` tables via SQLAlchemy models (add to `server.py`)
- [ ] Implement `GET /api/voc/dashboard/kpis` — aggregate NPS/CSAT/CES from `voc_responses`
- [ ] Implement `GET /api/voc/dashboard/trend` — 12-month GROUP BY month query
- [ ] Implement `GET /api/voc/dashboard/verbatims` — last 20 responses with sentiment
- [ ] Implement `GET /api/voc/dashboard/pain-points` — aggregate `pain_tags` array
- [ ] Implement CRUD for `voc_accounts` with RAG status auto-compute trigger
- [ ] Seed 6 demo accounts matching the current static data (Reliance, Axis, etc.)
- [ ] Seed 140+ demo responses across campaigns for realistic chart data

#### Frontend Tasks — `NPSCsatPage.jsx`
- [ ] Replace static KPI values with `GET /api/voc/dashboard/kpis` data
- [ ] Replace static `trendData` with `GET /api/voc/dashboard/trend` data
- [ ] Replace static verbatims with `GET /api/voc/dashboard/verbatims` data
- [ ] Replace static pain points with `GET /api/voc/dashboard/pain-points` data
- [ ] Wire Account Health section to `GET /api/voc/accounts`
- [ ] Add loading skeletons for all async sections
- [ ] Add auto-refresh polling every 5 minutes (FR-006)

---

### Phase 2 — Survey Builder + Email Campaigns
**Timeline: 2–3 weeks**

#### Survey Builder Tab
- [ ] Survey type selector: NPS / CSAT / CES / Combined
- [ ] Question editor with live preview panel (side-by-side layout)
- [ ] Practice area filter → pre-built question templates
- [ ] Star rating component for CSAT preview
- [ ] 0–10 scale component for NPS preview
- [ ] Save draft + Publish survey buttons → `POST /api/voc/surveys`
- [ ] Survey version history list

#### Email Campaigns Tab
- [ ] Campaign composer with live HTML email preview
- [ ] Merge tag toolbar: `{{CustomerName}}`, `{{Practice}}`, `{{AccountManager}}`, etc.
- [ ] Account selector + survey selector dropdowns
- [ ] Send now vs Schedule with date/time picker
- [ ] Campaign status board (Draft → Scheduled → Sending → Active → Closed)
- [ ] Stats panel: sent / opened / clicked / responded (FR-025)
- [ ] Day-5 auto-reminder toggle (FR-026)

#### Public Survey Page — `/s/:token`
- [ ] New route in `App.js`: `<Route path="/s/:token" element={<SurveyResponsePage />} />`
- [ ] Token validation on load (`GET /s/:token`)
- [ ] Render survey questions based on survey type
- [ ] Submit handler with score + verbatim → `POST /s/:token`
- [ ] Thank-you screen post-submit
- [ ] Single-use enforcement (used tokens show "already submitted")

---

### Phase 3 — AI Insights + Workflow Engine
**Timeline: 2–3 weeks**

#### AI Insights Tab
- [ ] Call `POST /api/voc/insights/generate` using Emergent LLM Key + Anthropic Claude API
- [ ] Prompt engineering: send verbatim corpus → request McKinsey SCR hypothesis
- [ ] Render SCR hypothesis (Situation / Complication / Resolution)
- [ ] BCG matrix visualisation — plot pain points on Frequency × Impact axes (Recharts ScatterChart)
- [ ] "Strengths to Scale" section with Bain-style praise theme extraction
- [ ] 90-day action plan list with priority ranking and NPS impact estimates
- [ ] "Regenerate" button with loading state + timestamp of last generation
- [ ] Cache: store insights in `voc_ai_insights`, serve from cache < 24 hours old

#### Workflow Engine Tab
- [ ] Visual 3-phase workflow diagram:
  - Phase 1: Trigger & Design (survey creation, account targeting)
  - Phase 2: Collect & Monitor (live response tracking)
  - Phase 3: Analyse & Act (AI insights, action items, close-loop)
- [ ] Detractor alert panel — list of NPS ≤ 6 responses requiring follow-up
- [ ] Task cards: Assignee / SLA countdown / Status (Open / In Progress / Resolved)
- [ ] Resolve task modal → `POST /api/voc/workflow/tasks/:id/resolve`
- [ ] Benchmark comparison table:
  | Metric | HSI Current | IT India Avg | Global Avg | World-class | HSI Target |
  |--------|------------|-------------|-----------|------------|-----------|
  | NPS    | +62        | +28         | +32        | +50         | +72        |
  | CSAT   | 87%        | 74%         | 78%        | 90%         | 92%        |

---

### Phase 4 — Security, Performance & Production-Readiness
**Timeline: 1–2 weeks**

- [ ] Row-Level Security: AMs can only see their own accounts (`account_manager_id = current_user`)
- [ ] Rate limiting on survey submission endpoint (prevent ballot stuffing)
- [ ] Survey token expiry enforcement (48-hour window)
- [ ] Unsubscribe endpoint + suppression list check before every email send
- [ ] Audit log entries for all state-changing operations
- [ ] PostgreSQL indexes: `voc_responses(campaign_id)`, `voc_responses(account_id, submitted_at)`, `voc_responses(sentiment)`
- [ ] `EXPLAIN ANALYZE` review for all dashboard aggregate queries
- [ ] API response caching for `/api/voc/dashboard/kpis` (30s Redis TTL)

---

## AI Integration Details (Phase 3)

**Provider:** Anthropic Claude via `emergentintegrations` library  
**Key:** Emergent Universal LLM Key (from platform profile)

### Insight Generation Prompt Structure

```python
system_prompt = """
You are a McKinsey-trained customer experience analyst for Hitachi Systems India.
Analyse the provided VoC response corpus and generate:
1. SCR Hypothesis (Situation, Complication, Resolution)  
2. Top 5 pain points ranked by frequency × impact
3. Top 4 praise themes for "Strengths to Scale"
4. 90-day action plan with 6 prioritised initiatives

Output strictly in JSON format.
"""

user_prompt = f"""
Survey period: {period}
Total responses: {total}
NPS: +{nps} | CSAT: {csat}% | CES: {ces}
Verbatims (sample of {len(verbatims)}):
{json.dumps(verbatims, indent=2)}
"""
```

### Stored Insight Schema

```json
{
  "scr": {
    "situation": "...",
    "complication": "...",
    "resolution": "..."
  },
  "pain_points": [
    { "theme": "Response Time", "frequency": 34, "impact": 8.2, "accounts": ["Reliance", "Axis"] }
  ],
  "strengths": [
    { "theme": "Technical Expertise", "mentions": 41, "representative_quote": "..." }
  ],
  "action_plan": [
    { "initiative": "SLA Triage Process", "priority": 1, "nps_impact_estimate": "+4pts", "owner": "Cybersecurity Practice", "deadline_days": 30 }
  ]
}
```

---

## Component Architecture

```
src/
├── pages/apps/
│   ├── NPSCsatPage.jsx          ← Main shell (tab router) — exists, needs live data
│   └── voc/
│       ├── DashboardTab.jsx     ← Phase 1: KPIs, charts, verbatims
│       ├── SurveyBuilderTab.jsx ← Phase 2: survey editor + live preview
│       ├── CampaignsTab.jsx     ← Phase 2: campaign composer + stats
│       ├── AccountsTab.jsx      ← Phase 1: account cards + RAG
│       ├── AIInsightsTab.jsx    ← Phase 3: Claude insights + BCG matrix
│       └── WorkflowTab.jsx      ← Phase 3: workflow diagram + tasks
│
├── pages/
│   └── SurveyResponsePage.jsx  ← Phase 2: public survey page (/s/:token)
│
└── hooks/
    ├── useVocDashboard.js       ← SWR/polling for KPI data
    └── useVocAccounts.js        ← Account list with filtering
```

---

## Functional Requirements Traceability

| FR | Description | Phase | Status |
|----|-------------|-------|--------|
| FR-001 | NPS score display with trend | 1 | ⬜ Static only |
| FR-002 | CSAT % with MoM trend | 1 | ⬜ Static only |
| FR-003 | CES score display | 1 | ⬜ Static only |
| FR-004 | Promoter/Passive/Detractor % | 1 | ⬜ Static only |
| FR-005 | Response count + rate | 1 | ⬜ Static only |
| FR-006 | Auto-refresh every 5 min | 1 | ⬜ Not implemented |
| FR-007 | 12-month trend chart | 1 | ⬜ Static only |
| FR-008 | NPS gauge with arc | 1 | ✅ Built (static data) |
| FR-009 | CSAT star distribution | 1 | ✅ Built (static data) |
| FR-010 | Verbatim feed with AI tagging | 1 | ⬜ Static only |
| FR-011 | Pain point ranked list | 1 | ⬜ Static only |
| FR-012 | AI praise/strength themes | 1 | ⬜ Static only |
| FR-013 | Account health mini-list | 1 | ⬜ Static only |
| FR-014 | 4 survey types | 2 | ⬜ Not implemented |
| FR-015 | Live survey preview | 2 | ⬜ Not implemented |
| FR-016 | Practice template filter | 2 | ⬜ Not implemented |
| FR-017 | Survey versioning | 2 | ⬜ Not implemented |
| FR-018 | Single-use tokenised URLs | 2 | ⬜ Not implemented |
| FR-019 | Configurable thank-you screen | 2 | ⬜ Not implemented |
| FR-020 | Mobile-responsive surveys | 2 | ⬜ Not implemented |
| FR-021 | Live email preview | 2 | ⬜ Not implemented |
| FR-022 | Personalisation merge tags | 2 | ⬜ Not implemented |
| FR-023 | Campaign scheduling | 2 | ⬜ Not implemented |
| FR-024 | Campaign state machine | 2 | ⬜ Not implemented |
| FR-025 | Real-time delivery tracking | 2 | ⬜ Not implemented |
| FR-026 | Day-5 auto-reminder | 2 | ⬜ Not implemented |
| FR-027 | Unsubscribe mechanism | 2 | ⬜ Not implemented |
| FR-028 | Email audit log | 2 | ⬜ Not implemented |
| FR-029 | Account cards with scores | 1 | ⬜ Static only |
| FR-030 | RAG status logic | 1 | ⬜ Not implemented |
| FR-031 | One-click send survey | 2 | ⬜ Not implemented |
| FR-032 | Account response history | 2 | ⬜ Not implemented |
| FR-033 | Detractor alert flags | 3 | ⬜ Not implemented |
| FR-034 | Account CSV export | 2 | ⬜ Not implemented |
| FR-035 | AI SCR hypothesis (Claude) | 3 | ⬜ Not implemented |
| FR-036 | BCG matrix view | 3 | ⬜ Not implemented |
| FR-037 | Bain strengths section | 3 | ⬜ Not implemented |
| FR-038 | 90-day action plan | 3 | ⬜ Not implemented |
| FR-039 | Stored AI insights | 3 | ⬜ Not implemented |
| FR-040 | Manual regenerate button | 3 | ⬜ Not implemented |
| FR-041 | Visual workflow diagram | 3 | ⬜ Not implemented |
| FR-042 | Detractor close-loop tasks | 3 | ⬜ Not implemented |
| FR-043 | Benchmark comparison table | 3 | ⬜ Not implemented |
| FR-044 | Workflow step tracking | 3 | ⬜ Not implemented |

**Legend:** ✅ Done · 🔄 In Progress · ⬜ Not Started

---

## Immediate Next Steps (Start Here)

1. **Get Anthropic API key** — required for Phase 3 AI Insights.  
   User provides key → stored in `backend/.env` as handled by Emergent LLM integration.

2. **Phase 1 backend** — Add `voc_*` SQLAlchemy models + seed data + dashboard API endpoints.

3. **Wire Dashboard** — Replace all static data in `NPSCsatPage.jsx` → `DashboardTab.jsx` with live API calls.

4. **Phase 2** — Build Survey Builder tab + Campaigns tab + public `/s/:token` page.

5. **Phase 3** — AI Insights tab + Workflow tab.

---

*Plan generated from PRD v1.0 · April 2026 · HSI VoC Intelligence Platform · Project VOICE*
