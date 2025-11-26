import os
import json
from typing import Any, Dict, List, Optional

from openai import OpenAI
from datetime import datetime, date
import time
from app.services.firestore import db
from google.cloud import firestore as gcfirestore

# Initialize OpenAI client (OPENAI_API_KEY must be set in env)
client = OpenAI()

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

    # Limit Google keyword ideas to at most 100 for AI processing
    # Reduces prompt tokens to mitigate TPM rate limits
    initial_limit = 100
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

    # Call OpenAI with basic retry/backoff on rate limit
    def _call_openai(p: str):
        return client.chat.completions.create(
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

    try:
        response = _call_openai(prompt)
    except Exception as e:
        # Detect rate limit by message content to avoid import dependency issues
        msg = str(e).lower()
        is_rate_limit = "rate limit" in msg or "rate_limit_exceeded" in msg or "429" in msg
        if not is_rate_limit:
            raise RuntimeError(f"OpenAI API request failed: {e}")
        # Retry once with smaller keyword batch to reduce tokens
        try:
            # Basic backoff: wait ~65s to clear TPM window
            time.sleep(65)
            reduced_limit = 100
            limited_keywords = raw_output[:reduced_limit] if isinstance(raw_output, list) else []
            prompt_retry = prompt_template
            prompt_retry = prompt_retry.replace(
                "{intake_json}",
                json.dumps(intake, ensure_ascii=False, indent=2, default=_json_default),
            )
            prompt_retry = prompt_retry.replace(
                "{keywords_list}",
                json.dumps(limited_keywords, ensure_ascii=False, indent=2, default=_json_default),
            )
            response = _call_openai(prompt_retry)
        except Exception as e2:
            # If still rate limited, surface a clear message for the frontend
            raise RuntimeError(
                "OpenAI rate limit exceeded. Please try again later or switch to a lower-load model in admin settings."
            )
        # Retry once with smaller keyword batch to reduce tokens
        try:
            reduced_limit = 100
            limited_keywords = raw_output[:reduced_limit] if isinstance(raw_output, list) else []
            prompt_retry = prompt_template
            prompt_retry = prompt_retry.replace(
                "{intake_json}",
                json.dumps(intake, ensure_ascii=False, indent=2, default=_json_default),
            )
            prompt_retry = prompt_retry.replace(
                "{keywords_list}",
                json.dumps(limited_keywords, ensure_ascii=False, indent=2, default=_json_default),
            )
            response = _call_openai(prompt_retry)
        except Exception as e2:
            msg2 = str(e2).lower()
            is_rate_limit2 = "rate limit" in msg2 or "rate_limit_exceeded" in msg2 or "429" in msg2
            if is_rate_limit2:
                # Surface a clear message for the frontend
                raise RuntimeError(
                    "OpenAI rate limit exceeded. Please try again later or switch to a lower-load model in admin settings."
                )
            raise RuntimeError(f"OpenAI API request failed after retry: {e2}")
        except Exception as e2:
            raise RuntimeError(f"OpenAI API request failed after retry: {e2}")
    except Exception as e:
        raise RuntimeError(f"OpenAI API request failed: {e}")

    if not response.choices:
        raise RuntimeError("OpenAI returned no choices")

    # Extract token usage from response
    token_usage = {
        "prompt_tokens": getattr(response.usage, "prompt_tokens", 0) if response.usage else 0,
        "completion_tokens": getattr(response.usage, "completion_tokens", 0) if response.usage else 0,
        "total_tokens": getattr(response.usage, "total_tokens", 0) if response.usage else 0,
    }

    content = response.choices[0].message.content
    try:
        result_json = json.loads(content)
    except json.JSONDecodeError as e:
        # In case the model returns slight deviations, expose a concise error
        snippet = content[:300]
        raise ValueError(f"Invalid JSON from model: {e}: {snippet}")

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

    # Update user's total token usage in Firestore
    try:
        user_ref = db.collection("users").document(user_id)
        user_ref.update({
            "tokenUsage": gcfirestore.Increment(token_usage["total_tokens"]),
            "lastActivity": gcfirestore.SERVER_TIMESTAMP,
        })
    except Exception as e:
        # Non-fatal: log but don't fail the request
        print(f"Warning: Failed to update user token usage: {e}")

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
