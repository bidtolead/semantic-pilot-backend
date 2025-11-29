import os
import requests
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse


SERPER_ENDPOINT = "https://google.serper.dev/search"


class SerperClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("SERPER_API_KEY")
        if not self.api_key:
            raise ValueError("SERPER_API_KEY is not set in environment")

    def search(self, q: str, location: Optional[str] = None, gl: Optional[str] = None, hl: Optional[str] = None, num: int = 20) -> Dict[str, Any]:
        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json",
        }
        # Request enough results to evaluate top N rankings
        payload: Dict[str, Any] = {"q": q, "num": max(1, min(int(num or 10), 100))}
        if location:
            payload["location"] = location
        if gl:
            payload["gl"] = gl
        if hl:
            payload["hl"] = hl

        resp = requests.post(SERPER_ENDPOINT, json=payload, headers=headers, timeout=20)
        resp.raise_for_status()
        return resp.json()

    def find_url_rank(self, q: str, target_url: str, location: Optional[str] = None, gl: Optional[str] = None, hl: Optional[str] = None, top: int = 20) -> Dict[str, Any]:
        # Ask Serper for at least `top` results so we can inspect that many
        data = self.search(q=q, location=location, gl=gl, hl=hl, num=top)
        serp_items: List[Dict[str, Any]] = []
        # Only organic results for ranking
        items = data.get("organic")
        if isinstance(items, list):
            serp_items.extend(items)

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

        return {
            "query": q,
            "target_url": target_url,
            "rank": rank,
            "url": url_hit,
            "totalChecked": min(len(serp_items), top),
            "top": top,
        }
