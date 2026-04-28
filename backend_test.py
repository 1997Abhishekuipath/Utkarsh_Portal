#!/usr/bin/env python3
"""
HSI Employee Engagement Platform - Sprint F Backend API Testing
Tests Sprint F features: Sentry integration, Request-ID middleware, health endpoint, profile updates
"""

import requests
import json
import time
import re
from datetime import datetime

# Configuration
BASE_URL = "https://init-demo-2.preview.emergentagent.com"
API_BASE = f"{BASE_URL}/api"

# Test credentials from /app/memory/test_credentials.md
ADMIN_EMAIL = "admin@hitachi-systems.com"
ADMIN_PASSWORD = "Admin@123"

class SprintFTester:
    def __init__(self):
        self.session = requests.Session()
        self.auth_token = None
        self.test_results = []
        
    def log_result(self, test_name, success, details="", response_data=None):
        """Log test result with details"""
        status = "✅ PASS" if success else "❌ FAIL"
        result = {
            "test": test_name,
            "status": status,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        if response_data:
            result["response_data"] = response_data
        self.test_results.append(result)
        print(f"{status}: {test_name}")
        if details:
            print(f"   Details: {details}")
        if not success and response_data:
            print(f"   Response: {response_data}")
        print()

    def test_root_endpoint(self):
        """Test 1: GET /api/ - verify Sprint F message and metadata"""
        try:
            response = self.session.get(f"{API_BASE}/")
            
            if response.status_code == 200:
                data = response.json()
                
                # Check message
                expected_message = "HSI Employee Engagement Platform API v2.0"
                if data.get("message") == expected_message:
                    message_check = True
                    message_details = f"Message correct: '{expected_message}'"
                else:
                    message_check = False
                    message_details = f"Expected: '{expected_message}', Got: '{data.get('message')}'"
                
                # Check sentry_active
                sentry_active = data.get("sentry_active")
                if sentry_active == False:
                    sentry_check = True
                    sentry_details = "sentry_active=false (correct)"
                else:
                    sentry_check = False
                    sentry_details = f"Expected sentry_active=false, Got: {sentry_active}"
                
                # Check sprint
                sprint = data.get("sprint")
                if sprint == "F":
                    sprint_check = True
                    sprint_details = "sprint='F' (correct)"
                else:
                    sprint_check = False
                    sprint_details = f"Expected sprint='F', Got: '{sprint}'"
                
                overall_success = message_check and sentry_check and sprint_check
                details = f"{message_details}; {sentry_details}; {sprint_details}"
                
                self.log_result("GET /api/ - Root endpoint metadata", overall_success, details, data)
            else:
                self.log_result("GET /api/ - Root endpoint metadata", False, 
                              f"HTTP {response.status_code}", response.text)
                
        except Exception as e:
            self.log_result("GET /api/ - Root endpoint metadata", False, f"Exception: {str(e)}")

    def test_health_endpoint(self):
        """Test 2: GET /api/health - verify health checks"""
        try:
            response = self.session.get(f"{API_BASE}/health")
            
            if response.status_code == 200:
                data = response.json()
                
                # Check overall status
                status = data.get("status")
                status_check = status == "healthy"
                
                # Check checks object
                checks = data.get("checks", {})
                
                # Check database status
                db_status = checks.get("database", {}).get("status")
                db_check = db_status == "ok"
                
                # Check for scheduler
                scheduler_exists = "scheduler" in checks
                
                # Check for sentry
                sentry_exists = "sentry" in checks
                
                overall_success = status_check and db_check and scheduler_exists and sentry_exists
                details = f"status={status}; database.status={db_status}; scheduler_present={scheduler_exists}; sentry_present={sentry_exists}"
                
                self.log_result("GET /api/health - Health endpoint", overall_success, details, data)
            else:
                self.log_result("GET /api/health - Health endpoint", False, 
                              f"HTTP {response.status_code}", response.text)
                
        except Exception as e:
            self.log_result("GET /api/health - Health endpoint", False, f"Exception: {str(e)}")

    def test_request_id_header(self):
        """Test 3: Check X-Request-ID header presence"""
        try:
            response = self.session.head(f"{API_BASE}/")
            
            request_id = response.headers.get("X-Request-ID")
            if request_id:
                self.log_result("X-Request-ID header presence", True, 
                              f"X-Request-ID header present: {request_id}")
            else:
                self.log_result("X-Request-ID header presence", False, 
                              "X-Request-ID header missing", dict(response.headers))
                
        except Exception as e:
            self.log_result("X-Request-ID header presence", False, f"Exception: {str(e)}")

    def authenticate(self):
        """Authenticate and get OTP from logs"""
        try:
            # Step 1: Login
            login_data = {
                "email": ADMIN_EMAIL,
                "password": ADMIN_PASSWORD
            }
            
            response = self.session.post(f"{API_BASE}/auth/login", json=login_data)
            
            if response.status_code == 200:
                print("✅ Login successful, checking for OTP in backend logs...")
                
                # Step 2: Get OTP from backend logs
                import subprocess
                try:
                    # Check backend logs for OTP
                    log_result = subprocess.run(
                        ["tail", "-n", "100", "/var/log/supervisor/backend.err.log"],
                        capture_output=True, text=True, timeout=10
                    )
                    
                    log_content = log_result.stdout
                    
                    # Look for OTP patterns
                    otp_patterns = [
                        r'OTP.*?(\d{6})',
                        r'otp.*?(\d{6})',
                        r'(\d{6})',  # Any 6-digit number
                    ]
                    
                    otp_code = None
                    for pattern in otp_patterns:
                        matches = re.findall(pattern, log_content, re.IGNORECASE)
                        if matches:
                            # Get the last match (most recent)
                            otp_code = matches[-1]
                            break
                    
                    if otp_code:
                        print(f"✅ Found OTP in logs: {otp_code}")
                        
                        # Step 3: Verify OTP
                        otp_data = {
                            "email": ADMIN_EMAIL,
                            "code": otp_code,
                            "purpose": "login"
                        }
                        otp_response = self.session.post(f"{API_BASE}/auth/verify-otp", json=otp_data)
                        
                        if otp_response.status_code == 200:
                            otp_result = otp_response.json()
                            self.auth_token = otp_result.get("access_token")
                            if self.auth_token:
                                self.session.headers.update({"Authorization": f"Bearer {self.auth_token}"})
                                self.log_result("Authentication flow", True, 
                                              f"Successfully authenticated with OTP: {otp_code}")
                                return True
                            else:
                                self.log_result("Authentication flow", False, 
                                              "No access_token in OTP response", otp_result)
                        else:
                            self.log_result("Authentication flow", False, 
                                          f"OTP verification failed: HTTP {otp_response.status_code}", 
                                          otp_response.text)
                    else:
                        self.log_result("Authentication flow", False, 
                                      "No OTP found in backend logs", log_content[-500:])
                        
                except subprocess.TimeoutExpired:
                    self.log_result("Authentication flow", False, "Timeout reading backend logs")
                except Exception as log_e:
                    self.log_result("Authentication flow", False, f"Error reading logs: {str(log_e)}")
                    
            else:
                self.log_result("Authentication flow", False, 
                              f"Login failed: HTTP {response.status_code}", response.text)
                
        except Exception as e:
            self.log_result("Authentication flow", False, f"Exception: {str(e)}")
            
        return False

    def test_profile_update(self):
        """Test 4: PATCH /api/users/me - profile self-update"""
        if not self.auth_token:
            self.log_result("PATCH /api/users/me - Profile update", False, "Not authenticated")
            return
            
        try:
            # Test profile update
            update_data = {
                "name": "Admin Test",
                "department": "IT"
            }
            
            response = self.session.patch(f"{API_BASE}/users/me", json=update_data)
            
            if response.status_code == 200:
                data = response.json()
                
                # Check if update was successful
                name_updated = data.get("name") == "Admin Test"
                dept_updated = data.get("department") == "IT"
                
                success = name_updated and dept_updated
                details = f"name_updated={name_updated}, department_updated={dept_updated}"
                
                self.log_result("PATCH /api/users/me - Profile update", success, details, data)
            else:
                self.log_result("PATCH /api/users/me - Profile update", False, 
                              f"HTTP {response.status_code}", response.text)
                
        except Exception as e:
            self.log_result("PATCH /api/users/me - Profile update", False, f"Exception: {str(e)}")

    def test_auth_me(self):
        """Test 5: GET /api/auth/me - verify last_login_at and profile updates"""
        if not self.auth_token:
            self.log_result("GET /api/auth/me - User profile", False, "Not authenticated")
            return
            
        try:
            response = self.session.get(f"{API_BASE}/auth/me")
            
            if response.status_code == 200:
                data = response.json()
                
                # Check last_login_at
                last_login = data.get("last_login_at")
                last_login_check = last_login is not None
                
                # Check profile updates
                name = data.get("name")
                department = data.get("department")
                name_check = name == "Admin Test"
                dept_check = department == "IT"
                
                success = last_login_check and name_check and dept_check
                details = f"last_login_at_present={last_login_check}, name='{name}', department='{department}'"
                
                self.log_result("GET /api/auth/me - User profile", success, details, data)
            else:
                self.log_result("GET /api/auth/me - User profile", False, 
                              f"HTTP {response.status_code}", response.text)
                
        except Exception as e:
            self.log_result("GET /api/auth/me - User profile", False, f"Exception: {str(e)}")

    def test_xp_summary(self):
        """Test 6: GET /api/xp/summary - verify XP summary response"""
        if not self.auth_token:
            self.log_result("GET /api/xp/summary - XP summary", False, "Not authenticated")
            return
            
        try:
            response = self.session.get(f"{API_BASE}/xp/summary")
            
            if response.status_code == 200:
                data = response.json()
                
                # Check for actual fields returned by the API
                expected_fields = ["total_xp", "quarter", "quarter_xp", "rank", "total_users", "breakdown", "level"]
                fields_present = all(field in data for field in expected_fields)
                
                details = f"Expected fields present: {fields_present}, Fields: {list(data.keys())}"
                
                self.log_result("GET /api/xp/summary - XP summary", fields_present, details, data)
            else:
                self.log_result("GET /api/xp/summary - XP summary", False, 
                              f"HTTP {response.status_code}", response.text)
                
        except Exception as e:
            self.log_result("GET /api/xp/summary - XP summary", False, f"Exception: {str(e)}")

    def test_incentive_statement(self):
        """Test 7: GET /api/incentive/statement - verify quarter format"""
        if not self.auth_token:
            self.log_result("GET /api/incentive/statement - Incentive statement", False, "Not authenticated")
            return
            
        try:
            response = self.session.get(f"{API_BASE}/incentive/statement")
            
            if response.status_code == 200:
                data = response.json()
                
                # Check quarter format
                quarter = data.get("quarter")
                quarter_pattern = r"(2025|2026)-Q[1-4]"
                quarter_valid = quarter and re.match(quarter_pattern, quarter)
                
                details = f"Quarter format valid: {quarter_valid}, Quarter: '{quarter}'"
                
                self.log_result("GET /api/incentive/statement - Incentive statement", 
                              quarter_valid, details, data)
            else:
                self.log_result("GET /api/incentive/statement - Incentive statement", False, 
                              f"HTTP {response.status_code}", response.text)
                
        except Exception as e:
            self.log_result("GET /api/incentive/statement - Incentive statement", False, f"Exception: {str(e)}")

    def test_admin_notification_send(self):
        """Test 8: POST /api/admin/notifications/send - send test notification"""
        if not self.auth_token:
            self.log_result("POST /api/admin/notifications/send - Send notification", False, "Not authenticated")
            return
            
        try:
            notification_data = {
                "title": "Sprint F Test",
                "body": "Security hardening complete",
                "category": "announcement",
                "target_type": "all"
            }
            
            response = self.session.post(f"{API_BASE}/admin/notifications/send", json=notification_data)
            
            if response.status_code == 200:
                data = response.json()
                
                # Check response - API returns 'sent' field, not 'success'
                success = data.get("sent", False)
                details = f"Notification sent successfully: {success}"
                
                self.log_result("POST /api/admin/notifications/send - Send notification", 
                              success, details, data)
            else:
                self.log_result("POST /api/admin/notifications/send - Send notification", False, 
                              f"HTTP {response.status_code}", response.text)
                
        except Exception as e:
            self.log_result("POST /api/admin/notifications/send - Send notification", False, f"Exception: {str(e)}")

    def test_notifications_list(self):
        """Test 9: GET /api/notifications - verify user can see notifications"""
        if not self.auth_token:
            self.log_result("GET /api/notifications - List notifications", False, "Not authenticated")
            return
            
        try:
            response = self.session.get(f"{API_BASE}/notifications")
            
            if response.status_code == 200:
                data = response.json()
                
                # Check if it's a paginated response with 'items' array
                has_items = "items" in data and isinstance(data["items"], list)
                has_total = "total" in data
                items = data.get("items", []) if has_items else []
                
                # Look for our test notification
                test_notification_found = False
                if has_items:
                    for notification in items:
                        if (notification.get("title") == "Sprint F Test" and 
                            notification.get("body") == "Security hardening complete"):
                            test_notification_found = True
                            break
                
                success = has_items and has_total and test_notification_found
                details = f"Has items: {has_items}, Has total: {has_total}, Test notification found: {test_notification_found}"
                
                self.log_result("GET /api/notifications - List notifications", success, details, 
                              {"total": data.get("total", 0), "items_count": len(items), "sample": items[:2] if items else []})
            else:
                self.log_result("GET /api/notifications - List notifications", False, 
                              f"HTTP {response.status_code}", response.text)
                
        except Exception as e:
            self.log_result("GET /api/notifications - List notifications", False, f"Exception: {str(e)}")

    def run_all_tests(self):
        """Run all Sprint F tests"""
        print("=" * 80)
        print("HSI Employee Engagement Platform - Sprint F Backend API Testing")
        print("=" * 80)
        print(f"Backend URL: {API_BASE}")
        print(f"Test Credentials: {ADMIN_EMAIL}")
        print("=" * 80)
        print()
        
        # Test 1-3: No auth required
        self.test_root_endpoint()
        self.test_health_endpoint()
        self.test_request_id_header()
        
        # Authenticate
        if self.authenticate():
            # Test 4-9: Auth required
            self.test_profile_update()
            self.test_auth_me()
            self.test_xp_summary()
            self.test_incentive_statement()
            self.test_admin_notification_send()
            self.test_notifications_list()
        else:
            print("❌ Authentication failed - skipping authenticated tests")
        
        # Summary
        print("=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        
        passed = sum(1 for result in self.test_results if "✅ PASS" in result["status"])
        failed = sum(1 for result in self.test_results if "❌ FAIL" in result["status"])
        total = len(self.test_results)
        
        print(f"Total Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print(f"Success Rate: {(passed/total*100):.1f}%" if total > 0 else "0%")
        print()
        
        if failed > 0:
            print("FAILED TESTS:")
            for result in self.test_results:
                if "❌ FAIL" in result["status"]:
                    print(f"  - {result['test']}: {result['details']}")
        
        return passed, failed, total

if __name__ == "__main__":
    tester = SprintFTester()
    passed, failed, total = tester.run_all_tests()
    
    # Exit with appropriate code
    exit(0 if failed == 0 else 1)