"""HSI Enterprise Portal — Backend API smoke tests (auth + dashboard + admin).

Updated for Sprint B+ (MFA enabled, @hitachi-systems.com domain enforced).
Run: pytest /app/backend/tests/test_hsi_portal.py -v
"""
import os
import uuid
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE, "REACT_APP_BACKEND_URL must be set"

DEMO_OTP = "000000"
ADMIN   = ("admin@hitachi-systems.com",   "Admin@123")
MANAGER = ("manager@hitachi-systems.com", "Manager@123")
EMP     = ("employee@hitachi-systems.com", "Employee@123")


def _login(email: str, password: str) -> str:
    """Two-step MFA login → access_token."""
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login {email} → {r.status_code} {r.text}"
    j = r.json()
    if not j.get("requires_otp"):
        return j["access_token"]
    v = requests.post(f"{BASE}/api/auth/verify-otp",
                      json={"email": email, "code": DEMO_OTP, "purpose": "login"},
                      timeout=15)
    assert v.status_code == 200, f"verify-otp {email} → {v.status_code} {v.text}"
    return v.json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


# ─────────── auth ───────────
class TestAuth:
    def test_login_admin(self):
        token = _login(*ADMIN)
        assert token
        r = requests.get(f"{BASE}/api/auth/me", headers=_h(token), timeout=10)
        assert r.status_code == 200
        u = r.json()
        assert u["role"] in ("admin", "super_admin")
        assert u["email"] == ADMIN[0]

    def test_login_manager(self):
        assert _login(*MANAGER)

    def test_login_invalid_password(self):
        r = requests.post(f"{BASE}/api/auth/login",
                          json={"email": ADMIN[0], "password": "wrongpass"}, timeout=10)
        assert r.status_code in (401, 423)   # 401 normally; 423 if locked from prior runs

    def test_login_invalid_domain(self):
        r = requests.post(f"{BASE}/api/auth/login",
                          json={"email": "nope@gmail.com", "password": "x"}, timeout=10)
        assert r.status_code in (400, 401, 403)

    def test_register_employee_pending(self):
        # Self-service register lands in pending-approval — no token issued.
        unique = f"test_{uuid.uuid4().hex[:8]}@hitachi-systems.com"
        r = requests.post(f"{BASE}/api/auth/register",
                          json={"name": "Test User", "email": unique,
                                "password": "Test@123", "role": "employee"},
                          timeout=10)
        # Either 200 with a pending=True flag or 201 — both acceptable shapes.
        assert r.status_code in (200, 201), r.text

    def test_me_unauthenticated(self):
        r = requests.get(f"{BASE}/api/auth/me", timeout=10)
        assert r.status_code == 401


# ─────────── dashboard ───────────
class TestDashboard:
    @pytest.fixture(scope="class")
    def token(self):
        return _login(*EMP)

    def test_stats_shape(self, token):
        r = requests.get(f"{BASE}/api/dashboard/stats", headers=_h(token), timeout=10)
        assert r.status_code == 200
        d = r.json()
        for k in ("best_practices", "efforts", "xp_incentive", "tech_days", "pending_actions"):
            assert k in d, f"missing key {k}"

    def test_activities_list(self, token):
        r = requests.get(f"{BASE}/api/dashboard/activities", headers=_h(token), timeout=10)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_leaderboard(self, token):
        r = requests.get(f"{BASE}/api/dashboard/leaderboard", headers=_h(token), timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert isinstance(d, list) and len(d) > 0
        assert {"rank", "xp", "name"}.issubset(d[0].keys())

    def test_announcements(self, token):
        r = requests.get(f"{BASE}/api/dashboard/announcements", headers=_h(token), timeout=10)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_pending_actions(self, token):
        r = requests.get(f"{BASE}/api/dashboard/pending-actions", headers=_h(token), timeout=10)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_upcoming_live_no_mock_strings(self, token):
        r = requests.get(f"{BASE}/api/dashboard/upcoming", headers=_h(token), timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert isinstance(d, list)
        # Sprint D removed hard-coded mocks — these phrases must NOT appear.
        flat = " ".join(str(i) for i in d)
        assert "Bajaj Finance" not in flat, "stale mock data still in /dashboard/upcoming"
        assert "All For SPTS" not in flat, "stale mock data still in /dashboard/upcoming"

    def test_score(self, token):
        r = requests.get(f"{BASE}/api/dashboard/score", headers=_h(token), timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert {"percentage", "total_xp", "breakdown"}.issubset(d.keys())


# ─────────── admin ───────────
class TestAdmin:
    @pytest.fixture(scope="class")
    def admin_token(self):
        return _login(*ADMIN)

    @pytest.fixture(scope="class")
    def emp_token(self):
        return _login(*EMP)

    def test_admin_users_list(self, admin_token):
        r = requests.get(f"{BASE}/api/admin/users", headers=_h(admin_token), timeout=10)
        assert r.status_code == 200
        d = r.json()
        # Endpoint may return list or {items: [...]}; tolerate both.
        items = d if isinstance(d, list) else d.get("items", [])
        assert len(items) >= 4   # 4 seed roles minimum

    def test_employee_cannot_list_users(self, emp_token):
        r = requests.get(f"{BASE}/api/admin/users", headers=_h(emp_token), timeout=10)
        assert r.status_code == 403
