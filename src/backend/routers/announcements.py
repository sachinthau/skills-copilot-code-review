from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, Optional

from ..database import announcements_collection, teachers_collection

router = APIRouter(
    prefix="/announcements",
    tags=["announcements"]
)


@router.get("", response_model=Dict[str, Any])
def list_announcements() -> Dict[str, Any]:
    """Return all non-expired announcements. The DB stores ISO strings for dates; the frontend
    is responsible for choosing which ones to show based on start/expiration, but we filter
    out expired ones server-side for convenience.
    """
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)

    announcements = {}
    for doc in announcements_collection.find({}):
        # Simple expiration filtering if expiration_date is set
        exp = doc.get("expiration_date")
        if exp:
            try:
                exp_dt = datetime.fromisoformat(exp.replace("Z", "+00:00"))
                if exp_dt < now:
                    continue
            except Exception:
                # If parse fails, include the announcement to be safe
                pass

        _id = str(doc.get("_id"))
        announcements[_id] = {k: v for k, v in doc.items() if k != "_id"}

    return announcements


def _require_teacher(username: Optional[str]):
    if not username:
        raise HTTPException(status_code=401, detail="Authentication required")

    teacher = teachers_collection.find_one({"_id": username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Invalid teacher credentials")

    return teacher


@router.post("", status_code=201)
def create_announcement(
    title: str,
    message: str,
    expiration_date: str = Query(..., description="ISO8601 expiration date"),
    start_date: Optional[str] = None,
    created_by: Optional[str] = Query(None, description="Teacher username performing the action")
):
    """Create a new announcement. Only authenticated teachers may create announcements."""
    _require_teacher(created_by)

    announcement = {
        "title": title,
        "message": message,
        "start_date": start_date,
        "expiration_date": expiration_date,
        "created_by": created_by,
    }

    result = announcements_collection.insert_one(announcement)
    return {"id": str(result.inserted_id), **announcement}


@router.put("/{announcement_id}")
def update_announcement(
    announcement_id: str,
    title: Optional[str] = None,
    message: Optional[str] = None,
    expiration_date: Optional[str] = None,
    start_date: Optional[str] = None,
    modified_by: Optional[str] = Query(None, description="Teacher username performing the action")
):
    _require_teacher(modified_by)

    update = {}
    if title is not None:
        update["title"] = title
    if message is not None:
        update["message"] = message
    if expiration_date is not None:
        update["expiration_date"] = expiration_date
    if start_date is not None:
        update["start_date"] = start_date

    if not update:
        raise HTTPException(status_code=400, detail="No fields to update")

    result = announcements_collection.update_one({"_id": announcement_id}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")

    return {"id": announcement_id, **update}


@router.delete("/{announcement_id}")
def delete_announcement(announcement_id: str, deleted_by: Optional[str] = Query(None)):
    _require_teacher(deleted_by)

    result = announcements_collection.delete_one({"_id": announcement_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")

    return {"id": announcement_id, "deleted": True}
