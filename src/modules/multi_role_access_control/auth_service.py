import bcrypt
from datetime import datetime
from typing import Optional

def login_user(db, username: str, password_attempt: str) -> Optional[dict]:
    """
    Validates credentials and constructs the P1 user session context dictionary.
    """
    user = db["users"].find_one({"username": username})
    if not user:
        return None # Username not found
        
    # Security: Verify secure hash
    stored_hash = user.get("password_hash", b"")
    if isinstance(stored_hash, str):
        stored_hash = stored_hash.encode('utf-8')
        
    if not bcrypt.checkpw(password_attempt.encode('utf-8'), stored_hash):
        return None # Password mismatch
        
    # Build secure User Context required for tracking and P5 role checks
    session_context = {
        "user_id": str(user["_id"]),
        "username": user.get("username"),
        "primary_role": user.get("primary_role"),
        "login_time": datetime.utcnow().isoformat(),
        # Cached boolean to simplify routing & rendering logic on the UI side
        "is_admin": user.get("primary_role") == "Admin" 
    }
    return session_context
