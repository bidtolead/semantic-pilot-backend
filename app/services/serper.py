import os
import requests
from typing import List, Optional, Dict, Any


SERPER_ENDPOINT = "https://google.serper.dev/search"


class SerperClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("SERPER_API_KEY")
        if not self.api_key:
            raise ValueError("SERPER_API_KEY is not set in environment")

    def search(self, q: str, location: Optional[str] = None, gl: Optional[str] = None, hl: Optional[str] = None) -> Dict[str, Any]:
        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json",
        }
        payload: Dict[str, Any] = {"q": q}
        if location:
            payload["location"] = location
        if gl:
            payload["gl"] = gl
        if hl:
            payload["hl"] = hl

        resp = requests.post(SERPER_ENDPOINT, json=payload, headers=headers, timeout=20)
        resp.raise_for_status()
        return resp.json()

    def find_domain_rank(self, q: str, domain: str, location: Optional[str] = None, max_results: int = 20) -> Dict[str, Any]:
        data = self.search(q=q, location=location)
        serp_items: List[Dict[str, Any]] = []
        # Only organic results for ranking
        items = data.get("organic")
        if isinstance(items, list):
            serp_items.extend(items)

        rank = None
        url_hit = None
        for idx, item in enumerate(serp_items[:max_results], start=1):
            url = item.get("link") or item.get("url")
            if not url:
                continue
            if domain in url:
                rank = idx
                url_hit = url
                break

        return {
            "query": q,
            "domain": domain,
            "rank": rank,
            "url": url_hit,
            "totalChecked": min(len(serp_items), max_results),
            "top": max_results,
        }
