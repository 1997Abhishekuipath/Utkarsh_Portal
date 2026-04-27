#!/usr/bin/env python3
"""
HSI Employee Engagement Platform - Backend API Testing
Tests Sprint D (XP & Incentive Engine) and Sprint E (Notifications + Auto-triggers)
"""

import requests
import json
import re
import subprocess
import sys
from datetime import datetime

# Configuration
BASE_URL = "https://docker-start-demo.preview.emergentagent.com/api"
ADMIN_EMAIL = "admin@hitachi-systems.com"
ADMIN_PASSWORD = "Admin@123"

class HSIBackendTester:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'HSI-Backend-Tester/1.0'
        })
        self.auth_token = None
        self.test_results = []
        
    def log_result(self, test_name, success, message, response_data=None):
        """Log test result"""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}: {message}")
        self.test_results.append({
            'test': test_name,
            'success': success,
            'message': message,
            'response_data': response_data
        })
        
    def get_otp_from_logs(self):
        """Extract OTP from backend logs"""
        try:
            result = subprocess.run(
                ['tail', '-n', '100', '/var/log/supervisor/backend.err.log'],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                # Look for OTP pattern in logs
                otp_pattern = r'OTP.*?(\d{6})'
                matches = re.findall(otp_pattern, result.stdout)
                if matches:
                    return matches[-1]  # Return the most recent OTP
                    
                # Alternative pattern
                otp_pattern2 = r'(\d{6})'
                lines = result.stdout.split('\n')
                for line in reversed(lines):
                    if 'otp' in line.lower() or 'code' in line.lower():
                        matches = re.findall(otp_pattern2, line)
                        if matches:
                            return matches[-1]
            return None
        except Exception as e:
            print(f"Error reading logs: {e}")
            return None
    
    def test_basic_api(self):
        """Test basic API connectivity"""
        try:
            response = self.session.get(f"{BASE_URL}/")
            if response.status_code == 200:
                data = response.json()
                self.log_result("Basic API", True, f"API is running: {data.get('message', 'Unknown')}")
                return True
            else:
                self.log_result("Basic API", False, f"API returned status {response.status_code}")
                return False
        except Exception as e:
            self.log_result("Basic API", False, f"Connection error: {str(e)}")
            return False
    
    def test_authentication(self):
        """Test authentication flow with MFA"""
        try:
            # Step 1: Login
            login_data = {
                "email": ADMIN_EMAIL,
                "password": ADMIN_PASSWORD
            }
            
            response = self.session.post(f"{BASE_URL}/auth/login", json=login_data)
            
            if response.status_code != 200:
                self.log_result("Auth Login", False, f"Login failed with status {response.status_code}: {response.text}")
                return False
                
            login_result = response.json()
            
            if not login_result.get('requires_otp'):
                self.log_result("Auth Login", False, "Expected OTP to be required but it wasn't")
                return False
                
            self.log_result("Auth Login", True, "Login successful, MFA required")
            
            # Step 2: Get OTP from logs
            print("Waiting for OTP in backend logs...")
            otp = self.get_otp_from_logs()
            
            if not otp:
                self.log_result("Auth OTP", False, "Could not extract OTP from backend logs")
                return False
                
            print(f"Found OTP: {otp}")
            
            # Step 3: Verify OTP
            otp_data = {
                "email": ADMIN_EMAIL,
                "code": otp,
                "purpose": "login"
            }
            response = self.session.post(f"{BASE_URL}/auth/verify-otp", json=otp_data)
            
            if response.status_code != 200:
                self.log_result("Auth OTP", False, f"OTP verification failed with status {response.status_code}: {response.text}")
                return False
                
            otp_result = response.json()
            self.auth_token = otp_result.get('access_token')
            
            if self.auth_token:
                self.session.headers.update({'Authorization': f'Bearer {self.auth_token}'})
                self.log_result("Auth OTP", True, "OTP verification successful, authenticated")
                return True
            else:
                self.log_result("Auth OTP", False, "No access token received")
                return False
                
        except Exception as e:
            self.log_result("Authentication", False, f"Authentication error: {str(e)}")
            return False
    
    def test_dashboard_endpoints(self):
        """Test dashboard endpoints for live data"""
        endpoints = [
            ("/dashboard/stats", "Dashboard Stats"),
            ("/dashboard/score", "Dashboard Score"),
            ("/dashboard/leaderboard", "Dashboard Leaderboard")
        ]
        
        for endpoint, name in endpoints:
            try:
                response = self.session.get(f"{BASE_URL}{endpoint}")
                if response.status_code == 200:
                    data = response.json()
                    # Check if it's live data (not mock)
                    if isinstance(data, dict):
                        if name == "Dashboard Leaderboard" and len(data.get('leaders', [])) == 0:
                            self.log_result(name, True, "Leaderboard returned empty list (expected with fresh data)")
                        elif data:
                            self.log_result(name, True, f"Returned live data with {len(data)} fields")
                        else:
                            self.log_result(name, False, "Returned empty or invalid data")
                    elif isinstance(data, list):
                        self.log_result(name, True, f"Returned list with {len(data)} items")
                    else:
                        self.log_result(name, False, f"Returned non-dict/non-list data: {type(data)} - {data}")
                else:
                    self.log_result(name, False, f"Status {response.status_code}: {response.text}")
            except Exception as e:
                self.log_result(name, False, f"Error: {str(e)}")
    
    def test_xp_endpoints(self):
        """Test XP-related endpoints"""
        endpoints = [
            ("/xp/summary", "XP Summary"),
            ("/xp/ledger", "XP Ledger")
        ]
        
        for endpoint, name in endpoints:
            try:
                response = self.session.get(f"{BASE_URL}{endpoint}")
                if response.status_code == 200:
                    data = response.json()
                    self.log_result(name, True, f"XP data retrieved successfully")
                else:
                    self.log_result(name, False, f"Status {response.status_code}: {response.text}")
            except Exception as e:
                self.log_result(name, False, f"Error: {str(e)}")
    
    def test_practices_endpoints(self):
        """Test best practices endpoints"""
        try:
            # Test GET approved practices
            response = self.session.get(f"{BASE_URL}/practices?status=approved")
            if response.status_code == 200:
                data = response.json()
                self.log_result("Practices List", True, f"Retrieved {len(data.get('practices', []))} approved practices")
            else:
                self.log_result("Practices List", False, f"Status {response.status_code}: {response.text}")
            
            # Test POST new practice
            practice_data = {
                "title": "Test Practice",
                "summary": "Test summary for automated testing",
                "difficulty": "medium",
                "pillar": "customer",
                "art_tag": "retain",
                "status": "pending"
            }
            
            response = self.session.post(f"{BASE_URL}/practices", json=practice_data)
            if response.status_code in [200, 201]:
                data = response.json()
                self.log_result("Practice Submit", True, f"Practice submitted successfully with ID: {data.get('id', 'unknown')}")
            else:
                self.log_result("Practice Submit", False, f"Status {response.status_code}: {response.text}")
                
        except Exception as e:
            self.log_result("Practices", False, f"Error: {str(e)}")
    
    def test_notifications_endpoints(self):
        """Test notification endpoints"""
        try:
            # Test unread count - need to check if endpoint exists
            response = self.session.get(f"{BASE_URL}/notifications/unread-count")
            if response.status_code == 200:
                data = response.json()
                self.log_result("Notifications Unread Count", True, f"Unread count: {data.get('count', 0)}")
            elif response.status_code == 404:
                self.log_result("Notifications Unread Count", False, "Endpoint /notifications/unread-count not found - may need to be implemented")
            else:
                self.log_result("Notifications Unread Count", False, f"Status {response.status_code}: {response.text}")
            
            # Test notifications list
            response = self.session.get(f"{BASE_URL}/notifications")
            if response.status_code == 200:
                data = response.json()
                self.log_result("Notifications List", True, f"Retrieved {data.get('total', 0)} notifications")
            else:
                self.log_result("Notifications List", False, f"Status {response.status_code}: {response.text}")
                
        except Exception as e:
            self.log_result("Notifications", False, f"Error: {str(e)}")
    
    def test_admin_endpoints(self):
        """Test admin endpoints"""
        try:
            # Test admin notification send
            notification_data = {
                "title": "Test Notification",
                "body": "Test message from automated testing",
                "category": "announcement",
                "target_type": "all"
            }
            
            response = self.session.post(f"{BASE_URL}/admin/notifications/send", json=notification_data)
            if response.status_code in [200, 201]:
                data = response.json()
                self.log_result("Admin Notification Send", True, f"Notification sent successfully: {data.get('notification_id', 'unknown')}")
            else:
                self.log_result("Admin Notification Send", False, f"Status {response.status_code}: {response.text}")
            
            # Test admin analytics
            response = self.session.get(f"{BASE_URL}/admin/analytics/summary")
            if response.status_code == 200:
                data = response.json()
                self.log_result("Admin Analytics", True, f"Analytics data retrieved with {len(data)} metrics")
            else:
                self.log_result("Admin Analytics", False, f"Status {response.status_code}: {response.text}")
                
        except Exception as e:
            self.log_result("Admin Endpoints", False, f"Error: {str(e)}")
    
    def test_tech_days_certifications(self):
        """Test tech days and certifications endpoints"""
        try:
            # Test tech days submission
            tech_day_data = {
                "title": "Test Tech Day",
                "description": "Automated test tech day submission",
                "conducted_on": "2024-01-15",
                "attendee_count": 10,
                "client_name": "Test Client"
            }
            
            response = self.session.post(f"{BASE_URL}/tech-days", json=tech_day_data)
            if response.status_code in [200, 201]:
                data = response.json()
                self.log_result("Tech Days Submit", True, f"Tech day submitted with ID: {data.get('id', 'unknown')}")
            else:
                self.log_result("Tech Days Submit", False, f"Status {response.status_code}: {response.text}")
            
            # Test certifications submission
            cert_data = {
                "cert_name": "Test Certification",
                "provider": "Test Provider",
                "issued_on": "2024-01-15",
                "expires_on": "2025-01-15",
                "evidence_url": "https://example.com/cert.pdf"
            }
            
            response = self.session.post(f"{BASE_URL}/certifications", json=cert_data)
            if response.status_code in [200, 201]:
                data = response.json()
                self.log_result("Certifications Submit", True, f"Certification submitted with ID: {data.get('id', 'unknown')}")
            else:
                self.log_result("Certifications Submit", False, f"Status {response.status_code}: {response.text}")
                
        except Exception as e:
            self.log_result("Tech Days/Certifications", False, f"Error: {str(e)}")
    
    def run_all_tests(self):
        """Run all backend tests"""
        print("=" * 60)
        print("HSI Employee Engagement Platform - Backend API Tests")
        print("=" * 60)
        
        # Test basic connectivity
        if not self.test_basic_api():
            print("❌ Basic API test failed. Stopping tests.")
            return False
        
        # Test authentication
        if not self.test_authentication():
            print("❌ Authentication failed. Stopping tests.")
            return False
        
        # Run all other tests
        self.test_dashboard_endpoints()
        self.test_xp_endpoints()
        self.test_practices_endpoints()
        self.test_notifications_endpoints()
        self.test_admin_endpoints()
        self.test_tech_days_certifications()
        
        # Summary
        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        
        passed = sum(1 for result in self.test_results if result['success'])
        total = len(self.test_results)
        
        print(f"Total Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {total - passed}")
        
        if total - passed > 0:
            print("\nFAILED TESTS:")
            for result in self.test_results:
                if not result['success']:
                    print(f"  ❌ {result['test']}: {result['message']}")
        
        return passed == total

if __name__ == "__main__":
    tester = HSIBackendTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)