import os
import json
import firebase_admin
from firebase_admin import credentials, firestore


def init_firestore():
    """
    Initialize Firestore in two modes:
    1. Render: credentials are inside GOOGLE_APPLICATION_CREDENTIALS_JSON
    2. Local: GOOGLE_APPLICATION_CREDENTIALS points to a JSON file
    """

    # --- Render Mode: JSON stored inside an environment variable ---
    json_str = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")

    if json_str:
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            raise ValueError("GOOGLE_APPLICATION_CREDENTIALS_JSON contains invalid JSON.")

        cred = credentials.Certificate(data)

        if not len(firebase_admin._apps):
            firebase_admin.initialize_app(cred)

        return firestore.client()

    # --- Local Mode: JSON file stored on your machine ---
    json_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

    if json_path and os.path.exists(json_path):
        cred = credentials.Certificate(json_path)

        if not len(firebase_admin._apps):
            firebase_admin.initialize_app(cred)

        return firestore.client()

    # --- No credentials found ---
    raise ValueError(
        "No Firestore credentials found.\n"
        "Set GOOGLE_APPLICATION_CREDENTIALS_JSON (Render) or "
        "GOOGLE_APPLICATION_CREDENTIALS pointing to a file (local)."
    )


# Initialize Firestore on import
db = init_firestore()