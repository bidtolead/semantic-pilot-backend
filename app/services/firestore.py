import os
import json
from firebase_admin import credentials, initialize_app, firestore


def init_firestore():
    """
    Initialize Firestore using JSON credentials stored in an environment variable.
    Works on Render (no filesystem needed) and locally.
    """

    # Try new JSON-based env var
    json_str = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")

    if json_str:
        try:
            cred_info = json.loads(json_str)
            cred = credentials.Certificate(cred_info)
        except Exception as e:
            raise ValueError(f"Invalid GOOGLE_APPLICATION_CREDENTIALS_JSON: {e}")
    else:
        # Fallback: file path (local dev only)
        file_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if not file_path or not os.path.exists(file_path):
            raise ValueError(
                "No Firestore credentials found. "
                "Set GOOGLE_APPLICATION_CREDENTIALS_JSON (Render) or "
                "GOOGLE_APPLICATION_CREDENTIALS pointing to a file (local)."
            )

        cred = credentials.Certificate(file_path)

    # Initialize only once
    if not len(firebase_admin._apps):
        initialize_app(cred)

    return firestore.client()


# Initialize Firestore DB
db = init_firestore()