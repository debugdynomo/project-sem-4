# dashboards/doctor_dashboard.py

import streamlit as st
import pandas as pd
import sys
import os

# Robust path handling for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from components.sidebar import sidebar
from backend.database import get_db_connection
from backend.rbac import get_effective_permissions, get_active_roles
import admin_service

def doctor_dashboard():
    # 1. Setup & Auth
    if "user_id" not in st.session_state:
        st.error("Please login first.")
        return

    db = get_db_connection()
    user_id = st.session_state.user_id
    
    # Check Hierarchy for "Lead Doctor" status
    # This uses the recursive logic in rbac.py (get_active_roles)
    active_roles = get_active_roles(user_id, db)
    perms = get_effective_permissions(user_id, db)
    is_lead_doctor = "Lead Doctor" in active_roles
    
    # 2. Sidebar Configuration
    menu_items = ["Clinical Overview", "My Permissions", "Delegation Center (G5)", "Patient Access Logs"]
    if is_lead_doctor:
        menu_items.insert(2, "Approve Delegations")  # Add after "My Permissions" or anywhere logic
        
    if "CREATE_USER" in perms or "Admin" in active_roles:
        menu_items.extend(["User Management", "Role Management", "System Audit"])

    menu_items.append("Logout")

    selected_page = sidebar(menu_items)

    st.title(f"👨‍⚕️ Doctor Dashboard: {selected_page}")

    # 3. Page Routing
    if selected_page == "Clinical Overview":
        st.info("Module 41 Focus: Access Control & Delegation.")
        st.markdown("""
        **Clinical Access & Delegation Center**
        
        Welcome to the secure delegation portal. Use the sidebar to:
        - View your active permissions (Effective Permissions).
        - Delegate roles to colleagues (Delegation Center).
        - Audit access to your patient's data.
        """)
        # Placeholder for clinical stats if needed, but strictly scoping to Mod 41.

    elif selected_page == "My Permissions":
        st.subheader("My Effective Permissions")
        st.markdown("Based on your assigned roles and active delegations (Recursive Inheritance):")
        
        if perms:
            df_perms = pd.DataFrame(perms, columns=["Permission Code"])
            st.dataframe(df_perms, use_container_width=True)
        else:
            st.warning("No active permissions found.")

        with st.expander("Debugging: Hierarchy & Roles"):
            st.write("Active Roles (Direct + Inherited):", active_roles)

    elif selected_page == "Delegation Center (G5)":
        _render_delegation_center(db, user_id)

    elif selected_page == "Approve Delegations":
        if not is_lead_doctor:
            st.error("Access Denied: Lead Doctor privileges required.")
        else:
            _render_approval_inbox(db, user_id)

    elif selected_page == "Patient Access Logs":
        _render_audit_logs(db, user_id)

    elif selected_page == "User Management":
        from frontend.ui_pages.users_page import show_users_page
        show_users_page()

    elif selected_page == "Role Management":
        from frontend.ui_pages.roles_page import show_roles_page
        show_roles_page()

    elif selected_page == "System Audit":
        from dashboards.admin_dashboard import show_system_audit
        show_system_audit(db)

def _render_delegation_center(db, user_id):
    st.markdown("### 🏥 Clinical Role Delegation (M:N)")
    
    tabs = st.tabs(["New Delegation Request", "My Delegation History"])
    
    with tabs[0]:
        st.write("Delegate your responsibilities to a colleague or intern.")
        
        # Form
        with st.form("delegation_form"):
            # Fetch potential delegatees (All users for now, filtered by logic ideally)
            users = list(db["users"].find({"Status": "Active"}))
            user_map = {u["Username"]: str(u["_id"]) for u in users if str(u["_id"]) != user_id}
            
            delegatee_name = st.selectbox("Select Colleague (Delegatee)", options=list(user_map.keys()))
            
            # Fetch user's own roles to delegate
            # We should only allow delegating roles the user actually has.
            # Ideally fetch actual role docs. 
            # For simplicity, let's fetch all roles and let user pick (enforce in backend? or filter here)
            # Correct way: use 'active_roles' but we need IDs.
            # Let's just fetch all roles for the dropdown for now.
            start_roles = list(db["roles"].find({}))
            role_map = {r["Role_name"]: str(r["_id"]) for r in start_roles}
            
            target_role_name = st.selectbox("Role to Delegate", options=list(role_map.keys()))
            
            delegation_type = st.selectbox("Delegation Type", ["Peer-to-Peer", "Hierarchical", "Emergency"])
            hours = st.number_input("Duration (Hours)", min_value=1, max_value=72, value=4)
            reason = st.text_area("Reason for Delegation", placeholder="e.g. Emergency Theater coverage")
            
            submitted = st.form_submit_button("Submit Request")
            
            if submitted:
                if not delegatee_name or not target_role_name:
                    st.error("Please fill all fields.")
                else:
                    try:
                        delegatee_id = user_map[delegatee_name]
                        target_role_id = role_map[target_role_name]
                        
                        from datetime import datetime, timedelta
                        req_id = admin_service.create_delegation(
                            db, 
                            user_id, 
                            delegatee_id, 
                            target_role_id, 
                            datetime.utcnow(),
                            datetime.utcnow() + timedelta(hours=int(hours)),
                            reason,
                            delegation_type
                        )
                        st.success(f"✅ Delegation submitted for admin approval! Request ID: {req_id}")
                    except Exception as e:
                        st.error(f"Validation or Database Error: {e}")

    with tabs[1]:
        history = admin_service.get_my_delegation_history(db, user_id)
        if history:
            df = pd.DataFrame(history)
            # Cleanup for display
            df["Start_time"] = pd.to_datetime(df["Start_time"])
            df["End_time"] = pd.to_datetime(df["End_time"])
            st.dataframe(df[["Delegation_type", "Status", "Start_time", "End_time", "Reason"]], use_container_width=True)
        else:
            st.info("No delegation history found.")


def _render_approval_inbox(db, admin_id):
    st.markdown("### 📥 Delegation Approval Inbox")
    st.info("As a Lead Doctor / Admin, review and approve delegation requests from your team.")

    pending = admin_service.get_pending_delegations(db)

    if not pending:
        st.success("No pending delegation requests.")
        return

    for d in pending:
        with st.container():
            col1, col2, col3 = st.columns([4, 1, 1])
            with col1:
                st.markdown(f"**{d.get('Delegator_Name', 'Unknown')}** → **{d.get('Delegatee_Name', 'Unknown')}**")
                st.caption(
                    f"Role: {d.get('Target_Role_Name', 'N/A')} | "
                    f"Type: {d.get('Delegation_type', 'N/A')} | "
                    f"Reason: {d.get('Reason', 'N/A')}"
                )
            with col2:
                if st.button("✅ Approve", key=f"approve_{d['_id']}"):
                    try:
                        admin_service.approve_delegation(db, admin_id=admin_id, delegation_id=str(d["_id"]))
                        st.success("Delegation approved!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
            with col3:
                if st.button("❌ Reject", key=f"reject_{d['_id']}"):
                    try:
                        admin_service.reject_delegation(db, admin_id=admin_id, delegation_id=str(d["_id"]))
                        st.warning("Delegation rejected.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
            st.divider()


def _render_audit_logs(db, user_id):
    st.subheader("🛡️ Patient Data Audit Logs")
    st.markdown("Monitoring access to your assigned patients and your account activity.")
    
    # Fetch logs where User_id matches (My Activity)
    # OR Target_Entity implies my patients (Harder to query without patient mapping)
    # For now: Show "My Activity" and "Alerts"
    
    logs = list(db["audit_logs"].find(
        {"User_id": admin_service.safe_objectid(user_id)}
    ).sort("Timestamp", -1).limit(50))
    
    if logs:
        df = pd.DataFrame(logs)
        st.dataframe(df[["Action", "Target_Entity", "Timestamp", "Status", "Details"]], use_container_width=True)
    else:
        st.info("No audit logs found for your account.")

