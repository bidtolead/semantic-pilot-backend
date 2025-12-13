import os
import requests
import json
import logging
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

SERPER_ENDPOINT = "https://google.serper.dev/search"


class SerperClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("SERPER_API_KEY")
        if not self.api_key:
            raise ValueError("SERPER_API_KEY is not set in environment")

    def search(self, q: str, location: Optional[str] = None, gl: Optional[str] = None, hl: Optional[str] = None, num: int = 20, page: int = 1) -> Dict[str, Any]:
        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json",
        }
        # Serper returns 10 results per page, use page parameter for pagination
        payload: Dict[str, Any] = {"q": q, "page": page}
        if location:
            payload["location"] = location
        if gl:
            payload["gl"] = gl
        if hl:
            payload["hl"] = hl

        logger.debug(f"Payload sent to Serper: {json.dumps(payload)}")
        resp = requests.post(SERPER_ENDPOINT, json=payload, headers=headers, timeout=20)
        resp.raise_for_status()
        result = resp.json()
        organic_count = len(result.get("organic", []))
        logger.debug(f"Serper returned {organic_count} organic results for page {page}")
        
        return result

    def find_url_rank(self, q: str, target_url: str, location: Optional[str] = None, gl: Optional[str] = None, hl: Optional[str] = None, top: int = 20) -> Dict[str, Any]:
        # Calculate how many pages we need (10 results per page)
        pages_needed = (top + 9) // 10  # Ceiling division
        logger.debug(f"Requesting top {top} results, will fetch {pages_needed} pages from Serper")
        
        serp_items: List[Dict[str, Any]] = []
        
        # Fetch multiple pages
        for page_num in range(1, pages_needed + 1):
            data = self.search(q=q, location=location, gl=gl, hl=hl, page=page_num)
            items = data.get("organic")
            if isinstance(items, list):
                serp_items.extend(items)
            else:
                break  # No more results
        
        logger.debug(f"Query: {q}, Location: {location}, GL: {gl}, Target: {target_url}")
        logger.debug(f"Received {len(serp_items)} total organic results across {pages_needed} pages")

        def _normalize(u: str) -> Dict[str, str]:
            try:
                p = urlparse(u)
                host = (p.hostname or "").lower().lstrip(".")
                if host.startswith("www."):
                    host = host[4:]
                # normalize path: drop trailing slash except for root
                path = (p.path or "").strip()
                if path != "/":
                    path = path.rstrip("/")
                return {"host": host, "path": path or "/"}
            except Exception:
                # fallback crude normalization
                s = (u or "").lower()
                s = s.replace("https://", "").replace("http://", "")
                if s.startswith("www."):
                    s = s[4:]
                parts = s.split("/", 1)
                host = parts[0]
                path = "/" + parts[1] if len(parts) > 1 else "/"
                if path != "/":
                    path = path.rstrip("/")
                return {"host": host, "path": path}

        target_norm = _normalize(target_url)

        rank = None
        url_hit = None
        domain_rank = None
        domain_url = None

        for idx, item in enumerate(serp_items[:top], start=1):
            url = item.get("link") or item.get("url")
            if not url:
                continue
            cand = _normalize(url)
            # Exact page match: same host and path
            if cand["host"] == target_norm["host"] and cand["path"] == target_norm["path"]:
                rank = idx
                url_hit = url
                break
            # Domain fallback: remember first occurrence of same host
            if domain_rank is None and cand["host"] == target_norm["host"]:
                domain_rank = idx
                domain_url = url

        # If exact not found, fall back to domain match within top N
        if rank is None and domain_rank is not None:
            rank = domain_rank
            url_hit = domain_url
        
        result = {
            "query": q,
            "target_url": target_url,
            "rank": rank,
            "url": url_hit,
            "totalChecked": min(len(serp_items), top),
            "top": top,
        }
        logger.debug(f"Final result: {result}")
        return result
