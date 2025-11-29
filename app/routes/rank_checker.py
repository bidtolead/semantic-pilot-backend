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



@router.post("/batch")
def batch_rank(payload: BatchRankRequest):
    try:
        if not payload.keywords:
            raise ValueError("No keywords provided")
        if len(payload.keywords) > 15:
            raise ValueError("Maximum of 15 final keywords per research")
        client = SerperClient()
        results = []
        for kw in payload.keywords:
            r = client.find_url_rank(q=kw, target_url=payload.target_url, location=payload.location, max_results=20)
            # Map rank None to "Not in top 20"
            results.append({
                "keyword": kw,
                "rank": r.get("rank") if r.get("rank") is not None else "Not in top 20",
                "url": r.get("url"),
            })
        return {"ok": True, "location": payload.location, "target_url": payload.target_url, "results": results}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
