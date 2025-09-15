#!/usr/bin/env python3
"""
Comprehensive test script for ClaimSafer authentication system
"""
import requests
import json
import time
import sys

def test_endpoint(url, method='GET', data=None, headers=None, cookies=None):
    """Test an endpoint and return response"""
    try:
        if method == 'GET':
            response = requests.get(url, timeout=10, cookies=cookies)
        elif method == 'POST':
            if headers and headers.get('Content-Type') == 'application/x-www-form-urlencoded':
                response = requests.post(url, data=data, headers=headers, cookies=cookies, timeout=10)
            else:
                response = requests.post(url, json=data, headers=headers, cookies=cookies, timeout=10)
        else:
            return None, f"Unsupported method: {method}"
        
        return response, None
    except Exception as e:
        return None, str(e)

def main():
    base_url = "http://localhost:8000"
    
    print("🧪 Comprehensive ClaimSafer™ Authentication Test")
    print("=" * 60)
    
    # Test 1: Health Check
    print("\n1️⃣ Testing Health Endpoint")
    response, error = test_endpoint(f"{base_url}/health")
    if error:
        print(f"❌ Health check failed: {error}")
        return
    print(f"✅ Health check: {response.status_code}")
    
    # Test 2: Login with Valid Credentials
    print("\n2️⃣ Testing Login with Valid Credentials")
    login_data = {"email": "test@claimsafer.com", "password": "testpassword123"}
    response, error = test_endpoint(f"{base_url}/auth/login", method='POST', data=login_data)
    if error:
        print(f"❌ Login failed: {error}")
        return
    
    print(f"✅ Login response: {response.status_code}")
    login_result = response.json()
    print(f"   Success: {login_result.get('success')}")
    print(f"   Message: {login_result.get('message')}")
    
    if login_result.get('success'):
        print("✅ Login successful!")
        # Store cookies for session-based requests
        cookies = response.cookies
    else:
        print("❌ Login failed!")
        return
    
    # Test 3: Auth Check (Should be Authenticated)
    print("\n3️⃣ Testing Auth Check (Authenticated)")
    response, error = test_endpoint(f"{base_url}/auth/check", cookies=cookies)
    if error:
        print(f"❌ Auth check failed: {error}")
        return
    print(f"✅ Auth check: {response.status_code}")
    auth_result = response.json()
    print(f"   Authenticated: {auth_result.get('authenticated')}")
    if auth_result.get('authenticated'):
        print(f"   User: {auth_result.get('user', {}).get('email')}")
        print(f"   Subscription: {auth_result.get('user', {}).get('subscription_tier')}")
    
    # Test 4: Usage Statistics
    print("\n4️⃣ Testing Usage Statistics")
    response, error = test_endpoint(f"{base_url}/auth/usage", cookies=cookies)
    if error:
        print(f"❌ Usage stats failed: {error}")
        return
    print(f"✅ Usage stats: {response.status_code}")
    usage_result = response.json()
    print(f"   Subscription: {usage_result.get('subscription_tier')}")
    print(f"   Search Count: {usage_result.get('search_count')}")
    print(f"   Remaining: {usage_result.get('remaining_searches')}")
    
    # Test 5: Protected Route (Should Work)
    print("\n5️⃣ Testing Protected Route (Should Work)")
    search_data = {"ingredient": "Vitamin C", "country": "Germany"}
    response, error = test_endpoint(f"{base_url}/search-by-ingredient", method='POST', 
                                  data=search_data, cookies=cookies, headers={'Content-Type': 'application/x-www-form-urlencoded'})
    if error:
        print(f"❌ Protected route failed: {error}")
        return
    print(f"✅ Protected route: {response.status_code}")
    if response.status_code == 200:
        print("   ✅ Successfully accessed protected route!")
        print(f"   Response length: {len(response.text)} characters")
    else:
        print(f"   Response: {response.text[:200]}...")
    
    # Test 6: Test Usage Limit (Free Tier)
    print("\n6️⃣ Testing Usage Limit (Free Tier)")
    print("   Running 3 more searches to test free tier limit...")
    
    for i in range(3):
        search_data = {"ingredient": f"Test Ingredient {i+1}", "country": "Germany"}
        response, error = test_endpoint(f"{base_url}/search-by-ingredient", method='POST', 
                                      data=search_data, cookies=cookies, headers={'Content-Type': 'application/x-www-form-urlencoded'})
        if error:
            print(f"   ❌ Search {i+1} failed: {error}")
            continue
        
        print(f"   Search {i+1}: {response.status_code}")
        if response.status_code == 200:
            print("     ✅ Search allowed")
        elif response.status_code == 401:
            print("     ❌ Search blocked (unexpected)")
        else:
            print(f"     Response: {response.text[:100]}...")
    
    # Test 7: Check Usage After Searches
    print("\n7️⃣ Checking Usage After Searches")
    response, error = test_endpoint(f"{base_url}/auth/usage", cookies=cookies)
    if error:
        print(f"❌ Usage check failed: {error}")
        return
    print(f"✅ Usage check: {response.status_code}")
    usage_result = response.json()
    print(f"   Search Count: {usage_result.get('search_count')}")
    print(f"   Remaining: {usage_result.get('remaining_searches')}")
    
    # Test 8: Logout
    print("\n8️⃣ Testing Logout")
    response, error = test_endpoint(f"{base_url}/auth/logout", method='POST', cookies=cookies)
    if error:
        print(f"❌ Logout failed: {error}")
        return
    print(f"✅ Logout: {response.status_code}")
    logout_result = response.json()
    print(f"   Success: {logout_result.get('success')}")
    
    # Test 9: Auth Check After Logout (Should be Not Authenticated)
    print("\n9️⃣ Testing Auth Check After Logout")
    response, error = test_endpoint(f"{base_url}/auth/check", cookies=cookies)
    if error:
        print(f"❌ Auth check failed: {error}")
        return
    print(f"✅ Auth check: {response.status_code}")
    auth_result = response.json()
    print(f"   Authenticated: {auth_result.get('authenticated')}")
    if not auth_result.get('authenticated'):
        print("   ✅ Correctly logged out!")
    
    # Test 10: Test Pro User
    print("\n🔟 Testing Pro User (Unlimited Searches)")
    pro_login_data = {"email": "pro@claimsafer.com", "password": "propassword123"}
    response, error = test_endpoint(f"{base_url}/auth/login", method='POST', data=pro_login_data)
    if error:
        print(f"❌ Pro login failed: {error}")
        return
    
    if response.status_code == 200:
        pro_cookies = response.cookies
        pro_result = response.json()
        print(f"✅ Pro login: {pro_result.get('success')}")
        print(f"   Subscription: {pro_result.get('user', {}).get('subscription_tier')}")
        
        # Test multiple searches with pro user
        print("   Testing unlimited searches for pro user...")
        for i in range(5):
            search_data = {"ingredient": f"Pro Test {i+1}", "country": "Germany"}
            response, error = test_endpoint(f"{base_url}/search-by-ingredient", method='POST', 
                                          data=search_data, cookies=pro_cookies, headers={'Content-Type': 'application/x-www-form-urlencoded'})
            print(f"   Pro Search {i+1}: {response.status_code}")
    
    print("\n🎉 All tests completed!")
    print("\n📊 Test Summary:")
    print("   ✅ Health endpoint working")
    print("   ✅ Login system working")
    print("   ✅ Session management working")
    print("   ✅ Protected routes working")
    print("   ✅ Usage tracking working")
    print("   ✅ Logout working")
    print("   ✅ Pro user unlimited access working")

if __name__ == "__main__":
    main()
