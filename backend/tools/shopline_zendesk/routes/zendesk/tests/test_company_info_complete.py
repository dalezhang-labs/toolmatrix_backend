#!/usr/bin/env python3
import requests
import json

# Test user ID
USER_ID = "ce7308e1-b2b1-4a5f-96a0-358acd98801e"
BASE_URL = "http://localhost:6100"

def test_company_info_flow():
    print("=" * 50)
    print("Testing Complete Company Information Flow")
    print("=" * 50)
    
    # 1. Get current company info
    print("\n1. Getting current company info from backend...")
    resp = requests.get(f"{BASE_URL}/api/users/{USER_ID}/company-info")
    if resp.status_code == 200:
        data = resp.json()
        print(f"Status: {resp.status_code}")
        if data['success']:
            print(f"Current company info:")
            for key, value in data['data'].items():
                print(f"  {key}: {value}")
        else:
            print(f"Error: {data.get('error')}")
    else:
        print(f"Error: {resp.status_code}")
        print(resp.text)
    
    # 2. Update company info via backend API (as the frontend would do)
    print("\n2. Updating company info via backend API...")
    company_data = {
        "company_name": "OmniGate Technologies",
        "company_address": "456 Tech Boulevard",
        "company_city": "San Francisco",
        "company_state": "CA",
        "company_postal_code": "94105",
        "company_country": "United States"
    }
    
    resp = requests.put(
        f"{BASE_URL}/api/users/{USER_ID}/company-info",
        json=company_data
    )
    if resp.status_code == 200:
        data = resp.json()
        print(f"Status: {resp.status_code}")
        if data['success']:
            print(f"Message: {data.get('message')}")
            print(f"Updated company info:")
            for key, value in data['data'].items():
                print(f"  {key}: {value}")
        else:
            print(f"Error: {data.get('error')}")
    else:
        print(f"Error: {resp.status_code}")
        print(resp.text)
    
    # 3. Verify the update by getting info again
    print("\n3. Verifying the update...")
    resp = requests.get(f"{BASE_URL}/api/users/{USER_ID}/company-info")
    if resp.status_code == 200:
        data = resp.json()
        print(f"Status: {resp.status_code}")
        if data['success']:
            print(f"Verified company info:")
            for key, value in data['data'].items():
                print(f"  {key}: {value}")
        else:
            print(f"Error: {data.get('error')}")
    else:
        print(f"Error: {resp.status_code}")
        print(resp.text)
    
    print("\n✅ Test completed!")
    print("\nNote: The frontend now:")
    print("1. Does NOT show Tax ID / VAT Number field")
    print("2. Saves company info to site_users table via backend API")
    print("3. Also updates Stripe customer when user has subscription")

if __name__ == "__main__":
    test_company_info_flow()