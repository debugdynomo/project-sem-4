import streamlit as st


def render_sidebar():

    st.sidebar.title("Access Control")

    if st.sidebar.button("Dashboard"):
        st.session_state["page"] = "Dashboard"

    if st.sidebar.button("Users"):
        st.session_state["page"] = "Users"

    if st.sidebar.button("Roles"):
        st.session_state["page"] = "Roles"

    if st.sidebar.button("Delegation"):
        st.session_state["page"] = "Delegation"