"""
app.py — Main Streamlit entry point with persistent login & section restore via cookies.
Uses extra-streamlit-components CookieManager to survive page refreshes.
"""
import streamlit as st
import extra_streamlit_components as stx
from auth.login import login_page
from auth.signup import signup_page
from dashboards.patient_dashboard import patient_dashboard
from dashboards.doctor_dashboard import doctor_dashboard
from dashboards.admin_dashboard import admin_dashboard
from backend.database import get_db_connection
from backend.rbac import get_effective_permissions
from bson.objectid import ObjectId

# ---------------- PAGE CONFIG ----------------
st.set_page_config(page_title="MediCare", layout="wide")

# ---------------- APPLY PREMIUM UI ----------------
from components.ui_config import apply_premium_ui
apply_premium_ui()

# ---------------- COOKIE MANAGER ----------------
cookie_manager = stx.CookieManager()

# ---------------- SESSION STATE DEFAULTS ----------------
st.session_state.setdefault("logged_in", False)
st.session_state.setdefault("page", "login")
st.session_state.setdefault("role", None)

# ---------------- PERSISTENT LOGIN RESTORE ----------------
# CookieManager is an async component: on the 1st render after refresh,
# its JS hasn't communicated back yet so .get() returns None.
# It auto-triggers a rerun once loaded.  We use a render counter so that
# we only attempt the DB restore after the component has had a chance to load.
st.session_state.setdefault("_cookie_render_count", 0)
st.session_state.setdefault("_logged_out", False)

if not st.session_state.logged_in and not st.session_state._logged_out:
    st.session_state._cookie_render_count += 1

    # On the very first render the component JS hasn't loaded yet —
    # skip and let the auto-rerun bring us back with real cookie data.
    if st.session_state._cookie_render_count >= 2:
        saved_user_id = cookie_manager.get("user_id")
        saved_section = cookie_manager.get("current_section")

        if saved_user_id and saved_user_id != "":
            try:
                db = get_db_connection()
                user = db["users"].find_one({"_id": ObjectId(saved_user_id)})

                if user and user.get("Status") == "Active":
                    # Priority-based role resolution (matches login.py)
                    ROLE_PRIORITY = {"Admin": 0, "System_Admin": 0, "Lead_Doctor": 1, "Doctor": 2, "Nurse": 2, "Patient": 9}
                    role = "Patient"
                    best_priority = 99

                    for role_item in user.get("Assigned_Roles", []):
                        r_id = role_item.get("role_id") if isinstance(role_item, dict) else role_item
                        role_doc = db["roles"].find_one({"_id": r_id})
                        if role_doc:
                            r_name = role_doc.get("Role_name", "Patient")
                            priority = ROLE_PRIORITY.get(r_name, 5)
                            if priority < best_priority:
                                best_priority = priority
                                role = r_name

                    # Resolve permissions
                    perms = get_effective_permissions(user["_id"], db)

                    # Restore session state
                    st.session_state.logged_in = True
                    st.session_state.role = role
                    st.session_state.user_id = str(user["_id"])
                    st.session_state.username = user.get("Username")
                    st.session_state.permissions = perms
                    st.session_state.page = "dashboard"

                    # Restore the section/sub-page the user was on
                    if saved_section and saved_section != "":
                        st.session_state.current_section = saved_section

                    st.rerun()
                else:
                    # User no longer exists or is deactivated — clear stale cookies
                    cookie_manager.delete("user_id", key="app_del_uid_1")
                    cookie_manager.delete("current_section", key="app_del_sec_1")
            except Exception:
                # Invalid cookie data (e.g., bad ObjectId) — clear it
                cookie_manager.delete("user_id", key="app_del_uid_2")
                cookie_manager.delete("current_section", key="app_del_sec_2")

# ---------------- HARD REDIRECT AFTER LOGIN ----------------
if st.session_state.logged_in:
    role = st.session_state.role
    if role == "Patient":
        patient_dashboard()
        st.stop()
    elif role in ("Doctor", "Nurse"):
        doctor_dashboard()
        st.stop()
    elif role in ("Lead_Doctor", "Lead Doctor"):
        doctor_dashboard()   # Lead Doctor uses the doctor dashboard (with extra capabilities)
        st.stop()
    elif role in ("Admin", "System_Admin"):
        admin_dashboard()
        st.stop()
    else:
        # Unknown role — show doctor dashboard as safe default and warn
        st.warning(f"Unrecognized role '{role}'. Defaulting to Doctor view.")
        doctor_dashboard()
        st.stop()

# ---------------- AUTH ROUTING ----------------
if st.session_state.page == "login":
    login_page()
elif st.session_state.page == "signup":
    signup_page()
