import streamlit as st


def render_sidebar():

    st.sidebar.title("Access Control")
    perms = st.session_state.get("permissions", [])

    if st.sidebar.button("Dashboard"):
        st.session_state["page"] = "Dashboard"

    if "MANAGE_USERS" in perms or "Admin" in st.session_state.get("role", ""):
        if st.sidebar.button("Users"):
            st.session_state["page"] = "Users"

    if "MANAGE_ROLES" in perms or "Admin" in st.session_state.get("role", ""):
        if st.sidebar.button("Roles"):
            st.session_state["page"] = "Roles"

    if "MANAGE_DELEGATIONS" in perms or "Admin" in st.session_state.get("role", ""):
        if st.sidebar.button("Delegation"):
            st.session_state["page"] = "Delegation"
            
    st.sidebar.divider()
    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.session_state["page"] = "login"
        st.rerun()