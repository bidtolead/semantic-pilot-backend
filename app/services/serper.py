import os
import requests
import json
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse


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

        print(f"[SERPER DEBUG] Payload sent to Serper: {json.dumps(payload)}")
        resp = requests.post(SERPER_ENDPOINT, json=payload, headers=headers, timeout=20)
        resp.raise_for_status()
        result = resp.json()
        organic_count = len(result.get("organic", []))
        print(f"[SERPER DEBUG] Serper returned {organic_count} organic results for page {page}")
        
        # Log first 5 organic results to debug
        for idx, item in enumerate(result.get("organic", [])[:5], start=1):
            global_position = (page - 1) * 10 + idx
            print(f"[SERPER DEBUG] Result #{global_position}: {item.get('title', 'N/A')[:50]}... | {item.get('link', 'N/A')}")
        
        return result

    def find_url_rank(self, q: str, target_url: str, location: Optional[str] = None, gl: Optional[str] = None, hl: Optional[str] = None, top: int = 20) -> Dict[str, Any]:
        # Calculate how many pages we need (10 results per page)
        pages_needed = (top + 9) // 10  # Ceiling division
        print(f"[SERPER DEBUG] Requesting top {top} results, will fetch {pages_needed} pages from Serper")
        
        serp_items: List[Dict[str, Any]] = []
        
        # Fetch multiple pages
        for page_num in range(1, pages_needed + 1):
            data = self.search(q=q, location=location, gl=gl, hl=hl, page=page_num)
            items = data.get("organic")
            if isinstance(items, list):
                serp_items.extend(items)
            else:
                break  # No more results
        
        # DEBUG: Log what Serper returned
        print(f"[SERPER DEBUG] Query: {q}, Location: {location}, GL: {gl}")
        print(f"[SERPER DEBUG] Target: {target_url}")
        print(f"[SERPER DEBUG] Received {len(serp_items)} total organic results across {pages_needed} pages")
        for idx, item in enumerate(serp_items[:10], start=1):
            url = item.get("link") or item.get("url")
            print(f"[SERPER DEBUG] #{idx}: {url}")

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
        print(f"[SERPER DEBUG] Target normalized: host={target_norm['host']}, path={target_norm['path']}")

        rank = None
        url_hit = None
        domain_rank = None
        domain_url = None

        for idx, item in enumerate(serp_items[:top], start=1):
            url = item.get("link") or item.get("url")
            if not url:
                continue
            cand = _normalize(url)
            print(f"[SERPER DEBUG] Comparing #{idx}: {url} -> host={cand['host']}, path={cand['path']}")
            # Exact page match: same host and path
            if cand["host"] == target_norm["host"] and cand["path"] == target_norm["path"]:
                print(f"[SERPER DEBUG] ✓ EXACT MATCH at #{idx}: {url}")
                rank = idx
                url_hit = url
                break
            # Domain fallback: remember first occurrence of same host
            if domain_rank is None and cand["host"] == target_norm["host"]:
                print(f"[SERPER DEBUG] ✓ DOMAIN MATCH at #{idx}: {url}")
                domain_rank = idx
                domain_url = url

        # If exact not found, fall back to domain match within top N
        if rank is None and domain_rank is not None:
            print(f"[SERPER DEBUG] No exact match, using domain fallback rank #{domain_rank}")
            rank = domain_rank
            url_hit = domain_url
        
        if rank is None:
            print(f"[SERPER DEBUG] ❌ NO MATCH FOUND in top {top} results")
        
        result = {
            "query": q,
            "target_url": target_url,
            "rank": rank,
            "url": url_hit,
            "totalChecked": min(len(serp_items), top),
            "top": top,
        }
        print(f"[SERPER DEBUG] Final result: {result}")
        return result
