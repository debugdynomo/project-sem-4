from datetime import datetime, timedelta

# ---------------- MOCK DATA ---------------- #

_users = [
    {"username": "admin", "email": "admin@test.com"},
    {"username": "doctor", "email": "doctor@test.com"},
    {"username": "intern", "email": "intern@test.com"},
]

_roles = [
    {"role_name": "Admin"},
    {"role_name": "Doctor"},
    {"role_name": "Intern"},
]

_permissions = [
    {"permission_name": "View Patients"},
    {"permission_name": "Edit Prescription"},
    {"permission_name": "Delete Records"},
]

_delegations = [
    {
        "delegator": "doctor",
        "delegatee": "intern",
        "role": "Doctor",
        "start_time": datetime.now(),
        "end_time": datetime.now() + timedelta(days=3),
        "reason": "Doctor on leave"
    }
]



def get_all_users():
    return _users


def create_user(username, email, password):
    _users.append({
        "username": username,
        "email": email
    })


def assign_role_to_user(username, role):
    print(f"[MOCK] Assigned role {role} to {username}")



def get_all_roles():
    return _roles


def create_role(role_name, description=None):
    _roles.append({
        "role_name": role_name
    })


def assign_permission_to_role(role, permission):
    print(f"[MOCK] Assigned permission {permission} to {role}")



def get_all_permissions():
    return _permissions



def get_active_delegations():
    return _delegations


def create_delegation(delegator, delegatee, role, start, end, reason):
    _delegations.append({
        "delegator": delegator,
        "delegatee": delegatee,
        "role": role,
        "start_time": start,
        "end_time": end,
        "reason": reason
    })