import os
import json
from typing import Any, Dict, List
from openai import OpenAI
from app.services.firestore import db
from google.cloud import firestore as gcfirestore
from app.utils.blog_ideas_prompt import BLOG_IDEAS_PROMPT
from app.utils.meta_prompt import META_TAGS_PROMPT

# Initialize OpenAI client
client = OpenAI()


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
    }
    
    prompt = BLOG_IDEAS_PROMPT.replace(
        "{user_intake_form}",
        json.dumps(intake, ensure_ascii=False, indent=2, default=_json_default),
    ).replace(
        "{final_keywords}",
        json.dumps(final_keywords, ensure_ascii=False, indent=2, default=_json_default),
    )
    
    model = os.getenv("OPENAI_MODEL") or _get_model_from_settings()
    
    try:
        response = client.chat.completions.create(
            model=model,
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
    
    # Extract token usage
    token_usage = {
        "prompt_tokens": getattr(response.usage, "prompt_tokens", 0) if response.usage else 0,
        "completion_tokens": getattr(response.usage, "completion_tokens", 0) if response.usage else 0,
        "total_tokens": getattr(response.usage, "total_tokens", 0) if response.usage else 0,
    }
    
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
    
    # Update user token usage
    try:
        user_ref = db.collection("users").document(user_id)
        user_ref.update({
            "tokenUsage": gcfirestore.Increment(token_usage["total_tokens"]),
            "lastActivity": gcfirestore.SERVER_TIMESTAMP,
        })
    except Exception as e:
        print(f"Warning: Failed to update user token usage: {e}")
    
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
    }
    
    prompt = META_TAGS_PROMPT.replace(
        "{user_intake_form}",
        json.dumps(intake, ensure_ascii=False, indent=2, default=_json_default),
    ).replace(
        "{final_keywords}",
        json.dumps(final_keywords, ensure_ascii=False, indent=2, default=_json_default),
    )
    
    model = os.getenv("OPENAI_MODEL") or _get_model_from_settings()
    
    try:
        response = client.chat.completions.create(
            model=model,
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
    
    # Extract token usage
    token_usage = {
        "prompt_tokens": getattr(response.usage, "prompt_tokens", 0) if response.usage else 0,
        "completion_tokens": getattr(response.usage, "completion_tokens", 0) if response.usage else 0,
        "total_tokens": getattr(response.usage, "total_tokens", 0) if response.usage else 0,
    }
    
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
    
    # Update user token usage
    try:
        user_ref = db.collection("users").document(user_id)
        user_ref.update({
            "tokenUsage": gcfirestore.Increment(token_usage["total_tokens"]),
            "lastActivity": gcfirestore.SERVER_TIMESTAMP,
        })
    except Exception as e:
        print(f"Warning: Failed to update user token usage: {e}")
    
    # Return payload without SERVER_TIMESTAMP sentinel
    return {
        "page_title": result_json.get("page_title", ""),
        "meta_description": result_json.get("meta_description", ""),
        "notes": result_json.get("notes", {}),
        "token_usage": token_usage,
        "status": "completed",
    }
