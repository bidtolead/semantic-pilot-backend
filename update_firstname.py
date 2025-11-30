#!/usr/bin/env python3
"""
Update firstName for existing users from Firebase Auth displayName.
"""
import sys
import firebase_admin
from firebase_admin import credentials, firestore, auth as firebase_auth

# Initialize Firebase Admin if not already initialized
if not firebase_admin._apps:
    cred = credentials.Certificate("app/keys/serviceAccountKey.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()

def update_user_firstname(email: str):
    """Update firstName for a user from their Firebase Auth displayName."""
    try:
        # Get user from Firebase Auth
        user = firebase_auth.get_user_by_email(email)
        uid = user.uid
        display_name = user.display_name
        
        print(f"🔍 Found user: {email}")
        print(f"   UID: {uid}")
        print(f"   Display Name: {display_name}")
        
        if not display_name:
            print("   ⚠️  No display name in Firebase Auth")
            return
        
        # Extract first name
        first_name = display_name.split()[0] if display_name else None
        
        # Update Firestore
        user_ref = db.collection("users").document(uid)
        user_ref.update({"firstName": first_name})
        
        print(f"   ✅ Updated firstName to: {first_name}")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 update_firstname.py <email>")
        sys.exit(1)
    
    email = sys.argv[1]
    update_user_firstname(email)
