import functools
from datetime import datetime, timezone
from bson import ObjectId
from bson.errors import InvalidId


def _normalize_object_id(value):
    if value is None or isinstance(value, ObjectId):
        return value
    if isinstance(value, str):
        try:
            return ObjectId(value)
        except InvalidId:
            return None
    return None


def log_audit_event(
    db,
    *,
    action,
    user_id=None,
    target_entity="System",
    ip_address="127.0.0.1",
    status="SUCCESS",
    details=None,
):
    """Insert one audit log and fail fast if logging cannot be persisted."""
    if db is None:
        raise ValueError("Audit logging requires a valid `db` handle.")

    doc = {
        "User_id": _normalize_object_id(user_id),
        "Action": action,
        "Target_Entity": target_entity,
        "Timestamp": datetime.now(timezone.utc),
        "IP_Address": ip_address,
        "Status": status,
        "Details": details,
    }
    db.audit_logs.insert_one(doc)

def audit_action(action_name, target_entity="System"):
    """
    A Python decorator to automatically log backend actions to the 
    MongoDB 'audit_logs' collection. 
    
    It intercepts execution, grabs user context from kwargs, and logs the 
    event. Fulfills the app-level Database Auditing requirement for G41.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Extract dependencies (db and user context) from the function's arguments
            db = kwargs.get("db")
            user_id = kwargs.get("user_id")
            
            # In a real Streamlit app, IP might be pulled from request headers
            ip_address = kwargs.get("ip_address", "127.0.0.1")
            resolved_target_entity = kwargs.get("target_entity", target_entity)

            try:
                result = func(*args, **kwargs)
                if db is not None:
                    log_audit_event(
                        db,
                        action=action_name,
                        user_id=user_id,
                        target_entity=resolved_target_entity,
                        ip_address=ip_address,
                        status="SUCCESS",
                    )
                return result
            except Exception as exc:
                if db is not None:
                    # Attempt to capture failure path as well for forensic parity.
                    log_audit_event(
                        db,
                        action=action_name,
                        user_id=user_id,
                        target_entity=resolved_target_entity,
                        ip_address=ip_address,
                        status="FAILED",
                        details={"error": str(exc)},
                    )
                raise

        return wrapper

    return decorator
