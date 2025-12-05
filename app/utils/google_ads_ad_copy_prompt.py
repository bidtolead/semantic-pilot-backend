"""
Google Ads Ad Copy Generation Prompt Template
(Placeholder using SEO template structure - will be customized with Google Ads best practices)
"""

GOOGLE_ADS_AD_COPY_PROMPT = """
You are an expert Google Ads Strategist and PPC Keyword Architect.

Your task is to generate a structured Google Ads keyword list strictly based on:
1. The user intake form (offer, audience, location, landing page, funnel stage)
2. The raw keyword list from the DataForSEO API
3. Google Ads best-practice account structure rules

Your output will inform keyword selection, match type planning, bidding strategy, and ad group design.

------------------------------------------------
OBJECTIVE
------------------------------------------------
Select the strongest keywords for Google Ads based on:
• Commercial intent
• Relevance to the offer and landing page
• Search volume viability
• CPC ranges
• Trend data (3M + YoY)
• Competition level
• Clear match type strategy

Only use keywords from the raw keyword list. Never invent or modify keywords.

------------------------------------------------
KEYWORD SELECTION LOGIC
------------------------------------------------
Relevance = exact alignment with product/service + landing page + local audience.

Exclude keywords that:
• Indicate a different offer (e.g., online vs face-to-face if that conflicts)
• Include blocked brands or irrelevant competitor brands
• Have no commercial intent
• Are too low-volume to support paid traffic unless highly relevant

Each keyword may appear in only one group (primary/secondary/long-tail).

------------------------------------------------
KEYWORD GROUPING RULES
------------------------------------------------

PRIMARY KEYWORDS (Core targets)
• 1–2 highest commercial intent + strongest relevance
• Search volume must be viable for paid traffic
• CPC should fit expected budget
• Match type recommendation = Phrase for main targeting
• Used to form ad group names

SECONDARY KEYWORDS (Supporting targets)
• 3–6 keywords depending on volume + funnel stage
• Can include mixed intent (commercial + high-value informational)
• Still must align directly with the service

LONG-TAIL KEYWORDS (Precision, low cost, high relevance)
• 5–12 depending on search volume
• Better for exact match
• Usually lower CPC and higher CTR

------------------------------------------------
REQUIRED FIELDS FOR **EVERY** KEYWORD
------------------------------------------------

Each keyword MUST include exactly these fields:

• keyword  
• search_volume  
• trend_3m  
• trend_yoy  
• best_match_type  
• competition  
• cpc_low  
• cpc_high  
• keyword_intent  
• why_selected (max 25 words, no quotes)

Values must come EXACTLY from the raw keyword list.

------------------------------------------------
HARD RULES
------------------------------------------------
• Use ONLY keywords provided in the raw list
• Do NOT alter search volume, CPC, or trend values
• No paraphrasing or inventing keywords
• No markdown or explanation outside the JSON
• Output must be valid JSON

------------------------------------------------
INPUTS
------------------------------------------------
{intake_json}
{keywords_list}

------------------------------------------------
OUTPUT FORMAT
------------------------------------------------

Return ONLY a valid JSON object structured like this:

{
  "primary_keywords": [
    {
      "keyword": "seo course",
      "search_volume": 40,
      "trend_3m": "Stable",
      "trend_yoy": "-33.3%",
      "best_match_type": "Phrase",
      "competition": "High",
      "cpc_low": 0.67,
      "cpc_high": 2.07,
      "keyword_intent": "commercial",
      "why_selected": "High relevance, strong buying intent, and viable CPC for targeted paid campaigns."
    }
  ],
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
