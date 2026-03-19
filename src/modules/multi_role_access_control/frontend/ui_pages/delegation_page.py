import streamlit as st
from datetime import datetime

from backend.database import get_db_connection
from admin_service import (
    get_all_users,
    get_all_roles,
    get_active_delegations,
    create_delegation,
    revoke_delegation
)

def show_delegation_page():
    db = get_db_connection()
    admin_id = st.session_state.get("user_id")

    st.title("Role Delegation")

    st.subheader("Create Delegation")

    users = get_all_users(db)
    roles = get_all_roles(db)

    user_names = [u.get("Username", "Unknown") for u in users]
    role_names = [r.get("Role_name", "Unknown") for r in roles]

    delegator = st.selectbox("Delegator (From User)", user_names)
    delegatee = st.selectbox("Delegatee (To User)", user_names)
    role = st.selectbox("Role to Delegate", role_names)

    start_date = st.date_input("Start Date")
    end_date = st.date_input("End Date")

    reason = st.text_input("Reason")

    if st.button("Create Delegation"):
        if delegator != delegatee:
            try:
                delegator_id = next((u["_id"] for u in users if u.get("Username") == delegator), None)
                delegatee_id = next((u["_id"] for u in users if u.get("Username") == delegatee), None)
                role_id = next((r["_id"] for r in roles if r.get("Role_name") == role), None)

                if not delegator_id or not delegatee_id or not role_id:
                    st.error("Invalid selection for users or role.")
                else:
                    create_delegation(
                        db,
                        delegator_id,
                        delegatee_id,
                        role_id,
                        datetime.combine(start_date, datetime.min.time()),
                        datetime.combine(end_date, datetime.max.time()),
                        reason,
                        delegation_type="Hierarchical"
                    )
                    st.success("Delegation created successfully")
            except Exception as e:
                st.error(f"Validation or Database Error: {str(e)}")
        else:
            st.error("Delegator and Delegatee cannot be identical")

    st.divider()

    st.subheader("Active Delegations")

    delegations = get_active_delegations(db)
    
    del_formatted = []
    for d in delegations:
        record = d.copy()
        record["_id"] = str(d["_id"])
        record["Delegator_id"] = str(d.get("Delegator_id"))
        record["Delegatee_id"] = str(d.get("Delegatee_id"))
        record["Target_Role_id"] = str(d.get("Target_Role_id"))
        del_formatted.append(record)

    if del_formatted:
        st.dataframe(del_formatted)
        
        st.subheader("Revoke Delegation")
        del_ids = [d["_id"] for d in del_formatted]
        revoke_id = st.selectbox("Select Delegation to Revoke", del_ids)
        if st.button("Revoke Delegation"):
            try:
                revoke_delegation(db, admin_id, revoke_id)
                st.success("Delegation revoked successfully")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {str(e)}")

    else:
        st.write("No active delegations")