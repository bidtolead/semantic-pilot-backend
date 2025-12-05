#!/usr/bin/env python3
"""Debug script to check ad-copy data and trace the 482 error."""

import sys
import os
import json
import firebase_admin
from firebase_admin import credentials, firestore

# Initialize Firebase
if not firebase_admin._apps:
    cred = credentials.Certificate("app/keys/serviceAccountKey.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()

def debug_ad_copy(user_id: str, research_id: str):
    """Check if all required data exists for ad-copy generation."""
    
    print(f"\n🔍 Debugging ad-copy for user_id={user_id}, research_id={research_id}")
    
    # Check user
    user_ref = db.collection("users").document(user_id)
    user_doc = user_ref.get()
    if user_doc.exists:
        user_data = user_doc.to_dict()
        print(f"✅ User found: role={user_data.get('role')}, credits={user_data.get('credits')}")
    else:
        print(f"❌ User not found")
        return
    
    # Check research_intakes document
    doc_id = f"{user_id}_{research_id}"
    intake_ref = db.collection("research_intakes").document(doc_id)
    intake_doc = intake_ref.get()
    if intake_doc.exists:
        print(f"✅ Intake found in research_intakes")
    else:
        print(f"❌ Intake NOT found in research_intakes/{doc_id}")
    
    # Check keyword_research
    keywords_ref = db.collection("intakes").document(user_id).collection(research_id).document("keyword_research")
    keywords_doc = keywords_ref.get()
    if keywords_doc.exists:
        keywords_data = keywords_doc.to_dict()
        primary_count = len(keywords_data.get("primary_keywords", []))
        secondary_count = len(keywords_data.get("secondary_keywords", []))
        print(f"✅ Keywords found: {primary_count} primary, {secondary_count} secondary")
    else:
        print(f"❌ Keywords NOT found in intakes/{user_id}/{research_id}/keyword_research")
    
    # Check ad_copy document (if exists)
    ad_copy_ref = db.collection("intakes").document(user_id).collection(research_id).document("ad_copy")
    ad_copy_doc = ad_copy_ref.get()
    if ad_copy_doc.exists:
        print(f"✅ Ad copy already exists (cache)")
    else:
        print(f"ℹ️  Ad copy doesn't exist yet (will be generated)")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python debug_ad_copy.py <user_id> <research_id>")
        sys.exit(1)
    
    user_id = sys.argv[1]
    research_id = sys.argv[2]
    debug_ad_copy(user_id, research_id)
