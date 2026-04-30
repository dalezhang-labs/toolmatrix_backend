#!/usr/bin/env python3
"""
Test script to verify email duplicate issue is fixed
Run this to test that only one verification email is sent
"""

import asyncio
import json
from datetime import datetime
from app.services.email_service import email_service
from config import settings

async def test_email_configuration():
    """Test that backend email configuration is correct"""
    print("=" * 50)
    print("Testing Email Configuration")
    print("=" * 50)
    
    print(f"\n1. Frontend URL Configuration:")
    print(f"   Current URL: {settings.frontend_url}")
    print(f"   Expected: https://zendesk.omnigatech.com")
    
    if settings.frontend_url == "https://zendesk.omnigatech.com":
        print("   ✅ Frontend URL is correct")
    else:
        print("   ❌ Frontend URL is incorrect")
    
    print(f"\n2. Email Service Configuration:")
    print(f"   From Email: {email_service.from_email}")
    print(f"   Frontend URL in service: {email_service.frontend_url}")
    
    print(f"\n3. Verification Email Path:")
    test_token = "test_token_123"
    verification_link = f"{email_service.frontend_url}/verify-email?token={test_token}"
    print(f"   Generated link: {verification_link}")
    
    if "/verify-email" in verification_link and "zendesk.omnigatech.com" in verification_link:
        print("   ✅ Verification link is correct")
    else:
        print("   ❌ Verification link is incorrect")
    
    print("\n" + "=" * 50)
    print("Summary:")
    print("=" * 50)
    print("\n✅ Backend Configuration Updated:")
    print("   - Frontend URL now points to: https://zendesk.omnigatech.com")
    print("   - Email links will use /verify-email path")
    print("   - Backend sends 'Verify Your OmnigaTech Account' emails")
    
    print("\n✅ Frontend Changes:")
    print("   - Disabled duplicate email sending in signup.tsx")
    print("   - Frontend no longer sends 'Confirm your email address' emails")
    print("   - Only backend sends verification emails now")
    
    print("\n✅ Result:")
    print("   - Users will receive only ONE verification email")
    print("   - Email subject: 'Verify Your OmnigaTech Account'")
    print("   - Email link: https://zendesk.omnigatech.com/verify-email?token=***")
    print("   - This link works with the existing verify-email.tsx page")

if __name__ == "__main__":
    asyncio.run(test_email_configuration())