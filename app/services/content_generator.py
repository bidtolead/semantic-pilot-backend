import os
import json
from typing import Any, Dict, List
from app.services.firestore import db
from google.cloud import firestore as gcfirestore
from app.utils.blog_ideas_prompt import BLOG_IDEAS_PROMPT
from app.utils.meta_prompt import META_TAGS_PROMPT
from app.utils.content_prompt import CONTENT_PROMPT
from app.utils.google_ads_ad_copy_prompt import GOOGLE_ADS_AD_COPY_PROMPT
from app.utils.google_ads_landing_page_prompt import GOOGLE_ADS_LANDING_PAGE_PROMPT
from app.utils.google_ads_negative_keywords_prompt import GOOGLE_ADS_NEGATIVE_KEYWORDS_PROMPT
from app.utils.cost_calculator import calculate_openai_cost

# Lazy initialize OpenAI client
_client = None

def get_openai_client():
    """Get or create OpenAI client (lazy initialization)."""
    global _client
    if _client is None:
        from openai import OpenAI
        _client = OpenAI()
    return _client


def _json_default(o):
    """JSON serializer for datetime objects."""
    if hasattr(o, "isoformat"):
        try:
            return o.isoformat()
        except Exception:
            return str(o)
    return str(o)


def _get_model_from_settings():
    """Get OpenAI model from Firestore settings or use default."""
    model = "gpt-4o-mini"
    try:
        settings_ref = db.collection("system_settings").document("openai")
        settings_doc = settings_ref.get()
        if settings_doc.exists:
            settings_data = settings_doc.to_dict()
            model = settings_data.get("model", "gpt-4o-mini")
    except Exception:
        pass
    return model


def _update_user_metrics(user_id: str, token_usage: dict, cost: float, model: str):
    """Update user token usage and spending."""
    try:
        user_ref = db.collection("users").document(user_id)
        user_ref.update({
            "tokenUsage": gcfirestore.Increment(token_usage.get("total_tokens", 0)),
            "promptTokens": gcfirestore.Increment(token_usage.get("prompt_tokens", 0)),
            "completionTokens": gcfirestore.Increment(token_usage.get("completion_tokens", 0)),
            "model": model,
            "totalSpend": gcfirestore.Increment(cost),
            "lastActivity": gcfirestore.SERVER_TIMESTAMP,
        })
    except Exception as e:
        pass  # Silently fail - metrics are non-critical


def generate_blog_ideas(
    *,
    intake: Dict[str, Any],
    keywords: Dict[str, List[Dict[str, Any]]],
    user_id: str,
    research_id: str,
) -> Dict[str, Any]:
    """Generate blog ideas based on intake form and final keywords."""
    
    # Format keywords for the prompt
    final_keywords = {
        "primary_keywords": keywords.get("primary_keywords", []),
        "secondary_keywords": keywords.get("secondary_keywords", []),
        "long_tail_keywords": keywords.get("long_tail_keywords", []),
        "deleted_keywords": keywords.get("deleted_keywords", []),
    }
    
    prompt = BLOG_IDEAS_PROMPT.replace(
        "{user_intake_form}",
        json.dumps(intake, ensure_ascii=False, indent=2, default=_json_default),
    ).replace(
        "{final_keywords}",
        json.dumps(final_keywords, ensure_ascii=False, indent=2, default=_json_default),
    )
    # Provide explicit guidance about deleted keywords
    if final_keywords.get("deleted_keywords"):
        prompt += "\n\nNOTE: The following keywords were explicitly removed by the user. Treat them as context only—do NOT target them directly unless essential for coherence. Removed Keywords: " + \
            ", ".join([k.get("keyword", "") if isinstance(k, dict) else str(k) for k in final_keywords["deleted_keywords"] if k])
    
    model = os.getenv("OPENAI_MODEL") or _get_model_from_settings()
    
    try:
        response = get_openai_client().chat.completions.create(
            model=model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert SEO content strategist. Always return strictly valid JSON.",
                },
                {"role": "user", "content": prompt},
            ],
        )
    except Exception as e:
        raise RuntimeError(f"OpenAI API request failed: {e}")
    
    if not response.choices:
        raise RuntimeError("OpenAI returned no choices")
    
    # Extract token usage and calculate cost
    token_usage = {
        "prompt_tokens": getattr(response.usage, "prompt_tokens", 0) if response.usage else 0,
        "completion_tokens": getattr(response.usage, "completion_tokens", 0) if response.usage else 0,
        "total_tokens": getattr(response.usage, "total_tokens", 0) if response.usage else 0,
    }
    
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
        snippet = content[:300]
        raise ValueError(f"Invalid JSON from model: {e}: {snippet}")
    
    # Save to Firestore
    doc_ref = (
        db.collection("intakes")
        .document(user_id)
        .collection(research_id)
        .document("blog_ideas")
    )
    
    # Payload for Firestore (includes SERVER_TIMESTAMP)
    firestore_payload = {
        "blog_ideas": result_json.get("blog_ideas", []),
        "token_usage": token_usage,
        "status": "completed",
        "createdAt": gcfirestore.SERVER_TIMESTAMP,
    }
    
    doc_ref.set(firestore_payload)
    
    # Update user metrics
    _update_user_metrics(user_id, token_usage, cost, model)
    
    # Update public stats counter
    try:
        blog_count = len(result_json.get("blog_ideas", []))
        db.collection("system").document("stats").update({
            "blog_ideas_created": gcfirestore.Increment(blog_count)
        })
    except Exception:
        pass  # Non-critical
    
    # Return payload without SERVER_TIMESTAMP sentinel
    return {
        "blog_ideas": result_json.get("blog_ideas", []),
        "token_usage": token_usage,
        "status": "completed",
    }


def generate_meta_tags(
    *,
    intake: Dict[str, Any],
    keywords: Dict[str, List[Dict[str, Any]]],
    user_id: str,
    research_id: str,
) -> Dict[str, Any]:
    """Generate meta tags based on intake form and final keywords."""
    
    # Format keywords for the prompt
    final_keywords = {
        "primary_keywords": keywords.get("primary_keywords", []),
        "secondary_keywords": keywords.get("secondary_keywords", []),
        "long_tail_keywords": keywords.get("long_tail_keywords", []),
        "deleted_keywords": keywords.get("deleted_keywords", []),
    }
    
    prompt = META_TAGS_PROMPT.replace(
        "{user_intake_form}",
        json.dumps(intake, ensure_ascii=False, indent=2, default=_json_default),
    ).replace(
        "{final_keywords}",
        json.dumps(final_keywords, ensure_ascii=False, indent=2, default=_json_default),
    )
    if final_keywords.get("deleted_keywords"):
        prompt += "\n\nDO NOT optimize for these removed keywords directly: " + \
            ", ".join([k.get("keyword", "") if isinstance(k, dict) else str(k) for k in final_keywords["deleted_keywords"] if k])
    
    model = os.getenv("OPENAI_MODEL") or _get_model_from_settings()
    
    try:
        response = get_openai_client().chat.completions.create(
            model=model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert SEO metadata strategist. Always return strictly valid JSON.",
                },
                {"role": "user", "content": prompt},
            ],
        )
    except Exception as e:
        raise RuntimeError(f"OpenAI API request failed: {e}")
    
    if not response.choices:
        raise RuntimeError("OpenAI returned no choices")
    
    # Extract token usage and calculate cost
    token_usage = {
        "prompt_tokens": getattr(response.usage, "prompt_tokens", 0) if response.usage else 0,
        "completion_tokens": getattr(response.usage, "completion_tokens", 0) if response.usage else 0,
        "total_tokens": getattr(response.usage, "total_tokens", 0) if response.usage else 0,
    }
    
    cost = calculate_openai_cost(
        prompt_tokens=token_usage["prompt_tokens"],
        completion_tokens=token_usage["completion_tokens"],
        model="gpt-4o-mini"
    )
    token_usage["estimated_cost_usd"] = cost
    
    content = response.choices[0].message.content
    try:
        result_json = json.loads(content)
    except json.JSONDecodeError as e:
        snippet = content[:300]
        raise ValueError(f"Invalid JSON from model: {e}: {snippet}")
    
    # Save to Firestore
    doc_ref = (
        db.collection("intakes")
        .document(user_id)
        .collection(research_id)
        .document("meta_tags")
    )
    
    # Payload for Firestore (includes SERVER_TIMESTAMP)
    firestore_payload = {
        "page_title": result_json.get("page_title", ""),
        "meta_description": result_json.get("meta_description", ""),
        "notes": result_json.get("notes", {}),
        "token_usage": token_usage,
        "status": "completed",
        "createdAt": gcfirestore.SERVER_TIMESTAMP,
    }
    
    doc_ref.set(firestore_payload)
    
    # Update user metrics
    _update_user_metrics(user_id, token_usage, cost)
    
    # Update public stats counter
    try:
        db.collection("system").document("stats").update({
            "meta_tags_generated": gcfirestore.Increment(1)
        })
    except Exception:
        pass  # Non-critical
    
    # Return payload without SERVER_TIMESTAMP sentinel
    return {
        "page_title": result_json.get("page_title"),
        "meta_description": result_json.get("meta_description"),
        "notes": result_json.get("notes"),
        "token_usage": token_usage,
        "status": "completed",
    }


def generate_page_content(
    *,
    intake: Dict[str, Any],
    keywords: Dict[str, List[Dict[str, Any]]],
    user_id: str,
    research_id: str,
) -> Dict[str, Any]:
    """Generate full page content draft based on intake form and final keywords."""
    
    # Format keywords for the prompt
    final_keywords = {
        "primary_keywords": keywords.get("primary_keywords", []),
        "secondary_keywords": keywords.get("secondary_keywords", []),
        "long_tail_keywords": keywords.get("long_tail_keywords", []),
        "deleted_keywords": keywords.get("deleted_keywords", []),
    }
    
    prompt = CONTENT_PROMPT.replace(
        "{user_intake_form}",
        json.dumps(intake, ensure_ascii=False, indent=2, default=_json_default),
    ).replace(
        "{final_keywords}",
        json.dumps(final_keywords, ensure_ascii=False, indent=2, default=_json_default),
    )
    if final_keywords.get("deleted_keywords"):
        prompt += "\n\nAvoid focusing on removed keywords; treat them only as context: " + \
            ", ".join([k.get("keyword", "") if isinstance(k, dict) else str(k) for k in final_keywords["deleted_keywords"] if k])
    
    model = os.getenv("OPENAI_MODEL") or _get_model_from_settings()
    
    try:
        response = get_openai_client().chat.completions.create(
            model=model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert SEO content strategist. Always return strictly valid JSON.",
                },
                {"role": "user", "content": prompt},
            ],
        )
    except Exception as e:
        raise RuntimeError(f"OpenAI API request failed: {e}")
    
    if not response.choices:
        raise RuntimeError("OpenAI returned no choices")
    
    # Extract token usage and calculate cost
    token_usage = {
        "prompt_tokens": getattr(response.usage, "prompt_tokens", 0) if response.usage else 0,
        "completion_tokens": getattr(response.usage, "completion_tokens", 0) if response.usage else 0,
        "total_tokens": getattr(response.usage, "total_tokens", 0) if response.usage else 0,
    }
    
    cost = calculate_openai_cost(
        prompt_tokens=token_usage["prompt_tokens"],
        completion_tokens=token_usage["completion_tokens"],
        model="gpt-4o-mini"
    )
    token_usage["estimated_cost_usd"] = cost
    
    content = response.choices[0].message.content
    try:
        result_json = json.loads(content)
    except json.JSONDecodeError as e:
        snippet = content[:300]
        raise ValueError(f"Invalid JSON from model: {e}: {snippet}")
    
    # Save to Firestore
    doc_ref = (
        db.collection("intakes")
        .document(user_id)
        .collection(research_id)
        .document("page_content")
    )
    
    # Payload for Firestore (includes SERVER_TIMESTAMP)
    firestore_payload = {
        "h1": result_json.get("h1", ""),
        "intro": result_json.get("intro", ""),
        "sections": result_json.get("sections", []),
        "faq": result_json.get("faq", []),
        "cta": result_json.get("cta", ""),
        "token_usage": token_usage,
        "status": "completed",
        "createdAt": gcfirestore.SERVER_TIMESTAMP,
    }
    
    doc_ref.set(firestore_payload)
    
    # Update user metrics
    _update_user_metrics(user_id, token_usage, cost)
    
    # Return payload without SERVER_TIMESTAMP sentinel    # Return payload without SERVER_TIMESTAMP sentinel
    return {
        "h1": result_json.get("h1", ""),
        "intro": result_json.get("intro", ""),
        "sections": result_json.get("sections", []),
        "faq": result_json.get("faq", []),
        "cta": result_json.get("cta", ""),
        "token_usage": token_usage,
        "status": "completed",
    }


def generate_google_ads_ad_copy(
    *,
    intake: Dict[str, Any],
    keywords: Dict[str, List[Dict[str, Any]]],
    user_id: str,
    research_id: str,
) -> Dict[str, Any]:
    """Generate Google Ads ad copy based on intake form and final keywords."""
    
    # Format keywords for the prompt
    final_keywords = {
        "primary_keywords": keywords.get("primary_keywords", []),
        "secondary_keywords": keywords.get("secondary_keywords", []),
        "long_tail_keywords": keywords.get("long_tail_keywords", []),
        "deleted_keywords": keywords.get("deleted_keywords", []),
    }
    
    prompt = GOOGLE_ADS_AD_COPY_PROMPT.replace(
        "{user_intake_form}",
        json.dumps(intake, ensure_ascii=False, indent=2, default=_json_default),
    ).replace(
        "{final_keywords}",
        json.dumps(final_keywords, ensure_ascii=False, indent=2, default=_json_default),
    )
    
    model = os.getenv("OPENAI_MODEL") or _get_model_from_settings()
    
    try:
        response = get_openai_client().chat.completions.create(
            model=model,
            temperature=0.3,  # Slightly higher for creative ad copy
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert Google Ads copywriter. Always return strictly valid JSON.",
                },
                {"role": "user", "content": prompt},
            ],
        )
    except Exception as e:
        raise RuntimeError(f"OpenAI API request failed: {e}")
    
    if not response.choices:
        raise RuntimeError("OpenAI returned no choices")
    
    # Extract token usage and calculate cost
    token_usage = {
        "prompt_tokens": getattr(response.usage, "prompt_tokens", 0) if response.usage else 0,
        "completion_tokens": getattr(response.usage, "completion_tokens", 0) if response.usage else 0,
        "total_tokens": getattr(response.usage, "total_tokens", 0) if response.usage else 0,
    }
    
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
        snippet = content[:300]
        raise ValueError(f"Invalid JSON from model: {e}: {snippet}")
    
    # Save to Firestore
    doc_ref = (
        db.collection("intakes")
        .document(user_id)
        .collection(research_id)
        .document("ad_copy")
    )
    
    firestore_payload = {
        **result_json,
        "token_usage": token_usage,
        "status": "completed",
        "createdAt": gcfirestore.SERVER_TIMESTAMP,
    }
    
    doc_ref.set(firestore_payload)
    
    # Update user metrics
    _update_user_metrics(user_id, token_usage, cost, model)
    
    return {
        **result_json,
        "token_usage": token_usage,
        "status": "completed",
    }


def generate_google_ads_landing_page(
    *,
    intake: Dict[str, Any],
    keywords: Dict[str, List[Dict[str, Any]]],
    user_id: str,
    research_id: str,
) -> Dict[str, Any]:
    """Generate Google Ads landing page recommendations."""
    
    final_keywords = {
        "primary_keywords": keywords.get("primary_keywords", []),
        "secondary_keywords": keywords.get("secondary_keywords", []),
        "long_tail_keywords": keywords.get("long_tail_keywords", []),
        "deleted_keywords": keywords.get("deleted_keywords", []),
    }
    
    prompt = GOOGLE_ADS_LANDING_PAGE_PROMPT.replace(
        "{user_intake_form}",
        json.dumps(intake, ensure_ascii=False, indent=2, default=_json_default),
    ).replace(
        "{final_keywords}",
        json.dumps(final_keywords, ensure_ascii=False, indent=2, default=_json_default),
    )
    
    model = os.getenv("OPENAI_MODEL") or _get_model_from_settings()
    
    try:
        response = get_openai_client().chat.completions.create(
            model=model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert landing page optimization specialist. Always return strictly valid JSON.",
                },
                {"role": "user", "content": prompt},
            ],
        )
    except Exception as e:
        raise RuntimeError(f"OpenAI API request failed: {e}")
    
    if not response.choices:
        raise RuntimeError("OpenAI returned no choices")
    
    token_usage = {
        "prompt_tokens": getattr(response.usage, "prompt_tokens", 0) if response.usage else 0,
        "completion_tokens": getattr(response.usage, "completion_tokens", 0) if response.usage else 0,
        "total_tokens": getattr(response.usage, "total_tokens", 0) if response.usage else 0,
    }
    
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
        snippet = content[:300]
        raise ValueError(f"Invalid JSON from model: {e}: {snippet}")
    
    doc_ref = (
        db.collection("intakes")
        .document(user_id)
        .collection(research_id)
        .document("landing_page")
    )
    
    firestore_payload = {
        **result_json,
        "token_usage": token_usage,
        "status": "completed",
        "createdAt": gcfirestore.SERVER_TIMESTAMP,
    }
    
    doc_ref.set(firestore_payload)
    _update_user_metrics(user_id, token_usage, cost, model)
    
    return {
        **result_json,
        "token_usage": token_usage,
        "status": "completed",
    }


def generate_google_ads_negative_keywords(
    *,
    intake: Dict[str, Any],
    keywords: Dict[str, List[Dict[str, Any]]],
    user_id: str,
    research_id: str,
) -> Dict[str, Any]:
    """Generate negative keyword recommendations for Google Ads."""
    
    final_keywords = {
        "primary_keywords": keywords.get("primary_keywords", []),
        "secondary_keywords": keywords.get("secondary_keywords", []),
        "long_tail_keywords": keywords.get("long_tail_keywords", []),
        "deleted_keywords": keywords.get("deleted_keywords", []),
    }
    
    prompt = GOOGLE_ADS_NEGATIVE_KEYWORDS_PROMPT.replace(
        "{user_intake_form}",
        json.dumps(intake, ensure_ascii=False, indent=2, default=_json_default),
    ).replace(
        "{final_keywords}",
        json.dumps(final_keywords, ensure_ascii=False, indent=2, default=_json_default),
    )
    
    model = os.getenv("OPENAI_MODEL") or _get_model_from_settings()
    
    try:
        response = get_openai_client().chat.completions.create(
            model=model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert Google Ads negative keyword strategist. Always return strictly valid JSON.",
                },
                {"role": "user", "content": prompt},
            ],
        )
    except Exception as e:
        raise RuntimeError(f"OpenAI API request failed: {e}")
    
    if not response.choices:
        raise RuntimeError("OpenAI returned no choices")
    
    token_usage = {
        "prompt_tokens": getattr(response.usage, "prompt_tokens", 0) if response.usage else 0,
        "completion_tokens": getattr(response.usage, "completion_tokens", 0) if response.usage else 0,
        "total_tokens": getattr(response.usage, "total_tokens", 0) if response.usage else 0,
    }
    
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
        snippet = content[:300]
        raise ValueError(f"Invalid JSON from model: {e}: {snippet}")
    
    doc_ref = (
        db.collection("intakes")
        .document(user_id)
        .collection(research_id)
        .document("negative_keywords")
    )
    
    firestore_payload = {
        **result_json,
        "token_usage": token_usage,
        "status": "completed",
        "createdAt": gcfirestore.SERVER_TIMESTAMP,
    }
    
    doc_ref.set(firestore_payload)
    _update_user_metrics(user_id, token_usage, cost, model)
    
    return {
        **result_json,
        "token_usage": token_usage,
        "status": "completed",
    }
