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
    delete_role,
    detect_all_conflicts,
    resolve_conflict,
    evaluate_access
)
from backend.permission_matrix import build_permission_matrix, get_latest_matrix
from backend.rbac import get_effective_permissions

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
            role_level = st.number_input("Hierarchy Level (1=Admin, 5=Patient)", min_value=1, max_value=10, value=4)

        submitted = st.form_submit_button("Create Role")
        if submitted:
            if role_name:
                try:
                    parent_id = None
                    if parent_role_name != "None":
                        parent_doc = next((r for r in roles if r.get("Role_name") == parent_role_name), None)
                        if parent_doc:
                            parent_id = str(parent_doc["_id"])
                            
                    create_role(db, admin_id, role_name, description, level=role_level, parent_role_id=parent_id)
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
                    # Self-protection for Admin role
                    if str(target_user["_id"]) == admin_id and revoke_role in ["Admin", "System_Admin"]:
                        st.error("Action denied: Cannot revoke your own Admin privileges.")
                    else:
                        revoke_role_from_user(db, admin_id, str(target_user["_id"]), revoke_role)
                        st.success(f"Role '{revoke_role}' revoked from '{revoke_user}'")
                        time.sleep(1.5)
                        st.rerun()
            except Exception as e:
                st.error(f"Error: {str(e)}")

    st.divider()

    st.subheader("Permission Matrix")
    st.write("Overview of all roles and their effective (inherited) permissions.")
    
    # Button to force matrix rebuild
    if st.button("Snapshot Latest Matrix"):
        build_permission_matrix(db, admin_id)
        st.success("Matrix snapshot created.")
        time.sleep(1)
        st.rerun()

    # Load matrix from DB
    latest_matrix_doc = get_latest_matrix(db)
    if not latest_matrix_doc:
        build_permission_matrix(db, admin_id)
        latest_matrix_doc = get_latest_matrix(db)

    if latest_matrix_doc and "matrix" in latest_matrix_doc:
        import pandas as pd
        matrix_rows = latest_matrix_doc["matrix"]
        
        # Build pandas dataframe with styled markers
        df_data = []
        for row in matrix_rows:
            flat_row = {"Role Name": row.get("role_name")}
            for perm_name, info in row.get("permissions", {}).items():
                if not info.get("granted"):
                    marker = "❌"
                elif info.get("direct"):
                    marker = "🟩 Direct"
                elif info.get("inherited"):
                    src = info.get("source", "Parent")
                    marker = f"🟦 Inherited ({src})"
                else:
                    marker = "✅"
                flat_row[perm_name] = marker
            df_data.append(flat_row)
            
        df = pd.DataFrame(df_data)
        st.dataframe(df, width="stretch")

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
            
        st.dataframe(table_data, width="stretch")
        
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

    st.divider()

    # ── Conflict Resolution ──
    st.subheader("Role Conflict Resolution")
    st.write("Detect and resolve incompatible role assignments across all users.")

    # Show current conflict matrix
    with st.expander("Conflict Matrix Definition"):
        st.markdown("""
        | Role | Incompatible With |
        |------|------------------|
        | Doctor | Patient |
        | Patient | Doctor, Admin, Lead_Doctor, Nurse |
        | Admin | Patient |
        """)

    if st.button("Scan for Conflicts", key="scan_conflicts"):
        conflicts = detect_all_conflicts(db)
        if not conflicts:
            st.success("No role conflicts detected across all users.")
        else:
            st.warning(f"Found **{len(conflicts)}** user(s) with conflicting role assignments.")
            for c in conflicts:
                with st.container():
                    st.markdown(f"**User:** {c['username']}")
                    for pair in c["conflicting_roles"]:
                        st.error(f"Conflict: `{pair[0]}` ↔ `{pair[1]}`")

                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button(f"Keep {pair[0]}, Remove {pair[1]}",
                                        key=f"keep_{c['user_id']}_{pair[0]}_{pair[1]}"):
                                try:
                                    resolve_conflict(db, admin_id, c["user_id"], pair[0], pair[1])
                                    st.success(f"Resolved: removed '{pair[1]}' from {c['username']}")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error: {e}")
                        with col2:
                            if st.button(f"Keep {pair[1]}, Remove {pair[0]}",
                                        key=f"keep_{c['user_id']}_{pair[1]}_{pair[0]}"):
                                try:
                                    resolve_conflict(db, admin_id, c["user_id"], pair[1], pair[0])
                                    st.success(f"Resolved: removed '{pair[0]}' from {c['username']}")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error: {e}")
                    st.divider()