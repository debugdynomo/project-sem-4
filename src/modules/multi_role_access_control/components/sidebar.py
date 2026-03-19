# components/sidebar.py
import streamlit as st
from streamlit_option_menu import option_menu

def sidebar(menu_items=None):
    role = st.session_state.get('role')
    
    if role == 'Patient':
        menu_items = ["Dashboard", "Privacy & Consent (G5)", "My Access Logs", "Logout"]
    elif role == 'Admin' or role == 'System_Admin':
        menu_items = ["Dashboard", "User Management", "Role Management", "Delegation Console (G5)", "System Audit", "Logout"]
    else:
        if not menu_items:
            menu_items = ["Dashboard", "Logout"]
            
    with st.sidebar:
        st.markdown("## 🏥 MediCare")
        
        default_icons = ["house", "shield", "activity", "people", "key", "list"]
        icons = default_icons[:len(menu_items)]
        if len(menu_items) > len(default_icons):
            icons.extend(["circle"] * (len(menu_items) - len(default_icons)))
            
        selected = option_menu(
            "",
            menu_items,
            icons=icons,
            default_index=0
        )

        if selected == "Logout" or st.button("Logout (Fallback)"):
            st.session_state.logged_in = False
            st.session_state.page = "login"
            st.session_state.role = None
            st.session_state.view = "main"
            st.session_state.selected_category = None
            st.session_state.selected_module = None
            st.rerun()

    return selected