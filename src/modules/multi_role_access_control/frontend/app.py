import streamlit as st

from ui_pages.dashboard import show_dashboard
from ui_pages.users_page import show_users_page
from ui_pages.roles_page import show_roles_page
from ui_pages.delegation_page import show_delegation_page

from components.sidebar import render_sidebar


def main():

    st.set_page_config(
        page_title="Multi Role Access Control",
        layout="wide"
    )

    render_sidebar()

    page = st.session_state.get("page", "Dashboard")

    if page == "Dashboard":
        show_dashboard()

    elif page == "Users":
        show_users_page()

    elif page == "Roles":
        show_roles_page()

    elif page == "Delegation":
        show_delegation_page()


if __name__ == "__main__":
    main()