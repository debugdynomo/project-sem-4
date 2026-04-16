import streamlit as st
import pandas as pd
import time

from backend.database import get_db_connection
from backend.rbac import get_effective_permissions
from admin_service import (
    create_user,
    get_all_users,
    assign_role_to_user,
    get_all_roles,
    delete_user,
    detect_all_conflicts
)
from components.permission_guard import user_status_badge
from datetime import datetime, timezone

def show_users_page():
    db = get_db_connection()
    admin_id = st.session_state.get("user_id")

    st.title("User Management")

    st.subheader("Create New User")

    with st.form("create_user_form"):

        username = st.text_input("Username")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")

        submitted = st.form_submit_button("Create User")

        if submitted:

            if username and email and password:
                try:
                    create_user(db, admin_id, username, email, password)
                    st.success("User created successfully")
                    time.sleep(1.5)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {str(e)}")

            else:
                st.error("Please fill all fields")

    st.divider()

    st.subheader("Assign Role to User")

    users = get_all_users(db)
    roles = get_all_roles(db)

    user_names = [u.get("Username", "Unknown") for u in users]
    role_names = [r.get("Role_name", "Unknown") for r in roles]

    if user_names and role_names:
        col1, col2 = st.columns(2)
        with col1:
            selected_user = st.selectbox("Select User", user_names)
            context_tags_str = st.text_input("Context Tags (Comma Separated)", placeholder="e.g. Cardiology, Wing-B")
        with col2:
            selected_role = st.selectbox("Select Role", role_names)
            valid_until = st.date_input("Valid Until (Optional, leave blank for permanent)", value=None)

        if st.button("Assign Role"):
            try:
                target_user = next((u for u in users if u.get("Username") == selected_user), None)
                if target_user:
                    context = None
                    if context_tags_str:
                        tags = [t.strip() for t in context_tags_str.split(",") if t.strip()]
                        if tags:
                            context = {"tags": tags}
                    
                    vu = None
                    if valid_until:
                        import datetime
                        vu = datetime.datetime.combine(valid_until, datetime.datetime.min.time())

                    assign_role_to_user(db, admin_id, str(target_user["_id"]), selected_role, context=context, valid_until=vu)
                    st.success("Role assigned successfully")
                    time.sleep(1.5)
                    st.rerun()
                else:
                    st.error("Selected user not found.")
            except Exception as e:
                st.error(f"Error: {str(e)}")

    st.divider()

    st.subheader("All Users & Effective Permissions")
    users = get_all_users(db)

    if users:
        conflicts = detect_all_conflicts(db)
        conflict_uids = {c["user_id"] for c in conflicts}
        now = datetime.now(timezone.utc)
        
        # Build dataframe data
        table_data = []
        for u in users:
            eff_perms = get_effective_permissions(u["_id"], db)
            eff_perms_str = ", ".join(eff_perms) if eff_perms else "None"
            
            # Map assigned roles from ObjectIds to Names
            assigned_roles_ids = u.get("Assigned_Roles", [])
            assigned_roles_names = []
            has_expiring = False
            
            for item in assigned_roles_ids:
                if isinstance(item, dict):
                    rid = item.get("role_id")
                    if item.get("valid_until"):
                        vu = item["valid_until"]
                        try:
                            # Handle timezone aware vs naive
                            if vu.tzinfo is None:
                                vu = vu.replace(tzinfo=timezone.utc)
                        except Exception:
                            pass
                        hours_left = (vu - now).total_seconds() / 3600
                        if 0 < hours_left < 48:
                            has_expiring = True
                else:
                    rid = item
                
                role_doc = next((r for r in roles if str(r["_id"]) == str(rid)), None)
                if role_doc:
                    assigned_roles_names.append(role_doc.get("Role_name", str(rid)))
                else:
                    assigned_roles_names.append(str(rid))
                    
            r_str = ", ".join(assigned_roles_names) if assigned_roles_names else "None"
            if has_expiring:
                r_str += " ⏰"
                
            # Delegation check
            active_delegations = list(db["delegations"].find({
                "Delegatee_id": u["_id"], "Status": "Active"
            }))
            if active_delegations:
                r_str += " ⚡"

            status = u.get("Status", "Unknown")
            status_display = f"{user_status_badge(status)} {status}"
            
            username_display = u.get("Username", "")
            if str(u["_id"]) in conflict_uids:
                username_display += " ⚠️"
                    
            table_data.append({
                "ID": str(u["_id"]),
                "Username": username_display,
                "Email": u.get("Email", ""),
                "Direct Roles": r_str,
                "Effective Permissions": eff_perms_str,
                "Status": status_display
            })
            
        st.dataframe(table_data, width="stretch")
        
        st.subheader("Delete User")
        del_user_name = st.selectbox("Select User to Delete", [u.get("Username", "Unknown") for u in users])
        if st.button("Delete User", type="primary"):
            try:
                target_user = next((u for u in users if u.get("Username") == del_user_name), None)
                if target_user:
                    if str(target_user["_id"]) == admin_id:
                        st.error("Action denied: Cannot delete your own account.")
                    else:
                        delete_user(db, admin_id, str(target_user["_id"]))
                        st.success(f"User {del_user_name} deleted successfully.")
                        st.rerun()
            except Exception as e:
                st.error(f"Error deleting user: {str(e)}")
    else:
        st.write("No users found")