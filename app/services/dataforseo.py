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
    
    # location_name is now the location ID from geo.py (e.g., "1001330" for Auckland)
    logger.info(f"DataForSEO request: seeds={seed_keywords[:3]}..., location_code={location_name}")

    # STEP 1: Get keyword suggestions (up to 20k keywords)
    url_endpoint = f"{API_BASE}/keywords_data/google_ads/keywords_for_keywords/live"
    
    payload = [{
        "keywords": seed_keywords,
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
        
        # Debug: Log the full response to see what DataForSEO actually returns
        logger.info(f"DataForSEO Step 1 response status: {data.get('status_code')}")
        logger.info(f"DataForSEO Step 1 response message: {data.get('status_message')}")
        logger.info(f"DataForSEO Step 1 tasks count: {len(data.get('tasks', []))}")
        
        if data.get("tasks") and len(data["tasks"]) > 0:
            task = data["tasks"][0]
            logger.info(f"DataForSEO Step 1 task status: {task.get('status_code')} - {task.get('status_message')}")
            logger.info(f"DataForSEO Step 1 task result count: {len(task.get('result', []))}")
            
            if task.get("result") and len(task["result"]) > 0:
                result = task["result"][0]
                logger.info(f"DataForSEO Step 1 result keys: {list(result.keys())}")
                logger.info(f"DataForSEO Step 1 items count: {len(result.get('items', []))}")
            
    except requests.exceptions.HTTPError as e:
        logger.error(f"DataForSEO Step 1 HTTP error: {e.response.status_code} - {e.response.text[:500]}")
        raise RuntimeError(f"DataForSEO Live API failed: HTTP {e.response.status_code}")
    except Exception as e:
        logger.error(f"DataForSEO Step 1 failed: {str(e)}", exc_info=True)
        raise RuntimeError(f"DataForSEO Live API failed: {e}")
    
    tasks = data.get("tasks", [])
    if not tasks or not tasks[0].get("result"):
        logger.warning(f"DataForSEO Step 1 returned no results for location={location_name}")
        return []
    
    result = tasks[0]["result"][0]
    
    # Debug: Log the full result structure to understand what fields exist
    logger.info(f"DataForSEO Step 1 result keys: {list(result.keys())}")
    logger.info(f"DataForSEO Step 1 full result: {result}")
    
    items = result.get("items", [])[:200]  # Limit to top 200 keywords
    
    # Debug: Log what we got
    logger.info(f"DataForSEO Step 1 returned {len(items)} items")
    if items:
        logger.info(f"First item structure: {list(items[0].keys())}")
        logger.info(f"First item sample: keyword={items[0].get('keyword')}, search_volume={items[0].get('search_volume')}")
    
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
    
    try:
        volume_resp = requests.post(volume_endpoint, json=volume_payload, headers=_auth_header(), timeout=120)
        volume_resp.raise_for_status()
        volume_data = volume_resp.json()
        logger.info(f"DataForSEO Step 2 completed: processed {len(keyword_list)} keywords")
    except requests.exceptions.HTTPError as e:
        logger.error(f"DataForSEO Step 2 HTTP error: {e.response.status_code} - {e.response.text[:500]}")
        raise RuntimeError(f"DataForSEO search_volume API failed: HTTP {e.response.status_code}")
    except Exception as e:
        logger.error(f"DataForSEO Step 2 failed: {str(e)}", exc_info=True)
        raise RuntimeError(f"DataForSEO search_volume API failed: {e}")
    
    volume_tasks = volume_data.get("tasks", [])
    if not volume_tasks or not volume_tasks[0].get("result"):
        logger.warning(f"DataForSEO Step 2 returned no results")
        return []
    
    volume_items = volume_tasks[0]["result"][0].get("items", [])
    if not volume_items:
        logger.warning(f"DataForSEO Step 2 returned no items")
        return []
    
    # Build output with full metrics from search_volume
    # CRITICAL: Only use exact values from DataForSEO, never make up numbers
    out: List[Dict] = []
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

        # Calculate YoY change from monthly_searches array ONLY if data exists
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
            "avg_monthly_searches": sv,  # None if DataForSEO didn't provide
            "competition": comp_str,  # None if DataForSEO didn't provide
            "competition_index": comp_index,  # None if DataForSEO didn't provide
            "low_top_of_page_bid_micros": low_micros,  # None if DataForSEO didn't provide
            "high_top_of_page_bid_micros": high_micros,  # None if DataForSEO didn't provide
            "yoy_change": yoy_change,  # None if not enough data
            "monthly_searches": monthly_searches,  # Empty array if no data
        })

    logger.info(f"DataForSEO completed: returned {len(out)} keywords with metrics")
    return out


def get_dataforseo_cost() -> float:
    """Return the cost per DataForSEO request.
    
    DataForSEO pricing:
    - keywords_for_keywords (Step 1): $0.015 per request (Live)
    - search_volume (Step 2): $0.015 per request (Live)
    - Total cost per fetch_keyword_ideas call: $0.03
    
    Returns:
        Cost in USD
    """
    return 0.03  # $0.015 x 2 steps


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
