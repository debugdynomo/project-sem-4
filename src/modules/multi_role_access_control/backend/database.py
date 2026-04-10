"""
database.py — MongoDB connection & schema setup for G41 Multi-Role Access Control.

Collections (mapped 1:1 from er_final.jpg):
    users, roles, permissions, delegations, audit_logs

Connection priority:
    1. st.secrets["MONGO_URI"]   (Streamlit Cloud / local secrets.toml)
    2. MONGO_URI env var          (CI, Docker, bare-metal)
    3. localhost fallback         (dev-only)
"""

import os
from typing import Any, Dict

import certifi
import streamlit as st
from pymongo import ASCENDING, MongoClient
from pymongo.database import Database
from pymongo.errors import CollectionInvalid, OperationFailure


# ---------------------------------------------------------------------------
# 1.  CONNECTION — uses @st.cache_resource so the client survives reruns
# ---------------------------------------------------------------------------

@st.cache_resource
def _init_mongo_client() -> MongoClient:
    """
    Create and cache a single MongoClient for the lifetime of the app.
    @st.cache_resource ensures this runs only once, even across Streamlit
    reruns. The client is thread-safe and connection-pooled.
    """
    try:
        uri = st.secrets["MONGO_URI"]
    except (FileNotFoundError, KeyError):
        uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")

    return MongoClient(uri, tlsCAFile=certifi.where())


def get_db_connection(db_name: str = "CDSS_G41") -> Database:
    """
    Return a pymongo Database handle.

    Parameters
    ----------
    db_name : str
        Override for the database name.  Reads from secrets → env → default.
    """
    client = _init_mongo_client()

    # Allow the DB name to come from secrets or env if not hardcoded
    try:
        resolved_name = st.secrets.get("MONGO_DB_NAME", db_name)
    except FileNotFoundError:
        resolved_name = os.environ.get("MONGO_DB_NAME", db_name)

    return client[resolved_name]


# ---------------------------------------------------------------------------
# 2.  COLLECTION TEMPLATES — canonical field reference for G41 (from ER diagram)
# ---------------------------------------------------------------------------

def get_collection_templates() -> Dict[str, Dict[str, Any]]:
    """Exact document shapes used as a reference for all 5 G41 collections."""
    return {
        "users": {
            "_id": "ObjectId",
            "Username": "string",
            "Hashed_password": "string",
            "Email": "string",
            "Status": "Active | Inactive | Suspended",
            "Assigned_Roles": ["ObjectId"],           # M:N → Assigned_to (ER)
        },
        "roles": {
            "_id": "ObjectId",
            "Role_name": "string",
            "Description": "string",
            "Level": "int",
            "Parent_Role_id": "ObjectId | null",      # Hierarchy (Recursive) (ER)
            "Permissions": ["ObjectId"],               # Grants M:N (ER)
        },
        "permissions": {
            "_id": "ObjectId",
            "Permission_name": "string",
            "Description": "string",
        },
        "delegations": {
            "_id": "ObjectId",
            "Delegator_id": "ObjectId",               # Initiates 1:N (ER)
            "Delegatee_id": "ObjectId",               # Receives  1:N (ER)
            "Target_Role_id": "ObjectId",             # Authorize N:1 (ER)
            "Delegation_type": "Hierarchical | Peer-to-Peer | Emergency | Health-Proxy",
            "Reason": "string",
            "Status": "Active | Expired | Revoked",
            "Start_time": "datetime",
            "End_time": "datetime",
        },
        "audit_logs": {
            "_id": "ObjectId",
            "User_id": "ObjectId | null",             # Generates 1:N (ER)
            "Action": "string",
            "Target_Entity": "string",
            "Timestamp": "datetime",
            "IP_Address": "string",
            "Status": "SUCCESS | FAILED",
            "Details": "object | null",
        },
    }


# ---------------------------------------------------------------------------
# 3.  SCHEMA VALIDATORS — enforce data integrity at the MongoDB engine level
# ---------------------------------------------------------------------------

_VALIDATORS: Dict[str, dict] = {
    "users": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["Username", "Hashed_password", "Email", "Status"],
            "properties": {
                "Username":        {"bsonType": "string"},
                "Hashed_password": {"bsonType": "string"},
                "Email":           {"bsonType": "string", "pattern": r"^.+@.+$"},
                "Status":          {"enum": ["Active", "Inactive", "Suspended"]},
                "Assigned_Roles":  {
                    "bsonType": "array",
                    "items": {"bsonType": ["objectId", "object"]},
                    "description": "Array of Role ObjectIds or Context Dicts (Assigned_to M:N)",
                },
            },
        }
    },
    "roles": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["Role_name", "Level"],
            "properties": {
                "Role_name":      {"bsonType": "string"},
                "Description":    {"bsonType": "string"},
                "Level":          {"bsonType": "int"},
                "Parent_Role_id": {"bsonType": ["objectId", "null"]},
                "Permissions":    {
                    "bsonType": "array",
                    "items": {"bsonType": "objectId"},
                    "description": "Array of Permission ObjectIds (Grants M:N)",
                },
            },
        }
    },
    "permissions": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["Permission_name"],
            "properties": {
                "Permission_name": {"bsonType": "string"},
                "Description":     {"bsonType": "string"},
            },
        }
    },
    "delegations": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": [
                "Delegator_id", "Delegatee_id", "Target_Role_id",
                "Status", "Start_time", "End_time",
            ],
            "properties": {
                "Delegator_id":    {"bsonType": "objectId"},
                "Delegatee_id":    {"bsonType": "objectId"},
                "Target_Role_id":  {"bsonType": "objectId"},
                "Delegation_type": {
                    "enum": ["Hierarchical", "Peer-to-Peer", "Emergency", "Health-Proxy"],
                },
                "Reason":     {"bsonType": "string"},
                "Status":     {"enum": ["Active", "Expired", "Revoked", "Pending", "Rejected"]},
                "Start_time": {"bsonType": "date"},
                "End_time":   {"bsonType": "date"},
            },
        }
    },
    "audit_logs": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["Action", "Timestamp"],
            "properties": {
                "User_id":       {"bsonType": ["objectId", "null"]},
                "Action":        {"bsonType": "string"},
                "Target_Entity": {"bsonType": "string"},
                "Timestamp":     {"bsonType": "date"},
                "IP_Address":    {"bsonType": "string"},
                "Status":        {"enum": ["SUCCESS", "FAILED"]},
                "Details":       {"bsonType": ["object", "null"]},
            },
        }
    },
}


def enforce_db_schema(db: Database) -> None:
    """Apply $jsonSchema validators to all 5 G41 collections."""
    for name, validator in _VALIDATORS.items():
        try:
            db.command("collMod", name, validator=validator)
        except OperationFailure as exc:
            if "ns does not exist" in str(exc).lower():
                db.create_collection(name, validator=validator)
            else:
                raise
        except CollectionInvalid:
            pass   # another thread/process created it first — safe to ignore


# ---------------------------------------------------------------------------
# 4.  INDEXES — uniqueness constraints + performance indexes + TTL
# ---------------------------------------------------------------------------

def create_indexes(db: Database) -> None:
    """
    Idempotent index creation for all 5 collections.
    Calling this multiple times is safe (MongoDB skips existing indexes).
    """
    # ── users ──
    db.users.create_index("Email",    unique=True, name="idx_unique_email")
    db.users.create_index("Username", unique=True, name="idx_unique_username")
    db.users.create_index("Assigned_Roles",        name="idx_assigned_roles")

    # ── roles ──
    db.roles.create_index("Role_name",     unique=True, name="idx_unique_role_name")
    db.roles.create_index("Parent_Role_id",             name="idx_parent_role")

    # ── permissions ──
    db.permissions.create_index("Permission_name", unique=True, name="idx_unique_perm")

    # ── delegations (includes TTL auto-expiry) ──
    db.delegations.create_index(
        [("End_time", ASCENDING)],
        expireAfterSeconds=0,
        name="ttl_delegation_expiry",
    )
    db.delegations.create_index(
        [("Delegatee_id", ASCENDING), ("Status", ASCENDING), ("Start_time", ASCENDING)],
        name="idx_active_delegations",
    )

    # ── audit_logs ──
    db.audit_logs.create_index("Timestamp",                      name="idx_audit_ts")
    db.audit_logs.create_index([("User_id", 1), ("Timestamp", -1)], name="idx_audit_user_ts")


# ---------------------------------------------------------------------------
# 5.  PUBLIC ENTRY POINT
# ---------------------------------------------------------------------------

def init_db() -> Database:
    """
    Full initialisation sequence:
        connect → enforce schema → create indexes → return db handle.

    Safe to call on every Streamlit rerun because the connection is cached
    and index creation is idempotent.
    """
    db = get_db_connection()
    enforce_db_schema(db)
    create_indexes(db)
    return db


# Allow standalone execution:  python -m backend.database
if __name__ == "__main__":
    database = init_db()
    print(f"✅ Connected to '{database.name}' — collections: {database.list_collection_names()}")
