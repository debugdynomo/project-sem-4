import streamlit as st
from datetime import datetime

# from backend.services.user_service import get_all_users
# from backend.services.role_service import get_all_roles
# from backend.services.access_control_service import create_delegation, get_active_delegations
from mock_backend.services import get_all_users
from mock_backend.services import get_all_roles
from mock_backend.services import get_active_delegations, create_delegation


def show_delegation_page():

    st.title("Role Delegation")

    st.subheader("Create Delegation")

    users = get_all_users()
    roles = get_all_roles()

    user_names = [u["username"] for u in users]
    role_names = [r["role_name"] for r in roles]

    delegator = st.selectbox("Delegator (From User)", user_names)
    delegatee = st.selectbox("Delegatee (To User)", user_names)
    role = st.selectbox("Role to Delegate", role_names)

    start_date = st.date_input("Start Date")
    end_date = st.date_input("End Date")

    reason = st.text_input("Reason")

    if st.button("Create Delegation"):

        if delegator != delegatee:

            create_delegation(
                delegator,
                delegatee,
                role,
                datetime.combine(start_date, datetime.min.time()),
                datetime.combine(end_date, datetime.min.time()),
                reason
            )

            st.success("Delegation created successfully")

        else:
            st.error("Delegator and Delegatee cannot be same")

    st.divider()

    st.subheader("Active Delegations")

    delegations = get_active_delegations()

    if delegations:
        st.dataframe(delegations)
    else:
        st.write("No active delegations")