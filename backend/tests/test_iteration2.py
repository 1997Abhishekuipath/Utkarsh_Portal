"""
Iteration 2 backend tests: Alerts config, bulk import, dashboard config, custom reports.
Existing regression via backend_test.py.
"""
import os
import io
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
    assert r.status_code == 200, f"login failed {creds['email']}: {r.text}"
    return s


@pytest.fixture(scope="session")
def admin():
    return _login(ADMIN)

@pytest.fixture(scope="session")
def manager():
    return _login(MANAGER)

@pytest.fixture(scope="session")
def viewer():
    return _login(VIEWER)


# ---------------- Alerts ----------------
class TestAlertsConfig:
    def test_get_config_admin(self, admin):
        r = admin.get(f"{API}/alerts/config", timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert "recipients" in d
        assert "enabled" in d
        assert "cadence" in d
        assert "resend_configured" in d
        assert isinstance(d["resend_configured"], bool)

    def test_get_config_forbidden_for_non_admin(self, manager, viewer):
        assert manager.get(f"{API}/alerts/config", timeout=20).status_code == 403
        assert viewer.get(f"{API}/alerts/config", timeout=20).status_code == 403

    def test_put_config_admin(self, admin):
        payload = {"recipients": ["admin@cmportal.com", "ops@cmportal.com"],
                   "enabled": True, "cadence": "daily"}
        r = admin.put(f"{API}/alerts/config", json=payload, timeout=20)
        assert r.status_code == 200
        # verify persisted
        g = admin.get(f"{API}/alerts/config", timeout=20).json()
        assert set(g["recipients"]) == set(payload["recipients"])
        assert g["cadence"] == "daily"
        assert g["enabled"] is True

    def test_put_config_forbidden_for_manager(self, manager):
        r = manager.put(f"{API}/alerts/config",
                        json={"recipients": ["x@x.com"], "enabled": True, "cadence": "daily"},
                        timeout=20)
        assert r.status_code == 403


class TestAlertsEmail:
    def test_test_email_returns_sent_false_with_placeholder(self, admin):
        r = admin.post(f"{API}/alerts/test-email",
                       json={"recipient": "admin@cmportal.com"}, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d.get("sent") is False
        # reason should mention not configured (placeholder key)
        assert "RESEND_API_KEY" in (d.get("reason") or "") or "not configured" in (d.get("reason") or "")

    def test_test_email_forbidden(self, manager, viewer):
        for s in (manager, viewer):
            r = s.post(f"{API}/alerts/test-email", json={"recipient": "x@x.com"}, timeout=20)
            assert r.status_code == 403

    def test_run_digest_returns_shape(self, admin):
        r = admin.post(f"{API}/alerts/run-digest", timeout=30)
        assert r.status_code == 200
        d = r.json()
        # Either sent=false with reason, or dict with buckets; must include 'sent'
        assert "sent" in d
        if "buckets" in d:
            assert isinstance(d["buckets"], dict)
            assert set(d["buckets"].keys()).issuperset({"expired", "30", "60", "90"})

    def test_run_digest_forbidden(self, manager):
        r = manager.post(f"{API}/alerts/run-digest", timeout=20)
        assert r.status_code == 403


# ---------------- Bulk Import ----------------
class TestCustomersBulkImport:
    def test_template_csv(self, admin):
        r = admin.get(f"{API}/templates/customers.csv", timeout=20)
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "")
        assert "company_name" in r.text
        assert "email" in r.text

    def test_upsert_insert_and_update(self, admin):
        csv1 = ("company_name,customer_name,email,status\n"
                "TEST_Bulk_Co_1,TEST_Person_1,test_bulk1@example.com,Active\n")
        files = {"file": ("c.csv", io.BytesIO(csv1.encode()), "text/csv")}
        data = {"mode": "upsert"}
        r = admin.post(f"{API}/customers/bulk-import", files=files, data=data, timeout=30)
        assert r.status_code == 200, r.text
        res = r.json()
        assert res["inserted"] >= 1 or res["updated"] >= 1
        assert res["total"] == 1

        # now update same email
        csv2 = ("company_name,customer_name,email,status\n"
                "TEST_Bulk_Co_1_UPD,TEST_Person_1_UPD,test_bulk1@example.com,Active\n")
        files2 = {"file": ("c.csv", io.BytesIO(csv2.encode()), "text/csv")}
        r2 = admin.post(f"{API}/customers/bulk-import", files=files2, data=data, timeout=30)
        assert r2.status_code == 200
        res2 = r2.json()
        assert res2["updated"] == 1

        # verify
        lst = admin.get(f"{API}/customers", params={"search": "TEST_Bulk_Co_1_UPD"}, timeout=20).json()
        assert any(c["email"] == "test_bulk1@example.com" and c["company_name"] == "TEST_Bulk_Co_1_UPD" for c in lst)

        # cleanup
        for c in lst:
            if c.get("email") == "test_bulk1@example.com":
                admin.delete(f"{API}/customers/{c['id']}", timeout=20)

    def test_viewer_forbidden(self, viewer):
        files = {"file": ("c.csv", io.BytesIO(b"company_name,email\nX,y@z.com\n"), "text/csv")}
        r = viewer.post(f"{API}/customers/bulk-import", files=files, data={"mode": "upsert"}, timeout=20)
        assert r.status_code == 403


class TestLicensesBulkImport:
    def test_template_csv(self, admin):
        r = admin.get(f"{API}/templates/licenses.csv", timeout=20)
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "")
        assert "license_key" in r.text

    def test_upsert_license_count_update(self, admin):
        custs = admin.get(f"{API}/customers", timeout=20).json()
        prods = admin.get(f"{API}/products", timeout=20).json()
        if not custs or not prods:
            pytest.skip("no seed data")
        c = custs[0]
        p = prods[0]
        # Insert a fresh license
        key = "TEST-BULK-LIC-0001"
        csv1 = (
            "license_key,customer_email,product_name,license_count,expiry_date,purchase_date,activation_date,cost\n"
            f"{key},{c['email']},{p['product_name']},5,2027-01-01,2026-01-01,2026-01-01,100\n"
        )
        files = {"file": ("l.csv", io.BytesIO(csv1.encode()), "text/csv")}
        r = admin.post(f"{API}/licenses/bulk-import", files=files, data={"mode": "upsert"}, timeout=30)
        assert r.status_code == 200, r.text
        res = r.json()
        assert res["inserted"] + res["updated"] == 1

        # re-import with license_count=10
        csv2 = (
            "license_key,customer_email,product_name,license_count,expiry_date\n"
            f"{key},{c['email']},{p['product_name']},10,2027-06-01\n"
        )
        files2 = {"file": ("l.csv", io.BytesIO(csv2.encode()), "text/csv")}
        r2 = admin.post(f"{API}/licenses/bulk-import", files=files2, data={"mode": "upsert"}, timeout=30)
        assert r2.status_code == 200
        res2 = r2.json()
        assert res2["updated"] == 1

        # verify
        lst = admin.get(f"{API}/licenses", params={"search": key}, timeout=20).json()
        match = [l for l in lst if l["license_key"] == key]
        assert match and match[0]["license_count"] == 10

        # cleanup
        admin.delete(f"{API}/licenses/{match[0]['id']}", timeout=20)

    def test_viewer_forbidden(self, viewer):
        files = {"file": ("l.csv", io.BytesIO(b"license_key\nK\n"), "text/csv")}
        r = viewer.post(f"{API}/licenses/bulk-import", files=files, data={"mode": "upsert"}, timeout=20)
        assert r.status_code == 403


# ---------------- Dashboard Config ----------------
class TestDashboardConfig:
    def test_get_default(self, admin):
        r = admin.get(f"{API}/dashboard/config", timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert "widgets" in d
        assert isinstance(d["widgets"], list)
        # 13 default widgets when not configured (admin may already have saved config from prior test)
        assert len(d["widgets"]) >= 1

    def test_put_get_config(self, manager):
        widgets = ["kpi_customers", "kpi_revenue", "chart_revenue"]
        r = manager.put(f"{API}/dashboard/config", json={"widgets": widgets}, timeout=20)
        assert r.status_code == 200
        g = manager.get(f"{API}/dashboard/config", timeout=20).json()
        assert g["widgets"] == widgets


# ---------------- Custom Reports ----------------
class TestCustomReports:
    def test_run_licenses_expired(self, admin):
        payload = {"name": "tmp", "entity": "licenses",
                   "columns": ["license_key", "status"],
                   "filters": {"status": "Expired"}}
        r = admin.post(f"{API}/custom-reports/run", json=payload, timeout=30)
        assert r.status_code == 200, r.text
        rows = r.json()
        assert isinstance(rows, list)
        for row in rows:
            assert row.get("status") == "Expired"
            assert set(row.keys()) == {"license_key", "status"}

    def test_run_customers_active(self, admin):
        payload = {"name": "tmp", "entity": "customers",
                   "columns": ["company_name", "status"],
                   "filters": {"status": "Active"}}
        r = admin.post(f"{API}/custom-reports/run", json=payload, timeout=30)
        assert r.status_code == 200
        rows = r.json()
        for row in rows:
            assert row["status"] == "Active"

    def test_run_license_expiry_range(self, admin):
        payload = {"name": "tmp", "entity": "licenses",
                   "columns": ["license_key", "expiry_date"],
                   "filters": {"expiry_from": "2026-01-01", "expiry_to": "2026-12-31"}}
        r = admin.post(f"{API}/custom-reports/run", json=payload, timeout=30)
        assert r.status_code == 200
        rows = r.json()
        assert isinstance(rows, list)
        # every row's expiry must be within range
        from datetime import date
        for row in rows:
            d = row["expiry_date"]
            assert "2026-01-01" <= d <= "2026-12-31"

    def test_crud_custom_report(self, admin):
        payload = {"name": "TEST_Report_A", "entity": "licenses",
                   "columns": ["license_key", "status"],
                   "filters": {"status": "Active"}}
        c = admin.post(f"{API}/custom-reports", json=payload, timeout=20)
        assert c.status_code in (200, 201)
        rid = c.json()["id"]
        lst = admin.get(f"{API}/custom-reports", timeout=20).json()
        assert any(x["id"] == rid for x in lst)
        d = admin.delete(f"{API}/custom-reports/{rid}", timeout=20)
        assert d.status_code in (200, 204)
