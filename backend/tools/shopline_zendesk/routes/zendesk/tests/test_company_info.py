#!/usr/bin/env python3
import requests
import json

# Test user ID
USER_ID = "ce7308e1-b2b1-4a5f-96a0-358acd98801e"
BASE_URL = "http://localhost:6100"

def test_company_info():
    print("=" * 50)
    print("Testing Company Information API")
    print("=" * 50)
    
    # 1. Get current company info (should be empty or null initially)
    print("\n1. Getting current company info...")
    resp = requests.get(f"{BASE_URL}/api/users/{USER_ID}/company-info")
    if resp.status_code == 200:
        data = resp.json()
        print(f"Status: {resp.status_code}")
        print(f"Response: {json.dumps(data, indent=2)}")
    else:
        print(f"Error: {resp.status_code}")
        print(resp.text)
    
    # 2. Update company info
    print("\n2. Updating company info...")
    company_data = {
        "company_name": "Acme Corporation",
        "company_address": "123 Main Street",
        "company_city": "New York",
        "company_state": "NY",
        "company_postal_code": "10001",
        "company_country": "United States"
    }
    
    resp = requests.put(
        f"{BASE_URL}/api/users/{USER_ID}/company-info",
        json=company_data
    )
    if resp.status_code == 200:
        data = resp.json()
        print(f"Status: {resp.status_code}")
        print(f"Response: {json.dumps(data, indent=2)}")
    else:
        print(f"Error: {resp.status_code}")
        print(resp.text)
    
    # 3. Get updated company info
    print("\n3. Getting updated company info...")
    resp = requests.get(f"{BASE_URL}/api/users/{USER_ID}/company-info")
    if resp.status_code == 200:
        data = resp.json()
        print(f"Status: {resp.status_code}")
        print(f"Response: {json.dumps(data, indent=2)}")
    else:
        print(f"Error: {resp.status_code}")
        print(resp.text)
    
    # 4. Partial update (only update company name)
    print("\n4. Partial update - changing company name only...")
    partial_data = {
        "company_name": "Tech Innovations Inc."
    }
    
    resp = requests.put(
        f"{BASE_URL}/api/users/{USER_ID}/company-info",
        json=partial_data
    )
    if resp.status_code == 200:
        data = resp.json()
        print(f"Status: {resp.status_code}")
        print(f"Response: {json.dumps(data, indent=2)}")
    else:
        print(f"Error: {resp.status_code}")
        print(resp.text)
    
    print("\n✅ Test completed!")

if __name__ == "__main__":
    test_company_info()