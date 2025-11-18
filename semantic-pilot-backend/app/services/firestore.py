import os
from pathlib import Path
from dotenv import load_dotenv
from firebase_admin import credentials, initialize_app, firestore


# -----------------------------
# FORCE LOAD .env FROM BACKEND ROOT
# -----------------------------
BACKEND_ROOT = Path(__file__).resolve().parents[2]   # goes to semantic-pilot-backend/
ENV_PATH = BACKEND_ROOT / ".env"
load_dotenv(dotenv_path=ENV_PATH)


def init_firestore():
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if not creds_path:
        raise ValueError("GOOGLE_APPLICATION_CREDENTIALS is not set in .env")

    cred = credentials.Certificate(creds_path)
    app = initialize_app(cred)
    return firestore.client()


db = init_firestore()
