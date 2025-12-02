import os
import time
import base64
import requests
from typing import List, Dict, Optional


API_BASE = os.getenv("DATAFORSEO_API_BASE", "https://api.dataforseo.com/v3")


def _auth_header() -> dict:
    login = os.getenv("DATAFORSEO_LOGIN")
    password = os.getenv("DATAFORSEO_PASSWORD")
    if not login or not password:
        raise ValueError("Missing DataForSEO credentials: DATAFORSEO_LOGIN/DATAFORSEO_PASSWORD")
    token = base64.b64encode(f"{login}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}


def post_keywords_for_seed_task(keywords: List[str], location_name: str, language_name: str = "English") -> str:
    url = f"{API_BASE}/keywords_data/google_ads/keywords_for_seed/task_post"
    payload = [{
        "keywords": keywords,
        "location_name": location_name,
        "language_name": language_name,
    }]
    resp = requests.post(url, json=payload, headers=_auth_header(), timeout=30)
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
    url = f"{API_BASE}/keywords_data/google_ads/keywords_for_seed/task_get/advanced/{task_id}"
    resp = requests.get(url, headers=_auth_header(), timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_keyword_ideas(
    seed_keywords: List[str],
    location_name: str,
    language_name: str = "English",
    poll_timeout_sec: int = 60,
    poll_interval_sec: float = 2.0,
) -> List[Dict]:
    """Fetch keyword ideas via DataForSEO Keywords for Seed.

    Returns a simplified list of dicts with fields similar to Google Ads output:
    - keyword
    - avg_monthly_searches
    - competition (as float 0-1 mapped to LOW/MEDIUM/HIGH)
    - competition_index (int scaled 0-100)
    - low_top_of_page_bid_micros (approx from cpc, same for high)
    """
    if not seed_keywords:
        return []

    task_id = post_keywords_for_seed_task(seed_keywords, location_name, language_name)

    deadline = time.time() + poll_timeout_sec
    result = None
    while time.time() < deadline:
        data = get_task_result(task_id)
        tasks = data.get("tasks", [])
        if tasks and tasks[0].get("result"):
            result = tasks[0]["result"][0]
            break
        time.sleep(poll_interval_sec)

    if not result:
        raise TimeoutError("DataForSEO: task result not ready in time")

    items = result.get("items", [])
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
    """Fetch all available Google Ads locations from DataForSEO.
    
    Returns a list of location dicts with:
    - location_code: unique ID
    - location_name: human-readable name
    - country_iso_code: 2-letter country code
    - location_type: "Country", "City", "Region", etc.
    
    This is a free endpoint and can be cached client-side.
    """
    url = f"{API_BASE}/keywords_data/google_ads/locations"
    resp = requests.get(url, headers=_auth_header(), timeout=30)
    resp.raise_for_status()
    data = resp.json()
    
    tasks = data.get("tasks", [])
    if not tasks or not tasks[0].get("result"):
        return []
    
    locations = tasks[0]["result"]
    return locations
