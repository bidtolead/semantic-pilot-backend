#!/usr/bin/env python3
"""
Check if selection_rationale is present in keyword research data
"""
import firebase_admin
from firebase_admin import credentials, firestore

# Initialize Firebase
if not firebase_admin._apps:
    creds = credentials.Certificate('/Users/timur/semantic-pilot/service-account.json')
    firebase_admin.initialize_app(creds)

db = firestore.client()

# Get all user intake collections
intakes_collection = db.collection("intakes")
users = list(intakes_collection.list_documents())

print(f"🔍 Searching through {len(users)} users for keyword research with data...")

found = False
keyword_doc = None

for user_ref in users:
    user_id = user_ref.id
    
    # Get all intake IDs for this user
    intake_ids = list(user_ref.collections())
    
    for intake_collection in intake_ids:
        intake_id = intake_collection.id
        
        # Try to get keyword_research document
        keyword_ref = db.collection("intakes").document(user_id).collection(intake_id).document("keyword_research")
        doc = keyword_ref.get()
        
        if doc.exists:
            data = doc.to_dict()
            # Check if it has any keywords
            total_keywords = (
                len(data.get("primary_keywords", [])) +
                len(data.get("secondary_keywords", [])) +
                len(data.get("long_tail_keywords", []))
            )
            
            if total_keywords > 0:
                print(f"\n✅ Found keyword research with {total_keywords} keywords!")
                print(f"   User ID: {user_id}")
                print(f"   Intake ID: {intake_id}")
                keyword_doc = doc
                found = True
                break
    
    if found:
        break

if not found:
    print("\n❌ No keyword_research documents found")
    print("Please run a new keyword research and try again.")
    exit(1)

# Now check the keyword data
data = keyword_doc.to_dict()

# Check each keyword category
for category in ["primary_keywords", "secondary_keywords", "long_tail_keywords"]:
    keywords = data.get(category, [])
    print(f"\n{'='*60}")
    print(f"{category.upper()}: {len(keywords)} keywords")
    print('='*60)
    
    for i, kw in enumerate(keywords[:3], 1):  # Show first 3 from each category
        has_rationale = "selection_rationale" in kw
        rationale = kw.get("selection_rationale", "MISSING")
        
        print(f"\n  Keyword {i}: {kw.get('keyword', 'N/A')}")
        print(f"  Has selection_rationale: {'✅ YES' if has_rationale else '❌ NO'}")
        if has_rationale:
            print(f"  Value: \"{rationale}\"")
        else:
            print(f"  Available fields: {list(kw.keys())}")
print("\n" + "="*60)
print("SUMMARY")
print("="*60)
print("If selection_rationale is missing (❌), the LLM did not generate it.")
print("You need to update your backend prompt or add validation to ensure it's always present.")
