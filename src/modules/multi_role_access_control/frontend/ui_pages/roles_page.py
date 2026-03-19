import streamlit as st

from backend.database import get_db_connection
from admin_service import (
    create_role,
    get_all_roles,
    assign_permission_to_role,
    get_all_permissions,
    revoke_role_from_user,
    get_all_users
)

def show_roles_page():
    db = get_db_connection()
    admin_id = st.session_state.get("user_id")

    st.title("Role Management")

    st.subheader("Create New Role")

    roles_for_parent = get_all_roles(db)
    parent_role_names = ["None"] + [r.get("Role_name", "Unknown") for r in roles_for_parent]
    
    col1, col2 = st.columns(2)
    with col1:
        role_name = st.text_input("Role Name")
        parent_role_name = st.selectbox("Parent Role (Inheritance)", parent_role_names)
    with col2:
        description = st.text_input("Description")

    if st.button("Create Role"):
        if role_name:
            try:
                parent_id = None
                if parent_role_name != "None":
                    parent_doc = next((r for r in roles_for_parent if r.get("Role_name") == parent_role_name), None)
                    if parent_doc:
                        parent_id = str(parent_doc["_id"])
                        
                create_role(db, admin_id, role_name, description, parent_role_id=parent_id)
                st.success("Role created successfully")
            except Exception as e:
                st.error(f"Error: {str(e)}")

        else:
            st.error("Role name is required")

    st.divider()

    st.subheader("Assign Permission to Role")

    roles = get_all_roles(db)
    permissions = get_all_permissions(db)

    role_names = [r.get("Role_name", "Unknown") for r in roles]
    permission_names = [p.get("Permission_name", "Unknown") for p in permissions]

    selected_role = st.selectbox("Select Role", role_names)
    selected_permission = st.selectbox("Select Permission", permission_names)

    if st.button("Assign Permission"):
        try:
            assign_permission_to_role(db, admin_id, selected_role, selected_permission)
            st.success("Permission assigned successfully")
        except Exception as e:
            st.error(f"Error: {str(e)}")

    st.divider()

    st.subheader("Revoke Role from User")
    users = get_all_users(db)
    user_names = [u.get("Username", "Unknown") for u in users]
    
    col3, col4 = st.columns(2)
    with col3:
        revoke_user = st.selectbox("Select User to Revoke From", user_names)
    with col4:
        revoke_role = st.selectbox("Select Role to Revoke", role_names)
        
    if st.button("Revoke Role"):
        try:
            target_user = next((u for u in users if u.get("Username") == revoke_user), None)
            if target_user:
                revoke_role_from_user(db, admin_id, str(target_user["_id"]), revoke_role)
                st.success("Role revoked successfully")
        except Exception as e:
            st.error(f"Error: {str(e)}")

    st.divider()

    st.subheader("All Roles")

    if roles:

        st.dataframe(roles)

    else:

        st.write("No roles found")