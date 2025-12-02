#!/usr/bin/env python3
"""Test DataForSEO API directly to see raw response"""
import os
import sys
import json
import base64
import requests

# Get credentials from environment
login = os.getenv("DATAFORSEO_LOGIN")
password = os.getenv("DATAFORSEO_PASSWORD")

if not login or not password:
    print("ERROR: Set DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD environment variables")
    sys.exit(1)

# Auth header
token = base64.b64encode(f"{login}:{password}".encode()).decode()
headers = {
    "Authorization": f"Basic {token}",
    "Content-Type": "application/json"
}

# Test request - same as what we use in production
url = "https://api.dataforseo.com/v3/keywords_data/google_ads/keywords_for_keywords/live"
payload = [{
    "keywords": ["seo course"],
    "location_name": "Auckland,Auckland,New Zealand",
    "language_name": "English",
    "search_partners": False,
}]

print("🔍 Testing DataForSEO Live API...")
print(f"URL: {url}")
print(f"Payload: {json.dumps(payload, indent=2)}")
print("\n" + "="*80 + "\n")

try:
    resp = requests.post(url, json=payload, headers=headers, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    
    # Print full response
    print("✅ FULL API RESPONSE:")
    print(json.dumps(data, indent=2))
    print("\n" + "="*80 + "\n")
    
    # Extract first keyword
    if data.get("tasks") and data["tasks"][0].get("result"):
        items = data["tasks"][0]["result"][0].get("items", [])
        if items:
            print("📊 FIRST KEYWORD DETAILS:")
            first = items[0]
            print(json.dumps(first, indent=2))
            print("\n" + "="*80 + "\n")
            
            # Show key fields
            print("🔑 KEY FIELDS:")
            print(f"  keyword: {first.get('keyword')}")
            print(f"  search_volume: {first.get('search_volume')}")
            print(f"  competition: {first.get('competition')}")
            print(f"  competition_index: {first.get('competition_index')}")
            print(f"  low_top_of_page_bid: {first.get('low_top_of_page_bid')}")
            print(f"  high_top_of_page_bid: {first.get('high_top_of_page_bid')}")
            print(f"  monthly_searches (count): {len(first.get('monthly_searches', []))}")
            if first.get('monthly_searches'):
                print(f"  monthly_searches[0]: {first['monthly_searches'][0]}")
                print(f"  monthly_searches[-1]: {first['monthly_searches'][-1]}")
        else:
            print("❌ No keywords returned in items array")
    else:
        print("❌ No result in response")
        
except Exception as e:
    print(f"❌ ERROR: {e}")
    sys.exit(1)
