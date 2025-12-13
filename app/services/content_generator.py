import os
import json
from typing import Any, Dict, List
from app.services.firestore import db
from google.cloud import firestore as gcfirestore
from app.utils.blog_ideas_prompt import BLOG_IDEAS_PROMPT
from app.utils.blog_draft_prompt import BLOG_DRAFT_PROMPT
from app.utils.meta_prompt import META_TAGS_PROMPT
from app.utils.content_prompt import CONTENT_PROMPT
from app.utils.google_ads_ad_copy_prompt import GOOGLE_ADS_AD_COPY_PROMPT
from app.utils.google_ads_landing_page_prompt import GOOGLE_ADS_LANDING_PAGE_PROMPT
from app.utils.google_ads_negative_keywords_prompt import GOOGLE_ADS_NEGATIVE_KEYWORDS_PROMPT
from app.utils.google_ads_structure_prompt import GOOGLE_ADS_STRUCTURE_PROMPT
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
        except Exception as e:
            import logging
            logging.warning(f"Failed to serialize datetime object: {e}")
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
    except Exception as e:
        import logging
        logging.warning(f"Failed to fetch model from settings: {e}")
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
        import logging
        logging.warning(f"Failed to update user metrics for {user_id}: {e}")


def generate_blog_ideas(
    *,
    intake: Dict[str, Any] = None,
    keywords: Dict[str, List[Dict[str, Any]]] = None,
    user_id: str = None,
    research_id: str = None,
    primary_keywords: List[str] = None,
    secondary_keywords: List[str] = None,
    long_tail_keywords: List[str] = None,
    user_intake_form: Dict[str, Any] = None,
    research_data: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """Generate blog ideas based on intake form and final keywords.
    
    Can be called in two ways:
    1. Old: intake, keywords, user_id, research_id (from GET endpoint)
    2. New: primary_keywords, secondary_keywords, long_tail_keywords, user_intake_form, user_id (from POST endpoint)
    """
    
    # Handle new POST endpoint calling style
    if primary_keywords is not None or user_intake_form is not None:
        intake = user_intake_form or {}
        keywords = {
            "primary_keywords": primary_keywords or [],
            "secondary_keywords": secondary_keywords or [],
            "long_tail_keywords": long_tail_keywords or [],
            "deleted_keywords": [],
        }
    
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
    
    # Save to Firestore if research_id is provided
    if research_id:
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
        
        # Update public stats counter
        try:
            blog_count = len(result_json.get("blog_ideas", []))
            db.collection("system").document("stats").update({
                "blog_ideas_created": gcfirestore.Increment(blog_count)
            })
        except Exception:
            pass  # Non-critical
    
    # Update user metrics
    _update_user_metrics(user_id, token_usage, cost, model)
    
    # Return payload without SERVER_TIMESTAMP sentinel
    return {
        "blog_ideas": result_json.get("blog_ideas", []),
        "token_usage": token_usage,
        "status": "completed",
    }


def generate_meta_tags(
    *,
    intake: Dict[str, Any] = None,
    keywords: Dict[str, List[Dict[str, Any]]] = None,
    user_id: str = None,
    research_id: str = None,
    primary_keywords: List[str] = None,
    secondary_keywords: List[str] = None,
    long_tail_keywords: List[str] = None,
    user_intake_form: Dict[str, Any] = None,
    research_data: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """Generate meta tags based on intake form and final keywords.
    
    Can be called in two ways:
    1. Old: intake, keywords, user_id, research_id (from GET endpoint)
    2. New: primary_keywords, secondary_keywords, long_tail_keywords, user_intake_form, user_id (from POST endpoint)
    """
    
    # Handle new POST endpoint calling style
    if primary_keywords is not None or user_intake_form is not None:
        intake = user_intake_form or {}
        keywords = {
            "primary_keywords": primary_keywords or [],
            "secondary_keywords": secondary_keywords or [],
            "long_tail_keywords": long_tail_keywords or [],
            "deleted_keywords": [],
        }
    
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
    
    # Save to Firestore if research_id is provided
    if research_id:
        doc_ref = (
            db.collection("intakes")
            .document(user_id)
            .collection(research_id)
            .document("meta_tags")
        )
        
        # Payload for Firestore (includes SERVER_TIMESTAMP)
        firestore_payload = {
            "page_title_variations": result_json.get("page_title_variations", []),
            "meta_description_variations": result_json.get("meta_description_variations", []),
            "notes": result_json.get("notes", {}),
            "token_usage": token_usage,
            "status": "completed",
            "createdAt": gcfirestore.SERVER_TIMESTAMP,
        }
        
        doc_ref.set(firestore_payload)
        
        # Update public stats counter
        try:
            db.collection("system").document("stats").update({
                "meta_tags_generated": gcfirestore.Increment(1)
            })
        except Exception:
            pass  # Non-critical
    
    # Update user metrics
    _update_user_metrics(user_id, token_usage, cost, model)
    
    # Return payload without SERVER_TIMESTAMP sentinel
    return {
        "page_title_variations": result_json.get("page_title_variations", []),
        "meta_description_variations": result_json.get("meta_description_variations", []),
        "notes": result_json.get("notes", {}),
        "token_usage": token_usage,
        "status": "completed",
    }


def generate_page_content(
    *,
    intake: Dict[str, Any] = None,
    keywords: Dict[str, List[Dict[str, Any]]] = None,
    user_id: str = None,
    research_id: str = None,
    primary_keywords: List[str] = None,
    secondary_keywords: List[str] = None,
    long_tail_keywords: List[str] = None,
    user_intake_form: Dict[str, Any] = None,
    research_data: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """Generate full page content draft based on intake form and final keywords.
    
    Can be called in two ways:
    1. Old: intake, keywords, user_id, research_id (from GET endpoint)
    2. New: primary_keywords, secondary_keywords, long_tail_keywords, user_intake_form, user_id (from POST endpoint)
    """
    
    # Handle new POST endpoint calling style
    if primary_keywords is not None or user_intake_form is not None:
        intake = user_intake_form or {}
        keywords = {
            "primary_keywords": primary_keywords or [],
            "secondary_keywords": secondary_keywords or [],
            "long_tail_keywords": long_tail_keywords or [],
            "deleted_keywords": [],
        }
    
    # Format keywords for the prompt
    final_keywords = {
        "primary_keywords": keywords.get("primary_keywords", []) if keywords else [],
        "secondary_keywords": keywords.get("secondary_keywords", []) if keywords else [],
        "long_tail_keywords": keywords.get("long_tail_keywords", []) if keywords else [],
        "deleted_keywords": keywords.get("deleted_keywords", []) if keywords else [],
    }
    
    # Check if this is a blog post - use dedicated blog prompt
    is_blog_post = (
        intake.get("page_type") == "blog_post" or 
        intake.get("content_style") == "informational_blog" or
        "blog" in str(intake.get("page_type", "")).lower()
    )
    
    selected_prompt = BLOG_DRAFT_PROMPT if is_blog_post else CONTENT_PROMPT
    
    prompt = selected_prompt.replace(
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
        model=model
    )
    token_usage["estimated_cost_usd"] = cost
    
    content = response.choices[0].message.content
    try:
        result_json = json.loads(content)
    except json.JSONDecodeError as e:
        snippet = content[:300]
        raise ValueError(f"Invalid JSON from model: {e}: {snippet}")
    
    # Validate external link is present if this is a blog post
    if is_blog_post:
        has_external_link = False
        
        # Check intro for external link
        if "intro" in result_json and result_json["intro"]:
            intro_content = result_json["intro"]
            if "[" in intro_content and "](" in intro_content and "http" in intro_content:
                has_external_link = True
        
        # Check sections for external link
        if not has_external_link and "sections" in result_json and isinstance(result_json["sections"], list):
            for section in result_json["sections"]:
                section_content = section.get("content", "")
                # Check for markdown link pattern [text](url)
                if "[" in section_content and "](" in section_content and "http" in section_content:
                    has_external_link = True
                    break
        
        if not has_external_link:
            print(f"[WARNING] Blog post missing external link - attempting to add one intelligently")
            # Find appropriate anchor text in the intro and convert it to a link
            import re
            link_added = False
            
            if "intro" in result_json and result_json["intro"]:
                intro = result_json["intro"]
                
                # Try to find the first occurrence of the primary keyword or a related term
                # and make that a Wikipedia link
                primary_kw = primary_keywords[0] if primary_keywords else ""
                
                # Look for the keyword (case-insensitive)
                if primary_kw:
                    # Try exact match first
                    pattern = re.compile(r'\b(' + re.escape(primary_kw) + r')\b', re.IGNORECASE)
                    match = pattern.search(intro)
                    
                    if match:
                        # Found the keyword - replace first occurrence with link
                        matched_text = match.group(1)
                        # Convert to title case for better Wikipedia URL
                        wiki_term = primary_kw.title()
                        wikipedia_url = f"https://en.wikipedia.org/wiki/{wiki_term.replace(' ', '_')}"
                        intro_with_link = pattern.sub(f"[{matched_text}]({wikipedia_url})", intro, count=1)
                        result_json["intro"] = intro_with_link
                        link_added = True
                        print(f"[INFO] Added Wikipedia link to '{matched_text}' in intro")
                
                if not link_added:
                    # Fallback: find first noun phrase or capitalize words (likely topic)
                    # Look for sequences of 1-4 capitalized words
                    cap_pattern = re.compile(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\b')
                    cap_match = cap_pattern.search(intro)
                    
                    if cap_match:
                        anchor_text = cap_match.group(1)
                        wikipedia_url = f"https://en.wikipedia.org/wiki/{anchor_text.replace(' ', '_')}"
                        intro_with_link = intro.replace(anchor_text, f"[{anchor_text}]({wikipedia_url})", 1)
                        result_json["intro"] = intro_with_link
                        link_added = True
                        print(f"[INFO] Added Wikipedia link to '{anchor_text}' in intro")
            
            # If still no link added, try to add it to the first section
            if not link_added and "sections" in result_json and isinstance(result_json["sections"], list) and len(result_json["sections"]) > 0:
                first_section = result_json["sections"][0]
                section_content = first_section.get("content", "")
                
                primary_kw = primary_keywords[0] if primary_keywords else ""
                if primary_kw and section_content:
                    pattern = re.compile(r'\b(' + re.escape(primary_kw) + r')\b', re.IGNORECASE)
                    match = pattern.search(section_content)
                    
                    if match:
                        matched_text = match.group(1)
                        wiki_term = primary_kw.title()
                        wikipedia_url = f"https://en.wikipedia.org/wiki/{wiki_term.replace(' ', '_')}"
                        section_with_link = pattern.sub(f"[{matched_text}]({wikipedia_url})", section_content, count=1)
                        result_json["sections"][0]["content"] = section_with_link
                        link_added = True
                        print(f"[INFO] Added Wikipedia link to '{matched_text}' in first section")
            
            # Absolute last resort: add generic link to intro
            if not link_added:
                if "intro" in result_json and result_json["intro"]:
                    result_json["intro"] += " [Learn more on Wikipedia](https://en.wikipedia.org)."
                    print(f"[INFO] Added generic Wikipedia link as last resort")
    
    # Update user metrics
    _update_user_metrics(user_id, token_usage, cost, model)
    
    # Generate meta tags (fallback only; primary source is blog prompt)
    meta_tags_result = generate_meta_tags(
        primary_keywords=primary_keywords or (keywords.get("primary_keywords", []) if keywords else []),
        secondary_keywords=secondary_keywords or (keywords.get("secondary_keywords", []) if keywords else []),
        long_tail_keywords=long_tail_keywords or (keywords.get("long_tail_keywords", []) if keywords else []),
        user_intake_form=intake,
        user_id=user_id,
        research_id=research_id,
    )

    # Prefer blog-prompt title/description; fallback to meta tags if absent (ONLY for blog posts)
    if is_blog_post:
        page_title_variations = result_json.get("page_title_variations") or []
        if not page_title_variations:
            if result_json.get("page_title"):
                page_title_variations = [{"title": result_json.get("page_title") }]
            elif result_json.get("h1"):
                page_title_variations = [{"title": result_json.get("h1") }]
        if not page_title_variations:
            page_title_variations = meta_tags_result.get("page_title_variations", [])

        meta_description_variations = result_json.get("meta_description_variations") or []
        if not meta_description_variations and result_json.get("meta_description"):
            meta_description_variations = [{"description": result_json.get("meta_description") }]
        if not meta_description_variations and result_json.get("intro"):
            meta_description_variations = [{"description": result_json.get("intro") }]
        if not meta_description_variations:
            meta_description_variations = meta_tags_result.get("meta_description_variations", [])
    else:
        # For regular page content, use ONLY meta-tags generator output
        page_title_variations = meta_tags_result.get("page_title_variations", [])
        meta_description_variations = meta_tags_result.get("meta_description_variations", [])
    
    # Save to Firestore if research_id is provided
    if research_id:
        doc_ref = (
            db.collection("intakes")
            .document(user_id)
            .collection(research_id)
            .document("page_content")
        )
        
        # For blogs, include blog-generated SEO fields; for regular content, use meta-tags only
        if is_blog_post:
            firestore_payload = {
                "h1": result_json.get("h1", ""),
                "intro": result_json.get("intro", ""),
                "sections": result_json.get("sections", []),
                "faq": result_json.get("faq", []),
                "cta": result_json.get("cta", ""),
                "page_title": result_json.get("page_title", ""),
                "meta_description": result_json.get("meta_description", ""),
                "page_title_variations": page_title_variations,
                "meta_description_variations": meta_description_variations,
                "token_usage": token_usage,
                "status": "completed",
                "createdAt": gcfirestore.SERVER_TIMESTAMP,
            }
        else:
            # Regular page content uses meta-tags generator output
            firestore_payload = {
                "h1": result_json.get("h1", ""),
                "intro": result_json.get("intro", ""),
                "sections": result_json.get("sections", []),
                "faq": result_json.get("faq", []),
                "cta": result_json.get("cta", ""),
                "page_title_variations": meta_tags_result.get("page_title_variations", []),
                "meta_description_variations": meta_tags_result.get("meta_description_variations", []),
                "token_usage": token_usage,
                "status": "completed",
                "createdAt": gcfirestore.SERVER_TIMESTAMP,
            }
        
        doc_ref.set(firestore_payload)
    
    # Return payload: blogs get blog-generated SEO fields, regular content uses meta-tags
    if is_blog_post:
        return {
            "h1": result_json.get("h1", ""),
            "intro": result_json.get("intro", ""),
            "sections": result_json.get("sections", []),
            "faq": result_json.get("faq", []),
            "cta": result_json.get("cta", ""),
            "page_title": result_json.get("page_title", ""),
            "meta_description": result_json.get("meta_description", ""),
            "page_title_variations": page_title_variations,
            "meta_description_variations": meta_description_variations,
            "meta_notes": meta_tags_result.get("notes", {}),
            "token_usage": token_usage,
            "status": "completed",
        }
    else:
        # Regular page content: content from CONTENT_PROMPT, titles/descriptions from meta-tags
        return {
            "h1": result_json.get("h1", ""),
            "intro": result_json.get("intro", ""),
            "sections": result_json.get("sections", []),
            "faq": result_json.get("faq", []),
            "cta": result_json.get("cta", ""),
            "page_title_variations": meta_tags_result.get("page_title_variations", []),
            "meta_description_variations": meta_tags_result.get("meta_description_variations", []),
            "meta_notes": meta_tags_result.get("notes", {}),
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

def generate_google_ads_structure(
    *,
    intake: Dict[str, Any],
    keywords: Dict[str, List[Dict[str, Any]]],
    user_id: str,
    research_id: str,
) -> Dict[str, Any]:
    """Generate Google Ads campaign structure."""
    
    final_keywords = {
        "primary_keywords": keywords.get("primary_keywords", []),
        "secondary_keywords": keywords.get("secondary_keywords", []),
        "long_tail_keywords": keywords.get("long_tail_keywords", []),
        "deleted_keywords": keywords.get("deleted_keywords", []),
    }
    
    prompt = GOOGLE_ADS_STRUCTURE_PROMPT.replace(
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
                    "content": "You are an expert Google Ads campaign strategist. Always return strictly valid JSON.",
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
        .document("structure")
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
