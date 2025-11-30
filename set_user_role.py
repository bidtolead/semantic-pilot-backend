#!/usr/bin/env python3
"""
Script to set a user's role in Firestore.
Usage: python set_user_role.py <email> <role>
Example: python set_user_role.py tester@example.com tester
"""

import sys
import firebase_admin
from firebase_admin import credentials, firestore, auth as firebase_auth

# Initialize Firebase Admin if not already initialized
if not firebase_admin._apps:
    cred = credentials.Certificate("app/keys/serviceAccountKey.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()


def set_user_role(email: str, role: str):
    """Set a user's role by email address."""
    
    valid_roles = ["user", "tester", "admin"]
    if role not in valid_roles:
        print(f"❌ Error: Invalid role '{role}'. Must be one of: {', '.join(valid_roles)}")
        return False
    
    try:
        # Get user by email from Firebase Auth
        user = firebase_auth.get_user_by_email(email)
        uid = user.uid
        
        print(f"✓ Found user: {email} (UID: {uid})")
        
        # Update Firestore document
        user_ref = db.collection("users").document(uid)
        doc = user_ref.get()
        
        if doc.exists:
            user_ref.update({"role": role})
            print(f"✅ Updated existing user role to: {role}")
        else:
            # Create new user document
            from datetime import datetime
            new_user = {
                "email": email,
                "firstName": user.display_name.split()[0] if user.display_name else None,
                "role": role,
                "plan": "free",
                "credits": 100,
                "researchCount": 0,
                "tokenUsage": 0,
                "totalSpend": 0.0,
                "createdAt": datetime.utcnow().isoformat(),
                "uid": uid,
            }
            user_ref.set(new_user)
            print(f"✅ Created new user document with role: {role}")
        
        return True
        
    except firebase_auth.UserNotFoundError:
        print(f"❌ Error: User with email '{email}' not found in Firebase Auth")
        print("   Make sure the user has been created in Firebase Authentication first.")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def list_users():
    """List all users and their roles."""
    print("\n📋 All users in Firestore:\n")
    users = db.collection("users").stream()
    
    count = 0
    for doc in users:
        data = doc.to_dict()
        email = data.get("email", "N/A")
        role = data.get("role", "N/A")
        uid = doc.id
        print(f"  • {email:<40} Role: {role:<10} UID: {uid}")
        count += 1
    
    if count == 0:
        print("  (No users found)")
    else:
        print(f"\n  Total: {count} users")


if __name__ == "__main__":
    if len(sys.argv) == 1:
        # No arguments - list all users
        list_users()
    elif len(sys.argv) == 3:
        # Set user role
        email = sys.argv[1]
        role = sys.argv[2]
        set_user_role(email, role)
    else:
        print("Usage:")
        print("  List all users:     python set_user_role.py")
        print("  Set user role:      python set_user_role.py <email> <role>")
        print("\nExamples:")
        print("  python set_user_role.py")
        print("  python set_user_role.py tester@example.com tester")
        print("  python set_user_role.py admin@example.com admin")
        sys.exit(1)
