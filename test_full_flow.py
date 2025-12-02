"""Test the complete flow: DataForSEO -> AI Filter -> Firestore structure"""
import asyncio
from app.services.dataforseo import fetch_keyword_ideas as dfs_fetch_keyword_ideas
from app.services.keyword_ai_filter import run_keyword_ai_filter
import json

async def main():
    print("Testing complete flow for Auckland SEO training...")
    
    # Step 1: Get raw keywords from DataForSEO (2-step process)
    raw_keywords = dfs_fetch_keyword_ideas(
        seed_keywords=["seo training", "seo course"],
        location_name="Auckland",
    )
    
    print(f"\n✅ Step 1: DataForSEO returned {len(raw_keywords)} keywords")
    
    # Print first 3 keywords with full detail
    print("\nFirst 3 raw keywords:")
    for i, kw in enumerate(raw_keywords[:3]):
        print(f"\n{i+1}. {kw.get('keyword')}")
        print(f"   avg_monthly_searches: {kw.get('avg_monthly_searches')}")
        print(f"   competition: {kw.get('competition')}")
        print(f"   competition_index: {kw.get('competition_index')}")
        print(f"   low_bid: {kw.get('low_top_of_page_bid_micros')}")
        print(f"   high_bid: {kw.get('high_top_of_page_bid_micros')}")
    
    # Step 2: Mock intake data
    intake = {
        "scope": "seo",
        "business_name": "Test SEO Training",
        "target_audience": "marketers",
        "target_location": "Auckland",
        "product_service_description": "SEO training courses",
        "keyword_intent": "commercial_only",
        "buyer_journey_stage": "decision",
    }
    
    print("\n🤖 Step 2: Running AI keyword filter...")
    
    # Step 3: Run AI filter
    structured = run_keyword_ai_filter(
        intake=intake,
        raw_output=raw_keywords,
        user_id="test_user",
        research_id="test_research_123",
    )
    
    print(f"\n✅ Step 3: AI returned {len(structured.get('primary_keywords', []))} primary keywords")
    
    # Check if metrics are preserved
    print("\nFirst primary keyword with metrics:")
    if structured.get('primary_keywords'):
        kw = structured['primary_keywords'][0]
        print(f"Keyword: {kw.get('keyword')}")
        print(f"search_volume: {kw.get('search_volume')}")
        print(f"competition: {kw.get('competition')}")
        print(f"competition_index: {kw.get('competition_index')}")
        print(f"low_bid: {kw.get('low_top_of_page_bid_micros')}")
        print(f"high_bid: {kw.get('high_top_of_page_bid_micros')}")
        
        # Check if these match the raw data
        raw_match = next((r for r in raw_keywords if r.get('keyword').lower() == kw.get('keyword', '').lower()), None)
        if raw_match:
            print("\n✅ Comparison with raw data:")
            print(f"   Raw avg_monthly_searches: {raw_match.get('avg_monthly_searches')}")
            print(f"   Structured search_volume: {kw.get('search_volume')}")
            print(f"   Match: {raw_match.get('avg_monthly_searches') == kw.get('search_volume')}")

asyncio.run(main())
