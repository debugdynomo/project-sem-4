# components/sidebar.py
"""
Sidebar navigation with cookie-based section persistence.
Saves current_section cookie on every navigation change so
the user returns to the same sub-page after a refresh.
Deletes both user_id and current_section cookies on logout.

PERMISSION-DRIVEN: Menu items are dynamically included based on the
user's effective permissions, not hardcoded role names.
"""
import streamlit as st
import extra_streamlit_components as stx
from streamlit_option_menu import option_menu
from components.permission_guard import role_indicator, delegation_indicator, has_permission
from backend.database import get_db_connection

# ── Permission-to-menu-item mapping ──
# Each menu item requires the user to hold at least one of the listed permissions.
# Items without a mapping are shown to all authenticated users.
MENU_PERMISSIONS = {
    "User Management":          ["CREATE_USER"],
    "Role Management":          ["CREATE_USER"],
    "Delegation Console (G5)":  ["APPROVE_DELEGATION"],
    "Access Recertification":   ["VIEW_AUDIT_LOGS"],
    "Override Tracking":        ["VIEW_AUDIT_LOGS"],
    "System Audit":             ["VIEW_AUDIT_LOGS"],
}

# ── Base menus per role category ──
_PATIENT_BASE = ["Dashboard", "Privacy & Consent (G5)", "My Access Logs"]
_DOCTOR_BASE  = ["Clinical Overview", "My Permissions", "Delegation Center (G5)", "Emergency Break-Glass", "Patient Access Logs"]
_ADMIN_BASE   = ["Dashboard", "User Management", "Role Management", "Delegation Console (G5)", "Access Recertification", "Override Tracking", "System Audit"]


def _build_menu(role, perms):
    """Build the sidebar menu dynamically based on role and permissions."""
    # Start with role-appropriate base menu
    if role == "Patient":
        candidates = list(_PATIENT_BASE)
    elif role in ("Admin", "System_Admin"):
        candidates = list(_ADMIN_BASE)
    else:
        # Doctor / Lead_Doctor / Nurse — start with doctor base
        candidates = list(_DOCTOR_BASE)

        # Dynamically add admin-level items if user has the required permissions
        # (e.g. via delegation granting CREATE_USER or APPROVE_DELEGATION)
        if has_permission("APPROVE_DELEGATION"):
            if "Approve Delegations" not in candidates:
                candidates.insert(2, "Approve Delegations")
        
        for admin_item in ["User Management", "Role Management", "System Audit"]:
            required = MENU_PERMISSIONS.get(admin_item, [])
            if required and any(has_permission(p) for p in required):
                if admin_item not in candidates:
                    candidates.append(admin_item)

    # Filter: remove items that require permissions the user doesn't have
    final_items = []
    for item in candidates:
        required = MENU_PERMISSIONS.get(item)
        if required:
            if any(has_permission(p) for p in required):
                final_items.append(item)
        else:
            # No permission requirement — always include
            final_items.append(item)

    final_items.append("Logout")
    return final_items


def sidebar(menu_items=None):
    cookie_manager = stx.CookieManager(key="sidebar_cookies")
    role = st.session_state.get('role')
    perms = st.session_state.get('permissions', [])

    # Build menu dynamically from permissions
    if menu_items is None:
        menu_items = _build_menu(role, perms)

    # ---------- Determine default_index from cookie ----------
    restored_section = st.session_state.get("current_section")
    default_idx = 0
    if restored_section and restored_section in menu_items:
        default_idx = menu_items.index(restored_section)

    with st.sidebar:
        st.markdown("## 🏥 MediCare")

        # ── Role badge + permission count ──
        role_indicator()

        # ── Delegation indicator ──
        try:
            db = get_db_connection()
            delegation_indicator(db)
        except Exception:
            pass

        st.divider()

        default_icons = ["house", "shield", "activity", "people", "key", "list", "gear", "eye", "alert-triangle"]
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