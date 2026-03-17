import os
from typing import Any, Dict

import certifi
from pymongo import MongoClient
from pymongo.errors import CollectionInvalid, OperationFailure

try:
    import streamlit as st
except Exception:  # pragma: no cover - streamlit may be unavailable in pure backend runs
    st = None

client = None
db_name_cached = None


def get_collection_templates() -> Dict[str, Dict[str, Any]]:
    """Exact document structures used as canonical templates for G41 collections."""
    return {
        "users": {
            "_id": "ObjectId",
            "Username": "string",
            "Hashed_password": "string",
            "Email": "string",
            "Status": "Active|Inactive|Suspended",
            "Assigned_Roles": ["ObjectId"],
        },
        "roles": {
            "_id": "ObjectId",
            "Role_name": "string",
            "Description": "string",
            "Level": "int",
            "Parent_Role_id": "ObjectId|null",
            "Permissions": ["ObjectId"],
        },
        "permissions": {
            "_id": "ObjectId",
            "Permission_name": "string",
            "Description": "string",
        },
        "audit_logs": {
            "_id": "ObjectId",
            "User_id": "ObjectId|null",
            "Action": "string",
            "Target_Entity": "string",
            "Timestamp": "datetime",
            "IP_Address": "string",
            "Status": "SUCCESS|FAILED",
            "Details": "object|null",
        },
    }

def get_db_connection():
    global client, db_name_cached
    if client is None:
        try:
            # First try streamlit secrets (preferred in Streamlit Cloud)
            if st is None:
                raise KeyError("streamlit unavailable")
            mongo_uri = st.secrets["mongo"]["uri"]
            db_name_cached = st.secrets["mongo"]["db_name"]
        except (FileNotFoundError, KeyError, AttributeError):
            # Fallback to local environment variables
            mongo_uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
            db_name_cached = os.environ.get("MONGO_DB_NAME", "CDSS_G41")

        # certifi.where() avoids SSL errors on some OS
        client = MongoClient(mongo_uri, tlsCAFile=certifi.where())
    
    return client[db_name_cached]


def enforce_db_schema(db):
    """
    Applies $jsonSchema validators to enforce data integrity 
    in our NoSQL collections. Similar to SQL table definitions.
    """
    
    # 1. Users Schema
    users_validator = {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["Username", "Hashed_password", "Email", "Status"],
            "properties": {
                "Username": {"bsonType": "string", "description": "must be a string and is required"},
                "Hashed_password": {"bsonType": "string", "description": "must be a string and is required"},
                "Email": {"bsonType": "string", "pattern": "^.+@.+$", "description": "must be a valid email string and is required"},
                "Status": {"enum": ["Active", "Inactive", "Suspended"], "description": "must be either Active, Inactive, or Suspended"},
                "Assigned_Roles": {
                    "bsonType": "array",
                    "description": "must be an array of ObjectIds referencing roles",
                    "items": { "bsonType": "objectId" }
                }
            }
        }
    }
    
    # 2. Roles Schema
    roles_validator = {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["Role_name", "Level"],
            "properties": {
                "Role_name": {"bsonType": "string", "description": "must be a string (e.g., 'Lead_Doctor')"},
                "Description": {"bsonType": "string"},
                "Level": {"bsonType": "int", "description": "Hierarchy level (e.g., 1 for Admin, 5 for Patient)"},
                "Parent_Role_id": {"bsonType": ["objectId", "null"], "description": "ObjectId of the parent role for inheritance"},
                "Permissions": {
                    "bsonType": "array", 
                    "description": "Array of ObjectIds referencing permissions",
                    "items": {"bsonType": "objectId"}
                }
            }
        }
    }
    
    # 3. Permissions Schema
    permissions_validator = {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["Permission_name"],
            "properties": {
                "Permission_name": {"bsonType": "string", "description": "Unique string like 'READ_PATIENT_DATA'"},
                "Description": {"bsonType": "string"}
            }
        }
    }
    
    # 4. Audit Logs Schema
    logs_validator = {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["Action", "Timestamp"],
            "properties": {
                "User_id": {"bsonType": ["objectId", "null"], "description": "ObjectId of the user who initiated the action"},
                "Action": {"bsonType": "string", "description": "Description of the event"},
                "Target_Entity": {"bsonType": "string", "description": "The table or entity modified"},
                "Timestamp": {"bsonType": "date"},
                "IP_Address": {"bsonType": "string"},
                "Status": {"enum": ["SUCCESS", "FAILED"], "description": "Success/Failure status"},
                "Details": {"bsonType": ["object", "null"], "description": "Optional structured metadata"},
            }
        }
    }

    validators = [
        ("users", users_validator),
        ("roles", roles_validator),
        ("permissions", permissions_validator),
        ("audit_logs", logs_validator)
    ]

    for collection_name, validator in validators:
        try:
            # Try applying validator to existing collection
            db.command("collMod", collection_name, validator=validator)
            print(f"Updated schema validator for `{collection_name}`.")
        except OperationFailure as e:
            if "ns does not exist" in str(e).lower():
                # Collection doesn't exist, create it with validator
                db.create_collection(collection_name, validator=validator)
                print(f"Created collection `{collection_name}` with schema validator.")
            else:
                print(f"Error configuring `{collection_name}`: {e}")
                raise
        except CollectionInvalid as e:
            print(f"Collection creation race for `{collection_name}`: {e}")


def create_indexes(db):
    """
    Creates necessary database indexes to ensure uniqueness and fast queries.
    """
    # Unique Constraints
    db.users.create_index("Email", unique=True)
    db.users.create_index("Username", unique=True)
    db.roles.create_index("Role_name", unique=True)
    db.permissions.create_index("Permission_name", unique=True)
    
    # Performance Indexes
    db.roles.create_index("Parent_Role_id")
    db.users.create_index("Assigned_Roles")
    db.audit_logs.create_index("Timestamp")
    db.audit_logs.create_index([("User_id", 1), ("Timestamp", -1)])
    print("Database indexes ensured.")


def init_db():
    print("Connecting to MongoDB...")
    db = get_db_connection()
    print(f"Connected to database: {db.name}")
    
    enforce_db_schema(db)
    create_indexes(db)
    return db


if __name__ == "__main__":
    init_db()
