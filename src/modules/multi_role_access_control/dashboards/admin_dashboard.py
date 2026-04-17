# dashboards/admin_dashboard.py
import streamlit as st
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

def to_ist(dt):
    """Format a naive IST datetime for display."""
    if dt is None:
        return "Unknown"
    try:
        return dt.strftime("%Y-%m-%d %I:%M:%S %p IST")
    except Exception:
        return str(dt)
import pymongo
from components.sidebar import sidebar
from backend.database import get_db_connection
from frontend.ui_pages.users_page import show_users_page
from frontend.ui_pages.roles_page import show_roles_page
from frontend.ui_pages.delegation_page import show_delegation_page
from frontend.ui_pages.reviews_page import show_reviews_page
from frontend.ui_pages.overrides_page import show_overrides_page
from backend.override_tracker import get_active_overrides, resolve_emergency_override
from admin_service import get_upcoming_expirations, cleanup_expired_roles
from backend.reviews_service import process_expired_campaigns

def admin_dashboard():
    db = get_db_connection()
    
    st.session_state.setdefault("view", "dashboard")

    # ── User Profile Banner ──
    user_name = st.session_state.get('username', 'Unknown User')
    user_role = st.session_state.get('role', 'Unknown Role')
    st.markdown(f"<div style='text-align: right; font-size: 0.9rem; color: var(--text-color); opacity: 0.7;'>👤 {user_name} &ensp; | &ensp; 🛡️ {user_role}</div>", unsafe_allow_html=True)

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
    elif selected == "Delegation Console":
        show_delegation_page()
    elif selected == "Access Recertification":
        show_reviews_page()
    elif selected == "Override Tracking":
        show_overrides_page()
    elif selected == "System Audit":
        show_system_audit(db)
    else:
        show_admin_home(db)

def show_admin_home(db):
    st.markdown("## Dashboard")
    st.divider()
    
    overrides = get_active_overrides(db)
    if overrides:
        st.error("**ACTIVE EMERGENCY OVERRIDES DETECTED**")
        for o in overrides:
            col, col2 = st.columns([4, 1])
            user_doc = db["users"].find_one({"_id": o["user_id"]})
            username = user_doc.get("Username") if user_doc else str(o["user_id"])
            col.write(f"**{username}** initiated break-glass access to **{o['overridden_system']}** at {to_ist(o.get('timestamp'))}")
            col.write(f"*Reason:* {o['reason']}")
            if col2.button("Resolve", key=f"res_{o['_id']}"):
                resolve_emergency_override(db, st.session_state.get("user_id"), str(o["_id"]))
                st.rerun()
        st.divider()
    
    col = st.columns(1)[0]
    with col:
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
            st.metric("Pending Approvals", pending_count)
        with metric_cols[1]:
            st.metric("Configured Roles", roles_count)
            st.metric("Security Events", audit_events)

    # ── Upcoming Expirations Panel ──
    st.divider()
    st.markdown("### Upcoming Expirations (Next 7 Days)")
    expirations = get_upcoming_expirations(db)

    if not expirations:
        st.success("No delegations or roles expiring in the next 7 days.")
    else:
        st.warning(f"**{len(expirations)}** item(s) expiring soon.")
        exp_data = []
        for e in expirations:
            urgency = "High" if e["hours_left"] < 24 else "Medium" if e["hours_left"] < 72 else "Low"
            exp_data.append({
                "Urgency": urgency,
                "Type": e["type"],
                "User": e["delegatee"],
                "Role": e["role"],
                "Expires": str(e["expires"]),
                "Hours Left": e["hours_left"]
            })
        st.dataframe(exp_data, width="stretch")

    # ── System Maintenance ──
    st.divider()
    st.markdown("### System Maintenance")
    maint_col1, maint_col2 = st.columns(2)

    with maint_col1:
        if st.button("Cleanup Expired Roles", key="cleanup_roles"):
            admin_id = st.session_state.get("user_id")
            try:
                count = cleanup_expired_roles(db, admin_id)
                if count > 0:
                    st.success(f"Cleaned up expired roles for {count} user(s).")
                else:
                    st.info("No expired roles found.")
            except Exception as e:
                st.error(f"Error: {e}")

    with maint_col2:
        if st.button("Process Expired Campaigns", key="process_campaigns"):
            admin_id = st.session_state.get("user_id")
            try:
                count = process_expired_campaigns(db, admin_id)
                if count > 0:
                    st.success(f"Processed {count} expired campaign(s).")
                else:
                    st.info("No expired campaigns to process.")
            except Exception as e:
                st.error(f"Error: {e}")

def show_system_audit(db):
    st.markdown("## System Audit Logs")
    st.divider()
    
    if db is not None:
        recent_logs = list(db.audit_logs.find().sort("Timestamp", pymongo.DESCENDING).limit(100))
        if not recent_logs:
            st.write("No security events found.")
        else:
            audit_data = []
            for log in recent_logs:
                ts = log.get("Timestamp")
                ts_str = to_ist(ts)
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
            st.dataframe(audit_data, width="stretch")
    else:
        st.error("Database connection failed.")