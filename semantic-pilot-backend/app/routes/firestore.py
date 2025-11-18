from fastapi import APIRouter
from app.services.firestore import db

router = APIRouter(prefix="/test-db", tags=["Firestore Test"])

@router.get("/write")
def write_test():
    db.collection("test_collection").document("hello").set({
        "message": "Firestore connection works!"
    })
    return {"status": "written"}

@router.get("/read")
def read_test():
    doc = db.collection("test_collection").document("hello").get()
    return {"data": doc.to_dict()}
