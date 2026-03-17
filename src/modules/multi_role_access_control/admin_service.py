from pymongo import ASCENDING
from datetime import datetime, timedelta


def _is_admin(db, user_id: str) -> bool:
    """Check if a user holds the 'Admin' role via Assigned_Roles."""
    user = db["users"].find_one({"_id": user_id})
    if not user:
        return False
    for role_id in user.get("Assigned_Roles", []):
        role = db["roles"].find_one({"_id": role_id})
        if role and role.get("Role_name") == "Admin":
            return True
    return False


def assign_role_to_user(db, admin_id: str, target_user_id: str, new_role: str) -> bool:
    """
    P5 Admin Capability: Appends a static role to a target user.
    """
    if not _is_admin(db, admin_id):
        raise PermissionError("Access Denied: Only Admins can execute role bindings.")

    # Look up role ObjectId by name
    role_doc = db["roles"].find_one({"Role_name": new_role})
    if not role_doc:
        raise ValueError(f"Role '{new_role}' does not exist.")

    result = db["users"].update_one(
        {"_id": target_user_id},
        {"$addToSet": {"Assigned_Roles": role_doc["_id"]}}
    )
    return result.modified_count > 0

def revoke_role_from_user(db, admin_id: str, target_user_id: str, target_role: str) -> bool:
    """
    P5 Admin Capability: Removes a static role from a target user.
    """
    if not _is_admin(db, admin_id):
        raise PermissionError("Access Denied: Only Admins can revoke roles.")

    role_doc = db["roles"].find_one({"Role_name": target_role})
    if not role_doc:
        raise ValueError(f"Role '{target_role}' does not exist.")

    result = db["users"].update_one(
        {"_id": target_user_id},
        {"$pull": {"Assigned_Roles": role_doc["_id"]}}
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
