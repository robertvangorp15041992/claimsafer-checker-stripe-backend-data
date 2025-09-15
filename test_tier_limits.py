#!/usr/bin/env python3
"""
Test script for ClaimSafer tier-based limits
Tests all subscription tiers: free, early_essentials, pro, enterprise
"""
import requests
import json
import time
import sys
import urllib.parse

def test_endpoint(url, method='GET', data=None, headers=None, cookies=None):
    """Test an endpoint and return response"""
    try:
        if method == 'GET':
            response = requests.get(url, timeout=10, cookies=cookies)
        elif method == 'POST':
            if headers and headers.get('Content-Type') == 'application/x-www-form-urlencoded':
                # Encode data for form-urlencoded
                encoded_data = urllib.parse.urlencode(data)
                response = requests.post(url, data=encoded_data, headers=headers, cookies=cookies, timeout=10)
            else:
                response = requests.post(url, json=data, headers=headers, cookies=cookies, timeout=10)
        else:
            return None, f"Unsupported method: {method}"
        
        return response, None
    except Exception as e:
        return None, str(e)

def test_tier_limits():
    base_url = "http://localhost:8000"
    
    print("🧪 ClaimSafer™ Tier Limits Test")
    print("============================================================")
    
    # Test users for each tier
    test_users = [
        {"email": "test@claimsafer.com", "password": "testpassword123", "tier": "free"},
        {"email": "early@claimsafer.com", "password": "earlypassword123", "tier": "early_essentials"},
        {"email": "pro@claimsafer.com", "password": "propassword123", "tier": "pro"},
        {"email": "enterprise@claimsafer.com", "password": "enterprisepassword123", "tier": "enterprise"}
    ]
    
    for user_info in test_users:
        print(f"\n🔍 Testing {user_info['tier'].upper()} tier user")
        print("-" * 50)
        
        # Login
        login_data = {"email": user_info["email"], "password": user_info["password"]}
        response, error = test_endpoint(f"{base_url}/auth/login", method='POST', data=login_data)
        
        if error:
            print(f"❌ Login failed: {error}")
            continue
        
        if response.status_code != 200:
            print(f"❌ Login failed with status {response.status_code}")
            continue
        
        login_result = response.json()
        if not login_result.get('success'):
            print(f"❌ Login failed: {login_result.get('message')}")
            continue
        
        print(f"✅ Logged in as {user_info['tier']} user")
        cookies = response.cookies
        
        # Test usage stats
        print(f"\n📊 Usage stats for {user_info['tier']} user:")
        response, error = test_endpoint(f"{base_url}/auth/usage", cookies=cookies)
        if not error and response.status_code == 200:
            usage = response.json()
            print(f"   Subscription: {usage.get('subscription_tier')}")
            print(f"   Search Count: {usage.get('search_count', 0)}")
            print(f"   Remaining: {usage.get('remaining_searches', 'N/A')}")
        
        # Test ingredient search (tests variation limits)
        print(f"\n🔍 Testing ingredient search for {user_info['tier']} user:")
        search_data = {"ingredient": "Vitamin C", "country": "Germany"}
        response, error = test_endpoint(f"{base_url}/search-by-ingredient", method='POST', 
                                      data=search_data, cookies=cookies, 
                                      headers={'Content-Type': 'application/x-www-form-urlencoded'})
        
        if error:
            print(f"❌ Search failed: {error}")
        elif response.status_code == 200:
            print(f"✅ Search successful (status: {response.status_code})")
            # Count variations in response
            html_content = response.text
            variation_count = html_content.count('View Variations')
            print(f"   Variations available: {variation_count}")
        else:
            print(f"❌ Search failed with status {response.status_code}")
            if response.text:
                print(f"   Response: {response.text[:200]}...")
        
        # Test claim search (tests ingredient limits)
        print(f"\n🔍 Testing claim search for {user_info['tier']} user:")
        search_data = {"claim": "immune system", "country": "Germany"}
        response, error = test_endpoint(f"{base_url}/search-by-claim", method='POST', 
                                      data=search_data, cookies=cookies, 
                                      headers={'Content-Type': 'application/x-www-form-urlencoded'})
        
        if error:
            print(f"❌ Claim search failed: {error}")
        elif response.status_code == 200:
            print(f"✅ Claim search successful (status: {response.status_code})")
            # Count ingredients in response
            html_content = response.text
            ingredient_count = html_content.count('class="font-semibold text-lg"')
            print(f"   Ingredients shown: {ingredient_count}")
        else:
            print(f"❌ Claim search failed with status {response.status_code}")
            if response.text:
                print(f"   Response: {response.text[:200]}...")
        
        # Test variations endpoint directly
        print(f"\n🔍 Testing variations endpoint for {user_info['tier']} user:")
        response, error = test_endpoint(f"{base_url}/get-variations?claim=Contributes to the immune system", cookies=cookies)
        
        if error:
            print(f"❌ Variations failed: {error}")
        elif response.status_code == 200:
            variations_data = response.json()
            variations = variations_data.get('variations', [])
            print(f"✅ Variations retrieved: {len(variations)} variations")
            if variations:
                print(f"   Sample: {variations[0][:50]}...")
        else:
            print(f"❌ Variations failed with status {response.status_code}")
        
        # Test search limits for free tier
        if user_info['tier'] == 'free':
            print(f"\n🔍 Testing free tier search limits:")
            for i in range(5):  # Try 5 searches
                search_data = {"ingredient": f"Test Ingredient {i+1}", "country": "Germany"}
                response, error = test_endpoint(f"{base_url}/search-by-ingredient", method='POST', 
                                              data=search_data, cookies=cookies, 
                                              headers={'Content-Type': 'application/x-www-form-urlencoded'})
                
                if response.status_code == 200:
                    print(f"   Search {i+1}: ✅ Allowed")
                else:
                    print(f"   Search {i+1}: ❌ Blocked (status: {response.status_code})")
                    if i >= 2:  # Should be blocked after 3 searches
                        print(f"   ✅ Correctly blocked after 3 searches")
                    break
        
        print(f"\n✅ Completed testing for {user_info['tier']} user")
    
    print("\n🎉 All tier limit tests completed!")
    print("\n📊 Expected Results Summary:")
    print("   FREE: 3 searches/week, 0 variations, unlimited ingredients")
    print("   EARLY ESSENTIALS: Unlimited searches, 3 variations, 50 ingredients max")
    print("   PRO: 150 searches/month, 10 variations, unlimited ingredients")
    print("   ENTERPRISE: Unlimited searches, 20+ variations, unlimited ingredients")

if __name__ == "__main__":
    test_tier_limits()
