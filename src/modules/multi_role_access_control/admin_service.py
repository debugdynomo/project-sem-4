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
    for role_item in user.get("Assigned_Roles", []):
        if isinstance(role_item, dict):
            valid_until = role_item.get("valid_until")
            if valid_until and valid_until < datetime.utcnow():
                continue
            role_id = role_item.get("role_id")
        else:
            role_id = role_item # backward compatibility
            
        role = db["roles"].find_one({"_id": safe_objectid(role_id)})
        if role and role.get("Role_name") in ["Admin", "System_Admin"]:
            return True
    return False

def __can_approve_delegations(db, current_user_id: str) -> bool:
    """Allows Admins OR Lead Doctors to approve delegations."""
    if _is_admin(db, current_user_id):
        return True
    user = db["users"].find_one({"_id": safe_objectid(current_user_id)})
    if not user: return False
    for role_item in user.get("Assigned_Roles", []):
        r_id = role_item.get("role_id") if isinstance(role_item, dict) else role_item
        role = db["roles"].find_one({"_id": safe_objectid(r_id)})
        if role and role.get("Role_name") in ["Lead Doctor", "Lead_Doctor"]:
            return True
    return False


def check_role_conflicts(db, target_user_id: str, new_role: str):
    user = db["users"].find_one({"_id": safe_objectid(target_user_id)})
    if not user: return
    
    # Conflict matrix definition for demonstration
    conflict_matrix = {
        "Doctor": ["Patient"],
        "Patient": ["Doctor", "Admin", "Lead Doctor", "Nurse"],
        "Admin": ["Patient"]
    }
    
    incompatible_roles = conflict_matrix.get(new_role, [])
    
    for r in user.get("Assigned_Roles", []):
        if isinstance(r, dict):
            r_id = r.get("role_id")
        else:
            r_id = r
        role_doc = db["roles"].find_one({"_id": r_id})
        if role_doc and role_doc.get("Role_name") in incompatible_roles:
            raise ValueError(f"Conflict Error: Cannot assign '{new_role}' while user holds incompatible role '{role_doc.get('Role_name')}'.")

@audit_action(action="ASSIGN_ROLE", target_entity="users")
def assign_role_to_user(db, admin_id: str, target_user_id: str, new_role: str, context: dict = None, valid_until: datetime = None) -> bool:
    """
    P5 Admin Capability: Appends a static role to a target user.
    """
    check_role_conflicts(db, target_user_id, new_role)

    if not _is_admin(db, admin_id):
        raise PermissionError("Access Denied: Only Admins can execute role bindings.")

    # Look up role ObjectId by name
    role_doc = db["roles"].find_one({"Role_name": new_role})
    if not role_doc:
        raise ValueError(f"Role '{new_role}' does not exist.")

    role_assignment = {
        "role_id": role_doc["_id"]
    }
    if context:
        role_assignment["context"] = context
    if valid_until:
        role_assignment["valid_until"] = valid_until

    result = db["users"].update_one(
        {"_id": safe_objectid(target_user_id)},
        {"$addToSet": {"Assigned_Roles": role_assignment}}
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

    user = db["users"].find_one({"_id": safe_objectid(target_user_id)})
    if not user: return False
    
    new_roles = []
    modified = False
    for r in user.get("Assigned_Roles", []):
        if isinstance(r, dict) and r.get("role_id") == role_doc["_id"]:
            modified = True
            continue
        if r == role_doc["_id"]:
            modified = True
            continue
        new_roles.append(r)
        
    if not modified:
        return False

    result = db["users"].update_one(
        {"_id": safe_objectid(target_user_id)},
        {"$set": {"Assigned_Roles": new_roles}}
    )
    return result.modified_count > 0

def get_all_roles(db) -> list:
    return list(db["roles"].find({}))

def get_all_permissions(db) -> list:
    return list(db["permissions"].find({}))

@audit_action(action="CREATE_ROLE", target_entity="roles")
def create_role(db, admin_id: str, role_name: str, description: str, level: int = 5, parent_role_id=None) -> str:
    if not _is_admin(db, admin_id):
        raise PermissionError("Only Admins can create roles.")
    
    role_doc = {
        "Role_name": role_name,
        "Description": description,
        "Level": int(level),
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


@audit_action(action="REVOKE_PERMISSION", target_entity="roles")
def revoke_permission_from_role(db, admin_id: str, role_name: str, permission_name: str) -> bool:
    """
    Revokes a permission from a role.
    """
    if not _is_admin(db, admin_id):
        raise PermissionError("Only Admins can revoke permissions.")

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
        {"$pull": {"Permissions": perm["_id"]}}
    )
    return result.modified_count > 0


# --- DELEGATION SERVICE LOGIC ---

@audit_action(action="CREATE_DELEGATION", target_entity="delegations")
def create_delegation(db, delegator_id: str, delegatee_id: str, 
                      target_role_id: str, start_time: datetime, end_time: datetime, 
                      reason: str, delegation_type: str = "Peer-to-Peer") -> str:
    """
    Creates a delegation request with Status='Pending'.
    An Admin must approve it before it becomes Active.
    """
    if delegation_type not in ["Hierarchical", "Peer-to-Peer", "Emergency", "Health-Proxy"]:
        raise ValueError("Invalid delegation_type. Must be Hierarchical, Peer-to-Peer, Emergency, or Health-Proxy")

    delegator = db["users"].find_one({"_id": safe_objectid(delegator_id)})
    delegatee = db["users"].find_one({"_id": safe_objectid(delegatee_id)})
    if not delegator or not delegatee:
        raise ValueError("Delegator or Delegatee not found.")

    target_role_doc = db["roles"].find_one({"_id": safe_objectid(target_role_id)})
    if not target_role_doc:
        raise ValueError("Target role not found.")

    target_role_id_obj = target_role_doc["_id"]

    # Validation: Ownership & Level Check
    owns_role = False
    delegator_best_level = 99
    
    # Fetch active delegations for delegator
    del_active_cursor = db["delegations"].find({
        "Delegatee_id": safe_objectid(delegator_id),
        "Status": "Active",
        "Start_time": {"$lte": datetime.utcnow()},
        "End_time": {"$gt": datetime.utcnow()}
    })
    delegator_roles = [safe_objectid(r.get("role_id") if isinstance(r, dict) else r) for r in delegator.get("Assigned_Roles", [])]
    for d in del_active_cursor:
        delegator_roles.append(safe_objectid(d["Target_Role_id"]))

    for r_id in set(delegator_roles):
        r_doc = db["roles"].find_one({"_id": r_id})
        if r_doc:
            if r_doc["_id"] == target_role_id_obj:
                owns_role = True
            level = r_doc.get("Level", 99)
            if level < delegator_best_level:
                delegator_best_level = level
    
    delegatee_best_level = 99
    delegatee_active_cursor = db["delegations"].find({
        "Delegatee_id": safe_objectid(delegatee_id),
        "Status": "Active",
        "Start_time": {"$lte": datetime.utcnow()},
        "End_time": {"$gt": datetime.utcnow()}
    })
    delegatee_roles = [safe_objectid(r.get("role_id") if isinstance(r, dict) else r) for r in delegatee.get("Assigned_Roles", [])]
    for d in delegatee_active_cursor:
        delegatee_roles.append(safe_objectid(d["Target_Role_id"]))

    for r_id in set(delegatee_roles):
        r_doc = db["roles"].find_one({"_id": r_id})
        if r_doc:
            level = r_doc.get("Level", 99)
            if level < delegatee_best_level:
                delegatee_best_level = level

    if not owns_role and delegation_type not in ("Emergency", "Health-Proxy"):
        raise PermissionError(f"Delegator does not possess the target role.")

    # Health-Proxy: patient delegates own role to a caregiver — skip level checks
    if delegation_type == "Peer-to-Peer" and delegator_best_level != delegatee_best_level:
        raise PermissionError(f"Peer-to-Peer delegation requires equal role levels (Delegator Rank: {delegator_best_level}, Delegatee Rank: {delegatee_best_level}).")
    elif delegation_type == "Hierarchical" and delegator_best_level >= delegatee_best_level:
        raise PermissionError(f"Hierarchical delegation requires Delegator to be a higher rank than Delegatee (Delegator Rank: {delegator_best_level}, Delegatee Rank: {delegatee_best_level}). Note: Lower number = Higher rank.")

    # Prevent duplicate delegations
    existing = db["delegations"].find_one({
        "Delegator_id": safe_objectid(delegator_id),
        "Delegatee_id": safe_objectid(delegatee_id),
        "Target_Role_id": safe_objectid(target_role_id),
        "Status": {"$in": ["Pending", "Active"]}
    })
    
    if existing:
        raise ValueError("A pending or active delegation already exists for this role between these users.")

    # Duration limit check
    duration = end_time - start_time
    if delegation_type == "Emergency" and duration > timedelta(days=1):
        raise ValueError("Emergency delegations cannot exceed 24 hours.")
    elif delegation_type == "Peer-to-Peer" and duration > timedelta(days=7):
        raise ValueError("Peer-to-Peer delegations cannot exceed 7 days.")
    elif delegation_type in ("Hierarchical", "Health-Proxy") and duration > timedelta(days=30):
        raise ValueError(f"{delegation_type} delegations cannot exceed 30 days.")

    # Cycle detection
    cycle_check = list(db["delegations"].aggregate([
        {"$match": {"Delegator_id": safe_objectid(delegatee_id), "Status": "Active"}},
        {"$graphLookup": {
            "from": "delegations",
            "startWith": "$Delegatee_id",
            "connectFromField": "Delegatee_id",
            "connectToField": "Delegator_id",
            "as": "chain",
            "restrictSearchWithMatch": {"Status": "Active"}
        }}
    ]))
    
    is_cycle = False
    for doc in cycle_check:
        if doc["Delegatee_id"] == safe_objectid(delegator_id):
            is_cycle = True
            break
        for chain_link in doc.get("chain", []):
            if chain_link["Delegatee_id"] == safe_objectid(delegator_id):
                is_cycle = True
                break
                
    if is_cycle:
        raise ValueError("Cyclic delegation detected. This action would create an infinite delegation loop.")

    delegation_doc = {
        "Delegator_id": safe_objectid(delegator_id),
        "Delegatee_id": safe_objectid(delegatee_id),
        "Target_Role_id": safe_objectid(target_role_id),
        "Delegation_type": delegation_type,
        "Reason": reason,
        "Status": "Pending",
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


@audit_action(action="APPROVE_DELEGATION", target_entity="delegations")
def approve_delegation(db, admin_id: str, delegation_id: str) -> bool:
    """
    Approves a Pending delegation, setting its status to Active.
    """
    if not __can_approve_delegations(db, admin_id):
        raise PermissionError("Only Admins or Lead Doctors can approve delegations.")

    result = db["delegations"].update_one(
        {"_id": safe_objectid(delegation_id), "Status": "Pending"},
        {"$set": {"Status": "Active"}}
    )
    return result.modified_count > 0


@audit_action(action="REJECT_DELEGATION", target_entity="delegations")
def reject_delegation(db, admin_id: str, delegation_id: str, reason: str = "") -> bool:
    """
    Rejects a Pending delegation, setting its status to Rejected.
    """
    if not __can_approve_delegations(db, admin_id):
        raise PermissionError("Only Admins or Lead Doctors can reject delegations.")

    result = db["delegations"].update_one(
        {"_id": safe_objectid(delegation_id), "Status": "Pending"},
        {"$set": {"Status": "Rejected", "Rejection_Reason": reason}}
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

@audit_action(action="CLEANUP_EXPIRED_ROLES", target_entity="users")
def cleanup_expired_roles(db, system_admin_id: str) -> int:
    """
    Scans all users and removes Assigned_Roles objects whose 'valid_until' is in the past.
    Returns the number of users modified.
    """
    now = datetime.utcnow()
    users = db["users"].find({})
    
    modified_count = 0
    for u in users:
        assigned = u.get("Assigned_Roles", [])
        new_roles = []
        has_expired = False
        
        for r in assigned:
            if isinstance(r, dict) and "valid_until" in r:
                if r["valid_until"] < now:
                    has_expired = True
                    continue  # drop it
            new_roles.append(r)
            
        if has_expired:
            db["users"].update_one(
                {"_id": u["_id"]},
                {"$set": {"Assigned_Roles": new_roles}}
            )
            modified_count += 1
            
    return modified_count


# --- UPCOMING EXPIRATIONS ---

def get_upcoming_expirations(db, days_ahead: int = 7) -> list:
    """
    Scans delegations and time-limited roles expiring within `days_ahead` days.
    Returns an enriched list for admin dashboard notifications.
    """
    now = datetime.utcnow()
    cutoff = now + timedelta(days=days_ahead)
    results = []

    # 1. Delegations expiring soon
    expiring_delegations = list(db["delegations"].find({
        "Status": "Active",
        "End_time": {"$gt": now, "$lte": cutoff}
    }).sort("End_time", 1))

    for d in expiring_delegations:
        delegator = db["users"].find_one({"_id": d["Delegator_id"]})
        delegatee = db["users"].find_one({"_id": d["Delegatee_id"]})
        role_doc = db["roles"].find_one({"_id": d["Target_Role_id"]})

        hours_left = max(0, (d["End_time"] - now).total_seconds() / 3600)

        results.append({
            "type": "Delegation",
            "delegator": delegator.get("Username", "Unknown") if delegator else "Unknown",
            "delegatee": delegatee.get("Username", "Unknown") if delegatee else "Unknown",
            "role": role_doc.get("Role_name", "Unknown") if role_doc else "Unknown",
            "expires": d["End_time"],
            "hours_left": round(hours_left, 1),
            "id": str(d["_id"])
        })

    # 2. Time-limited roles (valid_until) expiring soon
    all_users = list(db["users"].find({}))
    for u in all_users:
        for r in u.get("Assigned_Roles", []):
            if isinstance(r, dict) and "valid_until" in r and r["valid_until"]:
                if now < r["valid_until"] <= cutoff:
                    role_doc = db["roles"].find_one({"_id": r.get("role_id")})
                    hours_left = max(0, (r["valid_until"] - now).total_seconds() / 3600)
                    results.append({
                        "type": "Time-Limited Role",
                        "delegator": "-",
                        "delegatee": u.get("Username", "Unknown"),
                        "role": role_doc.get("Role_name", "Unknown") if role_doc else "Unknown",
                        "expires": r["valid_until"],
                        "hours_left": round(hours_left, 1),
                        "id": str(u["_id"])
                    })

    return sorted(results, key=lambda x: x["expires"])


# --- CENTRAL ACCESS GATEKEEPER ---

def evaluate_access(db, user_id: str, required_permission: str, context: str = None) -> tuple:
    """
    Central gatekeeper: checks whether a user holds a specific permission.
    Optionally validates against context tags.

    Returns:
        (bool, str): (allowed, reason)
    """
    from backend.rbac import get_effective_permissions, get_user_contexts

    perms = get_effective_permissions(safe_objectid(user_id), db)

    if required_permission not in perms:
        return (False, f"Permission '{required_permission}' not in effective permissions.")

    # Optional context check
    if context:
        user_contexts = get_user_contexts(safe_objectid(user_id), db)
        if user_contexts and context not in user_contexts:
            return (False, f"Permission exists but context '{context}' is not in user's active contexts: {user_contexts}")

    return (True, "Access granted.")


# --- ROLE PERMISSIONS RESOLVER ---

def get_role_permissions(db, role_id) -> list:
    """
    Returns the full list of permission names for a role, including
    permissions inherited from parent roles (recursive).
    """
    role_id = safe_objectid(role_id)
    if not role_id:
        return []

    visited = set()
    all_perm_ids = set()

    current_id = role_id
    while current_id and str(current_id) not in visited:
        visited.add(str(current_id))
        role_doc = db["roles"].find_one({"_id": current_id})
        if not role_doc:
            break
        for pid in role_doc.get("Permissions", []):
            all_perm_ids.add(pid)
        current_id = role_doc.get("Parent_Role_id")

    if not all_perm_ids:
        return []

    perm_docs = list(db["permissions"].find({"_id": {"$in": list(all_perm_ids)}}))
    return [p.get("Permission_name", str(p["_id"])) for p in perm_docs]


# --- CONFLICT DETECTION & RESOLUTION ---

def detect_all_conflicts(db) -> list:
    """
    Scans all users and returns a list of detected role conflicts.
    Each entry contains:
        user_id, username, conflicting_roles: [(role_a, role_b), ...]
    """
    conflict_matrix = {
        "Doctor": ["Patient"],
        "Patient": ["Doctor", "Admin", "Lead_Doctor", "Nurse"],
        "Admin": ["Patient"]
    }

    all_users = list(db["users"].find({}))
    all_roles = {str(r["_id"]): r.get("Role_name") for r in db["roles"].find({})}
    conflicts = []

    for u in all_users:
        assigned = u.get("Assigned_Roles", [])
        role_names = []
        for r in assigned:
            rid = r.get("role_id") if isinstance(r, dict) else r
            name = all_roles.get(str(rid))
            if name:
                role_names.append(name)

        found = []
        checked = set()
        for rn in role_names:
            incompatible = conflict_matrix.get(rn, [])
            for other in role_names:
                pair = tuple(sorted([rn, other]))
                if other in incompatible and pair not in checked:
                    found.append(pair)
                    checked.add(pair)

        if found:
            conflicts.append({
                "user_id": str(u["_id"]),
                "username": u.get("Username", "Unknown"),
                "conflicting_roles": found
            })

    return conflicts


@audit_action(action="RESOLVE_CONFLICT", target_entity="users")
def resolve_conflict(db, admin_id: str, target_user_id: str, keep_role: str, remove_role: str) -> bool:
    """
    Admin-initiated conflict resolution: keeps one role and removes the other.
    """
    if not _is_admin(db, admin_id):
        raise PermissionError("Only Admins can resolve role conflicts.")

    return revoke_role_from_user(db, admin_id, target_user_id, remove_role)

