# dashboards/admin_dashboard.py
import streamlit as st
import pymongo
from components.sidebar import sidebar
from backend.database import get_db_connection
from frontend.ui_pages.users_page import show_users_page
from frontend.ui_pages.roles_page import show_roles_page
from frontend.ui_pages.delegation_page import show_delegation_page
from frontend.ui_pages.reviews_page import show_reviews_page
from backend.override_tracker import get_active_overrides, resolve_emergency_override

def admin_dashboard():
    db = get_db_connection()
    
    st.session_state.setdefault("view", "dashboard")

    # The sidebar function uses role-based logic automatically
    selected = sidebar()

    st.session_state.setdefault("last_sidebar", "Dashboard")
    
    if selected != st.session_state.last_sidebar:
        st.session_state.last_sidebar = selected

    # ROUTER
    if selected == "Dashboard":
        show_admin_home(db)
    elif selected == "User Management":
        show_users_page()
    elif selected == "Role Management":
        show_roles_page()
    elif selected == "Delegation Console (G5)":
        show_delegation_page()
    elif selected == "Access Recertification":
        show_reviews_page()
    elif selected == "System Audit":
        show_system_audit(db)
    else:
        show_admin_home(db)

def show_admin_home(db):
    st.markdown("## 🏥 Admin Dashboard")
    st.markdown("Welcome to the Module 41 / G5 Access Control Center.")
    st.divider()
    
    overrides = get_active_overrides(db)
    if overrides:
        st.error("🚨 **ACTIVE EMERGENCY OVERRIDES DETECTED** 🚨")
        for o in overrides:
            col1, col2 = st.columns([4, 1])
            user_doc = db["users"].find_one({"_id": o["user_id"]})
            username = user_doc.get("Username") if user_doc else str(o["user_id"])
            col1.write(f"**{username}** initiated break-glass access to **{o['overridden_system']}** at {o['timestamp']}")
            col1.write(f"*Reason:* {o['reason']}")
            if col2.button("Resolve", key=f"res_{o['_id']}"):
                resolve_emergency_override(db, st.session_state.get("user_id"), str(o["_id"]))
                st.rerun()
        st.divider()
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### Access Statistics")
        metric_cols = st.columns(2)
        
        users_count = db.users.count_documents({}) if db is not None else 0
        roles_count = db.roles.count_documents({}) if db is not None else 0
        delegations_count = db.delegations.count_documents({"Status": "Active"}) if db is not None else 0
        pending_count = db.delegations.count_documents({"Status": "Pending"}) if db is not None else 0
        audit_events = db.audit_logs.count_documents({}) if db is not None else 0
        
        with metric_cols[0]:
            st.metric("Total Users", users_count)
            st.metric("Active Delegations", delegations_count)
            st.metric("⏳ Pending Approvals", pending_count)
        with metric_cols[1]:
            st.metric("Configured Roles", roles_count)
            st.metric("Security Events", audit_events)
            
    with col2:
         st.info("Use the sidebar to manage Users, Roles, Delegations, and view the System Audit.")

def show_system_audit(db):
    st.markdown("## 🛡️ System Audit Logs")
    st.caption("Comprehensive view of all Module 41 security events.")
    st.divider()
    
    if db is not None:
        recent_logs = list(db.audit_logs.find().sort("Timestamp", pymongo.DESCENDING).limit(100))
        if not recent_logs:
            st.write("No security events found.")
        else:
            audit_data = []
            for log in recent_logs:
                ts = log.get("Timestamp")
                ts_str = ts.strftime("%Y-%m-%d %H:%M:%S") if ts else "Unknown"
                action = log.get("Action", "UNKNOWN")
                status = log.get("Status", "UNKNOWN")
                
                # Try to resolve User
                username = str(log.get("User_id", "System"))
                if log.get("User_id"):
                    try:
                        u = db["users"].find_one({"_id": log["User_id"]})
                        if u: username = u.get("Username", str(log["User_id"]))
                    except: pass

                audit_data.append({
                    "Timestamp": ts_str,
                    "Action": action,
                    "Status": status,
                    "User": username,
                    "Target Entity": str(log.get("Target_Entity", "")),
                    "IP Address": log.get("IP_Address", "Unknown")
                })
            st.dataframe(audit_data, use_container_width=True)
    else:
        st.error("Database connection failed.")