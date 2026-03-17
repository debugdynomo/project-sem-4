"""
auth_service.py — P1 Authentication service for G41.
Validates credentials against the 'users' collection in MongoDB.
Field names match backend/database.py PascalCase schema: Username, Hashed_password, etc.
"""
import hashlib
from datetime import datetime, timezone
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

    # Build session context
    session_context = {
        "user_id": str(user["_id"]),
        "username": user.get("Username"),
        "assigned_roles": user.get("Assigned_Roles", []),
        "status": user.get("Status"),
        "login_time": datetime.now(timezone.utc).isoformat(),
    }
    return session_context
