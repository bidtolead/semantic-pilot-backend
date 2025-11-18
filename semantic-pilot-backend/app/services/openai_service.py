import os
import json
from openai import OpenAI
from app.utils.prompts import KEYWORD_RESEARCH_PROMPT

client = OpenAI()

def run_keyword_research_pipeline(intake: dict):
    prompt = KEYWORD_RESEARCH_PROMPT.format(
        intake_json=json.dumps(intake, indent=2)
    )

    response = client.chat.completions.create(
        model="gpt-4o-mini",  # You can upgrade later
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": "You are a keyword research engine that outputs JSON only."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
    )

    return json.loads(response.choices[0].message.content)
