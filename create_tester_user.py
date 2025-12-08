#!/usr/bin/env python3
"""
Create a tester user in Firebase with admin/tester privileges
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
password = "TesterPassword123!@#"  # Temporary password - user should reset

try:
    # Create user in Firebase Auth
    user = auth.create_user(
        email=email,
        password=password,
        display_name="Sasha Schwarzwald"
    )
    print(f"✅ Created Firebase Auth user: {user.uid}")
    
    # Create user document in Firestore with tester role
    user_ref = db.collection("users").document(user.uid)
    user_ref.set({
        "email": email,
        "role": "tester",
        "displayName": "Sasha Schwarzwald",
        "createdAt": firestore.SERVER_TIMESTAMP,
        "credits": 50,  # Give tester credits
        "monthlyCredits": 50,
        "dailyLimit": 20,
        "researchCount": 0,
        "tokenUsage": 0,
        "online": False,
    })
    print(f"✅ Created Firestore user document with tester role")
    print(f"\n📧 Email: {email}")
    print(f"🔑 Temporary Password: {password}")
    print(f"👤 User ID: {user.uid}")
    print(f"\n⚠️  User should reset password on first login")
    
except auth.EmailAlreadyExistsError:
    print(f"❌ Email already exists: {email}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error creating user: {e}")
    sys.exit(1)
