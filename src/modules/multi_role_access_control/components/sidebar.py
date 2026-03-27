# components/sidebar.py
"""
Sidebar navigation with cookie-based section persistence.
Saves current_section cookie on every navigation change so
the user returns to the same sub-page after a refresh.
Deletes both user_id and current_section cookies on logout.
"""
import streamlit as st
import extra_streamlit_components as stx
from streamlit_option_menu import option_menu



def sidebar(menu_items=None):
    cookie_manager = stx.CookieManager(key="sidebar_cookies")
    role = st.session_state.get('role')

    if role == 'Patient':
        menu_items = ["Dashboard", "Privacy & Consent (G5)", "My Access Logs", "Logout"]
    elif role == 'Admin' or role == 'System_Admin':
        menu_items = ["Dashboard", "User Management", "Role Management", "Delegation Console (G5)", "System Audit", "Logout"]
    else:
        if not menu_items:
            menu_items = ["Dashboard", "Logout"]

    # ---------- Determine default_index from cookie ----------
    # If a current_section was restored from cookie, jump to that index
    restored_section = st.session_state.get("current_section")
    default_idx = 0
    if restored_section and restored_section in menu_items:
        default_idx = menu_items.index(restored_section)

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
            default_index=default_idx
        )

        # ---------- Persist section to cookie on change ----------
        if selected and selected != "Logout":
            prev = st.session_state.get("_last_cookie_section")
            if selected != prev:
                cookie_manager.set("current_section", selected)
                st.session_state._last_cookie_section = selected

        # ---------- Logout: clear session AND cookies ----------
        if selected == "Logout" or st.button("Logout (Fallback)"):
            # Delete cookies — these render as components that send JS commands
            cookie_manager.delete("user_id", key="delete_user_id")
            cookie_manager.delete("current_section", key="delete_current_section")

            # Reset session state
            st.session_state.logged_in = False
            st.session_state.page = "login"
            st.session_state.role = None
            st.session_state.view = "main"
            st.session_state.selected_category = None
            st.session_state.selected_module = None
            st.session_state.current_section = None
            st.session_state._cookie_render_count = 0
            st.session_state._logged_out = True

            # IMPORTANT: Do NOT use st.rerun() here!
            # st.rerun() discards the current render, so the delete components
            # would never reach the browser.  st.stop() completes the render,
            # the browser JS deletes the cookies, then auto-triggers a rerun.
            st.stop()

    return selected