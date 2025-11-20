import os
import json
from openai import OpenAI
from app.utils.prompts import KEYWORD_RESEARCH_PROMPT

# Initialize OpenAI client (Render reads OPENAI_API_KEY from env)
client = OpenAI()

def run_keyword_research_pipeline(intake: dict):
    """
    Runs the keyword research pipeline using GPT-4o-mini
    and returns both the parsed JSON output + token usage.
    """

    # Inject intake into prompt (as formatted JSON)
    prompt = KEYWORD_RESEARCH_PROMPT.format(
        intake_json=json.dumps(intake, indent=2)
    )

    # -----------------------------
    # 🧠 Call OpenAI API
    # -----------------------------
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a keyword research engine. "
                    "Always return valid and clean JSON — no prose."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
    )

    # -----------------------------
    # Extract assistant JSON output
    # -----------------------------
    content = response.choices[0].message.content
    result_json = json.loads(content)

    # -----------------------------
    # Extract token usage
    # -----------------------------
    usage = {
        "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
        "completion_tokens": response.usage.completion_tokens if response.usage else 0,
        "total_tokens": response.usage.total_tokens if response.usage else 0,
    }

    return {
        "result": result_json,
        "usage": usage
    }