"""HSI Enterprise Portal - Backend API Tests"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestAuthEndpoints:
    """Auth endpoint tests"""

    def test_login_admin(self):
        r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": "admin@hsi.com", "password": "Admin@123"})
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data
        assert data["user"]["role"] == "admin"
        assert data["user"]["email"] == "admin@hsi.com"

    def test_login_employee(self):
        r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": "employee@hsi.com", "password": "Employee@123"})
        assert r.status_code == 200
        data = r.json()
        assert data["user"]["role"] == "employee"
        assert data["user"]["name"] == "Arjun Mehta"

    def test_login_manager(self):
        r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": "manager@hsi.com", "password": "Manager@123"})
        assert r.status_code == 200
        data = r.json()
        assert data["user"]["role"] == "manager"

    def test_login_invalid(self):
        r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": "wrong@hsi.com", "password": "wrongpass"})
        assert r.status_code == 401

    def test_register_employee(self):
        import uuid
        unique_email = f"test_{uuid.uuid4().hex[:8]}@hsi.com"
        r = requests.post(f"{BASE_URL}/api/auth/register", json={
            "name": "Test Employee", "email": unique_email,
            "password": "Test@123", "role": "employee"
        })
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data
        assert data["user"]["role"] == "employee"
        return data["access_token"]

    def test_me_endpoint(self):
        login = requests.post(f"{BASE_URL}/api/auth/login", json={"email": "admin@hsi.com", "password": "Admin@123"})
        token = login.json()["access_token"]
        r = requests.get(f"{BASE_URL}/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["email"] == "admin@hsi.com"

    def test_me_unauthenticated(self):
        r = requests.get(f"{BASE_URL}/api/auth/me")
        assert r.status_code == 401


class TestDashboardEndpoints:
    """Dashboard endpoints - all require auth"""

    @pytest.fixture(autouse=True)
    def auth_token(self):
        r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": "employee@hsi.com", "password": "Employee@123"})
        self.token = r.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def test_stats(self):
        r = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=self.headers)
        assert r.status_code == 200
        data = r.json()
        assert "best_practices" in data
        assert "efforts" in data
        assert "xp_incentive" in data
        assert "tech_days" in data
        assert "pending_actions" in data

    def test_activities(self):
        r = requests.get(f"{BASE_URL}/api/dashboard/activities", headers=self.headers)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_leaderboard(self):
        r = requests.get(f"{BASE_URL}/api/dashboard/leaderboard", headers=self.headers)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert "rank" in data[0]
        assert "xp" in data[0]

    def test_announcements(self):
        r = requests.get(f"{BASE_URL}/api/dashboard/announcements", headers=self.headers)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_pending_actions(self):
        r = requests.get(f"{BASE_URL}/api/dashboard/pending-actions", headers=self.headers)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_upcoming(self):
        r = requests.get(f"{BASE_URL}/api/dashboard/upcoming", headers=self.headers)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)

    def test_score(self):
        r = requests.get(f"{BASE_URL}/api/dashboard/score", headers=self.headers)
        assert r.status_code == 200
        data = r.json()
        assert "percentage" in data
        assert "total_xp" in data
        assert "breakdown" in data


class TestAdminEndpoints:
    """Admin panel endpoints"""

    @pytest.fixture(autouse=True)
    def tokens(self):
        admin_r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": "admin@hsi.com", "password": "Admin@123"})
        self.admin_token = admin_r.json()["access_token"]
        self.admin_headers = {"Authorization": f"Bearer {self.admin_token}"}

        emp_r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": "employee@hsi.com", "password": "Employee@123"})
        self.emp_token = emp_r.json()["access_token"]
        self.emp_headers = {"Authorization": f"Bearer {self.emp_token}"}

    def test_admin_get_users(self):
        r = requests.get(f"{BASE_URL}/api/admin/users", headers=self.admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) >= 3

    def test_employee_cannot_get_admin_users(self):
        r = requests.get(f"{BASE_URL}/api/admin/users", headers=self.emp_headers)
        assert r.status_code == 403

    def test_admin_update_role(self):
        # Get users first
        users_r = requests.get(f"{BASE_URL}/api/admin/users", headers=self.admin_headers)
        users = users_r.json()
        # Find an employee to update
        emp = next((u for u in users if u["role"] == "employee" and u["email"] != "admin@hsi.com"), None)
        if not emp:
            pytest.skip("No employee found to test role update")
        # Update role
        r = requests.put(f"{BASE_URL}/api/admin/users/{emp['id']}/role",
                         json={"role": "manager"}, headers=self.admin_headers)
        assert r.status_code == 200
        # Restore
        requests.put(f"{BASE_URL}/api/admin/users/{emp['id']}/role",
                     json={"role": "employee"}, headers=self.admin_headers)
