import sys
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

def now_ist():
    """Return current time in IST as a naive datetime (matches MongoDB storage)."""
    return datetime.now(tz=IST).replace(tzinfo=None)
from bson import ObjectId

# Add the project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import init_db

def seed_db():
    db = init_db()
    print("🚀 Resetting database and seeding fresh test data...")

    # Clear existing data for a total reset
    collections = ["users", "roles", "permissions", "delegations", "audit_logs", "overrides", "access_reviews"]
    for coll in collections:
        db[coll].delete_many({})
    
    print(f"🗑️  Cleared {len(collections)} collections.")

    # 1. Base Permissions
    perms = [
        {"Permission_name": "READ_PATIENT_DATA", "Description": "Can view patient records"},
        {"Permission_name": "EDIT_PATIENT_DATA", "Description": "Can edit patient records"},
        {"Permission_name": "DELETE_PATIENT_DATA", "Description": "Can permanently remove records"},
        {"Permission_name": "CREATE_USER", "Description": "Can add new system users"},
        {"Permission_name": "VIEW_AUDIT_LOGS", "Description": "Can view system audit logs"},
        {"Permission_name": "REQUEST_DELEGATION", "Description": "Can request temporary access"},
        {"Permission_name": "APPROVE_DELEGATION", "Description": "Can approve temporary access"}
    ]
    
    db.permissions.insert_many(perms)
    perm_map = {p["Permission_name"]: p["_id"] for p in db.permissions.find()}
    print(f"✅ Instantiated {len(perms)} Permissions.")

    # 2. Roles (Logical Hierarchy)

    # Patient Role (Base public role)
    patient_role = {
        "Role_name": "Patient",
        "Description": "Read-only access to own health data",
        "Level": 5,
        "Parent_Role_id": None,
        "Permissions": [perm_map["READ_PATIENT_DATA"]]
    }
    patient_role_id = db.roles.insert_one(patient_role).inserted_id

    # Doctor Role (Base clinical)
    doctor_role = {
        "Role_name": "Doctor",
        "Description": "Standard clinical access",
        "Level": 3,
        "Parent_Role_id": None,
        "Permissions": [perm_map["READ_PATIENT_DATA"], perm_map["EDIT_PATIENT_DATA"], perm_map["REQUEST_DELEGATION"]]
    }
    doctor_id = db.roles.insert_one(doctor_role).inserted_id

    # Lead Doctor Role (Inherits from Doctor)
    lead_doctor_role = {
        "Role_name": "Lead_Doctor",
        "Description": "Senior clinical lead with approval authority",
        "Level": 2,
        "Parent_Role_id": doctor_id,
        "Permissions": [perm_map["APPROVE_DELEGATION"]]
    }
    lead_doctor_id = db.roles.insert_one(lead_doctor_role).inserted_id

    # Admin Role (Independent administrative role)
    admin_role = {
        "Role_name": "Admin",
        "Description": "System administrative access",
        "Level": 1,
        "Parent_Role_id": None,  # Admin is separate from Clinical hierarchy
        "Permissions": list(perm_map.values())  # Superuser: all permissions
    }
    admin_role_id = db.roles.insert_one(admin_role).inserted_id

    print("✅ Instantiated roles: Patient, Doctor -> Lead_Doctor (Inheritance) and Admin (Independent).")

    # 3. Test Users
    # Password set to "password123" (sha256)
    hashed_pw = "ef92b778bafe771e89245b89ecbc08a44a4e166c06659911881f383d4473e94f"

    # IMPORTANT: Assigned_Roles MUST be stored as dicts {"role_id": ObjectId}
    # so that all consumers (login, rbac, admin_service) can use .get("role_id")
    users_data = [
        {
            "Username": "admin_alice",
            "Email": "alice@hospital.com",
            "Hashed_password": hashed_pw,
            "Status": "Active",
            # MULTI-ROLE: Alice is both Admin and Lead Doctor
            "Assigned_Roles": [
                {"role_id": admin_role_id},
                {"role_id": lead_doctor_id}
            ]
        },
        {
            "Username": "dr_bob",
            "Email": "bob@hospital.com",
            "Hashed_password": hashed_pw,
            "Status": "Active",
            "Assigned_Roles": [{"role_id": doctor_id}]
        },
        {
            "Username": "lead_dr_charlie",
            "Email": "charlie@hospital.com",
            "Hashed_password": hashed_pw,
            "Status": "Active",
            "Assigned_Roles": [{"role_id": lead_doctor_id}]
        },
        {
            "Username": "patient_diana",
            "Email": "diana@hospital.com",
            "Hashed_password": hashed_pw,
            "Status": "Active",
            "Assigned_Roles": [{"role_id": patient_role_id}]
        }
    ]

    db.users.insert_many(users_data)
    print("✅ Instantiated 4 users with Multi-Role proof-of-concept.")

    # 4. Advanced Test Cases (G5 Module 41 Specific)
    # Timestamps are relative to seed time so the demo data looks fresh
    now = now_ist()
    alice = db.users.find_one({"Username": "admin_alice"})
    bob = db.users.find_one({"Username": "dr_bob"})
    charlie = db.users.find_one({"Username": "lead_dr_charlie"})
    diana = db.users.find_one({"Username": "patient_diana"})

    # A. Active Delegation: Bob (Doctor) delegates Doctor role to Charlie (Lead Doctor)
    # Started 2 hours ago, expires in 2 days — shows active delegation during demo
    db.delegations.insert_one({
        "Delegator_id": bob["_id"],
        "Delegatee_id": charlie["_id"],
        "Target_Role_id": doctor_id,
        "Delegation_type": "Hierarchical",
        "Reason": "Conference attendance coverage",
        "Status": "Active",
        "Start_time": now - timedelta(hours=2),
        "End_time": now + timedelta(days=2)
    })

    # B. Pending Delegation: Charlie requests to delegate Lead_Doctor to Bob
    # This gives the demo an item in the Approval Inbox
    db.delegations.insert_one({
        "Delegator_id": charlie["_id"],
        "Delegatee_id": bob["_id"],
        "Target_Role_id": lead_doctor_id,
        "Delegation_type": "Peer-to-Peer",
        "Reason": "Supervision handover for night shift",
        "Status": "Pending",
        "Start_time": now,
        "End_time": now + timedelta(hours=8)
    })

    # C. Break-Glass Override — happened 15 min ago, still unresolved
    db.overrides.insert_one({
        "user_id": bob["_id"],
        "overridden_system": "HIGH-RISK-DATABASE-01",
        "reason": "Emergency triage during system outage",
        "timestamp": now - timedelta(minutes=15),
        "duration_hours": 2,
        "status": "Active Alert",
        "resolved": False,
        "resolved_by": None,
        "resolved_at": None
    })

    # D. Access Review Campaign — created yesterday, deadline in 3 days
    db.access_reviews.insert_one({
        "title": "Hospital Compliance Review Q2 2026",
        "deadline": now + timedelta(days=3),
        "created_by": alice["_id"],
        "created_at": now - timedelta(hours=18),
        "status": "Active",
        "reviews": [
            {"user_id": bob["_id"], "role_id": doctor_id, "status": "Pending", "reviewed_by": None, "review_date": None},
            {"user_id": charlie["_id"], "role_id": lead_doctor_id, "status": "Pending", "reviewed_by": None, "review_date": None}
        ]
    })

    # E. Pre-seeded audit logs for a realistic audit trail
    audit_entries = [
        {
            "User_id": alice["_id"],
            "Action": "ASSIGN_ROLE",
            "Target_Entity": "users",
            "Timestamp": now - timedelta(hours=20),
            "IP_Address": "192.168.1.10",
            "Status": "SUCCESS",
            "Details": None,
        },
        {
            "User_id": bob["_id"],
            "Action": "VIEW_PATIENT_AUDIT_LOGS",
            "Target_Entity": str(diana["_id"]),
            "Timestamp": now - timedelta(hours=3),
            "IP_Address": "192.168.1.22",
            "Status": "SUCCESS",
            "Details": None,
        },
        {
            "User_id": charlie["_id"],
            "Action": "CREATE_DELEGATION",
            "Target_Entity": "delegations",
            "Timestamp": now - timedelta(minutes=45),
            "IP_Address": "192.168.1.35",
            "Status": "SUCCESS",
            "Details": None,
        },
        {
            "User_id": bob["_id"],
            "Action": "LOG_EMERGENCY_OVERRIDE",
            "Target_Entity": "overrides",
            "Timestamp": now - timedelta(minutes=15),
            "IP_Address": "192.168.1.22",
            "Status": "SUCCESS",
            "Details": {"system": "HIGH-RISK-DATABASE-01"},
        },
    ]
    db.audit_logs.insert_many(audit_entries)

    print("✅ Seeded delegations, overrides, and review campaigns.")
    print("")
    print("📋 Test Credentials (password: password123):")
    print("   admin_alice   → Admin + Lead_Doctor (Admin Dashboard)")
    print("   lead_dr_charlie → Lead_Doctor (Doctor Dashboard with approval powers)")
    print("   dr_bob        → Doctor (Doctor Dashboard)")
    print("   patient_diana → Patient (Patient Dashboard)")
    print("✨ Database reset and seeding complete!")

if __name__ == "__main__":
    seed_db()
