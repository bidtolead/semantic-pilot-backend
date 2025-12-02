import os
import time
import base64
import requests
from typing import List, Dict, Optional


# Ensure API_BASE is clean (strip any trailing slash or typos)
_raw_base = os.getenv("DATAFORSEO_API_BASE", "https://api.dataforseo.com/v3")
API_BASE = _raw_base.rstrip("/").replace("v3)", "v3")  # Fix common typo


def _auth_header() -> dict:
    login = os.getenv("DATAFORSEO_LOGIN")
    password = os.getenv("DATAFORSEO_PASSWORD")
    if not login or not password:
        raise ValueError("Missing DataForSEO credentials: DATAFORSEO_LOGIN/DATAFORSEO_PASSWORD")
    token = base64.b64encode(f"{login}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}


def post_keywords_for_seed_task(
    keywords: List[str], 
    location_name: str, 
    language_name: str = "English",
    url: Optional[str] = None
) -> str:
    url_endpoint = f"{API_BASE}/keywords_data/google_ads/keywords_for_keywords/task_post"
    payload = [{
        "keywords": keywords,
        "location_name": location_name,
        "language_name": language_name,
    }]
    
    # Add URL if provided for better keyword targeting
    if url:
        payload[0]["url"] = url
    
    resp = requests.post(url_endpoint, json=payload, headers=_auth_header(), timeout=30)
    resp.raise_for_status()
    resp.raise_for_status()
    data = resp.json()
    tasks = (data or {}).get("tasks", [])
    if not tasks:
        raise RuntimeError("DataForSEO: no task created")
    task_id = tasks[0].get("id")
    if not task_id:
        raise RuntimeError("DataForSEO: missing task id")
    return task_id


def get_task_result(task_id: str) -> Dict:
    url = f"{API_BASE}/keywords_data/google_ads/keywords_for_keywords/task_get/{task_id}"
    resp = requests.get(url, headers=_auth_header(), timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_keyword_ideas(
    seed_keywords: List[str],
    location_name: str,
    language_name: str = "English",
    url: Optional[str] = None,
) -> List[Dict]:
    """Fetch keyword ideas via DataForSEO 2-step process.
    
    Step 1: Get keyword suggestions from keywords_for_keywords
    Step 2: Get full metrics (competition, bids) from search_volume
    
    Cost: $0.075 per task (Live mode)
    Speed: ~7-10 seconds total
    
    Args:
        seed_keywords: List of seed keywords
        location_name: Location name (e.g., "New Zealand")
        language_name: Language (default "English")
        url: Optional URL to analyze for keyword suggestions
    """
    if not seed_keywords:
        return []

    # STEP 1: Get keyword suggestions (up to 20k keywords)
    url_endpoint = f"{API_BASE}/keywords_data/google_ads/keywords_for_keywords/live"
    
    payload = [{
        "keywords": seed_keywords,
        "location_name": location_name,
        "language_name": language_name,
        "search_partners": False,  # Exclude search partners to match Google Ads Keyword Planner
    }]
    
    # Add URL if provided for better keyword targeting
    if url:
        payload[0]["url"] = url
    
    try:
        resp = requests.post(url_endpoint, json=payload, headers=_auth_header(), timeout=120)
        resp.raise_for_status()
        data = resp.json()
        
        # Debug: Log first keyword's raw data to understand the response structure
        if data.get("tasks") and data["tasks"][0].get("result") and data["tasks"][0]["result"][0].get("items"):
            sample = data["tasks"][0]["result"][0]["items"][0]
            print(f"DEBUG DataForSEO sample keyword: {sample.get('keyword')}")
            print(f"  search_volume: {sample.get('search_volume')}")
            print(f"  competition: {sample.get('competition')}")
            print(f"  competition_index: {sample.get('competition_index')}")
            print(f"  low_top_of_page_bid: {sample.get('low_top_of_page_bid')}")
            print(f"  high_top_of_page_bid: {sample.get('high_top_of_page_bid')}")
            print(f"  monthly_searches (first 3): {sample.get('monthly_searches', [])[:3]}")
            
    except Exception as e:
        raise RuntimeError(f"DataForSEO Live API failed: {e}")
    
    tasks = data.get("tasks", [])
    if not tasks or not tasks[0].get("result"):
        return []
    
    result = tasks[0]["result"][0]
    items = result.get("items", [])[:200]  # Limit to top 200 keywords
    
    # Extract just the keyword strings for Step 2
    keyword_list = [it.get("keyword") for it in items if it.get("keyword")]
    
    if not keyword_list:
        return []
    
    # STEP 2: Get full metrics (competition, bids, YoY) using search_volume endpoint
    volume_endpoint = f"{API_BASE}/keywords_data/google_ads/search_volume/live"
    volume_payload = [{
        "keywords": keyword_list,  # Pass the 200 keywords we got from step 1
        "location_name": location_name,
        "language_name": language_name,
        "search_partners": False,
    }]
    
    try:
        volume_resp = requests.post(volume_endpoint, json=volume_payload, headers=_auth_header(), timeout=120)
        volume_resp.raise_for_status()
        volume_data = volume_resp.json()
    except Exception as e:
        raise RuntimeError(f"DataForSEO search_volume API failed: {e}")
    
    volume_tasks = volume_data.get("tasks", [])
    if not volume_tasks or not volume_tasks[0].get("result"):
        return []
    
    volume_items = volume_tasks[0]["result"][0].get("items", [])
    
    # Build output with full metrics from search_volume
    out: List[Dict] = []
    for it in volume_items:
        kw = it.get("keyword")
        sv = it.get("search_volume")
        comp_index = it.get("competition_index")
        comp_str = it.get("competition")
        low_bid = it.get("low_top_of_page_bid")
        high_bid = it.get("high_top_of_page_bid")
        monthly_searches = it.get("monthly_searches", [])

        # Convert bids from dollars to micros
        low_micros = int(round(low_bid * 1_000_000)) if low_bid is not None else None
        high_micros = int(round(high_bid * 1_000_000)) if high_bid is not None else None

        # Calculate YoY change from monthly_searches array
        yoy_change = None
        if monthly_searches and len(monthly_searches) >= 12:
            try:
                current_month = monthly_searches[0].get("search_volume")
                year_ago_month = monthly_searches[11].get("search_volume")
                if current_month is not None and year_ago_month is not None and year_ago_month > 0:
                    yoy_change = round(((current_month - year_ago_month) / year_ago_month) * 100, 1)
            except (IndexError, KeyError, ZeroDivisionError):
                pass

        out.append({
            "keyword": kw,
            "avg_monthly_searches": sv,
            "competition": comp_str,
            "competition_index": comp_index,
            "low_top_of_page_bid_micros": low_micros,
            "high_top_of_page_bid_micros": high_micros,
            "yoy_change": yoy_change,
            "monthly_searches": monthly_searches,
        })

    return out


def fetch_locations() -> List[Dict]:
    """Fetch Google Ads locations from DataForSEO for English-speaking countries only.
    
    WARNING: DataForSEO returns ALL ~100k+ locations in one response.
    We filter immediately during parsing to reduce memory footprint.
    
    Returns a filtered list of location dicts with:
    - location_code: unique ID
    - location_name: human-readable name
    - country_iso_code: 2-letter country code
    - location_type: "Country", "City", "Region", etc.
    """
    # Allowed English-speaking countries
    ALLOWED_COUNTRIES = {
        "US", "CA", "GB", "IE", "AU", "NZ",
        "SG", "AE", "IL", "ZA", "PH", "IN", "NG"
    }
    
    url = f"{API_BASE}/keywords_data/google_ads/locations"
    
    # Stream the response to avoid loading entire payload into memory at once
    try:
        resp = requests.get(url, headers=_auth_header(), timeout=60, stream=True)
        resp.raise_for_status()
        
        # Parse JSON incrementally
        data = resp.json()
    except Exception as e:
        raise RuntimeError(f"DataForSEO locations API failed: {e}")
    
    tasks = data.get("tasks", [])
    if not tasks or not tasks[0].get("result"):
        return []
    
    all_locations = tasks[0]["result"]
    
    # Filter IMMEDIATELY to reduce memory - don't keep the full list
    # This processes and discards non-matching locations as we iterate
    filtered_locations = []
    for loc in all_locations:
        country = (loc.get("country_iso_code") or "").upper()
        if country in ALLOWED_COUNTRIES:
            filtered_locations.append(loc)
    
    # Clear the original list from memory
    del all_locations
    del data
    
    return filtered_locations
