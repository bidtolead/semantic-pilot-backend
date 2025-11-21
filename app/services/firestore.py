import os
import json
from firebase_admin import credentials, initialize_app, firestore


def init_firestore():
    """
    Initialize Firestore using JSON credentials stored in an environment variable.
    This works on Render (where files may not exist) and locally.
    """

    # Get JSON string from environment variable
    json_str = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")

    if not json_str:
        raise ValueError(
            "GOOGLE_APPLICATION_CREDENTIALS_JSON is not set. "
            "Make sure it is added in your Render environment variables."
        )

    try:
        # Parse JSON into dict
        cred_dict = json.loads(json_str)
    except json.JSONDecodeError:
        raise ValueError("GOOGLE_APPLICATION_CREDENTIALS_JSON contains invalid JSON")

    # Convert dict into Firebase credential object
    cred = credentials.Certificate(cred_dict)

    # Initialize Firebase app (avoid reinitializing if already done)
    try:
        app = initialize_app(cred)
    except ValueError:
        # Firebase already initialized — retrieve existing app
        pass

    return firestore.client()


# Global Firestore client to import anywhere
db = init_firestore()