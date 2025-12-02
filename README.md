# Semantic Pilot Backend

This backend powers keyword research and content generation for Semantic Pilot.

## Environment Variables

Create `.env` in the backend root (already loaded by `app/core/env.py`). Required keys:

- Firestore
  - `GOOGLE_APPLICATION_CREDENTIALS=app/keys/serviceAccountKey.json`
- Frontend CORS
  - `FRONTEND_URL` and `FRONTEND_URL_PROD`
- OpenAI & Serper (optional)
  - `OPENAI_API_KEY`, `SERPER_API_KEY`
- DataForSEO (keyword data provider)
  - `DATAFORSEO_LOGIN` — your DataForSEO account login (email)
  - `DATAFORSEO_PASSWORD` — your API password
  - `DATAFORSEO_API_BASE` — optional, default `https://api.dataforseo.com/v3`
- (Legacy) Google Ads keys — no longer required for keyword data, kept for optional geo lookup
  - `GOOGLE_ADS_*`

## Keyword Research Provider

We use DataForSEO `keywords_for_seed` endpoint for Google Ads keyword ideas.

- Service: `app/services/dataforseo.py`
- Routes using DFS:
  - `POST /seo/research` — quick ad-hoc research from suggested keywords
  - `GET /keyword-research/run/{userId}/{intakeId}` — full pipeline from intake
  - `POST /google-ads/keyword-research` — admin-triggered run; now DFS-backed

Returned fields are mapped to our canonical structure used by the frontend:

- `keyword`
- `avg_monthly_searches`
- `competition` — `LOW|MEDIUM|HIGH` from DFS float
- `competition_index` — 0..100
- `low_top_of_page_bid_micros`, `high_top_of_page_bid_micros` — derived from DFS `cpc` dollars

## Run Locally

```zsh
uvicorn app.app.main:app --reload
```

## Quick Test

```zsh
curl -X POST "http://localhost:8000/seo/research" \
  -H "Authorization: Bearer <FIREBASE_ID_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"suggested_keywords":["plumber","emergency plumber"],"location":"Auckland"}'
```

## Deploy on Render

- Add secrets to Render Service → Environment:
  - `DATAFORSEO_LOGIN`, `DATAFORSEO_PASSWORD`, optionally `DATAFORSEO_API_BASE`
- Redeploy the service to apply changes.

