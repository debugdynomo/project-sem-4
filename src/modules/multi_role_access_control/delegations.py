from datetime import datetime, timedelta

def create_delegation(db, delegator_id: str, delegatee_id: str, target_role: str, ttl_hours: int, reason: str, delegation_type: str = "Peer-to-Peer") -> str:
    """
    Creates a time-bound delegation of a specific role from one user to another.
    Includes business logic for hierarchical, peer-to-peer, and emergency rules.
    """
    # 1. Rules validation based on delegation_type
    if delegation_type not in ["Hierarchical", "Peer-to-Peer", "Emergency"]:
        raise ValueError("Invalid delegation_type. Must be Hierarchical, Peer-to-Peer, or Emergency")
        
    if delegation_type == "Emergency" and ttl_hours > 24:
        raise ValueError("Emergency delegations cannot exceed 24 hours.")
        
    start_time = datetime.utcnow()
    end_time = start_time + timedelta(hours=ttl_hours)
    
    delegation_doc = {
        "delegator_id": delegator_id,
        "delegatee_id": delegatee_id,
        "target_role": target_role,
        "delegation_type": delegation_type,
        "start_time": start_time,
        "end_time": end_time,
        "reason": reason,
        "status": "Active" # Can manually be changed to "Revoked" earlier if needed
    }
    
    result = db["delegations"].insert_one(delegation_doc)
    return str(result.inserted_id)

def get_role_permissions(db, role_name: str) -> list:
    """Helper tool to fetch permissions array for a given role dynamically."""
    role = db["roles"].find_one({"name": role_name})
    return role.get("permissions", []) if role else []

def evaluate_access(db, user_id: str, required_permission: str, effective_permissions_list: list) -> bool:
    """
    Central gatekeeper function.
    Conflict Resolution Strategy: 
    1. Short-circuits to True if the static 'effective_permissions_list' contains the permission.
    2. If static denies, queries the delegations collection to check temporary roles.
    3. If no active, matching temporary roles are found, universally evaluates to False.
    """
    # Check 1: Static / Inherited Permissions
    if required_permission in effective_permissions_list:
        return True
        
    # Check 2: Temporary Delegated Permissions
    now = datetime.utcnow()
    
    # Query for any delegations that are fully active right now.
    # Note: Documents missing due to TTL expiration will naturally not return here.
    active_delegations = db["delegations"].find({
        "delegatee_id": user_id,
        "status": "Active",
        "start_time": {"$lte": now},
        "end_time": {"$gt": now}
    })
    
    # Iterate through active temporary roles to map to permissions
    for delegation in active_delegations:
        temp_role = delegation.get("target_role")
        temp_permissions = get_role_permissions(db, temp_role)
        
        if required_permission in temp_permissions:
            return True # Temporary Access explicitly granted
            
    return False # Default Deny
