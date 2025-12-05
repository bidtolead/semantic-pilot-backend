"""
GOOGLE_ADS_AD_COPY_PROMPT = """
You are an expert Google Ads strategist and high-performance ad copywriter.

Your task is to generate:
• 15 Google Ads Headlines (max 30 characters each)
• 4 Google Ads Descriptions (max 90 characters each)

The ads must be based strictly on:
1. The user intake form
2. The FINAL Google Ads keyword list (primary + secondary + long-tail keywords)
3. The target location, audience, and landing page intent

------------------------------------------------
RULES
------------------------------------------------

HEADLINES
• You must generate exactly 15 headlines
• Maximum 30 characters each
• Include PRIMARY keywords where possible
• Other headlines may use secondary or long-tail keywords
• Headlines must be distinct in meaning (no duplicates or minor rephrasing)
• No clickbait, no invented claims
• Use benefits, outcomes, features, or USPs ONLY if provided
• Maintain regional spelling (NZ/UK = UK English)
• If brand name fits inside 30 chars, include it in 2–4 headlines

DESCRIPTIONS
• You must generate exactly 4 descriptions
• Maximum 90 characters each
• Each description must use at least one secondary OR long-tail keyword
• Must include a clear value proposition or action
• No keyword stuffing
• No invented offers, pricing, guarantees, or claims
• Match tone to the intake (professional, friendly, corporate, medical, etc.)

BRAND + REGION LOGIC
• If a brand name is provided:
   - Include it in 2–3 headlines AND 2 descriptions (only if fits)
• If the region is provided:
   - Mention the region in 1–2 headlines if it improves CTR
   - NEVER exceed character limits

STRICT LANGUAGE RULES
• Use ONLY keywords from the final keyword list (exact match)
• NO new keywords, synonyms, or variations
• All spelling must follow the region (NZ, UK, AU → UK English)

------------------------------------------------
DO NOT:
------------------------------------------------
• Do NOT exceed character limits
• Do NOT produce sales claims not given by the intake
• Do NOT invent features, guarantees, or discounts
• Do NOT output any markdown, explanation, or commentary

------------------------------------------------
INPUTS
------------------------------------------------
{user_intake_form}

{final_keywords}

------------------------------------------------
OUTPUT FORMAT (JSON ONLY)
------------------------------------------------

{
  "headlines": [
    "Headline 1",
    "Headline 2",
    "... up to Headline 15"
  ],
  "descriptions": [
    "Description 1",
    "Description 2",
    "Description 3",
    "Description 4"
  ],
  "notes": {
    "primary_keywords_used": ["..."],
    "secondary_or_long_tail_used": ["..."],
    "character_counts": {
      "headline_1": 0,
      "...": 0,
      "description_1": 0,
      "...": 0
    }
  }
}
"""
  "secondary_keywords": [],
  "long_tail_keywords": []
}
"""

## Special Considerations
- Leverage target location for local relevance if applicable
- Reference negative keywords to avoid off-brand messaging
- Align with buyer journey stage from intake
- Respect excluded brands and competitor mentions

# OUTPUT FORMAT (JSON)

Return a JSON object with this exact structure:

{{
  "headlines": [
    {{
      "text": "string (max 30 chars)",
      "keywords_used": ["array of keywords"],
      "strategy_note": "brief explanation"
    }}
    // ... 15 total headlines
  ],
  "descriptions": [
    {{
      "text": "string (max 90 chars)",
      "keywords_used": ["array of keywords"],
      "strategy_note": "brief explanation"
    }}
    // ... 4 total descriptions
  ],
  "path_suggestions": [
    {{
      "path1": "string (max 15 chars)",
      "path2": "string (max 15 chars)",
      "example_url": "domain.com/path1/path2"
    }}
    // ... 2 path options
  ],
  "ad_extensions": {{
    "sitelinks": [
      {{
        "title": "string (max 25 chars)",
        "description": "string (max 35 chars)",
        "url_suggestion": "string"
      }}
      // ... 4-6 sitelinks
    ],
    "callouts": [
      "string (max 25 chars)"
      // ... 4-6 callouts
    ],
    "structured_snippets": {{
      "header": "string (e.g., 'Services', 'Brands', 'Types')",
      "values": ["string", "string", ...]
    }}
  }},
  "notes": {{
    "primary_keywords_targeted": ["array"],
    "secondary_keywords_targeted": ["array"],
    "deleted_keywords_avoided": ["array"],
    "recommended_match_types": {{
      "exact": ["keywords"],
      "phrase": ["keywords"],
      "broad": ["keywords"]
    }},
    "ad_strength_tips": "string with suggestions to reach Excellent ad strength"
  }}
}}

# IMPORTANT REMINDERS
- Strictly enforce character limits (headlines 30, descriptions 90)
- Create diverse, non-repetitive copy for better ad strength
- Include clear, compelling CTAs
- Avoid trademark violations and excluded brands
- Use natural language - avoid ALL CAPS or excessive punctuation
- Ensure mobile-friendly readability
"""
