"""
Sprint G backend tests — HSI Employee Engagement Platform
Covers:
  - Basic root / health
  - MFA login flow (OTP from backend dev-fallback log)
  - Uploads (local storage fallback), category validation, size limits, auth
  - Practices with attachments
  - PATCH /api/users/me
  - Admin analytics endpoints (xp-trends, top-contributors, practice-funnel,
    revenue, notification-engagement)
  - Admin payout endpoints (quarters, per-quarter breakdown, CSV, PDF, approve)
  - RBAC (employee should receive 403 on /api/admin/*)
  - Regression: /api/dashboard/stats, /api/xp/summary, /api/practices, /api/notifications
"""
import io
import os
import re
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    BASE_URL = "http://localhost:8001"  # fallback for in-pod run

ADMIN_EMAIL = "admin@hitachi-systems.com"
ADMIN_PW = "Admin@123"
EMPLOYEE_EMAIL = "employee@hitachi-systems.com"
EMPLOYEE_PW = "Employee@123"

BACKEND_ERR_LOG = "/var/log/supervisor/backend.err.log"
OTP_RE = re.compile(r"OTP for (\S+) \(purpose=(\w+)\): (\d{4,8})")


def _read_latest_otp(email: str, purpose: str = "login") -> str:
    """Grep backend err log for the latest dev-fallback OTP for (email, purpose)."""
    # Small sleep to ensure log flush
    time.sleep(0.3)
    try:
        with open(BACKEND_ERR_LOG, "r", errors="ignore") as f:
            data = f.read()
    except FileNotFoundError:
        pytest.skip("backend err log unavailable; cannot read dev-fallback OTP")
    matches = OTP_RE.findall(data)
    for e, p, code in reversed(matches):
        if e.lower() == email.lower() and p == purpose:
            return code
    pytest.fail(f"No dev-fallback OTP found in log for {email}/{purpose}")


def _login_with_mfa(email: str, password: str) -> dict:
    """Performs login + OTP verify; returns verify-otp response JSON."""
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    body = r.json()
    if not body.get("requires_otp"):
        # MFA disabled, token already present
        return body
    code = _read_latest_otp(email, "login")
    r2 = requests.post(f"{BASE_URL}/api/auth/verify-otp",
                       json={"email": email, "code": code, "purpose": "login"},
                       timeout=15)
    assert r2.status_code == 200, f"verify-otp failed: {r2.status_code} {r2.text}"
    out = r2.json()
    assert "access_token" in out
    return out


# ── Fixtures ─────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def admin_auth():
    data = _login_with_mfa(ADMIN_EMAIL, ADMIN_PW)
    return {"token": data["access_token"], "user": data["user"],
            "headers": {"Authorization": f"Bearer {data['access_token']}"}}


@pytest.fixture(scope="module")
def employee_auth():
    data = _login_with_mfa(EMPLOYEE_EMAIL, EMPLOYEE_PW)
    return {"token": data["access_token"], "user": data["user"],
            "headers": {"Authorization": f"Bearer {data['access_token']}"}}


# ── Basic endpoints ──────────────────────────────────────────────────────────
class TestRootAndHealth:
    def test_root(self):
        r = requests.get(f"{BASE_URL}/api/", timeout=10)
        assert r.status_code == 200
        body = r.json()
        assert body.get("sprint") == "G"
        assert body.get("storage_mode") == "local"
        assert body.get("minio_active") is False

    def test_health(self):
        r = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert r.status_code == 200
        body = r.json()
        assert body.get("status") == "healthy"
        checks = body.get("checks", {})
        assert checks.get("database", {}).get("status") == "ok"
        assert checks.get("storage", {}).get("status") == "ok"
        assert checks.get("storage", {}).get("mode") == "local"


# ── Auth / MFA ───────────────────────────────────────────────────────────────
class TestAuth:
    def test_admin_login_returns_requires_otp(self):
        r = requests.post(f"{BASE_URL}/api/auth/login",
                          json={"email": ADMIN_EMAIL, "password": ADMIN_PW})
        assert r.status_code == 200
        body = r.json()
        assert body.get("requires_otp") is True
        assert body.get("email") == ADMIN_EMAIL

    def test_mfa_verify_flow(self, admin_auth):
        assert admin_auth["user"]["email"] == ADMIN_EMAIL
        assert admin_auth["user"]["role"] in ("admin", "super_admin")

    def test_login_invalid(self):
        r = requests.post(f"{BASE_URL}/api/auth/login",
                          json={"email": ADMIN_EMAIL, "password": "wrong"})
        assert r.status_code == 401


# ── Uploads ──────────────────────────────────────────────────────────────────
class TestUploads:
    def test_upload_success_and_fetch_back(self, employee_auth):
        content = b"hello sprint G upload"
        files = {"file": ("test.txt", io.BytesIO(content), "text/plain")}
        data = {"category": "practice"}
        r = requests.post(f"{BASE_URL}/api/uploads", headers=employee_auth["headers"],
                          files=files, data=data, timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        for k in ("id", "key", "url", "filename", "size", "content_type"):
            assert k in body, f"missing key {k} in {body}"
        assert body["storage"] == "local"
        assert body["size"] == len(content)
        assert body["filename"] == "test.txt"
        # Now GET the URL and verify content round-trip
        url = body["url"]
        # url may be relative like /api/uploads-local/practice/<uuid>.txt
        if url.startswith("/"):
            full = f"{BASE_URL}{url}"
        else:
            full = url
        g = requests.get(full, timeout=10)
        assert g.status_code == 200, f"GET url failed: {g.status_code} body={g.text[:200]}"
        assert g.content == content

    def test_upload_rejects_empty_file(self, employee_auth):
        files = {"file": ("empty.txt", io.BytesIO(b""), "text/plain")}
        data = {"category": "practice"}
        r = requests.post(f"{BASE_URL}/api/uploads", headers=employee_auth["headers"],
                          files=files, data=data)
        assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text}"

    def test_upload_rejects_invalid_category(self, employee_auth):
        files = {"file": ("a.txt", io.BytesIO(b"abc"), "text/plain")}
        data = {"category": "not_a_category"}
        r = requests.post(f"{BASE_URL}/api/uploads", headers=employee_auth["headers"],
                          files=files, data=data)
        assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text}"

    def test_upload_rejects_oversized(self, employee_auth):
        # 10 MB + 1 byte > MAX_UPLOAD_BYTES (10MB)
        big = b"x" * (10 * 1024 * 1024 + 1)
        files = {"file": ("big.bin", io.BytesIO(big), "application/octet-stream")}
        data = {"category": "practice"}
        r = requests.post(f"{BASE_URL}/api/uploads", headers=employee_auth["headers"],
                          files=files, data=data)
        assert r.status_code == 413, f"expected 413, got {r.status_code}: {r.text[:300]}"

    def test_upload_requires_auth(self):
        files = {"file": ("a.txt", io.BytesIO(b"abc"), "text/plain")}
        data = {"category": "practice"}
        r = requests.post(f"{BASE_URL}/api/uploads", files=files, data=data)
        assert r.status_code == 401, f"expected 401, got {r.status_code}: {r.text}"


# ── Practices with attachments ───────────────────────────────────────────────
class TestPracticesAttachments:
    def test_create_practice_with_attachments(self, employee_auth):
        # First create an upload
        files = {"file": ("doc.txt", io.BytesIO(b"doc content"), "text/plain")}
        up = requests.post(f"{BASE_URL}/api/uploads",
                           headers=employee_auth["headers"],
                           files=files, data={"category": "practice"}).json()
        payload = {
            "title": "TEST_SprintG Practice",
            "summary": "Testing attachments round-trip.",
            "description": "Testing attachments round-trip.",
            "pillar": "innovator",
            "icon": "lightbulb",
            "attachments": [{
                "key": up["key"], "url": up["url"],
                "filename": up["filename"], "content_type": up["content_type"],
                "size": up["size"],
            }],
        }
        r = requests.post(f"{BASE_URL}/api/practices",
                          headers=employee_auth["headers"], json=payload, timeout=15)
        assert r.status_code in (200, 201), f"{r.status_code} {r.text}"
        body = r.json()
        assert body.get("title") == payload["title"]
        assert isinstance(body.get("attachments"), list)
        assert len(body["attachments"]) == 1
        assert body["attachments"][0]["key"] == up["key"]


# ── Users /me patch ──────────────────────────────────────────────────────────
class TestUsersMe:
    def test_patch_users_me(self, employee_auth):
        payload = {"avatar_url": "http://x/y.png",
                   "phone": "+91 00000",
                   "designation": "PM"}
        r = requests.patch(f"{BASE_URL}/api/users/me",
                           headers=employee_auth["headers"], json=payload, timeout=15)
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        body = r.json()
        assert body.get("avatar_url") == payload["avatar_url"]
        assert body.get("phone") == payload["phone"]
        assert body.get("designation") == payload["designation"]


# ── Admin analytics ──────────────────────────────────────────────────────────
class TestAdminAnalytics:
    def test_xp_trends(self, admin_auth):
        r = requests.get(f"{BASE_URL}/api/admin/analytics/xp-trends?period=weekly&buckets=12",
                         headers=admin_auth["headers"], timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("period") == "weekly"
        assert isinstance(body.get("series"), list)
        if body["series"]:
            s0 = body["series"][0]
            assert "bucket" in s0 and "xp" in s0 and "events" in s0

    def test_top_contributors(self, admin_auth):
        r = requests.get(f"{BASE_URL}/api/admin/analytics/top-contributors?limit=5",
                         headers=admin_auth["headers"], timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "quarter" in body
        assert isinstance(body.get("items"), list)
        assert len(body["items"]) <= 5

    def test_practice_funnel(self, admin_auth):
        r = requests.get(f"{BASE_URL}/api/admin/analytics/practice-funnel",
                         headers=admin_auth["headers"], timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "practices" in body and "replications" in body
        for k in ("draft", "pending", "approved", "rejected"):
            assert k in body["practices"]
        for k in ("pending", "approved", "rejected"):
            assert k in body["replications"]
            assert "count" in body["replications"][k]
            assert "with_po" in body["replications"][k]

    def test_revenue(self, admin_auth):
        r = requests.get(f"{BASE_URL}/api/admin/analytics/revenue",
                         headers=admin_auth["headers"], timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "overall" in body and "by_quarter" in body
        assert "total_deals" in body["overall"]
        assert "total_revenue" in body["overall"]
        assert isinstance(body["by_quarter"], list)

    def test_notification_engagement(self, admin_auth):
        r = requests.get(f"{BASE_URL}/api/admin/analytics/notification-engagement",
                         headers=admin_auth["headers"], timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("window_days") == 30
        totals = body.get("totals", {})
        for k in ("delivered", "read", "dismissed", "read_rate"):
            assert k in totals
        assert isinstance(body.get("by_category"), list)

    def test_employee_blocked_from_notification_engagement(self, employee_auth):
        r = requests.get(f"{BASE_URL}/api/admin/analytics/notification-engagement",
                         headers=employee_auth["headers"])
        assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text}"


# ── Admin payout ─────────────────────────────────────────────────────────────
class TestAdminPayout:
    def test_quarters(self, admin_auth):
        r = requests.get(f"{BASE_URL}/api/admin/payout/quarters",
                         headers=admin_auth["headers"], timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        # Endpoint returns a list per spec; accept list or dict with 'quarters'
        assert isinstance(body, (list, dict))

    def test_payout_detail(self, admin_auth):
        r = requests.get(f"{BASE_URL}/api/admin/payout/2026-Q2",
                         headers=admin_auth["headers"], timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        # Should contain per-user breakdown + total_inr + rates
        assert "total_inr" in body
        assert "rates" in body
        # per-user breakdown key may be 'items', 'users', 'breakdown', etc.
        has_items = any(k in body for k in ("items", "users", "breakdown", "rows"))
        assert has_items, f"no per-user breakdown key in {list(body.keys())}"

    def test_payout_csv_export(self, admin_auth):
        r = requests.get(f"{BASE_URL}/api/admin/payout/2026-Q2/export.csv",
                         headers=admin_auth["headers"], timeout=15)
        assert r.status_code == 200, r.text
        ct = r.headers.get("content-type", "")
        assert "text/csv" in ct, f"unexpected content-type: {ct}"
        body = r.text
        assert body.startswith("employee_id,name,email"), f"unexpected header: {body[:120]}"

    def test_payout_pdf_export(self, admin_auth):
        r = requests.get(f"{BASE_URL}/api/admin/payout/2026-Q2/export.pdf",
                         headers=admin_auth["headers"], timeout=20)
        assert r.status_code == 200, r.text[:200]
        ct = r.headers.get("content-type", "")
        assert "application/pdf" in ct, f"unexpected content-type: {ct}"
        assert r.content[:4] == b"%PDF", f"unexpected PDF magic: {r.content[:12]}"

    def test_payout_approve(self, admin_auth):
        r = requests.post(f"{BASE_URL}/api/admin/payout/2026-Q2/approve",
                          headers=admin_auth["headers"], timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("quarter") == "2026-Q2"
        assert "approved" in body
        # Verify the GET still works after approve
        g = requests.get(f"{BASE_URL}/api/admin/payout/2026-Q2",
                         headers=admin_auth["headers"], timeout=15)
        assert g.status_code == 200


# ── RBAC ─────────────────────────────────────────────────────────────────────
class TestRBAC:
    @pytest.mark.parametrize("path", [
        "/api/admin/analytics/xp-trends",
        "/api/admin/analytics/top-contributors",
        "/api/admin/analytics/practice-funnel",
        "/api/admin/analytics/revenue",
        "/api/admin/payout/quarters",
        "/api/admin/payout/2026-Q2",
    ])
    def test_employee_blocked_from_admin_paths(self, employee_auth, path):
        r = requests.get(f"{BASE_URL}{path}", headers=employee_auth["headers"])
        assert r.status_code == 403, f"{path}: expected 403, got {r.status_code}"


# ── Regression ───────────────────────────────────────────────────────────────
class TestRegression:
    def test_dashboard_stats(self, employee_auth):
        r = requests.get(f"{BASE_URL}/api/dashboard/stats",
                         headers=employee_auth["headers"])
        assert r.status_code == 200, r.text

    def test_xp_summary(self, employee_auth):
        r = requests.get(f"{BASE_URL}/api/xp/summary",
                         headers=employee_auth["headers"])
        assert r.status_code == 200, r.text

    def test_practices_list(self, employee_auth):
        r = requests.get(f"{BASE_URL}/api/practices",
                         headers=employee_auth["headers"])
        assert r.status_code == 200, r.text

    def test_notifications_list(self, employee_auth):
        r = requests.get(f"{BASE_URL}/api/notifications",
                         headers=employee_auth["headers"])
        assert r.status_code == 200, r.text
