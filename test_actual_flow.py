"""Test what actually gets saved to Firestore"""
import sys
sys.path.insert(0, '/Users/timur/semantic-pilot/semantic-pilot-backend')

from app.services.dataforseo import fetch_keyword_ideas as dfs_fetch_keyword_ideas
from app.services.keyword_ai_filter import run_keyword_ai_filter
import json

# Step 1: Get raw data from DataForSEO
print("=== STEP 1: DataForSEO Raw Data ===")
raw_keywords = dfs_fetch_keyword_ideas(
    seed_keywords=["seo course"],
    location_name="New Zealand",
)

print(f"Total keywords: {len(raw_keywords)}\n")

# Find "seo course auckland"
target = None
for kw in raw_keywords:
    if "seo course" in kw.get("keyword", "").lower() and "auckland" in kw.get("keyword", "").lower():
        target = kw
        break

if not target:
    # Just use first one
    target = raw_keywords[0] if raw_keywords else {}

print("Sample keyword from raw DataForSEO:")
print(f"  keyword: {target.get('keyword')}")
print(f"  avg_monthly_searches: {target.get('avg_monthly_searches')}")
print(f"  competition: {target.get('competition')}")
print(f"  competition_index: {target.get('competition_index')}")
print(f"  low_top_of_page_bid_micros: {target.get('low_top_of_page_bid_micros')}")
print(f"  high_top_of_page_bid_micros: {target.get('high_top_of_page_bid_micros')}")
print(f"  yoy_change: {target.get('yoy_change')}")

# Step 2: Process through AI filter
print("\n=== STEP 2: After AI Filter ===")

intake = {
    "scope": "seo",
    "business_name": "Test",
    "target_audience": "marketers",
    "target_location": "New Zealand",
    "product_service_description": "SEO training",
    "keyword_intent": "commercial_only",
    "buyer_journey_stage": "decision",
}

structured = run_keyword_ai_filter(
    intake=intake,
    raw_output=raw_keywords[:50],  # Just first 50 to save API cost
    user_id="test_user",
    research_id="test_123",
)

# Find same keyword in structured
all_keywords = (
    structured.get("primary_keywords", []) +
    structured.get("secondary_keywords", []) +
    structured.get("long_tail_keywords", [])
)

structured_target = None
for kw in all_keywords:
    if kw.get("keyword", "").lower() == target.get("keyword", "").lower():
        structured_target = kw
        break

if not structured_target and all_keywords:
    structured_target = all_keywords[0]

print(f"Sample keyword after AI filter:")
print(f"  keyword: {structured_target.get('keyword')}")
print(f"  search_volume: {structured_target.get('search_volume')}")
print(f"  competition: {structured_target.get('competition')}")
print(f"  competition_index: {structured_target.get('competition_index')}")
print(f"  low_top_of_page_bid_micros: {structured_target.get('low_top_of_page_bid_micros')}")
print(f"  high_top_of_page_bid_micros: {structured_target.get('high_top_of_page_bid_micros')}")
print(f"  trend_yoy: {structured_target.get('trend_yoy')}")

print("\n=== COMPARISON ===")
print(f"Raw avg_monthly_searches: {target.get('avg_monthly_searches')}")
print(f"Structured search_volume: {structured_target.get('search_volume')}")
print(f"Match: {target.get('avg_monthly_searches') == structured_target.get('search_volume')}")
