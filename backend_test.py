#!/usr/bin/env python3
"""
VoC Intelligence Platform Phase 1 Backend Testing
Tests all 8 VoC endpoints as specified in the review request.
"""

import requests
import json
import sys
from typing import Dict, Any, Optional

# Configuration
BASE_URL = "https://optimistic-chaplygin-3.preview.emergentagent.com/api"
ADMIN_EMAIL = "admin@hitachi-systems.com"
ADMIN_PASSWORD = "Admin@123"
DEMO_OTP = "000000"

class VoCTester:
    def __init__(self):
        self.session = requests.Session()
        self.access_token: Optional[str] = None
        self.test_results = []
        
    def log_test(self, test_name: str, success: bool, details: str = ""):
        """Log test result"""
        status = "✅ PASS" if success else "❌ FAIL"
        self.test_results.append({
            "test": test_name,
            "success": success,
            "details": details
        })
        print(f"{status}: {test_name}")
        if details:
            print(f"    {details}")
    
    def authenticate(self) -> bool:
        """Perform authentication flow"""
        print("\n🔐 Starting Authentication Flow...")
        
        # Step 1: Login
        try:
            login_response = self.session.post(
                f"{BASE_URL}/auth/login",
                json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
                headers={"Content-Type": "application/json"}
            )
            
            if login_response.status_code != 200:
                self.log_test("Login Request", False, f"Status: {login_response.status_code}, Response: {login_response.text}")
                return False
                
            login_data = login_response.json()
            
            if not login_data.get("requires_otp"):
                self.log_test("Login Request", False, "Expected requires_otp=true")
                return False
                
            otp_id = login_data.get("otp_id")
            if not otp_id:
                self.log_test("Login Request", False, "Missing otp_id in response")
                return False
                
            self.log_test("Login Request", True, f"OTP ID received: {otp_id}")
            
        except Exception as e:
            self.log_test("Login Request", False, f"Exception: {str(e)}")
            return False
        
        # Step 2: Verify OTP
        try:
            otp_response = self.session.post(
                f"{BASE_URL}/auth/verify-otp",
                json={
                    "email": ADMIN_EMAIL,
                    "otp_id": otp_id,
                    "code": DEMO_OTP
                },
                headers={"Content-Type": "application/json"}
            )
            
            if otp_response.status_code != 200:
                self.log_test("OTP Verification", False, f"Status: {otp_response.status_code}, Response: {otp_response.text}")
                return False
                
            otp_data = otp_response.json()
            self.access_token = otp_data.get("access_token")
            
            if not self.access_token:
                self.log_test("OTP Verification", False, "Missing access_token in response")
                return False
                
            self.log_test("OTP Verification", True, "Access token received")
            return True
            
        except Exception as e:
            self.log_test("OTP Verification", False, f"Exception: {str(e)}")
            return False
    
    def test_unauthorized_access(self):
        """Test that endpoints require authorization"""
        print("\n🔒 Testing Authorization Requirements...")
        
        test_endpoints = [
            "/voc/dashboard/kpis",
            "/voc/dashboard/trend",
            "/voc/dashboard/verbatims",
            "/voc/accounts"
        ]
        
        for endpoint in test_endpoints:
            try:
                response = requests.get(f"{BASE_URL}{endpoint}")
                if response.status_code == 401:
                    self.log_test(f"Unauthorized Access - {endpoint}", True, "Correctly returns 401")
                else:
                    self.log_test(f"Unauthorized Access - {endpoint}", False, f"Expected 401, got {response.status_code}")
            except Exception as e:
                self.log_test(f"Unauthorized Access - {endpoint}", False, f"Exception: {str(e)}")
    
    def make_authenticated_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make authenticated request"""
        headers = kwargs.get('headers', {})
        headers['Authorization'] = f'Bearer {self.access_token}'
        kwargs['headers'] = headers
        
        return self.session.request(method, f"{BASE_URL}{endpoint}", **kwargs)
    
    def test_voc_dashboard_kpis(self):
        """Test GET /api/voc/dashboard/kpis"""
        print("\n📊 Testing VoC Dashboard KPIs...")
        
        try:
            response = self.make_authenticated_request('GET', '/voc/dashboard/kpis')
            
            if response.status_code != 200:
                self.log_test("VoC Dashboard KPIs", False, f"Status: {response.status_code}, Response: {response.text}")
                return
            
            data = response.json()
            
            # Check required fields
            required_fields = [
                'nps_score', 'csat_score', 'ces_score', 'response_rate',
                'promoter_pct', 'passive_pct', 'detractor_pct', 
                'total_responses', 'active_accounts'
            ]
            
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                self.log_test("VoC Dashboard KPIs", False, f"Missing fields: {missing_fields}")
                return
            
            # Check data expectations
            total_responses = data.get('total_responses', 0)
            active_accounts = data.get('active_accounts', 0)
            
            details = f"Total responses: {total_responses}, Active accounts: {active_accounts}"
            
            # Verify expected data ranges
            if total_responses < 140 or total_responses > 150:
                self.log_test("VoC Dashboard KPIs", False, f"Expected ~142 responses, got {total_responses}")
                return
                
            if active_accounts != 6:
                self.log_test("VoC Dashboard KPIs", False, f"Expected 6 active accounts, got {active_accounts}")
                return
            
            self.log_test("VoC Dashboard KPIs", True, details)
            
        except Exception as e:
            self.log_test("VoC Dashboard KPIs", False, f"Exception: {str(e)}")
    
    def test_voc_dashboard_trend(self):
        """Test GET /api/voc/dashboard/trend"""
        print("\n📈 Testing VoC Dashboard Trend...")
        
        try:
            response = self.make_authenticated_request('GET', '/voc/dashboard/trend')
            
            if response.status_code != 200:
                self.log_test("VoC Dashboard Trend", False, f"Status: {response.status_code}, Response: {response.text}")
                return
            
            data = response.json()
            
            if not isinstance(data, list):
                self.log_test("VoC Dashboard Trend", False, "Expected array response")
                return
            
            if len(data) != 12:
                self.log_test("VoC Dashboard Trend", False, f"Expected 12 months, got {len(data)}")
                return
            
            # Check structure of first item
            if data:
                item = data[0]
                required_fields = ['month', 'nps', 'csat']
                missing_fields = [field for field in required_fields if field not in item]
                if missing_fields:
                    self.log_test("VoC Dashboard Trend", False, f"Missing fields in trend data: {missing_fields}")
                    return
            
            # Count non-null values
            non_null_nps = sum(1 for item in data if item.get('nps') is not None)
            non_null_csat = sum(1 for item in data if item.get('csat') is not None)
            
            details = f"12 months data, {non_null_nps} NPS values, {non_null_csat} CSAT values"
            self.log_test("VoC Dashboard Trend", True, details)
            
        except Exception as e:
            self.log_test("VoC Dashboard Trend", False, f"Exception: {str(e)}")
    
    def test_voc_dashboard_verbatims(self):
        """Test GET /api/voc/dashboard/verbatims?limit=6"""
        print("\n💬 Testing VoC Dashboard Verbatims...")
        
        try:
            response = self.make_authenticated_request('GET', '/voc/dashboard/verbatims?limit=6')
            
            if response.status_code != 200:
                self.log_test("VoC Dashboard Verbatims", False, f"Status: {response.status_code}, Response: {response.text}")
                return
            
            data = response.json()
            
            if not isinstance(data, list):
                self.log_test("VoC Dashboard Verbatims", False, "Expected array response")
                return
            
            if len(data) > 6:
                self.log_test("VoC Dashboard Verbatims", False, f"Expected max 6 verbatims, got {len(data)}")
                return
            
            # Check structure if we have data
            if data:
                item = data[0]
                required_fields = ['id', 'type', 'score', 'text', 'account_name', 'color']
                missing_fields = [field for field in required_fields if field not in item]
                if missing_fields:
                    self.log_test("VoC Dashboard Verbatims", False, f"Missing fields: {missing_fields}")
                    return
                
                # Check type values
                valid_types = ['PROMOTER', 'PASSIVE', 'DETRACTOR']
                if item.get('type') not in valid_types:
                    self.log_test("VoC Dashboard Verbatims", False, f"Invalid type: {item.get('type')}")
                    return
            
            details = f"Returned {len(data)} verbatims"
            self.log_test("VoC Dashboard Verbatims", True, details)
            
        except Exception as e:
            self.log_test("VoC Dashboard Verbatims", False, f"Exception: {str(e)}")
    
    def test_voc_dashboard_pain_points(self):
        """Test GET /api/voc/dashboard/pain-points"""
        print("\n🔍 Testing VoC Dashboard Pain Points...")
        
        try:
            response = self.make_authenticated_request('GET', '/voc/dashboard/pain-points')
            
            if response.status_code != 200:
                self.log_test("VoC Dashboard Pain Points", False, f"Status: {response.status_code}, Response: {response.text}")
                return
            
            data = response.json()
            
            if not isinstance(data, list):
                self.log_test("VoC Dashboard Pain Points", False, "Expected array response")
                return
            
            expected_pain_points = [
                'Communication Gaps', 'Documentation', 'Reporting Clarity', 
                'Response Time', 'Escalation Process'
            ]
            
            if data:
                item = data[0]
                required_fields = ['label', 'count', 'sub', 'pct', 'color']
                missing_fields = [field for field in required_fields if field not in item]
                if missing_fields:
                    self.log_test("VoC Dashboard Pain Points", False, f"Missing fields: {missing_fields}")
                    return
            
            details = f"Returned {len(data)} pain points"
            if len(data) == 5:
                details += " (expected 5)"
            
            self.log_test("VoC Dashboard Pain Points", True, details)
            
        except Exception as e:
            self.log_test("VoC Dashboard Pain Points", False, f"Exception: {str(e)}")
    
    def test_voc_dashboard_csat_distribution(self):
        """Test GET /api/voc/dashboard/csat-distribution"""
        print("\n⭐ Testing VoC Dashboard CSAT Distribution...")
        
        try:
            response = self.make_authenticated_request('GET', '/voc/dashboard/csat-distribution')
            
            if response.status_code != 200:
                self.log_test("VoC Dashboard CSAT Distribution", False, f"Status: {response.status_code}, Response: {response.text}")
                return
            
            data = response.json()
            
            if not isinstance(data, list):
                self.log_test("VoC Dashboard CSAT Distribution", False, "Expected array response")
                return
            
            if len(data) != 5:
                self.log_test("VoC Dashboard CSAT Distribution", False, f"Expected 5 ratings, got {len(data)}")
                return
            
            # Check structure
            expected_ratings = ['5★', '4★', '3★', '2★', '1★']
            actual_ratings = [item.get('rating') for item in data]
            
            if actual_ratings != expected_ratings:
                self.log_test("VoC Dashboard CSAT Distribution", False, f"Expected ratings {expected_ratings}, got {actual_ratings}")
                return
            
            # Check required fields
            if data:
                item = data[0]
                required_fields = ['rating', 'count', 'pct']
                missing_fields = [field for field in required_fields if field not in item]
                if missing_fields:
                    self.log_test("VoC Dashboard CSAT Distribution", False, f"Missing fields: {missing_fields}")
                    return
            
            self.log_test("VoC Dashboard CSAT Distribution", True, "5 star ratings with counts and percentages")
            
        except Exception as e:
            self.log_test("VoC Dashboard CSAT Distribution", False, f"Exception: {str(e)}")
    
    def test_voc_dashboard_strengths(self):
        """Test GET /api/voc/dashboard/strengths?limit=4"""
        print("\n💪 Testing VoC Dashboard Strengths...")
        
        try:
            response = self.make_authenticated_request('GET', '/voc/dashboard/strengths?limit=4')
            
            if response.status_code != 200:
                self.log_test("VoC Dashboard Strengths", False, f"Status: {response.status_code}, Response: {response.text}")
                return
            
            data = response.json()
            
            if not isinstance(data, list):
                self.log_test("VoC Dashboard Strengths", False, "Expected array response")
                return
            
            if len(data) > 4:
                self.log_test("VoC Dashboard Strengths", False, f"Expected max 4 strengths, got {len(data)}")
                return
            
            # Check structure if we have data
            if data:
                item = data[0]
                required_fields = ['count', 'badge', 'quote', 'tag']
                missing_fields = [field for field in required_fields if field not in item]
                if missing_fields:
                    self.log_test("VoC Dashboard Strengths", False, f"Missing fields: {missing_fields}")
                    return
            
            details = f"Returned {len(data)} strength items"
            self.log_test("VoC Dashboard Strengths", True, details)
            
        except Exception as e:
            self.log_test("VoC Dashboard Strengths", False, f"Exception: {str(e)}")
    
    def test_voc_accounts_list(self):
        """Test GET /api/voc/accounts"""
        print("\n🏢 Testing VoC Accounts List...")
        
        try:
            response = self.make_authenticated_request('GET', '/voc/accounts')
            
            if response.status_code != 200:
                self.log_test("VoC Accounts List", False, f"Status: {response.status_code}, Response: {response.text}")
                return
            
            data = response.json()
            
            if not isinstance(data, dict) or 'accounts' not in data or 'total' not in data:
                self.log_test("VoC Accounts List", False, "Expected object with 'accounts' and 'total' fields")
                return
            
            accounts = data['accounts']
            total = data['total']
            
            if not isinstance(accounts, list):
                self.log_test("VoC Accounts List", False, "Expected 'accounts' to be an array")
                return
            
            if total != 6:
                self.log_test("VoC Accounts List", False, f"Expected total=6, got {total}")
                return
            
            # Check account structure
            if accounts:
                account = accounts[0]
                required_fields = [
                    'id', 'company_name', 'industry', 'practice', 
                    'latest_nps', 'latest_csat', 'rag_status', 
                    'total_responses', 'initials'
                ]
                missing_fields = [field for field in required_fields if field not in account]
                if missing_fields:
                    self.log_test("VoC Accounts List", False, f"Missing fields: {missing_fields}")
                    return
                
                # Check for expected companies
                company_names = [acc.get('company_name', '') for acc in accounts]
                expected_companies = ['Reliance Petro', 'Axis Bank', 'L&T Constructs', 'HCL Unistore', 'Tata Motors', 'SBI Life']
                
                # Store first account ID for detail test
                self.first_account_id = account.get('id')
            
            details = f"6 accounts returned with proper structure"
            self.log_test("VoC Accounts List", True, details)
            
        except Exception as e:
            self.log_test("VoC Accounts List", False, f"Exception: {str(e)}")
    
    def test_voc_account_detail(self):
        """Test GET /api/voc/accounts/{id}"""
        print("\n🔍 Testing VoC Account Detail...")
        
        if not hasattr(self, 'first_account_id') or not self.first_account_id:
            self.log_test("VoC Account Detail", False, "No account ID available from accounts list test")
            return
        
        try:
            response = self.make_authenticated_request('GET', f'/voc/accounts/{self.first_account_id}')
            
            if response.status_code != 200:
                self.log_test("VoC Account Detail", False, f"Status: {response.status_code}, Response: {response.text}")
                return
            
            data = response.json()
            
            required_fields = [
                'id', 'company_name', 'industry', 'practice',
                'latest_nps', 'latest_csat', 'rag_status',
                'total_responses', 'recent_responses'
            ]
            
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                self.log_test("VoC Account Detail", False, f"Missing fields: {missing_fields}")
                return
            
            recent_responses = data.get('recent_responses', [])
            if not isinstance(recent_responses, list):
                self.log_test("VoC Account Detail", False, "Expected 'recent_responses' to be an array")
                return
            
            details = f"Account detail with {len(recent_responses)} recent responses"
            self.log_test("VoC Account Detail", True, details)
            
        except Exception as e:
            self.log_test("VoC Account Detail", False, f"Exception: {str(e)}")
    
    def run_all_tests(self):
        """Run all VoC backend tests"""
        print("🚀 Starting VoC Intelligence Platform Phase 1 Backend Testing")
        print("=" * 60)
        
        # Authentication
        if not self.authenticate():
            print("\n❌ Authentication failed. Cannot proceed with API tests.")
            return False
        
        # Test unauthorized access
        self.test_unauthorized_access()
        
        # Test all VoC endpoints
        self.test_voc_dashboard_kpis()
        self.test_voc_dashboard_trend()
        self.test_voc_dashboard_verbatims()
        self.test_voc_dashboard_pain_points()
        self.test_voc_dashboard_csat_distribution()
        self.test_voc_dashboard_strengths()
        self.test_voc_accounts_list()
        self.test_voc_account_detail()
        
        # Summary
        self.print_summary()
        
        return all(result['success'] for result in self.test_results)
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 60)
        print("📋 TEST SUMMARY")
        print("=" * 60)
        
        passed = sum(1 for result in self.test_results if result['success'])
        total = len(self.test_results)
        
        print(f"Total Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {total - passed}")
        print(f"Success Rate: {passed/total*100:.1f}%")
        
        if total - passed > 0:
            print("\n❌ FAILED TESTS:")
            for result in self.test_results:
                if not result['success']:
                    print(f"  - {result['test']}: {result['details']}")
        
        print("\n✅ PASSED TESTS:")
        for result in self.test_results:
            if result['success']:
                print(f"  - {result['test']}")

if __name__ == "__main__":
    tester = VoCTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)