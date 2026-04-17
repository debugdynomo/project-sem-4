import functools
import socket
from datetime import datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

def now_ist():
    """Return current time in IST as a naive datetime (matches MongoDB storage)."""
    return datetime.now(tz=IST).replace(tzinfo=None)
from bson import ObjectId
from bson.errors import InvalidId

# ── IP address cache ────────────────────────────────────────────────
_cached_ip = None


def _get_client_ip():
    """Return the actual IP address of this machine (cached after first call).

    Strategy:
      1. Open a UDP socket to a public DNS server to discover the local
         network IP (works on LAN / WiFi without sending any data).
      2. If that fails, try an external API (httpbin) for the public IP.
      3. Ultimate fallback: 127.0.0.1
    """
    global _cached_ip
    if _cached_ip is not None:
        return _cached_ip

    # ── Method 1: UDP socket trick (no data is actually sent) ──
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(2)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if ip and ip != "0.0.0.0":
            _cached_ip = ip
            return _cached_ip
    except Exception:
        pass

    # ── Method 2: External API for public IP ──
    try:
        import urllib.request
        ip = urllib.request.urlopen("https://api.ipify.org", timeout=3).read().decode().strip()
        if ip:
            _cached_ip = ip
            return _cached_ip
    except Exception:
        pass

    # ── Fallback ──
    _cached_ip = "127.0.0.1"
    return _cached_ip


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
    ip_address=None,
    status="SUCCESS",
    details=None,
):
    """Insert one audit log and fail fast if logging cannot be persisted."""
    if db is None:
        raise ValueError("Audit logging requires a valid `db` handle.")

    if ip_address is None:
        ip_address = _get_client_ip()

    doc = {
        "User_id": _normalize_object_id(user_id),
        "Action": action,
        "Target_Entity": target_entity,
        "Timestamp": now_ist(),
        "IP_Address": ip_address,
        "Status": status,
        "Details": details,
    }
    db.audit_logs.insert_one(doc)

def audit_action(action, target_entity="System"):
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
            db = kwargs.get("db") if "db" in kwargs else (args[0] if len(args) > 0 else None)
            
            user_id = kwargs.get("user_id") if "user_id" in kwargs else (
                kwargs.get("admin_id") if "admin_id" in kwargs else (
                    args[1] if len(args) > 1 else None
                )
            )
            
            # Use actual client IP instead of hardcoded localhost
            ip_address = kwargs.get("ip_address", _get_client_ip())
            
            # Use dynamic target_entity if passed, else fallback to decorator value
            resolved_target_entity = kwargs.get("target_entity", target_entity)

            try:
                result = func(*args, **kwargs)
                if db is not None:
                    log_audit_event(
                        db,
                        action=action,
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
                        action=action,
                        user_id=user_id,
                        target_entity=resolved_target_entity,
                        ip_address=ip_address,
                        status="FAILED",
                        details={"error": str(exc)},
                    )
                raise

        return wrapper

    return decorator
