#!/usr/bin/env python3
import requests
import json
import re
import subprocess

BASE_URL = "https://docker-start-demo.preview.emergentagent.com/api"
ADMIN_EMAIL = "admin@hitachi-systems.com"
ADMIN_PASSWORD = "Admin@123"

def get_otp_from_logs():
    try:
        result = subprocess.run(
            ['tail', '-n', '100', '/var/log/supervisor/backend.err.log'],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            otp_pattern = r'OTP.*?(\d{6})'
            matches = re.findall(otp_pattern, result.stdout)
            if matches:
                return matches[-1]
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

session = requests.Session()
session.headers.update({'Content-Type': 'application/json'})

# Login
login_data = {"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
response = session.post(f"{BASE_URL}/auth/login", json=login_data)
print(f"Login response: {response.status_code} - {response.text}")

if response.status_code == 200:
    otp = get_otp_from_logs()
    if otp:
        print(f"Found OTP: {otp}")
        otp_data = {"email": ADMIN_EMAIL, "code": otp, "purpose": "login"}
        response = session.post(f"{BASE_URL}/auth/verify-otp", json=otp_data)
        print(f"OTP response: {response.status_code} - {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            token = result.get('access_token')
            session.headers.update({'Authorization': f'Bearer {token}'})
            
            # Test leaderboard
            response = session.get(f"{BASE_URL}/dashboard/leaderboard")
            print(f"Leaderboard response: {response.status_code}")
            print(f"Leaderboard data type: {type(response.json())}")
            print(f"Leaderboard data: {response.json()}")