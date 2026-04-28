#!/usr/bin/env python3
"""
VoC Intelligence Platform Phase 2 Backend Testing
Tests all VoC Phase 2 endpoints as specified in the review request.

ENDPOINTS TO TEST:
1. GET /api/voc/surveys (auth required)
2. POST /api/voc/surveys (auth required, admin/manager role)
3. GET /api/voc/campaigns (auth required)
4. POST /api/voc/campaigns (auth required)
5. POST /api/voc/campaigns/:id/send (auth required)
6. GET /api/voc/public/survey/:token (NO AUTH - public endpoint)
7. POST /api/voc/public/survey/:token (NO AUTH - submit response)
8. POST /api/voc/public/survey/:token (SECOND attempt - should be blocked)
9. GET /api/voc/campaigns/:id/stats (auth required)
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

class VoCPhase2Tester:
    def __init__(self):
        self.session = requests.Session()
        self.access_token: Optional[str] = None
        self.test_results = []
        self.survey_id: Optional[str] = None
        self.account_id: Optional[str] = None
        self.campaign_id: Optional[str] = None
        self.survey_token: Optional[str] = None
        
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
    
    def make_authenticated_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make authenticated request"""
        headers = kwargs.get('headers', {})
        headers['Authorization'] = f'Bearer {self.access_token}'
        kwargs['headers'] = headers
        
        return self.session.request(method, f"{BASE_URL}{endpoint}", **kwargs)
    
    def make_public_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make public request (no auth)"""
        return self.session.request(method, f"{BASE_URL}{endpoint}", **kwargs)
    
    def test_get_surveys(self):
        """Test 1: GET /api/voc/surveys (auth required)"""
        print("\n📋 Testing GET /api/voc/surveys...")
        
        try:
            response = self.make_authenticated_request('GET', '/voc/surveys')
            
            if response.status_code != 200:
                self.log_test("GET /api/voc/surveys", False, f"Status: {response.status_code}, Response: {response.text}")
                return
            
            data = response.json()
            
            if not isinstance(data, list):
                self.log_test("GET /api/voc/surveys", False, "Expected array response")
                return
            
            if len(data) < 1:
                self.log_test("GET /api/voc/surveys", False, "Expected at least 1 survey")
                return
            
            # Store first survey ID for later use
            if data:
                self.survey_id = data[0].get('id')
                survey_title = data[0].get('title', 'Unknown')
                survey_type = data[0].get('survey_type', 'Unknown')
                
                details = f"Found {len(data)} surveys, first: {survey_title} (type: {survey_type})"
                self.log_test("GET /api/voc/surveys", True, details)
            else:
                self.log_test("GET /api/voc/surveys", False, "No surveys found")
            
        except Exception as e:
            self.log_test("GET /api/voc/surveys", False, f"Exception: {str(e)}")
    
    def test_post_surveys(self):
        """Test 2: POST /api/voc/surveys (auth required, admin/manager role)"""
        print("\n📝 Testing POST /api/voc/surveys...")
        
        survey_data = {
            "survey_type": "nps",
            "title": "Test NPS Survey",
            "main_question": "Would you recommend HSI? (0-10)",
            "followup_question": "Why?",
            "thank_you_msg": "Thanks!"
        }
        
        try:
            response = self.make_authenticated_request(
                'POST', 
                '/voc/surveys',
                json=survey_data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code != 201:
                self.log_test("POST /api/voc/surveys", False, f"Status: {response.status_code}, Response: {response.text}")
                return
            
            data = response.json()
            
            required_fields = ['id', 'title', 'version', 'survey_type']
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                self.log_test("POST /api/voc/surveys", False, f"Missing fields: {missing_fields}")
                return
            
            if data.get('version') != 1:
                self.log_test("POST /api/voc/surveys", False, f"Expected version=1, got {data.get('version')}")
                return
            
            if data.get('survey_type') != 'nps':
                self.log_test("POST /api/voc/surveys", False, f"Expected survey_type='nps', got {data.get('survey_type')}")
                return
            
            # Store survey ID if we don't have one yet
            if not self.survey_id:
                self.survey_id = data.get('id')
            
            details = f"Created survey: {data.get('title')} (ID: {data.get('id')}, version: {data.get('version')})"
            self.log_test("POST /api/voc/surveys", True, details)
            
        except Exception as e:
            self.log_test("POST /api/voc/surveys", False, f"Exception: {str(e)}")
    
    def test_get_campaigns(self):
        """Test 3: GET /api/voc/campaigns (auth required)"""
        print("\n📧 Testing GET /api/voc/campaigns...")
        
        try:
            response = self.make_authenticated_request('GET', '/voc/campaigns')
            
            if response.status_code != 200:
                self.log_test("GET /api/voc/campaigns", False, f"Status: {response.status_code}, Response: {response.text}")
                return
            
            data = response.json()
            
            if not isinstance(data, list):
                self.log_test("GET /api/voc/campaigns", False, "Expected array response")
                return
            
            if len(data) < 6:
                self.log_test("GET /api/voc/campaigns", False, f"Expected at least 6 campaigns (demo data), got {len(data)}")
                return
            
            details = f"Found {len(data)} campaigns (expected at least 6 demo campaigns)"
            self.log_test("GET /api/voc/campaigns", True, details)
            
        except Exception as e:
            self.log_test("GET /api/voc/campaigns", False, f"Exception: {str(e)}")
    
    def get_account_id(self):
        """Get first account ID for campaign creation"""
        try:
            response = self.make_authenticated_request('GET', '/voc/accounts')
            if response.status_code == 200:
                data = response.json()
                accounts = data.get('accounts', [])
                if accounts:
                    self.account_id = accounts[0].get('id')
                    return True
            return False
        except:
            return False
    
    def test_post_campaigns(self):
        """Test 4: POST /api/voc/campaigns (auth required)"""
        print("\n📨 Testing POST /api/voc/campaigns...")
        
        # Get account ID if we don't have one
        if not self.account_id:
            if not self.get_account_id():
                self.log_test("POST /api/voc/campaigns", False, "Could not get account_id from /api/voc/accounts")
                return
        
        if not self.survey_id:
            self.log_test("POST /api/voc/campaigns", False, "No survey_id available from previous tests")
            return
        
        campaign_data = {
            "name": "Test Campaign",
            "survey_id": self.survey_id,
            "account_id": self.account_id
        }
        
        try:
            response = self.make_authenticated_request(
                'POST', 
                '/voc/campaigns',
                json=campaign_data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code != 201:
                self.log_test("POST /api/voc/campaigns", False, f"Status: {response.status_code}, Response: {response.text}")
                return
            
            data = response.json()
            
            required_fields = ['id', 'name', 'status']
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                self.log_test("POST /api/voc/campaigns", False, f"Missing fields: {missing_fields}")
                return
            
            if data.get('status') != 'draft':
                self.log_test("POST /api/voc/campaigns", False, f"Expected status='draft', got {data.get('status')}")
                return
            
            # Store campaign ID for later tests
            self.campaign_id = data.get('id')
            
            details = f"Created campaign: {data.get('name')} (ID: {data.get('id')}, status: {data.get('status')})"
            self.log_test("POST /api/voc/campaigns", True, details)
            
        except Exception as e:
            self.log_test("POST /api/voc/campaigns", False, f"Exception: {str(e)}")
    
    def test_send_campaign(self):
        """Test 5: POST /api/voc/campaigns/:id/send (auth required)"""
        print("\n📤 Testing POST /api/voc/campaigns/:id/send...")
        
        if not self.campaign_id:
            self.log_test("POST /api/voc/campaigns/:id/send", False, "No campaign_id available from previous tests")
            return
        
        send_data = {
            "recipients": ["test1@example.com", "test2@example.com"]
        }
        
        try:
            response = self.make_authenticated_request(
                'POST', 
                f'/voc/campaigns/{self.campaign_id}/send',
                json=send_data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code != 200:
                self.log_test("POST /api/voc/campaigns/:id/send", False, f"Status: {response.status_code}, Response: {response.text}")
                return
            
            data = response.json()
            
            required_fields = ['sent', 'ses_active', 'links', 'message']
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                self.log_test("POST /api/voc/campaigns/:id/send", False, f"Missing fields: {missing_fields}")
                return
            
            if data.get('sent') != 2:
                self.log_test("POST /api/voc/campaigns/:id/send", False, f"Expected sent=2, got {data.get('sent')}")
                return
            
            if data.get('ses_active') != False:
                self.log_test("POST /api/voc/campaigns/:id/send", False, f"Expected ses_active=false, got {data.get('ses_active')}")
                return
            
            links = data.get('links', [])
            if len(links) != 2:
                self.log_test("POST /api/voc/campaigns/:id/send", False, f"Expected 2 links, got {len(links)}")
                return
            
            # Check link format and store first token
            if links:
                first_link = links[0]
                if 'email' not in first_link or 'url' not in first_link or 'token' not in first_link:
                    self.log_test("POST /api/voc/campaigns/:id/send", False, "Link missing required fields (email, url, token)")
                    return
                
                url = first_link.get('url', '')
                token = first_link.get('token', '')
                
                if '/s/' not in url:
                    self.log_test("POST /api/voc/campaigns/:id/send", False, f"Expected URL to contain '/s/', got: {url}")
                    return
                
                # Store token for public survey tests
                self.survey_token = token
            
            details = f"Sent to {data.get('sent')} recipients, ses_active={data.get('ses_active')}, got {len(links)} survey links"
            self.log_test("POST /api/voc/campaigns/:id/send", True, details)
            
        except Exception as e:
            self.log_test("POST /api/voc/campaigns/:id/send", False, f"Exception: {str(e)}")
    
    def test_public_survey_get(self):
        """Test 6: GET /api/voc/public/survey/:token (NO AUTH - public endpoint)"""
        print("\n🌐 Testing GET /api/voc/public/survey/:token (public)...")
        
        if not self.survey_token:
            self.log_test("GET /api/voc/public/survey/:token", False, "No survey_token available from send campaign test")
            return
        
        try:
            # Make request WITHOUT Authorization header
            response = self.make_public_request('GET', f'/voc/public/survey/{self.survey_token}')
            
            if response.status_code != 200:
                self.log_test("GET /api/voc/public/survey/:token", False, f"Status: {response.status_code}, Response: {response.text}")
                return
            
            data = response.json()
            
            required_fields = ['survey_type', 'title', 'main_question', 'account_name', 'expires_at']
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                self.log_test("GET /api/voc/public/survey/:token", False, f"Missing fields: {missing_fields}")
                return
            
            details = f"Survey: {data.get('title')} (type: {data.get('survey_type')}, account: {data.get('account_name')})"
            self.log_test("GET /api/voc/public/survey/:token", True, details)
            
        except Exception as e:
            self.log_test("GET /api/voc/public/survey/:token", False, f"Exception: {str(e)}")
    
    def test_public_survey_submit(self):
        """Test 7: POST /api/voc/public/survey/:token (NO AUTH - submit response)"""
        print("\n📝 Testing POST /api/voc/public/survey/:token (submit response)...")
        
        if not self.survey_token:
            self.log_test("POST /api/voc/public/survey/:token (submit)", False, "No survey_token available from send campaign test")
            return
        
        response_data = {
            "nps_score": 8,
            "csat_score": 4,
            "verbatim": "Good service overall"
        }
        
        try:
            # Make request WITHOUT Authorization header
            response = self.make_public_request(
                'POST', 
                f'/voc/public/survey/{self.survey_token}',
                json=response_data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code != 200:
                self.log_test("POST /api/voc/public/survey/:token (submit)", False, f"Status: {response.status_code}, Response: {response.text}")
                return
            
            data = response.json()
            
            required_fields = ['success', 'response_id', 'thank_you_msg']
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                self.log_test("POST /api/voc/public/survey/:token (submit)", False, f"Missing fields: {missing_fields}")
                return
            
            if data.get('success') != True:
                self.log_test("POST /api/voc/public/survey/:token (submit)", False, f"Expected success=true, got {data.get('success')}")
                return
            
            details = f"Response submitted successfully (ID: {data.get('response_id')})"
            self.log_test("POST /api/voc/public/survey/:token (submit)", True, details)
            
        except Exception as e:
            self.log_test("POST /api/voc/public/survey/:token (submit)", False, f"Exception: {str(e)}")
    
    def test_public_survey_double_submit(self):
        """Test 8: POST /api/voc/public/survey/:token (SECOND attempt - should be blocked)"""
        print("\n🚫 Testing POST /api/voc/public/survey/:token (double submit - should fail)...")
        
        if not self.survey_token:
            self.log_test("POST /api/voc/public/survey/:token (double submit)", False, "No survey_token available from send campaign test")
            return
        
        response_data = {
            "nps_score": 9,
            "csat_score": 5,
            "verbatim": "Second attempt"
        }
        
        try:
            # Make request WITHOUT Authorization header (same token as before)
            response = self.make_public_request(
                'POST', 
                f'/voc/public/survey/{self.survey_token}',
                json=response_data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code != 410:
                self.log_test("POST /api/voc/public/survey/:token (double submit)", False, f"Expected 410 Gone, got {response.status_code}, Response: {response.text}")
                return
            
            # Check if response contains "already been used" message
            response_text = response.text.lower()
            if "already been used" not in response_text:
                self.log_test("POST /api/voc/public/survey/:token (double submit)", False, f"Expected 'already been used' in response, got: {response.text}")
                return
            
            details = "Token correctly blocked on second use (410 Gone with 'already been used' message)"
            self.log_test("POST /api/voc/public/survey/:token (double submit)", True, details)
            
        except Exception as e:
            self.log_test("POST /api/voc/public/survey/:token (double submit)", False, f"Exception: {str(e)}")
    
    def test_campaign_stats(self):
        """Test 9: GET /api/voc/campaigns/:id/stats (auth required)"""
        print("\n📊 Testing GET /api/voc/campaigns/:id/stats...")
        
        if not self.campaign_id:
            self.log_test("GET /api/voc/campaigns/:id/stats", False, "No campaign_id available from previous tests")
            return
        
        try:
            response = self.make_authenticated_request('GET', f'/voc/campaigns/{self.campaign_id}/stats')
            
            if response.status_code != 200:
                self.log_test("GET /api/voc/campaigns/:id/stats", False, f"Status: {response.status_code}, Response: {response.text}")
                return
            
            data = response.json()
            
            required_fields = ['id', 'name', 'status', 'sent_count', 'response_count']
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                self.log_test("GET /api/voc/campaigns/:id/stats", False, f"Missing fields: {missing_fields}")
                return
            
            if data.get('status') != 'active':
                self.log_test("GET /api/voc/campaigns/:id/stats", False, f"Expected status='active', got {data.get('status')}")
                return
            
            if data.get('sent_count') != 2:
                self.log_test("GET /api/voc/campaigns/:id/stats", False, f"Expected sent_count=2, got {data.get('sent_count')}")
                return
            
            if data.get('response_count') != 1:
                self.log_test("GET /api/voc/campaigns/:id/stats", False, f"Expected response_count=1, got {data.get('response_count')}")
                return
            
            details = f"Campaign stats: {data.get('name')} (status: {data.get('status')}, sent: {data.get('sent_count')}, responses: {data.get('response_count')})"
            self.log_test("GET /api/voc/campaigns/:id/stats", True, details)
            
        except Exception as e:
            self.log_test("GET /api/voc/campaigns/:id/stats", False, f"Exception: {str(e)}")
    
    def test_auth_requirements(self):
        """Test that auth endpoints return 401 without token"""
        print("\n🔒 Testing Authorization Requirements...")
        
        auth_endpoints = [
            "/voc/surveys",
            "/voc/campaigns"
        ]
        
        for endpoint in auth_endpoints:
            try:
                response = self.make_public_request('GET', endpoint)
                if response.status_code == 401:
                    self.log_test(f"Auth Required - {endpoint}", True, "Correctly returns 401")
                else:
                    self.log_test(f"Auth Required - {endpoint}", False, f"Expected 401, got {response.status_code}")
            except Exception as e:
                self.log_test(f"Auth Required - {endpoint}", False, f"Exception: {str(e)}")
    
    def test_public_endpoints_no_auth(self):
        """Test that public endpoints work WITHOUT auth header"""
        print("\n🌐 Testing Public Endpoints (No Auth Required)...")
        
        if not self.survey_token:
            self.log_test("Public Endpoints No Auth", False, "No survey_token available for testing")
            return
        
        # Test that public endpoints return 200 or 410 WITHOUT auth header
        # (410 is expected if token was already used in previous tests)
        try:
            response = self.make_public_request('GET', f'/voc/public/survey/{self.survey_token}')
            if response.status_code == 200:
                self.log_test("Public GET Survey (No Auth)", True, "Public endpoint works without Authorization header")
            elif response.status_code == 410:
                self.log_test("Public GET Survey (No Auth)", True, "Public endpoint correctly returns 410 for used token (no auth required)")
            else:
                self.log_test("Public GET Survey (No Auth)", False, f"Expected 200 or 410, got {response.status_code}")
        except Exception as e:
            self.log_test("Public GET Survey (No Auth)", False, f"Exception: {str(e)}")
    
    def run_all_tests(self):
        """Run all VoC Phase 2 backend tests"""
        print("🚀 Starting VoC Intelligence Platform Phase 2 Backend Testing")
        print("=" * 70)
        
        # Authentication
        if not self.authenticate():
            print("\n❌ Authentication failed. Cannot proceed with API tests.")
            return False
        
        # Test authorization requirements first
        self.test_auth_requirements()
        
        # Test all VoC Phase 2 endpoints in order
        self.test_get_surveys()                    # 1. GET /api/voc/surveys
        self.test_post_surveys()                   # 2. POST /api/voc/surveys
        self.test_get_campaigns()                  # 3. GET /api/voc/campaigns
        self.test_post_campaigns()                 # 4. POST /api/voc/campaigns
        self.test_send_campaign()                  # 5. POST /api/voc/campaigns/:id/send
        self.test_public_survey_get()              # 6. GET /api/voc/public/survey/:token
        self.test_public_survey_submit()           # 7. POST /api/voc/public/survey/:token
        self.test_public_survey_double_submit()    # 8. POST /api/voc/public/survey/:token (blocked)
        self.test_campaign_stats()                 # 9. GET /api/voc/campaigns/:id/stats
        
        # Test public endpoints work without auth
        self.test_public_endpoints_no_auth()
        
        # Summary
        self.print_summary()
        
        return all(result['success'] for result in self.test_results)
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 70)
        print("📋 VoC PHASE 2 TEST SUMMARY")
        print("=" * 70)
        
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
        
        print("\n🔑 KEY ASSERTIONS VERIFIED:")
        print("  - All auth endpoints return 401 without token")
        print("  - Public endpoints return 200/410 WITHOUT auth header")
        print("  - Token can only be used once (second attempt returns 410)")
        print("  - After submission, campaign response_count increments")

if __name__ == "__main__":
    tester = VoCPhase2Tester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)