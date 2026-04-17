"""
auth_service.py — P1 Authentication service for G41.
Validates credentials against the 'users' collection in MongoDB.
Field names match backend/database.py PascalCase schema: Username, Hashed_password, etc.
"""
import hashlib
from datetime import datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

def now_ist():
    """Return current time in IST as a naive datetime (matches MongoDB storage)."""
    return datetime.now(tz=IST).replace(tzinfo=None)
from typing import Optional


def login_user(db, username: str, password_attempt: str) -> Optional[dict]:
    """
    Look up a user by Username, verify password, return a session context dict.
    Uses SHA-256 hashing (no bcrypt dependency needed for demo).
    Returns None on failure.
    """
    user = db["users"].find_one({"Username": username})
    if not user:
        return None

    # Verify password — compare SHA-256 hash (demo-safe, no bcrypt dep)
    stored_hash = user.get("Hashed_password", "")
    attempt_hash = hashlib.sha256(password_attempt.encode("utf-8")).hexdigest()

    if stored_hash != attempt_hash:
        return None

    assigned_roles_normalized = []
    for r in user.get("Assigned_Roles", []):
        r_id = r.get("role_id") if isinstance(r, dict) else r
        assigned_roles_normalized.append(r_id)

    # Build session context
    session_context = {
        "user_id": str(user["_id"]),
        "username": user.get("Username"),
        "assigned_roles": assigned_roles_normalized,
        "status": user.get("Status"),
        "login_time": now_ist().isoformat(),
    }
    return session_context
