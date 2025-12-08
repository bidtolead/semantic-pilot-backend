#!/usr/bin/env python3
"""
Cleanup script to retroactively enforce 20-report limit for all users.
Calls the admin endpoint to delete oldest reports beyond 20 per user.

Usage:
    python3 cleanup_report_history.py
"""

import os
import sys
import asyncio
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def cleanup_report_history():
    """Call the admin cleanup endpoint to enforce 20-report limit for all users."""
    
    # Get backend URL
    backend_url = os.getenv("NEXT_PUBLIC_BACKEND_URL") or os.getenv("NEXT_PUBLIC_API_URL") or "https://semantic-pilot-backend.onrender.com"
    cleanup_endpoint = f"{backend_url}/admin/cleanup/enforce-history-limit"
    
    print(f"📋 Cleanup Report History Limit")
    print(f"================================")
    print(f"Endpoint: {cleanup_endpoint}")
    print()
    
    # Note: This script requires a valid admin Firebase ID token
    # You can either:
    # 1. Pass token via environment variable: ADMIN_TOKEN
    # 2. Or manually call the endpoint with an admin token
    
    admin_token = os.getenv("ADMIN_TOKEN")
    
    if not admin_token:
        print("⚠️  No ADMIN_TOKEN environment variable found.")
        print()
        print("To run this cleanup, you need to:")
        print("1. Get a Firebase ID token for an admin user")
        print("2. Set it as ADMIN_TOKEN environment variable")
        print("3. Run: ADMIN_TOKEN='your_token_here' python3 cleanup_report_history.py")
        print()
        print("Or, you can call the endpoint directly:")
        print(f"  curl -X POST {cleanup_endpoint} \\")
        print("    -H 'Authorization: Bearer YOUR_ADMIN_TOKEN'")
        return
    
    try:
        print("🔄 Calling cleanup endpoint...")
        response = requests.post(
            cleanup_endpoint,
            headers={
                "Authorization": f"Bearer {admin_token}",
                "Content-Type": "application/json"
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Cleanup successful!")
            print(f"   - Users processed: {result.get('users_processed', 0)}")
            print(f"   - Reports deleted: {result.get('reports_deleted', 0)}")
            print(f"   - Message: {result.get('message', '')}")
        else:
            print(f"❌ Cleanup failed with status {response.status_code}")
            print(f"   Error: {response.text}")
            sys.exit(1)
    
    except Exception as e:
        print(f"❌ Error calling cleanup endpoint: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(cleanup_report_history())
