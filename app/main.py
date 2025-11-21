from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import routers
from app.routes.intake import router as intake_router
from app.routes.seo import router as seo_router
from app.routes.auth import router as auth_router
from app.routes.firestore import router as firestore_router
from app.routes.test_db import router as test_db_router
from app.routes.admin import router as admin_router       # admin import
from app.routes.activity import router as activity_router  # heartbeat import
from app.routes.google_locations import router as google_locations_router  # ⭐ NEW

# -------------------------------------------------
# Create FastAPI app
# -------------------------------------------------
app = FastAPI(
    title="Semantic Pilot Backend",
    version="1.0.0"
)

# -------------------------------------------------
# CORS settings (FULL FIX FOR RENDER + VERCEL)
# -------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*",  # You can restrict this later to Vercel domains
        "https://semantic-pilot-frontend.vercel.app",
        "https://semantic-pilot-frontend-*--timurs-projects.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "X-Requested-With",
        "Accept",
        "Origin",
    ],
    expose_headers=[
        "Content-Type",
        "Authorization",
    ],
)

# -------------------------------------------------
# Register Routers
# -------------------------------------------------
app.include_router(intake_router)
app.include_router(seo_router)
app.include_router(auth_router)
app.include_router(firestore_router)
app.include_router(test_db_router)

# ⭐ IMPORTANT: admin endpoints under /admin
app.include_router(admin_router, prefix="/admin")

# ⭐ Heartbeat endpoint for tracking user online activity
app.include_router(activity_router)

# ⭐ Google Location Search (for intake autocomplete)
app.include_router(google_locations_router, prefix="/google")

# -------------------------------------------------
# Health Check
# -------------------------------------------------
@app.get("/")
def root():
    return {
        "status": "ok",
        "message": "Semantic Pilot Backend is running!"
    }