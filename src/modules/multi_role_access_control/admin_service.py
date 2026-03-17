from pymongo import ASCENDING
from datetime import datetime, timedelta

def assign_role_to_user(db, admin_id: str, target_user_id: str, new_role: str) -> bool:
    """
    P5 Admin Capability: Appends a static role to a target user.
    """
    # 1. Strict Security Check: Ensure execution is legitimately from an Admin
    admin_user = db["users"].find_one({"_id": admin_id})
    if not admin_user or admin_user.get("primary_role") != "Admin":
        raise PermissionError("Access Denied: Only Admins can execute role bindings.")
        
    # 2. Add to set prevents duplicate role assignments
    result = db["users"].update_one(
        {"_id": target_user_id},
        {"$addToSet": {"assigned_roles": new_role}}
    )
    return result.modified_count > 0

def revoke_role_from_user(db, admin_id: str, target_user_id: str, target_role: str) -> bool:
    """
    P5 Admin Capability: Removes a static role from a target user.
    """
    admin_user = db["users"].find_one({"_id": admin_id})
    if not admin_user or admin_user.get("primary_role") != "Admin":
        raise PermissionError("Access Denied: Only Admins can revoke roles.")
        
    result = db["users"].update_one(
        {"_id": target_user_id},
        {"$pull": {"assigned_roles": target_role}}
    )
    return result.modified_count > 0

def get_upcoming_expirations(db, days_out: int) -> list:
    """
    Reporting Function: Finds active delegations set to expire soon.
    Useful for Admin dashboards to handle access recertification reviews.
    """
    now = datetime.utcnow()
    forecast_date = now + timedelta(days=days_out)
    
    query = {
        "status": "Active",
        "end_time": {
            "$gte": now,
            "$lte": forecast_date
        }
    }
    
    # Return sorted by nearest expiration first
    cursor = db["delegations"].find(query).sort("end_time", ASCENDING)
    
    # Format array for easy Streamlit dataframe rendering
    expiring_list = []
    for doc in cursor:
        doc["_id"] = str(doc["_id"]) # Cast ObjectId to string for JSON serialization
        expiring_list.append(doc)
        
    return expiring_list
