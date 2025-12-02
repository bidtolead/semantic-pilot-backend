"""
Google Ads Negative Keywords Prompt Template
"""

GOOGLE_ADS_NEGATIVE_KEYWORDS_PROMPT = """
You are a Google Ads negative keyword strategist focused on improving campaign ROI by eliminating wasteful ad spend.

Given the following user intake form and keyword research results, generate a comprehensive negative keyword list to prevent ads from showing for irrelevant searches.

# USER INTAKE FORM
{user_intake_form}

# FINAL KEYWORDS
{final_keywords}

# REQUIREMENTS

## Negative Keyword Categories
1. **Job Seekers**: careers, jobs, hiring, employment, resume, salary
2. **Free/Cheap Seekers**: free, cheap, discount, coupon, deal (if premium brand)
3. **DIY/How-To**: DIY, how to make, tutorial, instructions (if service-based)
4. **Informational Only**: definition, what is, meaning, wiki, information
5. **Competitors**: Brand names from excluded_brands field
6. **Geographic Mismatches**: Locations outside target area
7. **Wrong Product/Service**: Similar but different offerings
8. **Academic/Research**: study, research, thesis, project, school
9. **Wholesale/Bulk** (if B2C): wholesale, bulk, distributor
10. **Adult/Inappropriate**: Filter obvious bad traffic

## Match Type Strategy
- **Exact Match** `[keyword]`: Block specific phrases
- **Phrase Match** `"keyword"`: Block phrases containing term
- **Broad Match** `keyword`: Block broad variations (use sparingly)

## Business-Specific Analysis
- Analyze product_service_description to identify non-relevant searches
- Use negative_keywords field from intake as seed list
- Consider buyer_journey_stage - exclude opposite stages
- Review USPs to identify what you're NOT offering

# OUTPUT FORMAT (JSON)

Return a JSON object with this exact structure:

{{
  "negative_keywords_by_category": {{
    "job_seekers": {{
      "keywords": ["careers", "jobs", "hiring", "employment", "resume"],
      "match_type": "phrase",
      "rationale": "Excludes job seekers searching for employment opportunities"
    }},
    "price_sensitive": {{
      "keywords": ["free", "cheap", "discount", "coupon"],
      "match_type": "phrase",
      "rationale": "string"
    }},
    "diy_how_to": {{
      "keywords": ["array"],
      "match_type": "phrase | broad",
      "rationale": "string"
    }},
    "informational_only": {{
      "keywords": ["array"],
      "match_type": "phrase",
      "rationale": "string"
    }},
    "competitors": {{
      "keywords": ["array - from excluded_brands + common misspellings"],
      "match_type": "phrase | exact",
      "rationale": "string"
    }},
    "geographic": {{
      "keywords": ["array - cities/regions outside target"],
      "match_type": "phrase",
      "rationale": "string"
    }},
    "wrong_product_category": {{
      "keywords": ["array - similar but different products/services"],
      "match_type": "phrase | broad",
      "rationale": "string"
    }},
    "academic_research": {{
      "keywords": ["array"],
      "match_type": "phrase",
      "rationale": "string"
    }},
    "custom_exclusions": {{
      "keywords": ["array - business-specific exclusions from intake negative_keywords"],
      "match_type": "phrase | exact",
      "rationale": "string"
    }}
  }},
  "consolidated_list": {{
    "exact_match": [
      "[keyword]"
      // ... exact match negatives
    ],
    "phrase_match": [
      "\\"keyword phrase\\""
      // ... phrase match negatives
    ],
    "broad_match": [
      "keyword"
      // ... broad match negatives (use sparingly)
    ]
  }},
  "campaign_level_negatives": [
    "string - negatives to apply across all ad groups"
  ],
  "ad_group_level_negatives": {{
    "primary_keywords_ad_group": ["array - specific to primary KW ad group"],
    "secondary_keywords_ad_group": ["array - specific to secondary KW ad group"],
    "long_tail_ad_group": ["array - specific to long-tail ad group"]
  }},
  "monitoring_recommendations": {{
    "search_terms_to_watch": ["array - terms to monitor in search query reports"],
    "review_frequency": "weekly | bi-weekly - recommended review cadence",
    "expansion_opportunities": "string - how to identify new negative keywords over time"
  }},
  "notes": {{
    "total_negative_keywords": "number",
    "estimated_impression_reduction": "string - rough estimate of traffic filtered",
    "roi_impact": "string - how this improves campaign performance",
    "deleted_keywords_context": "string - how user's deleted keywords informed this list"
  }}
}}

# IMPORTANT REMINDERS
- Start conservative - you can always add more negatives later
- Don't block legitimate traffic variations
- Use phrase match as default - broad match blocks too much
- Include common misspellings of competitor brands
- Consider seasonality and trends
- Leverage user's negative_keywords input as high-priority exclusions
- Avoid blocking your own primary keywords or close variants
- Include negative keywords from deleted_keywords that indicate wrong intent
"""
