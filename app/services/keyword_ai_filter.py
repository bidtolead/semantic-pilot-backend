import os
import json
from typing import Any, Dict, List, Optional

# Lazy import OpenAI
from datetime import datetime, date
import time
from app.services.firestore import db
from google.cloud import firestore as gcfirestore
from app.utils.cost_calculator import calculate_openai_cost

# Client initialized lazily
_client = None

def get_openai_client():
    """Get or create OpenAI client (lazy initialization)."""
    global _client
    if _client is None:
        from openai import OpenAI
        _client = OpenAI()
    return _client

PROMPT_FALLBACK = None
try:
    # Optional fallback: use existing prompt from utils if available
    from app.utils.prompts import KEYWORD_RESEARCH_PROMPT as PROMPT_FALLBACK
except Exception:
    PROMPT_FALLBACK = None


def _load_prompt_text() -> str:
    """Load the keyword research prompt from a local file.

    Tries to read "keyword_research_prompt.txt" from the current working directory.
    Falls back to app.utils.prompts.KEYWORD_RESEARCH_PROMPT if the file isn't found.
    Raises ValueError if neither source is available.
    """
    candidate_paths = [
        os.path.join(os.getcwd(), "keyword_research_prompt.txt"),
        os.path.abspath("keyword_research_prompt.txt"),
    ]

    for path in candidate_paths:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()

    if PROMPT_FALLBACK:
        return PROMPT_FALLBACK

    raise ValueError(
        "Prompt file 'keyword_research_prompt.txt' not found and no fallback prompt available."
    )


def _json_default(o):
    """Best-effort JSON serializer for Firestore timestamps and datetimes.

    Converts datetime/date and Google Firestore DatetimeWithNanoseconds to ISO strings.
    Falls back to str(o) for unknown types to avoid serialization crashes.
    """
    # Datetime / date to ISO
    if isinstance(o, (datetime, date)):
        try:
            return o.isoformat()
        except Exception:
            return str(o)

    # Objects that implement isoformat (e.g., Firestore DatetimeWithNanoseconds)
    if hasattr(o, "isoformat"):
        try:
            return o.isoformat()
        except Exception:
            return str(o)

    # Fallback for anything else
    return str(o)


def run_keyword_ai_filter(
    *,
    intake: Dict[str, Any],
    raw_output: List[Dict[str, Any]],
    user_id: str,
    research_id: str,
) -> Dict[str, Any]:
    """Run AI keyword intelligence filtering (Step 3) and persist structured results.

    - Loads the prompt template
    - Injects intake and raw_output JSON blocks
    - Calls OpenAI chat completions with JSON response_format
    - Parses JSON safely
    - Saves structured results to Firestore under research/{userId}/{researchId}

    Returns the parsed JSON structure.
    """
    prompt_template = _load_prompt_text()

    # Limit Google keyword ideas to mitigate TPM rate limits
    # Start conservatively; we can tune upward later if stable
    initial_limit = 50
    limited_keywords = raw_output[:initial_limit] if isinstance(raw_output, list) else []

    # Build prompt with injected JSON blocks
    prompt = prompt_template
    prompt = prompt.replace(
        "{intake_json}",
        json.dumps(intake, ensure_ascii=False, indent=2, default=_json_default),
    )
    prompt = prompt.replace(
        "{keywords_list}",
        json.dumps(limited_keywords, ensure_ascii=False, indent=2, default=_json_default),
    )

    # Load model from system settings or use default
    model = "gpt-4o-mini"  # default
    try:
        settings_ref = db.collection("system_settings").document("openai")
        settings_doc = settings_ref.get()
        if settings_doc.exists:
            settings_data = settings_doc.to_dict()
            model = settings_data.get("model", "gpt-4o-mini")
    except Exception:
        # Fallback to default if settings not available
        pass

    # Call OpenAI once
    def _call_openai(p: str):
        return get_openai_client().chat.completions.create(
            model=os.getenv("OPENAI_MODEL") or model,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert SEO strategist and keyword analyst. "
                        "Always return strictly valid JSON — no markdown, no extra prose."
                    ),
                },
                {"role": "user", "content": p},
            ],
        )

    # Simple retry with exponential backoff on rate limits
    attempts = 0
    max_attempts = 2  # initial + one retry
    backoff_seconds = 60
    response = None

    while attempts < max_attempts:
        try:
            response = _call_openai(prompt)
            break
        except Exception as e:
            msg = str(e).lower()
            is_rate_limit = (
                "rate limit" in msg or "rate_limit_exceeded" in msg or "429" in msg
            )
            if not is_rate_limit:
                raise RuntimeError(f"OpenAI API request failed: {e}")
            attempts += 1
            if attempts >= max_attempts:
                raise RuntimeError(
                    "OpenAI rate limit exceeded. Please try again later or switch to a lower-load model in admin settings."
                )
            # Backoff and reduce keyword count further before retry
            time.sleep(backoff_seconds)
            reduced_limit = 30
            limited_keywords = raw_output[:reduced_limit] if isinstance(raw_output, list) else []
            prompt = prompt_template
            prompt = prompt.replace(
                "{intake_json}",
                json.dumps(intake, ensure_ascii=False, indent=2, default=_json_default),
            )
            prompt = prompt.replace(
                "{keywords_list}",
                json.dumps(limited_keywords, ensure_ascii=False, indent=2, default=_json_default),
            )

    if not response.choices:
        raise RuntimeError("OpenAI returned no choices")

    # Extract token usage from response
    token_usage = {
        "prompt_tokens": getattr(response.usage, "prompt_tokens", 0) if response.usage else 0,
        "completion_tokens": getattr(response.usage, "completion_tokens", 0) if response.usage else 0,
        "total_tokens": getattr(response.usage, "total_tokens", 0) if response.usage else 0,
    }
    
    # Calculate cost
    cost = calculate_openai_cost(
        prompt_tokens=token_usage["prompt_tokens"],
        completion_tokens=token_usage["completion_tokens"],
        model=model
    )
    token_usage["estimated_cost_usd"] = cost

    content = response.choices[0].message.content
    try:
        result_json = json.loads(content)
    except json.JSONDecodeError as e:
        # In case the model returns slight deviations, expose a concise error
        snippet = content[:300]
        raise ValueError(f"Invalid JSON from model: {e}: {snippet}")

    # Debug: Log the raw AI response
    print(f"\n=== RAW AI RESPONSE ===")
    print(f"AI JSON keys: {list(result_json.keys())}")
    print(f"Primary count from AI: {len(result_json.get('primary_keywords', []))}")
    print(f"Secondary count from AI: {len(result_json.get('secondary_keywords', []))}")
    print(f"Long-tail count from AI: {len(result_json.get('long_tail_keywords', []))}")
    if result_json.get('primary_keywords'):
        print(f"Sample primary: {result_json['primary_keywords'][0]}")
    
    # Validate and correct search_volume values against raw data
    # Also merge in all Google Ads metrics (competition, bid data, etc.)
    # CRITICAL: Use the same limited_keywords that we sent to the AI, not all raw_output
    raw_keyword_map = {
        item.get("keyword", "").lower().strip(): item
        for item in limited_keywords
        if isinstance(item, dict)
    }
    
    print(f"\n=== KEYWORD VALIDATION DEBUG ===")
    print(f"Raw keyword map has {len(raw_keyword_map)} keywords")
    print(f"Sample raw keywords: {list(raw_keyword_map.keys())[:5]}")
    
    # Debug: Show what AI returned
    ai_primary = result_json.get("primary_keywords", [])
    ai_secondary = result_json.get("secondary_keywords", [])
    ai_longtail = result_json.get("long_tail_keywords", [])
    print(f"\n=== AI RETURNED ===")
    print(f"Primary: {len(ai_primary)} keywords")
    print(f"Secondary: {len(ai_secondary)} keywords")
    print(f"Long-tail: {len(ai_longtail)} keywords")
    if ai_primary:
        print(f"First primary keyword from AI: '{ai_primary[0].get('keyword')}'")
    
    def validate_and_fix_search_volumes(keywords_list):
        """Ensure search_volume matches avg_monthly_searches from raw data and merge Google Ads metrics.
        
        CRITICAL: Only include keywords that exist in the raw DataForSEO data.
        If AI generates a keyword not in raw data, SKIP IT entirely.
        Use EXACT metrics from DataForSEO - never make up numbers.
        Use "-" for missing values instead of None to display cleanly in UI.
        """
        if not isinstance(keywords_list, list):
            return keywords_list
        
        fixed_keywords = []
        for kw in keywords_list:
            if not isinstance(kw, dict):
                continue  # Skip non-dict entries
            
            keyword_text = kw.get("keyword", "").lower().strip()
            raw_data = raw_keyword_map.get(keyword_text)
            
            # CRITICAL FIX: If keyword doesn't exist in raw data, SKIP it entirely
            if not raw_data:
                print(f"⚠️  SKIPPING '{keyword_text}' - not found in DataForSEO raw data")
                print(f"   AI made up search_volume: {kw.get('search_volume')} (invalid)")
                continue  # Don't add this keyword to results
            
            # Keyword exists in raw data - merge all metrics
            print(f"✅ MATCH for '{keyword_text}'")
            print(f"   AI gave: {kw.get('search_volume')} → Using DataForSEO avg_monthly_searches: {raw_data.get('avg_monthly_searches')}")
            print(f"   DataForSEO raw data keys: {list(raw_data.keys())}")
            print(f"   Full DataForSEO data for this keyword: {raw_data}")
            
            # Replace ALL fields with actual DataForSEO data
            # Use "-" for missing values instead of None for clean UI display
            kw["search_volume"] = raw_data.get("avg_monthly_searches") if raw_data.get("avg_monthly_searches") is not None else "-"
            kw["competition"] = raw_data.get("competition") if raw_data.get("competition") is not None else "-"
            kw["competition_index"] = raw_data.get("competition_index") if raw_data.get("competition_index") is not None else "-"
            kw["low_top_of_page_bid_micros"] = raw_data.get("low_top_of_page_bid_micros") if raw_data.get("low_top_of_page_bid_micros") is not None else "-"
            kw["high_top_of_page_bid_micros"] = raw_data.get("high_top_of_page_bid_micros") if raw_data.get("high_top_of_page_bid_micros") is not None else "-"
            
            # Add YoY trend data
            yoy = raw_data.get("yoy_change")
            if yoy is not None:
                kw["trend_yoy"] = f"{'+' if yoy > 0 else ''}{yoy}%"
            else:
                kw["trend_yoy"] = "-"
            
            # Add monthly searches data (preserve empty array if no data)
            kw["monthly_searches"] = raw_data.get("monthly_searches", [])
            
            fixed_keywords.append(kw)
        
        return fixed_keywords
    
    # Apply validation to all keyword categories
    if "primary_keywords" in result_json:
        result_json["primary_keywords"] = validate_and_fix_search_volumes(result_json["primary_keywords"])
    if "secondary_keywords" in result_json:
        result_json["secondary_keywords"] = validate_and_fix_search_volumes(result_json["secondary_keywords"])
    if "long_tail_keywords" in result_json:
        result_json["long_tail_keywords"] = validate_and_fix_search_volumes(result_json["long_tail_keywords"])

    # Persist to Firestore
    doc_ref = db.collection("research").document(user_id).collection("research").document(research_id)
    payload = {
        "primary_keywords": result_json.get("primary_keywords", []),
        "secondary_keywords": result_json.get("secondary_keywords", []),
        "long_tail_keywords": result_json.get("long_tail_keywords", []),
        # Carry-over context that may be useful to the frontend
        "seed_keywords_used": intake.get("suggested_search_terms", ""),
        "metadata": {
            **result_json.get("metadata", {}),
            "google_keywords_total": len(raw_output) if isinstance(raw_output, list) else 0,
            "google_keywords_used_for_ai": len(limited_keywords),
        },
        "token_usage": token_usage,  # Add token usage tracking
        "status": "completed",
        "createdAt": gcfirestore.SERVER_TIMESTAMP,
    }

    doc_ref.set(payload)

    # Update user's total token usage and spending in Firestore
    try:
        user_ref = db.collection("users").document(user_id)
        
        # First, ensure fields exist (set with merge to avoid overwriting)
        user_ref.set({
            "tokenUsage": 0,
            "totalSpend": 0.0
        }, merge=True)
        
        # Now increment
        user_ref.update({
            "tokenUsage": gcfirestore.Increment(token_usage["total_tokens"]),
            "totalSpend": gcfirestore.Increment(cost),
            "lastActivity": gcfirestore.SERVER_TIMESTAMP,
        })
    except Exception as e:
        pass  # Silently fail - metrics are non-critical
    
    # Update public stats counter for keywords analyzed
    try:
        total_keywords = len(payload["primary_keywords"]) + len(payload["secondary_keywords"]) + len(payload["long_tail_keywords"])
        db.collection("system").document("stats").update({
            "keywords_analyzed": gcfirestore.Increment(total_keywords)
        })
    except Exception:
        pass  # Non-critical

    # Mirror structured keywords back into intake path for legacy UI compatibility
    try:
        intake_keywords_ref = (
            db.collection("intakes")
            .document(user_id)
            .collection(research_id)
            .document("keyword_research")
        )
        intake_keywords_ref.set(
            {
                "primary_keywords": payload["primary_keywords"],
                "secondary_keywords": payload["secondary_keywords"],
                "long_tail_keywords": payload["long_tail_keywords"],
                "status": payload["status"],
                "updatedAt": gcfirestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )
    except Exception:
        # Best-effort; do not fail the main pipeline if legacy mirroring fails
        pass

    return payload
