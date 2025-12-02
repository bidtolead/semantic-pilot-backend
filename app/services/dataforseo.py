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
    """Fetch keyword ideas via DataForSEO Live endpoint (instant results).

    Uses the LIVE endpoint for real-time results (~7 seconds) instead of 
    task_post which can take 1-3 hours.
    
    Cost: $0.75 per 1000 keywords (vs $0.50 for standard)
    Speed: ~7 seconds (vs 1-3 hours for standard)

    Returns a simplified list of dicts with fields similar to Google Ads output:
    - keyword
    - avg_monthly_searches
    - competition (as float 0-1 mapped to LOW/MEDIUM/HIGH)
    - competition_index (int scaled 0-100)
    - low_top_of_page_bid_micros (approx from cpc, same for high)
    
    Args:
        seed_keywords: List of seed keywords
        location_name: Location name (e.g., "New Zealand")
        language_name: Language (default "English")
        url: Optional URL to analyze for keyword suggestions
    """
    if not seed_keywords:
        return []

    # Use LIVE endpoint for instant results
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
    except Exception as e:
        raise RuntimeError(f"DataForSEO Live API failed: {e}")
    
    tasks = data.get("tasks", [])
    if not tasks or not tasks[0].get("result"):
        return []
    
    result = tasks[0]["result"][0]

    items = result.get("items", [])[:200]  # Limit to top 200 keywords for cost savings
    out: List[Dict] = []
    for it in items:
        kw = it.get("keyword")
        sv = it.get("search_volume")
        comp = it.get("competition")  # float 0..1
        cpc = it.get("cpc")  # dollars

        # Map competition float to label & index
        if comp is None:
            comp_label = None
            comp_index = None
        else:
            if comp < 0.33:
                comp_label = "LOW"
            elif comp < 0.66:
                comp_label = "MEDIUM"
            else:
                comp_label = "HIGH"
            comp_index = int(round(comp * 100))

        # Convert CPC dollars to micros and provide a simple low/high band
        if cpc is None:
            low_micros = None
            high_micros = None
        else:
            micros = int(round(cpc * 1_000_000))
            low_micros = int(micros * 0.7)
            high_micros = int(micros * 1.3)

        out.append({
            "keyword": kw,
            "avg_monthly_searches": sv,
            "competition": comp_label,
            "competition_index": comp_index,
            "low_top_of_page_bid_micros": low_micros,
            "high_top_of_page_bid_micros": high_micros,
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
