import os
import json
from typing import Any, Dict, List, Optional

from openai import OpenAI
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

    # Build prompt with injected JSON blocks
    prompt = prompt_template
    prompt = prompt.replace("{intake_json}", json.dumps(intake, ensure_ascii=False, indent=2))
    prompt = prompt.replace("{keywords_list}", json.dumps(raw_output, ensure_ascii=False, indent=2))

    try:
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert SEO strategist and keyword analyst. "
                        "Always return strictly valid JSON — no markdown, no extra prose."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )
    except Exception as e:
        raise RuntimeError(f"OpenAI API request failed: {e}")

    if not response.choices:
        raise RuntimeError("OpenAI returned no choices")

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
        "metadata": result_json.get("metadata", {}),
        "status": "completed",
        "createdAt": gcfirestore.SERVER_TIMESTAMP,
    }

    doc_ref.set(payload)

    return payload
