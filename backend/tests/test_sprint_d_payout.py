"""
Sprint D — Payout state-machine + live /dashboard/upcoming tests.
Run: pytest /app/backend/tests/test_sprint_d_payout.py -v
"""
import os
import pytest
import requests
from datetime import date

BASE = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE, "REACT_APP_BACKEND_URL must be set"

DEMO_OTP = "000000"
ADMIN = ("admin@hitachi-systems.com", "Admin@123")
EMP   = ("employee@hitachi-systems.com", "Employee@123")


# ───────── auth helpers ─────────
def login(email: str, password: str) -> str:
    """Complete MFA login flow — returns access_token."""
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login {email} → {r.status_code} {r.text}"
    j = r.json()
    if j.get("requires_otp"):
        v = requests.post(f"{BASE}/api/auth/verify-otp",
                          json={"email": email, "code": DEMO_OTP, "purpose": "login"},
                          timeout=15)
        assert v.status_code == 200, f"verify-otp {email} → {v.status_code} {v.text}"
        return v.json()["access_token"]
    return j["access_token"]


def h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ───────── fixtures ─────────
@pytest.fixture(scope="module")
def admin_token():
    return login(*ADMIN)


@pytest.fixture(scope="module")
def emp_token():
    return login(*EMP)


@pytest.fixture(scope="module")
def seeded_quarter(admin_token):
    """Pick quarter with XP rows (prefer 2026-Q2)."""
    r = requests.get(f"{BASE}/api/admin/payout/quarters", headers=h(admin_token), timeout=15)
    assert r.status_code == 200
    quarters = r.json()
    assert quarters, "No quarters returned from /api/admin/payout/quarters"
    for q in quarters:
        if q["quarter"] == "2026-Q2":
            return q["quarter"]
    return quarters[0]["quarter"]


# ═══════════════════════════════════════════════════════════════════════════════
# 1. /dashboard/upcoming — live data, NOT hard-coded mock
# ═══════════════════════════════════════════════════════════════════════════════
class TestUpcomingLive:
    def test_upcoming_as_employee_returns_live_data(self, emp_token):
        r = requests.get(f"{BASE}/api/dashboard/upcoming", headers=h(emp_token), timeout=15)
        assert r.status_code == 200, r.text
        items = r.json()
        assert isinstance(items, list)
        assert len(items) > 0
        # No hard-coded mock strings allowed
        mock_tokens = [
            "All For SPTS",
            "Visitor — Bajaj Finance",
            "Visitor - Bajaj Finance",
            "365 Incentive Payout",
        ]
        joined = " | ".join(str(i) for i in items)
        for tok in mock_tokens:
            assert tok not in joined, f"Hard-coded mock token '{tok}' leaked in /dashboard/upcoming"
        # Each item has required live-data fields
        for it in items:
            assert "id" in it and "title" in it
            assert "type" in it, "Missing 'type' — live payload must tag tech_day/payout/empty"
            assert it["type"] in ("tech_day", "payout", "empty")

    def test_upcoming_contains_payout_with_current_quarter(self, emp_token):
        r = requests.get(f"{BASE}/api/dashboard/upcoming", headers=h(emp_token), timeout=15)
        items = r.json()
        payouts = [i for i in items if i.get("type") == "payout"]
        # There should be at least 1 payout entry for a typical live system
        # (unless the current quarter's payout-due date is already past).
        if payouts:
            p = payouts[0]
            assert "Incentive Payout" in p["title"]
            assert p["id"].startswith("payout-")


# ═══════════════════════════════════════════════════════════════════════════════
# 2. /api/admin/payout/quarters
# ═══════════════════════════════════════════════════════════════════════════════
class TestQuartersList:
    def test_quarters_list(self, admin_token):
        r = requests.get(f"{BASE}/api/admin/payout/quarters",
                         headers=h(admin_token), timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) > 0
        for q in data:
            assert "quarter" in q and "users" in q and "xp_total" in q
            assert isinstance(q["users"], int) and isinstance(q["xp_total"], int)

    def test_quarters_rbac(self, emp_token):
        r = requests.get(f"{BASE}/api/admin/payout/quarters",
                         headers=h(emp_token), timeout=15)
        assert r.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════════
# 3. /api/admin/payout/{q}/calcs — shape check
# ═══════════════════════════════════════════════════════════════════════════════
class TestCalcsEndpoint:
    def test_calcs_shape(self, admin_token, seeded_quarter):
        r = requests.get(f"{BASE}/api/admin/payout/{seeded_quarter}/calcs",
                         headers=h(admin_token), timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data["quarter"] == seeded_quarter
        assert "counts" in data
        for s in ("draft", "approved", "paid", "on_hold"):
            assert s in data["counts"]
            assert isinstance(data["counts"][s], int)
        assert "items" in data and isinstance(data["items"], list)
        for i in data["items"]:
            assert "id" in i and "user_id" in i and "name" in i and "status" in i
            assert i["status"] in ("draft", "approved", "paid", "on_hold")

    def test_calcs_rbac(self, emp_token, seeded_quarter):
        r = requests.get(f"{BASE}/api/admin/payout/{seeded_quarter}/calcs",
                         headers=h(emp_token), timeout=15)
        assert r.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════════
# 4. State machine: approve → hold → resume → approve → mark-paid round-trip
# ═══════════════════════════════════════════════════════════════════════════════
class TestStateMachine:
    def test_approve_creates_approved_rows(self, admin_token, seeded_quarter):
        r = requests.post(f"{BASE}/api/admin/payout/{seeded_quarter}/approve",
                          headers=h(admin_token), timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["quarter"] == seeded_quarter
        assert "approved" in body and isinstance(body["approved"], int)
        # Verify counts reflect approved rows (assuming seed has at least one draft/paid)
        c = requests.get(f"{BASE}/api/admin/payout/{seeded_quarter}/calcs",
                         headers=h(admin_token), timeout=15).json()
        total_rows = sum(c["counts"].values())
        assert total_rows > 0
        # At least one row should end up approved or paid (paid retained)
        assert c["counts"]["approved"] + c["counts"]["paid"] > 0

    def test_approve_rbac(self, emp_token, seeded_quarter):
        r = requests.post(f"{BASE}/api/admin/payout/{seeded_quarter}/approve",
                          headers=h(emp_token), timeout=15)
        assert r.status_code == 403

    def test_hold_then_resume_roundtrip(self, admin_token, seeded_quarter):
        # Fetch a non-paid row
        calcs = requests.get(f"{BASE}/api/admin/payout/{seeded_quarter}/calcs",
                             headers=h(admin_token), timeout=15).json()
        target = next((i for i in calcs["items"] if i["status"] != "paid"), None)
        if not target:
            pytest.skip("No non-paid rows available to hold/resume")

        cid = target["id"]
        prev_status = target["status"]

        # HOLD
        h_r = requests.post(f"{BASE}/api/admin/payout/calc/{cid}/hold",
                            headers=h(admin_token), timeout=15)
        assert h_r.status_code == 200, h_r.text
        assert h_r.json()["status"] == "on_hold"

        # Verify via GET
        c2 = requests.get(f"{BASE}/api/admin/payout/{seeded_quarter}/calcs",
                          headers=h(admin_token), timeout=15).json()
        row = next(i for i in c2["items"] if i["id"] == cid)
        assert row["status"] == "on_hold"

        # RESUME (requires status=on_hold)
        r_r = requests.post(f"{BASE}/api/admin/payout/calc/{cid}/resume",
                            headers=h(admin_token), timeout=15)
        assert r_r.status_code == 200, r_r.text
        assert r_r.json()["status"] == "draft"

        # Resume again must 409 (now draft, not on_hold)
        r_r2 = requests.post(f"{BASE}/api/admin/payout/calc/{cid}/resume",
                             headers=h(admin_token), timeout=15)
        assert r_r2.status_code == 409

    def test_hold_paid_rejected_409(self, admin_token, seeded_quarter):
        calcs = requests.get(f"{BASE}/api/admin/payout/{seeded_quarter}/calcs",
                             headers=h(admin_token), timeout=15).json()
        paid = next((i for i in calcs["items"] if i["status"] == "paid"), None)
        if not paid:
            pytest.skip("No paid row available to test 409 on hold")
        r = requests.post(f"{BASE}/api/admin/payout/calc/{paid['id']}/hold",
                          headers=h(admin_token), timeout=15)
        assert r.status_code == 409

    def test_hold_rbac(self, emp_token, admin_token, seeded_quarter):
        calcs = requests.get(f"{BASE}/api/admin/payout/{seeded_quarter}/calcs",
                             headers=h(admin_token), timeout=15).json()
        if not calcs["items"]:
            pytest.skip("No rows")
        cid = calcs["items"][0]["id"]
        r = requests.post(f"{BASE}/api/admin/payout/calc/{cid}/hold",
                          headers=h(emp_token), timeout=15)
        assert r.status_code == 403

    def test_resume_rbac(self, emp_token, admin_token, seeded_quarter):
        calcs = requests.get(f"{BASE}/api/admin/payout/{seeded_quarter}/calcs",
                             headers=h(admin_token), timeout=15).json()
        if not calcs["items"]:
            pytest.skip("No rows")
        cid = calcs["items"][0]["id"]
        r = requests.post(f"{BASE}/api/admin/payout/calc/{cid}/resume",
                          headers=h(emp_token), timeout=15)
        assert r.status_code == 403

    def test_mark_paid_and_409_when_empty(self, admin_token, seeded_quarter):
        # Ensure we have approved rows first — approve will re-approve any draft
        requests.post(f"{BASE}/api/admin/payout/{seeded_quarter}/approve",
                      headers=h(admin_token), timeout=20)
        c_before = requests.get(f"{BASE}/api/admin/payout/{seeded_quarter}/calcs",
                                headers=h(admin_token), timeout=15).json()
        approved_before = c_before["counts"]["approved"]

        if approved_before == 0:
            # No approved rows — mark-paid must 409
            r = requests.post(
                f"{BASE}/api/admin/payout/{seeded_quarter}/mark-paid",
                headers=h(admin_token),
                json={"payroll_ref": f"TEST-{seeded_quarter}",
                      "payout_date": date.today().isoformat()},
                timeout=15)
            assert r.status_code == 409
            pytest.skip("No approved rows; 409 branch verified")

        r = requests.post(
            f"{BASE}/api/admin/payout/{seeded_quarter}/mark-paid",
            headers=h(admin_token),
            json={"payroll_ref": f"TEST-{seeded_quarter}",
                  "payout_date": date.today().isoformat()},
            timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["paid"] == approved_before
        assert body["payroll_ref"] == f"TEST-{seeded_quarter}"
        assert body["payout_date"] == date.today().isoformat()

        # Now zero approved → 409
        r2 = requests.post(
            f"{BASE}/api/admin/payout/{seeded_quarter}/mark-paid",
            headers=h(admin_token),
            json={"payroll_ref": "TEST-EMPTY"},
            timeout=15)
        assert r2.status_code == 409

        # Verify paid count persisted via GET
        c_after = requests.get(f"{BASE}/api/admin/payout/{seeded_quarter}/calcs",
                               headers=h(admin_token), timeout=15).json()
        assert c_after["counts"]["approved"] == 0
        assert c_after["counts"]["paid"] >= approved_before

    def test_mark_paid_rbac(self, emp_token, seeded_quarter):
        r = requests.post(f"{BASE}/api/admin/payout/{seeded_quarter}/mark-paid",
                          headers=h(emp_token),
                          json={"payroll_ref": "TEST"}, timeout=15)
        assert r.status_code == 403
