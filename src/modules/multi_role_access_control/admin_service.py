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


@audit_action(action="DELETE_USER", target_entity="users")
def delete_user(db, admin_id: str, target_user_id: str) -> bool:
    """
    Deletes a user from the system.
    """
    if not _is_admin(db, admin_id):
        raise PermissionError("Only Admins can delete users.")

    result = db["users"].delete_one({"_id": safe_objectid(target_user_id)})
    return result.deleted_count > 0


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

def get_all_permissions(db) -> list:
    return list(db["permissions"].find({}))

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


@audit_action(action="DELETE_ROLE", target_entity="roles")
def delete_role(db, admin_id: str, role_name: str) -> bool:
    """
    Deletes a role from the system.
    """
    if not _is_admin(db, admin_id):
        raise PermissionError("Only Admins can delete roles.")

    result = db["roles"].delete_one({"Role_name": role_name})
    return result.deleted_count > 0


@audit_action(action="GRANT_PERMISSION", target_entity="roles")
def assign_permission_to_role(db, admin_id: str, role_name: str, permission_name: str) -> bool:
    """
    Grants a permission to a role.
    """
    if not _is_admin(db, admin_id):
        raise PermissionError("Only Admins can grant permissions.")

    # 1. Resolve role_id
    role = db["roles"].find_one({"Role_name": role_name})
    if not role:
        raise ValueError(f"Role '{role_name}' not found.")
    
    # 2. Resolve permission_id
    perm = db["permissions"].find_one({"Permission_name": permission_name})
    if not perm: 
        raise ValueError(f"Permission '{permission_name}' not found.")

    # 3. Update role
    result = db["roles"].update_one(
        {"_id": role["_id"]},
        {"$addToSet": {"Permissions": perm["_id"]}}
    )
    return result.modified_count > 0


# --- DELEGATION SERVICE LOGIC ---

@audit_action(action="CREATE_DELEGATION", target_entity="delegations")
def create_delegation(db, delegator_id: str, delegatee_id: str, 
                      target_role_id: str, start_time: datetime, end_time: datetime, 
                      reason: str, delegation_type: str = "Peer-to-Peer") -> str:
    """
    Creates an active delegation between two users.
    Validates ObjectIds robustly to comply with MongoDB $jsonSchema.
    """
    delegation_doc = {
        "Delegator_id": ObjectId(delegator_id) if not isinstance(delegator_id, ObjectId) else delegator_id,
        "Delegatee_id": ObjectId(delegatee_id) if not isinstance(delegatee_id, ObjectId) else delegatee_id,
        "Target_Role_id": ObjectId(target_role_id) if not isinstance(target_role_id, ObjectId) else target_role_id,
        "Delegation_type": delegation_type,
        "Reason": reason,
        "Status": "Active",
        "Start_time": start_time,
        "End_time": end_time
    }
    
    result = db["delegations"].insert_one(delegation_doc)
    return str(result.inserted_id)

@audit_action(action="REVOKE_DELEGATION", target_entity="delegations")
def revoke_delegation(db, admin_id: str, delegation_id: str) -> bool:
    """
    Revokes an existing active delegation.
    """
    result = db["delegations"].update_one(
        {"_id": safe_objectid(delegation_id)},
        {"$set": {"Status": "Revoked"}}
    )
    return result.modified_count > 0

def get_pending_delegations(db) -> list:
    """
    Returns pending delegations enriched with names for UI display.
    """
    delegations = list(db["delegations"].find({"Status": "Pending"}))
    enriched = []
    for d in delegations:
        delegator = db["users"].find_one({"_id": d["Delegator_id"]})
        delegatee = db["users"].find_one({"_id": d["Delegatee_id"]})
        t_role = db["roles"].find_one({"_id": d["Target_Role_id"]})
        
        d["Delegator_Name"] = delegator["Username"] if delegator else "Unknown"
        d["Delegatee_Name"] = delegatee["Username"] if delegatee else "Unknown"
        d["Target_Role_Name"] = t_role["Role_name"] if t_role else "Unknown"
        enriched.append(d)
    return enriched

def get_my_delegation_history(db, user_id: str) -> list:
    """
    Returns history of delegations created by this user.
    """
    return list(db["delegations"].find({"Delegator_id": safe_objectid(user_id)}).sort("Start_time", -1))

def get_active_delegations(db) -> list:
    """
    Returns a list of all delegations with status 'Active'.
    Enriched with names for UI display.
    """
    delegations = list(db["delegations"].find({"Status": "Active"}))
    enriched = []
    for d in delegations:
        delegator = db["users"].find_one({"_id": d["Delegator_id"]})
        delegatee = db["users"].find_one({"_id": d["Delegatee_id"]})
        t_role = db["roles"].find_one({"_id": d["Target_Role_id"]})
        
        d["Delegator_Name"] = delegator["Username"] if delegator else "Unknown"
        d["Delegatee_Name"] = delegatee["Username"] if delegatee else "Unknown"
        d["Target_Role_Name"] = t_role["Role_name"] if t_role else "Unknown"
        enriched.append(d)
    return enriched

