#!/usr/bin/env python3
"""Test middleware execution"""
import asyncio
import httpx
import sys

async def test_middleware():
    """Test if middleware is executing"""
    base_url = "http://localhost:6100"
    
    # Test customer search endpoint with Zendesk subdomain header
    headers = {
        "X-Zendesk-Subdomain": "hllhome",
        "X-Zendesk-Token": "test-token"
    }
    
    print("Testing /api/customers/search endpoint...")
    print(f"Headers: {headers}")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{base_url}/api/customers/search",
                params={"email": "test@example.com"},
                headers=headers
            )
            
            print(f"Status: {response.status_code}")
            print(f"Response: {response.json()}")
            
        except Exception as e:
            print(f"Error: {e}")
            
    # Also test tenant config endpoint
    print("\n\nTesting /api/tenants/config/hllhome endpoint...")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{base_url}/api/tenants/config/hllhome"
            )
            
            print(f"Status: {response.status_code}")
            print(f"Response: {response.json()}")
            
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_middleware())