from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import routers
from app.routes.intake import router as intake_router
from app.routes.seo import router as seo_router
from app.routes.auth import router as auth_router
from app.routes.firestore import router as firestore_router
from app.routes.test_db import router as test_db_router
from app.routes.admin import router as admin_router       # <-- admin import
from app.routes.activity import router as activity_router  # <-- heartbeat import

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
    allow_origins=["*"],      # you can restrict this later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------
# Register Routers
# -------------------------------------------------
app.include_router(intake_router)
app.include_router(seo_router)
app.include_router(auth_router)
app.include_router(firestore_router)
app.include_router(test_db_router)

# ⭐ IMPORTANT: admin endpoints must sit under /admin
app.include_router(admin_router, prefix="/admin")

# ⭐ Heartbeat endpoint for tracking user online activity
app.include_router(activity_router)

# -------------------------------------------------
# Health Check
# -------------------------------------------------
@app.get("/")
def root():
    return {
        "status": "ok",
        "message": "Semantic Pilot Backend is running!"
    }