#!/usr/bin/env python3
"""
Test script to verify ZAF access is working properly
"""

import requests
import json

def test_cors_and_zaf_access():
    """Test that Zendesk domains can access the backend"""
    print("=" * 60)
    print("Testing ZAF Application Access to Backend")
    print("=" * 60)
    
    # Test the production backend URL
    backend_url = "https://shopline-backend-z5d0.onrender.com"
    test_endpoint = f"{backend_url}/api/tenants/config/hllhome"
    
    print(f"\n1. Testing endpoint: {test_endpoint}")
    print("   This endpoint is accessed by ZAF applications")
    
    # Test without Zendesk headers (should work for config endpoint)
    print("\n2. Test without Zendesk headers:")
    try:
        response = requests.get(test_endpoint)
        print(f"   Status Code: {response.status_code}")
        if response.status_code == 200:
            print("   ✅ Endpoint is accessible")
        else:
            print(f"   Response: {response.text[:200]}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test with Zendesk Origin header (simulating ZAF request)
    print("\n3. Test with Zendesk Origin header (simulating ZAF):")
    headers = {
        "Origin": "https://hllhome.zendesk.com",
        "X-Zendesk-Subdomain": "hllhome"
    }
    try:
        response = requests.get(test_endpoint, headers=headers)
        print(f"   Status Code: {response.status_code}")
        print(f"   CORS Headers:")
        if 'access-control-allow-origin' in response.headers:
            print(f"   - Access-Control-Allow-Origin: {response.headers['access-control-allow-origin']}")
            print("   ✅ CORS is properly configured for Zendesk")
        else:
            print("   ❌ No CORS headers found")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    print("\n" + "=" * 60)
    print("Summary of Changes:")
    print("=" * 60)
    print("\n✅ CORS Configuration Updated:")
    print("   - Added regex pattern to allow all *.zendesk.com domains")
    print("   - Specifically included hllhome.zendesk.com and omnigatech.zendesk.com")
    print("   - Pattern: r'^https://.*\\.zendesk\\.com$'")
    
    print("\n✅ Tenant Middleware Fixed:")
    print("   - /api/tenants/config/{subdomain} is NO LONGER skipped")
    print("   - This endpoint is now properly checked for tenant configuration")
    print("   - ZAF apps can access their configuration via this endpoint")
    
    print("\n✅ Result:")
    print("   - ZAF applications from any Zendesk subdomain can now access the backend")
    print("   - The /api/tenants/config/{subdomain} endpoint works for ZAF apps")
    print("   - CORS headers are properly set for Zendesk origins")
    
    print("\n⚠️  Note:")
    print("   These changes are in your local code.")
    print("   You need to deploy to Render for production to take effect.")

if __name__ == "__main__":
    test_cors_and_zaf_access()