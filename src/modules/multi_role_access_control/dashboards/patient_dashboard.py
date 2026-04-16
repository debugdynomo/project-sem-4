# dashboards/patient_dashboard.py
import streamlit as st
import pymongo
from components.sidebar import sidebar
from backend.database import get_db_connection
from backend.audit import log_audit_event
import datetime
from datetime import time, timezone
from bson.objectid import ObjectId

def patient_dashboard():
    st.session_state.setdefault("view", "main")

    # Sidebar ignores explicit list, depends on st.session_state.role internally
    selected = sidebar()

    st.session_state.setdefault("last_sidebar", "Dashboard")
    
    if selected != st.session_state.last_sidebar:
        st.session_state.last_sidebar = selected

    # ROUTER
    if selected == "Dashboard":
        show_main_dashboard()
    elif selected == "Privacy & Consent (G5)":
        render_privacy_and_consent()
    elif selected == "My Access Logs":
        render_access_logs()
    else:
        show_main_dashboard()

def show_main_dashboard():
    st.markdown("## Welcome to the Patient Portal")
    st.markdown("*Your secure gateway to health records and privacy management.*")
    st.divider()
    st.info("Navigate to **Privacy & Consent (G5)** or **My Access Logs** to manage your data security.")

def render_access_logs():
    st.markdown("## 🛡️ My Access Logs")
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
            week_ago = datetime.datetime.now(timezone.utc) - datetime.timedelta(days=7)
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
                    "Date & Time": log.get("Timestamp", "N/A"),
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
    st.markdown("## 🤝 Privacy & Consent (G5)")
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
                    st.subheader("⏳ Pending Requests")
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
                                start_dt = datetime.datetime.combine(valid_from, time.min, tzinfo=timezone.utc)
                                end_dt = datetime.datetime.combine(valid_until, time.max, tzinfo=timezone.utc)

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