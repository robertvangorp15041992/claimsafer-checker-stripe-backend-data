#!/usr/bin/env python3
"""
Test script for ClaimSafer authentication system
"""
import requests
import json
import time
import sys

def test_endpoint(url, method='GET', data=None, headers=None):
    """Test an endpoint and return response"""
    try:
        if method == 'GET':
            response = requests.get(url, timeout=10)
        elif method == 'POST':
            response = requests.post(url, json=data, headers=headers, timeout=10)
        else:
            return None, f"Unsupported method: {method}"
        
        return response, None
    except Exception as e:
        return None, str(e)

def main():
    base_url = "http://localhost:8000"
    
    print("🧪 Testing ClaimSafer™ Authentication System")
    print("=" * 50)
    
    # Test 1: Health Check
    print("\n1️⃣ Testing Health Endpoint")
    response, error = test_endpoint(f"{base_url}/health")
    if error:
        print(f"❌ Health check failed: {error}")
        return
    print(f"✅ Health check: {response.status_code}")
    print(f"   Response: {response.json()}")
    
    # Test 2: Login Page
    print("\n2️⃣ Testing Login Page")
    response, error = test_endpoint(f"{base_url}/login")
    if error:
        print(f"❌ Login page failed: {error}")
        return
    print(f"✅ Login page: {response.status_code}")
    print(f"   Contains ClaimSafer: {'ClaimSafer' in response.text}")
    
    # Test 3: Auth Check (Not Authenticated)
    print("\n3️⃣ Testing Auth Check (Not Authenticated)")
    response, error = test_endpoint(f"{base_url}/auth/check")
    if error:
        print(f"❌ Auth check failed: {error}")
        return
    print(f"✅ Auth check: {response.status_code}")
    print(f"   Response: {response.json()}")
    
    # Test 4: Login with Invalid Credentials
    print("\n4️⃣ Testing Login with Invalid Credentials")
    login_data = {"email": "test@example.com", "password": "wrongpassword"}
    response, error = test_endpoint(f"{base_url}/auth/login", method='POST', data=login_data)
    if error:
        print(f"❌ Login test failed: {error}")
        return
    print(f"✅ Login test: {response.status_code}")
    print(f"   Response: {response.json()}")
    
    # Test 5: Protected Route (Should Fail)
    print("\n5️⃣ Testing Protected Route (Should Fail)")
    response, error = test_endpoint(f"{base_url}/search-by-ingredient", method='POST', 
                                  data={"ingredient": "Vitamin C", "country": "Germany"})
    if error:
        print(f"❌ Protected route test failed: {error}")
        return
    print(f"✅ Protected route test: {response.status_code}")
    if response.status_code == 401:
        print("   ✅ Correctly blocked unauthorized access")
    else:
        print(f"   Response: {response.text[:200]}...")
    
    print("\n🎉 All basic tests completed!")
    print("\n📝 Next Steps:")
    print("   1. Create a test user in the database")
    print("   2. Test login with valid credentials")
    print("   3. Test protected routes with authentication")
    print("   4. Test usage tracking and limits")

if __name__ == "__main__":
    main()
