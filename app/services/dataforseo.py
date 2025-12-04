import os
import time
import base64
import requests
import logging
from typing import List, Dict, Optional

# Configure logging
logger = logging.getLogger(__name__)

# Ensure API_BASE is clean (strip any trailing slash or typos)
_raw_base = os.getenv("DATAFORSEO_API_BASE", "https://api.dataforseo.com/v3")
API_BASE = _raw_base.rstrip("/").replace("v3)", "v3")  # Fix common typo

# Track actual costs from DataForSEO API responses
_last_step1_cost = 0.0
_last_step2_cost = 0.0
_last_total_cost = 0.0


def clean_location_name(location: str) -> str:
    """Clean location string and convert to DataForSEO format.
    
    Examples:
        "Auckland (City · NZ)" -> "Auckland,New Zealand"
        "Auckland, New Zealand (City · NZ)" -> "Auckland,New Zealand"  
        "New Zealand (Country · NZ)" -> "New Zealand"
        "United States" -> "United States"
    
    Args:
        location: Raw location string from frontend
    
    Returns:
        Cleaned location name for DataForSEO API
    """
    if not location:
        return location
    
    original_location = location
    logger.debug(f"clean_location_name input: '{original_location}'")
    
    # Map of country codes to full country names
    country_map = {
        "NZ": "New Zealand",
        "AU": "Australia", 
        "US": "United States",
        "GB": "United Kingdom",
        "UK": "United Kingdom",
        "CA": "Canada",
        "IE": "Ireland",
        "SG": "Singapore",
        "AE": "United Arab Emirates",
        "IL": "Israel",
        "ZA": "South Africa",
        "PH": "Philippines",
        "IN": "India",
        "NG": "Nigeria",
    }
    
    # Extract location name and country code
    # Format: "Auckland (City · NZ)" or "Auckland, New Zealand (City - NZ)"
    if "(" in location:
        parts = location.split("(")
        location_name = parts[0].strip()
        
        # Extract country code from parentheses
        if len(parts) > 1:
            metadata = parts[1].rstrip(")")
            # Extract country code (last part after · or -)
            if "·" in metadata:
                country_code = metadata.split("·")[-1].strip()
            elif "-" in metadata:
                country_code = metadata.split("-")[-1].strip()
            else:
                country_code = metadata.strip()
            
            # Convert country code to full name
            country_full = country_map.get(country_code.upper())
            
            if country_full:
                # Check if location_name already contains the country
                if country_full.lower() in location_name.lower():
                    # Already has country in it, remove any spaces after commas for DataForSEO
                    cleaned = location_name.replace(", ", ",")
                    logger.debug(f"clean_location_name output: '{cleaned}' (country already in name)")
                    return cleaned
                
                # Check if location_name is the same as country
                if location_name.lower() == country_full.lower():
                    # Just return country name
                    logger.debug(f"clean_location_name output: '{country_full}' (country only)")
                    return country_full
                else:
                    # Return "City,Country" format for DataForSEO (no space after comma)
                    result = f"{location_name},{country_full}"
                    logger.debug(f"clean_location_name output: '{result}' (city,country)")
                    return result
    
    # No parentheses - return as-is
    logger.debug(f"clean_location_name output: '{location}' (no changes)")
    return location


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
        logger.warning("fetch_keyword_ideas called with empty seed_keywords")
        return []
    
    # Clean seed keywords: remove trailing periods, extra spaces, and invalid characters
    # Google Ads doesn't allow certain symbols at the end of keywords or commas within them
    cleaned_seeds = []
    for kw in seed_keywords:
        if kw:
            # Strip whitespace and trailing periods/commas
            cleaned = kw.strip().rstrip('.,;:!?')
            # Remove commas from within the keyword (Google Ads doesn't allow them)
            cleaned = cleaned.replace(',', '')
            # Remove extra whitespace
            cleaned = ' '.join(cleaned.split())
            if cleaned:
                cleaned_seeds.append(cleaned)
    
    if not cleaned_seeds:
        logger.warning("All seed keywords were empty after cleaning")
        return []
    
    # location_name is now the location ID from geo.py (e.g., "1001330" for Auckland)
    logger.info(f"DataForSEO request: seeds={cleaned_seeds[:3]}..., location_code={location_name}")

    # STEP 1: Get keyword suggestions (up to 20k keywords)
    url_endpoint = f"{API_BASE}/keywords_data/google_ads/keywords_for_keywords/live"
    
    payload = [{
        "keywords": cleaned_seeds,
        "location_code": int(location_name),  # DataForSEO requires numeric location code
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
            
    except requests.exceptions.HTTPError as e:
        logger.error(f"DataForSEO Step 1 HTTP error: {e.response.status_code} - {e.response.text[:500]}")
        raise RuntimeError(f"DataForSEO Live API failed: HTTP {e.response.status_code}")
    except Exception as e:
        logger.error(f"DataForSEO Step 1 failed: {str(e)}", exc_info=True)
        raise RuntimeError(f"DataForSEO Live API failed: {e}")
    
    tasks = data.get("tasks", [])
    if not tasks or not tasks[0].get("result"):
        logger.warning(f"DataForSEO Step 1 returned no results for location_code={location_name}")
        return []
    
    # Capture actual Step 1 cost
    global _last_step1_cost
    _last_step1_cost = tasks[0].get("cost", 0.0)
    print(f"🔍 Step 1 actual cost from DataForSEO: ${_last_step1_cost:.6f}", flush=True)
    
    # IMPORTANT: result is already an array of keyword items, not a wrapper object with "items"
    # We pay the same $0.075 whether we use 200 or 1000 keywords, so fetch all available keywords
    items = tasks[0]["result"][:1000]  # Limit to top 1000 keywords (same price as 200)
    
    logger.info(f"DataForSEO Step 1 returned {len(items)} keywords for location_code={location_name}")
    
    # Extract just the keyword strings for Step 2
    keyword_list = [it.get("keyword") for it in items if it.get("keyword")]
    
    if not keyword_list:
        logger.warning(f"DataForSEO Step 1 returned items but no valid keywords for location_code={location_name}")
        logger.warning(f"Sample item (if exists): {items[0] if items else 'No items'}")
        return []
    
    # STEP 2: Get full metrics (competition, bids, YoY) using search_volume endpoint
    volume_endpoint = f"{API_BASE}/keywords_data/google_ads/search_volume/live"
    volume_payload = [{
        "keywords": keyword_list,  # Pass the 200 keywords we got from step 1
        "location_code": int(location_name),  # DataForSEO requires numeric location code
        "language_name": language_name,
        "search_partners": False,
    }]
    
    print(f"🔍 Step 2 payload: keywords={len(keyword_list)}, location_code={int(location_name)}, language={language_name}", flush=True)
    
    try:
        volume_resp = requests.post(volume_endpoint, json=volume_payload, headers=_auth_header(), timeout=120)
        volume_resp.raise_for_status()
        volume_data = volume_resp.json()
        
        # Debug Step 2 response structure
        print(f"🔍 Step 2 response status: {volume_data.get('status_code')}", flush=True)
        print(f"🔍 Step 2 tasks count: {len(volume_data.get('tasks', []))}", flush=True)
        if volume_data.get("tasks") and len(volume_data["tasks"]) > 0:
            task = volume_data["tasks"][0]
            print(f"🔍 Step 2 task status: {task.get('status_code')} - {task.get('status_message')}", flush=True)
            print(f"🔍 Step 2 task cost: {task.get('cost')}", flush=True)
            print(f"🔍 Step 2 task credits_used: {task.get('credits_used')}", flush=True)
            result = task.get('result')
            if result:
                print(f"🔍 Step 2 result count: {len(result)}", flush=True)
            else:
                print(f"🔍 Step 2 result is None (error)", flush=True)
            
        logger.info(f"DataForSEO Step 2 completed: processed {len(keyword_list)} keywords")
    except requests.exceptions.HTTPError as e:
        logger.error(f"DataForSEO Step 2 HTTP error: {e.response.status_code} - {e.response.text[:500]}")
        raise RuntimeError(f"DataForSEO search_volume API failed: HTTP {e.response.status_code}")
    except Exception as e:
        logger.error(f"DataForSEO Step 2 failed: {str(e)}", exc_info=True)
        raise RuntimeError(f"DataForSEO search_volume API failed: {e}")
    
    volume_tasks = volume_data.get("tasks", [])
    if not volume_tasks:
        logger.warning(f"DataForSEO Step 2 returned no tasks")
        return []
    
    # Capture actual Step 2 cost
    global _last_step2_cost, _last_total_cost
    _last_step2_cost = volume_tasks[0].get("cost", 0.0)
    _last_total_cost = _last_step1_cost + _last_step2_cost
    print(f"🔍 Step 2 actual cost from DataForSEO: ${_last_step2_cost:.6f}", flush=True)
    print(f"💰 TOTAL COST: Step 1=${_last_step1_cost:.6f} + Step 2=${_last_step2_cost:.6f} = ${_last_total_cost:.6f}", flush=True)
    
    volume_result = volume_tasks[0].get("result")
    if not volume_result:
        logger.warning(f"DataForSEO Step 2 task has no result")
        return []
    
    # IMPORTANT: result is already an array of keyword items, not a wrapper object with "items"
    volume_items = volume_result
    if not isinstance(volume_items, list) or len(volume_items) == 0:
        logger.warning(f"DataForSEO Step 2 returned no items")
        return []
    
    logger.info(f"DataForSEO Step 2 returned {len(volume_items)} keywords with full metrics")
    
    # Build output with full metrics from search_volume
    # CRITICAL: Only use exact values from DataForSEO, never make up numbers
    out: List[Dict] = []
    
    # DEBUG: Log first few items from DataForSEO response
    print(f"\n🔍 DataForSEO Step 2 - First 3 keywords with metrics:")
    for idx, it in enumerate(volume_items[:3]):
        print(f"  [{idx}] keyword: {it.get('keyword')}")
        print(f"      search_volume: {it.get('search_volume')}")
        print(f"      competition: {it.get('competition')}")
        print(f"      competition_index: {it.get('competition_index')}")
        print(f"      low_bid: {it.get('low_top_of_page_bid')}")
        print(f"      high_bid: {it.get('high_top_of_page_bid')}")
        monthly = it.get("monthly_searches", [])
        print(f"      monthly_searches count: {len(monthly)}")
        if monthly:
            print(f"      latest month volume: {monthly[0].get('search_volume')}")
    
    for it in volume_items:
        kw = it.get("keyword")
        sv = it.get("search_volume")  # May be None
        comp_index = it.get("competition_index")  # May be None
        comp_str = it.get("competition")  # May be None
        low_bid = it.get("low_top_of_page_bid")  # May be None
        high_bid = it.get("high_top_of_page_bid")  # May be None
        monthly_searches = it.get("monthly_searches", [])

        # Convert bids from dollars to micros ONLY if value exists
        low_micros = int(round(low_bid * 1_000_000)) if low_bid is not None else None
        high_micros = int(round(high_bid * 1_000_000)) if high_bid is not None else None

        # DEBUG: Log monthly_searches structure for first 3 keywords
        if keyword_list.index(kw) < 3:
            print(f"\n🔍 DEBUG: Keyword '{kw}'")
            print(f"   monthly_searches length: {len(monthly_searches)}")
            if monthly_searches:
                print(f"   Monthly data (first 3): {monthly_searches[:3]}")
                print(f"   Latest month (index 0): {monthly_searches[0]}")
                if len(monthly_searches) > 2:
                    print(f"   2 months ago (index 2): {monthly_searches[2]}")
                if len(monthly_searches) > 11:
                    print(f"   12 months ago (index 11): {monthly_searches[11]}")
                if len(monthly_searches) > 12:
                    print(f"   13 months ago (index 12): {monthly_searches[12]}")

        # Calculate YoY change from monthly_searches array ONLY if data exists
        # Proper YoY requires comparing the SAME calendar month from last year
        # e.g., Oct 2025 vs Oct 2024 (exactly 12 months apart)
        # We need at least 13 data points to have this
        yoy_change = None
        if monthly_searches and len(monthly_searches) >= 13:
            try:
                current_month_data = monthly_searches[0]
                year_ago_month_data = monthly_searches[12]  # Exactly 12 months prior
                
                current_month = current_month_data.get("search_volume")
                year_ago_month = year_ago_month_data.get("search_volume")
                current_date = (current_month_data.get("year"), current_month_data.get("month"))
                year_ago_date = (year_ago_month_data.get("year"), year_ago_month_data.get("month"))
                
                # Verify we're comparing same calendar month (e.g., Oct vs Oct, not Oct vs Nov)
                if current_date[1] == year_ago_date[1] and current_month is not None and year_ago_month is not None and year_ago_month > 0:
                    yoy_change = round(((current_month - year_ago_month) / year_ago_month) * 100, 1)
                    print(f"   YoY (13+ months, same calendar month): {current_date} {current_month} vs {year_ago_date} {year_ago_month} = {yoy_change}%")
            except (IndexError, KeyError, ZeroDivisionError):
                pass
        
        # Fallback: if we only have 12 months and can't do proper YOY, leave as None
        if yoy_change is None and monthly_searches and len(monthly_searches) >= 12:
            print(f"   YoY: Only 12 months of data available, cannot compare same calendar month (would need 13+ months)")

        out.append({
            "keyword": kw,
            "avg_monthly_searches": sv,  # None if DataForSEO didn't provide
            "competition": comp_str,  # None if DataForSEO didn't provide
            "competition_index": comp_index,  # None if DataForSEO didn't provide
            "low_top_of_page_bid_micros": low_micros,  # None if DataForSEO didn't provide
            "high_top_of_page_bid_micros": high_micros,  # None if DataForSEO didn't provide
            "yoy_change": yoy_change,  # None if not enough data
            "monthly_searches": monthly_searches if monthly_searches is not None else [],  # Always an array, never None
        })

    logger.info(f"DataForSEO completed: returned {len(out)} keywords with metrics")
    return out


def get_dataforseo_cost() -> float:
    """Return the actual cost of the last DataForSEO request.
    
    DataForSEO returns the actual cost in each task response.
    This function returns the combined cost from the last fetch_keyword_ideas call.
    
    Returns:
        Actual cost in USD from the last DataForSEO request (or $0.00 if not run yet)
    """
    return _last_total_cost


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
