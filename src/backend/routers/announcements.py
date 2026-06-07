"""
Announcement endpoints for the High School Management System API
"""

from fastapi import APIRouter, HTTPException
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from datetime import datetime, timezone
from bson import ObjectId

from ..database import announcements_collection, teachers_collection

router = APIRouter(
    prefix="/announcements",
    tags=["announcements"]
)


class AnnouncementCreate(BaseModel):
    message: str
    start_date: Optional[str] = None
    expiration_date: str


class AnnouncementUpdate(BaseModel):
    message: Optional[str] = None
    start_date: Optional[str] = None
    expiration_date: Optional[str] = None


def _serialize(doc: dict) -> dict:
    """Convert a MongoDB document to a JSON-serializable dict."""
    doc["id"] = str(doc.pop("_id"))
    return doc


def _is_active(announcement: dict) -> bool:
    """Return True if announcement is currently active."""
    now = datetime.now(timezone.utc).isoformat()

    start = announcement.get("start_date")
    if start and start > now:
        return False

    expiration = announcement.get("expiration_date")
    if expiration and expiration < now:
        return False

    return True


@router.get("", response_model=List[Dict[str, Any]])
@router.get("/", response_model=List[Dict[str, Any]])
def get_active_announcements() -> List[Dict[str, Any]]:
    """Get all currently active announcements (public endpoint)."""
    result = []
    for doc in announcements_collection.find():
        doc = _serialize(doc)
        if _is_active(doc):
            result.append(doc)
    return result


@router.get("/all", response_model=List[Dict[str, Any]])
def get_all_announcements(teacher_username: str) -> List[Dict[str, Any]]:
    """Get all announcements including expired ones. Requires authentication."""
    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Authentication required")

    result = []
    for doc in announcements_collection.find():
        doc = _serialize(doc)
        doc["is_active"] = _is_active(doc)
        result.append(doc)
    return result


@router.post("", response_model=Dict[str, Any])
def create_announcement(
    body: AnnouncementCreate,
    teacher_username: str
) -> Dict[str, Any]:
    """Create a new announcement. Requires authentication."""
    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Authentication required")

    if not body.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    doc = {
        "message": body.message.strip(),
        "start_date": body.start_date or None,
        "expiration_date": body.expiration_date,
        "created_by": teacher_username,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    result = announcements_collection.insert_one(doc)
    doc["id"] = str(result.inserted_id)
    doc.pop("_id", None)
    return doc


@router.put("/{announcement_id}", response_model=Dict[str, Any])
def update_announcement(
    announcement_id: str,
    body: AnnouncementUpdate,
    teacher_username: str
) -> Dict[str, Any]:
    """Update an existing announcement. Requires authentication."""
    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        oid = ObjectId(announcement_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid announcement ID")

    existing = announcements_collection.find_one({"_id": oid})
    if not existing:
        raise HTTPException(status_code=404, detail="Announcement not found")

    updates: dict = {}
    if body.message is not None:
        if not body.message.strip():
            raise HTTPException(status_code=400, detail="Message cannot be empty")
        updates["message"] = body.message.strip()
    if body.expiration_date is not None:
        updates["expiration_date"] = body.expiration_date
    if "start_date" in body.model_fields_set:
        updates["start_date"] = body.start_date

    if updates:
        announcements_collection.update_one({"_id": oid}, {"$set": updates})

    updated = announcements_collection.find_one({"_id": oid})
    return _serialize(updated)


@router.delete("/{announcement_id}")
def delete_announcement(announcement_id: str, teacher_username: str) -> Dict[str, Any]:
    """Delete an announcement. Requires authentication."""
    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        oid = ObjectId(announcement_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid announcement ID")

    result = announcements_collection.delete_one({"_id": oid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")

    return {"message": "Announcement deleted successfully"}
