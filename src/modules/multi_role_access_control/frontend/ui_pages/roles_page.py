import streamlit as st
import time

from backend.database import get_db_connection
from admin_service import (
    create_role,
    get_all_roles,
    assign_permission_to_role,
    get_all_permissions,
    revoke_role_from_user,
    get_all_users,
    delete_role
)

def show_roles_page():
    db = get_db_connection()
    admin_id = st.session_state.get("user_id")

    st.title("Role Management")

    st.subheader("Create New Role")

    roles = get_all_roles(db)
    parent_role_names = ["None"] + [r.get("Role_name", "Unknown") for r in roles]
    
    with st.form("create_role_form"):
        col1, col2 = st.columns(2)
        with col1:
            role_name = st.text_input("Role Name")
            parent_role_name = st.selectbox("Parent Role (Inheritance)", parent_role_names)
        with col2:
            description = st.text_input("Description")

        submitted = st.form_submit_button("Create Role")
        if submitted:
            if role_name:
                try:
                    parent_id = None
                    if parent_role_name != "None":
                        parent_doc = next((r for r in roles if r.get("Role_name") == parent_role_name), None)
                        if parent_doc:
                            parent_id = str(parent_doc["_id"])
                            
                    create_role(db, admin_id, role_name, description, parent_role_id=parent_id)
                    st.success(f"Role '{role_name}' created successfully")
                    time.sleep(1.5)
                    st.rerun()
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

    if role_names and permission_names:
        col1, col2 = st.columns(2)
        with col1:
            selected_role = st.selectbox("Select Role to Assign To", role_names)
        with col2:
            selected_permission = st.selectbox("Select Permission", permission_names)

        if st.button("Assign Permission"):
            try:
                assign_permission_to_role(db, admin_id, selected_role, selected_permission)
                st.success("Permission assigned successfully")
                time.sleep(1.5)
                st.rerun()
            except Exception as e:
                st.error(f"Error: {str(e)}")

    st.divider()

    st.subheader("Revoke Role from User")
    users = get_all_users(db)
    user_names = [u.get("Username", "Unknown") for u in users]
    
    if user_names and role_names:
        col3, col4 = st.columns(2)
        with col3:
            revoke_user = st.selectbox("Select User to Revoke From", user_names)
        with col4:
            revoke_role = st.selectbox("Select Role to Revoke", role_names)
            
        if st.button("Revoke Role from User"):
            try:
                target_user = next((u for u in users if u.get("Username") == revoke_user), None)
                if target_user:
                    revoke_role_from_user(db, admin_id, str(target_user["_id"]), revoke_role)
                    st.success(f"Role '{revoke_role}' revoked from '{revoke_user}'")
                    time.sleep(1.5)
                    st.rerun()
            except Exception as e:
                st.error(f"Error: {str(e)}")

    st.divider()

    st.subheader("All Roles")

    if roles:
        # Build table data safely
        table_data = []
        for r in roles:
            parent_name = "None"
            if r.get("Parent_Role_id"):
                parent_doc = next((pr for pr in roles if str(pr["_id"]) == str(r["_id"]) is False and str(pr["_id"]) == str(r["Parent_Role_id"])), None)
                if parent_doc: parent_name = parent_doc.get("Role_name", str(r["Parent_Role_id"]))
                
            perms_list = []
            for pid in r.get("Permissions", []):
                perm_doc = next((p for p in permissions if str(p["_id"]) == str(pid)), None)
                if perm_doc: perms_list.append(perm_doc.get("Permission_name", str(pid)))
                else: perms_list.append(str(pid))
                
            table_data.append({
                "Role Name": r.get("Role_name", ""),
                "Description": r.get("Description", ""),
                "Parent Role": parent_name,
                "Direct Permissions": ", ".join(perms_list) if perms_list else "None"
            })
            
        st.dataframe(table_data, use_container_width=True)
        
        st.subheader("Delete Role")
        del_role_name = st.selectbox("Select Role to Delete", role_names)
        if st.button("Delete Role", type="primary"):
            try:
                delete_role(db, admin_id, del_role_name)
                st.success(f"Role '{del_role_name}' deleted successfully.")
                time.sleep(1.5)
                st.rerun()
            except Exception as e:
                st.error(f"Error: {str(e)}")
    else:
        st.write("No roles found")