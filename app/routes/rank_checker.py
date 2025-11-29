from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.serper import SerperClient


router = APIRouter(prefix="/rank", tags=["rank"])



class RankRequest(BaseModel):
    query: str
    target_url: str
    location: str | None = None



@router.post("/check")
def check_rank(payload: RankRequest):
    try:
        client = SerperClient()
        result = client.find_url_rank(q=payload.query, target_url=payload.target_url, location=payload.location, max_results=20)
        return {"ok": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))



class BatchRankRequest(BaseModel):
    keywords: list[str]
    target_url: str
    location: str
    top: int | None = 20  # number of organic results to check (default 20)



def _parse_location(loc: str):
    """Extract a city name and country code from a display string like
    'Auckland (City · NZ)'. Returns (location, gl) where gl is a lowercased
    country code suitable for Serper's 'gl' parameter. If parsing fails,
    returns (loc, None).
    """
    try:
        name = loc
        gl = None
        if "(" in loc and ")" in loc:
            # e.g., 'Auckland (City · NZ)'
            name = loc.split("(", 1)[0].strip()
            inside = loc.split("(", 1)[1].split(")", 1)[0]
            parts = [p.strip() for p in inside.split("·")]
            if parts:
                cc = parts[-1].strip()
                if len(cc) == 2:
                    gl = cc.lower()
        return name, gl
    except Exception:
        return loc, None


@router.post("/batch")
def batch_rank(payload: BatchRankRequest):
    try:
        if not payload.keywords:
            raise ValueError("No keywords provided")
        if len(payload.keywords) > 15:
            raise ValueError("Maximum of 15 final keywords per research")
        client = SerperClient()
        # Normalize location and derive gl from the LocationCombobox format
        norm_location, gl = _parse_location(payload.location)
        top = int(payload.top or 20)
        top = 20 if top < 1 else min(top, 100)
        results = []
        for kw in payload.keywords:
            r = client.find_url_rank(
                q=kw,
                target_url=payload.target_url,
                location=norm_location,
                gl=gl,
                hl="en",
                top=top,
            )
            # Map rank None to "Not in top 20"
            results.append({
                "keyword": kw,
                "rank": r.get("rank") if r.get("rank") is not None else f"Not in top {top}",
                "url": r.get("url"),
            })
        return {"ok": True, "location": norm_location, "gl": gl, "target_url": payload.target_url, "top": top, "results": results}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
