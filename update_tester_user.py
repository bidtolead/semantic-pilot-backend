#!/usr/bin/env python3
"""
Update user role to tester
"""
import firebase_admin
from firebase_admin import credentials, firestore, auth
import sys

# Initialize Firebase
if not firebase_admin._apps:
    creds = credentials.Certificate('app/keys/serviceAccountKey.json')
    firebase_admin.initialize_app(creds)

db = firestore.client()
email = "sasha.schwarzwald@gmail.com"

try:
    # Get user by email
    user = auth.get_user_by_email(email)
    print(f"✅ Found user: {user.uid}")
    
    # Update Firestore document with tester role
    user_ref = db.collection("users").document(user.uid)
    user_ref.update({
        "role": "tester",
        "credits": 50,
        "monthlyCredits": 50,
        "dailyLimit": 20,
    })
    print(f"✅ Updated user role to 'tester'")
    print(f"👤 User ID: {user.uid}")
    print(f"📧 Email: {email}")
    print(f"⭐ Role: tester")
    print(f"💳 Credits: 50")
    
except auth.UserNotFoundError:
    print(f"❌ User not found: {email}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error updating user: {e}")
    sys.exit(1)
