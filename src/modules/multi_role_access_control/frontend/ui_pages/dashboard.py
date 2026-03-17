import streamlit as st
# from backend.services.user_service import get_all_users
# from backend.services.role_service import get_all_roles
# from backend.services.access_control_service import get_active_delegations
from mock_backend.services import get_all_users
from mock_backend.services import get_all_roles
from mock_backend.services import get_active_delegations

def show_dashboard():

    st.title("System Dashboard")

    users = get_all_users()
    roles = get_all_roles()
    delegations = get_active_delegations()

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total Users", len(users))

    with col2:
        st.metric("Total Roles", len(roles))

    with col3:
        st.metric("Active Delegations", len(delegations))

    st.divider()

    st.subheader("Recent Users")

    for user in users[:5]:
        st.write(f"{user['username']} - {user['email']}")