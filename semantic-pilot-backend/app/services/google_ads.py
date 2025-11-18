# app/services/google_ads.py
import random

def fetch_keyword_ideas(keywords: list[str]) -> list[dict]:
    """Return mock keyword ideas until Google Ads Standard Access is approved."""

    mock_results = []

    for kw in keywords:
        mock_results.append({
            "keyword": kw,
            "avg_monthly_searches": random.randint(1000, 25000),
            "competition": random.choice(["LOW", "MEDIUM", "HIGH"]),
            "cpc": round(random.uniform(0.5, 4.5), 2)
        })

    return mock_results
