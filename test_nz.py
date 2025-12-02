import os, sys, json, base64, requests

login = "contact@bidtolead.com"
password = "25a5cd2ca93fe3a4"
token = base64.b64encode(f"{login}:{password}".encode()).decode()
headers = {"Authorization": f"Basic {token}", "Content-Type": "application/json"}

# Test different location formats
tests = [
    "New Zealand",
    "Auckland,New Zealand", 
    "Auckland,Auckland,New Zealand"
]

for loc in tests:
    print(f"\n{'='*80}")
    print(f"Testing location: {loc}")
    print('='*80)
    
    payload = [{
        "keywords": ["seo course"],
        "location_name": loc,
        "language_name": "English",
        "search_partners": False,
    }]
    
    resp = requests.post(
        "https://api.dataforseo.com/v3/keywords_data/google_ads/keywords_for_keywords/live",
        json=payload, headers=headers, timeout=120
    )
    
    data = resp.json()
    if data.get("tasks") and data["tasks"][0].get("result"):
        items = data["tasks"][0]["result"][0].get("items", [])[:3]
        for item in items:
            print(f"\nKeyword: {item.get('keyword')}")
            print(f"  search_volume: {item.get('search_volume')}")
            print(f"  competition: {item.get('competition')}")
            print(f"  competition_index: {item.get('competition_index')}")
            print(f"  low_bid: {item.get('low_top_of_page_bid')}")
            print(f"  high_bid: {item.get('high_top_of_page_bid')}")
