import json
import os
from typing import Dict, Any, List
from datetime import datetime, date

from openai import OpenAI

from app.utils.google_ads_utm_prompt import GOOGLE_ADS_UTM_PROMPT

_client = None

def get_openai_client():
    global _client
    if _client is None:
        _client = OpenAI()
    return _client


def _json_default(o):
    """Best-effort serializer for Firestore timestamps and datetimes."""
    if isinstance(o, (datetime, date)):
        try:
            return o.isoformat()
        except Exception:
            return str(o)
    if hasattr(o, "isoformat"):
        try:
            return o.isoformat()
        except Exception:
            return str(o)
    return str(o)

def _serialize_keywords(keywords_doc: Dict[str, Any]) -> List[str]:
    keywords: List[str] = []
    for category in ["primary_keywords", "secondary_keywords", "long_tail_keywords"]:
        for kw in keywords_doc.get(category, []) or []:
            if isinstance(kw, dict) and kw.get("keyword"):
                keywords.append(str(kw.get("keyword")))
            elif isinstance(kw, str):
                keywords.append(kw)
    return keywords

def generate_google_ads_utm(*, intake: Dict[str, Any], keywords_doc: Dict[str, Any]) -> Dict[str, Any]:
    final_keywords = _serialize_keywords(keywords_doc)

    prompt = GOOGLE_ADS_UTM_PROMPT
    prompt = prompt.replace("{user_intake_form}", json.dumps(intake, ensure_ascii=False, indent=2, default=_json_default))
    prompt = prompt.replace("{final_keywords}", json.dumps(final_keywords, ensure_ascii=False, indent=2, default=_json_default))

    response = get_openai_client().chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": "You are an expert in Google Ads attribution. Always return strictly valid JSON.",
            },
            {"role": "user", "content": prompt},
        ],
    )

    content = response.choices[0].message.content
    data = json.loads(content)

    # Ensure consistent shape for frontend
    final_url = data.get("final_tracking_url")
    urls = data.get("urls")
    if not urls:
        urls = [final_url] if final_url else []
    return {
        **data,
        "urls": urls,
    }
