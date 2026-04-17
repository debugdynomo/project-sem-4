from datetime import datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

def now_ist():
    """Return current time in IST as a naive datetime (matches MongoDB storage)."""
    return datetime.now(tz=IST).replace(tzinfo=None)
from bson import ObjectId
from backend.audit import audit_action

def safe_objectid(val):
    if not val:
        return None
    if isinstance(val, ObjectId):
        return val
    try:
        return ObjectId(val)
    except:
        return val

@audit_action(action="LOG_EMERGENCY_OVERRIDE", target_entity="overrides")
def log_emergency_override(db, user_id: str, overridden_system: str, reason: str, duration_hours: int = 1) -> str:
    """
    Records an emergency 'Break-Glass' override.
    These are strictly tracked and trigger compliance alerts.
    """
    override_doc = {
        "user_id": safe_objectid(user_id),
        "overridden_system": overridden_system,
        "reason": reason,
        "timestamp": now_ist(),
        "duration_hours": duration_hours,
        "status": "Active Alert",
        "resolved": False,
        "resolved_by": None,
        "resolved_at": None
    }
    result = db["overrides"].insert_one(override_doc)
    return str(result.inserted_id)

@audit_action(action="RESOLVE_EMERGENCY_OVERRIDE", target_entity="overrides")
def resolve_emergency_override(db, admin_id: str, override_id: str) -> bool:
    """
    Resolves an active emergency override alert.
    """
    result = db["overrides"].update_one(
        {"_id": safe_objectid(override_id), "resolved": False},
        {"$set": {
            "status": "Resolved",
            "resolved": True,
            "resolved_by": safe_objectid(admin_id),
            "resolved_at": now_ist()
        }}
    )
    return result.modified_count > 0

def get_active_overrides(db) -> list:
    """Fetched by admin dashboard to show glowing red alerts."""
    return list(db["overrides"].find({"resolved": False}).sort("timestamp", -1))
