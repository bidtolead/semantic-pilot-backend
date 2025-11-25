from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import routers
from app.routes.intake import router as intake_router
from app.routes.seo import router as seo_router
from app.routes.auth import router as auth_router
from app.routes.firestore import router as firestore_router
from app.routes.test_db import router as test_db_router
from app.routes.admin import router as admin_router
from app.routes.activity import router as activity_router

# ⭐ CORRECT Google Ads Location Search Router
from app.routes.geo import router as geo_router


# -------------------------------------------------
# Create FastAPI app
# -------------------------------------------------
app = FastAPI(
    title="Semantic Pilot Backend",
    version="1.0.0"
)

# -------------------------------------------------
# CORS settings
# -------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://semantic-pilot-frontend.vercel.app",
        "http://localhost:3000",
    ],
    # Allow Vercel preview deployments for this project
    allow_origin_regex=r"^https://semantic-pilot-frontend(-[a-zA-Z0-9-]+)?\.vercel\.app$",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "X-Requested-With",
        "Accept",
        "Origin",
    ],
    expose_headers=["Content-Type", "Authorization"],
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