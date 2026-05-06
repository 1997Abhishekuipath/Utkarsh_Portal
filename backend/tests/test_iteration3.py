"""
Iteration 3 backend tests:
- File attachments (upload/list/download/delete) for customers and licenses
- Renewal history versioning on license updates
- Role gating
"""
import io
import os
import uuid
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
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def admin_s():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def manager_s():
    return _login(MANAGER)


@pytest.fixture(scope="module")
def viewer_s():
    return _login(VIEWER)


@pytest.fixture(scope="module")
def seed_customer(admin_s):
    payload = {
        "company_name": "TEST_iter3_company",
        "customer_name": "TEST_iter3_contact",
        "email": f"test_iter3_{uuid.uuid4().hex[:6]}@example.com",
        "contact_number": "1234567890",
        "status": "Active",
    }
    r = admin_s.post(f"{API}/customers", json=payload, timeout=20)
    assert r.status_code == 200, r.text
    cid = r.json()["id"]
    yield cid
    admin_s.delete(f"{API}/customers/{cid}", timeout=20)


@pytest.fixture(scope="module")
def seed_product(admin_s):
    payload = {"product_name": f"TEST_iter3_prod_{uuid.uuid4().hex[:6]}", "vendor": "TestVendor", "product_category": "SaaS"}
    r = admin_s.post(f"{API}/products", json=payload, timeout=20)
    assert r.status_code == 200, r.text
    pid = r.json()["id"]
    yield pid
    admin_s.delete(f"{API}/products/{pid}", timeout=20)


@pytest.fixture(scope="module")
def seed_license(admin_s, seed_customer, seed_product):
    payload = {
        "license_key": f"TEST-ITER3-{uuid.uuid4().hex[:6]}",
        "customer_id": seed_customer,
        "product_id": seed_product,
        "license_count": 5,
        "cost": 100.0,
        "currency": "USD",
        "purchase_date": "2025-01-01",
        "activation_date": "2025-01-01",
        "expiry_date": "2026-01-01",
    }
    r = admin_s.post(f"{API}/licenses", json=payload, timeout=20)
    assert r.status_code == 200, r.text
    lid = r.json()["id"]
    yield lid
    admin_s.delete(f"{API}/licenses/{lid}", timeout=20)


# Tiny PDF (valid header) bytes
TINY_PDF = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj<<>>endobj\nxref\n0 1\n0000000000 65535 f \ntrailer<<>>\n%%EOF\n"


# ============== Upload tests ==============
class TestAttachmentsUpload:
    def test_upload_pdf_to_customer(self, admin_s, seed_customer):
        files = {"file": ("test_doc.pdf", TINY_PDF, "application/pdf")}
        data = {"entity_type": "customer", "entity_id": seed_customer, "description": "iter3 test"}
        r = admin_s.post(f"{API}/attachments/upload", files=files, data=data, timeout=60)
        if r.status_code == 503:
            pytest.skip(f"Storage unavailable: {r.text}")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["filename"] == "test_doc.pdf"
        assert body["entity_type"] == "customer"
        assert body["entity_id"] == seed_customer
        assert body["content_type"] == "application/pdf"
        assert body["size"] > 0
        assert "id" in body and "storage_path" in body
        assert body["uploaded_by"] == ADMIN["email"]
        assert body.get("is_deleted") is False
        # save for next tests
        pytest.shared_customer_attachment_id = body["id"]

    def test_upload_png_to_license(self, admin_s, seed_license):
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
        files = {"file": ("img.png", png, "image/png")}
        data = {"entity_type": "license", "entity_id": seed_license}
        r = admin_s.post(f"{API}/attachments/upload", files=files, data=data, timeout=60)
        if r.status_code == 503:
            pytest.skip("Storage unavailable")
        assert r.status_code == 200, r.text
        pytest.shared_license_attachment_id = r.json()["id"]

    def test_upload_rejects_exe(self, admin_s, seed_customer):
        files = {"file": ("evil.exe", b"MZ\x00", "application/octet-stream")}
        data = {"entity_type": "customer", "entity_id": seed_customer}
        r = admin_s.post(f"{API}/attachments/upload", files=files, data=data, timeout=20)
        assert r.status_code == 400, r.text
        assert "not allowed" in r.json()["detail"].lower()

    def test_upload_rejects_oversized(self, admin_s, seed_customer):
        big = b"\x00" * (10 * 1024 * 1024 + 100)  # >10 MB
        files = {"file": ("big.pdf", big, "application/pdf")}
        data = {"entity_type": "customer", "entity_id": seed_customer}
        r = admin_s.post(f"{API}/attachments/upload", files=files, data=data, timeout=120)
        assert r.status_code == 413, r.text

    def test_upload_rejects_bad_entity(self, admin_s):
        files = {"file": ("f.pdf", TINY_PDF, "application/pdf")}
        data = {"entity_type": "customer", "entity_id": "non-existent-id-zzz"}
        r = admin_s.post(f"{API}/attachments/upload", files=files, data=data, timeout=30)
        assert r.status_code == 404, r.text

    def test_upload_rejects_invalid_entity_type(self, admin_s, seed_customer):
        files = {"file": ("f.pdf", TINY_PDF, "application/pdf")}
        data = {"entity_type": "vendor", "entity_id": seed_customer}
        r = admin_s.post(f"{API}/attachments/upload", files=files, data=data, timeout=20)
        assert r.status_code == 400, r.text

    def test_upload_viewer_forbidden(self, viewer_s, seed_customer):
        files = {"file": ("f.pdf", TINY_PDF, "application/pdf")}
        data = {"entity_type": "customer", "entity_id": seed_customer}
        r = viewer_s.post(f"{API}/attachments/upload", files=files, data=data, timeout=20)
        assert r.status_code == 403, r.text

    def test_upload_manager_allowed(self, manager_s, seed_customer):
        files = {"file": ("mgr.pdf", TINY_PDF, "application/pdf")}
        data = {"entity_type": "customer", "entity_id": seed_customer}
        r = manager_s.post(f"{API}/attachments/upload", files=files, data=data, timeout=60)
        if r.status_code == 503:
            pytest.skip("Storage unavailable")
        assert r.status_code == 200, r.text


# ============== List/Download/Delete ==============
class TestAttachmentsLifecycle:
    def test_list_customer_attachments(self, admin_s, seed_customer):
        r = admin_s.get(f"{API}/attachments/customer/{seed_customer}", timeout=20)
        assert r.status_code == 200, r.text
        rows = r.json()
        assert isinstance(rows, list)
        if hasattr(pytest, "shared_customer_attachment_id"):
            ids = [x["id"] for x in rows]
            assert pytest.shared_customer_attachment_id in ids

    def test_list_license_attachments(self, admin_s, seed_license):
        r = admin_s.get(f"{API}/attachments/license/{seed_license}", timeout=20)
        assert r.status_code == 200, r.text
        rows = r.json()
        assert isinstance(rows, list)
        if hasattr(pytest, "shared_license_attachment_id"):
            ids = [x["id"] for x in rows]
            assert pytest.shared_license_attachment_id in ids

    def test_download_returns_binary(self, admin_s):
        if not hasattr(pytest, "shared_customer_attachment_id"):
            pytest.skip("no upload in previous test")
        fid = pytest.shared_customer_attachment_id
        r = admin_s.get(f"{API}/attachments/{fid}/download", timeout=60)
        if r.status_code == 503:
            pytest.skip("Storage unavailable")
        assert r.status_code == 200, f"{r.status_code} {r.headers} {r.text[:200]}"
        # content should be binary; check Content-Disposition
        cd = r.headers.get("Content-Disposition", "")
        assert "filename=" in cd
        assert r.headers.get("Content-Type", "").startswith("application/pdf") or len(r.content) > 0

    def test_delete_soft_deletes(self, admin_s, seed_customer):
        if not hasattr(pytest, "shared_customer_attachment_id"):
            pytest.skip("no upload in previous test")
        fid = pytest.shared_customer_attachment_id
        r = admin_s.delete(f"{API}/attachments/{fid}", timeout=20)
        assert r.status_code == 200, r.text
        # subsequent list should exclude
        r2 = admin_s.get(f"{API}/attachments/customer/{seed_customer}", timeout=20)
        ids = [x["id"] for x in r2.json()]
        assert fid not in ids
        # subsequent download 404
        r3 = admin_s.get(f"{API}/attachments/{fid}/download", timeout=20)
        assert r3.status_code == 404, r3.text


# ============== License history ==============
class TestRenewalHistory:
    def test_update_creates_history(self, admin_s, seed_license, seed_customer, seed_product):
        # Update cost
        payload = {
            "license_key": f"TEST-ITER3-UPD-{uuid.uuid4().hex[:6]}",
            "customer_id": seed_customer,
            "product_id": seed_product,
            "license_count": 5,
            "cost": 250.0,  # changed from 100
            "currency": "USD",
            "purchase_date": "2025-01-01",
            "activation_date": "2025-01-01",
            "expiry_date": "2026-06-01",  # changed
        }
        r = admin_s.put(f"{API}/licenses/{seed_license}", json=payload, timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        assert body["changes"] >= 2

        # Verify history endpoint
        h = admin_s.get(f"{API}/licenses/{seed_license}/history", timeout=20)
        assert h.status_code == 200, h.text
        history = h.json()
        assert len(history) >= 1
        latest = history[0]
        assert latest["license_id"] == seed_license
        assert latest["changed_by"] == ADMIN["email"]
        assert "changes" in latest
        assert "cost" in latest["changes"]
        assert latest["changes"]["cost"]["from"] == 100.0
        assert latest["changes"]["cost"]["to"] == 250.0
        assert "snapshot_after" in latest

    def test_no_op_update_no_history(self, admin_s, seed_license):
        # Get current snapshot via history
        h0 = admin_s.get(f"{API}/licenses/{seed_license}/history", timeout=20)
        before = len(h0.json())
        snap = h0.json()[0]["snapshot_after"]
        # Re-PUT same snapshot
        r = admin_s.put(f"{API}/licenses/{seed_license}", json=snap, timeout=20)
        assert r.status_code == 200, r.text
        assert r.json()["changes"] == 0
        h1 = admin_s.get(f"{API}/licenses/{seed_license}/history", timeout=20)
        assert len(h1.json()) == before

    def test_history_newest_first(self, admin_s, seed_license, seed_customer, seed_product):
        # Trigger another change
        payload = {
            "license_key": f"TEST-ITER3-V2-{uuid.uuid4().hex[:6]}",
            "customer_id": seed_customer,
            "product_id": seed_product,
            "license_count": 7,  # change
            "cost": 250.0,
            "currency": "USD",
            "purchase_date": "2025-01-01",
            "activation_date": "2025-01-01",
            "expiry_date": "2026-06-01",
        }
        r = admin_s.put(f"{API}/licenses/{seed_license}", json=payload, timeout=20)
        assert r.status_code == 200, r.text
        h = admin_s.get(f"{API}/licenses/{seed_license}/history", timeout=20).json()
        assert len(h) >= 2
        ts = [row["timestamp"] for row in h]
        assert ts == sorted(ts, reverse=True)


# ============== Smoke regression ==============
class TestSmokeRegression:
    def test_dashboard_stats(self, admin_s):
        r = admin_s.get(f"{API}/dashboard/stats", timeout=20)
        assert r.status_code == 200
        d = r.json()
        # Schema includes counts and series
        assert isinstance(d, dict)
        # at least some meaningful keys
        assert any(k in d for k in ("monthly_revenue", "customer_growth", "monthly_renewals"))

    def test_customers_list(self, admin_s):
        r = admin_s.get(f"{API}/customers", timeout=20)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_licenses_list(self, admin_s):
        r = admin_s.get(f"{API}/licenses", timeout=20)
        assert r.status_code == 200

    def test_products_list(self, admin_s):
        r = admin_s.get(f"{API}/products", timeout=20)
        assert r.status_code == 200

    def test_alerts_config(self, admin_s):
        r = admin_s.get(f"{API}/alerts/config", timeout=20)
        assert r.status_code == 200
        assert "resend_configured" in r.json()

    def test_customers_template(self, admin_s):
        r = admin_s.get(f"{API}/templates/customers.csv", timeout=20)
        assert r.status_code == 200
        assert "name" in r.text.lower()

    def test_licenses_template(self, admin_s):
        r = admin_s.get(f"{API}/templates/licenses.csv", timeout=20)
        assert r.status_code == 200
