import os
import json
from openai import OpenAI
from app.utils.prompts import KEYWORD_RESEARCH_PROMPT

# Initialize OpenAI client (Render reads OPENAI_API_KEY from env)
client = OpenAI()

def run_keyword_research_pipeline(intake: dict):
    """Run keyword research via OpenAI, with robust error handling.

    Returns dict with result JSON and usage metrics.
    Raises ValueError / RuntimeError for downstream handling.
    """
    prompt = KEYWORD_RESEARCH_PROMPT.format(
        intake_json=json.dumps(intake, indent=2)
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a keyword research engine. "
                        "Always return valid and clean JSON — no prose."
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
        raise ValueError(f"Invalid JSON from model: {e}: {content[:200]}")

    usage = {
        "prompt_tokens": getattr(getattr(response, "usage", None), "prompt_tokens", 0),
        "completion_tokens": getattr(getattr(response, "usage", None), "completion_tokens", 0),
        "total_tokens": getattr(getattr(response, "usage", None), "total_tokens", 0),
    }

    return {"result": result_json, "usage": usage}