from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Import routers
from app.routes.intake import router as intake_router
from app.routes.seo import router as seo_router
from app.routes.auth import router as auth_router
from app.routes.firestore import router as firestore_router
from app.routes.test_db import router as test_db_router
from app.routes.admin import router as admin_router
from app.routes.activity import router as activity_router
from app.routes.content import router as content_router
from app.routes.stats import router as stats_router

# ⭐ CORRECT Google Ads Location Search Router
from app.routes.geo import router as geo_router


# -------------------------------------------------
# Rate Limiter Setup
# -------------------------------------------------
limiter = Limiter(key_func=get_remote_address)

# -------------------------------------------------
# Create FastAPI app
# -------------------------------------------------
app = FastAPI(
    title="Semantic Pilot Backend",
    version="1.0.0"
)

# Add rate limiter to app state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# -------------------------------------------------
# CORS settings
# -------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://semantic-pilot-frontend.vercel.app",
        "http://localhost:3000",
        "https://semanticpilot.com",
        "https://www.semanticpilot.com",
    ],
    # Allow Vercel preview deployments (including team/user-scoped URLs)
    allow_origin_regex=r"^https://(semantic-pilot-frontend.*\.vercel\.app|[a-z0-9-]+\.semanticpilot\.com)$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# -------------------------------------------------
# Register Routers
# -------------------------------------------------
app.include_router(intake_router)
app.include_router(seo_router)
app.include_router(auth_router)
app.include_router(firestore_router)
app.include_router(test_db_router)

# Admin endpoints
app.include_router(admin_router)

# Content generation endpoints
app.include_router(content_router)

# Public stats endpoints
app.include_router(stats_router)

# Heartbeat for tracking user activity
app.include_router(activity_router)

# ⭐ Correct Google Ads location search routes
app.include_router(geo_router, prefix="/google-ads")

# -------------------------------------------------
# Health Check
# -------------------------------------------------
@app.get("/")
def root():
    return {
        "status": "ok",
        "message": "Semantic Pilot Backend is running!"
    }