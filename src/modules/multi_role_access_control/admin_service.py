from pymongo import ASCENDING
from datetime import datetime, timedelta
import hashlib
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


def get_all_users(db) -> list:
    return list(db["users"].find({}))


@audit_action(action="CREATE_USER", target_entity="users")
def create_user(db, admin_id: str, username: str, email: str, password: str) -> str:
    if not _is_admin(db, admin_id):
        raise PermissionError("Only Admins can create users manually from UI.")
    
    # Hash password same as auth_service
    pw_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
    
    user_doc = {
        "Username": username,
        "Email": email,
        "Hashed_password": pw_hash,
        "Status": "Active",
        "Assigned_Roles": []
    }
    result = db["users"].insert_one(user_doc)
    return str(result.inserted_id)


def _is_admin(db, user_id: str) -> bool:
    """Check if a user holds the 'Admin' role via Assigned_Roles."""
    user = db["users"].find_one({"_id": safe_objectid(user_id)})
    if not user:
        return False
    for role_id in user.get("Assigned_Roles", []):
        role = db["roles"].find_one({"_id": safe_objectid(role_id)})
        if role and role.get("Role_name") == "Admin":
            return True
    return False


@audit_action(action="ASSIGN_ROLE", target_entity="users")
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
        {"_id": safe_objectid(target_user_id)},
        {"$addToSet": {"Assigned_Roles": role_doc["_id"]}}
    )
    return result.modified_count > 0

@audit_action(action="REVOKE_ROLE", target_entity="users")
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
        {"_id": safe_objectid(target_user_id)},
        {"$pull": {"Assigned_Roles": role_doc["_id"]}}
    )
    return result.modified_count > 0

def get_all_roles(db) -> list:
    return list(db["roles"].find({}))

@audit_action(action="CREATE_ROLE", target_entity="roles")
def create_role(db, admin_id: str, role_name: str, description: str, parent_role_id=None) -> str:
    if not _is_admin(db, admin_id):
        raise PermissionError("Only Admins can create roles.")
    
    role_doc = {
        "Role_name": role_name,
        "Description": description,
        "Level": 1,
        "Parent_Role_id": safe_objectid(parent_role_id),
        "Permissions": []
    }
    result = db["roles"].insert_one(role_doc)
    return str(result.inserted_id)

def get_all_permissions(db) -> list:
    return list(db["permissions"].find({}))

@audit_action(action="ASSIGN_PERMISSION", target_entity="roles")
def assign_permission_to_role(db, admin_id: str, role_name: str, permission_name: str) -> bool:
    if not _is_admin(db, admin_id):
        raise PermissionError("Only Admins can assign permissions.")
        
    perm_doc = db["permissions"].find_one({"Permission_name": permission_name})
    if not perm_doc:
        raise ValueError(f"Permission '{permission_name}' does not exist.")
        
    result = db["roles"].update_one(
        {"Role_name": role_name},
        {"$addToSet": {"Permissions": perm_doc["_id"]}}
    )
    return result.modified_count > 0

def get_active_delegations(db) -> list:
    return list(db["delegations"].find({"Status": "Active"}))

@audit_action(action="CREATE_DELEGATION", target_entity="delegations")
def create_delegation(db, user_id: str, delegator_name: str, delegatee_name: str, role_name: str, start: datetime, end: datetime, reason: str) -> str:
    delegator_doc = db["users"].find_one({"Username": delegator_name})
    delegatee_doc = db["users"].find_one({"Username": delegatee_name})
    role_doc = db["roles"].find_one({"Role_name": role_name})
    
    if not delegator_doc or not delegatee_doc or not role_doc:
        raise ValueError("Invalid user or role.")
        
    del_doc = {
        "Delegator_id": delegator_doc["_id"],
        "Delegatee_id": delegatee_doc["_id"],
        "Target_Role_id": role_doc["_id"],
        "Delegation_type": "Peer-to-Peer",
        "Reason": reason,
        "Status": "Active",
        "Start_time": start,
        "End_time": end
    }
    
    result = db["delegations"].insert_one(del_doc)
    return str(result.inserted_id)

@audit_action(action="REVOKE_DELEGATION", target_entity="delegations")
def revoke_delegation(db, admin_id: str, delegation_id: str) -> bool:
    if not _is_admin(db, admin_id):
        raise PermissionError("Only Admins can manually revoke delegations.")
        
    result = db["delegations"].update_one(
        {"_id": safe_objectid(delegation_id)},
        {"$set": {"Status": "Revoked", "End_time": datetime.utcnow()}}
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

@audit_action(action="DELETE_USER", target_entity="users")
def delete_user(db, admin_id: str, target_user_id: str) -> bool:
    if not _is_admin(db, admin_id):
        raise PermissionError("Access Denied: Only Admins can delete users.")

    result = db["users"].delete_one({"_id": safe_objectid(target_user_id)})
    return result.deleted_count > 0

@audit_action(action="DELETE_ROLE", target_entity="roles")
def delete_role(db, admin_id: str, role_name: str) -> bool:
    if not _is_admin(db, admin_id):
        raise PermissionError("Access Denied: Only Admins can delete roles.")

    result = db["roles"].delete_one({"Role_name": role_name})
    return result.deleted_count > 0
