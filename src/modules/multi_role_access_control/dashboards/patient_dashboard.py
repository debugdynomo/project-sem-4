# dashboards/patient_dashboard.py
import streamlit as st
import pymongo
from components.sidebar import sidebar
from backend.database import get_db_connection
from backend.audit import log_audit_event
from components.permission_guard import require_permission
import datetime
from datetime import time
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

def now_ist():
    """Return current time in IST as a naive datetime (matches MongoDB storage)."""
    return datetime.datetime.now(tz=IST).replace(tzinfo=None)

def to_ist(dt):
    """Format a naive IST datetime for display."""
    if dt is None:
        return "N/A"
    try:
        return dt.strftime("%Y-%m-%d %I:%M:%S %p IST")
    except Exception:
        return str(dt)
from bson.objectid import ObjectId

def patient_dashboard():
    st.session_state.setdefault("view", "main")

    # ── User Profile Banner ──
    user_name = st.session_state.get('username', 'Unknown User')
    user_role = st.session_state.get('role', 'Unknown Role')
    st.markdown(f"<div style='text-align: right; font-size: 0.9rem; color: var(--text-color); opacity: 0.7;'>👤 {user_name} | 🛡️ {user_role}</div>", unsafe_allow_html=True)

    # Sidebar ignores explicit list, depends on st.session_state.role internally
    selected = sidebar()

    st.session_state.setdefault("last_sidebar", "Dashboard")
    
    if selected != st.session_state.last_sidebar:
        st.session_state.last_sidebar = selected

    # ROUTER
    if selected == "Dashboard":
        show_main_dashboard()
    elif selected == "Privacy & Consent":
        render_privacy_and_consent()
    elif selected == "My Access Logs":
        render_access_logs()
    else:
        show_main_dashboard()

def show_main_dashboard():
    st.markdown("##Patient Portal")
    st.markdown("*Your secure gateway to health records and privacy management.*")
    st.divider()
    st.info("Navigate to **Privacy & Consent** or **My Access Logs** to manage your data security.")

    # ── Who Can See My Data panel ──
    st.divider()
    st.markdown("### Who Can See My Data")
    st.caption("Users who currently have access to your health records.")

    try:
        db = get_db_connection()
        user_id = st.session_state.get("user_id")

        # Find the READ_PATIENT_DATA permission
        read_perm = db["permissions"].find_one({"Permission_name": "READ_PATIENT_DATA"})
        if not read_perm:
            st.info("Permission configuration not found.")
            return

        # Find all roles that have READ_PATIENT_DATA (direct or inherited)
        all_roles = list(db["roles"].find({}))
        roles_with_read = set()
        role_map = {str(r["_id"]): r for r in all_roles}

        for r in all_roles:
            # Walk inheritance chain
            visited = set()
            current = r
            while current and str(current["_id"]) not in visited:
                visited.add(str(current["_id"]))
                if read_perm["_id"] in current.get("Permissions", []):
                    roles_with_read.add(str(r["_id"]))
                    break
                parent_id = current.get("Parent_Role_id")
                current = role_map.get(str(parent_id)) if parent_id else None

        # Find users with those roles
        all_users = list(db["users"].find({"Status": "Active"}))
        accessor_list = []

        for u in all_users:
            if str(u["_id"]) == user_id:
                continue  # Skip self

            for role_item in u.get("Assigned_Roles", []):
                rid = role_item.get("role_id") if isinstance(role_item, dict) else role_item
                if str(rid) in roles_with_read:
                    role_name = role_map.get(str(rid), {}).get("Role_name", "Unknown")
                    accessor_list.append({
                        "User": u.get("Username", "Unknown"),
                        "Access Via": f"Role: {role_name}",
                        "Type": "Direct Role"
                    })
                    break

        # Also check active delegations for roles with READ_PATIENT_DATA
        now = now_ist()
        active_delegations = list(db["delegations"].find({
            "Status": "Active",
            "Start_time": {"$lte": now},
            "End_time": {"$gt": now}
        }))

        for d in active_delegations:
            if str(d["Target_Role_id"]) in roles_with_read:
                delegatee = db["users"].find_one({"_id": d["Delegatee_id"]})
                if delegatee and str(delegatee["_id"]) != user_id:
                    role_name = role_map.get(str(d["Target_Role_id"]), {}).get("Role_name", "Unknown")
                    # Don't add if already in list
                    existing_users = {a["User"] for a in accessor_list}
                    if delegatee.get("Username") not in existing_users:
                        accessor_list.append({
                            "User": delegatee.get("Username", "Unknown"),
                            "Access Via": f"Delegation: {role_name}",
                            "Type": "Delegated"
                        })

        if accessor_list:
            st.dataframe(accessor_list, width="stretch")
        else:
            st.success("No users currently have access to your health records.")
    except Exception as e:
        st.error(f"Unable to load access data: {e}")

def render_access_logs():
    st.markdown("## My Access Logs")
    st.markdown("A history of who accessed your medical records and when.")
    st.divider()

    try:
        db = get_db_connection()
    except Exception as e:
        st.error("Could not connect to database.")
        return

    if db is not None:
        try:
            current_user_id = st.session_state.get("user_id")

            # Safely convert to ObjectId for comparisons
            try:
                current_oid = ObjectId(current_user_id) if isinstance(current_user_id, str) and len(current_user_id) == 24 else current_user_id
            except Exception:
                current_oid = current_user_id

            # ── Weekly access metric ──
            week_ago = now_ist() - datetime.timedelta(days=7)
            weekly_count = db["audit_logs"].count_documents({
                "Target_Entity": str(current_user_id),
                "User_id": {"$ne": current_oid},
                "Timestamp": {"$gte": week_ago}
            })

            st.metric("External Accesses This Week", weekly_count)
            st.divider()

            # ── Full log listing (external accesses only) ──
            logs_cursor = db["audit_logs"].find(
                {
                    "Target_Entity": str(current_user_id),
                    "User_id": {"$ne": current_oid}
                }
            ).sort("Timestamp", pymongo.DESCENDING).limit(50)

            audit_data = []
            for log in logs_cursor:
                username = "Unknown/System"
                if log.get("User_id"):
                    try:
                        u = db["users"].find_one({"_id": log["User_id"]})
                        if u:
                            username = u.get("Username", "Unknown")
                    except Exception:
                        pass

                audit_data.append({
                    "Date & Time": to_ist(log.get("Timestamp")),
                    "Accessed By": username,
                    "Action": log.get("Action", ""),
                    "Status": log.get("Status", ""),
                    "Details": str(log.get("Details", "")) if log.get("Details") else ""
                })

            if audit_data:
                st.dataframe(audit_data, width="stretch")
            else:
                st.info("No recent external access to your medical records.")
        except Exception as e:
            st.error(f"Unable to load audit logs: {e}")

def render_privacy_and_consent():
    st.markdown("## Privacy & Consent")
    st.markdown("Manage who has delegated access to your health data.")
    st.divider()
    
    tab1, tab2 = st.tabs(["Consent Management", "Assign Health Proxy"])
    
    try:
        db = get_db_connection()
    except Exception as e:
        st.error("Could not connect to database.")
        return

    # TAB 1: Consent Management & Revocation
    with tab1:
        st.subheader("Consent Management")
        st.markdown("List of users who currently have delegated access to your data.")
        
        if db is not None:
            user_id = st.session_state.get("user_id")
            if user_id:
                # Convert to ObjectId for proper matching
                try:
                    uid_oid = ObjectId(user_id) if isinstance(user_id, str) and len(user_id) == 24 else user_id
                except Exception:
                    uid_oid = user_id

                # ── Active delegations (with Revoke button) ──
                active = list(db["delegations"].find({"Delegator_id": uid_oid, "Status": "Active"}))
                
                if not active:
                    st.info("You currently have no active proxies or delegated access.")
                else:
                    for doc in active:
                        del_name = doc.get("Delegatee_Username", "Unknown/System")
                        if not del_name or del_name == "Unknown/System":
                            try:
                                del_u = db["users"].find_one({"_id": doc.get("Delegatee_id")})
                                if del_u: del_name = del_u.get("Username")
                            except: pass

                        with st.container():
                            col1, col2 = st.columns([3, 1])
                            with col1:
                                st.markdown(f"**Delegatee**: {del_name}")
                                st.caption(f"Reason: {doc.get('Reason', 'N/A')} | Expires: {doc.get('End_time', 'N/A')}")
                            with col2:
                                if st.button("Revoke", key=f"revoke_{doc['_id']}"):
                                    db["delegations"].update_one(
                                        {"_id": doc["_id"]},
                                        {"$set": {"Status": "Revoked"}}
                                    )
                                    log_audit_event(db, action="DELEGATION_REVOKED", 
                                                    user_id=user_id,
                                                    target_entity="delegations", status="SUCCESS", 
                                                    details={"delegation_id": str(doc["_id"])})
                                    st.success(f"Revoked access for {del_name}.")
                                    st.rerun()
                            st.divider()

                # ── Pending requests (read-only) ──
                pending = list(db["delegations"].find({"Delegator_id": uid_oid, "Status": "Pending"}))

                if pending:
                    st.markdown("---")
                    st.subheader("Pending Requests")
                    st.caption("These proxy requests are awaiting admin/lead doctor approval.")

                    for doc in pending:
                        del_name = "Unknown/System"
                        try:
                            del_u = db["users"].find_one({"_id": doc.get("Delegatee_id")})
                            if del_u:
                                del_name = del_u.get("Username", "Unknown")
                        except Exception:
                            pass

                        with st.container():
                            st.markdown(
                                f"**Delegatee**: {del_name}  \n"
                                f"**Type**: {doc.get('Delegation_type', 'N/A')} | "
                                f"**Reason**: {doc.get('Reason', 'N/A')} | "
                                f"**Valid**: {doc.get('Start_time', 'N/A')} → {doc.get('End_time', 'N/A')}"
                            )
                            st.divider()

    # TAB 2: Health Proxy
    with tab2:
        st.subheader("Assign Health Proxy")
        st.markdown("Temporarily delegate your Patient access to another user (e.g., a family member).")

        with require_permission("REQUEST_DELEGATION", fallback_msg="🔒 You do not have permission to request a health proxy."):
            # Build a dropdown of active users (excluding the current patient)
            current_uid = st.session_state.get("user_id")
            all_users = list(db["users"].find({"Status": "Active"}))
            user_map = {
                u.get("Username", "unknown"): str(u["_id"])
                for u in all_users
                if str(u["_id"]) != current_uid
            }

            if not user_map:
                st.info("No other active users available to assign as proxy.")
            else:
                with st.form("new_proxy_form"):
                    col1, col2 = st.columns(2)
                    with col1:
                        selected_delegatee = st.selectbox(
                            "Caregiver/Family Member",
                            options=list(user_map.keys())
                        )
                        reason = st.text_input("Reason")
                    with col2:
                        valid_from = st.date_input("Valid From", value=datetime.date.today())
                        valid_until = st.date_input("Valid Until", value=datetime.date.today() + datetime.timedelta(days=7))

                    submit = st.form_submit_button("Grant Access", type="primary")
                    if submit:
                        if valid_until < valid_from:
                            st.error("Expiry date cannot be before start date.")
                        else:
                            try:
                                delegatee_id = user_map[selected_delegatee]
                                p_role = db["roles"].find_one({"Role_name": "Patient"})

                                if not p_role:
                                    st.error("Patient role not found in database.")
                                else:
                                    start_dt = datetime.datetime.combine(valid_from, time.min)
                                    end_dt = datetime.datetime.combine(valid_until, time.max)

                                    from admin_service import create_delegation
                                    req_id = create_delegation(
                                        db=db,
                                        delegator_id=current_uid,
                                        delegatee_id=delegatee_id,
                                        target_role_id=p_role["_id"],
                                        start_time=start_dt,
                                        end_time=end_dt,
                                        reason=reason,
                                        delegation_type="Health-Proxy"
                                    )
                                    log_audit_event(
                                        db,
                                        action="HEALTH_PROXY_GRANTED",
                                        user_id=current_uid,
                                        target_entity=delegatee_id,
                                        status="SUCCESS",
                                        details={"delegatee": selected_delegatee, "delegation_id": req_id}
                                    )
                                    st.success(f"✅ Health proxy submitted for admin approval. Proxy ID: {req_id}")
                                    st.rerun()
                            except Exception as e:
                                st.error(f"Validation or Database Error: {e}")