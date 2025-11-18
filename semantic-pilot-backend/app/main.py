from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.intake import router as intake_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(intake_router)
