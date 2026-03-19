import streamlit as st
# from backend.services.user_service import get_all_users
# from backend.services.role_service import get_all_roles
# from backend.services.access_control_service import get_active_delegations
from backend.database import get_db_connection
from admin_service import (
    get_all_users,
    get_all_roles,
    get_active_delegations
)

def show_dashboard():

    st.title("System Dashboard")

    db = get_db_connection()
    users = get_all_users(db)
    roles = get_all_roles(db)
    delegations = get_active_delegations(db)

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
        st.write(f"{user.get('Username')} - {user.get('Email')}")