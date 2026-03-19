from backend.database import init_db

def seed_db():
    db = init_db()
    print("Seeding database...")

    # Clear existing data for an idempotency
    db.users.delete_many({})
    db.roles.delete_many({})
    db.permissions.delete_many({})
    db.audit_logs.delete_many({})

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
    
    result = db.permissions.insert_many(perms)
    perm_map = {p["Permission_name"]: p["_id"] for p in db.permissions.find()}
    print(f"Instantiated {len(result.inserted_ids)} Permissions.")

    # 2. Roles (Hierarchical)
    # Note: Insert in order of dependency so we can grab ObjectIds
    
    # Patient Role
    patient_role = {
        "Role_name": "Patient",
        "Description": "Standard Patient Access",
        "Level": 5,
        "Parent_Role_id": None,
        "Permissions": [perm_map["READ_PATIENT_DATA"], perm_map["REQUEST_DELEGATION"]]
    }
    patient_id = db.roles.insert_one(patient_role).inserted_id

    # Doctor Role
    doctor_role = {
        "Role_name": "Doctor",
        "Description": "Standard Doctor Access",
        "Level": 3,
        "Parent_Role_id": None, # Doctors don't inherit patient permissions because they have different views
        "Permissions": [perm_map["READ_PATIENT_DATA"], perm_map["EDIT_PATIENT_DATA"], perm_map["REQUEST_DELEGATION"]]
    }
    doctor_id = db.roles.insert_one(doctor_role).inserted_id

    # Lead Doctor Role (Inherits from Doctor)
    lead_doctor_role = {
        "Role_name": "Lead_Doctor",
        "Description": "Senior Doctor Access",
        "Level": 2,
        "Parent_Role_id": doctor_id, # INHERITANCE HAPPENS HERE
        "Permissions": [perm_map["APPROVE_DELEGATION"]] # Inherits EDIT and READ from Doctor
    }
    lead_doctor_id = db.roles.insert_one(lead_doctor_role).inserted_id

    # Admin Role
    admin_role = {
        "Role_name": "Admin",
        "Description": "Superuser Access",
        "Level": 1,
        "Parent_Role_id": lead_doctor_id, # Top level inherits EVERYTHING
        "Permissions": [perm_map["CREATE_USER"], perm_map["VIEW_AUDIT_LOGS"], perm_map["DELETE_PATIENT_DATA"]]
    }
    admin_id = db.roles.insert_one(admin_role).inserted_id
    print("Instantiated 4 Roles with Hierarchy.")

    # 3. Test Users
    # Note: Hashed passwords should use a library like bcrypt or passlib in production
    users = [
        {
            "Username": "admin_alice",
            "Email": "alice@hospital.com",
            # sha256 for "password123"
            "Hashed_password": "ef92b778bafe771e89245b89ecbc08a44a4e166c06659911881f383d4473e94f",
            "Status": "Active",
            "Assigned_Roles": [admin_id]
        },
        {
            "Username": "dr_bob",
            "Email": "bob@hospital.com",
            "Hashed_password": "ef92b778bafe771e89245b89ecbc08a44a4e166c06659911881f383d4473e94f",
            "Status": "Active",
            "Assigned_Roles": [doctor_id]
        },
        {
            "Username": "lead_dr_charlie",
            "Email": "charlie@hospital.com",
            "Hashed_password": "ef92b778bafe771e89245b89ecbc08a44a4e166c06659911881f383d4473e94f",
            "Status": "Active",
            "Assigned_Roles": [lead_doctor_id]
        }
    ]
    
    db.users.insert_many(users)
    print("Instantiated 3 Test Users.")
    print("Database seeding complete!")

if __name__ == "__main__":
    seed_db()
