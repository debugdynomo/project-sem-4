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
            
            # Find logs where Target_Entity is this patient's user_id, 
            # and the user who performed the action is NOT this patient.
            logs_cursor = db["audit_logs"].find(
                {
                    "Target_Entity": str(current_user_id), 
                    "User_id": {"$ne": ObjectId(current_user_id) if isinstance(current_user_id, str) and len(current_user_id)==24 else current_user_id}
                }
            ).sort("Timestamp", pymongo.DESCENDING).limit(50)
            
            audit_data = []
            for log in logs_cursor:
                action = log.get("Action", "")
                
                username = "Unknown/System"
                if log.get("User_id"):
                    try:
                        u = db["users"].find_one({"_id": log["User_id"]})
                        if u: username = u.get("Username", "Unknown")
                    except: pass
                    
                audit_data.append({
                    "Date & Time": log.get("Timestamp", "N/A"),
                    "Accessed By": username,
                    "Action": action,
                    "Status": log.get("Status", "")
                })
                
            if audit_data:
                st.dataframe(audit_data, use_container_width=True)
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
                active = list(db["delegations"].find({"Delegator_id": user_id, "Status": "Active"}))
                
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

    # TAB 2: Health Proxy
    with tab2:
        st.subheader("Assign Health Proxy")
        st.markdown("Temporarily delegate your Patient access to another user (e.g., a family member).")
        
        with st.form("new_proxy_form"):
            col1, col2 = st.columns(2)
            with col1:
                delegate_email = st.text_input("Caregiver/Family Member Username")
                reason = st.text_input("Reason")
            with col2:
                valid_from = st.date_input("Valid From", value=datetime.date.today())
                valid_until = st.date_input("Valid Until", value=datetime.date.today() + datetime.timedelta(days=7))
            
            submit = st.form_submit_button("Grant Access", type="primary")
            if submit:
                if not delegate_email:
                    st.error("Please provide the username.")
                elif valid_until < valid_from:
                    st.error("Expiry date cannot be before start date.")
                else:
                    if db is not None:
                        try:
                            del_user = db["users"].find_one({"Username": delegate_email})
                            p_role = db["roles"].find_one({"Role_name": "Patient"})
                            
                            if del_user and p_role:
                                start_dt = datetime.datetime.combine(valid_from, time.min, tzinfo=timezone.utc)
                                end_dt = datetime.datetime.combine(valid_until, time.max, tzinfo=timezone.utc)
                                
                                doc = {
                                    "Delegator_id": st.session_state.get("user_id"),
                                    "Delegatee_id": del_user["_id"],
                                    "Target_Role_id": p_role["_id"],
                                    "Delegation_type": "Health-Proxy", 
                                    "Reason": reason,
                                    "Status": "Active",
                                    "Start_time": start_dt,
                                    "End_time": end_dt,
                                    "Delegatee_Username": delegate_email,
                                    "Target_Role_Name": "Patient"
                                }
                                db["delegations"].insert_one(doc)
                                log_audit_event(db, action="HEALTH_PROXY_GRANTED", 
                                               user_id=st.session_state.get("user_id"),
                                               target_entity=str(del_user["_id"]), status="SUCCESS", 
                                               details={"delegatee": delegate_email})
                                               
                                st.success(f"Successfully granted temporary access to {delegate_email}.")
                                st.rerun()
                            else:
                                st.error("Target username not found or Patient role missing in DB.")
                        except Exception as e:
                            st.error(f"Error connecting to database: {e}")