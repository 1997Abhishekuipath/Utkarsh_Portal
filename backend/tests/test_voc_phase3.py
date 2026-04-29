"""
Phase 3 — VoC AI Insights + Workflow Tasks (OpenRouter integration)

Covers:
- POST /api/voc/insights/generate         (live OpenRouter / Claude Sonnet 4)
- GET  /api/voc/insights
- GET  /api/voc/insights/{id}
- GET  /api/voc/workflow/tasks  (+ filters)
- PATCH /api/voc/workflow/tasks/{id}
- GET  /api/voc/workflow/stats

Phase 1 / Phase 2 regression smoke (status-only)
"""
import os
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE, "REACT_APP_BACKEND_URL not set"

ADMIN_EMAIL = "admin@hitachi-systems.com"
ADMIN_PW    = "Admin@123"
DEMO_OTP    = "000000"


# ──────────────────────────── auth helpers ────────────────────────────
def _login(email: str, password: str) -> str:
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    j = r.json()
    if j.get("requires_otp"):
        v = requests.post(f"{BASE}/api/auth/verify-otp",
                          json={"email": email, "code": DEMO_OTP, "purpose": "login"},
                          timeout=15)
        assert v.status_code == 200, f"otp verify failed: {v.status_code} {v.text}"
        return v.json()["access_token"]
    return j["access_token"]


@pytest.fixture(scope="module")
def admin_token() -> str:
    return _login(ADMIN_EMAIL, ADMIN_PW)


@pytest.fixture(scope="module")
def H(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ──────────────────────────── Workflow ────────────────────────────────
class TestWorkflow:
    def test_workflow_stats(self, H):
        r = requests.get(f"{BASE}/api/voc/workflow/stats", headers=H, timeout=10)
        assert r.status_code == 200, r.text
        j = r.json()
        for k in ("open", "in_progress", "resolved", "total"):
            assert k in j, f"missing stat: {k}"
        assert j["total"] == j["open"] + j["in_progress"] + j["resolved"]
        # Should have ~12 detractor tasks seeded
        assert j["total"] >= 10, f"expected ≥10 seeded tasks, got {j['total']}"

    def test_workflow_tasks_list(self, H):
        r = requests.get(f"{BASE}/api/voc/workflow/tasks", headers=H, timeout=15)
        assert r.status_code == 200, r.text
        tasks = r.json()
        assert isinstance(tasks, list)
        assert len(tasks) >= 10
        # Schema sanity on first task
        t = tasks[0]
        for k in ("id", "status", "account_id", "response", "created_at"):
            assert k in t, f"missing key {k} in task"
        assert t["status"] in ("open", "in_progress", "resolved")
        assert t["response"] is None or "verbatim" in t["response"]

    def test_workflow_tasks_filter_by_status(self, H):
        r = requests.get(f"{BASE}/api/voc/workflow/tasks?status=open",
                         headers=H, timeout=10)
        assert r.status_code == 200
        for t in r.json():
            assert t["status"] == "open"

    def test_workflow_tasks_filter_by_account(self, H):
        all_r = requests.get(f"{BASE}/api/voc/workflow/tasks", headers=H, timeout=10)
        all_tasks = all_r.json()
        if not all_tasks:
            pytest.skip("no tasks to filter")
        acc_id = next((t["account_id"] for t in all_tasks if t.get("account_id")), None)
        if not acc_id:
            pytest.skip("no task with account_id")
        r = requests.get(f"{BASE}/api/voc/workflow/tasks?account_id={acc_id}",
                         headers=H, timeout=10)
        assert r.status_code == 200
        filtered = r.json()
        assert filtered, "filter returned 0"
        for t in filtered:
            assert t["account_id"] == acc_id

    def test_workflow_patch_status_and_resolved_at(self, H):
        # Pick first 'open' task, move to in_progress, then resolved, then back to open.
        r = requests.get(f"{BASE}/api/voc/workflow/tasks?status=open",
                         headers=H, timeout=10)
        tasks = r.json()
        if not tasks:
            pytest.skip("no open tasks")
        tid = tasks[0]["id"]

        # → in_progress
        p1 = requests.patch(f"{BASE}/api/voc/workflow/tasks/{tid}",
                            headers=H,
                            json={"status": "in_progress",
                                  "resolution_notes": "TEST_PHASE3_progress"},
                            timeout=10)
        assert p1.status_code == 200, p1.text
        assert p1.json()["status"] == "in_progress"
        assert p1.json()["resolved_at"] is None
        assert p1.json()["resolution_notes"] == "TEST_PHASE3_progress"

        # → resolved (resolved_at must be set)
        p2 = requests.patch(f"{BASE}/api/voc/workflow/tasks/{tid}",
                            headers=H,
                            json={"status": "resolved",
                                  "resolution_notes": "TEST_PHASE3_done"},
                            timeout=10)
        assert p2.status_code == 200, p2.text
        assert p2.json()["status"] == "resolved"
        assert p2.json()["resolved_at"] is not None

        # → reset to open (resolved_at must clear)
        p3 = requests.patch(f"{BASE}/api/voc/workflow/tasks/{tid}",
                            headers=H,
                            json={"status": "open"},
                            timeout=10)
        assert p3.status_code == 200, p3.text
        assert p3.json()["status"] == "open"
        assert p3.json()["resolved_at"] is None

    def test_workflow_patch_invalid_status(self, H):
        r = requests.get(f"{BASE}/api/voc/workflow/tasks", headers=H, timeout=10)
        tasks = r.json()
        if not tasks:
            pytest.skip("no tasks")
        tid = tasks[0]["id"]
        bad = requests.patch(f"{BASE}/api/voc/workflow/tasks/{tid}",
                             headers=H, json={"status": "wibble"}, timeout=10)
        assert bad.status_code == 400

    def test_workflow_patch_404(self, H):
        bad = requests.patch(f"{BASE}/api/voc/workflow/tasks/no-such-id",
                             headers=H, json={"status": "open"}, timeout=10)
        assert bad.status_code == 404


# ──────────────────────────── AI Insights ─────────────────────────────
class TestAiInsights:
    def test_insights_list_initial(self, H):
        r = requests.get(f"{BASE}/api/voc/insights", headers=H, timeout=10)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_insights_generate_live_openrouter(self, H):
        """LIVE call to OpenRouter — gives a 90s timeout."""
        r = requests.post(
            f"{BASE}/api/voc/insights/generate",
            headers=H,
            json={"period": "Q2 2026", "days": 90},
            timeout=90,
        )
        assert r.status_code == 200, f"generate failed: {r.status_code} {r.text[:500]}"
        j = r.json()
        assert "id" in j and j["id"]
        assert "insights" in j
        ins = j["insights"]
        # Required insight keys per PRD
        for k in ("executive_summary", "key_themes", "pain_points",
                  "strengths", "recommendations", "risk_accounts"):
            assert k in ins, f"missing insight key: {k}"
        # Loose shape checks
        assert isinstance(ins["key_themes"], list)
        assert isinstance(ins["pain_points"], list)
        assert isinstance(ins["strengths"], list)
        assert isinstance(ins["recommendations"], list)
        # Recommendations should have action/priority shape
        if ins["recommendations"]:
            rec = ins["recommendations"][0]
            for k in ("action", "priority"):
                assert k in rec, f"rec missing {k}"

        # Persist + side-effects
        gid = j["id"]
        list_r = requests.get(f"{BASE}/api/voc/insights", headers=H, timeout=10)
        assert list_r.status_code == 200
        ids = [x["id"] for x in list_r.json()]
        assert gid in ids, "newly generated insight not in list"

        single = requests.get(f"{BASE}/api/voc/insights/{gid}", headers=H, timeout=10)
        assert single.status_code == 200
        sj = single.json()
        assert sj["id"] == gid
        assert "insights" in sj and "executive_summary" in sj["insights"]

    def test_insights_get_404(self, H):
        r = requests.get(f"{BASE}/api/voc/insights/does-not-exist",
                         headers=H, timeout=10)
        assert r.status_code == 404


# ──────────────────────────── Phase 1 / 2 regression ──────────────────
class TestRegression:
    @pytest.mark.parametrize("path", [
        "/api/voc/dashboard/kpis",
        "/api/voc/dashboard/trend",
        "/api/voc/dashboard/verbatims",
        "/api/voc/dashboard/pain-points",
        "/api/voc/dashboard/csat-distribution",
        "/api/voc/dashboard/strengths",
        "/api/voc/accounts",
        "/api/voc/surveys",
        "/api/voc/campaigns",
    ])
    def test_phase1_phase2_endpoints_200(self, H, path):
        r = requests.get(f"{BASE}{path}", headers=H, timeout=15)
        assert r.status_code == 200, f"{path} -> {r.status_code} {r.text[:200]}"
