"""
Google Ads Ad Copy Generation Prompt Template
(Placeholder using SEO template structure - will be customized with Google Ads best practices)
"""

GOOGLE_ADS_AD_COPY_PROMPT = """
You are an expert Google Ads copywriter specializing in high-converting PPC campaigns.

Given the following user intake form and keyword research results, generate compelling Google Ads copy optimized for click-through rate (CTR) and conversions.

# USER INTAKE FORM
{user_intake_form}

# FINAL KEYWORDS
{final_keywords}

# REQUIREMENTS

## Ad Format Guidelines
- **Headlines**: Create 15 headlines (max 30 characters each)
- **Descriptions**: Create 4 descriptions (max 90 characters each)
- **Path Fields**: Suggest 2 path options (max 15 characters each)

## Copy Strategy
1. **Headlines**: Mix of keyword-focused, benefit-driven, and unique value propositions
2. **Descriptions**: Focus on USPs, calls-to-action, and social proof
3. **Character Limits**: Strictly adhere to Google Ads character limits
4. **Ad Strength**: Aim for "Excellent" ad strength with diverse, relevant copy

## Keyword Integration
- Incorporate primary keywords naturally in headlines
- Use dynamic keyword insertion (DKI) suggestions where appropriate
- Avoid keyword stuffing while maintaining relevance

## Tone & Style
- Match the business tone from intake form
- Use action-oriented language
- Include clear CTAs (e.g., "Get Quote", "Shop Now", "Learn More")
- Highlight competitive advantages and USPs from intake

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
