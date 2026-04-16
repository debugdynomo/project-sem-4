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
from backend.rbac import get_effective_permissions, get_active_roles, get_user_contexts
import admin_service
from backend.override_tracker import log_emergency_override
from backend.audit import log_audit_event
from bson import ObjectId
from bson.errors import InvalidId

# Roles that grant Lead Doctor / approval capabilities
_LEAD_ROLE_NAMES = {"Lead Doctor", "Lead_Doctor", "Admin", "System_Admin"}

def _check_is_lead_doctor(db, user_id, active_roles_from_aggregation=None):
    """
    Triple-redundant check for Lead Doctor / Admin status:
    1. Direct DB query on user's Assigned_Roles (most reliable — always current)
    2. Fallback: active_roles list from get_active_roles() aggregation
    3. Fallback: st.session_state.role

    This is needed because the session role string may be stale after an admin
    assigns a new role to a currently-logged-in user.
    """
    # --- Method 1: Direct DB check (bypasses aggregation) ---
    try:
        uid = ObjectId(user_id) if isinstance(user_id, str) else user_id
        user_doc = db["users"].find_one({"_id": uid}, {"Assigned_Roles": 1})
        if user_doc:
            for role_item in user_doc.get("Assigned_Roles", []):
                r_id = role_item.get("role_id") if isinstance(role_item, dict) else role_item
                role_doc = db["roles"].find_one({"_id": r_id}, {"Role_name": 1})
                if role_doc and role_doc.get("Role_name") in _LEAD_ROLE_NAMES:
                    return True
    except Exception:
        pass

    # --- Method 2: Aggregation result ---
    if active_roles_from_aggregation:
        if any(r in _LEAD_ROLE_NAMES for r in active_roles_from_aggregation):
            return True

    # --- Method 3: Session state role ---
    session_role = st.session_state.get("role", "")
    return session_role in _LEAD_ROLE_NAMES


def doctor_dashboard():
    # 1. Setup & Auth
    if "user_id" not in st.session_state:
        st.error("Please login first.")
        return

    db = get_db_connection()
    user_id = st.session_state.user_id
    
    # Check Hierarchy for "Lead Doctor" status
    # Use the aggregation for permissions, but use a direct DB check for
    # is_lead_doctor so it always reflects the current DB state regardless
    # of what role was set in session at login time.
    active_roles = get_active_roles(user_id, db)
    perms = get_effective_permissions(user_id, db)

    # Direct DB check — does not rely on aggregation or session role string
    is_lead_doctor = _check_is_lead_doctor(db, user_id, active_roles)
    
    # 2. Sidebar Configuration
    menu_items = ["Clinical Overview", "My Permissions", "Delegation Center (G5)", "Emergency Break-Glass", "Patient Access Logs"]
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
        
        contexts = get_user_contexts(user_id, db)
        if contexts:
            st.info(f"📍 **Active Context Restrictions:** {', '.join(contexts)}")
            
        if perms:
            df_perms = pd.DataFrame(perms, columns=["Permission Code"])
            st.dataframe(df_perms, width="stretch")
        else:
            st.warning("No active permissions found.")

        with st.expander("Debugging: Hierarchy & Roles"):
            st.write("Active Roles (Direct + Inherited):", active_roles)

    elif selected_page == "Delegation Center (G5)":
        _render_delegation_center(db, user_id)

    elif selected_page == "Emergency Break-Glass":
        _render_emergency_override(db, user_id)

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
            st.dataframe(df[["Delegation_type", "Status", "Start_time", "End_time", "Reason"]], width="stretch")
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
    st.markdown("Monitor access to patient health records, as well as your own account activity.")

    tab1, tab2 = st.tabs(["Patient Access Report", "My Activity Logs"])

    # ── Tab 1: Select a patient and view ALL access to their records ──
    with tab1:
        st.markdown("Select a patient to view who has accessed their health records.")

        # Fetch all users with the Patient role (global access – no restrictions)
        patient_role = db["roles"].find_one({"Role_name": "Patient"})

        patient_users = []
        if patient_role:
            # Support both dict-style and raw ObjectId role entries
            patient_users = list(db["users"].find({
                "$or": [
                    {"Assigned_Roles.role_id": patient_role["_id"]},
                    {"Assigned_Roles": patient_role["_id"]}
                ],
                "Status": "Active"
            }))

        if not patient_users:
            st.info("No patients found in the system.")
        else:
            patient_map = {
                f"{u.get('Username')} ({u.get('Email', 'N/A')})": str(u["_id"])
                for u in patient_users
            }
            selected_label = st.selectbox(
                "Select Patient", options=list(patient_map.keys())
            )
            selected_patient_id = patient_map[selected_label]

            # Audit: log the doctor's act of viewing this patient's logs
            # Use session state to avoid duplicate audit entries on Streamlit reruns
            last_viewed = st.session_state.get("_last_viewed_patient_logs")
            if last_viewed != selected_patient_id:
                log_audit_event(
                    db,
                    action="VIEW_PATIENT_AUDIT_LOGS",
                    user_id=user_id,
                    target_entity=selected_patient_id,
                    status="SUCCESS",
                )
                st.session_state._last_viewed_patient_logs = selected_patient_id

            st.markdown(f"**Access logs for:** {selected_label}")

            # Query audit_logs where Target_Entity matches the patient
            # (includes ALL access – third-party and the patient's own)
            patient_logs = list(db["audit_logs"].find(
                {"Target_Entity": selected_patient_id}
            ).sort("Timestamp", -1).limit(50))

            if patient_logs:
                display_data = []
                for log in patient_logs:
                    accessed_by = "Unknown/System"
                    if log.get("User_id"):
                        try:
                            u_doc = db["users"].find_one({"_id": log["User_id"]})
                            if u_doc:
                                accessed_by = u_doc.get("Username", "Unknown")
                        except Exception:
                            pass

                    display_data.append({
                        "Date & Time": log.get("Timestamp", "N/A"),
                        "Accessed By": accessed_by,
                        "Action": log.get("Action", ""),
                        "Status": log.get("Status", ""),
                        "Details": str(log.get("Details", "")) if log.get("Details") else ""
                    })

                st.dataframe(pd.DataFrame(display_data), width="stretch")
            else:
                st.info("No access logs found for this patient.")

    # ── Tab 2: Doctor's own activity ──
    with tab2:
        st.markdown("History of actions performed by your account.")

        my_logs = list(db["audit_logs"].find(
            {"User_id": admin_service.safe_objectid(user_id)}
        ).sort("Timestamp", -1).limit(50))

        if my_logs:
            df = pd.DataFrame(my_logs)
            st.dataframe(
                df[["Action", "Target_Entity", "Timestamp", "Status", "Details"]],
                width="stretch",
            )
        else:
            st.info("No audit logs found for your account.")

def _render_emergency_override(db, user_id):
    st.markdown("### 🚨 Emergency Break-Glass Override")
    st.error("WARNING: Use of this tool grants temporary uninhibited access to a target system or patient file. All actions are heavily audited and trigger immediate administrative alerts.")
    
    with st.form("break_glass_form"):
        target_system = st.text_input("Target System / Patient ID to Override", placeholder="e.g. PATIENT-99214")
        reason = st.text_area("Justification (Required)", placeholder="Describe the life-safety or clinical emergency...")
        duration = st.number_input("Duration (Hours)", min_value=1, max_value=24, value=2)
        
        submitted = st.form_submit_button("🚨 ACTIVATE EMERGENCY ACCESS 🚨", type="primary")
        
        if submitted:
            if not target_system or not reason:
                st.warning("Please provide both the Target System and a valid Justification.")
            else:
                try:
                    log_id = log_emergency_override(db, user_id, target_system, reason, int(duration))
                    st.success(f"Emergency Override Activated. ID: {log_id}. Administrators have been notified.")
                except Exception as e:
                    st.error(f"Error activating override: {e}")

