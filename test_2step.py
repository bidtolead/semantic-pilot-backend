#!/usr/bin/env python3
"""Test the 2-step DataForSEO process to see actual data"""
import base64, requests, json

login = "contact@bidtolead.com"
password = "25a5cd2ca93fe3a4"
token = base64.b64encode(f"{login}:{password}".encode()).decode()
headers = {"Authorization": f"Basic {token}", "Content-Type": "application/json"}

print("="*80)
print("STEP 1: Get keyword suggestions from keywords_for_keywords")
print("="*80)

# Step 1: Get keyword suggestions
payload1 = [{
    "keywords": ["seo course"],
    "location_name": "Auckland,Auckland,New Zealand",
    "language_name": "English",
    "search_partners": False,
}]

resp1 = requests.post(
    "https://api.dataforseo.com/v3/keywords_data/google_ads/keywords_for_keywords/live",
    json=payload1, headers=headers, timeout=120
)

data1 = resp1.json()
if data1.get("tasks") and data1["tasks"][0].get("result"):
    items = data1["tasks"][0]["result"][0].get("items", [])[:200]
    keyword_list = [it.get("keyword") for it in items if it.get("keyword")]
    
    print(f"\nGot {len(keyword_list)} keyword suggestions")
    print(f"First 5 keywords: {keyword_list[:5]}")
    print(f"\nSample data from Step 1 (first keyword):")
    print(json.dumps(items[0], indent=2))
    
    print("\n" + "="*80)
    print("STEP 2: Get full metrics from search_volume endpoint")
    print("="*80)
    
    # Step 2: Get full metrics for those keywords
    payload2 = [{
        "keywords": keyword_list[:5],  # Test with first 5 keywords
        "location_name": "Auckland,Auckland,New Zealand",
        "language_name": "English",
        "search_partners": False,
    }]
    
    resp2 = requests.post(
        "https://api.dataforseo.com/v3/keywords_data/google_ads/search_volume/live",
        json=payload2, headers=headers, timeout=120
    )
    
    data2 = resp2.json()
    
    print(f"\nFull API response from search_volume:")
    print(json.dumps(data2, indent=2))
    
    print("\n" + "="*80)
    print("FORMATTED OUTPUT (what users will see)")
    print("="*80)
    
    if data2.get("tasks") and data2["tasks"][0].get("result"):
        items2 = data2["tasks"][0]["result"][0].get("items", [])
        for item in items2:
            print(f"\nKeyword: {item.get('keyword')}")
            print(f"  Search Volume: {item.get('search_volume')}")
            print(f"  Competition: {item.get('competition')}")
            print(f"  Competition Index: {item.get('competition_index')}")
            print(f"  Low Bid: ${item.get('low_top_of_page_bid')}")
            print(f"  High Bid: ${item.get('high_top_of_page_bid')}")
            print(f"  CPC: ${item.get('cpc')}")
            
            monthly = item.get('monthly_searches', [])
            if monthly and len(monthly) >= 12:
                current = monthly[0].get('search_volume')
                year_ago = monthly[11].get('search_volume')
                if current and year_ago and year_ago > 0:
                    yoy = round(((current - year_ago) / year_ago) * 100, 1)
                    print(f"  YoY Change: {yoy}%")
                print(f"  Monthly data points: {len(monthly)}")
else:
    print("No results from Step 1")
