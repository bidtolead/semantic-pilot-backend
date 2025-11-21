import os
import json
import firebase_admin
from firebase_admin import credentials, firestore

def init_firestore():
    firebase_json = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")

    if not firebase_json:
        raise ValueError("GOOGLE_APPLICATION_CREDENTIALS_JSON is not set in Render env")

    # Parse JSON string from environment variable
    cred_dict = json.loads(firebase_json)
    cred = credentials.Certificate(cred_dict)

    # Initialize only once
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)

    return firestore.client()

db = init_firestore()