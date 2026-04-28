"""
Sprint D follow-ups — payroll_ref regex, cancelled terminal state, calcs counts.
Run: pytest /app/backend/tests/test_sprint_d_followups.py -v
"""
import os
import subprocess
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE, "REACT_APP_BACKEND_URL must be set"

DEMO_OTP = "000000"
ADMIN = ("admin@hitachi-systems.com", "Admin@123")
EMP   = ("employee@hitachi-systems.com", "Employee@123")
QUARTER = "2026-Q2"


def _login(email, password):
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, r.text
    j = r.json()
    if j.get("requires_otp"):
        v = requests.post(f"{BASE}/api/auth/verify-otp",
                          json={"email": email, "code": DEMO_OTP, "purpose": "login"},
                          timeout=15)
        assert v.status_code == 200, v.text
        return v.json()["access_token"]
    return j["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}", "Content-Type": "application/json"}


def _reset_quarter_to_draft():
    """Force all 2026-Q2 calc rows back to draft so happy-path tests have data."""
    sql = (
        "UPDATE incentive_calculations "
        "SET status='draft', payout_date=NULL, payroll_ref=NULL, "
        "approved_at=NULL, approved_by=NULL "
        f"WHERE quarter='{QUARTER}';"
    )
    subprocess.run(
        ["psql", "-h", "localhost", "-U", "hsi_user", "-d", "hsi_portal", "-c", sql],
        env={**os.environ, "PGPASSWORD": "hsi_password123"},
        check=True, capture_output=True,
    )


@pytest.fixture(scope="module")
def admin_token():
    return _login(*ADMIN)


@pytest.fixture(scope="module")
def emp_token():
    return _login(*EMP)


# ─────────────── payroll_ref regex validation ───────────────
class TestPayrollRefRegex:
    def test_invalid_payroll_ref_400(self, admin_token):
        _reset_quarter_to_draft()
        # First approve so we have approved rows
        r = requests.post(f"{BASE}/api/admin/payout/{QUARTER}/approve",
                          headers=_h(admin_token), timeout=15)
        assert r.status_code == 200
        # Lower-case + space — should fail regex
        r = requests.post(f"{BASE}/api/admin/payout/{QUARTER}/mark-paid",
                          headers=_h(admin_token),
                          json={"payroll_ref": "bad ref!"}, timeout=15)
        assert r.status_code == 400
        assert "^[A-Z0-9-]{3,40}$" in r.json().get("detail", "")

    def test_too_short_payroll_ref_400(self, admin_token):
        r = requests.post(f"{BASE}/api/admin/payout/{QUARTER}/mark-paid",
                          headers=_h(admin_token),
                          json={"payroll_ref": "AB"}, timeout=15)  # only 2 chars
        assert r.status_code == 400

    def test_lowercase_payroll_ref_400(self, admin_token):
        r = requests.post(f"{BASE}/api/admin/payout/{QUARTER}/mark-paid",
                          headers=_h(admin_token),
                          json={"payroll_ref": "payroll-q2-2026"}, timeout=15)
        assert r.status_code == 400

    def test_valid_payroll_ref_persists(self, admin_token):
        _reset_quarter_to_draft()
        requests.post(f"{BASE}/api/admin/payout/{QUARTER}/approve",
                      headers=_h(admin_token), timeout=15)
        valid_ref = "PAYROLL-Q2-2026-A"
        r = requests.post(f"{BASE}/api/admin/payout/{QUARTER}/mark-paid",
                          headers=_h(admin_token),
                          json={"payroll_ref": valid_ref}, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["payroll_ref"] == valid_ref
        # Verify GET returns the same ref
        g = requests.get(f"{BASE}/api/admin/payout/{QUARTER}/calcs",
                         headers=_h(admin_token), timeout=15)
        paid = [c for c in g.json()["items"] if c["status"] == "paid"]
        assert paid, "expected at least one paid row"
        assert all(c["payroll_ref"] == valid_ref for c in paid)


# ─────────────── 'cancelled' terminal state ───────────────
class TestCancelledState:
    def test_cancel_draft_calc(self, admin_token):
        _reset_quarter_to_draft()
        g = requests.get(f"{BASE}/api/admin/payout/{QUARTER}/calcs",
                         headers=_h(admin_token), timeout=15)
        items = g.json()["items"]
        assert items, "need at least one draft row to test cancel"
        cid = items[0]["id"]
        r = requests.post(f"{BASE}/api/admin/payout/calc/{cid}/cancel",
                          headers=_h(admin_token),
                          json={"reason": "test-employee-separated"}, timeout=15)
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "cancelled"
        assert body["previous_status"] == "draft"
        assert body["reason"] == "test-employee-separated"

    def test_cancel_already_cancelled_409(self, admin_token):
        # Reuse the cancelled row from test_cancel_draft_calc
        g = requests.get(f"{BASE}/api/admin/payout/{QUARTER}/calcs",
                         headers=_h(admin_token), timeout=15)
        cancelled = [c for c in g.json()["items"] if c["status"] == "cancelled"]
        assert cancelled, "previous test should have left a cancelled row"
        cid = cancelled[0]["id"]
        r = requests.post(f"{BASE}/api/admin/payout/calc/{cid}/cancel",
                          headers=_h(admin_token), json={}, timeout=15)
        assert r.status_code == 409
        assert "already cancelled" in r.json()["detail"].lower()

    def test_cannot_hold_cancelled_409(self, admin_token):
        g = requests.get(f"{BASE}/api/admin/payout/{QUARTER}/calcs",
                         headers=_h(admin_token), timeout=15)
        cancelled = [c for c in g.json()["items"] if c["status"] == "cancelled"]
        assert cancelled
        cid = cancelled[0]["id"]
        r = requests.post(f"{BASE}/api/admin/payout/calc/{cid}/hold",
                          headers=_h(admin_token), timeout=15)
        assert r.status_code == 409

    def test_cannot_cancel_paid_409(self, admin_token):
        # Get a paid row from prior tests (TestPayrollRefRegex.test_valid_payroll_ref_persists)
        g = requests.get(f"{BASE}/api/admin/payout/{QUARTER}/calcs",
                         headers=_h(admin_token), timeout=15)
        paid = [c for c in g.json()["items"] if c["status"] == "paid"]
        if not paid:
            # Set one up
            _reset_quarter_to_draft()
            requests.post(f"{BASE}/api/admin/payout/{QUARTER}/approve",
                          headers=_h(admin_token), timeout=15)
            requests.post(f"{BASE}/api/admin/payout/{QUARTER}/mark-paid",
                          headers=_h(admin_token),
                          json={"payroll_ref": "PAYROLL-TEST-PAID"}, timeout=15)
            g = requests.get(f"{BASE}/api/admin/payout/{QUARTER}/calcs",
                             headers=_h(admin_token), timeout=15)
            paid = [c for c in g.json()["items"] if c["status"] == "paid"]
        assert paid
        cid = paid[0]["id"]
        r = requests.post(f"{BASE}/api/admin/payout/calc/{cid}/cancel",
                          headers=_h(admin_token), json={}, timeout=15)
        assert r.status_code == 409
        assert "paid" in r.json()["detail"].lower()

    def test_calcs_counts_includes_cancelled(self, admin_token):
        r = requests.get(f"{BASE}/api/admin/payout/{QUARTER}/calcs",
                         headers=_h(admin_token), timeout=15)
        assert r.status_code == 200
        counts = r.json()["counts"]
        assert "cancelled" in counts, f"counts missing 'cancelled' bucket: {counts}"
        # Should include all 5 keys
        for k in ("draft", "approved", "paid", "on_hold", "cancelled"):
            assert k in counts


# ─────────────── RBAC ───────────────
class TestCancelRBAC:
    def test_cancel_employee_forbidden_403(self, emp_token, admin_token):
        g = requests.get(f"{BASE}/api/admin/payout/{QUARTER}/calcs",
                         headers=_h(admin_token), timeout=15)
        items = g.json()["items"]
        assert items
        cid = items[0]["id"]
        r = requests.post(f"{BASE}/api/admin/payout/calc/{cid}/cancel",
                          headers=_h(emp_token), json={}, timeout=15)
        assert r.status_code == 403
