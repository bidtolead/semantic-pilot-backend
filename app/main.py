from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import all routers
from app.routes.intake import router as intake_router
from app.routes.seo import router as seo_router
from app.routes.auth import router as auth_router
from app.routes.firestore import router as firestore_router
from app.routes.test_db import router as test_db_router

# ✅ ADMIN ROUTER — must be imported
from app.routes.admin import router as admin_router

app = FastAPI(
    title="Semantic Pilot Backend",
    version="1.0.0"
)

# -------------------------------------------------
# CORS
# -------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------
# Register routers
# -------------------------------------------------
app.include_router(intake_router)
app.include_router(seo_router)
app.include_router(auth_router)
app.include_router(firestore_router)
app.include_router(test_db_router)

# ✅ IMPORTANT: Register admin router with PREFIX
app.include_router(admin_router, prefix="/admin")

# -------------------------------------------------
# Health check
# -------------------------------------------------
@app.get("/")
def root():
    return {
        "status": "ok",
        "message": "Semantic Pilot Backend is running!"
    }