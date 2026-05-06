"""
Backend regression tests for Customer Management Portal.
Covers: auth, dashboard, customers, products, licenses, reports, users, notifications, activity-logs.
"""
import os
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else "https://license-hub-56.preview.emergentagent.com"
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@cmportal.com", "password": "Admin@123"}
MANAGER = {"email": "manager@cmportal.com", "password": "Manager@123"}
VIEWER = {"email": "viewer@cmportal.com", "password": "Viewer@123"}


def _login(creds):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=creds, timeout=20)
    assert r.status_code == 200, f"login failed for {creds['email']}: {r.status_code} {r.text}"
    return s, r


@pytest.fixture(scope="session")
def admin_session():
    s, _ = _login(ADMIN)
    return s


@pytest.fixture(scope="session")
def manager_session():
    s, _ = _login(MANAGER)
    return s


@pytest.fixture(scope="session")
def viewer_session():
    s, _ = _login(VIEWER)
    return s


# ---------------- Auth ----------------
class TestAuth:
    def test_login_admin_sets_cookies(self):
        s, r = _login(ADMIN)
        data = r.json()
        assert data["email"] == ADMIN["email"]
        assert data["role"] == "admin"
        # cookies set
        cookie_names = {c.name for c in s.cookies}
        assert "access_token" in cookie_names
        assert "refresh_token" in cookie_names

    def test_login_manager(self):
        _, r = _login(MANAGER)
        assert r.json()["role"] == "manager"

    def test_login_viewer(self):
        _, r = _login(VIEWER)
        assert r.json()["role"] == "viewer"

    def test_login_invalid_credentials(self):
        r = requests.post(f"{API}/auth/login", json={"email": "admin@cmportal.com", "password": "wrong"}, timeout=20)
        assert r.status_code in (400, 401)

    def test_me_with_cookie(self, admin_session):
        r = admin_session.get(f"{API}/auth/me", timeout=20)
        assert r.status_code == 200
        assert r.json()["email"] == ADMIN["email"]

    def test_me_without_auth(self):
        r = requests.get(f"{API}/auth/me", timeout=20)
        assert r.status_code == 401

    def test_logout_clears_cookies(self):
        s, _ = _login(ADMIN)
        r = s.post(f"{API}/auth/logout", timeout=20)
        assert r.status_code in (200, 204)
        # subsequent /me should fail
        r2 = s.get(f"{API}/auth/me", timeout=20)
        assert r2.status_code == 401


# ---------------- Dashboard ----------------
class TestDashboard:
    def test_dashboard_stats(self, admin_session):
        r = admin_session.get(f"{API}/dashboard/stats", timeout=20)
        assert r.status_code == 200
        d = r.json()
        for key in ["totals", "monthly_revenue", "monthly_renewals", "customer_growth",
                    "vendor_stats", "product_stats", "critical_expiring", "top_customers"]:
            assert key in d, f"missing {key}"
        assert isinstance(d["monthly_revenue"], list)
        assert isinstance(d["totals"], dict)

    def test_dashboard_unauth(self):
        r = requests.get(f"{API}/dashboard/stats", timeout=20)
        assert r.status_code == 401


# ---------------- Customers ----------------
class TestCustomers:
    def test_list_customers(self, admin_session):
        r = admin_session.get(f"{API}/customers", timeout=20)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_search_customers(self, admin_session):
        r = admin_session.get(f"{API}/customers", params={"search": "a"}, timeout=20)
        assert r.status_code == 200

    def test_status_filter(self, admin_session):
        r = admin_session.get(f"{API}/customers", params={"status": "Active"}, timeout=20)
        assert r.status_code == 200

    def test_admin_create_then_get_then_delete(self, admin_session):
        payload = {"company_name": "TEST_Co_A", "customer_name": "TEST_Customer_A",
                    "email": "test_cust_a@example.com", "contact_number": "1234567890",
                    "status": "Active"}
        r = admin_session.post(f"{API}/customers", json=payload, timeout=20)
        assert r.status_code in (200, 201), r.text
        cid = r.json()["id"]
        rg = admin_session.get(f"{API}/customers/{cid}", timeout=20)
        assert rg.status_code == 200
        assert rg.json()["customer_name"] == "TEST_Customer_A"
        # PUT requires full payload
        upd_payload = {**payload, "customer_name": "TEST_Customer_A_upd"}
        ru = admin_session.put(f"{API}/customers/{cid}", json=upd_payload, timeout=20)
        assert ru.status_code == 200, ru.text
        rg2 = admin_session.get(f"{API}/customers/{cid}", timeout=20)
        assert rg2.json()["customer_name"] == "TEST_Customer_A_upd"
        rd = admin_session.delete(f"{API}/customers/{cid}", timeout=20)
        assert rd.status_code in (200, 204)
        rg3 = admin_session.get(f"{API}/customers/{cid}", timeout=20)
        assert rg3.status_code == 404

    def test_manager_can_create_but_not_delete(self, manager_session):
        payload = {"company_name": "TEST_Co_M", "customer_name": "TEST_Customer_M",
                    "email": "test_cust_m@example.com", "contact_number": "1112223333",
                    "status": "Active"}
        r = manager_session.post(f"{API}/customers", json=payload, timeout=20)
        assert r.status_code in (200, 201), r.text
        cid = r.json()["id"]
        rd = manager_session.delete(f"{API}/customers/{cid}", timeout=20)
        assert rd.status_code == 403
        s_admin, _ = _login(ADMIN)
        s_admin.delete(f"{API}/customers/{cid}", timeout=20)

    def test_viewer_cannot_create(self, viewer_session):
        r = viewer_session.post(f"{API}/customers",
                                 json={"company_name": "TEST_X", "customer_name": "TEST_X", "status": "Active"},
                                 timeout=20)
        assert r.status_code == 403


# ---------------- Products ----------------
class TestProducts:
    def test_list_products(self, admin_session):
        r = admin_session.get(f"{API}/products", timeout=20)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_admin_crud_product(self, admin_session):
        payload = {"product_name": "TEST_Prod", "vendor": "TEST_Vendor",
                    "product_category": "Software", "description": "Test product"}
        r = admin_session.post(f"{API}/products", json=payload, timeout=20)
        assert r.status_code in (200, 201), r.text
        pid = r.json()["id"]
        # No GET /products/{id} endpoint exposed; verify via list
        lst = admin_session.get(f"{API}/products", timeout=20).json()
        assert any(p["id"] == pid for p in lst)
        upd_payload = {**payload, "vendor": "TEST_Vendor_upd"}
        ru = admin_session.put(f"{API}/products/{pid}", json=upd_payload, timeout=20)
        assert ru.status_code == 200, ru.text
        lst2 = admin_session.get(f"{API}/products", timeout=20).json()
        updated = next((p for p in lst2 if p["id"] == pid), None)
        assert updated and updated["vendor"] == "TEST_Vendor_upd"
        rd = admin_session.delete(f"{API}/products/{pid}", timeout=20)
        assert rd.status_code in (200, 204)

    def test_viewer_cannot_create_product(self, viewer_session):
        r = viewer_session.post(f"{API}/products",
                                 json={"product_name": "TEST_X", "vendor": "v"},
                                 timeout=20)
        assert r.status_code == 403


# ---------------- Licenses ----------------
class TestLicenses:
    def test_list_licenses_enriched(self, admin_session):
        r = admin_session.get(f"{API}/licenses", timeout=20)
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list)
        if items:
            lic = items[0]
            for f in ("status", "customer_name", "product_name", "vendor"):
                assert f in lic, f"license missing {f}: {lic}"
            assert lic["status"] in ("Active", "Expiring Soon", "Expired")

    def test_admin_create_license(self, admin_session):
        # need an existing customer + product
        cust = admin_session.get(f"{API}/customers", timeout=20).json()
        prod = admin_session.get(f"{API}/products", timeout=20).json()
        if not cust or not prod:
            pytest.skip("no seed data")
        payload = {
            "customer_id": cust[0]["id"],
            "product_id": prod[0]["id"],
            "license_key": "TEST-LIC-AAAA-BBBB",
            "purchase_date": "2026-01-01",
            "activation_date": "2026-01-01",
            "expiry_date": "2027-01-01",
            "license_count": 5,
            "cost": 100.0,
        }
        r = admin_session.post(f"{API}/licenses", json=payload, timeout=20)
        assert r.status_code in (200, 201), r.text
        lic = r.json()
        assert lic.get("status") in ("Active", "Expiring Soon", "Expired")
        # cleanup
        admin_session.delete(f"{API}/licenses/{lic['id']}", timeout=20)


# ---------------- Reports ----------------
class TestReports:
    @pytest.mark.parametrize("rtype", [
        "monthly-expiry", "customer-license", "vendor", "revenue", "renewal", "expired"
    ])
    def test_report(self, admin_session, rtype):
        r = admin_session.get(f"{API}/reports/{rtype}", timeout=30)
        assert r.status_code == 200, f"{rtype}: {r.text[:200]}"
        # Should be JSON list/dict
        try:
            r.json()
        except Exception:
            pytest.fail(f"{rtype} not JSON")


# ---------------- Users (admin-only) ----------------
class TestUsers:
    def test_admin_list_users(self, admin_session):
        r = admin_session.get(f"{API}/users", timeout=20)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_manager_cannot_list_users(self, manager_session):
        r = manager_session.get(f"{API}/users", timeout=20)
        assert r.status_code == 403

    def test_viewer_cannot_list_users(self, viewer_session):
        r = viewer_session.get(f"{API}/users", timeout=20)
        assert r.status_code == 403

    def test_admin_user_crud(self, admin_session):
        payload = {"name": "TEST_User", "email": "test_user_x@example.com",
                    "password": "Test@1234", "role": "viewer"}
        r = admin_session.post(f"{API}/users", json=payload, timeout=20)
        assert r.status_code in (200, 201), r.text
        uid = r.json()["id"]
        ru = admin_session.put(f"{API}/users/{uid}", json={"name": "TEST_User_upd"}, timeout=20)
        assert ru.status_code == 200
        rd = admin_session.delete(f"{API}/users/{uid}", timeout=20)
        assert rd.status_code in (200, 204)


# ---------------- Notifications & Activity Logs ----------------
class TestNotifications:
    def test_get_notifications(self, admin_session):
        r = admin_session.get(f"{API}/notifications", timeout=20)
        assert r.status_code == 200
        assert isinstance(r.json(), list)


class TestActivityLogs:
    def test_admin_logs(self, admin_session):
        r = admin_session.get(f"{API}/activity-logs", timeout=20)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_manager_cannot_access_logs(self, manager_session):
        r = manager_session.get(f"{API}/activity-logs", timeout=20)
        assert r.status_code == 403
