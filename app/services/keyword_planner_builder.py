"""
Keyword Planner Request Builder

This module transforms intake form data into a format suitable for Google Keyword Planner API.
Only fields that are accepted by Keyword Planner are included in the output.
"""

from typing import Optional


def build_keyword_planner_request(intake: dict, geo_id: str) -> dict:
    """
    Build a Keyword Planner request payload from intake form data.
    
    Args:
        intake: Dictionary containing the intake form answers
        geo_id: Geographic target constant ID (e.g., "1023191" for New York)
    
    Returns:
        Dictionary with the following structure:
        {
            "seed_keywords": [...],
            "landing_page": "<string or None>",
            "competitor_urls": [...],
            "geo_id": geo_id,
            "language_id": "1000"
        }
    """
    # 1. Extract and normalize seed keywords
    seed_keywords = []
    raw_keywords = intake.get("suggested_search_terms", "")
    if raw_keywords:
        # Split by comma, strip whitespace, remove empty items
        seed_keywords = [
            kw.strip() 
            for kw in raw_keywords.split(",") 
            if kw.strip()
        ]
    
    # 2. Extract landing page URL
    landing_page = intake.get("target_page_url") or None
    
    # 3. Extract competitor URLs (only non-empty ones)
    competitor_urls = []
    competitor_1 = intake.get("competitor_url_1", "").strip()
    competitor_2 = intake.get("competitor_url_2", "").strip()
    
    if competitor_1:
        competitor_urls.append(competitor_1)
    if competitor_2:
        competitor_urls.append(competitor_2)
    
    # 4. Build and return the payload
    return {
        "seed_keywords": seed_keywords,
        "landing_page": landing_page,
        "competitor_urls": competitor_urls,
        "geo_id": geo_id,
        "language_id": "1000"
    }
