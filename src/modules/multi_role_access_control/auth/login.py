"""
auth/login.py — Streamlit login page wired to MongoDB backend.
Sets user_id cookie on successful login for persistent sessions.
"""
import hashlib

import streamlit as st
import extra_streamlit_components as stx
from backend.database import get_db_connection
from backend.audit import log_audit_event
from backend.rbac import get_effective_permissions



def login_page():
    st.title("🏥 MediCare Login")

    cookie_manager = stx.CookieManager(key="login_cookies")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        if not username or not password:
            st.error("Please enter username and password")
            return

        db = get_db_connection()

        # Look up user by Username (PascalCase — matches DB schema)
        user = db["users"].find_one({"Username": username})

        if user is None:
            st.error("❌ User not found. Check your username.")
            log_audit_event(db, action="LOGIN_FAILED", target_entity="auth",
                            status="FAILED", details={"reason": "user_not_found", "username": username})
            return

        # Hash the password attempt (SHA-256) to match signup.py's storage format
        stored_pw = user.get("Hashed_password", "")
        attempt_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
        if stored_pw != attempt_hash:
            st.error("❌ Incorrect password.")
            log_audit_event(db, action="LOGIN_FAILED", user_id=str(user["_id"]),
                            target_entity="auth", status="FAILED",
                            details={"reason": "wrong_password"})
            return

        # Resolve effective permissions via $graphLookup
        perms = get_effective_permissions(user["_id"], db)
        
        # Calculate Primary Role strictly from MongoDB database to prevent UI override spoofing
        role = "Patient" # Fallback safety
        if user.get("Assigned_Roles") and len(user["Assigned_Roles"]) > 0:
            first_role = user["Assigned_Roles"][0]
            r_id = first_role.get("role_id") if isinstance(first_role, dict) else first_role
            role_doc = db["roles"].find_one({"_id": r_id})
            if role_doc:
                role = role_doc.get("Role_name", "Patient")

        st.session_state.logged_in = True
        st.session_state.role = role
        st.session_state.user_id = str(user["_id"])
        st.session_state.username = user.get("Username")
        st.session_state.permissions = perms
        st.session_state.page = "dashboard"
        st.session_state._logged_out = False

        # ---- PERSIST LOGIN TO COOKIE ----
        cookie_manager.set("user_id", str(user["_id"]))

        log_audit_event(db, action="LOGIN_SUCCESS", user_id=str(user["_id"]),
                        target_entity="auth", status="SUCCESS")

        st.success(f"✅ Welcome, {user.get('Username')}!  Permissions: {perms}")
        st.rerun()

    st.markdown("Don't have an account?")
    if st.button("Signup"):
        st.session_state.page = "signup"
        st.rerun()
