#!/usr/bin/env python3
"""
Quick script to check a user's login status and debug issues.
Usage: python check_user.py <email>
"""

import sys
import firebase_admin
from firebase_admin import credentials, firestore, auth as firebase_auth

# Initialize Firebase Admin if not already initialized
if not firebase_admin._apps:
    cred = credentials.Certificate("app/keys/serviceAccountKey.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()


def check_user(email: str):
    """Check user status in both Firebase Auth and Firestore."""
    
    print(f"\n🔍 Checking user: {email}\n")
    print("=" * 80)
    
    # Check Firebase Auth
    print("\n1️⃣  Firebase Authentication:")
    print("-" * 80)
    try:
        auth_user = firebase_auth.get_user_by_email(email)
        print(f"✅ User exists in Firebase Auth")
        print(f"   UID:           {auth_user.uid}")
        print(f"   Email:         {auth_user.email}")
        print(f"   Display Name:  {auth_user.display_name or 'Not set'}")
        print(f"   Email Verified: {auth_user.email_verified}")
        print(f"   Disabled:      {auth_user.disabled}")
        print(f"   Created:       {auth_user.user_metadata.creation_timestamp}")
        print(f"   Last Sign In:  {auth_user.user_metadata.last_sign_in_timestamp or 'Never'}")
        
        uid = auth_user.uid
        
    except firebase_auth.UserNotFoundError:
        print(f"❌ User NOT found in Firebase Auth")
        print(f"   → User needs to be created in Firebase Authentication first")
        print(f"   → Go to Firebase Console > Authentication > Users")
        return False
    except Exception as e:
        print(f"❌ Error checking Firebase Auth: {e}")
        return False
    
    # Check Firestore
    print("\n2️⃣  Firestore Database:")
    print("-" * 80)
    try:
        user_ref = db.collection("users").document(uid)
        doc = user_ref.get()
        
        if doc.exists:
            data = doc.to_dict()
            print(f"✅ User document exists in Firestore")
            print(f"   Email:         {data.get('email', 'N/A')}")
            print(f"   First Name:    {data.get('firstName', 'N/A')}")
            print(f"   Role:          {data.get('role', 'N/A')} ⭐")
            print(f"   Plan:          {data.get('plan', 'N/A')}")
            print(f"   Credits:       {data.get('credits', 0)}")
            print(f"   Research Count: {data.get('researchCount', 0)}")
            print(f"   Token Usage:   {data.get('tokenUsage', 0)}")
            print(f"   Created At:    {data.get('createdAt', 'N/A')}")
            print(f"   Last Login:    {data.get('lastLoginAt', 'N/A')}")
            
            role = data.get('role', 'user')
            
        else:
            print(f"❌ User document NOT found in Firestore")
            print(f"   → Document will be auto-created on first login attempt")
            print(f"   → Default role will be 'user' (needs manual upgrade to 'tester' or 'admin')")
            role = None
            
    except Exception as e:
        print(f"❌ Error checking Firestore: {e}")
        return False
    
    # Check login access
    print("\n3️⃣  Login Access Status:")
    print("-" * 80)
    
    if role in ["admin", "tester"]:
        print(f"✅ User CAN login to the application")
        print(f"   → Role '{role}' is authorized")
        if role == "tester":
            print(f"   → Will redirect to: /dashboard")
        else:
            print(f"   → Will redirect to: /admin")
    elif role == "user":
        print(f"❌ User CANNOT login - insufficient permissions")
        print(f"   → Current role: 'user'")
        print(f"   → Required role: 'admin' or 'tester'")
        print(f"\n   To fix, run:")
        print(f"   python set_user_role.py {email} tester")
    elif role is None:
        print(f"⚠️  User will be auto-created on first login")
        print(f"   → But will get error: 'Account created. Please contact admin to grant access.'")
        print(f"   → Then admin needs to set role to 'tester' or 'admin'")
        print(f"\n   To fix, run:")
        print(f"   python set_user_role.py {email} tester")
    
    print("\n" + "=" * 80 + "\n")
    return True


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python check_user.py <email>")
        print("\nExample:")
        print("  python check_user.py tester@example.com")
        sys.exit(1)
    
    email = sys.argv[1]
    check_user(email)
