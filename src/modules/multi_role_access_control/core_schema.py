from pymongo import ASCENDING
from pymongo.collection import Collection

def init_core_collections(db):
    """
    Initializes core RBAC collections and indexes.
    """
    users_col = db["users"]
    roles_col = db["roles"]
    permissions_col = db["permissions"]
    audit_logs_col = db["audit_logs"]
    
    # 1. User Indexes
    users_col.create_index([("email", ASCENDING)], unique=True, name="idx_unique_user_email")
    users_col.create_index([("username", ASCENDING)], unique=True, name="idx_unique_username")
    
    # 2. Role Indexes
    roles_col.create_index([("role_name", ASCENDING)], unique=True, name="idx_unique_role_name")
    
    # 3. Permission Indexes
    permissions_col.create_index([("permission_name", ASCENDING)], unique=True, name="idx_unique_permission_name")
    
    # 4. Audit Log Indexes for faster querying
    audit_logs_col.create_index([("timestamp", ASCENDING)], name="idx_audit_timestamp")
    audit_logs_col.create_index([("user_id", ASCENDING)], name="idx_audit_user_id")
    
    print("Core RBAC collections and indexes initialized successfully.")
