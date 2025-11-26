KEYWORD_RESEARCH_PROMPT = """
You are an expert SEO strategist and keyword analyst.

Your task is to generate structured keyword recommendations strictly and exclusively based on:
1. The intake data (target audience, service, location, funnel stage, etc.)
2. The raw keyword list provided from the Google Keyword Planner API

---

OBJECTIVE

Generate keywords to optimise the target page for:
• Best-practice SEO/GEO performance
• Inclusion in Google AI Overviews (AIO)
• Natural, reader-friendly content aligned with the specified word count

Focus: Best SEO/GEO content strategies.

---

STRUCTURE AND WORD COUNT LOGIC

Return a single valid JSON object with these sections:

• primary_keywords (1–2)  
• secondary_keywords (2–6 depending on word count)  
• long_tail_keywords (3–15 depending on word count)

Rules:
• Prioritise high-volume keywords for primary group
• Ensure long-tail keywords reflect specific intent and are exact matches from the raw keyword list
• DO NOT generate keywords not present in the provided keyword list

---

REGIONAL SPELLING

Use UK English for: New Zealand, UK, Australia

---

EACH KEYWORD MUST INCLUDE:

• keyword: exact match from raw keyword list  
• search_volume: copy EXACTLY from "avg_monthly_searches" field in raw data (do not modify, round, or estimate)
  Example: if raw data shows {"keyword": "seo course", "avg_monthly_searches": 40}, you MUST output "search_volume": 40
• location: target location from intake data
• trend_3m: realistic 3-month trend (e.g., "+5%", "Stable", "-3%")
• trend_yoy: realistic year-over-year trend (e.g., "+10%", "+8%", "Stable")
• best_use_case:
   - Primary → "Meta Tags (Page Title, Meta Description), Intro Paragraph"
   - Secondary → "H2 Subheading", "Blog Content", "Service Page", "Informational Page", etc.
   - Long-tail → "FAQ Section", "How-To Guide", "Local SEO", "Comparison Page", etc.
• keyword_intent: informational or commercial  
• selection_rationale: max 30 words (optional)
• recommended_density (optional)  
• synonym_overlap (optional)

---

HARD RULES

• Use only keywords from the uploaded list  
• Search volume MUST be copied exactly from the "avg_monthly_searches" field - DO NOT modify, round, average, or estimate
• Exclude all keywords with negative terms or blocked brands  
• Exclude keywords not matching the funnel stage (mid → no top-of-funnel)  
• Output must be valid JSON with no markdown or extra text  

---

INPUTS

{intake_json}
{keywords_list}

---

OUTPUT
Return ONLY a valid JSON object with this exact structure:

{
  "metadata": {
    "target_page_url": "...",
    "target_location": "...",
    "intent": "...",
    "region_spelling": "UK English"
  },
  "primary_keywords": [
    {
      "keyword": "exact keyword from list",
      "search_volume": 40,  // MUST match avg_monthly_searches from raw data exactly
      "location": "Auckland (City - NZ)",
      "trend_3m": "Stable",
      "trend_yoy": "+10%",
      "best_use_case": "Meta Tags (Page Title, Meta Description), Intro Paragraph",
      "keyword_intent": "commercial"
    }
  ],
  "secondary_keywords": [...],
  "long_tail_keywords": [...]
}

CRITICAL: The search_volume field MUST be the exact same number as avg_monthly_searches from the raw keyword data. Do not round, estimate, or modify it in any way.
"""
